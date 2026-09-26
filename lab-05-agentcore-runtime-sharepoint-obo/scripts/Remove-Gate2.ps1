[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath,
    [ValidateRange(60, 3600)][int] $TimeoutSeconds = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')
. (Join-Path $PSScriptRoot 'Aws.ps1')
. (Join-Path $PSScriptRoot 'Cleanup.ps1')

$binding = Get-GateBinding -Path $BindingPath
$names = Get-ExperimentNames
$statePath = Get-StatePath -BindingPath $BindingPath
$state = Read-ExperimentState -Path $statePath
$labRoot = Split-Path -Parent $PSScriptRoot

if ($binding.CleanupWriteApproval -ne 'approved') {
    throw 'The ignored binding does not approve Gate 2 cleanup.'
}
if (-not $state.ContainsKey('gate2')) {
    Write-Output '{"gate2Cleanup":"already-absent"}'
    exit 0
}
$gate2 = $state['gate2']
if (
    $gate2['azureSecretSoftDeleted'] -and
    (-not $state.ContainsKey('entra') -or -not $state.ContainsKey('aws'))
) {
    az account set --subscription $binding.AzureSubscriptionId --only-show-errors
    if ($LASTEXITCODE -ne 0) {
        throw 'The Azure subscription context could not be selected.'
    }
    $deletedSecret = Invoke-BoundedAz `
        -Arguments @(
            'keyvault', 'secret', 'show-deleted',
            '--subscription', $binding.AzureSubscriptionId,
            '--vault-name', $binding.KeyVaultName,
            '--name', $names.TransportSecret,
            '--only-show-errors',
            '--output', 'json'
        ) `
        -TimeoutSeconds 60 `
        -AllowNotFound
    if ($deletedSecret) {
        if (
            [string]$deletedSecret.kid -ne
                [string]$gate2['azureSecretId']
        ) {
            throw 'The soft-deleted Key Vault secret does not match state.'
        }
        Write-Output '{"gate2Cleanup":"pending-platform-purge"}'
        exit 0
    }
    $state.Remove('gate2')
    Save-ExperimentState -Path $statePath -State $state
    Write-Output '{"gate2Cleanup":"complete"}'
    exit 0
}
if (-not $state.ContainsKey('entra') -or -not $state.ContainsKey('aws')) {
    throw 'Gate 2 cleanup requires the retained identity and AWS state.'
}
$entra = $state['entra']

function ConvertTo-CanonicalRequiredResourceAccess {
    param([object[]] $Value)

    return @(
        $Value |
            ForEach-Object {
                [ordered]@{
                    resourceAppId = [string]$_.resourceAppId
                    resourceAccess = @(
                        $_.resourceAccess |
                            ForEach-Object {
                                [ordered]@{
                                    id = [string]$_.id
                                    type = [string]$_.type
                                }
                            } |
                            Sort-Object id, type
                    )
                }
            } |
            Sort-Object resourceAppId
    ) | ConvertTo-Json -Depth 20 -Compress
}

az account set --subscription $binding.AzureSubscriptionId --only-show-errors
if ($LASTEXITCODE -ne 0) {
    throw 'The Azure subscription context could not be selected.'
}
Connect-MgGraph -TenantId $binding.TenantId -Scopes @(
    'AgentIdentityBlueprint.ReadWrite.All'
    'AgentIdentityBlueprint.UpdateAuthProperties.All'
    'AgentIdentityBlueprint.AddRemoveCreds.All'
    'AppRoleAssignment.ReadWrite.All'
    'DelegatedPermissionGrant.ReadWrite.All'
    'Sites.FullControl.All'
    'Application.Read.All'
) -UseDeviceCode -ContextScope CurrentUser -NoWelcome
$context = Get-MgContext
if (-not $context -or $context.TenantId -ne $binding.TenantId) {
    throw 'The Microsoft Graph context does not match the binding.'
}

& (Join-Path $PSScriptRoot 'Stop-RuntimeSessions.ps1') `
    -BindingPath $BindingPath `
    -TimeoutSeconds ([Math]::Min($TimeoutSeconds, 600))

& (Join-Path $PSScriptRoot 'Deploy-Gate1.ps1') `
    -BindingPath $BindingPath `
    -TimeoutSeconds $TimeoutSeconds
$state = Read-ExperimentState -Path $statePath
$gate2 = $state['gate2']
if (-not $gate2.ContainsKey('runtimeDetached')) {
    $gate2['runtimeDetached'] = $true
    Save-ExperimentState -Path $statePath -State $state
}

if ($gate2['sitePermissionId'] -and $gate2['siteId']) {
    $permissionUri = (
        "https://graph.microsoft.com/v1.0/sites/$($gate2['siteId'])" +
        "/permissions/$($gate2['sitePermissionId'])"
    )
    $permission = Invoke-BoundedGraph `
        -Method GET `
        -Uri $permissionUri `
        -TimeoutSeconds 60 `
        -ExpectedStatus @(200) `
        -AllowNotFound
    if ($permission) {
        $grantees = @(
            $permission.grantedToIdentitiesV2 |
                ForEach-Object { [string]$_.application.id }
        )
        if ($entra['agentIdentityAppId'] -notin $grantees) {
            throw 'The selected-site grant does not belong to the experiment child identity.'
        }
        $null = Invoke-BoundedGraph `
            -Method DELETE `
            -Uri $permissionUri `
            -TimeoutSeconds 60 `
            -ExpectedStatus @(204)
    }
    Assert-GraphAbsent -Uri $permissionUri
    $gate2.Remove('sitePermissionId')
    Save-ExperimentState -Path $statePath -State $state
}

if ($gate2['graphDelegatedGrantId']) {
    $grantUri = (
        'https://graph.microsoft.com/v1.0/oauth2PermissionGrants/' +
        [string]$gate2['graphDelegatedGrantId']
    )
    $grant = Invoke-BoundedGraph `
        -Method GET `
        -Uri $grantUri `
        -TimeoutSeconds 60 `
        -ExpectedStatus @(200) `
        -AllowNotFound
    if ($grant) {
        if (
            [string]$grant.clientId -ne [string]$entra['blueprintPrincipalId']
        ) {
            throw 'The delegated grant client does not match the experiment Blueprint principal.'
        }
        $previousScope = [string]$gate2['graphDelegatedGrantPreviousScope']
        if ([string]::IsNullOrWhiteSpace($previousScope)) {
            $null = Invoke-BoundedGraph `
                -Method DELETE `
                -Uri $grantUri `
                -TimeoutSeconds 60 `
                -ExpectedStatus @(204)
            Assert-GraphAbsent -Uri $grantUri
        }
        else {
            $null = Invoke-BoundedGraph `
                -Method PATCH `
                -Uri $grantUri `
                -Body @{ scope = $previousScope } `
                -TimeoutSeconds 60 `
                -ExpectedStatus @(200, 204)
            $restored = Invoke-BoundedGraph `
                -Method GET `
                -Uri $grantUri `
                -TimeoutSeconds 60 `
                -ExpectedStatus @(200)
            if ([string]$restored.scope -ne $previousScope) {
                throw 'The delegated grant was not restored to its previous scope.'
            }
        }
    }
    $gate2.Remove('graphDelegatedGrantId')
    $gate2.Remove('graphDelegatedGrantPreviousScope')
    $gate2.Remove('gate4LabelPreviousGrantScope')
    $gate2.Remove('gate4LabelDelegatedGrantConfigured')
    Save-ExperimentState -Path $statePath -State $state
}

if ($gate2['graphInheritanceConfigured']) {
    $inheritanceUri = (
        'https://graph.microsoft.com/v1.0/applications/' +
        "microsoft.graph.agentIdentityBlueprint/$($entra['blueprintObjectId'])" +
        '/inheritablePermissions/00000003-0000-0000-c000-000000000000'
    )
    $existing = Invoke-BoundedGraph `
        -Method GET `
        -Uri $inheritanceUri `
        -Headers @{ 'OData-Version' = '4.0' } `
        -TimeoutSeconds 60 `
        -ExpectedStatus @(200) `
        -AllowNotFound
    if ($existing) {
        $null = Invoke-BoundedGraph `
            -Method DELETE `
            -Uri $inheritanceUri `
            -Headers @{ 'OData-Version' = '4.0' } `
            -TimeoutSeconds 60 `
            -ExpectedStatus @(204)
    }
    Assert-GraphAbsent -Uri $inheritanceUri
    $gate2.Remove('graphInheritanceConfigured')
    Save-ExperimentState -Path $statePath -State $state
}

if ($gate2['requiredResourceAccessConfigured']) {
    $blueprintUri = (
        "https://graph.microsoft.com/v1.0/applications/" +
        "$($entra['blueprintObjectId'])"
    )
    $previousAccess = @($gate2['previousRequiredResourceAccess'])
    $null = Invoke-BoundedGraph `
        -Method PATCH `
        -Uri $blueprintUri `
        -Body @{ requiredResourceAccess = $previousAccess } `
        -TimeoutSeconds 60 `
        -ExpectedStatus @(204)
    $restored = Invoke-BoundedGraph `
        -Method GET `
        -Uri "${blueprintUri}?`$select=requiredResourceAccess" `
        -TimeoutSeconds 60 `
        -ExpectedStatus @(200)
    $expectedJson = ConvertTo-CanonicalRequiredResourceAccess `
        -Value $previousAccess
    $actualJson = ConvertTo-CanonicalRequiredResourceAccess `
        -Value @($restored.requiredResourceAccess)
    if ($actualJson -ne $expectedJson) {
        throw 'The Blueprint requiredResourceAccess was not restored.'
    }
    $gate2.Remove('requiredResourceAccessConfigured')
    $gate2.Remove('gate4LabelRequiredResourceAccessConfigured')
    $gate2.Remove('previousRequiredResourceAccess')
    Save-ExperimentState -Path $statePath -State $state
}

if ($gate2['ficId']) {
    $ficUri = (
        "https://graph.microsoft.com/beta/applications(appId='" +
        "$($entra['blueprintAppId'])')/federatedIdentityCredentials/" +
        "$($gate2['ficId'])"
    )
    $fic = Invoke-BoundedGraph `
        -Method GET `
        -Uri $ficUri `
        -TimeoutSeconds 60 `
        -ExpectedStatus @(200) `
        -AllowNotFound
    if ($fic) {
        if (
            [string]$fic.name -ne $names.Fic -or
            [string]$fic.subject -ne [string]$gate2['managedIdentityPrincipalId']
        ) {
            throw 'The federated credential does not match issue-206 ownership.'
        }
        $null = Invoke-BoundedGraph `
            -Method DELETE `
            -Uri $ficUri `
            -TimeoutSeconds 60 `
            -ExpectedStatus @(204)
    }
    Assert-GraphAbsent -Uri $ficUri
    $gate2.Remove('ficId')
    Save-ExperimentState -Path $statePath -State $state
}

$appRoleSpecs = @(
    @{
        Key = 'gate4LabelV1ManagedIdentityAppRoleConfigured'
        Value = 'SensitivityLabel.Read'
    },
    @{
        Key = 'gate4LabelManagedIdentityAppRoleConfigured'
        Value = 'InformationProtectionPolicy.Read.All'
    }
)
$pendingAppRoles = @(
    $appRoleSpecs |
        Where-Object { $gate2.ContainsKey($_.Key) }
)
if ($pendingAppRoles.Count -gt 0) {
    $managedIdentityId = [string]$gate2['managedIdentityPrincipalId']
    if (-not $managedIdentityId) {
        throw 'Managed identity state is missing before Graph app-role cleanup.'
    }
    $graphServicePrincipal = Invoke-BoundedGraph `
        -Method GET `
        -Uri (
            "https://graph.microsoft.com/v1.0/servicePrincipals" +
            "(appId='00000003-0000-0000-c000-000000000000')" +
            '?$select=id,appRoles'
        ) `
        -TimeoutSeconds 60 `
        -ExpectedStatus @(200)
    $assignmentsUri = (
        "https://graph.microsoft.com/v1.0/servicePrincipals/$managedIdentityId" +
        '/appRoleAssignments'
    )
    $assignments = Invoke-BoundedGraph `
        -Method GET `
        -Uri $assignmentsUri `
        -TimeoutSeconds 60 `
        -ExpectedStatus @(200)
    foreach ($roleSpec in $pendingAppRoles) {
        $role = @(
            $graphServicePrincipal.appRoles |
                Where-Object { $_.value -eq $roleSpec.Value }
        )
        if ($role.Count -ne 1) {
            throw "The Graph $($roleSpec.Value) role could not be resolved."
        }
        $matches = @(
            $assignments.value |
                Where-Object {
                    [string]$_.principalId -eq $managedIdentityId -and
                    [string]$_.resourceId -eq
                        [string]$graphServicePrincipal.id -and
                    [string]$_.appRoleId -eq [string]$role[0].id
                }
        )
        if ($matches.Count -gt 1) {
            throw "The Graph $($roleSpec.Value) assignment is duplicated."
        }
        if ($matches.Count -eq 1) {
            $assignmentUri = (
                "https://graph.microsoft.com/v1.0/servicePrincipals/" +
                "$managedIdentityId/appRoleAssignments/$($matches[0].id)"
            )
            $null = Invoke-BoundedGraph `
                -Method DELETE `
                -Uri $assignmentUri `
                -TimeoutSeconds 60 `
                -ExpectedStatus @(204)
            Assert-GraphAbsent -Uri $assignmentUri
        }
        $gate2.Remove($roleSpec.Key)
        Save-ExperimentState -Path $statePath -State $state
    }
}

$containerApp = Invoke-BoundedAz `
    -Arguments @(
        'containerapp', 'show',
        '--subscription', $binding.AzureSubscriptionId,
        '--resource-group', $binding.AzureResourceGroup,
        '--name', $names.ContainerApp,
        '--only-show-errors',
        '--output', 'json'
    ) `
    -TimeoutSeconds 60 `
    -AllowNotFound
if ($containerApp) {
    if (
        [string]$containerApp.id -ne [string]$gate2['containerAppResourceId'] -or
        [string]$containerApp.identity.principalId -ne $managedIdentityId
    ) {
        throw 'The live Container App identity does not match ignored state.'
    }
}

foreach ($assignmentSpec in @(
        @{
            Key = 'acrPullRoleAssignmentId'
            ExpectedRole = 'AcrPull'
        },
        @{
            Key = 'keyVaultRoleAssignmentId'
            ExpectedRole = 'Key Vault Secrets User'
        }
    )) {
    $assignmentId = [string]$gate2[$assignmentSpec.Key]
    if (-not $assignmentId) {
        continue
    }
    $assignment = Invoke-BoundedAz `
        -Arguments @(
            'role', 'assignment', 'list',
            '--subscription', $binding.AzureSubscriptionId,
            '--all',
            '--query', "[?id=='$assignmentId']",
            '--only-show-errors',
            '--output', 'json'
        ) `
        -TimeoutSeconds 60
    if (@($assignment).Count -gt 1) {
        throw 'The Azure role assignment ID returned multiple objects.'
    }
    if (@($assignment).Count -eq 1) {
        if (
            [string]$assignment[0].principalId -ne $managedIdentityId -or
            [string]$assignment[0].roleDefinitionName -ne
                [string]$assignmentSpec.ExpectedRole
        ) {
            throw 'The Azure role assignment does not match issue-206 ownership.'
        }
        $null = Invoke-BoundedAz `
            -Arguments @(
                'role', 'assignment', 'delete',
                '--subscription', $binding.AzureSubscriptionId,
                '--ids', $assignmentId,
                '--only-show-errors'
            ) `
            -TimeoutSeconds 60 `
            -Raw
    }
    $remaining = Invoke-BoundedAz `
        -Arguments @(
            'role', 'assignment', 'list',
            '--subscription', $binding.AzureSubscriptionId,
            '--all',
            '--query', "[?id=='$assignmentId']",
            '--only-show-errors',
            '--output', 'json'
        ) `
        -TimeoutSeconds 60
    if (@($remaining).Count -ne 0) {
        throw 'An Azure role assignment remains after deletion.'
    }
    $gate2.Remove($assignmentSpec.Key)
    Save-ExperimentState -Path $statePath -State $state
}

if ($containerApp) {
    $null = Invoke-BoundedAz `
        -Arguments @(
            'containerapp', 'delete',
            '--subscription', $binding.AzureSubscriptionId,
            '--resource-group', $binding.AzureResourceGroup,
            '--name', $names.ContainerApp,
            '--yes',
            '--only-show-errors'
        ) `
        -TimeoutSeconds 120 `
        -Raw
    Wait-Until `
        -TimeoutSeconds $TimeoutSeconds `
        -FailureMessage 'The owned Container App still exists after deletion.' `
        -Test {
            $null -eq (Invoke-BoundedAz `
                -Arguments @(
                    'containerapp', 'show',
                    '--subscription', $binding.AzureSubscriptionId,
                    '--resource-group', $binding.AzureResourceGroup,
                    '--name', $names.ContainerApp,
                    '--only-show-errors',
                    '--output', 'json'
                ) `
                -TimeoutSeconds 60 `
                -AllowNotFound)
        }
}
$gate2.Remove('containerAppResourceId')
$gate2.Remove('managedIdentityPrincipalId')
$gate2.Remove('fqdn')
$gate2.Remove('mcpUrl')
Save-ExperimentState -Path $statePath -State $state

if ($gate2['azureSecretId']) {
    $secret = Invoke-BoundedAz `
        -Arguments @(
            'keyvault', 'secret', 'show',
            '--subscription', $binding.AzureSubscriptionId,
            '--vault-name', $binding.KeyVaultName,
            '--name', $names.TransportSecret,
            '--only-show-errors',
            '--output', 'json'
        ) `
        -TimeoutSeconds 60 `
        -AllowNotFound
    if ($secret -and [string]$secret.id -ne [string]$gate2['azureSecretId']) {
        throw 'The Key Vault secret ID does not match ignored state.'
    }
    if ($secret) {
        $null = Invoke-BoundedAz `
            -Arguments @(
                'keyvault', 'secret', 'delete',
                '--subscription', $binding.AzureSubscriptionId,
                '--vault-name', $binding.KeyVaultName,
                '--name', $names.TransportSecret,
                '--only-show-errors',
                '--output', 'json'
            ) `
            -TimeoutSeconds 120
    }
    Wait-Until `
        -TimeoutSeconds $TimeoutSeconds `
        -FailureMessage 'The owned Key Vault secret remains active.' `
        -Test {
            $null -eq (Invoke-BoundedAz `
                -Arguments @(
                    'keyvault', 'secret', 'show',
                    '--subscription', $binding.AzureSubscriptionId,
                    '--vault-name', $binding.KeyVaultName,
                    '--name', $names.TransportSecret,
                    '--only-show-errors',
                    '--output', 'json'
                ) `
                -TimeoutSeconds 60 `
                -AllowNotFound)
        }
    $vault = Invoke-BoundedAz `
        -Arguments @(
            'keyvault', 'show',
            '--subscription', $binding.AzureSubscriptionId,
            '--resource-group', $binding.KeyVaultResourceGroup,
            '--name', $binding.KeyVaultName,
            '--only-show-errors',
            '--output', 'json'
        ) `
        -TimeoutSeconds 60
    if ($vault.properties.enablePurgeProtection -eq $true) {
        $deletedSecret = Invoke-BoundedAz `
            -Arguments @(
                'keyvault', 'secret', 'show-deleted',
                '--subscription', $binding.AzureSubscriptionId,
                '--vault-name', $binding.KeyVaultName,
                '--name', $names.TransportSecret,
                '--only-show-errors',
                '--output', 'json'
            ) `
            -TimeoutSeconds 60
        if (
            [string]$deletedSecret.kid -ne
                [string]$gate2['azureSecretId']
        ) {
            throw 'The soft-deleted Key Vault secret does not match state.'
        }
        $gate2['azureSecretSoftDeleted'] = $true
        $gate2['azureSecretScheduledPurgeDate'] = (
            [string]$deletedSecret.scheduledPurgeDate
        )
    }
    else {
        $null = Invoke-BoundedAz `
            -Arguments @(
                'keyvault', 'secret', 'purge',
                '--subscription', $binding.AzureSubscriptionId,
                '--vault-name', $binding.KeyVaultName,
                '--name', $names.TransportSecret,
                '--only-show-errors'
            ) `
            -TimeoutSeconds 120 `
            -AllowNotFound `
            -Raw
        Wait-Until `
            -TimeoutSeconds $TimeoutSeconds `
            -FailureMessage 'The owned Key Vault secret remains soft-deleted.' `
            -Test {
                $null -eq (Invoke-BoundedAz `
                    -Arguments @(
                        'keyvault', 'secret', 'show-deleted',
                        '--subscription', $binding.AzureSubscriptionId,
                        '--vault-name', $binding.KeyVaultName,
                        '--name', $names.TransportSecret,
                        '--only-show-errors',
                        '--output', 'json'
                    ) `
                    -TimeoutSeconds 60 `
                    -AllowNotFound)
            }
        $gate2.Remove('azureSecretId')
    }
    Save-ExperimentState -Path $statePath -State $state
}

if ($gate2['awsSecretName']) {
    $secret = Invoke-BoundedAws `
        -Arguments @(
            'secretsmanager', 'describe-secret',
            '--secret-id', [string]$gate2['awsSecretName'],
            '--output', 'json'
        ) `
        -Profile $binding.AwsProfile `
        -Region $binding.AwsRegion `
        -TimeoutSeconds 60 `
        -AllowNotFound
    if (
        $secret -and
        [string]$secret.ARN -ne [string]$gate2['awsSecretArn']
    ) {
        throw 'The AWS secret ARN does not match ignored state.'
    }
    if ($secret) {
        $null = Invoke-BoundedAws `
            -Arguments @(
                'secretsmanager', 'delete-secret',
                '--secret-id', [string]$gate2['awsSecretName'],
                '--force-delete-without-recovery',
                '--output', 'json'
            ) `
            -Profile $binding.AwsProfile `
            -Region $binding.AwsRegion `
            -TimeoutSeconds 60
    }
    Wait-Until `
        -TimeoutSeconds $TimeoutSeconds `
        -FailureMessage 'The owned AWS secret still exists.' `
        -Test {
            $null -eq (Invoke-BoundedAws `
                -Arguments @(
                    'secretsmanager', 'describe-secret',
                    '--secret-id', [string]$gate2['awsSecretName'],
                    '--output', 'json'
                ) `
                -Profile $binding.AwsProfile `
                -Region $binding.AwsRegion `
                -TimeoutSeconds 60 `
                -AllowNotFound)
        }
    $gate2.Remove('awsSecretName')
    $gate2.Remove('awsSecretArn')
    Save-ExperimentState -Path $statePath -State $state
}

if ($gate2['image']) {
    $imageReference = ([string]$gate2['image'] -split '/', 2)[1]
    if (-not $imageReference.StartsWith("$($names.AzureRepository):")) {
        throw 'The saved ACR image is outside the experiment repository path.'
    }
    $image = Invoke-BoundedAz `
        -Arguments @(
            'acr', 'repository', 'show',
            '--name', $binding.ContainerRegistry,
            '--image', $imageReference,
            '--only-show-errors',
            '--output', 'json'
        ) `
        -TimeoutSeconds 60 `
        -AllowNotFound
    if ($image) {
        $null = Invoke-BoundedAz `
            -Arguments @(
                'acr', 'repository', 'delete',
                '--name', $binding.ContainerRegistry,
                '--image', $imageReference,
                '--yes',
                '--only-show-errors'
            ) `
            -TimeoutSeconds 120 `
            -Raw
    }
    $remaining = Invoke-BoundedAz `
        -Arguments @(
            'acr', 'repository', 'show',
            '--name', $binding.ContainerRegistry,
            '--image', $imageReference,
            '--only-show-errors',
            '--output', 'json'
        ) `
        -TimeoutSeconds 60 `
        -AllowNotFound
    if ($remaining) {
        throw 'The experiment MCP image still exists.'
    }
    $gate2.Remove('image')
    $gate2.Remove('acrLoginServer')
    Save-ExperimentState -Path $statePath -State $state
}

$remainingKeys = @(
    $gate2.Keys |
        Where-Object {
            $_ -notin @(
                'runtimeDetached',
                'siteId',
                'azureSecretId',
                'azureSecretSoftDeleted',
                'azureSecretScheduledPurgeDate'
            )
        }
)
if ($remainingKeys.Count -gt 0) {
    throw 'Gate 2 cleanup is incomplete; ignored state retains unfinished keys.'
}
$softDeletePending = $gate2['azureSecretSoftDeleted'] -eq $true
if ($softDeletePending) {
    Save-ExperimentState -Path $statePath -State $state
    Remove-Item `
        -LiteralPath (Join-Path $labRoot 'gate2.containerapp.local.yaml') `
        -Force `
        -ErrorAction SilentlyContinue
    Write-Output '{"gate2Cleanup":"pending-platform-purge"}'
    exit 0
}
$state.Remove('gate2')
Save-ExperimentState -Path $statePath -State $state
Remove-Item `
    -LiteralPath (Join-Path $labRoot 'gate2.containerapp.local.yaml') `
    -Force `
    -ErrorAction SilentlyContinue
Write-Output '{"gate2Cleanup":"complete"}'

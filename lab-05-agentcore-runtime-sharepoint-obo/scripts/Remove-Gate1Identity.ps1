[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath,
    [ValidateRange(60, 600)][int] $TimeoutSeconds = 120
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

if ($binding.CleanupWriteApproval -ne 'approved') {
    throw 'The ignored binding does not approve the identity cleanup write.'
}
if (-not $state.ContainsKey('entra')) {
    Write-Output '{"identityCleanup":"already-absent"}'
    exit 0
}
if ($state.ContainsKey('aws')) {
    throw 'Identity cleanup requires Gate 2 and AWS cleanup to complete first.'
}
if ($state.ContainsKey('gate2')) {
    $allowedGate2Keys = @(
        'runtimeDetached',
        'siteId',
        'azureSecretId',
        'azureSecretSoftDeleted',
        'azureSecretScheduledPurgeDate'
    )
    $blockingGate2Keys = @(
        $state['gate2'].Keys |
            Where-Object { $_ -notin $allowedGate2Keys }
    )
    if (
        $state['gate2']['azureSecretSoftDeleted'] -ne $true -or
        $blockingGate2Keys.Count -gt 0
    ) {
        throw (
            'Identity cleanup requires all non-platform Gate 2 cleanup ' +
            'to complete first.'
        )
    }
}

Connect-MgGraph -TenantId $binding.TenantId -Scopes @(
    'AgentIdentity.DeleteRestore.All'
    'AgentIdentityBlueprint.DeleteRestore.All'
    'AgentIdentityBlueprintPrincipal.DeleteRestore.All'
    'Application.ReadWrite.All'
) -UseDeviceCode -ContextScope CurrentUser -NoWelcome
$context = Get-MgContext
if (-not $context -or $context.TenantId -ne $binding.TenantId) {
    throw 'The Microsoft Graph context does not match the binding.'
}

$entra = $state['entra']
$objects = @(
    @{
        Key = 'agentIdentityObjectId'
        ReadUri = "https://graph.microsoft.com/v1.0/servicePrincipals/$($entra['agentIdentityObjectId'])"
        DeleteUri = "https://graph.microsoft.com/v1.0/servicePrincipals/$($entra['agentIdentityObjectId'])/microsoft.graph.agentIdentity"
        ExpectedName = $names.AgentIdentity
        ExpectedAppId = [string]$entra['agentIdentityAppId']
    },
    @{
        Key = 'blueprintPrincipalId'
        ReadUri = "https://graph.microsoft.com/v1.0/servicePrincipals/$($entra['blueprintPrincipalId'])"
        DeleteUri = "https://graph.microsoft.com/v1.0/servicePrincipals/$($entra['blueprintPrincipalId'])/microsoft.graph.agentIdentityBlueprintPrincipal"
        ExpectedAppId = [string]$entra['blueprintAppId']
    },
    @{
        Key = 'blueprintObjectId'
        ReadUri = "https://graph.microsoft.com/v1.0/applications/$($entra['blueprintObjectId'])"
        DeleteUri = "https://graph.microsoft.com/v1.0/applications/$($entra['blueprintObjectId'])/microsoft.graph.agentIdentityBlueprint"
        ExpectedName = $names.Blueprint
        ExpectedAppId = [string]$entra['blueprintAppId']
    },
    @{
        Key = 'publicClientPrincipalId'
        ReadUri = "https://graph.microsoft.com/v1.0/servicePrincipals/$($entra['publicClientPrincipalId'])"
        DeleteUri = "https://graph.microsoft.com/v1.0/servicePrincipals/$($entra['publicClientPrincipalId'])"
        ExpectedName = $names.PublicClient
        ExpectedAppId = [string]$entra['publicClientAppId']
    },
    @{
        Key = 'publicClientObjectId'
        ReadUri = "https://graph.microsoft.com/v1.0/applications/$($entra['publicClientObjectId'])"
        DeleteUri = "https://graph.microsoft.com/v1.0/applications/$($entra['publicClientObjectId'])"
        ExpectedName = $names.PublicClient
        ExpectedAppId = [string]$entra['publicClientAppId']
    }
)

foreach ($object in $objects) {
    if (-not $entra[$object.Key]) {
        continue
    }
    $live = Invoke-BoundedGraph `
        -Method GET `
        -Uri $object.ReadUri `
        -TimeoutSeconds $TimeoutSeconds `
        -ExpectedStatus @(200) `
        -AllowNotFound
    if ($live) {
        if (
            $object.ExpectedName -and
            [string]$live.displayName -ne [string]$object.ExpectedName
        ) {
            throw "The live $($object.Key) name does not match issue-206 ownership."
        }
        if (
            $object.ExpectedAppId -and
            [string]$live.appId -ne [string]$object.ExpectedAppId
        ) {
            throw "The live $($object.Key) appId does not match ignored state."
        }
        $null = Invoke-BoundedGraph `
            -Method DELETE `
            -Uri $object.DeleteUri `
            -TimeoutSeconds $TimeoutSeconds `
            -ExpectedStatus @(204)
    }
    Assert-GraphAbsent `
        -Uri $object.ReadUri `
        -TimeoutSeconds $TimeoutSeconds
    $entra.Remove($object.Key)
    Save-ExperimentState -Path $statePath -State $state
}

$state.Remove('entra')
Save-ExperimentState -Path $statePath -State $state
Write-Output '{"identityCleanup":"complete"}'

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')

$binding = Get-GateBinding -Path $BindingPath
$statePath = Get-StatePath -BindingPath $BindingPath
$state = Read-ExperimentState -Path $statePath

if ($binding.Gate4LabelPolicyWriteApproval -ne 'approved') {
    throw 'The ignored binding does not approve Gate 4 label-policy writes.'
}
if ($binding.Gate4LabelV1AppWriteApproval -ne 'approved') {
    throw 'The ignored binding does not approve the Gate 4 v1 label-definition permission.'
}
if (
    -not $state.ContainsKey('entra') -or
    -not $state.ContainsKey('gate2') -or
    -not $state['gate2']['graphDelegatedGrantId'] -or
    -not $state['gate2']['managedIdentityPrincipalId']
) {
    throw 'Gate 2 Graph configuration is required.'
}

Connect-MgGraph `
    -TenantId $binding.TenantId `
    -Scopes @(
        'AgentIdentityBlueprint.ReadWrite.All'
        'AppRoleAssignment.ReadWrite.All'
        'DelegatedPermissionGrant.ReadWrite.All'
        'Application.Read.All'
    ) `
    -UseDeviceCode `
    -ContextScope Process `
    -NoWelcome
$context = Get-MgContext
if (-not $context -or $context.TenantId -ne $binding.TenantId) {
    throw 'The Microsoft Graph process context does not match the binding.'
}

$entra = $state['entra']
$gate2 = $state['gate2']
$graph = Invoke-MgGraphRequest `
    -Method GET `
    -Uri "https://graph.microsoft.com/v1.0/servicePrincipals(appId='00000003-0000-0000-c000-000000000000')?`$select=id,oauth2PermissionScopes,appRoles" `
    -OutputType PSObject
$requiredScopeValues = @(
    'Sites.Selected'
    'Files.Read.All'
    'InformationProtectionPolicy.Read'
)
$scopeByValue = @{}
foreach ($scopeValue in $requiredScopeValues) {
    $matches = @(
        $graph.oauth2PermissionScopes |
            Where-Object { $_.value -eq $scopeValue }
    )
    if ($matches.Count -ne 1) {
        throw "The Graph $scopeValue delegated scope was not resolved."
    }
    $scopeByValue[$scopeValue] = $matches[0]
}

if (-not $gate2['gate4LabelRequiredResourceAccessConfigured']) {
    $blueprint = Invoke-MgGraphRequest `
        -Method GET `
        -Uri "https://graph.microsoft.com/v1.0/applications/$($entra['blueprintObjectId'])?`$select=requiredResourceAccess" `
        -OutputType PSObject
    $required = @($blueprint.requiredResourceAccess)
    $graphAccess = @(
        $required |
            Where-Object {
                $_.resourceAppId -eq '00000003-0000-0000-c000-000000000000'
            }
    )
    if ($graphAccess.Count -ne 1) {
        throw 'The Blueprint Microsoft Graph access entry is missing or duplicated.'
    }
    $existingIds = @(
        $graphAccess[0].resourceAccess |
            ForEach-Object { [string]$_.id }
    )
    foreach ($scopeValue in $requiredScopeValues) {
        $scopeId = [string]$scopeByValue[$scopeValue].id
        if ($scopeId -notin $existingIds) {
            $graphAccess[0].resourceAccess += @{
                id = $scopeId
                type = 'Scope'
            }
        }
    }
    Invoke-MgGraphRequest `
        -Method PATCH `
        -Uri "https://graph.microsoft.com/v1.0/applications/$($entra['blueprintObjectId'])" `
        -ContentType 'application/json' `
        -Body (@{ requiredResourceAccess = $required } |
            ConvertTo-Json -Depth 10) | Out-Null
    $gate2['gate4LabelRequiredResourceAccessConfigured'] = $true
    Save-ExperimentState -Path $statePath -State $state
}

if (-not $gate2['gate4LabelDelegatedGrantConfigured']) {
    $grant = Invoke-MgGraphRequest `
        -Method GET `
        -Uri "https://graph.microsoft.com/v1.0/oauth2PermissionGrants/$($gate2['graphDelegatedGrantId'])" `
        -OutputType PSObject
    $scopeValues = @(
        ([string]$grant.scope).Split(
            ' ',
            [System.StringSplitOptions]::RemoveEmptyEntries
        )
    )
    $gate2['gate4LabelPreviousGrantScope'] = [string]$grant.scope
    $updatedScopes = @(
        $scopeValues + $requiredScopeValues |
            Select-Object -Unique
    )
    Invoke-MgGraphRequest `
        -Method PATCH `
        -Uri "https://graph.microsoft.com/v1.0/oauth2PermissionGrants/$($grant.id)" `
        -ContentType 'application/json' `
        -Body (@{ scope = ($updatedScopes -join ' ') } |
            ConvertTo-Json) | Out-Null
    $gate2['gate4LabelDelegatedGrantConfigured'] = $true
    Save-ExperimentState -Path $statePath -State $state
}

$labelV1AppRole = @(
    $graph.appRoles |
        Where-Object {
            $_.value -eq 'SensitivityLabel.Read' -and
            'Application' -in @($_.allowedMemberTypes)
        }
)
if ($labelV1AppRole.Count -ne 1) {
    throw 'The Graph SensitivityLabel.Read application role was not resolved.'
}
if (-not $gate2['gate4LabelV1ManagedIdentityAppRoleConfigured']) {
    $principalId = [string]$gate2['managedIdentityPrincipalId']
    $assignments = @(
        Invoke-MgGraphRequest `
            -Method GET `
            -Uri "https://graph.microsoft.com/v1.0/servicePrincipals/$principalId/appRoleAssignments" `
            -OutputType PSObject |
            Select-Object -ExpandProperty value
    )
    $appRoleId = [string]$labelV1AppRole[0].id
    $existing = @(
        $assignments |
            Where-Object {
                [string]$_.resourceId -eq [string]$graph.id -and
                [string]$_.appRoleId -eq $appRoleId
            }
    )
    if ($existing.Count -eq 0) {
        Invoke-MgGraphRequest `
            -Method POST `
            -Uri "https://graph.microsoft.com/v1.0/servicePrincipals/$principalId/appRoleAssignments" `
            -ContentType 'application/json' `
            -Body (@{
                principalId = $principalId
                resourceId = [string]$graph.id
                appRoleId = $appRoleId
            } | ConvertTo-Json) | Out-Null
    }
    elseif ($existing.Count -ne 1) {
        throw 'The managed identity v1 label-definition role assignment is duplicated.'
    }
    $gate2['gate4LabelV1ManagedIdentityAppRoleConfigured'] = $true
    Save-ExperimentState -Path $statePath -State $state
}

Write-Output (@{
        gate4LabelPolicy = 'ready'
        graphDelegatedScopes = $requiredScopeValues
        managedIdentityApplicationRole = 'SensitivityLabel.Read'
        sitesReadAllAdded = $false
    } | ConvertTo-Json -Compress)

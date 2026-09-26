[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')

$binding = Get-GateBinding -Path $BindingPath
$names = Get-ExperimentNames
$statePath = Get-StatePath -BindingPath $BindingPath
$state = Read-ExperimentState -Path $statePath

if ($binding.IdentityWriteApproval -ne 'approved') {
    throw 'The ignored binding does not approve the Entra identity write.'
}
if ($binding.ResourcePrefix -ne $names.Prefix) {
    throw 'The ignored binding does not select the fixed experiment prefix.'
}
if ($binding.RequiredScope -ne $names.Scope) {
    throw 'The ignored binding does not select the fixed Gate 1 scope.'
}
if (-not (Get-Command Get-MgContext -ErrorAction SilentlyContinue)) {
    throw 'Microsoft Graph PowerShell is not installed.'
}

$scopes = @(
    'AgentIdentityBlueprint.Create'
    'AgentIdentityBlueprint.ReadWrite.All'
    'AgentIdentityBlueprint.UpdateAuthProperties.All'
    'AgentIdentityBlueprintPrincipal.Create'
    'AgentIdentity.Create.All'
    'Application.ReadWrite.All'
    'User.Read'
)
$context = Get-MgContext
if (-not $context -or $context.TenantId -ne $binding.TenantId) {
    throw (
        'No matching Microsoft Graph process context exists. ' +
        'Run Initialize-Gate1Identity.ps1 so login and creation share one process.'
    )
}
$missingScopes = @($scopes | Where-Object { $_ -notin $context.Scopes })
if ($missingScopes.Count -gt 0) {
    throw 'The saved Microsoft Graph context lacks a required delegated scope.'
}

$me = Invoke-MgGraphRequest `
    -Method GET `
    -Uri 'https://graph.microsoft.com/v1.0/me?$select=id' `
    -OutputType PSObject
if (-not $me.id) {
    throw 'The signed-in sponsor could not be resolved.'
}
$sponsorBinding = "https://graph.microsoft.com/v1.0/users/$($me.id)"

if (-not $state.ContainsKey('entra')) {
    $state['entra'] = @{}
}
$entra = $state['entra']

function Assert-NoGraphCollision {
    param(
        [Parameter(Mandatory)][string] $Uri,
        [Parameter(Mandatory)][string] $ObjectClass
    )

    $result = Invoke-MgGraphRequest `
        -Method GET `
        -Uri $Uri `
        -Headers @{ 'OData-Version' = '4.0' } `
        -OutputType PSObject
    if (@($result.value).Count -gt 0) {
        throw "An exact $ObjectClass name exists outside the ignored state."
    }
}

if (-not $entra.ContainsKey('publicClientObjectId')) {
    $filter = [uri]::EscapeDataString(
        "displayName eq '$($names.PublicClient)'"
    )
    Assert-NoGraphCollision `
        -ObjectClass 'public client' `
        -Uri "https://graph.microsoft.com/v1.0/applications?`$filter=$filter&`$select=id"
    Write-Output '{"phase":"public-client","status":"started"}'
    $publicClient = Invoke-MgGraphRequest `
        -Method POST `
        -Uri 'https://graph.microsoft.com/v1.0/applications' `
        -ContentType 'application/json' `
        -Body (@{
                displayName = $names.PublicClient
                signInAudience = 'AzureADMyOrg'
                publicClient = @{
                    redirectUris = @($binding.PublicClientRedirectUri)
                }
            } | ConvertTo-Json -Depth 5) `
        -OutputType PSObject
    $entra['publicClientObjectId'] = [string]$publicClient.id
    $entra['publicClientAppId'] = [string]$publicClient.appId
    Save-ExperimentState -Path $statePath -State $state
}

if (-not $entra.ContainsKey('publicClientPrincipalId')) {
    $publicClientPrincipal = Invoke-MgGraphRequest `
        -Method POST `
        -Uri 'https://graph.microsoft.com/v1.0/servicePrincipals' `
        -ContentType 'application/json' `
        -Body (@{ appId = $entra['publicClientAppId'] } | ConvertTo-Json) `
        -OutputType PSObject
    $entra['publicClientPrincipalId'] = [string]$publicClientPrincipal.id
    Save-ExperimentState -Path $statePath -State $state
    Write-Output '{"phase":"public-client","status":"complete"}'
}

if (-not $entra.ContainsKey('blueprintObjectId')) {
    $filter = [uri]::EscapeDataString(
        "displayName eq '$($names.Blueprint)'"
    )
    Assert-NoGraphCollision `
        -ObjectClass 'Blueprint' `
        -Uri "https://graph.microsoft.com/v1.0/applications/microsoft.graph.agentIdentityBlueprint?`$filter=$filter&`$select=id"
    Write-Output '{"phase":"blueprint","status":"started"}'
    $blueprint = Invoke-MgGraphRequest `
        -Method POST `
        -Uri 'https://graph.microsoft.com/v1.0/applications/microsoft.graph.agentIdentityBlueprint' `
        -Headers @{ 'OData-Version' = '4.0' } `
        -ContentType 'application/json' `
        -Body (@{
                '@odata.type' = 'Microsoft.Graph.AgentIdentityBlueprint'
                displayName = $names.Blueprint
                'sponsors@odata.bind' = @($sponsorBinding)
                'owners@odata.bind' = @($sponsorBinding)
            } | ConvertTo-Json -Depth 5) `
        -OutputType PSObject
    $entra['blueprintObjectId'] = [string]$blueprint.id
    $entra['blueprintAppId'] = [string]$blueprint.appId
    $entra['scopeId'] = [string][guid]::NewGuid()
    Save-ExperimentState -Path $statePath -State $state
}

$scope = @{
    adminConsentDescription =
        'Allow the proof client to invoke the experiment agent.'
    adminConsentDisplayName = 'Invoke experiment agent'
    id = $entra['scopeId']
    isEnabled = $true
    type = 'User'
    value = $names.Scope
}

if (-not $entra.ContainsKey('blueprintScopeConfigured')) {
    Invoke-MgGraphRequest `
        -Method PATCH `
        -Uri "https://graph.microsoft.com/v1.0/applications/$($entra['blueprintObjectId'])" `
        -Headers @{ 'OData-Version' = '4.0' } `
        -ContentType 'application/json' `
        -Body (@{
                identifierUris = @("api://$($entra['blueprintAppId'])")
                api = @{
                    oauth2PermissionScopes = @($scope)
                }
            } | ConvertTo-Json -Depth 8) | Out-Null
    $entra['blueprintScopeConfigured'] = $true
    Save-ExperimentState -Path $statePath -State $state
}

if (-not $entra.ContainsKey('blueprintConfigured')) {
    $api = @{
        oauth2PermissionScopes = @($scope)
        preAuthorizedApplications = @(
            @{
                appId = $entra['publicClientAppId']
                delegatedPermissionIds = @($entra['scopeId'])
            }
        )
    }
    Invoke-MgGraphRequest `
        -Method PATCH `
        -Uri "https://graph.microsoft.com/v1.0/applications/$($entra['blueprintObjectId'])" `
        -Headers @{ 'OData-Version' = '4.0' } `
        -ContentType 'application/json' `
        -Body (@{ api = $api } | ConvertTo-Json -Depth 8) | Out-Null
    $entra['blueprintConfigured'] = $true
    Save-ExperimentState -Path $statePath -State $state
}

if (-not $entra.ContainsKey('blueprintPrincipalId')) {
    $blueprintPrincipal = Invoke-MgGraphRequest `
        -Method POST `
        -Uri 'https://graph.microsoft.com/v1.0/servicePrincipals/microsoft.graph.agentIdentityBlueprintPrincipal' `
        -Headers @{ 'OData-Version' = '4.0' } `
        -ContentType 'application/json' `
        -Body (@{ appId = $entra['blueprintAppId'] } | ConvertTo-Json) `
        -OutputType PSObject
    $entra['blueprintPrincipalId'] = [string]$blueprintPrincipal.id
    Save-ExperimentState -Path $statePath -State $state
    Write-Output '{"phase":"blueprint","status":"complete"}'
}

if (-not $entra.ContainsKey('agentIdentityObjectId')) {
    $filter = [uri]::EscapeDataString(
        "displayName eq '$($names.AgentIdentity)'"
    )
    Assert-NoGraphCollision `
        -ObjectClass 'Agent Identity' `
        -Uri "https://graph.microsoft.com/beta/servicePrincipals/Microsoft.Graph.AgentIdentity?`$filter=$filter&`$select=id"
    Write-Output '{"phase":"agent-identity","status":"started"}'
    $agentIdentity = Invoke-MgGraphRequest `
        -Method POST `
        -Uri 'https://graph.microsoft.com/beta/servicePrincipals/Microsoft.Graph.AgentIdentity' `
        -Headers @{ 'OData-Version' = '4.0' } `
        -ContentType 'application/json' `
        -Body (@{
                displayName = $names.AgentIdentity
                agentIdentityBlueprintId = $entra['blueprintAppId']
                'sponsors@odata.bind' = @($sponsorBinding)
                'owners@odata.bind' = @($sponsorBinding)
            } | ConvertTo-Json -Depth 5) `
        -OutputType PSObject
    $entra['agentIdentityObjectId'] = [string]$agentIdentity.id
    $entra['agentIdentityAppId'] = [string]$agentIdentity.appId
    Save-ExperimentState -Path $statePath -State $state
    Write-Output '{"phase":"agent-identity","status":"complete"}'
}

Write-Output (@{
        identity = 'ready'
        publicClient = 'ready'
        blueprint = 'ready'
        agentIdentity = 'ready'
        secretCreated = $false
        stateStoredInIgnoredFile = $true
    } | ConvertTo-Json -Compress)

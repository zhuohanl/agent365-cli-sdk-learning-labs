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

if ($binding.AzureWriteApproval -ne 'approved') {
    throw 'The ignored binding does not approve Gate 2 Graph writes.'
}
if (
    -not $state.ContainsKey('entra') -or
    -not $state.ContainsKey('gate2') -or
    -not $state['gate2']['managedIdentityPrincipalId']
) {
    throw 'Gate 1 identity and Gate 2 Azure skeleton are required.'
}

$scopes = @(
    'AgentIdentityBlueprint.ReadWrite.All'
    'AgentIdentityBlueprint.UpdateAuthProperties.All'
    'AgentIdentityBlueprint.AddRemoveCreds.All'
    'DelegatedPermissionGrant.ReadWrite.All'
    'Application.Read.All'
    'Sites.FullControl.All'
    'User.Read'
)
Connect-MgGraph `
    -TenantId $binding.TenantId `
    -Scopes $scopes `
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
    -Uri "https://graph.microsoft.com/v1.0/servicePrincipals(appId='00000003-0000-0000-c000-000000000000')?`$select=id,oauth2PermissionScopes" `
    -OutputType PSObject
$sitesSelected = @(
    $graph.oauth2PermissionScopes |
        Where-Object { $_.value -eq 'Sites.Selected' }
)
if ($sitesSelected.Count -ne 1) {
    throw 'The Graph Sites.Selected delegated scope was not resolved.'
}

if (-not $gate2.ContainsKey('requiredResourceAccessConfigured')) {
    $blueprint = Invoke-MgGraphRequest `
        -Method GET `
        -Uri "https://graph.microsoft.com/v1.0/applications/$($entra['blueprintObjectId'])?`$select=requiredResourceAccess" `
        -OutputType PSObject
    $gate2['previousRequiredResourceAccess'] = @(
        $blueprint.requiredResourceAccess
    )
    $required = @($blueprint.requiredResourceAccess)
    $graphAccess = @(
        $required |
            Where-Object {
                $_.resourceAppId -eq '00000003-0000-0000-c000-000000000000'
            }
    )
    if ($graphAccess.Count -gt 1) {
        throw 'The Blueprint has duplicate Microsoft Graph access entries.'
    }
    if ($graphAccess.Count -eq 0) {
        $required += @{
            resourceAppId = '00000003-0000-0000-c000-000000000000'
            resourceAccess = @(
                @{
                    id = [string]$sitesSelected[0].id
                    type = 'Scope'
                }
            )
        }
    }
    elseif (
        [string]$sitesSelected[0].id -notin @(
            $graphAccess[0].resourceAccess | ForEach-Object { [string]$_.id }
        )
    ) {
        $graphAccess[0].resourceAccess += @{
            id = [string]$sitesSelected[0].id
            type = 'Scope'
        }
    }
    Invoke-MgGraphRequest `
        -Method PATCH `
        -Uri "https://graph.microsoft.com/v1.0/applications/$($entra['blueprintObjectId'])" `
        -ContentType 'application/json' `
        -Body (@{ requiredResourceAccess = $required } |
            ConvertTo-Json -Depth 10) | Out-Null
    $gate2['requiredResourceAccessConfigured'] = $true
    Save-ExperimentState -Path $statePath -State $state
}

if (-not $gate2.ContainsKey('graphInheritanceConfigured')) {
    $inheritance = Invoke-MgGraphRequest `
        -Method GET `
        -Uri "https://graph.microsoft.com/v1.0/applications/microsoft.graph.agentIdentityBlueprint/$($entra['blueprintObjectId'])/inheritablePermissions" `
        -Headers @{ 'OData-Version' = '4.0' } `
        -OutputType PSObject
    $existing = @(
        $inheritance.value |
            Where-Object {
                $_.resourceAppId -eq '00000003-0000-0000-c000-000000000000'
            }
    )
    if ($existing.Count -gt 0) {
        throw 'Microsoft Graph inheritance exists outside ignored state.'
    }
    Invoke-MgGraphRequest `
        -Method POST `
        -Uri "https://graph.microsoft.com/v1.0/applications/microsoft.graph.agentIdentityBlueprint/$($entra['blueprintObjectId'])/inheritablePermissions" `
        -Headers @{ 'OData-Version' = '4.0' } `
        -ContentType 'application/json' `
        -Body (@{
                resourceAppId = '00000003-0000-0000-c000-000000000000'
                inheritableScopes = @{
                    '@odata.type' = '#microsoft.graph.allAllowedScopes'
                    kind = 'allAllowed'
                }
                inheritableRoles = @{
                    '@odata.type' = '#microsoft.graph.noRoles'
                    kind = 'none'
                }
            } | ConvertTo-Json -Depth 8) | Out-Null
    $gate2['graphInheritanceConfigured'] = $true
    Save-ExperimentState -Path $statePath -State $state
}

if (-not $gate2.ContainsKey('graphDelegatedGrantId')) {
    $filter = [uri]::EscapeDataString(
        "clientId eq '$($entra['blueprintPrincipalId'])' and resourceId eq '$($graph.id)'"
    )
    $grants = Invoke-MgGraphRequest `
        -Method GET `
        -Uri "https://graph.microsoft.com/v1.0/oauth2PermissionGrants?`$filter=$filter" `
        -OutputType PSObject
    if (@($grants.value).Count -gt 1) {
        throw 'Multiple Blueprint-to-Graph delegated grants exist.'
    }
    if (@($grants.value).Count -eq 0) {
        $grant = Invoke-MgGraphRequest `
            -Method POST `
            -Uri 'https://graph.microsoft.com/v1.0/oauth2PermissionGrants' `
            -ContentType 'application/json' `
            -Body (@{
                    clientId = $entra['blueprintPrincipalId']
                    consentType = 'AllPrincipals'
                    resourceId = [string]$graph.id
                    scope = 'Sites.Selected'
                } | ConvertTo-Json) `
            -OutputType PSObject
        $gate2['graphDelegatedGrantPreviousScope'] = ''
    }
    else {
        $grant = @($grants.value)[0]
        $gate2['graphDelegatedGrantPreviousScope'] = [string]$grant.scope
        $scopeValues = @(
            ([string]$grant.scope).Split(
                ' ',
                [System.StringSplitOptions]::RemoveEmptyEntries
            )
        )
        if ('Sites.Selected' -notin $scopeValues) {
            Invoke-MgGraphRequest `
                -Method PATCH `
                -Uri "https://graph.microsoft.com/v1.0/oauth2PermissionGrants/$($grant.id)" `
                -ContentType 'application/json' `
                -Body (@{
                        scope = (($scopeValues + 'Sites.Selected') -join ' ')
                    } | ConvertTo-Json) | Out-Null
        }
    }
    $gate2['graphDelegatedGrantId'] = [string]$grant.id
    Save-ExperimentState -Path $statePath -State $state
}

if (-not $gate2.ContainsKey('ficId')) {
    $fic = Invoke-MgGraphRequest `
        -Method POST `
        -Uri "https://graph.microsoft.com/beta/applications(appId='$($entra['blueprintAppId'])')/federatedIdentityCredentials" `
        -ContentType 'application/json' `
        -Body (@{
                name = $names.Fic
                issuer = "https://login.microsoftonline.com/$($binding.TenantId)/v2.0"
                subject = $gate2['managedIdentityPrincipalId']
                audiences = @('api://AzureADTokenExchange')
                description = 'Disposable issue-206 Container App identity.'
            } | ConvertTo-Json -Depth 5) `
        -OutputType PSObject
    $gate2['ficId'] = [string]$fic.id
    Save-ExperimentState -Path $statePath -State $state
}

if (-not $gate2.ContainsKey('siteId')) {
    $siteUri = [uri]$binding.SharePointSiteUrl
    $sitePath = $siteUri.AbsolutePath.TrimEnd('/')
    $site = Invoke-MgGraphRequest `
        -Method GET `
        -Uri "https://graph.microsoft.com/v1.0/sites/$($siteUri.Host):${sitePath}?`$select=id" `
        -OutputType PSObject
    if (-not $site.id) {
        throw 'The fixed SharePoint site could not be resolved.'
    }
    $gate2['siteId'] = [string]$site.id
    Save-ExperimentState -Path $statePath -State $state
}

if (-not $gate2.ContainsKey('sitePermissionId')) {
    $permissions = Invoke-MgGraphRequest `
        -Method GET `
        -Uri "https://graph.microsoft.com/v1.0/sites/$($gate2['siteId'])/permissions" `
        -OutputType PSObject
    $matches = @(
        $permissions.value |
            Where-Object {
                @(
                    $_.grantedToIdentitiesV2 |
                        ForEach-Object { $_.application.id }
                ) -contains $entra['agentIdentityAppId']
            }
    )
    if ($matches.Count -gt 0) {
        throw 'The child already has a site grant outside ignored state.'
    }
    $permission = Invoke-MgGraphRequest `
        -Method POST `
        -Uri "https://graph.microsoft.com/v1.0/sites/$($gate2['siteId'])/permissions" `
        -ContentType 'application/json' `
        -Body (@{
                roles = @('read')
                grantedToIdentities = @(
                    @{
                        application = @{
                            id = $entra['agentIdentityAppId']
                            displayName = $names.AgentIdentity
                        }
                    }
                )
            } | ConvertTo-Json -Depth 8) `
        -OutputType PSObject
    $gate2['sitePermissionId'] = [string]$permission.id
    Save-ExperimentState -Path $statePath -State $state
}

Write-Output (@{
        gate2Graph = 'ready'
        graphDelegatedScope = 'Sites.Selected'
        inheritableScopes = 'allAllowed'
        inheritableRoles = 'none'
        siteGrant = 'read'
        fic = 'ready'
    } | ConvertTo-Json -Compress)

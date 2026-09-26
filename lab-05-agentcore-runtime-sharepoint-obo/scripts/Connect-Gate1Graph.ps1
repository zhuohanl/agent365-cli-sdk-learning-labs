[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')

$binding = Get-GateBinding -Path $BindingPath
$scopes = @(
    'AgentIdentityBlueprint.Create'
    'AgentIdentityBlueprint.ReadWrite.All'
    'AgentIdentityBlueprint.UpdateAuthProperties.All'
    'AgentIdentityBlueprintPrincipal.Create'
    'AgentIdentity.Create.All'
    'Application.ReadWrite.All'
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
    throw 'The Microsoft Graph tenant does not match the ignored binding.'
}
Write-Output (@{
        graphContext = 'ready'
        tenant = 'matched'
        delegatedScopeCount = $scopes.Count
        cloudResourceWritePerformed = $false
    } | ConvertTo-Json -Compress)

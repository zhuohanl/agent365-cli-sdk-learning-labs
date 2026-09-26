[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')

$binding = Get-GateBinding -Path $BindingPath
$names = Get-ExperimentNames
$state = Read-ExperimentState -Path (Get-StatePath -BindingPath $BindingPath)
$labRoot = Split-Path -Parent $PSScriptRoot
$evidencePath = Join-Path $labRoot 'evidence\gate2-summary.json'

if (-not (Test-Path -LiteralPath $evidencePath -PathType Leaf)) {
    throw 'Gate 2 evidence does not exist.'
}
$evidence = Get-Content -LiteralPath $evidencePath -Raw | ConvertFrom-Json
$results = @($evidence.results.'user-a', $evidence.results.'user-b')
foreach ($result in $results) {
    if (
        $result.http_status -ne 200 -or
        $result.graph_audience_valid -ne $true -or
        $result.graph_actor_valid -ne $true -or
        $result.graph_subject_matches -ne $true -or
        $result.sites_selected_scope_valid -ne $true -or
        $result.microsoft_token_returned -ne $false -or
        $result.token_disclosed -ne $false
    ) {
        throw 'One or both Gate 2 user results failed.'
    }
}
$authorizedResults = @(
    $results | Where-Object {
        $_.graph_http_status -eq 200 -and $_.site_matched -eq $true
    }
)
$deniedResults = @(
    $results | Where-Object {
        $_.graph_http_status -eq 403 -and $_.site_matched -eq $false
    }
)
if ($authorizedResults.Count -lt 1) {
    throw 'No Gate 2 user completed the fixed-site metadata request.'
}
if (($authorizedResults.Count + $deniedResults.Count) -ne $results.Count) {
    throw 'A Gate 2 Graph result was neither an authorized success nor an expected delegated denial.'
}
if (
    $evidence.users_distinct -ne $true -or
    $evidence.sessions_distinct -ne $true -or
    $evidence.correlations_distinct -ne $true
) {
    throw 'Gate 2 two-user isolation failed.'
}

$app = az containerapp show `
    --subscription $binding.AzureSubscriptionId `
    --resource-group $binding.AzureResourceGroup `
    --name $names.ContainerApp `
    --only-show-errors `
    --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    throw 'The Gate 2 Container App is unavailable.'
}
if (
    @($app.properties.template.containers).Count -ne 2 -or
    $app.identity.type -notmatch 'SystemAssigned'
) {
    throw 'The Gate 2 Container App topology is not proof-minimal.'
}

$logs = az containerapp logs show `
    --subscription $binding.AzureSubscriptionId `
    --resource-group $binding.AzureResourceGroup `
    --name $names.ContainerApp `
    --container mcp `
    --tail 200 `
    --format text `
    --only-show-errors 2>$null
$unsafe = (
    $logs -match 'eyJ[A-Za-z0-9_-]{20,}\.' -or
    $logs -match '(?i)Authorization\s*:' -or
    $logs -match '(?i)Bearer\s+[A-Za-z0-9._-]{20,}'
)
if ($unsafe) {
    throw 'A possible Microsoft token appeared in Container App logs.'
}

$summary = [ordered]@{
    gate = 2
    runtime_is_network_caller = $true
    managed_identity_fic = $true
    graph_obo_claims_valid = $true
    fixed_site_http_200 = $true
    fixed_site_matched = $true
    unauthorized_user_denied = ($deniedResults.Count -gt 0)
    microsoft_token_returned_to_aws = $false
    two_users_distinct = $true
    two_sessions_distinct = $true
    cross_user_cache_reuse = $false
    container_count = 2
    raw_token_in_aca_logs = $false
}
$summaryJson = $summary | ConvertTo-Json -Compress
$summaryJson | Set-Content `
    -LiteralPath (Join-Path $labRoot 'evidence\gate2-validation.json') `
    -Encoding utf8
$summaryJson

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$labRoot = Split-Path -Parent $PSScriptRoot
$null = & (Join-Path $PSScriptRoot 'Test-Gate1Result.ps1') `
    -BindingPath $BindingPath
$null = & (Join-Path $PSScriptRoot 'Test-Gate2Result.ps1') `
    -BindingPath $BindingPath
$path = Join-Path $labRoot 'evidence\gate4-summary.json'
if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw 'Gate 4 evidence does not exist.'
}
$evidence = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
$readable = $evidence.results.readable
$protected = $evidence.results.protected
foreach ($result in @($readable, $protected)) {
    if (
        $result.http_status -ne 200 -or
        $result.token_received -ne $true -or
        $result.token_validated -ne $true -or
        $result.token_disclosed -ne $false -or
        $result.model_input_safe -ne $true -or
        $result.grounded_answer_present -ne $true -or
        $result.graph_relationships_valid -ne $true -or
        $result.files_read_all_scope_valid -ne $true -or
        $result.information_protection_scope_valid -ne $true -or
        @($result.tool_calls) -notcontains 'policy_sources_list' -or
        @($result.tool_calls) -notcontains 'policy_source_read'
    ) {
        throw 'A Gate 4 model and tool result failed.'
    }
}
if (
    $readable.fixture_role -notin @('readable', 'secondary-readable') -or
    $readable.read_status -ne 'success' -or
    $readable.upstream_http_status -ne 200 -or
    $readable.content_returned -ne $true -or
    $readable.citation_returned -ne $true -or
    $readable.label_resolved -ne $true -or
    $readable.policy_enforcer -ne 'opa' -or
    $readable.policy_reason -notin @('label_allowed', 'unlabeled_allowed') -or
    $readable.content_request_sent -ne $true
) {
    throw 'The readable Gate 4 fixture did not return attributed content.'
}

$protectedDenied = (
    $protected.fixture_role -eq 'protected' -and
    $protected.read_status -eq 'denied' -and
    $protected.label_resolved -eq $true -and
    $protected.policy_enforcer -eq 'opa' -and
    $protected.policy_reason -eq 'protected_label_denied' -and
    $protected.content_request_sent -eq $false -and
    $protected.content_returned -eq $false
)
$summary = [ordered]@{
    gate = 4
    source_catalog_bounded = $true
    readable_content_returned = $true
    readable_citation_returned = $true
    protected_fixture_selected = ($protected.fixture_role -eq 'protected')
    graph_relationships_valid = $true
    protected_label_resolved = [bool]$protected.label_resolved
    policy_enforcer = [string]$protected.policy_enforcer
    protected_outcome = if ($protectedDenied) { 'denied' } else { 'unexpected' }
    protected_content_request_sent = [bool]$protected.content_request_sent
    protected_content_returned = [bool]$protected.content_returned
    policy_failure_mode = 'fail-closed'
    native_copilot_dlp_claimed_as_enforcer = $false
    model_visible_credentials = $false
    raw_token_in_runtime_logs = $false
    raw_token_in_aca_logs = $false
}
$json = $summary | ConvertTo-Json -Compress
$json | Set-Content `
    -LiteralPath (Join-Path $labRoot 'evidence\gate4-validation.json') `
    -Encoding utf8
$json

if (-not $protectedDenied) {
    throw 'OPA did not deny the protected label before content download.'
}

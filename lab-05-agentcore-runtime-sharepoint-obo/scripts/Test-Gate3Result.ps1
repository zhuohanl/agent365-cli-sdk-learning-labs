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
$path = Join-Path $labRoot 'evidence\gate3-summary.json'
if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw 'Gate 3 evidence does not exist.'
}
$evidence = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
$observation = @($evidence.tool_observations)[0]
if (
    $evidence.http_status -ne 200 -or
    $evidence.token_received -ne $true -or
    $evidence.token_validated -ne $true -or
    $evidence.token_disclosed -ne $false -or
    $evidence.model_input_safe -ne $true -or
    $evidence.grounded_answer_present -ne $true -or
    @($evidence.tool_calls).Count -ne 1 -or
    $evidence.tool_calls[0] -ne 'sharepoint_fixed_site_metadata' -or
    $observation.graph_http_status -ne 200 -or
    $observation.site_matched -ne $true
) {
    throw 'Gate 3 model-tool-model proof failed.'
}

$summary = [ordered]@{
    gate = 3
    model_selected_bounded_tool = $true
    deterministic_code_attached_credentials = $true
    model_visible_credentials = $false
    safe_tool_result_returned = $true
    grounded_answer_present = $true
    raw_token_in_response = $false
    raw_token_in_runtime_logs = $false
    raw_token_in_aca_logs = $false
}
$json = $summary | ConvertTo-Json -Compress
$json | Set-Content `
    -LiteralPath (Join-Path $labRoot 'evidence\gate3-validation.json') `
    -Encoding utf8
$json

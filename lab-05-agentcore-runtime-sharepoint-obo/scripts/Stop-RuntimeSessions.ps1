[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath,
    [ValidateRange(60, 600)][int] $TimeoutSeconds = 600
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')
. (Join-Path $PSScriptRoot 'Aws.ps1')

$statePath = Get-StatePath -BindingPath $BindingPath
$state = Read-ExperimentState -Path $statePath
$sessionCount = @(
    foreach ($section in @('sessions', 'gate2Sessions')) {
        if ($state.ContainsKey($section)) {
            $state[$section].Values
        }
    }
).Count
if ($sessionCount -eq 0) {
    Write-Output '{"runtimeSessions":"already-absent","count":0}'
    exit 0
}

$labRoot = Split-Path -Parent $PSScriptRoot
Invoke-BoundedNative `
    -FilePath (Get-Command uv).Source `
    -Arguments @(
        'run',
        '--project', $labRoot,
        'python',
        (Join-Path $PSScriptRoot 'stop_runtime_sessions.py'),
        '--binding', (Resolve-Path -LiteralPath $BindingPath).Path,
        '--timeout-seconds', '60'
    ) `
    -CommandName 'OAuth Runtime session cleanup' `
    -TimeoutSeconds $TimeoutSeconds

$state = Read-ExperimentState -Path $statePath
foreach ($section in @('sessions', 'gate2Sessions')) {
    if ($state.ContainsKey($section)) {
        $state.Remove($section)
    }
}
Save-ExperimentState -Path $statePath -State $state
Write-Output '{"runtimeSessions":"complete"}'

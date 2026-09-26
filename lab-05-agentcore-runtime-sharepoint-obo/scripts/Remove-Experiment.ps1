[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath,
    [ValidateRange(60, 3600)][int] $TimeoutSeconds = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'Remove-Gate2.ps1') `
    -BindingPath $BindingPath `
    -TimeoutSeconds $TimeoutSeconds
& (Join-Path $PSScriptRoot 'Remove-Gate1Aws.ps1') `
    -BindingPath $BindingPath `
    -TimeoutSeconds $TimeoutSeconds
& (Join-Path $PSScriptRoot 'Remove-Gate1Identity.ps1') `
    -BindingPath $BindingPath `
    -TimeoutSeconds ([Math]::Min($TimeoutSeconds, 300))
& (Join-Path $PSScriptRoot 'Test-CleanupResult.ps1') `
    -BindingPath $BindingPath `
    -TimeoutSeconds $TimeoutSeconds

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

& (Join-Path $PSScriptRoot 'Connect-Gate1Graph.ps1') `
    -BindingPath $BindingPath

& (Join-Path $PSScriptRoot 'New-Gate1Identity.ps1') `
    -BindingPath $BindingPath

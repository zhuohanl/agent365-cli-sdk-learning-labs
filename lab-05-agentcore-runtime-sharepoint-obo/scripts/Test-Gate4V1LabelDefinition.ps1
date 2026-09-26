[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')

$binding = Get-GateBinding -Path $BindingPath
$names = Get-ExperimentNames
az containerapp exec `
    --subscription $binding.AzureSubscriptionId `
    --resource-group $binding.AzureResourceGroup `
    --name $names.ContainerApp `
    --container mcp `
    --command 'python /app/gate2/diagnose_v1_label.py'
if ($LASTEXITCODE -ne 0) {
    throw 'The Gate 4 v1 label-definition diagnostic failed.'
}

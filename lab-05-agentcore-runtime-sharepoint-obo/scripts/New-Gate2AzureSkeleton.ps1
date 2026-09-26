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
    throw 'The ignored binding does not approve Gate 2 Azure writes.'
}
foreach ($value in @(
        $binding.AzureSubscriptionId,
        $binding.AzureResourceGroup,
        $binding.ContainerAppsEnvironment,
        $binding.ContainerRegistry,
        $binding.KeyVaultName
    )) {
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw 'The ignored binding is missing a Gate 2 Azure value.'
    }
}
if (-not $state.ContainsKey('gate2')) {
    $state['gate2'] = @{}
}
$gate2 = $state['gate2']
az account set --subscription $binding.AzureSubscriptionId
if ($LASTEXITCODE -ne 0) {
    throw 'The Azure subscription context could not be selected.'
}

if (-not $gate2.ContainsKey('containerAppResourceId')) {
    $existing = az containerapp show `
        --subscription $binding.AzureSubscriptionId `
        --resource-group $binding.AzureResourceGroup `
        --name $names.ContainerApp `
        --only-show-errors `
        --output json 2>$null
    if ($LASTEXITCODE -eq 0 -and $existing) {
        throw 'The exact Container App exists outside ignored state.'
    }
    $created = az containerapp create `
        --subscription $binding.AzureSubscriptionId `
        --resource-group $binding.AzureResourceGroup `
        --name $names.ContainerApp `
        --environment $binding.ContainerAppsEnvironment `
        --image mcr.microsoft.com/k8se/quickstart:latest `
        --system-assigned `
        --ingress external `
        --target-port 80 `
        --min-replicas 1 `
        --max-replicas 1 `
        --only-show-errors `
        --output json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $created.id) {
        throw 'The Gate 2 Container App skeleton creation failed.'
    }
    $gate2['containerAppResourceId'] = [string]$created.id
    $gate2['managedIdentityPrincipalId'] = [string]$created.identity.principalId
    Save-ExperimentState -Path $statePath -State $state
}

$principal = [string]$gate2['managedIdentityPrincipalId']
if (-not $gate2.ContainsKey('acrPullRoleAssignmentId')) {
    $acr = az acr show `
        --subscription $binding.AzureSubscriptionId `
        --resource-group $binding.AzureResourceGroup `
        --name $binding.ContainerRegistry `
        --only-show-errors `
        --output json | ConvertFrom-Json
    $assignment = az role assignment create `
        --subscription $binding.AzureSubscriptionId `
        --assignee-object-id $principal `
        --assignee-principal-type ServicePrincipal `
        --scope $acr.id `
        --role AcrPull `
        --only-show-errors `
        --output json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $assignment.id) {
        throw 'The Container App AcrPull assignment failed.'
    }
    $gate2['acrPullRoleAssignmentId'] = [string]$assignment.id
    $gate2['acrLoginServer'] = [string]$acr.loginServer
    Save-ExperimentState -Path $statePath -State $state
}

if (-not $gate2.ContainsKey('keyVaultRoleAssignmentId')) {
    $vault = az keyvault show `
        --subscription $binding.AzureSubscriptionId `
        --resource-group $binding.KeyVaultResourceGroup `
        --name $binding.KeyVaultName `
        --only-show-errors `
        --output json | ConvertFrom-Json
    $assignment = az role assignment create `
        --subscription $binding.AzureSubscriptionId `
        --assignee-object-id $principal `
        --assignee-principal-type ServicePrincipal `
        --scope $vault.id `
        --role 'Key Vault Secrets User' `
        --only-show-errors `
        --output json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or -not $assignment.id) {
        throw 'The Container App Key Vault assignment failed.'
    }
    $gate2['keyVaultRoleAssignmentId'] = [string]$assignment.id
    Save-ExperimentState -Path $statePath -State $state
}

Write-Output (@{
        gate2AzureSkeleton = 'ready'
        systemAssignedIdentity = $true
        acrPull = 'ready'
        keyVaultSecretRead = 'ready'
    } | ConvertTo-Json -Compress)

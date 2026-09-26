[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath,
    [ValidateRange(60, 3600)][int] $TimeoutSeconds = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')
. (Join-Path $PSScriptRoot 'Aws.ps1')
. (Join-Path $PSScriptRoot 'Cleanup.ps1')

$binding = Get-GateBinding -Path $BindingPath
$names = Get-ExperimentNames
$state = Read-ExperimentState -Path (Get-StatePath -BindingPath $BindingPath)
$platformPurgePending = $false
foreach ($section in @('gate2', 'gate2Sessions', 'aws', 'sessions', 'entra')) {
    if ($state.ContainsKey($section)) {
        if (
            $section -eq 'gate2' -and
            $state['gate2']['azureSecretSoftDeleted'] -eq $true
        ) {
            $allowedGate2Keys = @(
                'runtimeDetached',
                'siteId',
                'azureSecretId',
                'azureSecretSoftDeleted',
                'azureSecretScheduledPurgeDate'
            )
            $unexpectedKeys = @(
                $state['gate2'].Keys |
                    Where-Object { $_ -notin $allowedGate2Keys }
            )
            if ($unexpectedKeys.Count -gt 0) {
                throw 'Gate 2 state contains unfinished non-platform cleanup.'
            }
            $platformPurgePending = $true
            continue
        }
        throw "Cleanup state still contains the $section section."
    }
}

$stack = Invoke-BoundedAws `
    -Arguments @(
        'cloudformation', 'describe-stacks',
        '--stack-name', $names.Stack,
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds 60 `
    -AllowNotFound
if ($stack) {
    throw 'The experiment AWS stack still exists.'
}
$repository = Invoke-BoundedAws `
    -Arguments @(
        'ecr', 'describe-repositories',
        '--repository-names', $names.Repository,
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds 60 `
    -AllowNotFound
if ($repository) {
    throw 'The experiment ECR repository still exists.'
}
$role = Invoke-BoundedAws `
    -Arguments @(
        'iam', 'get-role',
        '--role-name', $names.Role,
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds 60 `
    -AllowNotFound
if ($role) {
    throw 'The experiment execution role still exists.'
}
$awsSecret = Invoke-BoundedAws `
    -Arguments @(
        'secretsmanager', 'describe-secret',
        '--secret-id', $names.TransportSecret,
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds 60 `
    -AllowNotFound
if ($awsSecret) {
    throw 'The experiment AWS secret still exists.'
}

az account set --subscription $binding.AzureSubscriptionId --only-show-errors
if ($LASTEXITCODE -ne 0) {
    throw 'The Azure subscription context could not be selected.'
}
$containerApp = Invoke-BoundedAz `
    -Arguments @(
        'containerapp', 'show',
        '--subscription', $binding.AzureSubscriptionId,
        '--resource-group', $binding.AzureResourceGroup,
        '--name', $names.ContainerApp,
        '--only-show-errors',
        '--output', 'json'
    ) `
    -TimeoutSeconds 60 `
    -AllowNotFound
if ($containerApp) {
    throw 'The experiment Container App still exists.'
}
$acrImageRepository = Invoke-BoundedAz `
    -Arguments @(
        'acr', 'repository', 'show',
        '--name', $binding.ContainerRegistry,
        '--repository', $names.AzureRepository,
        '--only-show-errors',
        '--output', 'json'
    ) `
    -TimeoutSeconds 60 `
    -AllowNotFound
if ($acrImageRepository) {
    throw 'The experiment ACR repository path still contains manifests.'
}
$activeSecret = Invoke-BoundedAz `
    -Arguments @(
        'keyvault', 'secret', 'show',
        '--subscription', $binding.AzureSubscriptionId,
        '--vault-name', $binding.KeyVaultName,
        '--name', $names.TransportSecret,
        '--only-show-errors',
        '--output', 'json'
    ) `
    -TimeoutSeconds 60 `
    -AllowNotFound
if ($activeSecret) {
    throw 'The experiment Key Vault secret remains active.'
}
foreach ($sharedCheck in @(
        @(
            'group', 'show',
            '--subscription', $binding.AzureSubscriptionId,
            '--name', $binding.AzureResourceGroup,
            '--only-show-errors',
            '--output', 'json'
        ),
        @(
            'containerapp', 'env', 'show',
            '--subscription', $binding.AzureSubscriptionId,
            '--resource-group', $binding.AzureResourceGroup,
            '--name', $binding.ContainerAppsEnvironment,
            '--only-show-errors',
            '--output', 'json'
        ),
        @(
            'acr', 'show',
            '--subscription', $binding.AzureSubscriptionId,
            '--resource-group', $binding.AzureResourceGroup,
            '--name', $binding.ContainerRegistry,
            '--only-show-errors',
            '--output', 'json'
        ),
        @(
            'keyvault', 'show',
            '--subscription', $binding.AzureSubscriptionId,
            '--resource-group', $binding.KeyVaultResourceGroup,
            '--name', $binding.KeyVaultName,
            '--only-show-errors',
            '--output', 'json'
        )
    )) {
    $shared = Invoke-BoundedAz `
        -Arguments $sharedCheck `
        -TimeoutSeconds 60
    if (-not $shared) {
        throw 'A reused Azure baseline is missing after cleanup.'
    }
}

Connect-MgGraph -TenantId $binding.TenantId -Scopes @(
    'Application.Read.All'
    'Sites.Read.All'
) -UseDeviceCode -ContextScope CurrentUser -NoWelcome
foreach ($query in @(
        @{
            Uri = (
                'https://graph.microsoft.com/v1.0/applications?' +
                '$filter=' +
                [uri]::EscapeDataString("displayName eq '$($names.PublicClient)'") +
                '&$select=id'
            )
        },
        @{
            Uri = (
                'https://graph.microsoft.com/v1.0/applications?' +
                '$filter=' +
                [uri]::EscapeDataString("displayName eq '$($names.Blueprint)'") +
                '&$select=id'
            )
        },
        @{
            Uri = (
                'https://graph.microsoft.com/v1.0/servicePrincipals?' +
                '$filter=' +
                [uri]::EscapeDataString("displayName eq '$($names.AgentIdentity)'") +
                '&$select=id'
            )
        },
        @{
            Uri = (
                'https://graph.microsoft.com/v1.0/servicePrincipals?' +
                '$filter=' +
                [uri]::EscapeDataString("displayName eq '$($names.Blueprint)'") +
                '&$select=id'
            )
        },
        @{
            Uri = (
                'https://graph.microsoft.com/v1.0/servicePrincipals?' +
                '$filter=' +
                [uri]::EscapeDataString("displayName eq '$($names.PublicClient)'") +
                '&$select=id'
            )
        }
    )) {
    $result = Invoke-BoundedGraph `
        -Method GET `
        -Uri $query.Uri `
        -Headers $(
            if ($query.ContainsKey('Headers')) {
                $query.Headers
            }
            else {
                @{}
            }
        ) `
        -TimeoutSeconds ([Math]::Min($TimeoutSeconds, 120)) `
        -ExpectedStatus @(200)
    if (@($result.value).Count -ne 0) {
        throw 'An experiment Entra object still exists.'
    }
}

$siteUrl = [uri]$binding.SharePointSiteUrl
$sitePath = $siteUrl.AbsolutePath.TrimEnd('/')
$site = Invoke-BoundedGraph `
    -Method GET `
    -Uri (
        'https://graph.microsoft.com/v1.0/sites/' +
        "$($siteUrl.Host):$sitePath" +
        '?$select=id'
    ) `
    -TimeoutSeconds ([Math]::Min($TimeoutSeconds, 120)) `
    -ExpectedStatus @(200)
$lists = Invoke-BoundedGraph `
    -Method GET `
    -Uri (
        "https://graph.microsoft.com/v1.0/sites/$($site.id)/lists?" +
        '$select=id,displayName'
    ) `
    -TimeoutSeconds ([Math]::Min($TimeoutSeconds, 120)) `
    -ExpectedStatus @(200)
$library = @(
    $lists.value |
        Where-Object {
            [string]$_.displayName -eq $binding.DocumentLibraryName
        }
)
if ($library.Count -ne 1) {
    throw 'The approved SharePoint document library is missing or ambiguous.'
}
$folderPath = [uri]::EscapeDataString($binding.FolderPath) -replace '%2F', '/'
$children = Invoke-BoundedGraph `
    -Method GET `
    -Uri (
        "https://graph.microsoft.com/v1.0/sites/$($site.id)" +
        "/lists/$($library[0].id)/drive/root:/$($folderPath):/children?" +
        '$select=name'
    ) `
    -TimeoutSeconds ([Math]::Min($TimeoutSeconds, 120)) `
    -ExpectedStatus @(200)
$actualFiles = @($children.value | ForEach-Object { [string]$_.name })
foreach ($expectedFile in @(
        $binding.ReadableFileName,
        $binding.SecondaryReadableFileName,
        $binding.ProtectedFileName
    )) {
    if ($expectedFile -notin $actualFiles) {
        throw 'An approved SharePoint proof file is missing after cleanup.'
    }
}

if ($platformPurgePending) {
    Write-Output (@{
            cleanup = 'pending-platform-purge'
            deletableExperimentResourcesAbsent = $true
            sharedAzureBaselinesPresent = $true
            sharePointProofFilesPresent = $true
        } | ConvertTo-Json -Compress)
    throw (
        'The experiment Key Vault secret remains soft-deleted under ' +
        'shared purge protection.'
    )
}

Write-Output (@{
        cleanup = 'complete'
        experimentOwnedResourcesAbsent = $true
        sharedAzureBaselinesPresent = $true
        sharePointProofFilesPresent = $true
    } | ConvertTo-Json -Compress)

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')
. (Join-Path $PSScriptRoot 'Aws.ps1')

$binding = Get-GateBinding -Path $BindingPath
$names = Get-ExperimentNames
$statePath = Get-StatePath -BindingPath $BindingPath
$state = Read-ExperimentState -Path $statePath

if (
    $binding.AwsWriteApproval -ne 'approved' -or
    $binding.AzureWriteApproval -ne 'approved'
) {
    throw 'Gate 2 AWS and Azure writes are not both approved.'
}
if (-not $state.ContainsKey('gate2')) {
    $state['gate2'] = @{}
}
$gate2 = $state['gate2']
$secretPath = Join-Path $env:TEMP "gate2-key-$([guid]::NewGuid()).txt"
try {
    if (-not $gate2.ContainsKey('awsSecretName')) {
        $existing = Invoke-BoundedAws `
            -Arguments @(
                'secretsmanager', 'describe-secret',
                '--secret-id', $names.TransportSecret,
                '--output', 'json'
            ) `
            -Profile $binding.AwsProfile `
            -Region $binding.AwsRegion `
            -TimeoutSeconds 60 `
            -AllowNotFound
        if ($existing) {
            throw 'The exact AWS transport secret exists outside ignored state.'
        }
        $key = [Convert]::ToBase64String(
            [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
        )
        Set-Content -LiteralPath $secretPath -Value $key -NoNewline
        $created = Invoke-BoundedAws `
            -Arguments @(
                'secretsmanager', 'create-secret',
                '--name', $names.TransportSecret,
                '--description', 'Disposable issue-206 MCP transport key.',
                '--secret-string', "file://$secretPath",
                '--tags',
                'Key=managed-by,Value=issue-206',
                'Key=project,Value=agent365-learning-lab',
                '--output', 'json'
            ) `
            -Profile $binding.AwsProfile `
            -Region $binding.AwsRegion `
            -TimeoutSeconds 60
        $gate2['awsSecretName'] = $names.TransportSecret
        $gate2['awsSecretArn'] = [string]$created.ARN
        Save-ExperimentState -Path $statePath -State $state
    }

    if (-not $gate2.ContainsKey('azureSecretId')) {
        if (-not (Test-Path -LiteralPath $secretPath)) {
            $key = Invoke-BoundedAws `
                -Arguments @(
                    'secretsmanager', 'get-secret-value',
                    '--secret-id', $gate2['awsSecretName'],
                    '--query', 'SecretString',
                    '--output', 'text'
                ) `
                -Profile $binding.AwsProfile `
                -Region $binding.AwsRegion `
                -TimeoutSeconds 60 `
                -Raw
            Set-Content `
                -LiteralPath $secretPath `
                -Value $key.Trim() `
                -NoNewline
        }
        $secret = az keyvault secret set `
            --subscription $binding.AzureSubscriptionId `
            --vault-name $binding.KeyVaultName `
            --name $names.TransportSecret `
            --file $secretPath `
            --only-show-errors `
            --output json | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0 -or -not $secret.id) {
            throw 'Azure Key Vault transport secret creation failed.'
        }
        $gate2['azureSecretId'] = [string]$secret.id
        Save-ExperimentState -Path $statePath -State $state
    }
}
finally {
    $key = $null
    Remove-Item -LiteralPath $secretPath -Force -ErrorAction SilentlyContinue
}

Write-Output '{"gate2Secrets":"ready","secretValueDisclosed":false}'

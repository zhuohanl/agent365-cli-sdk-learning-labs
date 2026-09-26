[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')
. (Join-Path $PSScriptRoot 'Aws.ps1')

$binding = Get-GateBinding -Path $BindingPath
$state = Read-ExperimentState -Path (Get-StatePath -BindingPath $BindingPath)

if ($binding.AwsWriteApproval -ne 'approved') {
    throw 'The ignored binding does not approve the log-retention write.'
}
if (-not $state.ContainsKey('aws') -or -not $state['aws']['runtimeId']) {
    throw 'The ignored state has no Runtime ID.'
}

$prefix = "/aws/bedrock-agentcore/runtimes/$($state['aws']['runtimeId'])"
$logGroups = Invoke-BoundedAws `
    -Arguments @(
        'logs', 'describe-log-groups',
        '--log-group-name-prefix', $prefix,
        '--limit', '10',
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds 60
$owned = @(
    $logGroups.logGroups |
        Where-Object {
            $_.logGroupName -eq $prefix -or
            $_.logGroupName -like "$prefix-*"
        }
)
if ($owned.Count -eq 0) {
    throw 'No exact Runtime log group exists yet. Invoke user A first.'
}
foreach ($logGroup in $owned) {
    $null = Invoke-BoundedAws `
        -Arguments @(
            'logs', 'put-retention-policy',
            '--log-group-name', $logGroup.logGroupName,
            '--retention-in-days', [string]$binding.LogRetentionDays
        ) `
        -Profile $binding.AwsProfile `
        -Region $binding.AwsRegion `
        -TimeoutSeconds 60 `
        -Raw
}

Write-Output (@{
        retentionDays = $binding.LogRetentionDays
        exactOwnedLogGroupCount = $owned.Count
        retentionApplied = $true
    } | ConvertTo-Json -Compress)

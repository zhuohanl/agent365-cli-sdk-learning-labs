[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath,
    [ValidateRange(5, 300)][int] $TimeoutSeconds = 60
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')
. (Join-Path $PSScriptRoot 'Aws.ps1')

$binding = Get-GateBinding -Path $BindingPath
$names = Get-ExperimentNames
$state = Read-ExperimentState -Path (Get-StatePath -BindingPath $BindingPath)
$moduleRoot = Split-Path -Parent $PSScriptRoot

if (-not $state.ContainsKey('entra')) {
    throw 'The ignored state has no completed Entra identity stage.'
}
if ($binding.EnvironmentClass -notin @('development', 'test')) {
    throw 'The environment is not an approved non-production class.'
}
if ($binding.LogRetentionDays -ne 1) {
    throw 'Gate 1 log retention must be exactly one day.'
}
if (
    [string]::IsNullOrWhiteSpace($binding.CleanupOwner) -or
    [string]::IsNullOrWhiteSpace($binding.CostCeiling)
) {
    throw 'The cost ceiling or cleanup owner is missing.'
}

$identity = Invoke-BoundedAws `
    -Arguments @('sts', 'get-caller-identity', '--output', 'json') `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds $TimeoutSeconds
if ($identity.Account -ne $binding.AwsAccountId) {
    throw 'The active AWS account does not match the ignored binding.'
}
if ($identity.Arn -match ':root$') {
    throw 'The active AWS caller is root.'
}

$null = Invoke-BoundedAws `
    -Arguments @(
        'cloudformation', 'validate-template',
        '--template-body', "file://$(Join-Path $moduleRoot 'infrastructure\template.yaml')",
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds $TimeoutSeconds
$null = Invoke-BoundedAws `
    -Arguments @(
        'cloudformation', 'describe-type',
        '--type', 'RESOURCE',
        '--type-name', 'AWS::BedrockAgentCore::Runtime',
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds $TimeoutSeconds

$stack = Invoke-BoundedAws `
    -Arguments @(
        'cloudformation', 'describe-stacks',
        '--stack-name', $names.Stack,
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds $TimeoutSeconds `
    -AllowNotFound
if ($stack) {
    $tags = @{}
    foreach ($tag in @($stack.Stacks[0].Tags)) {
        $tags[$tag.Key] = $tag.Value
    }
    if (
        $tags['managed-by'] -ne 'issue-206' -or
        $tags['project'] -ne 'agent365-learning-lab'
    ) {
        throw 'The exact stack name exists without issue-206 ownership.'
    }
}
else {
    $repo = Invoke-BoundedAws `
        -Arguments @(
            'ecr', 'describe-repositories',
            '--repository-names', $names.Repository,
            '--output', 'json'
        ) `
        -Profile $binding.AwsProfile `
        -Region $binding.AwsRegion `
        -TimeoutSeconds $TimeoutSeconds `
        -AllowNotFound
    $role = Invoke-BoundedAws `
        -Arguments @(
            'iam', 'get-role',
            '--role-name', $names.Role,
            '--output', 'json'
        ) `
        -Profile $binding.AwsProfile `
        -Region $binding.AwsRegion `
        -TimeoutSeconds $TimeoutSeconds `
        -AllowNotFound
    $runtimes = Invoke-BoundedAws `
        -Arguments @(
            'bedrock-agentcore-control', 'list-agent-runtimes',
            '--max-results', '100',
            '--output', 'json'
        ) `
        -Profile $binding.AwsProfile `
        -Region $binding.AwsRegion `
        -TimeoutSeconds $TimeoutSeconds
    $runtime = @(
        $runtimes.agentRuntimes |
            Where-Object { $_.agentRuntimeName -eq $names.Runtime }
    )
    if ($repo -or $role -or $runtime.Count -gt 0) {
        throw 'An exact AWS object exists outside the owned stack.'
    }
}

Write-Output (@{
        preflight = 'passed'
        caller = 'non-root'
        account = 'matched'
        region = 'binding-selected'
        exactNameCollision = $false
        costCeilingRecorded = $true
        cleanupOwnerRecorded = $true
        cloudWritePerformed = $false
    } | ConvertTo-Json -Compress)

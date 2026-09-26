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
$statePath = Get-StatePath -BindingPath $BindingPath
$state = Read-ExperimentState -Path $statePath

if ($binding.CleanupWriteApproval -ne 'approved') {
    throw 'The ignored binding does not approve the AWS cleanup write.'
}
if (-not $state.ContainsKey('aws')) {
    Write-Output '{"awsCleanup":"already-absent"}'
    exit 0
}
$awsState = $state['aws']
if ([string]$awsState['stackName'] -ne $names.Stack) {
    throw 'The saved AWS stack name is outside the fixed experiment contract.'
}

$stack = Invoke-BoundedAws `
    -Arguments @(
        'cloudformation', 'describe-stacks',
        '--stack-name', [string]$awsState['stackName'],
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds 60 `
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
        throw 'The exact stack does not have issue-206 ownership.'
    }
}

$runtimeArn = [string]$awsState['runtimeArn']
if ($runtimeArn -and $state.ContainsKey('sessions')) {
    foreach ($sessionId in $state['sessions'].Values) {
        if (-not $sessionId) {
            continue
        }
        $null = Invoke-BoundedAws `
            -Arguments @(
                'bedrock-agentcore', 'stop-runtime-session',
                '--agent-runtime-arn', $runtimeArn,
                '--runtime-session-id', [string]$sessionId,
                '--qualifier', 'DEFAULT',
                '--output', 'json'
            ) `
            -Profile $binding.AwsProfile `
            -Region $binding.AwsRegion `
            -TimeoutSeconds 60 `
            -AllowNotFound
    }
}

$repositoryName = [string]$awsState['repositoryName']
if ($repositoryName -ne $names.Repository) {
    throw 'The saved ECR repository name is outside the fixed experiment contract.'
}
$images = Invoke-BoundedAws `
    -Arguments @(
        'ecr', 'list-images',
        '--repository-name', $repositoryName,
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds 60 `
    -AllowNotFound
if ($images) {
    foreach ($image in @($images.imageIds)) {
        $imageArgument = if ($image.imageTag) {
            "imageTag=$($image.imageTag)"
        }
        else {
            "imageDigest=$($image.imageDigest)"
        }
        $null = Invoke-BoundedAws `
            -Arguments @(
                'ecr', 'batch-delete-image',
                '--repository-name', $repositoryName,
                '--image-ids', $imageArgument,
                '--output', 'json'
            ) `
            -Profile $binding.AwsProfile `
            -Region $binding.AwsRegion `
            -TimeoutSeconds 60
    }
    $remainingImages = Invoke-BoundedAws `
        -Arguments @(
            'ecr', 'list-images',
            '--repository-name', $repositoryName,
            '--output', 'json'
        ) `
        -Profile $binding.AwsProfile `
        -Region $binding.AwsRegion `
        -TimeoutSeconds 60 `
        -AllowNotFound
    if ($remainingImages -and @($remainingImages.imageIds).Count -ne 0) {
        throw 'The owned ECR repository still contains images.'
    }
}

if ($stack) {
    $null = Invoke-BoundedAws `
        -Arguments @(
            'cloudformation', 'delete-stack',
            '--stack-name', [string]$awsState['stackName']
        ) `
        -Profile $binding.AwsProfile `
        -Region $binding.AwsRegion `
        -TimeoutSeconds 60 `
        -Raw
    $null = Invoke-BoundedAws `
        -Arguments @(
            'cloudformation', 'wait', 'stack-delete-complete',
            '--stack-name', [string]$awsState['stackName']
        ) `
        -Profile $binding.AwsProfile `
        -Region $binding.AwsRegion `
        -TimeoutSeconds $TimeoutSeconds `
        -Raw
}
$remainingStack = Invoke-BoundedAws `
    -Arguments @(
        'cloudformation', 'describe-stacks',
        '--stack-name', [string]$awsState['stackName'],
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds 60 `
    -AllowNotFound
if ($remainingStack) {
    throw 'The owned AWS stack still exists.'
}

$runtimeId = [string]$awsState['runtimeId']
if ($runtimeId) {
    $prefix = "/aws/bedrock-agentcore/runtimes/$runtimeId"
    $logGroups = Invoke-BoundedAws `
        -Arguments @(
            'logs', 'describe-log-groups',
            '--log-group-name-prefix', $prefix,
            '--limit', '20',
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
    foreach ($logGroup in $owned) {
        $null = Invoke-BoundedAws `
            -Arguments @(
                'logs', 'delete-log-group',
                '--log-group-name', [string]$logGroup.logGroupName
            ) `
            -Profile $binding.AwsProfile `
            -Region $binding.AwsRegion `
            -TimeoutSeconds 60 `
            -Raw
    }
    $remainingLogs = Invoke-BoundedAws `
        -Arguments @(
            'logs', 'describe-log-groups',
            '--log-group-name-prefix', $prefix,
            '--limit', '20',
            '--output', 'json'
        ) `
        -Profile $binding.AwsProfile `
        -Region $binding.AwsRegion `
        -TimeoutSeconds 60
    if (
        @(
            $remainingLogs.logGroups |
                Where-Object {
                    $_.logGroupName -eq $prefix -or
                    $_.logGroupName -like "$prefix-*"
                }
        ).Count -ne 0
    ) {
        throw 'An experiment Runtime log group still exists.'
    }
}

$state.Remove('aws')
if ($state.ContainsKey('sessions')) {
    $state.Remove('sessions')
}
Save-ExperimentState -Path $statePath -State $state
Write-Output '{"awsCleanup":"complete"}'

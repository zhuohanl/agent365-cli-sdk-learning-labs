[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath,
    [ValidateRange(60, 3600)][int] $TimeoutSeconds = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')
. (Join-Path $PSScriptRoot 'Aws.ps1')

$binding = Get-GateBinding -Path $BindingPath
$names = Get-ExperimentNames
$statePath = Get-StatePath -BindingPath $BindingPath
$state = Read-ExperimentState -Path $statePath
$labRoot = Split-Path -Parent $PSScriptRoot
$template = Join-Path $labRoot 'infrastructure\template.yaml'

if ($binding.AwsWriteApproval -ne 'approved') {
    throw 'The ignored binding does not approve the AWS write.'
}
if (-not $state.ContainsKey('entra')) {
    throw 'The Entra identity stage is incomplete.'
}

& (Join-Path $PSScriptRoot 'Test-AwsPreflight.ps1') `
    -BindingPath $BindingPath `
    -TimeoutSeconds ([Math]::Min($TimeoutSeconds, 120))

$entra = $state['entra']
$discoveryUrl = (
    "https://login.microsoftonline.com/$($binding.TenantId)" +
    '/v2.0/.well-known/openid-configuration'
)
$issuer = "https://login.microsoftonline.com/$($binding.TenantId)/v2.0"
$gate2McpUrl = if (
    $state.ContainsKey('gate2') -and
    -not $state['gate2']['runtimeDetached'] -and
    $state['gate2']['mcpUrl']
) {
    [string]$state['gate2']['mcpUrl']
}
else { '' }
$gate2SecretName = if (
    $state.ContainsKey('gate2') -and
    -not $state['gate2']['runtimeDetached'] -and
    $state['gate2']['awsSecretName']
) {
    [string]$state['gate2']['awsSecretName']
}
else { '' }
$gate3ModelId = if (
    $binding.Gate34WriteApproval -eq 'approved' -and
    $binding.Gate3ModelId
) {
    $binding.Gate3ModelId
}
else { '' }
$common = @(
    '--template-file', $template,
    '--stack-name', $names.Stack,
    '--capabilities', 'CAPABILITY_NAMED_IAM',
    '--tags',
    'project=agent365-learning-lab',
    'managed-by=issue-206',
    "environment=$($binding.EnvironmentClass)",
    '--parameter-overrides',
    "PlatformName=$($names.Prefix)",
    "RuntimeName=$($names.Runtime)",
    "EnvironmentClass=$($binding.EnvironmentClass)",
    "DiscoveryUrl=$discoveryUrl",
    "ExpectedIssuer=$issuer",
    "AllowedAudience=$($entra['blueprintAppId'])",
    "AllowedClient=$($entra['publicClientAppId'])",
    "AllowedScope=$($names.Scope)",
    "Gate2McpUrl=$gate2McpUrl",
    "Gate2SecretName=$gate2SecretName",
    "Gate3ModelId=$gate3ModelId"
)

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
if (-not $stack) {
    Write-Output '{"phase":"stack-baseline","status":"started"}'
    $null = Invoke-BoundedAws `
        -Arguments (@('cloudformation', 'deploy') + $common + @(
                'RuntimeEnabled=false'
            )) `
        -Profile $binding.AwsProfile `
        -Region $binding.AwsRegion `
        -TimeoutSeconds $TimeoutSeconds `
        -Raw
    Write-Output '{"phase":"stack-baseline","status":"complete"}'
}

$stack = Invoke-BoundedAws `
    -Arguments @(
        'cloudformation', 'describe-stacks',
        '--stack-name', $names.Stack,
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds 60
$repositoryUri = (
    $stack.Stacks[0].Outputs |
        Where-Object { $_.OutputKey -eq 'RepositoryUri' }
).OutputValue
if (-not $repositoryUri) {
    throw 'The stack did not publish the repository URI.'
}

$hashInput = @(
    Get-ChildItem (Join-Path $labRoot 'src') -File -Recurse
    Get-Item (Join-Path $labRoot 'Dockerfile')
    Get-Item (Join-Path $labRoot 'pyproject.toml')
) | Sort-Object FullName
$hashText = ($hashInput | ForEach-Object {
        (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }) -join ''
$tag = (
    [Convert]::ToHexString(
        [Security.Cryptography.SHA256]::HashData(
            [Text.Encoding]::UTF8.GetBytes($hashText)
        )
    )
).Substring(0, 12).ToLowerInvariant()

$images = Invoke-BoundedAws `
    -Arguments @(
        'ecr', 'list-images',
        '--repository-name', $names.Repository,
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds 60
$matchingImage = @(
    $images.imageIds |
        Where-Object {
            $_.PSObject.Properties.Name -contains 'imageTag' -and
            $_.imageTag -eq $tag
        }
)
if ($matchingImage.Count -eq 0) {
    Write-Output '{"phase":"image-build-push","status":"started"}'
    $dockerConfig = Join-Path $env:TEMP "gate1-docker-$([guid]::NewGuid())"
    try {
        $null = New-Item -ItemType Directory -Path $dockerConfig
        $password = Invoke-BoundedAws `
            -Arguments @('ecr', 'get-login-password') `
            -Profile $binding.AwsProfile `
            -Region $binding.AwsRegion `
            -TimeoutSeconds 60 `
            -Raw
        $registry = ($repositoryUri -split '/')[0]
        $password |
            docker --config $dockerConfig login `
                --username AWS `
                --password-stdin $registry | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw 'Docker login failed.'
        }
        Invoke-BoundedNative `
            -FilePath 'docker' `
            -CommandName 'docker buildx build and push' `
            -TimeoutSeconds $TimeoutSeconds `
            -Arguments @(
                '--config', $dockerConfig,
                'buildx', 'build',
                '--platform', 'linux/arm64',
                '--provenance=false',
                '--tag', "${repositoryUri}:$tag",
                '--push',
                $labRoot
            )
    }
    finally {
        $password = $null
        Remove-Item $dockerConfig -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Output '{"phase":"image-build-push","status":"complete"}'
}

Write-Output '{"phase":"runtime-deployment","status":"started"}'
$null = Invoke-BoundedAws `
    -Arguments (@('cloudformation', 'deploy') + $common + @(
            'RuntimeEnabled=true',
            "ImageUri=${repositoryUri}:$tag"
        )) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds $TimeoutSeconds `
    -Raw
Write-Output '{"phase":"runtime-deployment","status":"complete"}'

$stack = Invoke-BoundedAws `
    -Arguments @(
        'cloudformation', 'describe-stacks',
        '--stack-name', $names.Stack,
        '--output', 'json'
    ) `
    -Profile $binding.AwsProfile `
    -Region $binding.AwsRegion `
    -TimeoutSeconds 60
$outputs = @{}
foreach ($output in @($stack.Stacks[0].Outputs)) {
    $outputs[$output.OutputKey] = $output.OutputValue
}
if (-not $state.ContainsKey('aws')) {
    $state['aws'] = @{}
}
$state['aws']['stackName'] = $names.Stack
$state['aws']['repositoryName'] = $names.Repository
$state['aws']['runtimeArn'] = [string]$outputs['AgentRuntimeArn']
$state['aws']['runtimeId'] = [string]$outputs['AgentRuntimeId']
$state['aws']['runtimeVersion'] = [string]$outputs['AgentRuntimeVersion']
Save-ExperimentState -Path $statePath -State $state

Write-Output (@{
        deployment = 'ready'
        runtime = 'ready'
        defaultEndpoint = 'service-created'
        workloadIdentity = 'service-created'
        modelPermission = [bool]$gate3ModelId
        sourcePermission = $false
    } | ConvertTo-Json -Compress)

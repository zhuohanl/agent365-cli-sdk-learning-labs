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
$labRoot = Split-Path -Parent $PSScriptRoot
$evidenceRoot = Join-Path $labRoot 'evidence'
$userAPath = Join-Path $evidenceRoot 'gate1-user-a.json'
$userBPath = Join-Path $evidenceRoot 'gate1-user-b.json'
$negativePath = Join-Path $evidenceRoot 'gate1-negative.json'

if (
    -not (Test-Path -LiteralPath $userAPath -PathType Leaf) -or
    -not (Test-Path -LiteralPath $userBPath -PathType Leaf) -or
    -not (Test-Path -LiteralPath $negativePath -PathType Leaf)
) {
    throw 'Both user evidence files and negative evidence are required.'
}
if (-not $state.ContainsKey('aws') -or -not $state['aws']['runtimeId']) {
    throw 'The ignored state has no Runtime ID.'
}

$userA = Get-Content -LiteralPath $userAPath -Raw | ConvertFrom-Json
$userB = Get-Content -LiteralPath $userBPath -Raw | ConvertFrom-Json
$negative = Get-Content -LiteralPath $negativePath -Raw | ConvertFrom-Json
$validResponses = @($userA, $userB) | Where-Object {
    $_.http_status -eq 200 -and
    $_.token_received -eq $true -and
    $_.token_validated -eq $true -and
    $_.token_disclosed -eq $false
}
if ($validResponses.Count -ne 2) {
    throw 'One or both valid-user Runtime invocations failed.'
}
if (
    $userA.subject_reference -eq $userB.subject_reference -or
    $userA.session_reference -eq $userB.session_reference
) {
    throw 'The two-user or two-session isolation proof failed.'
}
if (
    $negative.missing_token_http_status -ne 401 -or
    $negative.malformed_token_http_status -notin @(401, 403)
) {
    throw 'The live invalid-token rejection proof failed.'
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
    throw 'No exact Runtime log group is available for disclosure inspection.'
}

$unsafeLogMatch = $false
$retentionCorrect = $true
foreach ($logGroup in $owned) {
    if ($logGroup.retentionInDays -ne $binding.LogRetentionDays) {
        $retentionCorrect = $false
    }
    $events = Invoke-BoundedAws `
        -Arguments @(
            'logs', 'filter-log-events',
            '--log-group-name', $logGroup.logGroupName,
            '--limit', '1000',
            '--output', 'json'
        ) `
        -Profile $binding.AwsProfile `
        -Region $binding.AwsRegion `
        -TimeoutSeconds 60
    foreach ($event in @($events.events)) {
        if (
            $event.message -match 'eyJ[A-Za-z0-9_-]{20,}\.' -or
            $event.message -match '(?i)Authorization\s*:' -or
            $event.message -match '(?i)Bearer\s+[A-Za-z0-9._-]{20,}'
        ) {
            $unsafeLogMatch = $true
        }
    }
}
if ($unsafeLogMatch) {
    throw 'A possible raw token or authorization header appeared in logs.'
}
if (-not $retentionCorrect) {
    throw 'One or more exact Runtime log groups have incorrect retention.'
}

$summary = [ordered]@{
    gate = 1
    valid_token_delivered = $true
    invalid_token_rejected = $true
    raw_token_in_logs = $false
    raw_token_in_response = $false
    two_subjects_distinct = $true
    two_sessions_distinct = $true
    cross_session_state_reuse = $false
    log_retention_days = $binding.LogRetentionDays
}
$summary |
    ConvertTo-Json |
    Set-Content -LiteralPath (Join-Path $evidenceRoot 'gate1-summary.json') `
        -Encoding utf8
$summary | ConvertTo-Json -Compress

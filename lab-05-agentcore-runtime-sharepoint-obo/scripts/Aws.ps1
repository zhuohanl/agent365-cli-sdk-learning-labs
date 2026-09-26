Set-StrictMode -Version Latest

function ConvertTo-NativeArgument {
    param([Parameter(Mandatory)][AllowEmptyString()][string] $Value)

    if ($Value -notmatch '[\s"]') {
        return $Value
    }
    $escaped = $Value -replace '(\\*)"', '$1$1\"'
    $escaped = $escaped -replace '(\\+)$', '$1$1'
    return "`"$escaped`""
}

function Get-PublicSafeAwsError {
    param([Parameter(Mandatory)][AllowEmptyString()][string] $Text)

    $safe = $Text -replace '\b[0-9]{12}\b', '<redacted-account>'
    $safe = $safe -replace 'arn:aws[^\s"'']+', '<redacted-arn>'
    $safe = $safe -replace 'https://[^\s"'']+', '<redacted-url>'
    $safe = $safe -replace '\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b', '<redacted-id>'
    if ([string]::IsNullOrWhiteSpace($safe)) {
        return 'AWS CLI returned no diagnostic text.'
    }
    return $safe.Trim()
}

function Invoke-BoundedAws {
    param(
        [Parameter(Mandatory)][string[]] $Arguments,
        [Parameter(Mandatory)][string] $Profile,
        [Parameter(Mandatory)][string] $Region,
        [ValidateRange(5, 3600)][int] $TimeoutSeconds = 60,
        [switch] $AllowNotFound,
        [switch] $Raw
    )

    $commandName = ($Arguments | Select-Object -First 2) -join ' '
    $stdoutPath = Join-Path $env:TEMP "gate1-aws-$([guid]::NewGuid()).out"
    $stderrPath = Join-Path $env:TEMP "gate1-aws-$([guid]::NewGuid()).err"
    $allArguments = @(
        '--profile', $Profile,
        '--region', $Region,
        '--cli-connect-timeout', '10',
        '--cli-read-timeout', [string][Math]::Min($TimeoutSeconds, 60)
    ) + $Arguments + @('--no-cli-pager')
    $argumentLine = (
        $allArguments |
            ForEach-Object { ConvertTo-NativeArgument -Value $_ }
    ) -join ' '

    try {
        $process = Start-Process `
            -FilePath (Get-Command aws).Source `
            -ArgumentList $argumentLine `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -PassThru `
            -NoNewWindow
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.Kill($true)
            $process.WaitForExit()
            throw (
                "AWS command '$commandName' timed out. " +
                'Inspect live state before retrying.'
            )
        }
        $stdout = if (Test-Path $stdoutPath) {
            Get-Content -LiteralPath $stdoutPath -Raw
        }
        else { '' }
        $stderr = if (Test-Path $stderrPath) {
            Get-Content -LiteralPath $stderrPath -Raw
        }
        else { '' }
        if ($process.ExitCode -ne 0) {
            if (
                $AllowNotFound -and
                $stderr -match 'NoSuchEntity|not found|does not exist|NotFoundException|ValidationError'
            ) {
                return $null
            }
            throw (
                "AWS command '$commandName' failed: " +
                (Get-PublicSafeAwsError -Text $stderr)
            )
        }
        if ($Raw) {
            return $stdout
        }
        if ([string]::IsNullOrWhiteSpace($stdout)) {
            return $null
        }
        return $stdout | ConvertFrom-Json
    }
    finally {
        Remove-Item $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
    }
}

function Invoke-BoundedNative {
    param(
        [Parameter(Mandatory)][string] $FilePath,
        [Parameter(Mandatory)][string[]] $Arguments,
        [Parameter(Mandatory)][string] $CommandName,
        [ValidateRange(5, 3600)][int] $TimeoutSeconds
    )

    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList (($Arguments | ForEach-Object {
                    ConvertTo-NativeArgument -Value $_
                }) -join ' ') `
        -PassThru `
        -NoNewWindow
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        $process.Kill($true)
        $process.WaitForExit()
        throw "$CommandName timed out. Inspect live state before retrying."
    }
    if ($process.ExitCode -ne 0) {
        throw "$CommandName failed with exit code $($process.ExitCode)."
    }
}

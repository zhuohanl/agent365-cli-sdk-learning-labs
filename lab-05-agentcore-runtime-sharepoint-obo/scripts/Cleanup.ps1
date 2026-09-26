Set-StrictMode -Version Latest

function Invoke-BoundedGraph {
    param(
        [Parameter(Mandatory)][ValidateSet('GET', 'POST', 'PATCH', 'DELETE')]
        [string] $Method,
        [Parameter(Mandatory)][string] $Uri,
        [hashtable] $Headers = @{},
        [object] $Body,
        [ValidateRange(5, 300)][int] $TimeoutSeconds = 60,
        [int[]] $ExpectedStatus = @(200),
        [switch] $AllowNotFound
    )

    $job = Start-ThreadJob -ArgumentList @(
        $Method,
        $Uri,
        $Headers,
        $Body
    ) -ScriptBlock {
        param($RequestMethod, $RequestUri, $RequestHeaders, $RequestBody)
        Import-Module Microsoft.Graph.Authentication -ErrorAction Stop
        $status = 0
        $parameters = @{
            Method = $RequestMethod
            Uri = $RequestUri
            Headers = $RequestHeaders
            OutputType = 'PSObject'
            SkipHttpErrorCheck = $true
            StatusCodeVariable = 'status'
        }
        if ($null -ne $RequestBody) {
            $parameters.ContentType = 'application/json'
            $parameters.Body = (
                $RequestBody | ConvertTo-Json -Depth 20 -Compress
            )
        }
        $response = Invoke-MgGraphRequest @parameters
        [pscustomobject]@{
            Status = [int]$status
            Body = $response
        }
    }
    try {
        if (-not (Wait-Job -Job $job -Timeout $TimeoutSeconds)) {
            Stop-Job -Job $job
            throw "Graph $Method timed out. Inspect live state before retrying."
        }
        $result = Receive-Job -Job $job -ErrorAction Stop
    }
    finally {
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }
    if ($AllowNotFound -and $result.Status -eq 404) {
        return $null
    }
    if ($result.Status -notin $ExpectedStatus) {
        throw "Graph $Method returned HTTP $($result.Status)."
    }
    return $result.Body
}

function Invoke-BoundedAz {
    param(
        [Parameter(Mandatory)][string[]] $Arguments,
        [ValidateRange(5, 600)][int] $TimeoutSeconds = 60,
        [switch] $AllowNotFound,
        [switch] $Raw
    )

    $commandName = ($Arguments | Select-Object -First 3) -join ' '
    $stdoutPath = Join-Path $env:TEMP "gate-cleanup-az-$([guid]::NewGuid()).out"
    $stderrPath = Join-Path $env:TEMP "gate-cleanup-az-$([guid]::NewGuid()).err"
    $argumentLine = (
        $Arguments |
            ForEach-Object { ConvertTo-NativeArgument -Value $_ }
    ) -join ' '
    try {
        $process = Start-Process `
            -FilePath (Get-Command az).Source `
            -ArgumentList $argumentLine `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -PassThru `
            -NoNewWindow
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.Kill($true)
            $process.WaitForExit()
            throw 'Azure CLI command timed out. Inspect live state before retrying.'
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
                $stderr -match 'not found|could not be found|ResourceNotFound'
            ) {
                return $null
            }
            $safeError = $stderr
            foreach ($argument in @($Arguments | Select-Object -Skip 3)) {
                if (
                    $argument -and
                    -not $argument.StartsWith('--') -and
                    $argument.Length -ge 4
                ) {
                    $safeError = $safeError.Replace(
                        $argument,
                        '<redacted-argument>'
                    )
                }
            }
            $safeError = $safeError -replace 'https://[^\s"'']+', '<redacted-url>'
            $safeError = $safeError -replace '\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b', '<redacted-id>'
            if ([string]::IsNullOrWhiteSpace($safeError)) {
                $safeError = "exit code $($process.ExitCode)"
            }
            throw (
                "Azure CLI command '$commandName' failed: " +
                $safeError.Trim()
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
        Remove-Item $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Wait-Until {
    param(
        [Parameter(Mandatory)][scriptblock] $Test,
        [Parameter(Mandatory)][string] $FailureMessage,
        [ValidateRange(5, 1800)][int] $TimeoutSeconds = 300,
        [ValidateRange(1, 30)][int] $DelaySeconds = 5
    )

    $stopwatch = [Diagnostics.Stopwatch]::StartNew()
    do {
        if (& $Test) {
            return
        }
        Start-Sleep -Seconds $DelaySeconds
    } while ($stopwatch.Elapsed.TotalSeconds -lt $TimeoutSeconds)
    throw $FailureMessage
}

function Assert-GraphAbsent {
    param(
        [Parameter(Mandatory)][string] $Uri,
        [ValidateRange(5, 300)][int] $TimeoutSeconds = 60
    )

    $remaining = Invoke-BoundedGraph `
        -Method GET `
        -Uri $Uri `
        -TimeoutSeconds $TimeoutSeconds `
        -ExpectedStatus @(200) `
        -AllowNotFound
    if ($null -ne $remaining) {
        throw 'A deleted Graph object is still present.'
    }
}

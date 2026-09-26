[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath,
    [string] $UserPrincipalName,
    [ValidateRange(30, 600)][int] $TimeoutSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')

$binding = Get-GateBinding -Path $BindingPath
if ($binding.Gate4LabelPolicyWriteApproval -ne 'approved') {
    throw 'The ignored binding does not approve Gate 4 label-policy publication.'
}
if (-not $UserPrincipalName) {
    $UserPrincipalName = az account show `
        --query user.name `
        --output tsv `
        --only-show-errors
    if ($LASTEXITCODE -ne 0 -or -not $UserPrincipalName) {
        throw 'Specify the Purview administrator user principal name.'
    }
}

$module = Get-Module -ListAvailable ExchangeOnlineManagement |
    Sort-Object Version -Descending |
    Select-Object -First 1
if (-not $module -or $module.Version -lt [version] '3.2.0') {
    throw 'ExchangeOnlineManagement 3.2.0 or later is required.'
}
Import-Module ExchangeOnlineManagement -MinimumVersion 3.2.0 `
    -ErrorAction Stop
$sessionOptions = New-PSSessionOption `
    -OpenTimeout ($TimeoutSeconds * 1000)
Connect-IPPSSession `
    -UserPrincipalName $UserPrincipalName `
    -DisableWAM `
    -PSSessionOption $sessionOptions `
    -ShowBanner:$false `
    -CommandName @('Get-Label') | Out-Null
try {
    $labels = @(Get-Label)
    $mapping = [ordered]@{}
    foreach ($label in $labels) {
        $id = [string]$label.ImmutableId
        $name = [string]$label.DisplayName
        if (-not $id -or -not $name) {
            throw 'Purview returned a label without an ID or display name.'
        }
        if ($mapping.Contains($id)) {
            throw 'Purview returned a duplicate label ID.'
        }
        $mapping[$id] = $name
    }
    $protectedMatches = @(
        $mapping.GetEnumerator() |
            Where-Object {
                [string]$_.Value -eq $binding.ProtectedLabelName
            }
    )
    if ($protectedMatches.Count -ne 1) {
        throw 'The protected label was not resolved exactly once in Purview.'
    }
    $outputPath = Join-Path (
        Split-Path -Parent $BindingPath
    ) 'gate4-labels.local.json'
    [ordered]@{
        schemaVersion = 1
        generatedAtUtc = [DateTime]::UtcNow.ToString('o')
        source = 'purview-security-compliance-powershell'
        labels = $mapping
    } | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $outputPath -Encoding utf8
    Write-Output (@{
        labelDefinitionPublication = 'ready'
        labelCount = $mapping.Count
        protectedLabelResolved = $true
        output = 'gate4-labels.local.json'
    } | ConvertTo-Json -Compress)
}
finally {
    Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue
}

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$labRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $PSScriptRoot 'compose.yaml'
$generatedPath = Join-Path $labRoot 'a365.generated.config.json'

$secureSecret = $null
$secretPointer = [IntPtr]::Zero

function Get-RequiredConfigValue {
    param(
        [Parameter(Mandatory)]
        [object]$Config,

        [Parameter(Mandatory)]
        [string]$Name
    )

    $property = $Config.PSObject.Properties[$Name]
    if (
        $null -eq $property -or
        [string]::IsNullOrWhiteSpace([string]$property.Value)
    ) {
        throw (
            "$Name not found in a365.generated.config.json. " +
            'Check the field names written by the installed CLI. ' +
            'Do not paste their values.'
        )
    }

    return [string]$property.Value
}

try {
    $generated = Get-Content $generatedPath -Raw | ConvertFrom-Json

    $tenantId = az account show --query tenantId --output tsv
    if (
        $LASTEXITCODE -ne 0 -or
        [string]::IsNullOrWhiteSpace($tenantId)
    ) {
        throw 'Could not resolve the tenant from the active Azure CLI account.'
    }

    $env:TENANT_ID = [string]$tenantId
    $env:BLUEPRINT_APP_ID = Get-RequiredConfigValue `
        -Config $generated `
        -Name 'agentBlueprintId'
    $env:AGENT_CLIENT_ID = Get-RequiredConfigValue `
        -Config $generated `
        -Name 'agenticAppId'

    $agentObjectId = az ad sp show `
        --id $env:AGENT_CLIENT_ID `
        --query id `
        --output tsv

    if (
        $LASTEXITCODE -ne 0 -or
        [string]::IsNullOrWhiteSpace($agentObjectId)
    ) {
        throw 'Could not resolve the Agent Identity service principal.'
    }

    $env:AGENT_OBJECT_ID = [string]$agentObjectId

    $secureSecret = Read-Host `
        'Enter the saved blueprint client secret' `
        -AsSecureString
    $secretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR(
        $secureSecret
    )
    $env:BLUEPRINT_CLIENT_SECRET =
        [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer)

    $required = @(
        $env:TENANT_ID
        $env:BLUEPRINT_APP_ID
        $env:BLUEPRINT_CLIENT_SECRET
        $env:AGENT_CLIENT_ID
        $env:AGENT_OBJECT_ID
    )

    if ($required.Where({ [string]::IsNullOrWhiteSpace($_) }).Count -ne 0) {
        throw 'One or more required local values are missing.'
    }

    # Remove any previous sidecar so that this run cannot reuse its token cache.
    docker compose -f $composeFile down --remove-orphans
    docker compose -f $composeFile up --force-recreate -d sidecar
    if ($LASTEXITCODE -ne 0) {
        throw 'The sidecar did not start.'
    }

    # The Python runtime needs the Agent Identity references, not the
    # blueprint credential or tenant configuration.
    Remove-Item Env:TENANT_ID -ErrorAction SilentlyContinue
    Remove-Item Env:BLUEPRINT_APP_ID -ErrorAction SilentlyContinue
    Remove-Item Env:BLUEPRINT_CLIENT_SECRET -ErrorAction SilentlyContinue

    Push-Location $labRoot
    try {
        $env:SIDECAR_URL = 'http://127.0.0.1:5000'
        Write-Host 'Use requests.http from a second terminal.'
        uv run python .\agent.py
    }
    finally {
        Pop-Location
        Remove-Item Env:SIDECAR_URL -ErrorAction SilentlyContinue
    }
}
finally {
    Remove-Item Env:BLUEPRINT_CLIENT_SECRET -ErrorAction SilentlyContinue

    # Compose needs values during interpolation, but cleanup does not use
    # these placeholders to authenticate.
    $env:TENANT_ID = 'cleanup-placeholder'
    $env:BLUEPRINT_APP_ID = 'cleanup-placeholder'
    $env:BLUEPRINT_CLIENT_SECRET = 'cleanup-placeholder'
    docker compose -f $composeFile down --remove-orphans

    Remove-Item Env:TENANT_ID -ErrorAction SilentlyContinue
    Remove-Item Env:BLUEPRINT_APP_ID -ErrorAction SilentlyContinue
    Remove-Item Env:BLUEPRINT_CLIENT_SECRET -ErrorAction SilentlyContinue
    Remove-Item Env:AGENT_CLIENT_ID -ErrorAction SilentlyContinue
    Remove-Item Env:AGENT_OBJECT_ID -ErrorAction SilentlyContinue

    if ($secretPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
    }
    if ($null -ne $secureSecret) {
        $secureSecret.Dispose()
    }
}

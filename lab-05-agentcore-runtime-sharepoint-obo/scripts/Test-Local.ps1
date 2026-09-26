[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$labRoot = Split-Path -Parent $PSScriptRoot
$runtimeImageName = 'lab-agentcore-sharepoint-obo:runtime'
$mcpImageName = 'lab-agentcore-sharepoint-obo:mcp'

Push-Location $labRoot
try {
    uv sync --quiet
    if ($LASTEXITCODE -ne 0) {
        throw 'Dependency restore failed.'
    }

    uv run pytest -q
    if ($LASTEXITCODE -ne 0) {
        throw 'Gate 1 tests failed.'
    }

    uv run python -m py_compile `
        .\scripts\invoke_gate1.py `
        .\scripts\invoke_gate1_negative.py `
        .\scripts\invoke_gate2.py `
        .\scripts\invoke_gate3.py `
        .\scripts\invoke_gate4.py
    if ($LASTEXITCODE -ne 0) {
        throw 'Invocation scripts failed syntax validation.'
    }

    docker build `
        --platform linux/arm64 `
        --tag $runtimeImageName `
        --quiet `
        .
    if ($LASTEXITCODE -ne 0) {
        throw 'ARM64 image build failed.'
    }

    Write-Output 'ARM64_IMAGE_BUILD=True'

    docker build `
        --platform linux/amd64 `
        --tag $mcpImageName `
        --quiet `
        --file .\gate2\Dockerfile `
        .
    if ($LASTEXITCODE -ne 0) {
        throw 'AMD64 MCP image build failed.'
    }

    Write-Output 'AMD64_MCP_IMAGE_BUILD=True'
    Write-Output 'LOCAL_VALIDATION_COMPLETE=True'
}
finally {
    Pop-Location
}

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath,
    [Parameter(Mandatory)][string] $CanonicalBindingPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$module = Join-Path (
    Split-Path -Parent (
        Split-Path -Parent (
            Split-Path -Parent $CanonicalBindingPath
        )
    )
) 'scripts\CommittedFleetBinding.psm1'
Import-Module $module -Force
$canonical = Import-CommittedFleetBinding -Path $CanonicalBindingPath

function Get-CanonicalValue {
    param([Parameter(Mandatory)][string] $Path)

    $node = $canonical
    foreach ($key in $Path.Split('.')) {
        $node = $node.Value[$key]
    }
    $value = ([string]$node.Value).Trim().Trim('"').Trim("'")
    if ([string]::IsNullOrWhiteSpace($value) -or $value -eq 'external') {
        throw "The canonical binding is missing $Path."
    }
    return $value
}

function ConvertTo-YamlQuoted {
    param([Parameter(Mandatory)][string] $Value)

    return ($Value | ConvertTo-Json -Compress)
}

$lines = @(Get-Content -LiteralPath $BindingPath)
$gate2Index = -1
for ($index = 0; $index -lt $lines.Count; $index++) {
    if ($lines[$index] -match '^gate2:\s*$') {
        $gate2Index = $index
        break
    }
}
if ($gate2Index -ge 0) {
    $lines = @($lines | Select-Object -First $gate2Index)
}

$gate2 = @(
    ''
    'gate2:'
    '  subscription_id: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'implementations.orchestrator.subscription_id'
        )
    )
    '  location: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'implementations.orchestrator.location'
        )
    )
    '  resource_group_name: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'implementations.orchestrator.resource_group_name'
        )
    )
    '  container_apps_environment_name: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'implementations.orchestrator.container_apps_environment_name'
        )
    )
    '  container_registry_name: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'implementations.orchestrator.container_registry_name'
        )
    )
    '  key_vault_resource_group_name: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'runtime_foundation.resource_group_name'
        )
    )
    '  key_vault_name: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'runtime_foundation.key_vault_name'
        )
    )
    '  sharepoint_site_url: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'implementations.sharepoint_policy.site_url'
        )
    )
    ''
    'gate3:'
    '  model_id: "anthropic.claude-3-haiku-20240307-v1:0"'
    ''
    'gate4:'
    '  document_library_name: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'implementations.sharepoint_policy.document_library_name'
        )
    )
    '  folder_path: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'implementations.sharepoint_policy.folder_path'
        )
    )
    '  readable_file_name: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'implementations.sharepoint_policy.readable_file_name'
        )
    )
    '  secondary_readable_file_name: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'implementations.sharepoint_policy.secondary_readable_file_name'
        )
    )
    '  protected_file_name: ' + (
        ConvertTo-YamlQuoted (
            Get-CanonicalValue 'implementations.sharepoint_policy.protected_file_name'
        )
    )
)

@($lines + $gate2) |
    Set-Content -LiteralPath $BindingPath -Encoding utf8
Write-Output '{"gate2Binding":"ready","cloudWritePerformed":false}'

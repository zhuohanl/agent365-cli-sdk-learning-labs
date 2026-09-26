Set-StrictMode -Version Latest

function Get-YamlScalarMap {
    param([Parameter(Mandatory)][string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'The ignored binding file does not exist.'
    }

    $values = @{}
    $parents = @()
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*(#.*)?$') {
            continue
        }
        if ($line -notmatch '^(\s*)([^:#]+):(?:\s*(.*))?$') {
            continue
        }
        $level = [int]($matches[1].Length / 2)
        $key = $matches[2].Trim()
        $value = $matches[3].Trim().Trim('"').Trim("'")
        if ($parents.Count -gt $level) {
            if ($level -eq 0) {
                $parents = [string[]]@()
            }
            else {
                $parents = [string[]]@(
                    $parents | Select-Object -First $level
                )
            }
        }
        if ($parents.Count -eq $level) {
            $parents += $key
        }
        else {
            $parents[$level] = $key
        }
        if ($value) {
            $values[$parents -join '.'] = $value
        }
    }
    return $values
}

function Get-RequiredValue {
    param(
        [Parameter(Mandatory)][hashtable] $Values,
        [Parameter(Mandatory)][string] $Key
    )

    if (
        -not $Values.ContainsKey($Key) -or
        [string]::IsNullOrWhiteSpace([string]$Values[$Key])
    ) {
        throw "The ignored binding is missing $Key."
    }
    return [string]$Values[$Key]
}

function Get-GateBinding {
    param([Parameter(Mandatory)][string] $Path)

    $values = Get-YamlScalarMap -Path $Path
    return [pscustomobject]@{
        Values = $values
        ResourcePrefix = Get-RequiredValue $values 'experiment.resource_prefix'
        IdentityWriteApproval = Get-RequiredValue $values 'approvals.identity_write'
        AwsWriteApproval = Get-RequiredValue $values 'approvals.aws_write'
        AzureWriteApproval = Get-RequiredValue $values 'approvals.azure_write'
        Gate34WriteApproval = if ($values.ContainsKey('approvals.gate3_4_write')) {
            [string]$values['approvals.gate3_4_write']
        }
        else { 'pending' }
        Gate4LabelPolicyWriteApproval = if (
            $values.ContainsKey('approvals.gate4_label_policy_write')
        ) {
            [string]$values['approvals.gate4_label_policy_write']
        }
        else { 'pending' }
        Gate4LabelV1AppWriteApproval = if (
            $values.ContainsKey('approvals.gate4_label_v1_app_write')
        ) {
            [string]$values['approvals.gate4_label_v1_app_write']
        }
        else { 'pending' }
        CleanupWriteApproval = Get-RequiredValue $values 'approvals.cleanup_write'
        AwsProfile = Get-RequiredValue $values 'aws.profile'
        AwsAccountId = Get-RequiredValue $values 'aws.account_id'
        AwsRegion = Get-RequiredValue $values 'aws.region'
        EnvironmentClass = Get-RequiredValue $values 'aws.environment_class'
        LogRetentionDays = [int](Get-RequiredValue $values 'aws.log_retention_days')
        CleanupOwner = Get-RequiredValue $values 'aws.cleanup_owner_reference'
        CostCeiling = Get-RequiredValue $values 'aws.monthly_cost_ceiling_reference'
        TenantId = Get-RequiredValue $values 'entra.tenant_id'
        PublicClientRedirectUri = Get-RequiredValue `
            $values 'entra.public_client_redirect_uri'
        RequiredScope = Get-RequiredValue $values 'entra.required_scope'
        AzureSubscriptionId = if ($values.ContainsKey('gate2.subscription_id')) {
            [string]$values['gate2.subscription_id']
        }
        else { '' }
        AzureLocation = if ($values.ContainsKey('gate2.location')) {
            [string]$values['gate2.location']
        }
        else { '' }
        AzureResourceGroup = if ($values.ContainsKey('gate2.resource_group_name')) {
            [string]$values['gate2.resource_group_name']
        }
        else { '' }
        ContainerAppsEnvironment = if ($values.ContainsKey('gate2.container_apps_environment_name')) {
            [string]$values['gate2.container_apps_environment_name']
        }
        else { '' }
        ContainerRegistry = if ($values.ContainsKey('gate2.container_registry_name')) {
            [string]$values['gate2.container_registry_name']
        }
        else { '' }
        KeyVaultResourceGroup = if ($values.ContainsKey('gate2.key_vault_resource_group_name')) {
            [string]$values['gate2.key_vault_resource_group_name']
        }
        else { '' }
        KeyVaultName = if ($values.ContainsKey('gate2.key_vault_name')) {
            [string]$values['gate2.key_vault_name']
        }
        else { '' }
        SharePointSiteUrl = if ($values.ContainsKey('gate2.sharepoint_site_url')) {
            [string]$values['gate2.sharepoint_site_url']
        }
        else { '' }
        Gate3ModelId = if ($values.ContainsKey('gate3.model_id')) {
            [string]$values['gate3.model_id']
        }
        else { '' }
        DocumentLibraryName = if ($values.ContainsKey('gate4.document_library_name')) {
            [string]$values['gate4.document_library_name']
        }
        else { '' }
        FolderPath = if ($values.ContainsKey('gate4.folder_path')) {
            [string]$values['gate4.folder_path']
        }
        else { '' }
        ReadableFileName = if ($values.ContainsKey('gate4.readable_file_name')) {
            [string]$values['gate4.readable_file_name']
        }
        else { '' }
        SecondaryReadableFileName = if ($values.ContainsKey('gate4.secondary_readable_file_name')) {
            [string]$values['gate4.secondary_readable_file_name']
        }
        else { '' }
        ProtectedFileName = if ($values.ContainsKey('gate4.protected_file_name')) {
            [string]$values['gate4.protected_file_name']
        }
        else { '' }
        ProtectedLabelName = if ($values.ContainsKey('gate4.protected_label_name')) {
            [string]$values['gate4.protected_label_name']
        }
        else { '' }
    }
}

function Get-ExperimentNames {
    return [pscustomobject]@{
        Prefix = 'lab-agentcore-sharepoint-obo'
        Runtime = 'lab_agentcore_sharepoint_obo'
        Repository = 'lab-agentcore-sharepoint-obo'
        Role = 'lab-agentcore-sharepoint-obo-runtime-role'
        Stack = 'lab-agentcore-sharepoint-obo'
        Blueprint = 'lab-agentcore-sharepoint-obo-blueprint'
        AgentIdentity = 'lab-agentcore-sharepoint-obo-agent'
        PublicClient = 'lab-agentcore-sharepoint-obo-client'
        ContainerApp = 'lab-agentcore-sharepoint-obo'
        AzureRepository = 'lab-agentcore-sharepoint-obo/gate2-mcp'
        TransportSecret = 'lab-agentcore-sharepoint-obo-mcp-key'
        Fic = 'lab-agentcore-sharepoint-obo-container-app'
        Scope = 'access_agent'
    }
}

function Get-StatePath {
    param([Parameter(Mandatory)][string] $BindingPath)

    return Join-Path (Split-Path -Parent $BindingPath) 'state.local.json'
}

function Read-ExperimentState {
    param([Parameter(Mandatory)][string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @{}
    }
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -AsHashtable
}

function Save-ExperimentState {
    param(
        [Parameter(Mandatory)][string] $Path,
        [Parameter(Mandatory)][hashtable] $State
    )

    $State | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $Path -Encoding utf8
}

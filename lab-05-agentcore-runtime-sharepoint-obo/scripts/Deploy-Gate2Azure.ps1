[CmdletBinding()]
param(
    [Parameter(Mandatory)][string] $BindingPath,
    [ValidateRange(60, 3600)][int] $TimeoutSeconds = 900
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Binding.ps1')

$binding = Get-GateBinding -Path $BindingPath
$names = Get-ExperimentNames
$statePath = Get-StatePath -BindingPath $BindingPath
$state = Read-ExperimentState -Path $statePath
$labRoot = Split-Path -Parent $PSScriptRoot

if ($binding.AzureWriteApproval -ne 'approved') {
    throw 'The ignored binding does not approve Gate 2 Azure writes.'
}
$gate4Configured = @(
    $binding.DocumentLibraryName
    $binding.FolderPath
    $binding.ReadableFileName
    $binding.SecondaryReadableFileName
    $binding.ProtectedFileName
) -notcontains ''
if (
    $gate4Configured -and
    $binding.Gate34WriteApproval -ne 'approved'
) {
    throw 'The ignored binding does not approve Gate 3 and Gate 4 writes.'
}
if (
    $gate4Configured -and
    $binding.Gate4LabelPolicyWriteApproval -ne 'approved'
) {
    throw 'The ignored binding does not approve Gate 4 label-policy writes.'
}
if (
    -not $state.ContainsKey('gate2') -or
    -not $state['gate2']['sitePermissionId'] -or
    -not $state['gate2']['azureSecretId']
) {
    throw 'Gate 2 secrets, Azure skeleton, and Graph setup are required.'
}
$gate2 = $state['gate2']
if (
    $gate4Configured -and (
        -not $gate2['gate4LabelRequiredResourceAccessConfigured'] -or
        -not $gate2['gate4LabelDelegatedGrantConfigured'] -or
        -not $gate2['gate4LabelV1ManagedIdentityAppRoleConfigured']
    )
) {
    throw 'Run Initialize-Gate4LabelPolicy.ps1 before deploying Gate 4 OPA.'
}
$labelMapPath = Join-Path $labRoot 'gate4-labels.local.json'
if ($gate4Configured -and -not (Test-Path -LiteralPath $labelMapPath)) {
    throw 'Run Export-Gate4LabelDefinitions.ps1 before deploying Gate 4 OPA.'
}
$labelNamesBase64 = ''
if ($gate4Configured) {
    $labelMap = Get-Content -LiteralPath $labelMapPath -Raw |
        ConvertFrom-Json -AsHashtable
    if (
        -not $labelMap.ContainsKey('labels') -or
        $labelMap['labels'].Count -eq 0
    ) {
        throw 'The Gate 4 label map is empty or invalid.'
    }
    $protectedMatches = @(
        $labelMap['labels'].GetEnumerator() |
            Where-Object {
                [string]$_.Value -eq $binding.ProtectedLabelName
            }
    )
    if ($protectedMatches.Count -ne 1) {
        throw 'The configured protected label was not resolved exactly once.'
    }
    $labelNamesJson = $labelMap['labels'] | ConvertTo-Json -Compress
    $labelNamesBase64 = [Convert]::ToBase64String(
        [Text.Encoding]::UTF8.GetBytes($labelNamesJson)
    )
}
az account set --subscription $binding.AzureSubscriptionId
if ($LASTEXITCODE -ne 0) {
    throw 'The Azure subscription context could not be selected.'
}

$hashInput = @(
    Get-ChildItem (Join-Path $labRoot 'src') -File -Recurse
    Get-ChildItem (Join-Path $labRoot 'gate2') -File -Recurse
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
$image = "$($gate2['acrLoginServer'])/$($names.AzureRepository):$tag"

az acr login `
    --subscription $binding.AzureSubscriptionId `
    --name $binding.ContainerRegistry `
    --only-show-errors | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Azure Container Registry login failed.'
}
docker buildx build `
    --platform linux/amd64 `
    --provenance=false `
    --tag $image `
    --push `
    --file (Join-Path $labRoot 'gate2\Dockerfile') `
    $labRoot
if ($LASTEXITCODE -ne 0) {
    throw 'The Gate 2 MCP image build and push failed.'
}

$environmentId = az containerapp env show `
    --subscription $binding.AzureSubscriptionId `
    --resource-group $binding.AzureResourceGroup `
    --name $binding.ContainerAppsEnvironment `
    --query id `
    --output tsv
if ($LASTEXITCODE -ne 0 -or -not $environmentId) {
    throw 'The Container Apps environment ID could not be resolved.'
}
$manifestPath = Join-Path $labRoot 'gate2.containerapp.local.yaml'
$manifest = @"
identity:
  type: SystemAssigned
properties:
  managedEnvironmentId: "$environmentId"
  configuration:
    activeRevisionsMode: Single
    ingress:
      external: true
      targetPort: 8080
      transport: auto
      allowInsecure: false
      traffic:
        - weight: 100
          latestRevision: true
    registries:
      - server: $($gate2['acrLoginServer'])
        identity: system
    secrets:
      - name: mcp-key
        keyVaultUrl: $($gate2['azureSecretId'])
        identity: system
  template:
    containers:
      - name: mcp
        image: $image
        resources:
          cpu: 0.25
          memory: 0.5Gi
        env:
          - name: MCP_ENDPOINT_KEY
            secretRef: mcp-key
          - name: OIDC_DISCOVERY_URL
            value: https://login.microsoftonline.com/$($binding.TenantId)/v2.0/.well-known/openid-configuration
          - name: EXPECTED_ISSUER
            value: https://login.microsoftonline.com/$($binding.TenantId)/v2.0
          - name: EXPECTED_AUDIENCE
            value: $($state['entra']['blueprintAppId'])
          - name: EXPECTED_CLIENT_ID
            value: $($state['entra']['publicClientAppId'])
          - name: REQUIRED_SCOPE
            value: $($names.Scope)
          - name: AGENT_CLIENT_ID
            value: $($state['entra']['agentIdentityAppId'])
          - name: SITE_ID
            value: $($gate2['siteId'])
          - name: DOCUMENT_LIBRARY_NAME
            value: $($binding.DocumentLibraryName)
          - name: FOLDER_PATH
            value: $($binding.FolderPath)
          - name: READABLE_FILE_NAME
            value: $($binding.ReadableFileName)
          - name: SECONDARY_READABLE_FILE_NAME
            value: $($binding.SecondaryReadableFileName)
          - name: PROTECTED_FILE_NAME
            value: $($binding.ProtectedFileName)
          - name: PROTECTED_LABEL_NAME
            value: $($binding.ProtectedLabelName)
          - name: LABEL_NAMES_B64
            value: $labelNamesBase64
      - name: sidecar
        image: mcr.microsoft.com/entra-sdk/auth-sidecar:1.0.0-azurelinux3.0-distroless
        resources:
          cpu: 0.25
          memory: 0.5Gi
        env:
          - name: AzureAd__Instance
            value: https://login.microsoftonline.com/
          - name: AzureAd__TenantId
            value: $($binding.TenantId)
          - name: AzureAd__ClientId
            value: $($state['entra']['blueprintAppId'])
          - name: AzureAd__Audience
            value: $($state['entra']['blueprintAppId'])
          - name: AzureAd__Scopes
            value: $($names.Scope)
          - name: AzureAd__ClientCredentials__0__SourceType
            value: SignedAssertionFromManagedIdentity
          - name: AzureAd__ClientCredentials__0__ManagedIdentityClientId
            value: ""
          - name: DownstreamApis__graph__BaseUrl
            value: https://graph.microsoft.com/v1.0/
          - name: DownstreamApis__graph__Scopes__0
            value: https://graph.microsoft.com/Sites.Selected
          - name: DownstreamApis__graph__Scopes__1
            value: https://graph.microsoft.com/Files.Read.All
          - name: DownstreamApis__graph__Scopes__2
            value: https://graph.microsoft.com/InformationProtectionPolicy.Read
          - name: ASPNETCORE_ENVIRONMENT
            value: Production
          - name: ASPNETCORE_URLS
            value: http://+:5000
          - name: AllowedHosts
            value: "*"
    scale:
      minReplicas: 1
      maxReplicas: 1
"@
$manifest | Set-Content -LiteralPath $manifestPath -Encoding utf8

az containerapp update `
    --subscription $binding.AzureSubscriptionId `
    --resource-group $binding.AzureResourceGroup `
    --name $names.ContainerApp `
    --yaml $manifestPath `
    --only-show-errors `
    --output none
if ($LASTEXITCODE -ne 0) {
    throw 'The Gate 2 two-container deployment failed.'
}
$app = az containerapp show `
    --subscription $binding.AzureSubscriptionId `
    --resource-group $binding.AzureResourceGroup `
    --name $names.ContainerApp `
    --only-show-errors `
    --output json | ConvertFrom-Json
$gate2['image'] = $image
$gate2['acrRepositoryOwned'] = $true
$gate2['fqdn'] = [string]$app.properties.configuration.ingress.fqdn
$gate2['mcpUrl'] = "https://$($gate2['fqdn'])/mcp"
Save-ExperimentState -Path $statePath -State $state

& (Join-Path $PSScriptRoot 'Deploy-Gate1.ps1') `
    -BindingPath $BindingPath `
    -TimeoutSeconds $TimeoutSeconds

Write-Output (@{
        gate2Deployment = 'ready'
        containerCount = 2
        systemAssignedIdentity = $true
        mcpIngress = 'https'
        sidecarIngress = 'localhost-only'
    } | ConvertTo-Json -Compress)

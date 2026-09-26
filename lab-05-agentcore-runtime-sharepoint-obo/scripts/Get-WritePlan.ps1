[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$plan = [ordered]@{
    experiment = 'lab-agentcore-sharepoint-obo'
    currentBoundary = 'Gate 1 passed; Gate 2 cloud writes require explicit approval'
    gate1 = [ordered]@{
        identity = @(
            'Create one single-tenant public client with PKCE and no secret.'
            'Create or resume one exact Blueprint and principal.'
            'Expose one access_agent scope and preauthorize the public client.'
            'Create one child Agent Identity.'
        )
        aws = @(
            'Create one ECR repository and push one ARM64 proof image.'
            'Create one proof-minimal Runtime execution role.'
            'Create one HTTP Runtime with Entra JWT authorization.'
            'Allow-list only the Authorization request header.'
            'Accept only the service-created initial version, DEFAULT endpoint, workload identity, and proof logs.'
        )
        proof = @(
            'Invoke with two users and two distinct Runtime session IDs.'
            'Reject wrong issuer, audience, client, expiry, and scope.'
            'Scan Runtime output and logs for token disclosure.'
        )
    }
    gate2 = [ordered]@{
        startCondition = 'Gate 1 passed'
        azure = @(
            'Reuse the approved Container Apps environment, registry, workspace, and Key Vault.'
            'Store one random transport key in AWS Secrets Manager and the existing Azure Key Vault.'
            'Create one proof Container App with exactly MCP and sidecar containers.'
            'Enable one system-assigned managed identity.'
            'Grant that identity AcrPull and Key Vault secret access.'
            'Create one Blueprint federated identity credential.'
            'Declare and consent delegated Graph Sites.Selected for the Blueprint.'
            'Configure Graph scope inheritance with no app-role inheritance.'
            'Grant the child Agent Identity read access to the fixed SharePoint site.'
            'Push one proof MCP image and update the existing Runtime in place.'
        )
        proof = @(
            'Runtime calls one fixed-site metadata operation.'
            'MCP requires endpoint authentication and the user assertion.'
            'Sidecar returns no Microsoft token to Runtime.'
            'Graph returns HTTP 200 for the expected fixed site.'
            'Two simultaneous users cannot share an OBO cache entry.'
        )
    }
    gate3 = [ordered]@{
        startCondition = 'Gate 2 passed and Gate 3/4 scope is approved'
        aws = @(
            'Push one updated Runtime image to the existing ECR repository.'
            'Add bedrock:InvokeModel for only the configured Claude 3 Haiku foundation model.'
            'Update the existing Runtime in place with the model ID.'
        )
        proof = @(
            'A normal user request causes the model to select one bounded metadata tool.'
            'Credentials are attached only by deterministic code after tool selection.'
            'Model input, tool arguments, result, final answer, and logs expose no credential or hidden identity value.'
        )
    }
    gate4 = [ordered]@{
        azure = @(
            'Push one updated MCP image to the existing ACR repository.'
            'Update the existing two-container revision with exact library, folder, and three fixture names.'
            'Do not create or modify SharePoint content, permissions, identities, or Graph consent.'
        )
        proof = @(
            'List only the three configured fixture files.'
            'Read one readable DOCX with bounded text and citation.'
            'Read the protected DOCX and preserve the real Microsoft 365 outcome.'
            'Return no protected content downstream after an authorization denial.'
        )
    }
    stopConditions = @(
        'Any exact binding, approval, cost, or cleanup owner is unavailable.'
        'A duplicate or unrelated matching object exists.'
        'A broader Graph permission, client secret, second Runtime, or new shared baseline is required.'
        'The same failure needs more than two distinct fixes.'
        'A sensitive value would enter tracked or public evidence.'
    )
    cleanup = @(
        'Detach Gate 2 endpoint and secret settings from the Runtime.'
        'Restore prior Blueprint Graph declarations and delegated consent.'
        'Remove the site grant, inheritance configuration, and federated credential.'
        'Remove owned role assignments, Container App, transport secrets, and proof image.'
        'Retain Gate 1 resources until their separate cleanup approval.'
    )
    nextCloudWrite = 'Create the two copies of the random Gate 2 transport key only after azure_write approval.'
}

$plan | ConvertTo-Json -Depth 6

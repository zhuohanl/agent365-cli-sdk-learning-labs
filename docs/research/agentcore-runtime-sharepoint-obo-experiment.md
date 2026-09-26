# AgentCore Runtime delegated SharePoint OBO experiment

## Purpose

This report records the issue-206 feasibility experiment for the proposed
AWS AgentCore Runtime to SharePoint delegated OBO path. It is an implementation
reference for the engineer who builds the production path.

The experiment first tested the two highest-risk boundaries before adding a
model loop or file retrieval:

1. AgentCore Runtime accepts, forwards, and independently validates a
   Microsoft Entra delegated user assertion without token disclosure or
   cross-session reuse.
2. The Runtime calls an Azure Container Apps MCP endpoint whose local Entra
   Auth SDK sidecar obtains a child Agent Identity OBO token and calls a fixed
   SharePoint site through Microsoft Graph.

The approved scope expansion then added Gates 3 and 4. Both gates passed.
Gate 4 first disproved the expected native DLP denial: the exact protected
fixture was selected with the expected delegated child-Agent-Identity token,
but Microsoft Graph returned HTTP 200 and readable content. The revised Gate 4
uses live label extraction, a Purview-admin-published label-definition
snapshot, and OPA as the custom-agent enforcement point.

## Result

The architecture is feasible through the bounded model loop, readable DOCX
retrieval, and label-aware OPA denial before protected content download.
Native Microsoft 365 Copilot DLP does not cover this custom agent-to-Graph
tool path.

| Boundary | Live result |
| --- | --- |
| Entra delegated token to AgentCore front door | Passed |
| AgentCore forwarding of `Authorization` | Passed |
| Runtime signature, issuer, audience, client, expiry, and scope validation | Passed |
| Missing or malformed assertion rejection | Passed |
| Two-user and two-Runtime-session isolation | Passed |
| Runtime to Azure Container Apps MCP call | Passed |
| Container App managed identity to Blueprint federation | Passed |
| Child Agent Identity Graph OBO token | Passed |
| Delegated `Sites.Selected` and fixed-site metadata | Passed |
| No Microsoft token returned to AWS | Passed |
| No token in Runtime or Container App logs | Passed |
| Delegated denial for a user without SharePoint access | Passed |
| Model selects a credential-free bounded tool | Passed |
| Deterministic code attaches credentials after tool selection | Passed |
| Readable DOCX content and citation | Passed |
| Native DLP denial for the custom Graph path | Disproved: Graph returned HTTP 200 and readable content |
| Purview-label prefetch plus OPA pre-download denial | Passed: protected label denied before `/content` |

The authorized test user received Microsoft Graph HTTP 200 for the configured
site. A second user without access to that site received Graph HTTP 403. The
second token still had the expected human subject, child actor, Graph audience,
and `Sites.Selected` scope. This is valid isolation and least-privilege
evidence: the second request did not reuse the first user's OBO token and did
not bypass the second user's SharePoint rights.

Gate 3 used the existing Runtime with one exact Claude 3 Haiku on-demand model.
The model selected the fixed metadata tool from a normal user request. The
model-visible request contained no user token, endpoint key, MCP endpoint,
Blueprint identifier, or child identity identifier. Deterministic Runtime code
attached credentials after selection, returned the safe tool result, and the
model produced a grounded response.

Gate 4 returned a three-item bounded catalog. The controller initially found
that the model could answer from catalog titles without reading a source. The
final controller rejects that premature answer and requires
`policy_source_read` before completion. The readable fixture then returned
bounded DOCX text and a citation. The configured protected fixture also
returned HTTP 200 and readable content for the selected user. The experiment
recorded that real result and stopped instead of inventing a policy denial.

The revised proof calls `extractSensitivityLabels` before content retrieval.
Microsoft Graph's beta label-definition endpoints returned an Azure
Application Gateway HTTP 403 for both a correctly scoped ordinary delegated
user token and an app-only token with
`InformationProtectionPolicy.Read.All`. The failure therefore was not caused
by the child Agent Identity actor or a missing documented beta permission.
Microsoft's separate v1.0
`security/dataSecurityAndGovernance/sensitivityLabels/{labelId}` API was then
live-proved with managed identity application `SensitivityLabel.Read`: it
returned HTTP 200 JSON, the returned name matched the Purview snapshot, and
Graph returned the request correlation headers.

The working control remains configuration-first. A Purview administrator
publishes the current label ID-to-display-name map from Security and
Compliance PowerShell into an ignored local snapshot before deployment.
Unknown IDs use the verified v1.0 API; the old delegated beta route remains a
diagnostic compatibility attempt. An unresolved ID fails closed.

The final live proof confirmed:

- a successfully extracted empty label set is treated as confirmed unlabeled,
  OPA returns `unlabeled_allowed`, and the readable DOCX plus citation are
  returned;
- the protected label ID resolves through the Purview-admin snapshot, OPA
  returns `protected_label_denied`, and no protected `/content` request is
  sent; and
- all expected delegated token relationships and scopes remain valid, with no
  Microsoft token disclosed to AWS or model-visible data.

The subsequent read-only Purview inspection confirmed that the policy is
enabled and its rule is enforced. Its action is
`ExcludeContentProcessing=Block`, while general SharePoint `BlockAccess` is
false. The committed-fleet bootstrap contract in
`platforms/microsoft-power-platform/copilot-studio/agents/agent-01/scripts/PurviewBootstrap.ps1`
verifies that the policy targets only the `Copilot.M365` location. Its
simulation-mode assertion records the original bootstrap state; a human later
moved the policy to enforcement. This is the expected configuration for
blocking supported Copilot knowledge processing; it is not a general Graph
file-read control.

[Microsoft's Agent 365 documentation](https://learn.microsoft.com/en-us/purview/ai-agent-365#data-loss-prevention-and-ai-interactions)
describes DLP blocking for agent-to-human and human-to-agent interactions in
Teams, OneDrive or SharePoint, and email. It does not list DLP blocking for
agent-to-tools, although agent-to-tools auditing is supported. The AgentCore
MCP request is a custom agent-to-tool Graph call, so the observed HTTP 200 is
consistent with the documented enforcement boundary.

## Proven trust chain

The live request path was:

1. A local PKCE client obtained a Blueprint-audience delegated token, `Tc`.
2. AgentCore's JWT authorizer accepted only tokens whose Entra `azp` claim
   matched the approved public client.
3. AgentCore forwarded `Authorization` to the Runtime.
4. Deterministic Runtime code independently validated `Tc`.
5. Runtime read an MCP transport key from AWS Secrets Manager.
6. Runtime called the external MCP endpoint with both `x-mcp-key` and `Tc`.
7. The MCP container validated transport authentication and delegated user
   authority separately.
8. The localhost-only sidecar authenticated the Blueprint with the Container
   App system-assigned managed identity and its federated credential.
9. The sidecar exchanged Blueprint and user authority for a child Agent
   Identity Microsoft Graph OBO token.
10. The MCP container called only the configured fixed-site metadata endpoint.
11. The MCP container returned bounded booleans and safe references, never a
    Microsoft token.

The proof Container App had exactly two containers:

- the external, proof-minimal MCP bridge; and
- `mcr.microsoft.com/entra-sdk/auth-sidecar:1.0.0-azurelinux3.0-distroless`,
  reachable only over localhost.

## Authorization semantics confirmed by the experiment

Delegated `Sites.Selected` uses an intersection, not an elevation:

1. the Blueprint and child must have effective delegated
   `Sites.Selected`;
2. the child must have the fixed-site `read` grant; and
3. the signed-in human must independently be able to access the site.

The child site grant does not grant the human access. A user without site
access must remain denied even when token issuance succeeds. Production tests
should include both an authorized user and an unauthorized user because the
pair proves the success path and the least-privilege boundary.

## Public resource names

The experiment uses deterministic public-safe names:

| Resource | Name |
| --- | --- |
| Prefix | `lab-agentcore-sharepoint-obo` |
| AgentCore Runtime | `lab_agentcore_sharepoint_obo` |
| ECR repository | `lab-agentcore-sharepoint-obo` |
| Runtime role | `lab-agentcore-sharepoint-obo-runtime-role` |
| Blueprint | `lab-agentcore-sharepoint-obo-blueprint` |
| Child Agent Identity | `lab-agentcore-sharepoint-obo-agent` |
| Public client | `lab-agentcore-sharepoint-obo-client` |
| Container App | `lab-agentcore-sharepoint-obo` |
| ACR repository | `lab-agentcore-sharepoint-obo/gate2-mcp` |
| Transport secret | `lab-agentcore-sharepoint-obo-mcp-key` |
| Federated credential | `lab-agentcore-sharepoint-obo-container-app` |

All experiment-owned resources use the equivalent of
`managed-by=issue-206`. Environment-specific identifiers, endpoints, account
references, tenant references, site identifiers, and credentials belong only
in ignored local binding, state, and evidence files.

## Approval and state model

`binding.local.yaml` is ignored and contains independent approval fields for:

- `identity_write`;
- `aws_write`;
- `azure_write`;
- the Gate 3 and Gate 4 expansion;
- both label-policy changes; and
- `cleanup_write`.

Every mutation script checks the approval it needs. `state.local.json` is also
ignored and makes provisioning, deployment, and cleanup resumable. Scripts
must never infer ownership from a name alone when ignored state can prove the
exact object created by this experiment.

At the preservation commit, the completed experiment resources remain in
place only until the separately approved cleanup stage runs. Shared Azure
baselines, the fixed SharePoint site, test files, labels, policies, and users
are never experiment-owned.

## Reproduction flow

Run commands from `lab-05-agentcore-runtime-sharepoint-obo`.

### 1. Local validation

```powershell
pwsh -NoProfile -File .\scripts\Test-Local.ps1
pwsh -NoProfile -File .\scripts\Get-WritePlan.ps1
```

This restores dependencies, runs the tests, syntax-checks the Python clients,
and builds the ARM64 Runtime and amd64 MCP images without a cloud call.

### 2. Initialize Gate 1 identity

```powershell
pwsh -NoProfile -File .\scripts\Initialize-Gate1Identity.ps1 `
  -BindingPath .\binding.local.yaml
```

Keep device-code login and Graph provisioning in the same PowerShell process.
The Graph context used by this experiment did not carry across separate
PowerShell processes.

### 3. Deploy and prove Gate 1

```powershell
pwsh -NoProfile -File .\scripts\Test-AwsPreflight.ps1 `
  -BindingPath .\binding.local.yaml

pwsh -NoProfile -File .\scripts\Deploy-Gate1.ps1 `
  -BindingPath .\binding.local.yaml `
  -TimeoutSeconds 900

uv run python .\scripts\invoke_gate1.py `
  --binding .\binding.local.yaml `
  --label user-a

pwsh -NoProfile -File .\scripts\Set-Gate1LogRetention.ps1 `
  -BindingPath .\binding.local.yaml

uv run python .\scripts\invoke_gate1.py `
  --binding .\binding.local.yaml `
  --label user-b

uv run python .\scripts\invoke_gate1_negative.py `
  --binding .\binding.local.yaml

pwsh -NoProfile -File .\scripts\Test-Gate1Result.ps1 `
  -BindingPath .\binding.local.yaml
```

### 4. Initialize the Gate 2 binding

```powershell
pwsh -NoProfile -File .\scripts\Initialize-Gate2Binding.ps1 `
  -BindingPath .\binding.local.yaml `
  -CanonicalBindingPath <canonical-binding.local.yaml>
```

This copies only the required Azure and SharePoint baseline values into the
ignored lab binding.

### 5. Create Gate 2 secret and Azure skeleton

```powershell
pwsh -NoProfile -File .\scripts\New-Gate2Secrets.ps1 `
  -BindingPath .\binding.local.yaml

pwsh -NoProfile -File .\scripts\New-Gate2AzureSkeleton.ps1 `
  -BindingPath .\binding.local.yaml
```

One random transport key is stored in AWS Secrets Manager and the existing
Azure Key Vault without printing it. The skeleton creates the Container App,
its system-assigned identity, and the narrowly scoped ACR and Key Vault role
assignments.

### 6. Configure Blueprint, Graph, and SharePoint

```powershell
pwsh -NoProfile -File .\scripts\Initialize-Gate2Graph.ps1 `
  -BindingPath .\binding.local.yaml
```

This user-visible command configures:

- Blueprint delegated Graph `Sites.Selected`;
- delegated consent;
- Graph scope inheritance with no app-role inheritance;
- the Blueprint federated identity credential; and
- the child fixed-site `read` grant.

### 7. Deploy the two-container path

```powershell
pwsh -NoProfile -File .\scripts\Deploy-Gate2Azure.ps1 `
  -BindingPath .\binding.local.yaml `
  -TimeoutSeconds 900
```

This builds and pushes the MCP image, deploys exactly MCP plus sidecar, captures
the external MCP URL in ignored state, and updates the existing AgentCore
Runtime in place.

### 8. Run the two-user Gate 2 proof

```powershell
uv run python -u .\scripts\invoke_gate2.py `
  --binding .\binding.local.yaml

pwsh -NoProfile -File .\scripts\Test-Gate2Result.ps1 `
  -BindingPath .\binding.local.yaml
```

Use two distinct accounts. At least one must have access to the configured
site. An HTTP 403 for a second user without site access is expected when all
token relationship checks still pass.

### 9. Deploy and prove Gate 3 and Gate 4

After exact approval, set `approvals.gate3_4_write` to `approved` in the
ignored binding and update the existing Runtime and two-container revision:

```powershell
pwsh -NoProfile -File .\scripts\Deploy-Gate2Azure.ps1 `
  -BindingPath .\binding.local.yaml `
  -TimeoutSeconds 900

uv run python -u .\scripts\invoke_gate3.py `
  --binding .\binding.local.yaml

pwsh -NoProfile -File .\scripts\Test-Gate3Result.ps1 `
  -BindingPath .\binding.local.yaml

uv run python -u .\scripts\invoke_gate4.py `
  --binding .\binding.local.yaml

pwsh -NoProfile -File .\scripts\Test-Gate4Result.ps1 `
  -BindingPath .\binding.local.yaml
```

`Test-Gate4Result.ps1` persists the real protected-file outcome before it
stops. A readable protected fixture sets `scenario_revision_required=true`;
it is not converted into a denial.

## Script inventory

### Shared PowerShell support

| Script | Responsibility |
| --- | --- |
| `scripts/Binding.ps1` | Parse ignored scalar bindings, derive exact public names, and load or save ignored resumable state. |
| `scripts/Aws.ps1` | Run bounded AWS CLI commands with explicit profile, Region, timeout, and safe not-found handling. |
| `scripts/Cleanup.ps1` | Run bounded Graph and Azure requests and verify deletion or restoration against live state. |
| `scripts/Get-WritePlan.ps1` | Print the public-safe mutation sequence, stop conditions, and cleanup order without cloud calls. |
| `scripts/Remove-Experiment.ps1` | Run Gate 2, AWS, and Entra cleanup in dependency order, stopping on the first failure. |
| `scripts/Stop-RuntimeSessions.ps1` | Stop tracked OAuth/JWT Runtime sessions through bounded bearer-authenticated HTTPS and retain state on failure. |
| `scripts/Test-CleanupResult.ps1` | Prove experiment-owned resources are absent, shared Azure baselines remain, and the SharePoint proof files still exist. |
| `scripts/Test-Local.ps1` | Restore dependencies, run tests, syntax-check clients, and build both architecture-specific images. |

### Gate 1 PowerShell

| Script | Responsibility |
| --- | --- |
| `scripts/Connect-Gate1Graph.ps1` | Authenticate Microsoft Graph with device code in the current process. |
| `scripts/Initialize-Gate1Identity.ps1` | Keep Graph login and identity provisioning in one process. |
| `scripts/New-Gate1Identity.ps1` | Create or resume the public client, Blueprint, principal, exposed scope, preauthorization, and child Agent Identity. |
| `scripts/Test-AwsPreflight.ps1` | Confirm account, Region, caller, quotas, ownership, collision, cost, and cleanup prerequisites. |
| `scripts/Deploy-Gate1.ps1` | Build and push the Runtime image and create or update the AgentCore stack and Runtime. |
| `scripts/Set-Gate1LogRetention.ps1` | Apply the proof-minimal one-day Runtime log retention. |
| `scripts/Test-Gate1Result.ps1` | Validate positive and negative evidence and scan Runtime logs for disclosure. |
| `scripts/Remove-Gate1Aws.ps1` | Remove only owned Runtime, logs, ECR, and role resources after cleanup approval. |
| `scripts/Remove-Gate1Identity.ps1` | Remove only owned Entra Gate 1 identities and grants after cleanup approval. |

### Gate 2 PowerShell

| Script | Responsibility |
| --- | --- |
| `scripts/Initialize-Gate2Binding.ps1` | Copy the approved Azure and SharePoint baseline into the ignored lab binding. |
| `scripts/New-Gate2Secrets.ps1` | Create one random transport key in AWS Secrets Manager and Azure Key Vault without disclosure. |
| `scripts/New-Gate2AzureSkeleton.ps1` | Create the Container App system identity and its ACR and Key Vault access. |
| `scripts/Initialize-Gate2Graph.ps1` | Configure Graph declaration, delegated consent, scope inheritance, FIC, site resolution, and child site grant. |
| `scripts/Deploy-Gate2Azure.ps1` | Push the MCP image, deploy MCP plus sidecar, and update the existing Runtime. |
| `scripts/Test-Gate2Result.ps1` | Validate OBO claims, site result, two-user isolation, topology, and log disclosure; persist public-safe validation evidence. |
| `scripts/Remove-Gate2.ps1` | Detach Runtime configuration, restore prior Graph state, and remove only Gate 2 owned resources after cleanup approval. |
| `scripts/Test-Gate3Result.ps1` | Validate model tool selection, deterministic credential attachment, grounded output, and Runtime plus ACA log safety. |
| `scripts/Test-Gate4Result.ps1` | Validate bounded catalog/read behavior and persist the protected fixture's real outcome without simulating denial. |

### Python clients and Runtime code

| File | Responsibility |
| --- | --- |
| `scripts/invoke_gate1.py` | Acquire a PKCE token, invoke AgentCore over HTTPS, and save public-safe evidence. |
| `scripts/invoke_gate1_negative.py` | Prove missing and malformed assertions are rejected at the AgentCore boundary. |
| `scripts/invoke_gate2.py` | Acquire two distinct assertions in memory and invoke the Runtime concurrently. |
| `scripts/invoke_gate3.py` | Run the one-tool model proof and persist only public-safe model/tool evidence. |
| `scripts/invoke_gate4.py` | Run readable and protected user questions without persisting answers or document content. |
| `src/runtime_app.py` | Implement the AgentCore HTTP contract, deterministic token validation, and bounded Gate 2 orchestration. |
| `src/token_validation.py` | Perform OIDC discovery, JWKS signature checks, claim checks, case-insensitive header extraction, and safe reference generation. |
| `src/gate2_client.py` | Read the transport key from AWS Secrets Manager and call the MCP JSON-RPC operation. |
| `src/model_loop.py` | Run the bounded Bedrock Converse loop, enforce tool sequencing, and keep credentials outside model-visible data. |
| `gate2/mcp_app.py` | Validate transport and user authority, call the local sidecar, validate safe Graph relationships, and request fixed-site metadata. |

### Infrastructure and tests

| File | Responsibility |
| --- | --- |
| `infrastructure/template.yaml` | Define ECR, the Runtime role, AgentCore Runtime, Entra JWT authorization, forwarded headers, Gate 2 environment, and narrow secret access. |
| `Dockerfile` | Build the Linux ARM64 AgentCore Runtime image. |
| `gate2/Dockerfile` | Build the Linux amd64 MCP image. |
| `tests/test_gate1_runtime.py` | Cover token validation, disclosure prevention, concurrency, proxy header casing, and Gate 2 forwarding. |
| `tests/test_invoke_gate1.py` | Cover callback handling, stale OAuth callbacks, safe diagnostics, and Entra `azp` authorization configuration. |
| `tests/test_gate2_mcp.py` | Prove MCP output never exposes user or Graph tokens. |
| `tests/test_model_loop.py` | Prove credentials remain outside model-visible requests and premature catalog-only answers cannot bypass source reads. |

## Important implementation findings

### AgentCore authorization must match Entra `azp`

AgentCore `AllowedClients` evaluates the JWT `client_id` claim. Entra v2
delegated access tokens identify the public client in `azp`. The working
configuration uses an exact custom claim rule for `azp`.

### Forwarded HTTP header names are case-insensitive

AgentCore or an intermediary can change header casing. Converting headers to a
plain case-sensitive dictionary caused valid assertions to disappear. Every
lookup for `Authorization` and Runtime session headers must remain
case-insensitive.

### AgentCore can wrap Runtime failures

AgentCore can return HTTP 424 `RuntimeClientError` when the container returns a
4xx or 5xx. Diagnostics must inspect Runtime logs and must not assume the outer
status is the container's original status.

### OAuth callback servers must ignore stale requests

A stopped login flow can leave a browser page that later calls a new local
callback listener with an old `state`. Browser probes can do the same. The
callback server must continue until it receives the expected state or reaches
its timeout; it must not exit after the first request.

### Graph scope creation and preauthorization are separate writes

Microsoft Graph rejected a PATCH that created a new exposed scope and
referenced that scope in `preAuthorizedApplications` in the same request.
Create the scope first, wait for it to exist, and then add preauthorization.

### Graph login context is process-local in this environment

A device-code context created in one PowerShell process was not usable by a
later process. Keep authentication and dependent Graph mutations in the same
process.

### Key Vault network changes can lag

The existing Key Vault initially rejected the secret write with
`ForbiddenByConnection`. After public network access was enabled, the control
plane reported the new setting before the data plane accepted it. The
resumable secret script succeeded after propagation without creating a second
AWS secret.

### Delegated access preserves human authorization

The experiment confirmed the intended intersection. A valid child OBO token
does not let a user read a site that the user cannot access. This behavior is
required, not a failure of OBO.

### Prompt instructions are not a sufficient sequencing control

Claude could list the catalog and answer from source titles without calling
`policy_source_read`, despite the system instruction. The working controller
checks the completed tool trace. If Gate 4 has listed sources but not read one,
it rejects the premature answer and asks the model to select an opaque source
ID and call the read tool.

### Copilot DLP does not authorize or deny a custom Graph file read

The configured protected fixture was readable for the selected human and child
actor because the DLP action controls supported Copilot content processing,
not general Graph `/content` authorization. The reference AWS implementation
uses the same classification in a different way: deterministic MCP code calls
Graph `extractSensitivityLabels`, resolves the label, and supplies it to an
OPA pre-tool-call policy. OPA denies a Confidential item before any
`/content` request.

That design is implemented under the separately approved permission contract.
Microsoft documents
`Files.Read.All` as the least-privileged delegated permission for
[`extractSensitivityLabels`](https://learn.microsoft.com/en-us/graph/api/driveitem-extractsensitivitylabels);
the experiment retains `Sites.Selected` and adds `Files.Read.All` only for
label extraction. It must not infer a label from the fixture name or simulate
the OPA result.

## Guidance for the production implementer

- Keep token handling in deterministic controller and tool code. Do not put
  `Tc`, Blueprint exchange tokens, Graph tokens, or authorization headers in
  prompts, model messages, tool arguments, traces, or business results.
- Authenticate the cross-cloud transport independently from delegated user
  authority. The endpoint key proves the approved Runtime caller; `Tc` proves
  the signed-in human.
- Keep user assertions request-local. Do not persist them and do not use a
  process-global token cache that can cross users or Runtime sessions.
- Key every reusable OBO cache entry by all authority-defining inputs,
  including the human subject, tenant, child identity, resource, and scopes.
- Validate the Blueprint audience assertion at both the AgentCore front door
  and the Runtime before making an outbound call.
- Keep the sidecar localhost-only and deploy MCP plus sidecar in the same
  Container App revision.
- Keep delegated `Sites.Selected` as the approved site-content boundary.
  Gate 4 separately approves `Files.Read.All` for label extraction,
  `InformationProtectionPolicy.Read` for legacy delegated diagnostics, and
  `SensitivityLabel.Read` on the Container App managed identity for the
  supported v1.0 label-definition fallback. `Sites.Read.All` remains absent.
- Refresh `gate4-labels.local.json` through the Purview-admin publication
  script before the first deployment and after label lifecycle or publication
  changes. Treat an invalid snapshot, failed extraction, unavailable OPA, or
  failed v1.0 fallback for an unknown ID as a denial.
- Treat Graph HTTP 403 for an unauthorized human as an expected authorization
  result. Do not turn it into a success-shaped fallback.
- Preserve correlation references that are safe to log, but never log raw
  identifiers or tokens.
- Make every provisioning and cleanup operation resumable and ownership
  checked.

## Preservation state

The preservation commit keeps the issue-206 implementation as a reusable
reference, including:

- the public PKCE client, Blueprint, and child Agent Identity;
- the AgentCore Runtime, ECR repository, execution role, and authorizer;
- the Container App, system identity, FIC, MCP container, and sidecar;
- the transport secrets and narrow role assignments; and
- the delegated `Sites.Selected` declaration, inheritance, consent, and site
  grant.

Gate 3 updated the existing Runtime in place and added one exact model
permission. The deterministic controller validates and separates the user
assertion before model invocation.

Gate 4 extended the fixed operation with bounded file fixtures:

1. readable metadata and content for an authorized user;
2. denial for a user without site access;
3. a sensitivity-labelled or protected fixture whose selected-user outcome
   is currently readable; and
4. evidence that the result follows delegated human authority and current
   SharePoint protection, not app-only assumptions.

The owner accepted the completed proof as an experiment and approved cleanup.
The tracked reference remains after the live experiment resources are removed.

## Cleanup after all gates

After explicit cleanup approval:

```powershell
pwsh -NoProfile -File .\scripts\Remove-Experiment.ps1 `
  -BindingPath .\binding.local.yaml `
  -TimeoutSeconds 900
```

The orchestrator first detaches the Runtime from the MCP endpoint and AWS
secret, restores the previous Blueprint Graph declaration and delegated
consent, and removes the owned site grant, inheritance, FIC, role assignments,
Container App, secrets, and MCP image. It then removes the owned AWS stack,
Runtime logs, and Entra identities. Every mutation has a bounded timeout and
live-state verification. A failure preserves the unfinished state key for a
safe retry; completion is reported only after the final verifier confirms the
owned objects are absent and the shared Azure and SharePoint baselines remain.

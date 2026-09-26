# Lab 5: Prove the AgentCore Runtime delegated SharePoint path

## User task

Determine whether the two highest-risk boundaries in the approved
AgentCore-to-SharePoint OBO design work before implementing the full agent:

1. AgentCore Runtime validates and forwards one Microsoft Entra user
   assertion without leaking or sharing it between sessions.
2. Runtime calls one Azure Container Apps MCP probe whose local Entra Auth SDK
   sidecar obtains a child Agent Identity OBO token and returns fixed-site
   metadata through Microsoft Graph.

The approved scope expansion also proves Gates 3 and 4 with one bounded model
loop and three pre-existing fixed SharePoint fixtures. This lab still does not
add a production UI, Agent 365 registration, general-purpose SharePoint
search, content mutation, or general-purpose MCP operations.

## Expected result

- Gate 1 proves valid token delivery, invalid-token rejection, no raw-token
  disclosure, and two-session isolation.
- Gate 2 proves the Runtime-to-ACA network hop, managed-identity-backed
  Blueprint authentication, child OBO, fixed-site HTTP 200, and user-bound
  token-cache isolation.
- Gate 3 proves model tool selection without model-visible credentials.
- Gate 4 proves bounded readable content and OPA denial of the protected
  Purview label before content download.
- A failure stops the experiment after at most two distinct fixes for the
  same boundary.

See [expected-output.md](expected-output.md) for the public-safe result shape.
See the
[research report](../docs/research/agentcore-runtime-sharepoint-obo-experiment.md)
for the complete script inventory, live findings, and implementation guidance.

## Safety boundary

- Do not put tokens, credentials, tenant IDs, site IDs, user IDs, account IDs,
  ARNs, endpoints, or local paths in tracked files or public evidence.
- Use `binding.local.yaml` for experiment-local references. It is ignored.
- Use `evidence/*.json` for controlled evidence. These files are ignored.
- Put secrets only in an approved external store.
- Do not modify or clean up the existing issue-60 Runtime or any untagged AWS
  Runtime.
- Stop before every cloud mutation until its exact plan is approved.
- The first approved mutation is the experiment public-client application.

## Fixed public names

| Object | Public-safe name |
| --- | --- |
| Resource prefix | `lab-agentcore-sharepoint-obo` |
| Runtime | `lab_agentcore_sharepoint_obo` |
| ECR repository | `lab-agentcore-sharepoint-obo` |
| Execution role | `lab-agentcore-sharepoint-obo-runtime-role` |
| Blueprint | `lab-agentcore-sharepoint-obo-blueprint` |
| Child Agent Identity | `lab-agentcore-sharepoint-obo-agent` |
| Public client | `lab-agentcore-sharepoint-obo-client` |

Every owned object must carry the equivalent of `managed-by=issue-206`.

## Prerequisites

- The canonical committed-fleet binding is valid.
- AWS authentication uses the approved non-root IAM Identity Center operator.
- The active AWS account and Runtime Region match the approved binding.
- The existing account budget, cost ceiling, and cleanup owner are recorded.
- Docker can build a Linux ARM64 image.
- The active Microsoft Entra tenant matches the approved binding.
- Two distinct interactive users are available for the isolation proof.
- The three Entra names and three AWS names above have no collision.
- A Purview administrator can run `Get-Label` through Security and Compliance
  PowerShell and owns the Gate 4 label-map publication cadence.
- The ignored `gate4-labels.local.json` mapping is refreshed before the first
  Gate 4 deployment and after every label lifecycle or publication change.

The completed read-only preflight found two unrelated existing Runtime
objects. One is owned by issue 60 and one is untagged. Both are retained.

## Local validation

From this lab directory:

```powershell
Copy-Item .\binding.example.yaml .\binding.local.yaml
pwsh -NoProfile -File .\scripts\Test-Local.ps1
pwsh -NoProfile -File .\scripts\Get-WritePlan.ps1
```

Populate only the ignored local binding. Do not paste its values into a
tracked file or issue comment.

`Test-Local.ps1` restores dependencies, runs all tests, syntax-checks the
invocation clients, and builds the ARM64 Runtime plus amd64 MCP images
locally. It performs no cloud calls.

`Get-WritePlan.ps1` prints the public-safe mutation sequence and stop
boundaries. It performs no cloud calls.

## Gate 1 commands

These commands are documentation until the matching approval field in the
ignored binding is set to `approved`.

Create the Entra proof identities:

```powershell
pwsh -NoProfile -File .\scripts\Initialize-Gate1Identity.ps1 `
  -BindingPath .\binding.local.yaml
```

The initializer keeps device-code login and resource creation in one
PowerShell process. Do not run the connect and create scripts in separate
`pwsh` processes because Microsoft Graph process context does not cross that
boundary.

Run the final read-only AWS preflight, then deploy:

```powershell
pwsh -NoProfile -File .\scripts\Test-AwsPreflight.ps1 `
  -BindingPath .\binding.local.yaml

pwsh -NoProfile -File .\scripts\Deploy-Gate1.ps1 `
  -BindingPath .\binding.local.yaml `
  -TimeoutSeconds 900
```

Invoke user A, apply retention after the first log group appears, then invoke
user B:

```powershell
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

The live negative test proves AgentCore rejects missing and malformed tokens.
The signed local tests separately cover wrong issuer, audience, authorized
client, expiry, and scope without creating extra clients or waiting for token
expiry.

## Gate 1 implementation

The Runtime implements only:

- `GET /ping`;
- `POST /invocations`;
- a custom JWT authorizer at the AgentCore boundary;
- an explicit `Authorization` request-header allow-list; and
- deterministic in-container validation of issuer, audience, authorized
  client, expiry, signature, and required scope.

The container creates only keyed, process-local safe references for the
subject and Runtime session. It does not retain the token or return claims.

Gate 1 uses a local PKCE test client rather than an Azure-hosted UI. The two
users invoke the Runtime with distinct Runtime session IDs. This removes UI
deployment from the feasibility proof without changing the Runtime boundary.

## Gate 2 implementation

Gate 2 starts only after Gate 1 passes.

It adds:

- one proof Container App in the approved existing Container Apps
  environment;
- exactly two containers: a fixed-site metadata MCP probe and a localhost-only
  Entra Auth SDK sidecar;
- the Container App system-assigned managed identity;
- one Blueprint federated identity credential;
- one fixed-site metadata operation;
- independent endpoint-key and user-assertion checks; and
- public-safe correlation across Runtime, MCP, sidecar, and Graph.

The Graph token stays in the Container App. Runtime receives only the bounded
site result.

## Gate 2 commands

First copy the approved Azure and SharePoint baseline values into the ignored
lab binding. This is a local-only operation:

```powershell
pwsh -NoProfile -File .\scripts\Initialize-Gate2Binding.ps1 `
  -BindingPath .\binding.local.yaml `
  -CanonicalBindingPath <canonical-binding.local.yaml>
```

Stop here until the exact Gate 2 mutation plan is approved and
`approvals.azure_write` is set to `approved` in the ignored binding.

After approval, create the matching transport secrets and the empty Container
App skeleton:

```powershell
pwsh -NoProfile -File .\scripts\New-Gate2Secrets.ps1 `
  -BindingPath .\binding.local.yaml

pwsh -NoProfile -File .\scripts\New-Gate2AzureSkeleton.ps1 `
  -BindingPath .\binding.local.yaml
```

Configure Blueprint federation, delegated Graph access, scopes-only
inheritance, and the child fixed-site read grant. Run this in a user-visible
terminal because device-code authentication may be required:

```powershell
pwsh -NoProfile -File .\scripts\Initialize-Gate2Graph.ps1 `
  -BindingPath .\binding.local.yaml
```

Build and push the MCP image, deploy exactly the MCP and sidecar containers,
then update the existing Runtime in place:

```powershell
pwsh -NoProfile -File .\scripts\Deploy-Gate2Azure.ps1 `
  -BindingPath .\binding.local.yaml `
  -TimeoutSeconds 900
```

Run the two-user proof. Sign in as user A, then as a distinct user B; both
assertions remain memory-only and the Runtime calls run concurrently:

```powershell
uv run python .\scripts\invoke_gate2.py `
  --binding .\binding.local.yaml

pwsh -NoProfile -File .\scripts\Test-Gate2Result.ps1 `
  -BindingPath .\binding.local.yaml
```

Gate 2 passes when both users receive Runtime HTTP 200, at least one
authorized user receives Graph HTTP 200 for the fixed site, all
user/session/correlation references are distinct, and neither Runtime
responses nor Container App logs contain a Microsoft token. A second user
without SharePoint access may receive Graph HTTP 403; this is valid isolation
evidence when that Graph token's human subject still matches the second user.

## Gate 3 and Gate 4 implementation

Gate 3 reuses the existing Runtime and adds only one exact on-demand
foundation model. The model sees a normal user message and a credential-free
tool schema. Deterministic Runtime code attaches the user assertion and MCP
transport key only after the model selects the tool.

Gate 4 adds exactly two model tools:

- `policy_sources_list` lists only the three fixture names configured from the
  canonical ignored binding; and
- `policy_source_read` accepts one opaque source ID returned by the list call.

The MCP resolves the exact site, document library, folder, and fixture names
server-side. For Gate 4's revised protected path, deterministic MCP code must
resolve the live Purview sensitivity label before downloading content, pass
the normalized label fact to OPA, and call `/content` only after OPA allows
the read. An unresolved label or unavailable policy engine fails closed.

Native Purview `ExcludeContentProcessing` applies to the Microsoft 365 Copilot
location and does not block this custom Graph agent-to-tool request. Gate 4
must identify OPA as the enforcer and must not report a SharePoint or Purview
DLP denial.

The separately approved label-read boundary retains `Sites.Selected`, adds
delegated `Files.Read.All` and `InformationProtectionPolicy.Read`, and does
not add `Sites.Read.All`. The Container App managed identity has application
`SensitivityLabel.Read` for the supported Microsoft Graph v1.0
`dataSecurityAndGovernance` label-definition fallback. The older beta
label-definition paths return Azure Application Gateway HTTP 403 in this
tenant even with their documented permissions. The working primary path is a
Purview-admin-published ID-to-name snapshot; unknown IDs use the verified
v1.0 fallback and fail closed if they remain unresolved.

## Gate 3 and Gate 4 commands

Keep `approvals.gate3_4_write` set to `pending` until the exact Runtime IAM,
image, Container App revision, and paid model invocation plan is approved.
After approval, set it to `approved` in the ignored binding and update the
existing two-container deployment and Runtime in place:

```powershell
pwsh -NoProfile -File .\scripts\Initialize-Gate4LabelPolicy.ps1 `
  -BindingPath .\binding.local.yaml

pwsh -NoProfile -File .\scripts\Export-Gate4LabelDefinitions.ps1 `
  -BindingPath .\binding.local.yaml

pwsh -NoProfile -File .\scripts\Deploy-Gate2Azure.ps1 `
  -BindingPath .\binding.local.yaml `
  -TimeoutSeconds 900
```

`Export-Gate4LabelDefinitions.ps1` is a mandatory prerequisite, not optional
evidence collection. Re-run it whenever a Purview administrator adds,
replaces, renames, retires, or republishes a sensitivity label. Deployment
stops if the ignored mapping is absent, empty, or cannot resolve the protected
label exactly once.

Run the one-tool model proof:

```powershell
uv run python -u .\scripts\invoke_gate3.py `
  --binding .\binding.local.yaml

pwsh -NoProfile -File .\scripts\Test-Gate3Result.ps1 `
  -BindingPath .\binding.local.yaml
```

Run the readable and protected file proof with the same authorized user:

```powershell
uv run python -u .\scripts\invoke_gate4.py `
  --binding .\binding.local.yaml

pwsh -NoProfile -File .\scripts\Test-Gate4Result.ps1 `
  -BindingPath .\binding.local.yaml
```

The completed command records both the native Graph relationships and the OPA
decision. The revised Gate 4 proves:

- the live sensitivity label was resolved before content download;
- OPA allowed the readable or confirmed-unlabeled fixture and denied the
  protected label;
- no `/content` request was sent for the protected item;
- label or policy resolution failures deny without content; and
- no protected content or credential enters model-visible data or evidence.

## Retained state

Gate 1 resources are retained only long enough to run Gate 2. Gate 2 resources
are retained only until the final evidence is recorded or the approved
retention deadline is reached.

Do not clean up shared Azure baselines, existing budgets, existing test users,
the selected SharePoint site, or unrelated identity objects.

## Cleanup order

After `approvals.cleanup_write` is explicitly set to `approved`, run the
ownership-checked orchestrator:

```powershell
pwsh -NoProfile -File .\scripts\Remove-Experiment.ps1 `
  -BindingPath .\binding.local.yaml `
  -TimeoutSeconds 900
```

The orchestrator stops on the first failure and leaves the unfinished object
in ignored state. Each delete compares live identity or ownership evidence,
uses a bounded command or wait, and verifies absence or restored state before
removing its state key. It preserves the shared Container Apps environment,
registry, monitoring workspace, Key Vault, resource groups, SharePoint
content, labels, policies, and user permissions.

Because the Runtime uses OAuth/JWT inbound authorization, tracked Runtime
sessions are stopped through bounded bearer-authenticated HTTPS rather than
the SigV4 AWS CLI operation. The cleanup opens the approved public-client
interactive sign-in only when tracked sessions remain.

If the shared Key Vault enforces purge protection, cleanup deletes the active
experiment secret, verifies the exact soft-deleted record, retains its
scheduled platform purge in ignored state, and continues deleting unrelated
experiment resources. Final verification remains incomplete until Key Vault
automatically purges that record; the script never weakens the shared Vault.

Cleanup removes owned objects in dependency order:

1. stop active proof sessions;
2. detach the Runtime from Gate 2 and remove Gate 2 owned resources;
3. restore the previous Blueprint Graph declaration and delegated grant;
4. remove both experiment managed-identity Graph app-role assignments;
5. remove the owned Azure role assignments, Container App, transport secrets,
   and all manifests under the experiment-only MCP repository path;
6. delete the experiment Runtime stack and wait for its service-created
   children;
7. delete only the experiment Runtime log groups;
8. remove the public client, child Agent Identity, Blueprint principal, and
   Blueprint; and
9. verify all experiment-owned resources are absent while shared Azure
   baselines remain.

The cleanup command must prove exact ownership before each deletion and report
partial failures without claiming completion.

# Identity stack provisioning research

Research date: 2026-09-12

## Question

Is there a supported CLI or API workflow that is better than individually
creating and reconciling the following objects and permission state?

1. Agent Identity Blueprint;
2. tenant-local Blueprint principal;
3. Agent Identity; and
4. Blueprint or Agent Identity permissions.

The desired workflow must stop before Agent Registration creation so Lab 20
can create the companion Registration once, with its final deterministic
`sourceAgentId`.

## Conclusion

There is no verified atomic or declarative full-stack operation that creates
the complete identity stack and stops before Registration.

The best current implementation seam remains an **identity-only Microsoft
Graph v1.0 reconciler**:

1. ensure the dedicated or explicitly shared Blueprint;
2. ensure its tenant-local principal;
3. apply the approved permission profile;
4. ensure the Agent Identity;
5. read back and persist every resulting ID and permission outcome; and
6. return those identity references without creating an Agent Registration.

The companion Registration remains a separate operation. Its create request
should contain the final companion source ID, Blueprint app ID, and Agent
Identity object ID together.

Two first-party tools can reduce implementation work but do not replace that
seam:

- `a365 setup blueprint` is a useful Blueprint-and-principal provisioning
  implementation with credential and permission behavior.
- Microsoft Entra PowerShell provides the closest interactive end-to-end
  identity workflow through `Invoke-EntraAgentIdInteractive`.

Neither is a stack transaction. `a365 setup all` is not suitable because its
normal identity-producing path also creates an Agent Registration with a
CLI-selected source ID.

## Installed Agent 365 CLI

The installed CLI inspected for this research was:

```text
Microsoft.Agents.A365.DevTools.Cli 1.1.214+90c444832f
```

The following local help commands were inspected without running provisioning:

```powershell
a365 --version
a365 setup --help
a365 setup blueprint --help
a365 setup permissions --help
a365 setup permissions mcp --help
a365 setup permissions bot --help
a365 setup permissions custom --help
a365 setup permissions copilotstudio --help
a365 setup all --help
a365 query-entra --help
a365 cleanup --help
a365 cleanup blueprint --help
```

The current public setup reference is
[Agent 365 CLI Setup Command Reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/setup).

## Agent 365 CLI options

### `a365 setup blueprint`

The command can run without an `a365.config.json` file:

```powershell
a365 setup blueprint --agent-name "<name>" --tenant-id "<tenant-id>" --no-endpoint
```

Its current options include:

- `--agent-name` and `--tenant-id`;
- `--dry-run`;
- `--no-endpoint`;
- `--endpoint-only`;
- `--update-endpoint`;
- `--messaging-endpoint`;
- `--m365`;
- `--skip-requirements`; and
- `--show-secret`.

`--no-endpoint` means that messaging endpoint registration is skipped. It
does not mean that only one Graph object is created.

The inspected first-party implementation creates or reuses the Blueprint
application and then creates or repairs its tenant-local Blueprint principal.
It also handles authentication properties, credentials, Microsoft Graph
permission configuration, inheritance, and consent-related outcomes.

The principal creation is a separate Graph request:

```http
POST /v1.0/servicePrincipals/microsoft.graph.agentIdentityBlueprintPrincipal
```

with the Blueprint application `appId` in the request body. Therefore:

- Graph Blueprint creation does not automatically create the principal;
- the Agent 365 CLI performs that second operation internally; and
- Blueprint success alone does not prove principal or permission success.

Implementation references:

- [`BlueprintSubcommand.cs`](https://github.com/microsoft/Agent365-devTools/blob/08e48a963dd879c6938d032e97e87ccbb03613de/src/Microsoft.Agents.A365.DevTools.Cli/Commands/SetupSubcommands/BlueprintSubcommand.cs#L1351-L1357)
- [`BlueprintSubcommand.cs` principal repair path](https://github.com/microsoft/Agent365-devTools/blob/08e48a963dd879c6938d032e97e87ccbb03613de/src/Microsoft.Agents.A365.DevTools.Cli/Commands/SetupSubcommands/BlueprintSubcommand.cs#L1463-L1479)
- [Create an Agent Identity Blueprint principal](https://learn.microsoft.com/en-us/graph/api/agentidentityblueprintprincipal-post?view=graph-rest-1.0)

`a365 setup blueprint` does not create the child Agent Identity. It is a
valuable partial implementation, not a complete identity-stack command.

### `a365 setup permissions`

The CLI exposes Blueprint-oriented permission commands:

| Command | Purpose |
| --- | --- |
| `setup permissions mcp` | Configure MCP OAuth2 grants and inheritable permissions. |
| `setup permissions bot` | Configure Messaging Bot API, observability, and related permissions. |
| `setup permissions custom` | Configure a custom resource application and delegated scopes. |
| `setup permissions copilotstudio` | Configure `CopilotStudio.Copilots.Invoke`. |

These commands can run with `--agent-name`, `--tenant-id`, and `--dry-run`.
They configure permission state for an existing Blueprint, but they do not
provide a standalone Agent Identity create command.

The CLI documentation describes permission reconciliation, not merely adding
new entries. This matters for shared Blueprints: running a configuration
intended for one source could remove or change state required by another
source. A permission profile must therefore belong to the approved Blueprint
assignment, not to an individual invocation.

### `a365 setup all`

The installed help describes the default non-AI-Teammate flow as:

- Blueprint;
- permissions;
- Agent Identity;
- Agent Registration; and
- applicable infrastructure or endpoint work.

It supports config-free execution:

```powershell
a365 setup all --agent-name "<name>"
```

and supports `--authmode obo|s2s|both`.

However, no `--skip-registration`, identity-only full-stack option, or
companion `sourceAgentId` option was found. `--agent-registration-only` does
the opposite: it skips the earlier setup and performs Registration handling.

The first-party Registration implementation selects the Agent Identity ID as
`sourceAgentId`, with a Blueprint fallback. That is not Lab 20's final
companion source key.

References:

- [Agent 365 CLI setup reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/setup#setup-all)
- [`NonDwBlueprintSetupOrchestrator.cs`](https://github.com/microsoft/Agent365-devTools/blob/08e48a963dd879c6938d032e97e87ccbb03613de/src/Microsoft.Agents.A365.DevTools.Cli/Commands/SetupSubcommands/NonDwBlueprintSetupOrchestrator.cs#L445-L615)
- [`GraphApiService.cs` Registration source selection](https://github.com/microsoft/Agent365-devTools/blob/08e48a963dd879c6938d032e97e87ccbb03613de/src/Microsoft.Agents.A365.DevTools.Cli/Services/GraphApiService.cs#L1631-L1654)

`a365 setup all --aiteammate` provisions Blueprint and permission state without
the normal child identity path. It therefore does not supply the requested
Blueprint, principal, Agent Identity, and permissions stack.

## Microsoft Graph v1.0 building blocks

Current operation-specific documentation exposes the core identity operations
through Microsoft Graph v1.0:

| Resource or action | Operation |
| --- | --- |
| Blueprint create | `POST /v1.0/applications/microsoft.graph.agentIdentityBlueprint` |
| Blueprint upsert | `PATCH /v1.0/applications(uniqueName='{uniqueName}')/microsoft.graph.agentIdentityBlueprint` with `Prefer: create-if-missing` |
| Blueprint principal create | `POST /v1.0/servicePrincipals/microsoft.graph.agentIdentityBlueprintPrincipal` |
| Agent Identity create | `POST /v1.0/servicePrincipals/microsoft.graph.agentIdentity` |
| Delegated grant | `POST /v1.0/oauth2PermissionGrants` |
| Application role assignment | `POST /v1.0/servicePrincipals/{id}/appRoleAssignments` |

References:

- [Create Agent Identity Blueprint](https://learn.microsoft.com/en-us/graph/api/agentidentityblueprint-post?view=graph-rest-1.0)
- [Upsert Agent Identity Blueprint](https://learn.microsoft.com/en-us/graph/api/agentidentityblueprint-upsert?view=graph-rest-1.0)
- [Create Blueprint principal](https://learn.microsoft.com/en-us/graph/api/agentidentityblueprintprincipal-post?view=graph-rest-1.0)
- [Create Agent Identity](https://learn.microsoft.com/en-us/graph/api/agentidentity-post?view=graph-rest-1.0)
- [Create delegated permission grant](https://learn.microsoft.com/en-us/graph/api/oauth2permissiongrant-post?view=graph-rest-1.0)
- [Create app-role assignment](https://learn.microsoft.com/en-us/graph/api/serviceprincipal-post-approleassignments?view=graph-rest-1.0)

Identifier handling remains important:

- a Blueprint has both an application object `id` and application/client
  `appId`;
- principal creation uses the Blueprint `appId`;
- Agent Identity `agentIdentityBlueprintId` uses the Blueprint `appId`;
- permission grants and app-role assignments commonly use service-principal
  object IDs.

The durable mapping must preserve these identifiers separately.

### Blueprint `uniqueName` upsert

The documented Blueprint upsert is an improvement over display-name lookup.
It provides a client-controlled immutable alternate key and returns:

- `201 Created` when it creates the Blueprint; or
- `204 No Content` when it updates an existing Blueprint.

It is still a single-resource operation. It does not create the principal,
credentials, permissions, child Agent Identity, or Registration.

It also requires `AgentIdentityBlueprint.ReadWrite.All`, which differs from a
create-only permission model. Adoption requires a deliberate authorization
decision and readback of the existing binding before update.

## Permission layers

The Agent ID permission model contains distinct layers:

| Layer | Meaning |
| --- | --- |
| Blueprint `requiredResourceAccess` | Declares requested permissions for review; it is not consent. |
| Blueprint `inheritablePermissions` | Selects permissions eligible to flow to children; it is not consent. |
| Grants on the Blueprint principal | Tenant authorization that children may inherit. |
| Direct grants on an Agent Identity | Authorization applying only to that identity. |

References:

- [Inheritable permissions concepts](https://learn.microsoft.com/en-us/entra/agent-id/concept-inheritable-permissions)
- [Configure inheritable permissions](https://learn.microsoft.com/en-us/entra/agent-id/configure-inheritable-permissions-blueprints)

An identity provisioning plan should separately model:

1. authorization to create and manage identity objects;
2. the approved runtime permission profile;
3. consent or administrator action still required;
4. permission application and readback outcomes; and
5. authorization to create the companion Registration.

Creating the identity stack must not silently grant broad runtime access.

## No atomic stack API

Microsoft Graph JSON batching can combine up to 20 requests and can order
requests with `dependsOn`, but it is not an all-or-nothing transaction.
Individual requests have individual results, and dependent requests can fail
with `424`.

[Microsoft Graph JSON batching](https://learn.microsoft.com/en-us/graph/json-batching)
does not document response-value substitution that would safely pass a newly
generated Blueprint `appId` into later principal and Agent Identity request
bodies. Directory replication also remains an observable dependency.

No stack-level Graph manifest, composite endpoint, transaction, rollback
contract, or complete desired-state operation was found for Blueprint,
principal, Agent Identity, and permissions.

Graph batching can reduce network round trips for independent reads. It does
not remove staged provisioning, write gates, readback, or reconciliation.

## Other first-party interfaces

### Microsoft Entra PowerShell

Microsoft documents dedicated Agent ID cmdlets and an interactive workflow:

```powershell
Invoke-EntraAgentIdInteractive
```

The workflow covers:

1. Blueprint creation;
2. client-secret configuration;
3. interactive-agent scopes;
4. Agent User configuration;
5. inheritable permissions;
6. static or dynamic permission mode;
7. admin consent; and
8. one or more Agent Identities and Agent Users.

It does not document an Agent Registration step.

[Invoke-EntraAgentIdInteractive](https://learn.microsoft.com/en-us/powershell/module/microsoft.entra.applications/invoke-entraagentidinteractive?view=entra-powershell)
is therefore the closest first-party "walk me through the identity stack"
command. It is interactive and stateful, not declarative, headless, atomic, or
fleet-reconciling.

The module also exposes individual cmdlets:

- [New-EntraAgentIdentityBlueprint](https://learn.microsoft.com/en-us/powershell/module/microsoft.entra.applications/new-entraagentidentityblueprint?view=entra-powershell)
- [New-EntraAgentIdentityBlueprintPrincipal](https://learn.microsoft.com/en-us/powershell/module/microsoft.entra.applications/new-entraagentidentityblueprintprincipal?view=entra-powershell)
- [New-EntraAgentIDForAgentIdentityBlueprint](https://learn.microsoft.com/en-us/powershell/module/microsoft.entra.applications/new-entraagentidforagentidentityblueprint?view=entra-powershell)

The inspected first-party PowerShell source has an unresolved object-ID versus
app-ID concern in its implicit session state. Until that behavior is
tenant-tested, callers should pass and verify explicit Graph identifiers
rather than relying on implicit state.

### Microsoft Graph PowerShell and Azure CLI

Microsoft Graph PowerShell can execute the same explicit Graph operations,
including generic `Invoke-MgGraphRequest`, delegated grants, and app-role
assignments. Azure CLI `az rest` can also transport Graph requests.

These are alternative transports, not higher-level identity reconcilers.

### Bicep and Terraform

The published Microsoft Graph Bicep v1.0 and beta resource indexes did not
establish typed Agent Identity Blueprint, principal, or Agent Identity
resources:

- [Microsoft Graph Bicep v1.0 reference](https://learn.microsoft.com/en-us/graph/templates/bicep/reference/overview?view=graph-bicep-1.0)
- [Microsoft Graph Bicep beta reference](https://learn.microsoft.com/en-us/graph/templates/bicep/reference/overview?view=graph-bicep-beta)

The first-party Microsoft Graph Terraform provider has a generic
`msgraph_resource` capable of addressing Graph resources:

- [Terraform for Microsoft Graph](https://learn.microsoft.com/en-us/graph/templates/terraform/overview-terraform-for-graph)
- [`msgraph_resource` reference](https://github.com/microsoft/terraform-provider-msgraph/blob/d39d5b0b8196d15db670518c10c916d9a930e3a2/docs/resources/resource.md#L57-L74)

This is a plausible future declarative adapter, but exact Agent ID cast-route
lifecycle, relationship handling, import, and ambiguous-create recovery were
not validated. The provider is not currently a lower-risk replacement for the
explicit Graph workflow.

## Comparison

| Requirement | `a365 setup all` | `a365 setup blueprint` plus custom work | Identity-only Graph v1.0 reconciler |
| --- | --- | --- | --- |
| Creates Blueprint and principal | Yes | Yes | Yes |
| Creates Agent Identity | Yes | Additional API or PowerShell required | Yes |
| Applies permissions | Yes | CLI permission commands can help | Yes, from an explicit profile |
| Stops before Registration | No in the normal identity path | Yes | Yes |
| Accepts final companion source ID | No option found | Registration remains separate | Registration remains separate |
| Avoids extra Registration and Package | No | Yes | Yes |
| Supports dedicated assignment policy | Naming can approximate it | Requires external mapping | Explicitly encoded |
| Atomic transaction | No | No | No |
| Ambiguous-outcome reconciliation | CLI-specific behavior | Must be added | Required by the interface |
| Suitable for headless fleet reconciliation | Poor fit | Partial | Best fit |

## Recommended architecture

Expose one identity-only provisioning interface to the Add lifecycle:

```text
ensureIdentityStack(plan) -> IdentityStackResult
```

The request should contain:

- scoped provider source key;
- assignment mode and Blueprint group;
- deterministic Blueprint key;
- ownership and sponsor data;
- approved permission profile;
- credential or federation profile;
- policy version and approval reference; and
- whether writes are enabled.

The result should contain:

- Blueprint object ID and app ID;
- Blueprint principal object ID;
- Agent Identity object ID;
- permission and consent status;
- per-step outcomes;
- unresolved-operation markers; and
- no Registration or Package identifiers.

Internally, the implementation can use:

1. direct Microsoft Graph v1.0 requests as the authoritative path;
2. selected logic from the Agent 365 CLI as implementation reference;
3. `a365 setup blueprint --no-endpoint` as an optional human-operated adapter,
   provided its additional credential and permission behavior is approved and
   every object is read back; or
4. individual Entra PowerShell cmdlets as another human-operated adapter.

The external interface must not expose those transport choices to the Add
workflow. The Add caller should receive verified identity references and then
perform the separately approved companion Registration create.

## Proposed next experiment

Compare two disposable dedicated-source identity preparations without creating
a Registration:

### Path A: CLI-assisted

1. Run `a365 setup blueprint --agent-name <synthetic-name> --no-endpoint`.
2. Read back the Blueprint and principal.
3. Record credentials, required-resource declarations, inheritance, grants,
   consent status, and local generated state.
4. Create one Agent Identity explicitly through Graph v1.0.
5. Apply or verify the approved permission profile.

### Path B: Graph-only

1. Create or upsert the Blueprint using a deterministic `uniqueName`.
2. Create and verify its principal.
3. Apply the same credential and permission profile explicitly.
4. Create and verify one Agent Identity.

Compare:

- resulting Graph objects and IDs;
- permission declarations, inheritance, and actual grants;
- required operator and administrator roles;
- local state produced by the CLI;
- retry and reconciliation behavior;
- cleanup behavior; and
- whether either path changes an Agent Registration or Package.

Do not create the companion Registration until one identity path is selected
and its result has been reconciled.

## Remaining uncertainties

- No live provisioning or token acquisition was performed during this
  research.
- Installed CLI help and inspected implementation differ in how they describe
  default OBO grants. Readback is required before relying on either
  description.
- `a365 setup blueprint` performs more work than its short help description
  suggests, including credential and permission handling.
- The Entra PowerShell interactive workflow's implicit Blueprint identifier
  handling needs a bounded tenant experiment.
- Blueprint upsert is documented, but required ownership and sponsor metadata
  should be preserved and verified for create outcomes.
- Better identity provisioning does not make the beta companion Registration
  interface production-supported.
- Identity provisioning and permission configuration do not prove that a
  third-party runtime uses the resulting Agent Identity.

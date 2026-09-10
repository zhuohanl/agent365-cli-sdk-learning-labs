# Registry Sync: interim Blueprint and Agent Identity assignment

Research date: 2026-09-06. Context: the Lab 20 experiment for
microsoft/silver-couscous#113. This is a research recommendation, not an
implemented onboarding service or permission to create additional objects.

Creating an Entra identity, linking it to a catalog record, and making the
third-party runtime use it are three separate tasks.

| Reading goal | Start here |
| --- | --- |
| Understand the decision and its limits | [Recommendation](#recommendation) |
| Understand Registry Sync setup and its automation gap | [Connection creation research](#creating-and-operating-registry-sync-connections) |
| Distinguish a complete connection list from package-derived connection context | [Connection list/details research](#programmatic-connection-list-and-details-renewed-review) |
| Understand why the original record cannot yet be updated | [Path 2 research](#path-2-public-lookup-and-update-research) |
| Follow the best available interim approach | [Detailed walkthrough](#best-available-interim-solution-step-by-step) |
| Run the bounded steps end-to-end, offline-tested and read-only by default | [Notebook walkthrough](notebook-pilot/registry_sync_identity_walkthrough.ipynb) (see [`INSTRUCTION.md`](INSTRUCTION.md) for setup) |
| Plan the demo and operating safeguards | [1-2 day delivery](#recommended-1-2-day-delivery) |
| Prepare for future product support | [Migration](#prepare-for-native-support-without-assuming-its-migration-contract) |

## Table of contents

- **[Recommendation](#recommendation)**
- **[What the experiment actually established](#what-the-experiment-actually-established)**
- **[Path 2: public lookup and update research](#path-2-public-lookup-and-update-research)**
  - [Available operations](#available-operations)
  - [Why Package Details does not currently unblock Path 2](#why-package-details-does-not-currently-unblock-path-2)
  - [Creating and operating Registry Sync connections](#creating-and-operating-registry-sync-connections)
    - [Programmatic connection list and details: renewed review](#programmatic-connection-list-and-details-renewed-review)
- **[Alternatives to the two paths](#alternatives-to-the-two-paths)**
- **[Correct the proposed prerequisites](#correct-the-proposed-prerequisites)**
  - [Current Entra provisioning APIs](#current-entra-provisioning-apis)
- **[Best available interim solution: step by step](#best-available-interim-solution-step-by-step)**
  - [How to read and use the steps](#how-to-read-and-use-the-steps)
  - [Step 1 - Create or reuse Registry Sync and choose the connection discovery path](#step-1---create-or-reuse-registry-sync-and-choose-the-connection-discovery-path)
    - [Connection naming convention](#connection-naming-convention)
  - [Step 2 - Obtain the approved delegated Graph token and operator ID](#step-2---obtain-the-approved-delegated-graph-token-and-operator-id)
  - [Step 3 - List packages and follow every returned page](#step-3---list-packages-and-follow-every-returned-page)
  - [Step 4 - Read the original package and extract source metadata](#step-4---read-the-original-package-and-extract-source-metadata)
  - [Step 5 - Build the source key, Blueprint group, and no-write plan](#step-5---build-the-source-key-blueprint-group-and-no-write-plan)
    - [Inputs and who supplies them](#inputs-and-who-supplies-them)
    - [Manual grouping procedure](#manual-grouping-procedure)
  - [Step 6 - Reuse or create the Blueprint for the approved group](#step-6---reuse-or-create-the-blueprint-for-the-approved-group)
  - [Step 7 - Ensure the Blueprint principal exists](#step-7---ensure-the-blueprint-principal-exists)
  - [Step 8 - Reuse or create one Agent Identity for the source agent](#step-8---reuse-or-create-one-agent-identity-for-the-source-agent)
  - [Step 9 - Verify the actual Entra parent-child relationship](#step-9---verify-the-actual-entra-parent-child-relationship)
  - [Step 10 - Resolve only a known companion registration](#step-10---resolve-only-a-known-companion-registration)
  - [Step 11 - Write the identity association: choose A or B, never both](#step-11---write-the-identity-association-choose-a-or-b-never-both)
  - [Step 12 - Read back the companion's stored identity fields](#step-12---read-back-the-companions-stored-identity-fields)
  - [Step 13 - Compare both packages and establish the association outcome](#step-13---compare-both-packages-and-establish-the-association-outcome)
  - [Step 14 - Persist the result and prove repeatability](#step-14---persist-the-result-and-prove-repeatability)
  - [Step 15 - Optionally prove one actual runtime access path](#step-15---optionally-prove-one-actual-runtime-access-path)
  - [Step 16 - Retain deliberately or clean up with explicit approval](#step-16---retain-deliberately-or-clean-up-with-explicit-approval)
- **[Recommended 1-2 day delivery](#recommended-1-2-day-delivery)**
  - [Minimum implementation safeguards](#minimum-implementation-safeguards)
  - [Customer-facing claim](#customer-facing-claim)
- **[Prepare for native support without assuming its migration contract](#prepare-for-native-support-without-assuming-its-migration-contract)**
- **[Questions requiring PG confirmation](#questions-requiring-pg-confirmation)**
- **[Sources: inventory and registration](#sources-inventory-and-registration)**
- **[Sources: identity, runtime, and lifecycle](#sources-identity-runtime-and-lifecycle)**

## Recommendation

**Do not treat a companion registration as an update to a Registry Sync
record. One separately named GCP companion was created successfully in the
bounded experiment, but use read-only inventory evidence for the original
record and do not roll automatic companion creation out as production
onboarding.**

| Question | Answer |
| --- | --- |
| Can Registry Sync be created programmatically? | No publicly documented connection-create, credential-validation, or sync-trigger API was found. Use the documented admin-center setup for now; the installed CLI exposes no Registry Sync setup command. [A6, A10] |
| Can a package identify its Registry Sync connection? | Yes in the inspected GCP responses: parse the nested `definition` string and read `SourceIds.ConnectionId`. Match that exact value to known connection context; platform alone is insufficient. A public connection-management API and a cross-provider field guarantee remain unestablished. |
| Can all connections and each connection's details be retrieved programmatically? | No documented complete connection-list or connection-details interface was found in the reviewed surfaces. However, GCP package metadata provides connection IDs, platform, project, and region: a useful partial inventory, not an authoritative connection list or full configuration. See the renewed review below. |
| Can Path 2 find the correct existing registration from Package Details? | No publicly documented lookup or mapping was found. Discovering an ID would still leave write authority and sync persistence to establish. |
| Should a same-source Path 1 work? | One historical first create returned `201`, but current minimal creates for four sampled GCP Registry Sync sources all returned the same backend permission denial despite the documented delegated scope. A deleted known registration could not be recreated with its original successful body. Do not depend on same-source creation. |
| Can a separately named fresh companion be created? | Yes in one bounded GCP observation: a deterministic source ID distinct from the provider source returned `201`, GET by the returned Registration ID succeeded, and the original Package remained unchanged. This is not production or cross-provider proof. |
| Is there a third in-place assignment path? | None found in the reviewed public documentation. Entra-only association and SDK/runtime integration are alternatives with different outcomes, not hidden ways to update the synchronized record. |
| What should be implemented now? | Approved manual Registry Sync setup if needed, then API-based inventory discovery and explicit source-to-identity mapping. PATCH only a separately known, verified, user-owned registration. The fresh-companion pattern remains an explicitly gated experiment until its lifecycle, provider coverage, and production support are decided. |
| Can the customer onboard the whole fleet with this workaround? | Not as a supported production solution: the Agent Registration API explicitly excludes production use, and original-record association, lifecycle behavior, and runtime integration remain unresolved. [A1] |

If the requirement is specifically **"the original Registry Sync record must
show both IDs, without duplication"**, neither path currently establishes
that outcome. Obtain a supported PG route or revise the demo's scope; a
short deadline does not remove this product boundary.

## What the experiment actually established

| Claim | Evidence and limit |
| --- | --- |
| The selected GCP Registry Sync package is discoverable. | Package List and Details returned `200`; provider-native source metadata was present. |
| Package Details exposes a connection reference. | The parsed definition contains a nonempty `SourceIds.ConnectionId` in the saved original GCP package responses before and after companion creation. The inspected companion definition does not contain that field. This establishes field presence for these samples, not a universal provider contract or a connection-management API. |
| Package metadata also supplies some connection context. | The inspected original GCP definitions contain nonempty `SourceIds["mac.projectId"]`, `SourceIds["mac.region"]`, and `SourceIds["mac.agentRegistrationProviderType"]`. These are source-context observations, not proof of the connection's complete or current configuration. |
| The selected package exposes no Blueprint or Agent Identity link. | No Blueprint field was observed; `agentIdentityId` was null. This does not prove no related Entra object exists anywhere. |
| A same-source registration can be created. | Historical observation only: one user-owned create returned `201`. In the current time window, minimal POSTs for four sampled GCP Registry Sync sources all returned the same backend permission denial, including exact-body recreation after confirmed deletion. |
| That create enriched the original synchronized package. | **No.** A second package appeared; the original remained unchanged. |
| Package ID equals Registration ID. | Verified only for the API-created record, not as a general Registry Sync rule. |
| There are two public registrations for the agent. | Not established. Two inventory representations and one addressable public registration were established. |
| A registration containing both identity links works. | Not established. The attempted linked create failed, and removing both identity fields did not change the failure. The fields remain documented, but no successful association was observed. |
| An Entra policy controls the original GCP runtime. | Not tested; neither creating objects nor filling metadata fields demonstrates this. |

See [findings](findings.md), [experiment matrix](experiment-matrix.md), and the
[provider-source creation experiment](experiments/02-provider-source-registration-create/experiment.http).
The operator
also reported that a registration GET using the synchronized Package ID
failed. Treat that as an operator-reported observation: the recorded
collection `404` is a different request, and neither establishes a universal
ID-mapping rule or proves that a backing registration does not exist.

## Path 2: public lookup and update research

### Available operations

Paths below are relative to `https://graph.microsoft.com`. This table lists
documented API operations, not operations exercised by this research.

| Operation | Package Management API | Agent Registration API |
| --- | --- | --- |
| List | `GET /v1.0/copilot/admin/catalog/packages` | No documented list operation |
| Get | `GET /v1.0/copilot/admin/catalog/packages/{id}` | `GET /beta/copilot/agentRegistrations/{id}` |
| Create | No documented package-create operation | `POST /beta/copilot/agentRegistrations` |
| Update | `PATCH /beta/copilot/admin/catalog/packages/{id}` | `PATCH /beta/copilot/agentRegistrations/{id}` |
| Delete | No documented package-delete operation in this API family | `DELETE /beta/copilot/agentRegistrations/{id}` |
| Other actions | Beta `POST .../{id}/block`, `/unblock`, `/reassign` | No additional operation documented |
| Source-ID lookup / upsert | No registration-resolution operation documented | No source-ID lookup, alternate-key GET, or upsert documented |
| Set identity links | Not in the documented update contract | `agentIdentityBlueprintId` and `agentIdentityId` are documented create/update properties |

Sources: [A1-A5]. Package read and registration operations document both
delegated and application permissions. Package update/reassign document
delegated permissions only. The Package API requires an Agent 365 license;
portal inventory visibility has different licensing guidance. Do not infer
API entitlement from portal access. [A2, A3, A5, A7]

### Why Package Details does not currently unblock Path 2

- Package Details and Agent Registration document no cross-resource
  relationship. No reviewed reference defines Package `id`, `assetId`,
  `appId`, manifest ID, or nested `ManagedBy` as the registration lookup
  key for synchronized agents. [A1, A4]
- The observed nested `SourceIds.ConnectionId` is a connection reference,
  not a Registration ID. It helps correlate inventory to a connection but
  does not establish a registration lookup key.
- The observed Package `agentIdentityId` field also appears in Microsoft's
  generated Graph model, but field/schema presence is not a documented
  write contract. Package PATCH only documents `allowedUsersAndGroups`
  and `acquireUsersAndGroups`; `reassign` takes the new owner's `userId`.
  Neither is an identity-assignment operation. [A3, A8]
- `sourceAgentId` is registration metadata, not a documented global
  uniqueness constraint or upsert key. Repeating POST must not be treated
  as "update if already synchronized." [A1]
- Even a future successful registration GET would prove only readability.
  The experiment's app-managed create rejection shows ownership matters
  somewhere in this API. It does not establish the exact update rule for
  connector-managed records. PG must confirm write authority and whether a
  later sync preserves externally assigned identities.

**Result:** no publicly documented in-place solution was found. Do not strip
ID prefixes, guess another identifier, replay private portal calls, or PATCH
a field simply because it exists in a generated SDK.

The search covered Microsoft Learn's Package and Registration references,
Connected Platforms guidance, Entra registry convergence and registration
guidance, public Graph metadata, and generated Microsoft Graph models.
"Not found" describes that public evidence boundary, not proof that Microsoft
has no internal relationship or unpublished capability.

### Creating and operating Registry Sync connections

**Research result, 2026-09-06:** no publicly documented REST API or CLI
operation was found to create an Agent 365 Registry Sync connection,
validate its provider credentials, or trigger synchronization. The current
documented path is the Microsoft 365 admin center's **Connected platforms**
page. This is a public-documentation boundary, not proof that no internal
API exists. [A6]

| Operation | Documented way to perform it | Public Registry Sync API found? |
| --- | --- | --- |
| Create a platform connection | **+ Connect a platform**, enter provider/environment/credentials, validate, then save | No |
| Validate provider credentials | Validation step in the connection wizard | No |
| Start synchronization | **Sync agents** on an approved connection | No |
| List connections or inspect sync status/errors | Connected Platforms page and connection details | No |
| Configure scheduled synchronization | The current guide describes scheduled sync as a future release; do not assume it is available | No |
| List/read agents after synchronization | Package List and Package Details | Yes, inventory reads; not connection management |
| Delete a connection | Connected Platforms management UI | No |

The guide also mentions an automatic-import choice during setup. That does
not establish a scheduled-sync API, a schedule contract, or a per-agent
import filter. Confirm the actual options exposed in the tenant. [A6]

The review covered the current Connected Platforms instructions, Agent
Registry Graph guidance, targeted public searches for create/validate/sync
operations, and installed `a365 --help` and `a365 setup --help`.
CLI `1.1.214+90c444832f` exposes Blueprint/environment setup, not a Registry
Sync connection-creation command. This local help observation does not rule
out a future CLI feature. The Graph guidance's automation language links
to Package List/Details; it does not document a connector-provisioning
endpoint. [A10]

**Do not substitute a different API:** Graph's documented
`POST /v1.0/external/connections` creates a Microsoft Search external
connection, not an Agent 365 Registry Sync connection. Foundry connections,
OAuth tool connections, and Agent Registration POST are also different
resources. Browser automation or replaying private portal calls would not
establish a supported Registry Sync API contract and is not the recommended
customer-onboarding approach. [A1, A11]

**Practical boundary:** perform approved connection setup and the initial
sync manually when needed. Start the supported programmatic portion at
Package List and read the selected Package Details. Read the platform
directly from the top-level `platform` field; no connection lookup is needed
to identify it. A protected connection map can enrich provenance when
needed, but is not a prerequisite for platform identification or Blueprint
group assignment.
The inspected GCP Package Details
responses expose `SourceIds.ConnectionId` after parsing the nested
`definition` string. Use that exact value, scoped by tenant and platform,
to group packages by connection and match a known connection record.
Do not infer connection membership from the platform name alone. Grouping
packages by connection is separate from assigning a Blueprint group.

**Correction to the earlier interpretation:** the absence of a documented
connection-management endpoint does not mean the package has no connection
reference. Local evidence files `disposable-before-create.json`,
`step_5.1_get_details_of_selected_package_test_agent.json`, and
`disposable-package-detail-after-create.json` contain the field; real values
remain in ignored evidence. The inspected
`disposable-created-package-detail.json` companion definition omits it.
These are observations, not a guarantee about every provider, package type,
or future schema.

The connection reference alone does not retrieve full configuration,
credentials, or sync status. However, the inspected GCP definitions also
include project, region, and provider metadata, as detailed below. Match
observed context to operator-approved scope; do not invent missing context.
If fully unattended connection creation or sync scheduling is mandatory,
that part remains blocked pending a documented PG-supported interface.

#### Programmatic connection list and details: renewed review

**Finding, 2026-09-06:** no documented interface for a complete Registry
Sync connection list, or for reading a connection's full details by its
`ConnectionId`, was found in the reviewed public surfaces. This is a
bounded research result, not a claim that no Microsoft-internal or
PG-provided interface exists.

| Surface reviewed | What was found | Consequence for connection list/details |
| --- | --- | --- |
| Connected Platforms guidance | Portal connection management and details including provider, regions, last run, sync status, agent count, and results. [A6] | The page documents UI actions, not list/get API requests. |
| Agent 365 Graph and Package references | Agent/package List and Details. [A2, A4, A5, A10] | Read package metadata; no dedicated connection-list/get operation found. |
| Live public Graph v1.0 and beta metadata | `copilotAdmin.catalog.packages`; no Registry Sync connection navigation/type found in the inspected schema. [A12] | Supporting evidence only. Metadata absence does not rule out another administration API, and metadata presence alone does not establish an operation's support. |
| Official CLI reference and inspected local CLI | No Registry Sync connection-list/details command found in the documented command tree or inspected help. [A10, A13] | No identified `a365` route for this task. |
| PowerShell discovery and generic Graph requests | No Registry Sync-specific list/details cmdlet found. `Invoke-MgGraphRequest` can call a known Graph REST URI even without a typed cmdlet. [A14] | PowerShell can call Package List/Details; a generic HTTP wrapper does not supply a missing connection endpoint. Unsuccessful cmdlet/module-name searches do not prove absence. |
| SDK, announcement, and public-code discovery | The SDK overview describes agent integration; the official launch announcement describes Registry Sync through the admin center. Targeted public SDK/sample and administration-script searches revealed no connection-list/details client. [A16] | No additional callable contract found. Keyword-search coverage is limited and does not establish that no implementation exists. |
| Entra Agent Registry resources | Agent instances, collections, and card manifests; not a documented Registry Sync connection/configuration resource. [A15] | Do not substitute agent collections for platform connections. |
| Microsoft Search external connections | A separate connector resource for indexed external content. [A11] | Do not use `/external/connections` or its ID-based lookup as a Registry Sync contract. |

No tenant endpoint was probed during this research, and no private portal
request was captured or replayed. A hidden endpoint, a guessed route, or
an unrelated connector API would not establish a supported customer path.

**Useful alternative: derive an observed connection inventory from packages.**
The available fields are more than a bare connection ID:

| Information | Observed source in the GCP sample | Interpretation |
| --- | --- | --- |
| Platform | Package `platform`; parsed `SourceIds["mac.agentRegistrationProviderType"]` | Provider classification; compare the two if both are present. |
| Connection ID | Parsed `SourceIds.ConnectionId` | Reference for grouping and matching a known connection. |
| Project | Parsed `SourceIds["mac.projectId"]` | Observed native project, not proof of all projects covered by the connection. |
| Region | Parsed `SourceIds["mac.region"]` | Observed native region, not proof of the complete configured region set. |
| Source agent | Parsed `SourceAgentId` | Exact agent reference, distinct from connection and package IDs. |
| Connection name, current sync status, last sync results, complete configuration | No established source for these in the inspected package metadata | Keep unresolved or obtain through approved portal inspection; do not substitute package display name or modification time. |

After choosing fresh setup or reuse in Step 1, perform this read-only
sequence through Steps 2-5:

1. Read Package List using the approved Graph client and
   `CopilotPackages.Read.All`; follow every returned `@odata.nextLink`.
   Do not invent undocumented paging parameters or assume a collection
   sample establishes tenant-wide completeness.
2. Read Details for relevant visible packages, excluding known companions.
   Parse each applicable `definition` string; preserve parsing failures,
   missing fields, and conflicting metadata as unresolved observations.
3. Group observed references by `(tenant, platform, ConnectionId)`.
   Within each group, preserve the observed project/region pairs and
   package/source-agent references. Do not arbitrarily choose one scope
   or form a cross-product of separately collected projects and regions.
4. Match this derived inventory to approved connection context. Leave
   connection names and current configuration/status unresolved where
   no authoritative source has supplied them. The metadata itself does
   not authorize identity provisioning.

The HTTP operations remain the documented Package List and Details
requests in Steps 3-4. This sequence is a proposed aggregation over those
reads, not a new Microsoft connection API or an implemented fleet scan.
For example, its local output could be:

```json
{
  "inventoryOrigin": "package-metadata",
  "completeConnectionInventory": false,
  "connections": [
    {
      "tenant": "<tenant-id>",
      "platform": "GoogleVertexAI",
      "connectionId": "<exact-source-connection-id>",
      "observedScopes": [
        {
          "projectId": "<observed-project-id>",
          "region": "<observed-region>"
        }
      ],
      "packageIds": ["<original-package-id>"],
      "connectionDisplayName": null,
      "syncStatus": null,
      "fullConfigurationResolved": false
    }
  ]
}
```

This output is explicitly **not** the full tenant connection list. It
cannot reveal connections with no visible imported packages, including
empty connections, connections that have never completed a sync, or ones
whose packages are no longer visible. Historical packages may also retain
references after connection changes; a reference does not prove that the
connection is currently active. Read failures or missing provider metadata
further reduce coverage. Other providers require independent evidence.

For the 1-2 day pilot, this is enough to derive candidate connection groups
and observed GCP scopes for already imported, visible agents, then obtain
the required scope/Blueprint approvals. It is not enough to claim complete
connection discovery, current sync health, or full configuration retrieval.
Ask PG specifically for **List connections** and **Get connection by
ConnectionId**, including auth, pagination, returned fields, and support
status; those are distinct from package metadata extraction.

## Alternatives to the two paths

| Approach | What it achieves | Does it enrich the original synced record? | Recommendation |
| --- | --- | --- | --- |
| Entra-only provisioning plus an external mapping | Real Blueprint/Agent Identity objects, correlated to the source agent in customer-managed state | No; it is your association, not an Agent 365 native link | Lowest-impact fallback when duplicate catalog records are unacceptable. Do not promise that the original card displays the IDs. |
| Managed onboarding with Agent 365 CLI/SDK | Identity-backed registration and optional runtime capabilities for an agent you can integrate | No documented Registry Sync adoption/deduplication step | Consider for developer-owned agents, not as a blanket retrofit for vendor-managed agents. [I2, I7] |
| Runtime authentication integration | The agent uses its assigned Entra identity for a specific downstream operation | Does not solve catalog association | Necessary when the requirement is actual access control, rather than inventory metadata. An official Bedrock sample illustrates this distinction. [I6, I11] |
| Wrapper or gateway with its own identity | An identity for the integration component and the calls routed through it | No; it represents the wrapper unless a supported binding proves otherwise | Do not present it as automatically governing the underlying agent or bypass paths. |
| PG-supported native association or approved preview | Potentially the intended in-place result | Only if PG explicitly confirms the contract | Preferred for fleet onboarding; availability and migration behavior are not established. |

Entra's registry-convergence guidance explicitly includes agents without
Entra identities in Agent 365's inventory. It does not document how to
upgrade a synchronized record. The separate "register existing Blueprints"
guidance adds an Agent Registry call after Entra provisioning; its bulk/batch
reference does not establish a merge or adoption contract. [A7, I2]

Provider results remain independent:

| Provider | What can be concluded here |
| --- | --- |
| Google Vertex AI | The disposable same-source companion behavior was observed; identity-bearing association and runtime use remain untested. |
| AWS | Registry Sync is documented; the separate Bedrock authentication sample demonstrates a code-integrated downstream-token pattern, not enrichment of a synced record. [A6, I11] |
| Salesforce Agentforce | Registry Sync is documented. No identity-association or runtime result from the GCP experiment transfers to it. [A6] |
| Anthropic Claude Managed Agents | Registry Sync is documented as preview. Its connection credentials and managed runtime require their own assessment. No live result is claimed here. [A6] |

## Correct the proposed prerequisites

**One identity per agent is a reasonable model; one Blueprint per platform
is not a safe default.** Microsoft explicitly defines a Blueprint as a
credential boundary. Group only agents that can safely share credentials and
inherited baseline permissions. A connection may be a useful grouping input,
but separate environments, owners, trust boundaries, or permission needs may
require multiple Blueprints within that connection. [I1]

Also, "one per connection" and "one per platform" are different: a platform
can have multiple connections. An absent Blueprint field on a package does
not prove that a reusable, approved Blueprint is absent in Entra.

**Human-maintained input:** `blueprintGroup` is a customer-defined policy
label, not a field returned by Package Details, a Microsoft group object,
or an Entra Blueprint ID. An accountable maintainer must define the groups,
approve their members and shared credential/permission boundaries, and
maintain the assignments. Step 1 identifies the people and decisions
needed; Steps 3-4 supply source metadata; Step 5 records the actual grouping
policy before Step 6 resolves or creates a Blueprint.

The order is approval -> create/reuse Registry Sync connection -> approved
initial sync or existing import evidence -> inventory discovery ->
platform/source reads and connection provenance -> human-approved Blueprint grouping ->
Blueprint application and principal -> per-agent identity -> companion
association. The detailed walkthrough below makes the reuse, creation,
and stop decisions explicit. Do not provision identities for the entire
inventory before proving association and lifecycle behavior.

### Current Entra provisioning APIs

The current Graph reference documents these **v1.0** operations, although
some Entra tutorials still show beta examples. Do not copy an old tutorial's
version indiscriminately. These calls create directory objects, not a
Registry Sync package-to-registration relationship. [I2-I5]

| Object | Graph operation | Least-privileged delegated create permission |
| --- | --- | --- |
| Blueprint | `POST /v1.0/applications/microsoft.graph.agentIdentityBlueprint` | `AgentIdentityBlueprint.Create` |
| Blueprint principal | `POST /v1.0/servicePrincipals/microsoft.graph.agentIdentityBlueprintPrincipal` | `AgentIdentityBlueprintPrincipal.Create` |
| Agent Identity | `POST /v1.0/servicePrincipals/microsoft.graph.agentIdentity` | `AgentIdentity.Create.All` |

An authorized operator also needs the documented role or ownership and
consent prerequisites. Blueprint and identity creation require a valid
sponsor. For read-back, the dedicated references document
`AgentIdentityBlueprint.Read.All`, `AgentIdentityBlueprintPrincipal.Read.All`,
and `AgentIdentity.Read.All`. The existing Package/Registration permissions
do not authorize Entra provisioning. Do not silently expand tenant consent.
[I2-I5, I8, I9, I12]

Keep identifier types explicit: the Blueprint has both an application
**object ID** and an **appId**. Entra's `agentIdentityBlueprintId` references
the Blueprint's **appId**; the Blueprint principal has a separate object ID.
Store these separately rather than using an ambiguous `blueprintId`
variable. [I3-I5]

The **Agent Registration** reference is less precise: it calls its fields
identity "identifiers" without specifying appId versus object ID. Using the
Blueprint appId and Agent Identity object ID is a plausible candidate based
on Entra's convention, not a verified cross-API contract. Confirm with PG or
the bounded disposable test; storing strings successfully is not enough to
prove that Agent 365 resolves them to the intended Entra objects. [A1, I5]

**No Blueprint secret is necessary merely to create identities through the
authorized delegated path.** Blueprint-authenticated automated provisioning
is another documented path, with its own credential and permission setup.
Runtime authentication later requires supported credentials and token
acquisition. Do not turn the experiment's public-client login app into the
agent's runtime credential. [I2, I5, I6]

## Best available interim solution: step by step

**Chosen approach:** retain Registry Sync as the inventory source, provision
or reuse actual Entra objects, and associate them with a separately managed
companion registration. For this lab, reuse the existing disposable
registration instead of creating another one. For a new pilot agent with
no prior companion, an explicitly approved create is the alternative.

Step 1 chooses between manual connection setup/first sync and reuse of an
already approved connection with imported agents. Steps 2-4 authenticate,
read packages, take `platform` directly from Package Details, and extract
source identity and connection provenance;
Step 5 combines those observations with human-maintained grouping policy
and approves the source-to-Blueprint plan. Do not require a complete
connection list or a fully populated manual connection map for these
inventory reads or for platform identification. Group assignment depends
on approved source membership and the shared-authority decision, not on
looking up the connection.

Run Steps 6-7 once per approved Blueprint group. Repeat Steps 8-14 for each
allowlisted agent in that group, reusing the parent Blueprint/principal
while assigning a distinct Agent Identity to each source agent. Start with
one agent; expand only after the association and repeatability gates pass.
This is not authorization to process the entire inventory.

This is the best bounded experiment supported by the evidence so far, not
a proven in-place solution or a production-ready onboarding service.
If the customer rejects duplicate inventory records, stop at Entra
provisioning plus the external mapping; neither record mutation nor a
native Agent 365 association has then been demonstrated.

### How to read and use the steps

Each numbered heading is the **Step**. Each step then provides
**Description**, **Sample API Call**, **Sample Output**,
**Gap Identified**, and **Actions Required**. Code blocks keep longer
requests readable instead of placing them in a very wide table.

All examples use synthetic names and placeholders. **No request below was
executed while adding this walkthrough.** Output labels distinguish:

- **Observed shape:** a synthetic illustration of behavior already observed
  in Lab 20, not a copied tenant response.
- **Expected:** a documented success response for an unexecuted step.
- **Success target:** an outcome to establish, not an API guarantee.
- **Local example:** proposed application/operator state, not a Microsoft
  response or an already implemented command.

`...` in an abridged output means omitted entries or fields. Such blocks are
display excerpts, not valid JSON to replay. Request bodies never contain
ellipsis. Substitute values only in ignored local configuration, using
these conventions:

| Placeholder | Meaning |
| --- | --- |
| `{{tenantId}}`, `{{clientId}}` | Approved tenant and public-client application used for the operator's delegated sign-in |
| `{{graphAccessToken}}` | Current Microsoft Graph token with the approved permissions for that stage; never an agent runtime token |
| `{{operatorUserId}}`, `{{sponsorUserId}}` | Signed-in creator/owner and approved accountable sponsor; they may be the same person |
| `{{sourceAgentId}}`, `{{sourceCreatedAt}}`, `{{sourceModifiedAt}}` | Exact provider source values from the selected baseline; preserve ISO 8601 timestamps |
| `{{originalPackageId}}` | Existing Registry Sync package, never substituted for a registration ID |
| `{{blueprintObjectId}}`, `{{blueprintAppId}}`, `{{blueprintPrincipalId}}` | Three distinct Entra references captured from actual create/read responses |
| `{{agentIdentityId}}` | The child Agent Identity's returned `id` |
| `{{companionRegistrationId}}`, `{{companionPackageId}}` | Separately recorded references, correlated from actual responses rather than assumed globally equal |

The new snippets are documentation, not additions to the runnable `.http`
files. The existing HTTP files cover the earlier experiment only. Use them
for their existing requests; add any newly approved request to ignored
local working material, and send it individually. Do not use "send all."

[`registry_sync_identity_walkthrough.ipynb`](notebook-pilot/registry_sync_identity_walkthrough.ipynb)
implements the control-plane portion as a simple **three-part notebook** for
Google Vertex AI's **Test V2**. This report retains its detailed 16-step
reference; the notebook separates platform/group preparation from individual
agent assignment:

| Notebook section | Relationship to this report |
| --- | --- |
| Prerequisites / Prep | Existing import context, login app/scopes, browser sign-in, and all visible Package List pages (Steps 1-3) |
| Part 1: platform and Blueprint groups | Group the List packages results by platform without fetching every package's details; manually confirm Registry Sync platforms, define groups, then read/create each group's Blueprint and principal (group-level planning from Step 5; Steps 6-7) |
| Part 2: selected agent identity | Read that agent's details and exact source ID, manually select a group under its returned platform, then read/create its Agent Identity (Step 4, agent membership from Step 5, Steps 8-9) |
| Part 3: registration | GET/PATCH a known registration, or explicitly create its first companion, then compare stored fields and inventory (Steps 10-14) |
| Cleanup | Retain by default or retire one approved newly created object (Step 16); runtime integration from Step 15 remains unperformed |

All Python logic and API calls remain in the corresponding cells; there is
no separate workflow module. The notebook intentionally scopes group labels
by platform within its one-tenant state:
`blueprint_bindings[platform][group]`. The same label on another platform
does not imply the same Blueprint. Approval of this group-level plan does
not assign every agent on those platforms; Part 2 separately approves one
agent's membership. Connections remain provenance, not the platform/group
lookup.

The notebook defaults to `RUN_WRITES = False`, saves IDs in ignored local
state, and is not itself authorization for any live write; see
[`INSTRUCTION.md`](INSTRUCTION.md) for setup and its own boundary notes.

### Step 1 - Create or reuse Registry Sync and choose the connection discovery path

**Description:** Establish an approved, non-production source of imported
agents. Use Google Vertex AI for the concrete walkthrough. Separate the
manual connection lifecycle from the programmatic discovery of connection
references in packages; do not require a complete connection list before
reading the imported inventory.

| Task | Current approach |
| --- | --- |
| Create a connection, validate credentials, and run its first sync, if needed | Approved manual setup in the Microsoft 365 admin center. [A6] |
| Identify connections represented by imported, visible agents | Package List and Details, then group by `(tenant, platform, SourceIds.ConnectionId)` after parsing `definition`. Authenticate in Step 2 and perform the reads in Steps 3-4. |
| Obtain observed GCP project and region | Read `SourceIds["mac.projectId"]` and `SourceIds["mac.region"]` from the parsed definition; compare them with approved scope in Step 5. |
| Obtain the full connection list or current connection configuration/sync status | No publicly documented supported list/get interface found in the renewed review. Use approved portal inspection where needed; leave unknown information unresolved. |

This step creates no Blueprint, Agent Identity, or companion registration.
Connection metadata does not authorize those later writes.

**Approval gate:** Creating a new connection and running a sync require
explicit approval for that environment and its full import scope. This
document update is not that approval. Do not create provider agents, cloud
infrastructure, long-lived keys, or additional permissions to satisfy this
walkthrough. If approved prerequisites are unavailable, stop.

**Reuse branch for the current lab:** The approved connection and imported
disposable agent already exist. Skip connection creation, credential
validation, and a new sync. Continue to Steps 2-4 to read the inventory and
extract its connection ID, project, and region. Use existing setup records
or approved portal inspection to resolve additional context when needed.
Do not require a manually completed connection map before those reads, and
do not create a duplicate connector or rerun sync merely to follow this lab.

**Fresh-setup branch:** Only if a new connection and its first sync are
explicitly approved, follow the documented portal workflow below. [A6]

1. Sign in to the Microsoft 365 admin center as an authorized administrator.
2. Open **Agents** -> **All agents** -> **Connected platforms** -> **Manage**.
3. Select **+ Connect a platform**.
4. Enter a connection name using the
   [proposed naming convention](#proposed-connection-naming-convention)
   and a description of its approved scope. Keep tracked examples synthetic.
5. Select **Google Vertex AI** and the approved region; provide the existing
   project and provider credentials requested by the wizard.
6. Review the automatic-import choice. Keep optional automatic import off
   for this controlled pilot where the UI permits; do not assume it
   provides scheduling or an agent-level allowlist.
7. Validate the credentials. Stop on failure; do not broaden permissions
   or replace credentials without a separate review.
8. Save the connection. Treat this as a remote mutation and record whether
   the connection was newly created or reused.
9. If an approved first sync has not already completed, select **Sync
   agents**. Do not launch a duplicate run if import has already started.
10. Inspect the connection's sync results and errors. Record the actual
    status, last run, and synced-agent count. After a usable import result,
    continue to Step 2, then the Package reads in Steps 3-4. A saved
    connection alone is not evidence that agents were imported.

| Portal input | Example or source |
| --- | --- |
| Connection name | `googlevertexai-dev-us-central1-demo-project` |
| Description | `Approved non-production Registry Sync experiment` |
| Platform | Google Vertex AI |
| Project and region | Existing, approved project ID and region; real values stay local |
| Provider credential | Existing, approved Google service-account credential supplied only through the authorized portal flow |
| Import scope | Entire scope exposed by that connection; confirm before saving or syncing |

Microsoft's current GCP instructions list `aiplatform.reasoningEngines.list`,
`aiplatform.reasoningEngines.get`, and
`aiplatform.reasoningEngines.delete` for a custom role, or the broader Vertex
AI Administrator role. This is not a purely read-only credential recipe.
Have the environment owner review the credential's capabilities; do not
grant delete/admin rights simply to make validation pass. The later
one-agent identity allowlist does **not** constrain what Registry Sync
imports from the connection. [A6]

**Sample API Call:** No documented connection-create, credential-validation,
sync-trigger, complete connection-list, or connection-details request was
found. However, the following documented Package reads support the
package-derived discovery path. [A4, A5, A10]

These are a preview of Steps 3-4, not requests to execute before sign-in.
Obtain the approved token in Step 2, then run each read in its own step;
do not repeat them merely because they also appear here.

```http
GET https://graph.microsoft.com/v1.0/copilot/admin/catalog/packages
Authorization: Bearer {{graphAccessToken}}
Accept: application/json
```

```http
GET https://graph.microsoft.com/v1.0/copilot/admin/catalog/packages/{{originalPackageId}}
Authorization: Bearer {{graphAccessToken}}
Accept: application/json
```

The list response supplies package IDs, not a connection collection.
Details supplies the `definition` strings to parse. Follow returned paging
links, exclude known companions, and retain unresolved metadata rather than
guessing a connection. The full read procedure remains in Steps 3-4.

**Sample Output:**

Fresh-setup portal observation fields, shown as illustrative targets rather
than an API response:

```text
Connection: googlevertexai-dev-us-central1-demo-project
Platform: Google Vertex AI
Region: <approved-region>
Connection saved: yes
Credential validation: completed successfully
Last sync status: <actual portal status>
Last run: <actual portal time>
Total synced agents: <observed count>
Synchronization results: <inspect actual successes and errors>
```

These are not results from a newly executed setup or guaranteed literal
portal labels.

For either branch, a later local projection of the GCP Package Details
fields can look like this. It is a synthetic example based on observed
fields, not a connection-GET response or an already completed fleet scan:

```json
{
  "inventoryOrigin": "package-metadata",
  "completeConnectionInventory": false,
  "platform": "GoogleVertexAI",
  "connectionId": "<exact-source-connection-id>",
  "observedProjectId": "<observed-project-id>",
  "observedRegion": "<observed-region>",
  "connectionDisplayName": null,
  "currentSyncStatus": null
}
```

**Gap Identified:** The manual gap concerns connection creation/first sync
and access to complete connection configuration, not extraction of every
connection reference or source-scope field. Package-derived discovery
cannot reveal connections without visible imported packages, and it does
not establish current connection health or full configured scope.
The GCP metadata shape is not yet established for other providers.
Do not use an empty package-derived result to conclude that no connection
exists, or use a package's display name/timestamps as connection details.

**Actions Required:**

1. Choose the reuse branch for the current lab. For an approved fresh
   setup, record the connection creation and import result, along with
   any connection ID actually exposed by the portal or setup records.
2. Continue in order: Step 2 for authentication, Steps 3-4 for Package
   reads and metadata extraction, then Step 5 for source identification
   and scope/Blueprint approval. Read `platform` directly from Package
   Details. A connection map is optional provenance enrichment, not an
   intermediate lookup needed to identify the platform or assign a group.
3. Keep current sync status and other unavailable details unresolved
   unless supplied by an authoritative source. Identify the grouping-policy
   maintainer and the accountable owner/security approver. Collect the
   selected agent's environment, responsible team, intended Blueprint
   credential controller, and allowed shared baseline access, plus its
   sponsor. These are human decisions, not values to infer from a connection
   ID; the detailed input table and grouping procedure are in Step 5.
   Missing decisions do not block read-only discovery, but they block
   provisioning. Obtain separate approval for exact Entra/companion
   mutations; do not manufacture a match from platform or name.
4. Record any newly created connection's retention/cleanup decision for
   Step 16. Existing connections and deferred cleanup remain untouched.
   If complete unattended connection management is mandatory, stop that
   requirement and obtain a supported interface from PG; do not replay
   private portal requests.

#### Connection naming convention

The consolidated decision, companion source-ID convention, and required
mapping fields are recorded in
[Lab 20 design decisions](design-decisions.md).

Use a human-readable connection label with region before source scope:

```text
<platform>-<env>[-<region>]-<source-scope>
```

The brackets indicate an optional segment; they are not literal characters
in the name. This order puts broader grouping fields first, groups names
by region when sorted, and leaves potentially long source identifiers last.
It is a proposed team convention, not a Microsoft naming requirement.

| Component | Convention |
| --- | --- |
| `platform` | Consistent lowercase label, such as `googlevertexai`. Keep the canonical API platform value separately; the display label does not change `GoogleVertexAI`. |
| `env` | Use a controlled vocabulary, such as `dev`, `test`, `uat`, or `prod`. The experiment remains limited to approved non-production objects. |
| `region` | Configured region, such as `us-central1`. Omit the segment when region does not apply; do not treat an unknown region as not applicable. |
| `source-scope` | Stable project ID, account alias, organization identifier, or workspace identifier, depending on the provider. For GCP, use the project ID rather than its display name. |

Synthetic examples:

```text
googlevertexai-dev-us-central1-demo-project
googlevertexai-dev-europe-west1-demo-project
salesforceagentforce-uat-demo-org
```

Use lowercase letters, digits, and hyphens for the human-readable label.
Store environment, configured region, and exact native scope identifiers
as separate fields; do not recover them by splitting the name on hyphens.
Preserve source identifiers exactly even if their display label is
normalized. When matching connection records, use `ConnectionId`, scoped by
tenant and the platform already read from Package Details. Connection names
and connection lookups are not the source of the package's platform.

Keep Blueprint group labels separate: a connection may contain agents
assigned to different groups. A name does not establish group membership,
permissions, sync health, or uniqueness. These examples do not rename any
existing connection; changing this document is not approval to do so.

### Step 2 - Obtain the approved delegated Graph token and operator ID

**Description:** Reuse the existing approved public-client sign-in approach.
Request only the permissions for the current phase; obtain a new token
after any separately approved consent change. [I13, I14]

The notebook now uses normal Microsoft Entra browser sign-in through
MSAL `acquire_token_interactive` (authorization code with PKCE), not device
code. The existing login app must have `http://localhost` registered under
**Mobile and desktop applications**; request the app owner's approval if a
configuration change is needed. The browser and kernel must run on the same
local computer. No new secret or additional permission is required merely
to switch login flows. See the
[MSAL interactive-token guidance](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens#acquire-token-interactive).
The device-code HTTP requests and observed output below are retained for the
separate REST Client walkthrough and earlier evidence; both flows obtain
delegated tokens from Entra. They are not additional notebook steps.

| Phase | Delegated permissions to approve when needed |
| --- | --- |
| Discovery | `CopilotPackages.Read.All`, `User.Read` |
| Entra read/reuse | `AgentIdentityBlueprint.Read.All`, `AgentIdentityBlueprintPrincipal.Read.All`, `AgentIdentity.Read.All` |
| Entra creation | `AgentIdentityBlueprint.Create`, `AgentIdentityBlueprintPrincipal.Create`, `AgentIdentity.Create.All`; omit creation permissions for objects being reused |
| Companion read/write | `AgentRegistration.Read.All`; add `AgentRegistration.ReadWrite.All` only for an approved mutation |

These permissions do not replace ownership, role, license, or tenant-policy
requirements. Credentials, runtime grants, and cleanup permissions are
separate decisions, not part of the default token request. Include
`User.Read` when repeating `/me` after a later sign-in, and confirm that
the operator still matches the creator/owner recorded in the approved plan.

**Sample API Call:**

```http
POST https://login.microsoftonline.com/{{tenantId}}/oauth2/v2.0/devicecode
Content-Type: application/x-www-form-urlencoded

client_id={{clientId}}&scope={{scopeFormValue}}
```

For initial discovery, `scopeFormValue` is
`https%3A%2F%2Fgraph.microsoft.com%2FCopilotPackages.Read.All%20https%3A%2F%2Fgraph.microsoft.com%2FUser.Read`.
For later phases, form-encode the approved space-separated Graph scopes.
Complete sign-in using the returned instructions, then exchange the
returned device code:

```http
POST https://login.microsoftonline.com/{{tenantId}}/oauth2/v2.0/token
Content-Type: application/x-www-form-urlencoded

grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Adevice_code&client_id={{clientId}}&device_code={{deviceCode}}
```

Use the access token to obtain the creator ID:

```http
GET https://graph.microsoft.com/v1.0/me?$select=id
Authorization: Bearer {{graphAccessToken}}
```

**Sample Output (observed sign-in pattern; synthetic values):**

```text
Device authorization: 200 OK
{
  "device_code": "<never-save-device-code>",
  "user_code": "<never-share-user-code>",
  "verification_uri": "https://microsoft.com/devicelogin",
  "interval": 5,
  "expires_in": 900
}

Token exchange after sign-in: 200 OK
{
  "token_type": "Bearer",
  "scope": "CopilotPackages.Read.All User.Read",
  "access_token": "<never-save-access-token>"
}

Current user: 200 OK
{"id": "<operator-user-id>"}
```

**Gap Identified:** The earlier successful token does not establish Entra
creation rights. Permission consent can block the whole 1-2 day schedule.

**Actions Required:** Keep token responses out of evidence files, logs, and
source control. Respect the returned polling interval and device-code expiry;
stop on declined consent. Do not request `offline_access` for this short
pilot. Record `operatorUserId` locally. The notebook proposes the signed-in
operator as the default sponsor and preserves an existing saved override;
group-plan approval must confirm that responsibility or select another
approved sponsor. A default value is not a substitute for that approval.

### Step 3 - List packages and follow every returned page

**Description:** Start with the complete Package inventory. Do not filter
only by a Copilot host, because that may exclude external-platform entries.
Client-side platform filtering is a first pass, not proof of sync origin. [A5]

**Sample API Call:**

```http
GET https://graph.microsoft.com/v1.0/copilot/admin/catalog/packages
Authorization: Bearer {{graphAccessToken}}
Accept: application/json
```

If a response supplies `@odata.nextLink`, follow that returned continuation
URL unchanged using the appropriate Graph token. Do not construct your own
skip token. Stop only when there is no continuation.

**Sample Output (observed package shapes, abridged):**

```text
200 OK
{
  "value": [
    ...
    {"id": "<original-package-id>", "displayName": "Demo Agent",
     "platform": "GoogleVertexAI", "type": "lob"},
    {"id": "<known-companion-package-id>", "displayName": "Demo Agent",
     "platform": "GoogleVertexAI", "type": "shared"}
    ...
  ]
}
```

**Gap Identified:** Both synchronized and API-created records can have the
same platform and display name. The sample's `lob`/`shared` distinction is
an observation, not a guaranteed cross-provider classification rule.

**Actions Required:** Keep the complete response only in ignored evidence.
Exclude known companion IDs; select the approved original package for
detail inspection. Reconcile all pages before declaring an agent absent.

### Step 4 - Read the original package and extract source metadata

**Description:** Capture a before-mutation baseline and inspect the nested
definition. The GCP sample exposed its source ID, provider markers, and
`SourceIds.ConnectionId`, plus `SourceIds["mac.projectId"]` and
`SourceIds["mac.region"]`, inside `elementDetails[].elements[].definition`,
a JSON-encoded string. Parse that string before reading these fields;
they are not top-level Package Details fields. [A4]

**Sample API Call:**

```http
GET https://graph.microsoft.com/v1.0/copilot/admin/catalog/packages/{{originalPackageId}}
Authorization: Bearer {{graphAccessToken}}
Accept: application/json
```

**Sample Output (observed shape, synthetic and abridged):**

```text
200 OK
{
  "id": "<original-package-id>",
  "platform": "GoogleVertexAI",
  "agentIdentityId": null,
  "elementDetails": [
    ...
    {
      "elements": [
        {
          "definition": "{\"SourceAgentId\":\"<provider-native-agent-id>\",\"CreatedDateTime\":\"2026-09-01T00:00:00Z\",\"LastModifiedDateTime\":\"2026-09-02T00:00:00Z\",\"SourceIds\":{\"ConnectionId\":\"<exact-source-connection-id>\",\"mac.projectId\":\"<observed-project-id>\",\"mac.region\":\"<observed-region>\",\"mac.agentRegistrationType\":\"ConnectedPlatform\",\"mac.agentRegistrationProviderType\":\"GoogleVertexAI\"}}"
        }
      ]
    }
    ...
  ]
}
```

**Gap Identified:** This nested provider schema is observed, not a stable
cross-provider API contract. `SourceIds.ConnectionId` supplies a connection
reference, not a Registration ID or the connection's full configuration.
Some identity/owner fields are absent or null; absence must not be silently
replaced with a guessed ID.

**Actions Required:** Read the top-level `platform` directly from Package
Details and preserve its API value, such as `GoogleVertexAI`. Do not derive
it from `ConnectionId`, a connection alias, or a display-label mapping.
Parse the outer JSON and then the relevant definition string. Reject
missing, contradictory, or multiple candidate source IDs.
Preserve the exact source ID and ISO timestamps without decoding or
normalizing them speculatively. If inspecting with PowerShell, preserve
timestamp strings, for example with `ConvertFrom-Json -DateKind String`;
do not reproduce the earlier locale-formatted timestamp failure.
Extract `SourceIds.ConnectionId` with its observed casing and preserve the
exact value. Read dotted metadata keys such as `mac.projectId` and
`mac.region` as literal keys, not additional nested objects. Retain their
paired values as observed source scope and compare them with approved
context. Record missing or conflicting connection references explicitly;
do not fall back to platform-only matching when correlating connections.
This does not prevent reading the package's own `platform`. Do not treat these fields'
presence or absence as a universal synchronized-versus-companion classifier.
Pass the directly observed platform, source key, and connection provenance
to Step 5. Source identity identifies the agent to assign; connection
metadata records its sync origin. Neither determines a `blueprintGroup`
assignment or decides which agents may share Blueprint authority.

### Step 5 - Build the source key, Blueprint group, and no-write plan

**Description:** Use the Package Details already read in Step 4.
`id` identifies the inventory record, while the top-level `platform`
directly identifies its platform. There is no
`Package ID -> Connection ID -> platform` lookup in this step. Keep the
returned platform value, such as `GoogleVertexAI`, without translating it
through a connection name or display-label mapping.

Build the source key from the authenticated tenant, that platform, the
observed native scope, and the exact source agent ID. Separately retain
`parsedDefinition.SourceIds.ConnectionId` as sync provenance. If additional
connection context is needed, correlate it with an approved connection
record; that lookup is not needed to discover the platform and does not
choose the Blueprint group. An optional `connectionAlias` is only a label.

Independently apply a **human-defined and maintained grouping policy**.
`blueprintGroup`, such as `demo-team-nonproduction`, is a stable local
policy label chosen by the maintainer. It is neither returned by a
Microsoft API nor an Entra security group to create. Within a tenant,
each approved group maps to one active Blueprint binding in the journal;
each selected source agent must have exactly one approved group assignment.

#### Inputs and who supplies them

| Input | Source | Required decision |
| --- | --- | --- |
| Package ID and platform | Package Details `id` and top-level `platform` | Identify the inventory record and read its platform directly; no connection lookup or platform-label mapping is needed. |
| Tenant, exact source agent ID, observed project/region | Authenticated context and parsed Package definition in Steps 2-4 | Build the source key; do not replace source identity with a Package ID or display name. |
| Connection ID and optional connection context | Parsed `SourceIds.ConnectionId`; approved connection records only when additional context is needed | Preserve sync provenance separately; do not use it to derive platform or assign the Blueprint group. |
| Environment and responsible team | Environment owner | Confirm non-production scope and accountable ownership; a project name alone is not approval. |
| Blueprint credential controller | Accountable owner/security approver | Identify who may control the Blueprint's credential or federation setup and act through its child identities. Record responsibility, never secret values. |
| Shared baseline access | Resource owner/security approver | Record allowed resources and inherited permissions, or an explicit provisioning-only/no-runtime-access decision. Do not copy the operator's Graph administration permissions. |
| Group label, member allowlist, policy maintainer, and approval record | Maintainer with the accountable approver | Define and maintain the policy; the script must not invent these values. |
| Existing Blueprint object/app/principal IDs | Durable journal and approved Entra reads | Resolve the group's actual Blueprint in Steps 6-7, not by matching its display name. |

#### Manual grouping procedure

1. Start with the single approved disposable agent. Review its source
   metadata and obtain the human inputs above. If responsibility or the
   intended permission boundary is unknown, leave it unassigned; do not
   place it in a default platform-wide group.
2. Decide which agents may share Blueprint authority. A Blueprint can act
   through its child identities, so this is a trust and credential decision,
   not an inventory-labeling convenience. For this pilot, keep different
   environments, responsible teams, credential controllers, or incompatible
   shared access requirements in separate groups unless an explicit
   reviewed decision establishes a safe shared boundary. [I1]
3. Choose a stable local label, for example `demo-team-nonproduction`.
   Record the reason, accountable maintainer, environment, credential
   controller, and shared-access decision. One connection may require
   several groups; several connections may share a group only after the
   same boundary review. Neither equal nor different connection IDs make
   that decision automatically.
4. Assign exact source keys to the group. For the 1-2 day pilot, use an
   explicit member allowlist rather than platform/connection wildcards.
   When a new agent appears, it remains unassigned until the maintainer
   approves membership. An existing source seen through another connection
   is reconciled as the same source, not silently assigned a second group.
5. Record policy version, approval status, and an approval reference. Keep
   the proposed JSON policy in protected ignored storage, for example
   `evidence\blueprint-groups.json`; designate who updates and reviews it.
   The JSON below illustrates the broader design. The simple notebook
   instead uses inline groups per platform, a sponsor ID, and separate
   approval flags for the group plan and its one selected agent's
   membership. It saves IDs under
   `evidence\notebook-pilot\`; it does not implement this separate
   policy-file format or a general grouping engine.
6. Resolve each selected source key against the approved membership list.
   Zero matches, multiple group matches, pending approval, or conflict
   with an existing identity/Blueprint binding blocks that agent's plan.
   Inspect the journal's `(tenant, blueprintGroup)` binding before deciding
   whether Step 6 may reuse or create an actual Blueprint.

For example, two agents imported by the same GCP connection may need
separate groups if different teams control their credentials or require
incompatible inherited access. Conversely, two approved non-production
connections do not require separate Blueprints merely because their
connection IDs differ. For the current one-agent pilot, start with one
explicitly approved group and add no other members by default.

**Sample API Call:** None. There is no API request in this workflow to
"get the blueprint group" or resolve platform through a connection.
Platform comes directly from Package Details; Blueprint group assignment
uses the customer-maintained policy. This step neither
creates a Microsoft group nor grants permissions. Human-readable connection
names may remain unresolved, but group membership and its credential/access
boundary must be approved before provisioning.

**Sample Output:**

Proposed human-maintained policy, shown with pending approval. All fields
below are local configuration, not Microsoft API properties:

```json
{
  "policyVersion": 1,
  "groups": [
    {
      "tenant": "<tenant-id>",
      "blueprintGroup": "demo-team-nonproduction",
      "maintainer": "<accountable-policy-maintainer>",
      "environment": "nonproduction",
      "responsibleTeam": "<approved-responsible-team>",
      "credentialController": "<approved-blueprint-credential-controller>",
      "baselineAccessDecision": "No runtime access is configured by this provisioning-only pilot.",
      "groupingReason": "Only the approved disposable agent is included in this pilot.",
      "approval": {
        "status": "pending",
        "reference": null
      },
      "members": [
        {
          "tenant": "<tenant-id>",
          "provider": "GoogleVertexAI",
          "nativeScope": "<approved-project-and-region>",
          "sourceAgentId": "<exact-source-agent-id>"
        }
      ]
    }
  ]
}
```

The baseline-access decision does not prove that a reused Blueprint has
no pre-existing credentials or grants. Review that Blueprint against the
approved boundary before reuse. Do not grant runtime permissions merely
to complete this policy example.

Resulting draft plan for this lab's existing companion, still blocked on
grouping approval and separate authorization for the proposed mutations:

```json
{
  "sourceKey": {
    "tenant": "<tenant-id>",
    "provider": "GoogleVertexAI",
    "nativeScope": "<approved-project-and-region>",
    "sourceAgentId": "<exact-source-agent-id>"
  },
  "connectionId": "<exact-source-connection-id>",
  "connectionAlias": "googlevertexai-dev-us-central1-demo-project",
  "blueprintGroup": "demo-team-nonproduction",
  "groupingPolicyVersion": 1,
  "groupingApprovalStatus": "pending",
  "originalPackageId": "<original-package-id>",
  "companionRegistrationId": "<previously-created-registration-id>",
  "plan": ["resolve-blueprint", "resolve-agent-identity", "patch-companion"],
  "apply": false
}
```

**Gap Identified:** Inventory metadata cannot supply the customer's
credential-sharing decision, permission boundary, approval, or policy
maintainer. Without this human-owned input, `blueprintGroup` is unresolved
even when platform and source identity are known. The notebook uses an explicit one-agent
choice and approval flag; a general fleet grouping engine and versioned
policy management remain outside that simple example.
Additional connection context can remain unresolved without making the
top-level platform unknown. The nested schema is not
established across providers, and a recreated connection can change its ID
without changing the source agent.

**Actions Required:** Maintain two distinct records: the reviewed grouping
policy defines membership and boundaries; the runtime journal records the
actual Blueprint binding and object-creation outcomes. Real values remain
in protected storage. Retain the exact connection ID as provenance, not
as a substitute for the source key or group assignment.

Review and version the policy when agents are added/removed or team,
environment, credential authority, or access requirements change. Re-run
the no-write plan against that version and retain prior approved versions
for audit. A policy edit must not automatically move an existing Agent
Identity to another Blueprint, create a replacement, or delete an old one;
stop for a separately approved migration decision.

Resolve missing or conflicting source identity, and any provenance needed
to establish the approved scope, before writing. An unresolved connection
alias or unavailable full connection record alone does not block reading
platform or assigning a group. Missing or overlapping membership, pending
approval, or an incomplete/lost journal still requires reconciliation,
not guessed labels or "assume missing, create again." Approve the exact
planned objects and mutations separately before changing `apply` to true.

### Step 6 - Reuse or create the Blueprint for the approved group

**Description:** Use the approved `(tenant, blueprintGroup)` from Step 5
to resolve the journal's Blueprint binding. If an approved Blueprint object
ID is recorded, read it and verify its appId and intended credential
boundary. The local group label is not a Blueprint ID or a Graph query key.
Create only when no approved reusable Blueprint exists and a new object
is authorized. [I3, I8]

**Sample API Call (reuse):**

```http
GET https://graph.microsoft.com/v1.0/applications/{{blueprintObjectId}}/microsoft.graph.agentIdentityBlueprint
Authorization: Bearer {{graphAccessToken}}
```

**Sample API Call (approved creation instead):**

```http
POST https://graph.microsoft.com/v1.0/applications/microsoft.graph.agentIdentityBlueprint
Authorization: Bearer {{graphAccessToken}}
Content-Type: application/json
OData-Version: 4.0

{
  "displayName": "Demo Team Nonproduction Blueprint",
  "sponsors@odata.bind": [
    "https://graph.microsoft.com/v1.0/users/{{sponsorUserId}}"
  ],
  "owners@odata.bind": [
    "https://graph.microsoft.com/v1.0/users/{{operatorUserId}}"
  ]
}
```

**Sample Output (expected; not executed):**

```text
200 OK on read, or 201 Created on create
{
  "id": "<blueprint-object-id>",
  "appId": "<blueprint-app-id>",
  "displayName": "Demo Team Nonproduction Blueprint"
}
```

**Gap Identified:** A missing Blueprint field on the package is not proof
that no suitable Blueprint exists. A failed GET is not a create decision.

**Actions Required:** Save `id` and `appId` in separate journal fields
immediately, bound to the approved tenant/group and policy version.
Subsequent members of that group reuse this binding rather than creating
one Blueprint per agent. Verify the selected Blueprint and sponsor with
the owner. Stop on access denial, conflicting bindings, or ambiguous lookup.
Do not add a secret, runtime permission grant, or federated credential for
this provisioning-only step.

### Step 7 - Ensure the Blueprint principal exists

**Description:** The Blueprint application and its tenant principal are
different objects. The portal wizard may already have created both.
The principal has a documented appId lookup, unlike Agent Registration.
[I4, I12]

**Sample API Call (read first):**

```http
GET https://graph.microsoft.com/v1.0/servicePrincipals(appId='{{blueprintAppId}}')/microsoft.graph.agentIdentityBlueprintPrincipal
Authorization: Bearer {{graphAccessToken}}
```

Only after confirming that the principal is genuinely absent, and that no
earlier create is still unresolved, use the approved create branch:

```http
POST https://graph.microsoft.com/v1.0/servicePrincipals/microsoft.graph.agentIdentityBlueprintPrincipal
Authorization: Bearer {{graphAccessToken}}
Content-Type: application/json
OData-Version: 4.0

{"appId": "{{blueprintAppId}}"}
```

**Sample Output (expected; not executed):**

```text
200 OK on read, or 201 Created on create
{
  "@odata.type": "#microsoft.graph.agentIdentityBlueprintPrincipal",
  "id": "<blueprint-principal-id>",
  "appId": "<blueprint-app-id>",
  "accountEnabled": true
}
```

**Gap Identified:** Blueprint creation alone does not establish that a
usable principal is present. Authorization failures and propagation delays
must not be handled as unconditional create triggers.

**Actions Required:** Persist `blueprintPrincipalId`, verify its appId
against Step 6, and add it to the same tenant/group journal binding.
Stop if disabled or inconsistent. A conflict or uncertain create outcome
requires read/reconciliation, not another POST.

### Step 8 - Reuse or create one Agent Identity for the source agent

**Description:** Reuse the journaled Agent Identity if it belongs to the
approved source and Blueprint. Otherwise create one child identity with an
accountable sponsor, only when the create has been approved. [I5, I9]

**Sample API Call (reuse):**

```http
GET https://graph.microsoft.com/v1.0/servicePrincipals/{{agentIdentityId}}/microsoft.graph.agentIdentity
Authorization: Bearer {{graphAccessToken}}
```

**Sample API Call (approved creation instead):**

```http
POST https://graph.microsoft.com/v1.0/servicePrincipals/microsoft.graph.agentIdentity
Authorization: Bearer {{graphAccessToken}}
Content-Type: application/json
OData-Version: 4.0

{
  "displayName": "Demo Agent Identity",
  "agentIdentityBlueprintId": "{{blueprintAppId}}",
  "sponsors@odata.bind": [
    "https://graph.microsoft.com/v1.0/users/{{sponsorUserId}}"
  ],
  "owners@odata.bind": [
    "https://graph.microsoft.com/v1.0/users/{{operatorUserId}}"
  ]
}
```

**Sample Output (expected; not executed):**

```text
200 OK on read, or 201 Created on create
{
  "@odata.type": "#microsoft.graph.agentIdentity",
  "id": "<agent-identity-id>",
  "displayName": "Demo Agent Identity",
  "servicePrincipalType": "ServiceIdentity",
  "agentIdentityBlueprintId": "<blueprint-app-id>"
}
```

**Gap Identified:** This operation does not consume the provider's source
ID or the original Package ID. Entra therefore does not establish the
external-agent correlation for the application.

**Actions Required:** Persist the source-key-to-identity mapping immediately.
Do not reuse an identity merely because its display name matches. Confirm
the sponsor/owner relationships in Entra; adding identities does not assign
them runtime credentials or downstream permissions.

### Step 9 - Verify the actual Entra parent-child relationship

**Description:** Read the Blueprint and Agent Identity back from the same
approved tenant. This establishes the Entra objects and parent reference
before attempting a separate catalog association. [I8, I9]

**Sample API Call:**

```http
GET https://graph.microsoft.com/v1.0/applications/{{blueprintObjectId}}/microsoft.graph.agentIdentityBlueprint?$select=id,appId
Authorization: Bearer {{graphAccessToken}}

###

GET https://graph.microsoft.com/v1.0/servicePrincipals/{{agentIdentityId}}/microsoft.graph.agentIdentity?$select=id,agentIdentityBlueprintId,servicePrincipalType
Authorization: Bearer {{graphAccessToken}}
```

**Sample Output (expected; not executed):**

```text
Blueprint: 200 OK
{"id": "<blueprint-object-id>", "appId": "<blueprint-app-id>"}

Agent Identity: 200 OK
{"id": "<agent-identity-id>", "agentIdentityBlueprintId": "<blueprint-app-id>",
 "servicePrincipalType": "ServiceIdentity"}
```

**Gap Identified:** Successful Entra reads prove neither source-agent
ownership nor Agent 365's interpretation of registration identity fields.

**Actions Required:** Compare exact returned values, not names. Halt on any
parent/type/tenant mismatch. If duplicate catalog records are unacceptable,
stop here with an explicitly external mapping; do not describe it as a
native link on the synchronized package.

### Step 10 - Resolve only a known companion registration

**Description:** For the existing Lab 20 experiment, read the Registration
ID already returned by its successful POST. For a new pilot, distinguish
"never created" from "creation outcome unknown." [A1]

**Sample API Call:**

```http
GET https://graph.microsoft.com/beta/copilot/agentRegistrations/{{companionRegistrationId}}
Authorization: Bearer {{graphAccessToken}}
```

**Sample Output (observed pre-association shape, abridged):**

```text
200 OK
{
  "id": "<companion-registration-id>",
  "sourceAgentId": "<exact-source-agent-id>",
  "originatingStore": "GoogleVertexAI",
  "ownerIds": ["<operator-user-id>"]
  ...
}
```

**Gap Identified:** No registration-list/source-ID lookup is documented.
The original Package ID cannot fill a missing registration-ID entry.

**Actions Required:** Verify source, ownership, and journal provenance.
If this owned companion is confirmed, use Step 11A. Only an explicitly
approved first-time companion uses Step 11B. A failed read, missing journal,
or lost POST response requires reconciliation; it does not authorize create.

### Step 11 - Write the identity association: choose A or B, never both

**Description:** Use the documented identity fields on the companion
registration. The payloads below use Blueprint appId and Agent Identity id
as the **candidate convention** described earlier. Their semantic resolution
in Agent Registration is still a bounded experiment, not an established
contract. [A1]

**Sample API Call A (preferred for this lab: update the known companion):**

```http
PATCH https://graph.microsoft.com/beta/copilot/agentRegistrations/{{companionRegistrationId}}
Authorization: Bearer {{graphAccessToken}}
Content-Type: application/json

{
  "agentIdentityBlueprintId": "{{blueprintAppId}}",
  "agentIdentityId": "{{agentIdentityId}}"
}
```

**Sample API Call B (only for an approved, first-time companion):**

```http
POST https://graph.microsoft.com/beta/copilot/agentRegistrations
Authorization: Bearer {{graphAccessToken}}
Content-Type: application/json

{
  "displayName": "Demo Agent - identity companion",
  "description": "Disposable companion registration; original Registry Sync record retained",
  "createdBy": "{{operatorUserId}}",
  "ownerIds": ["{{operatorUserId}}"],
  "sourceAgentId": "{{sourceAgentId}}",
  "originatingStore": "GoogleVertexAI",
  "sourceCreatedDateTime": "{{sourceCreatedAt}}",
  "sourceLastModifiedDateTime": "{{sourceModifiedAt}}",
  "agentIdentityBlueprintId": "{{blueprintAppId}}",
  "agentIdentityId": "{{agentIdentityId}}"
}
```

**Sample Output (expected; identity-bearing writes not executed):**

```text
Branch A:
200 OK
(empty response body)

Branch B:
201 Created
{"id": "<new-companion-registration-id>"}
```

**Gap Identified:** The successful earlier POST omitted both identity
fields. Their acceptance, resolution, and package visibility remain to be
established. The Registry Sync record is not the target of either branch.

**Actions Required:** Obtain approval for this specific write. Do not copy
the connector's managing-app value into `managedByAppId`; retain the
approved user-owned approach. Include all required fields and exact source
timestamps on create. Save the returned Registration ID immediately and
record a pending-verification state. Never replay a successful or
ambiguous POST. On failure, record the safe error class and stop; do not
swap identifier types or mutate the original package by guesswork.

### Step 12 - Read back the companion's stored identity fields

**Description:** Confirm that the registration persisted the intended
values and retained the correct source correlation. [A1]

**Sample API Call:**

```http
GET https://graph.microsoft.com/beta/copilot/agentRegistrations/{{companionRegistrationId}}?$select=id,sourceAgentId,originatingStore,agentIdentityBlueprintId,agentIdentityId
Authorization: Bearer {{graphAccessToken}}
```

**Sample Output (success target; not yet observed):**

```text
200 OK
{
  "id": "<companion-registration-id>",
  "sourceAgentId": "<exact-source-agent-id>",
  "originatingStore": "GoogleVertexAI",
  "agentIdentityBlueprintId": "<blueprint-app-id>",
  "agentIdentityId": "<agent-identity-id>"
}
```

**Gap Identified:** Storing two strings is weaker than resolving them to
actual Entra objects. No public cross-resource relationship proves that
resolution through this response alone.

**Actions Required:** Compare all five values to the journal and Step 9.
If they match, record `companion-links-stored`, not "runtime governed" or
"original package enriched." Missing/mismatched fields are an unsuccessful
association attempt requiring investigation.

### Step 13 - Compare both packages and establish the association outcome

**Description:** Repeat Package List, identify the companion only through
evidence-backed correlation, then inspect it and the original package.
For the already-created lab control, the companion's Package ID was
observed to equal its Registration ID. Do not assume this for every new
record. [A2, A4, A5]

**Sample API Call (send in order, resolving the package ID before its GET):**

```http
GET https://graph.microsoft.com/v1.0/copilot/admin/catalog/packages
Authorization: Bearer {{graphAccessToken}}

###

GET https://graph.microsoft.com/v1.0/copilot/admin/catalog/packages/{{originalPackageId}}
Authorization: Bearer {{graphAccessToken}}

###

GET https://graph.microsoft.com/v1.0/copilot/admin/catalog/packages/{{companionPackageId}}
Authorization: Bearer {{graphAccessToken}}
```

**Sample Output (list: observed two-record pattern, abridged):**

```text
200 OK
{
  "value": [
    ...
    {"id": "<original-package-id>", "platform": "GoogleVertexAI", "type": "lob"},
    {"id": "<companion-package-id>", "platform": "GoogleVertexAI", "type": "shared"}
    ...
  ]
}
```

**Sample Output (details: success target, not yet observed after identity assignment):**

```text
Original: 200 OK
{"id": "<original-package-id>", "agentIdentityId": null, ...}

Companion: 200 OK
{"id": "<companion-package-id>", "agentIdentityId": "<agent-identity-id>", ...}
```

**Gap Identified:** Neither companion-package identity propagation nor a
Blueprint field on Package Details is guaranteed by the reviewed write
contract. If no evidence-backed companion package can be identified, a
display-name match is insufficient.

**Actions Required:** Read all pages and allow for propagation without
retrying POST. Confirm that the original source metadata remains intact;
investigate changes rather than assuming the workaround caused them.
Use the supported admin experience, where available, to confirm that the
companion resolves to the intended Entra identity/Blueprint, or obtain PG
confirmation. If only stored strings or separate Entra objects can be
shown, leave the companion's identity resolution **inconclusive** and
describe the demo as such. Do not fabricate a Blueprint field in the
sample package response.

### Step 14 - Persist the result and prove repeatability

**Description:** Retain the complete source/object mapping and rerun the
plan in read-only mode. Verify that the same source does not generate
another identity or companion registration.

**Sample API Call:** Repeat the read-only calls in Steps 6-10 and 12-13.
There is no public "reconcile this Registry Sync agent" endpoint; the
journal and plan comparison are application responsibilities.

**Sample Output (local example; a possible inconclusive pilot outcome):**

```json
{
  "state": "companion-links-stored",
  "sourceMappingVerified": true,
  "entraParentVerified": true,
  "registrationFieldsMatch": true,
  "companionAssociationResolution": "inconclusive",
  "runtimeBinding": "not-tested",
  "plannedNewObjectsOnRerun": 0
}
```

**Gap Identified:** The cross-service sequence is not a transaction. There
is no documented registration upsert, and later sync behavior is not
established by an immediate read.

**Actions Required:** Persist every successful creation before continuing,
record partial/unknown outcomes, and serialize operations per source key.
Observe an already-authorized subsequent sync before expanding the pilot;
do not trigger connection-wide changes solely for this step. Do not expand
while association resolution remains inconclusive, even if the repeated
plan is a no-op. Stop if the second plan proposes an unexplained new
object. Retain an explicit rollback/cleanup inventory rather than
automatically deleting partial work.

### Step 15 - Optionally prove one actual runtime access path

**Description:** Only under a separate approved runtime experiment, make
the real agent or authorized integration component acquire a resource token
as the assigned Agent Identity using the recommended auth SDK. [I6, I11]

**Sample API Call (illustrative customer test resource, not a Microsoft API):**

```http
GET https://api.example.com/pilot/read
Authorization: Bearer {{agentResourceToken}}
```

`api.example.com` must be replaced with an existing, approved, protected test
resource. `agentResourceToken` is issued for that resource; never substitute
the operator's Graph token. The sample does not provision a resource or
define a ready-to-run token-acquisition implementation.

**Sample Output (success target; application-specific):**

```text
200 OK
{"result": "authorized"}
```

**Gap Identified:** A `200` alone does not prove which identity was used.
Even a verified token path does not bind every tool call or control the
third-party runtime's native credentials.

**Actions Required:** Use server-side authentication/audit evidence to
confirm the expected subject/actor, audience, and effective permissions.
Use an approved negative authorization case if demonstrating enforcement.
Keep evidence redacted and local. If runtime integration or credentials
are not approved, skip this step and explicitly label runtime binding
"not tested"; do not expand into new infrastructure.

### Step 16 - Retain deliberately or clean up with explicit approval

**Description:** Record which objects are retained and why. Cleanup of the
existing Lab 20 registration is still deferred; the examples below do not
authorize deletion. Registration deletion is irreversible. [A9, I10, I15, I16]

**Sample API Call (conditional example: approved companion retirement only):**

```http
DELETE https://graph.microsoft.com/beta/copilot/agentRegistrations/{{companionRegistrationId}}
Authorization: Bearer {{graphAccessToken}}
```

**Sample Output (expected if approved and executed; not run):**

```text
204 No Content
(empty response body)
```

**Gap Identified:** Registration deletion does not establish safe identity
cleanup or automatic package disappearance. The two catalog records and
Entra objects have separate lifecycle checks; a shared Blueprint may serve
other agents.

**Actions Required:** First confirm that no consumer depends on the
companion association, including any adopted native link. After an approved
delete, read the registration, list packages, and read the original package
and Entra identity again. Establish the actual result before proceeding.
Only then, under separate approval and with no remaining dependents,
retire experiment-created Entra objects using the documented procedures:

```http
DELETE https://graph.microsoft.com/v1.0/servicePrincipals/{{agentIdentityId}}/microsoft.graph.agentIdentity
Authorization: Bearer {{graphCleanupToken}}

###

DELETE https://graph.microsoft.com/v1.0/applications/{{blueprintObjectId}}/microsoft.graph.agentIdentityBlueprint
Authorization: Bearer {{graphCleanupToken}}
```

These are separate conditional actions, **not a send-all sequence**.
Successful standard deletions return `204 No Content`. Deleting the
Blueprint application also removes its principal and triggers child
cleanup; never do it for a reused/shared Blueprint. If retaining a Blueprint
but retiring only its experiment-created principal is specifically
approved, the corresponding target is
`DELETE /v1.0/servicePrincipals/{{blueprintPrincipalId}}`; it also triggers
child cleanup and is not a harmless unlink.

For the two typed DELETE examples, `graphCleanupToken` requires separately
approved `AgentIdentity.DeleteRestore.All` and
`AgentIdentityBlueprint.DeleteRestore.All`, respectively, plus the
documented role/ownership requirements. The principal-only alternative has
its own deletion requirements. Creation scopes are not assumed to
authorize deletion. Prefer the specific API permission references over
adding broad directory permissions. [I15, I16]

Revoke only pilot-added credentials/grants that are no longer needed.
Preserve required audit mappings, clear REST Client request history and
token response tabs, and remove only known local sensitive artifacts after
the retention decision. Do not delete the GCP agent or a pre-existing
connector.

If Step 1 created a disposable connection under explicit approval, record
its retention decision separately. Only with a new, scoped cleanup approval,
delete that exact connection through **Connected platforms**; do not select
an agent-deletion action. No public connection-delete API was found.
Inspect inventory afterward: deleting the connection must not be assumed
to remove its imported packages, companion registration, or Entra objects.
Revoke a pilot-only provider credential only after its owner confirms that
nothing else uses it. The current lab's existing connection is not a
cleanup target. [A6]

## Recommended 1-2 day delivery

Scope the delivery as an **identity and catalog-association pilot**, not
production onboarding for every connected agent. It is achievable only if
the necessary access and disposable objects are approved in time.

| Stage | Work and acceptance boundary |
| --- | --- |
| Day 1: Registry Sync and inventory plan | Step 1: reuse the existing approved connection/imported agent, or perform explicitly approved manual setup and first sync; identify grouping-policy ownership and required decisions. Steps 2-4: derive connection IDs and observed scopes from Package reads. Step 5: define/review explicit group membership and boundaries, version the policy, and approve the no-write plan. |
| Day 1: one identity pair | Steps 6-9: reuse/provision the approved Blueprint/principal and child identity; verify their actual relationship. |
| Day 1: one registration association | Steps 10-13: prefer PATCH of the existing companion; compare both catalog records and distinguish stored fields from resolved identity links. |
| Day 2: repeatability | Step 14: the repeated plan must propose no unexplained new objects. Keep unresolved operations explicit. |
| Day 2: customer demonstration | Show the original record, the companion and Entra objects, and the exact level of association established. Disclose duplicates and unresolved resolution. Record retention or approved cleanup in Step 16. |
| Optional, separately approved | Step 15: prove one real downstream identity-based operation; otherwise make no runtime-binding claim. |

If the identity-field write fails, stop at that boundary and retain the
Entra-side mapping as an explicitly separate result. Do not compensate with
an undocumented Package PATCH or a new registration on every retry.

Updating this **companion** registration is not validation of Path 2, which
targets the **original Registry Sync** representation.

### Minimum implementation safeguards

- **Identity key:** scope the provider-native source ID by tenant, provider,
  and native account/project scope; retain connection provenance separately.
  Preserve the original source value. Where only a connection distinguishes
  records, use it conservatively and flag overlaps/re-created connections
  for reconciliation. Never match agents by display name.
- **Filter genuine synchronized records:** `platform == GoogleVertexAI`
  alone is insufficient. Our API-created companion has the same platform.
  Verify import provenance and exclude known companion registrations to
  prevent repeated duplicate creation. The nested source metadata observed
  in this lab is not a guaranteed cross-provider schema.
- **Human-owned grouping policy:** maintain explicit source-key membership,
  credential/access boundaries, owner, approval reference, and policy
  version. Do not infer a Blueprint group from platform or connection alone;
  unmatched or multiply matched agents remain blocked.
- **Durable journal:** save the source key, original package ID, Blueprint
  app/object/principal IDs, Agent Identity ID, companion registration/package
  IDs, exact observed connection ID, separately resolved connection context,
  tenant/group binding, grouping-policy version, ownership, creation
  provenance, and operation state. Keep actual object bindings in the
  journal rather than a competing copy in the grouping policy. Keep all
  real values in protected local/customer state, never tracked examples.
- **Retry safety:** serialize writes for a source key; persist returned IDs
  immediately. A timeout or ambiguous server error after POST is an unknown
  outcome, not permission to POST again. Without a supported lookup, require
  reconciliation before continuing.
- **Separate provisioning from runtime:** never give every agent the
  onboarding application's administrative permissions. Default to dry-run,
  approved batches, and no automatic deletion.

Before bulk use, confirm throttling, consent, licensing, credentials,
recovery, sync lifecycle, and provider-specific behavior, and obtain a
production-supported registration/association route. Microsoft's deletion
guidance describes a 250-agent-identity-per-Blueprint limit for app-only
provisioning; soft-deleted identities continue to consume quota. Do not
design an unbounded "one Blueprint for the entire platform" automation
loop. [I10]

### Customer-facing claim

> We can provision individual Entra Agent Identities for selected external
> agents and demonstrate their association with separately managed Agent 365
> registrations. This does not yet enrich the original Registry Sync record
> or establish control over the external runtime.

Use that wording only after the identity-bearing association succeeds.
Until then, the demonstrated result is the same-source duplicate-registration
experiment, not completed identity onboarding.

Adding IDs alone does not change GCP IAM, AWS IAM, Salesforce permissions,
Anthropic credentials, tool routing, or existing sessions. A runtime or an
authorized integration component must actually acquire and use tokens for
the chosen Agent Identity. SDK observability, resource authorization, and
runtime enforcement remain separate integration work. A policy/token
demonstration proves only the tested resource path, not an external compute
kill switch. [I1, I6, I7]

## Prepare for native support without assuming its migration contract

Keep the provider-native source key as the durable identity of the external
agent. Package IDs, registration IDs, and Entra IDs are separately managed
references, not interchangeable primary keys.

| Future product behavior | Required migration |
| --- | --- |
| Native sync can adopt our existing Entra identity and Blueprint. | Verify adoption on one agent; preserve identity-dependent grants and runtime configuration where supported; retire the companion registration only after safe unlink/delete semantics are confirmed. |
| Native sync creates its own identity or requires its own Blueprint. | Treat this as an identity replacement: review and re-establish grants, resource assignments, federation/token configuration, policies, owners/sponsors, and audit correlation. Do not assume identities can be reparented or IDs preserved. |
| Native sync still cannot adopt or deduplicate existing records. | Keep the pilot isolated and the source mapping intact. Require a PG-supported reconciliation procedure before fleet migration. |

Use a per-agent transition such as `inventory-only` ->
`companion-links-stored` -> `companion-association-verified` ->
`native-association-verified` -> `companion-retired`. Do not advance from
stored links to verified association without the evidence described in
Step 13. These are application states, not Microsoft API values, and
runtime-binding status is tracked independently.

Freeze new companion creation during a migration canary. Observe at least
one completed sync cycle, confirm the intended native record and identity
persist, and test any actual runtime dependency before switching the
authoritative mapping. Preserve the old mapping for audit and rollback.
Automatic source disappearance must not trigger identity deletion.

**Do not delete a shared Blueprint as routine migration cleanup.** Deleting
the Blueprint or its principal triggers asynchronous deletion of child
Agent Identities. Check dependencies before retiring even one identity, and
obtain explicit approval for each destructive step. [I10]

The prior experiment's cleanup remains deferred: its created registration
and companion package have not been deleted. This research creates no new
remote objects, credentials, or raw evidence. Any subsequent pilot must
inventory its own objects, approvals, permissions, credentials, and local
artifacts; retire only those no longer needed, with explicit authorization.

## Questions requiring PG confirmation

1. Is there a supported mapping or claim/attach operation for an existing
   Registry Sync package, and does that record have a public registration?
2. Which identity-ID types are expected, who may update connector-managed
   records, and will subsequent sync preserve the assignment?
3. Can the customer use a companion registration in production under an
   explicitly supported arrangement, despite the public beta restriction?
4. Will native support adopt customer-created identities/Blueprints or
   create replacements? How should duplicates and dependent permissions be
   migrated without losing audit correlation?
5. Which supported APIs create connections, validate provider credentials,
   trigger/schedule sync, and list/read connection configuration? Is the
   observed `SourceIds.ConnectionId` a supported package-to-connection
   reference across providers? Which reconciliation mechanism makes
   repeated setup and onboarding retry-safe?

## Sources: inventory and registration

- **A1:** [agentRegistration resource and operations](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/agent-registration/resources/agentregistration), [create](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/agent-registration/agentregistration-create), and [update](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/agent-registration/agentregistration-update).
- **A2:** [Package Management API overview](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/package/overview).
- **A3:** [Update Copilot package](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/package/copilotpackagedetail-update) and [reassign ownership](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/package/copilotpackage-reassign).
- **A4:** [copilotPackageDetail properties and relationships](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/package/resources/copilotpackagedetail).
- **A5:** [List packages: permissions, licensing, and filters](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/package/copilotpackages-list).
- **A6:** [Connected platforms: connection management and provider support](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/connected-platforms).
- **A7:** [Agent Registry convergence with Microsoft Agent 365](https://learn.microsoft.com/en-us/entra/agent-id/agent-registry-convergence).
- **A8:** [Microsoft Graph generated CopilotPackage model](https://github.com/microsoftgraph/msgraph-sdk-dotnet/blob/main/src/Microsoft.Graph/Generated/Models/CopilotPackage.cs) and [public beta metadata](https://graph.microsoft.com/beta/$metadata). Schema/model presence does not establish write support.
- **A9:** [Get agentRegistration](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/agent-registration/agentregistration-get) and [delete agentRegistration](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/agent-registration/agentregistration-delete).
- **A10:** [Graph API for agent registry and agent details](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/graph-api): inventory APIs, not Registry Sync connection provisioning. Installed CLI capability was separately inspected through `a365 --version`, `a365 --help`, and `a365 setup --help`.
- **A11:** [Create externalConnection](https://learn.microsoft.com/en-us/graph/api/externalconnectors-external-post-connections?view=graph-rest-1.0): a Microsoft Search connector API, not Agent 365 Registry Sync.
- **A12:** [Public Graph v1.0 metadata](https://graph.microsoft.com/v1.0/$metadata) and [public Graph beta metadata](https://graph.microsoft.com/beta/$metadata), inspected on 2026-09-06. Schema evidence is not an operation-support guarantee.
- **A13:** [Official Agent 365 CLI command reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/).
- **A14:** [Invoke-MgGraphRequest](https://learn.microsoft.com/en-us/powershell/module/microsoft.graph.authentication/invoke-mggraphrequest?view=graph-powershell-1.0): generic Graph REST access requires a known URI and applicable permissions.
- **A15:** [agentRegistry resource](https://learn.microsoft.com/en-us/graph/api/resources/agentregistry?view=graph-rest-beta) and [agentCollection resource](https://learn.microsoft.com/en-us/graph/api/resources/agentcollection?view=graph-rest-beta): agent resources, not Registry Sync connections.
- **A16:** [Agent 365 SDK overview](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-sdk) and [official Agent 365 launch announcement](https://www.microsoft.com/en-us/security/blog/2026/05/01/microsoft-agent-365-now-generally-available-expands-capabilities-and-integrations/). Additional targeted public-code discovery included Microsoft SDK/sample repositories and the [external-agent-inventory preflight script](https://github.com/microsoft/frontier-ai-governance-rvas/blob/main/modules/external-agent-inventory/implementation/scripts/preflight.ps1), which validates a local decision record rather than calling a connection-management API.

## Sources: identity, runtime, and lifecycle

These sources describe supported operations and concepts, not evidence that
this tenant has completed the proposed association.

- **I1:** [Agent 365 identity: credential boundaries and permissions](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/identity).
- **I2:** [Create an agent identity blueprint: portal and API prerequisites](https://learn.microsoft.com/en-us/entra/agent-id/create-blueprint).
- **I3:** [Create agentIdentityBlueprint, Graph v1.0](https://learn.microsoft.com/en-us/graph/api/agentidentityblueprint-post?view=graph-rest-1.0).
- **I4:** [Create agentIdentityBlueprintPrincipal, Graph v1.0](https://learn.microsoft.com/en-us/graph/api/agentidentityblueprintprincipal-post?view=graph-rest-1.0).
- **I5:** [Create agentIdentity, Graph v1.0](https://learn.microsoft.com/en-us/graph/api/agentidentity-post?view=graph-rest-1.0) and [agentIdentity properties](https://learn.microsoft.com/en-us/graph/api/resources/agentidentity?view=graph-rest-1.0).
- **I6:** [Agent authentication protocols](https://learn.microsoft.com/en-us/entra/agent-id/agent-oauth-protocols) and [autonomous app flow](https://learn.microsoft.com/en-us/entra/agent-id/agent-autonomous-app-oauth-flow).
- **I7:** [Choose an Agent 365 integration option](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/choose-integration-option) and [connect an existing agent](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/get-started).
- **I8:** [Get agentIdentityBlueprint](https://learn.microsoft.com/en-us/graph/api/agentidentityblueprint-get?view=graph-rest-1.0).
- **I9:** [Get agentIdentity](https://learn.microsoft.com/en-us/graph/api/agentidentity-get?view=graph-rest-1.0).
- **I10:** [Agent identity deletion: cascade behavior and quota](https://learn.microsoft.com/en-us/entra/agent-id/concept-agent-identity-deletion).
- **I11:** [Secure an Amazon Bedrock agent with Microsoft Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/integrate-aws-bedrock-agent). This is a separate application/sidecar sample, not a Registry Sync conversion procedure.
- **I12:** [Get agentIdentityBlueprintPrincipal: object ID and appId addressing](https://learn.microsoft.com/en-us/graph/api/agentidentityblueprintprincipal-get?view=graph-rest-1.0).
- **I13:** [OAuth 2.0 device authorization grant](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code).
- **I14:** [Get the signed-in user](https://learn.microsoft.com/en-us/graph/api/user-get?view=graph-rest-1.0).
- **I15:** [Delete and restore agent identity objects](https://learn.microsoft.com/en-us/entra/agent-id/howto-delete-agent-identity).
- **I16:** [Delete agentIdentity](https://learn.microsoft.com/en-us/graph/api/agentidentity-delete?view=graph-rest-1.0) and [delete agentIdentityBlueprint](https://learn.microsoft.com/en-us/graph/api/agentidentityblueprint-delete?view=graph-rest-1.0): typed operations and least-privileged permissions.

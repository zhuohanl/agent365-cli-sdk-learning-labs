# Lab 20 design decisions

These decisions turn the Lab 20 observations into stable experiment
conventions. They are not Microsoft product contracts and do not establish
that companion registration creation is supported in production.

## Contents

- [DD-001: Registry Sync platform connection names](#dd-001-registry-sync-platform-connection-names)
- [DD-002: Companion source IDs](#dd-002-companion-source-ids)
- [DD-003: Durable relationship mapping](#dd-003-durable-relationship-mapping)
- [DD-004: Add lifecycle](#dd-004-add-lifecycle)
- [DD-005: Delete lifecycle](#dd-005-delete-lifecycle)
- [DD-006: Rename lifecycle](#dd-006-rename-lifecycle)
- [Current boundaries](#current-boundaries)

| ID | Decision | Status |
| --- | --- | --- |
| DD-001 | Use a consistent human-readable name for each Registry Sync platform connection. | Adopted local convention |
| DD-002 | Derive a companion source ID from the exact provider source ID. | Adopted from GCP creation and connection-recreation evidence; production and cross-provider support unresolved |
| DD-003 | Keep a durable source-to-package-to-registration mapping even when the companion source ID is reversible. | Required |
| DD-004 | Add identities through one platform-level Blueprint step followed by a per-Package Agent Identity and companion Registration loop. | Experiment-derived implementation rule; production support unresolved |
| DD-005 | Treat source disappearance as a reconciliation signal and retire the companion Registration before its dedicated Agent Identity. | Experiment-derived implementation rule; production support unresolved |
| DD-006 | Treat a display-name change for the same scoped provider source key as an in-place rename, not delete plus add. | Documented update operations identified; end-to-end rename not yet observed |

## DD-001: Registry Sync platform connection names

Use this display-name format:

```text
<platform>-<env>[-<region>]-<source-scope>
```

The region segment is optional only when region does not apply. An unknown
region must not be treated as not applicable.

| Segment | Rule |
| --- | --- |
| `platform` | Use one controlled lowercase label for the provider, such as `googlevertexai`. Store the canonical Agent 365 platform value separately. |
| `env` | Use a controlled value such as `dev`, `test`, `uat`, or `prod`. Lab 20 remains limited to approved non-production objects. |
| `region` | Use the configured provider region when applicable, such as `us-central1`. |
| `source-scope` | Use a stable project ID, account alias, organization identifier, or workspace identifier. Do not use a mutable display name. |

Synthetic examples:

```text
googlevertexai-dev-us-central1-demo-project
googlevertexai-dev-europe-west1-demo-project
awsbedrock-dev-us-east-1-123456789012
salesforceagentforce-uat-00d000000000000aaa
anthropicclaude-dev-wrk-demo123
```

For Gemini Enterprise Agent Platform, use the project id or a controlled stable
account alias as the source scope.

For AWS Bedrock, use the AWS account ID or a controlled stable account alias
as the source scope.

For Salesforce Agentforce, use the 18-character
organization ID.

For Anthropic Claude Managed Agents, use the dedicated
workspace ID.

AWS and Google connection names include the configured region;
Salesforce and Anthropic connection names omit it because it does not apply
to those connection forms.

Use lowercase letters, digits, and hyphens in the display name. Keep the
actual connection ID, environment, region, and native source-scope identifier
as separate fields. Do not reconstruct authoritative values by splitting the
display name.

The connection name is for operators. It does not prove connection identity,
scope, sync status, Blueprint group membership, or agent ownership. Match an
observed connection by its actual connection ID, scoped by tenant and
platform, when that ID is available.

## DD-002: Companion source IDs

Do not use a random UUID as the complete companion source ID. Derive a stable,
recognizable value from the exact Registry Sync provider source ID:

```text
agent-governance:companion:v1:<platform-code>:<original-source-agent-id>
```

Use these local platform codes:

| Provider family | Platform code |
| --- | --- |
| Google Vertex AI | `gcp` |
| AWS | `aws` |
| Salesforce | `salesforce` |
| Anthropic Claude | `anthropic` |

Synthetic GCP example:

```text
agent-governance:companion:v1:gcp:projects%2fdemo-project%2flocations%2fus-central1%2freasoningEngines%2f123456789
```

The fixed prefix identifies a companion owned by the customer-wide agent
governance capability, `v1` versions the format, and the platform code limits
cross-provider ambiguity. The namespace deliberately does not encode a
committed fleet, rollout wave, or demonstration cohort because those are
selection and delivery concepts rather than the solution's applicability
boundary. Everything after the platform-code separator is the exact provider
source ID observed from Registry Sync.

Preserve that source value byte-for-byte:

- do not URL-decode and re-encode it;
- do not normalize case;
- do not replace slashes, percent escapes, colons, or other provider
  characters;
- let the JSON client serialize it in a request body; and
- apply URL encoding only at an HTTP path or query boundary that requires it.

The same tenant, platform, native scope, and exact source ID must produce the
same companion source ID on every run. If a previously saved value uses
another format, stop for reconciliation rather than silently creating a
second companion.

This format remains part of the experiment. Its acceptance by the Agent
Registration API, including any undocumented character or length limit, must
be observed. Do not automatically retry with a hash after a failure because
that would change more than one experiment variable. If the readable format
is rejected specifically because of length or characters, define a separate
versioned decision such as:

```text
agent-governance:companion:v2:<platform-code>:sha256:<digest>
```

The earlier GCP experiment created one Registration with the legacy
`committed-fleet:companion:v1` prefix. Preserve that exact observed value in
its durable mapping. Do not delete or recreate the Registration solely to
rename the namespace. New companion Registrations use
`agent-governance:companion:v1`.

### Evidence confirming the identity anchor

The GCP stability experiment compared the exact provider source ID, Registry
Sync connection ID, and Package ID across three controlled events:

| Event | Provider source ID | Connection ID | Package ID | Interpretation |
| --- | --- | --- | --- | --- |
| No-change sync | Unchanged | Unchanged | Unchanged | Control only; both identity candidates survived. |
| Provider display-name rename | Unchanged | Unchanged | Unchanged | Rename is metadata-only but does not distinguish the candidates. |
| Delete and recreate the Registry Sync connection while retaining the provider agent | Unchanged | Changed | Changed | The provider source survived rematerialization while the connection and inventory representations did not. |

After connection deletion, the target Package count changed from one to zero.
After connection recreation and a successful sync, exactly one matching target
returned under a new Package ID; the old Package did not remain as a duplicate.

Continue using the DD-002 companion source ID derived from the exact scoped
provider source ID. Do not derive it from either the current Package ID or the
Registry Sync connection ID. Those values remain useful mapping and provenance
fields, but the experiment demonstrated that they can change while the
provider agent remains the same.

This conclusion is evidence-backed only for the tested Google Vertex AI
connection lifecycle. AWS, Salesforce, and Anthropic must each be observed
independently before treating the same stability behavior as cross-provider
fact.

## DD-003: Durable relationship mapping

A reversible companion source ID reduces operator effort, but it does not
replace the mapping journal. The authoritative source key is scoped, not a
display name:

```text
(tenant, platform, native account/project/workspace scope, exact provider source agent ID)
```

Persist at least:

| Field | Purpose |
| --- | --- |
| `platform` | Canonical Agent 365 platform value. |
| `providerSourceAgentId` | Exact provider-native source value observed through Registry Sync. |
| `connectionId` | Registry Sync provenance when exposed; not the agent identity. |
| `packageId` | Current Registry Sync inventory reference; not a Registration ID. |
| `companionSourceAgentId` | Deterministic DD-002 value. |
| `companionRegistrationId` | Addressable ID returned by a successful registration POST. |
| `blueprintId` | Actual Blueprint application ID used by the companion. |
| `agentIdentityId` | Actual Entra Agent Identity object ID used by the companion. |
| `status` | Planned, pending, created, failed, deleted, or reconciliation-required. |
| `lastObservedAt` | Time at which the relationship was last verified. |
| `sourceDisplayName` | Latest non-authoritative display name observed from Registry Sync. |
| `companionDisplayName` | Last display name successfully applied to the companion objects. |

Enforce one active companion per scoped provider source key and one scoped
provider source key per active companion Registration ID. Treat a POST timeout
or unexpected server response as unresolved until reconciled; deterministic
naming is not permission to resend it.

The Package ID remains an observed inventory pointer because Registry Sync may
change or recreate inventory records. The provider source key anchors the
relationship, while the returned Registration ID anchors supported GET,
PATCH, and DELETE operations on the separately managed companion.

## DD-004: Add lifecycle

The add flow has two different levels. Blueprint preparation is
platform-level work. Agent Identity and companion Registration preparation
are per-agent work performed while iterating through individual Registry Sync
Packages.

### Part 1: Prepare the platform Blueprint once

For each configured platform, first resolve the approved platform Blueprint
and its principal. Create them only when the platform has no approved reusable
objects and creation has been explicitly enabled.

Persist the Blueprint object ID, Blueprint app ID, principal ID, platform, and
capacity state. Do not create a new Blueprint for every Package.

A platform-level Blueprint may still need planned sharding when product limits
or customer isolation requirements prevent every platform agent from sharing
one Blueprint. That is a capacity decision within Part 1; it does not move
Blueprint creation into the per-Package loop.

### Parts 2 and 3: Process one Package at a time

Read every page of Registry Sync Package inventory. For each individual
Package:

1. Read Package Details and extract the exact scoped provider source key:
   `(tenant, platform, native account/project/workspace scope,
   providerSourceAgentId)`.
2. Reconcile that key with the durable mapping. A changed Package ID for the
   same source updates the inventory pointer; it does not create another
   identity or companion.
3. Resolve or create one Agent Identity for that source under the platform
   Blueprint, then save its ID before continuing.
4. Resolve the companion state from the journal. If an active Registration ID
   exists, read and verify it instead of creating another Registration.
5. When an approved source has no existing or unresolved companion, create
   exactly one Registration using the DD-002 companion source ID and the
   source's Agent Identity.
6. Save the returned Registration ID immediately, GET that exact ID, and
   verify its source, Blueprint, Agent Identity, owner, and platform fields.
7. Re-read the original Registry Sync Package and confirm that its independent
   inventory record was not assumed to be enriched or replaced.

Serialize writes for each scoped provider source key. A timeout or unexpected
server response after an Agent Identity or Registration create is an unknown
outcome that requires reconciliation; it must not automatically start another
create.

The intended add states are:

```text
package-observed
-> platform-blueprint-resolved
-> agent-identity-resolved
-> companion-create-pending
-> companion-created
-> companion-association-verified
```

The Blueprint state is shared platform preparation. The remaining states are
tracked independently for each Package/source.

### Add flow

This flow follows the rightmost concept in
[`third_party_agent_registry.svg`](third_party_agent_registry.svg): discover
the platforms first, prepare the shared Blueprint at platform scope, and then
loop through each Package to create or resolve the per-agent objects.

All three lifecycle diagrams below use the same regions, so they can be read
against each other:

| Region | Colour | Meaning |
| --- | --- | --- |
| Discovery / detection | Amber | Read-only observation before any decision |
| PART 1 | Blue | Blueprint, platform scope, shared |
| PART 2 | Purple | Agent Identity, one per scoped provider source |
| PART 3 | Green | Companion Registration, one per scoped provider source |
| Loop / gate | Grey | Iteration boundary or approval gate |

```mermaid
%%{init: {"theme":"base","themeVariables":{"background":"#ffffff","primaryColor":"#ffffff","primaryTextColor":"#111827","primaryBorderColor":"#334155","secondaryColor":"#ffffff","tertiaryColor":"#ffffff","lineColor":"#334155","textColor":"#111827","clusterBkg":"#ffffff","clusterBorder":"#334155","titleColor":"#111827","edgeLabelBackground":"#ffffff","fontSize":"16px"}}}%%
flowchart TB
    subgraph DISCOVERY["<b>DISCOVERY</b> - read only"]
        direction TB
        A1["Read every<br/>Package List page"]
        A2["Group Packages<br/>by platform"]
        A1 --> A2
    end

    subgraph PART1["<b>PART 1: BLUEPRINT</b> - once per platform"]
        direction TB
        B1{"Approved platform<br/>Blueprint exists?"}
        B2["Create one approved<br/>platform Blueprint"]
        B3["Blueprint ID<br/>shared by the platform"]
        B1 -->|No| B2
        B2 --> B3
        B1 -->|Yes| B3
    end

    subgraph LOOP["<b>FOR EACH PACKAGE</b> in the platform - repeat Parts 2 and 3"]
        direction TB
        C1["Read Package Details"]
        C2["Companion source ID<br/>built from the exact scoped<br/>provider sourceAgentId"]
        C1 --> C2

        subgraph PART2["<b>PART 2: AGENT IDENTITY</b> - one per source"]
            direction TB
            D1{"Identity already<br/>mapped?"}
            D2["Create Agent Identity<br/>under the platform Blueprint"]
            D3["Agent Identity ID"]
            D1 -->|No| D2
            D2 --> D3
            D1 -->|Yes| D3
        end

        subgraph PART3["<b>PART 3: COMPANION REGISTRATION</b> - one per source"]
            direction TB
            E0["Registration POST needs<br/>all three inputs together"]
            E1{"Companion already<br/>recorded?"}
            E2["Reconcile the recorded<br/>outcome, create nothing"]
            E3["POST one companion<br/>Registration"]
            E4["Registration ID"]
            E0 --> E1
            E1 -->|Yes| E2
            E1 -->|No| E3
            E3 --> E4
        end

        F1["Persist the mapping:<br/>source, Package, Blueprint,<br/>Identity, Registration"]
        F2["Re-read the original<br/>Registry Sync Package"]
        E2 --> F1
        E4 --> F1
        F1 --> F2
    end

    A2 --> B1
    B3 --> C1
    C2 --> D1
    B3 -.->|"input 1: Blueprint ID"| E0
    D3 -->|"input 2: Agent Identity ID"| E0
    C2 -.->|"input 3: companion source ID"| E0
    F2 --> G1["Finish when every Package<br/>and platform is reconciled"]

    style DISCOVERY fill:#fdf3e3,stroke:#b45309,stroke-width:3px,color:#7c2d12
    style PART1 fill:#e8f1fd,stroke:#1d4ed8,stroke-width:4px,color:#1e3a8a
    style PART2 fill:#f3ecfd,stroke:#6d28d9,stroke-width:4px,color:#4c1d95
    style PART3 fill:#e7f8f0,stroke:#047857,stroke-width:4px,color:#064e3b
    style LOOP fill:#f8fafc,stroke:#475569,stroke-width:3px,color:#1e293b
```

The three dotted and solid inputs into Part 3 are the point of the diagram: a
companion Registration POST is only possible once the platform Blueprint ID
from Part 1, the Agent Identity ID from Part 2, and the deterministic companion
source ID derived from the exact scoped provider `sourceAgentId` all exist for
the same source.

Part 1 is shared preparation performed once for each platform. The outer
Package loop then runs Parts 2 and 3 separately for each scoped provider
source. That loop owns one mapping entry, one Agent Identity, and one companion
Registration per source; it reuses the platform Blueprint prepared in Part 1.

## DD-005: Delete lifecycle

Automatic Package disappearance must not automatically delete a companion
Registration or Agent Identity. Registry Sync inventory may be incomplete
because of pagination, propagation delay, connector failure, permissions, or
Package recreation.

Use this reconciliation sequence:

1. Read every page of the latest Package List and match by the DD-003 scoped
   provider source key, not only by the last Package ID or display name.
2. If the previous Package ID is absent but the same provider source key has a
   new Package ID, update the mapping and retain the companion objects.
3. If the source key is absent, mark it `source-missing-candidate`; do not
   delete anything.
4. Confirm that Registry Sync completed successfully and allow the configured
   propagation/grace period. Where available, also confirm through the
   provider that the source agent was deleted. Without adequate confirmation,
   leave the mapping `reconciliation-required`.
5. Lock the source mapping and read the mapped companion Registration, Agent
   Identity, and Blueprint. Verify that they belong to the expected source and
   identify any runtime, authorization, registration, or other mapping
   dependents.
6. After explicit retirement approval, DELETE the known companion Registration
   ID first. GET the same ID and require `404`, then re-read Package inventory
   and the original Package independently. Do not assume Registration deletion
   automatically removes a catalog record.
7. Delete the Agent Identity only under separate approval, and only when it
   was created for this source and no remaining Registration, runtime binding,
   grant, policy, or other consumer depends on it.
8. Retain the platform Blueprint unless its own separately approved retirement
   process proves that it is no longer shared or needed. Blueprint deletion is
   not normal per-agent cleanup.
9. Preserve a tombstone in the durable mapping with the source key, former
   object IDs, deletion reason, timestamps, and final outcomes. The tombstone
   prevents stale inventory from silently creating a replacement companion.

The intended delete states are:

```text
active
-> source-missing-candidate
-> source-deletion-confirmed
-> companion-retirement-approved
-> registration-deleted
-> identity-deleted
-> tombstoned
```

If Registration deletion succeeds but Agent Identity cleanup is blocked or
fails, record that partial state and retry only the identity cleanup according
to its documented semantics. Do not recreate the Registration as recovery.

### Delete flow

The three parts are read top to bottom in the same order as the add flow. The
write order is deliberately the reverse: the companion Registration is always
deleted before the Agent Identity, and the platform Blueprint is never part of
per-agent cleanup. The ordered execution block at the bottom carries that
constraint.

```mermaid
%%{init: {"theme":"base","themeVariables":{"background":"#ffffff","primaryColor":"#ffffff","primaryTextColor":"#111827","primaryBorderColor":"#334155","secondaryColor":"#ffffff","tertiaryColor":"#ffffff","lineColor":"#334155","textColor":"#111827","clusterBkg":"#ffffff","clusterBorder":"#334155","titleColor":"#111827","edgeLabelBackground":"#ffffff","fontSize":"16px"}}}%%
flowchart TB
    subgraph DETECT["<b>DETECTION</b> - read only"]
        direction TB
        A1["Refresh every<br/>Package List page"]
        A2{"Scoped provider<br/>source key still<br/>present?"}
        A3["Same Package ID:<br/>keep companion,<br/>refresh state"]
        A4["New Package ID:<br/>update the Package<br/>pointer only"]
        A5["Mark<br/>source-missing-candidate"]
        A1 --> A2
        A2 -->|Yes, same Package ID| A3
        A2 -->|Yes, new Package ID| A4
        A2 -->|No| A5
    end

    subgraph GATE["<b>CONFIRMATION GATE</b> - nothing is deleted yet"]
        direction TB
        B1{"Provider deletion,<br/>healthy sync, and<br/>grace period all<br/>confirmed?"}
        B2["Mark reconciliation-required<br/>and stop"]
        B3["Lock mapping; read<br/>Registration, Identity,<br/>and dependents"]
        B1 -->|No| B2
        B1 -->|Yes| B3
    end

    subgraph PART1["<b>PART 1: BLUEPRINT</b> - retained"]
        direction TB
        C1["Shared platform scope:<br/>retain the Blueprint and<br/>exclude it from cleanup"]
    end

    subgraph PART2["<b>PART 2: AGENT IDENTITY</b> - decide disposition"]
        direction TB
        D1{"Dedicated to this source,<br/>no remaining consumers,<br/>separately approved?"}
        D2["Plan: retain the<br/>Agent Identity"]
        D3["Plan: delete the<br/>Agent Identity"]
        D1 -->|No| D2
        D1 -->|Yes| D3
    end

    subgraph PART3["<b>PART 3: COMPANION REGISTRATION</b> - decide retirement"]
        direction TB
        E1{"Registration retirement<br/>approved?"}
        E2["Plan: delete the mapped<br/>companion Registration"]
        E3["Mark reconciliation-required<br/>and stop"]
        E1 -->|Yes| E2
        E1 -->|No| E3
    end

    subgraph EXEC["<b>ORDERED EXECUTION</b> - Registration before Identity"]
        direction TB
        F1["Step 1: DELETE the mapped<br/>companion Registration"]
        F2["Step 2: GET the Registration<br/>and require 404"]
        F3["Step 3: re-read Package<br/>inventory independently"]
        F4{"Identity deletion<br/>planned?"}
        F5["Record registration-deleted,<br/>identity-retained"]
        F6["Step 4: DELETE the<br/>dedicated Agent Identity"]
        F7["Step 5: GET the Identity<br/>and require 404"]
        F8["Step 6: write the<br/>durable tombstone"]
        F1 --> F2
        F2 --> F3
        F3 --> F4
        F4 -->|No| F5
        F4 -->|Yes| F6
        F6 --> F7
        F5 --> F8
        F7 --> F8
    end

    A5 --> B1
    B3 --> C1
    C1 --> D1
    D2 --> E1
    D3 --> E1
    E2 --> F1

    style DETECT fill:#fdf3e3,stroke:#b45309,stroke-width:3px,color:#7c2d12
    style GATE fill:#f8fafc,stroke:#475569,stroke-width:3px,color:#1e293b
    style PART1 fill:#e8f1fd,stroke:#1d4ed8,stroke-width:4px,color:#1e3a8a
    style PART2 fill:#f3ecfd,stroke:#6d28d9,stroke-width:4px,color:#4c1d95
    style PART3 fill:#e7f8f0,stroke:#047857,stroke-width:4px,color:#064e3b
    style EXEC fill:#fdeaea,stroke:#b91c1c,stroke-width:3px,color:#7f1d1d
```

The destructive path uses only IDs recovered from the locked mapping.
Registration deletion always precedes Agent Identity deletion. The shared
platform Blueprint is not part of per-agent cleanup.

## DD-006: Rename lifecycle

A provider-side display-name change does not change the agent's identity when
the DD-003 scoped provider source key remains exactly the same. Rename is an
in-place metadata update. It must not create a new Blueprint, Agent Identity,
or companion Registration.

Use this reconciliation sequence:

1. Read every Package List page and the selected Package Details.
2. Match the Package to the existing mapping using the exact scoped provider
   source key. Do not match by display name.
3. If the source key is unchanged and only the Package/provider display name
   changed, record `rename-observed` and update `sourceDisplayName`.
4. Keep the existing platform Blueprint, Agent Identity ID, companion source
   ID, and companion Registration ID.
5. Calculate the intended companion display name from the new source display
   name and the companion display-name convention. Do not reconstruct or
   modify the companion source ID.
6. GET the mapped Agent Identity and companion Registration and verify their
   IDs, Blueprint relationship, source relationship, and ownership before
   changing either object.
7. PATCH the Agent Identity `displayName` through its typed v1.0 endpoint and
   PATCH the known companion Registration `displayName` through its beta
   endpoint. The Registration update can also carry the newly observed
   `sourceLastModifiedDateTime` when that provider value is available and has
   been preserved exactly.
8. GET both objects again and require the intended names. Update
   `companionDisplayName`, rename timestamps, and final status in the mapping.
9. Re-read Package inventory and the original Package independently. Observe
   whether the companion Package representation follows the Registration
   rename; do not assume that propagation is immediate. The original Package's
   display name remains owned by Registry Sync, so do not PATCH it to force
   alignment.

The rename writes are separate operations, not a transaction. Persist the
result after each successful PATCH. If only one update succeeds, record
`rename-partial` and retry only the incomplete PATCH after reading both
objects again. Do not delete and recreate either object as rename recovery.

Do not change `sourceAgentId`, `originatingStore`, Blueprint IDs, Agent
Identity IDs, owners, grants, or runtime configuration as part of a display
name rename.

The intended rename states are:

```text
active
-> rename-observed
-> rename-update-pending
-> rename-partial
-> rename-verified
-> active
```

`rename-partial` is used only when one of the two independently persisted name
updates remains incomplete; a fully successful run can move directly from
`rename-update-pending` to `rename-verified`.

If the provider source ID or native scope changes as well as the display name,
do not classify the event as a rename. Leave both records
`reconciliation-required` until provider-specific evidence proves whether this
is a source migration, a replacement agent, or a delete followed by an add.

The current documented write operations are:

| Object | Operation | Expected success |
| --- | --- | --- |
| Agent Identity | [`PATCH /v1.0/servicePrincipals/{id}/microsoft.graph.agentIdentity`](https://learn.microsoft.com/graph/api/agentidentity-update?view=graph-rest-1.0) with `displayName` | `204 No Content` |
| Companion Registration | [`PATCH /beta/copilot/agentRegistrations/{id}`](https://learn.microsoft.com/microsoft-365/copilot/extensibility/api/admin-settings/agent-registration/agentregistration-update) with `displayName` and, when applicable, `sourceLastModifiedDateTime` | `200 OK` |

The Registration operation remains a beta interface that Microsoft does not
support for production applications. Its rename behavior and Package
propagation must be established in a bounded experiment before automation.

### Rename flow

Rename reads the same three parts top to bottom. Part 1 is a confirmation
checkpoint with no write; only Parts 2 and 3 change a display name.

```mermaid
%%{init: {"theme":"base","themeVariables":{"background":"#ffffff","primaryColor":"#ffffff","primaryTextColor":"#111827","primaryBorderColor":"#334155","secondaryColor":"#ffffff","tertiaryColor":"#ffffff","lineColor":"#334155","textColor":"#111827","clusterBkg":"#ffffff","clusterBorder":"#334155","titleColor":"#111827","edgeLabelBackground":"#ffffff","fontSize":"16px"}}}%%
flowchart TB
    subgraph DETECT["<b>DETECTION</b> - read only"]
        direction TB
        A1["Capture the Package<br/>and mapped objects"]
        A2["Rename only the disposable<br/>provider agent"]
        A3["Wait for healthy sync<br/>and propagation"]
        A4["Read Package List pages<br/>and Package Details"]
        A5{"Old and new Package<br/>records coexist?"}
        A6["Stop for duplication<br/>reconciliation"]
        A7{"Provider scope and exact<br/>sourceAgentId unchanged?"}
        A8["Mark reconciliation-required:<br/>migration or replacement"]
        A9["Update the Package pointer<br/>only if the Package ID changed"]
        A1 --> A2
        A2 --> A3
        A3 --> A4
        A4 --> A5
        A5 -->|Yes| A6
        A5 -->|No| A7
        A7 -->|No| A8
        A7 -->|Yes| A9
    end

    subgraph GATE["<b>VERIFICATION GATE</b> - nothing is written yet"]
        direction TB
        B1["GET the mapped Agent Identity<br/>and companion Registration"]
        B2{"Display-name update<br/>approved?"}
        B3["Keep both companion<br/>objects unchanged"]
        B1 --> B2
        B2 -->|No| B3
    end

    subgraph PART1["<b>PART 1: BLUEPRINT</b> - no write"]
        direction TB
        C1["Confirm the Blueprint and<br/>every identifier are unchanged"]
    end

    subgraph PART2["<b>PART 2: AGENT IDENTITY</b> - rename"]
        direction TB
        D1["PATCH the Agent Identity<br/>displayName"]
        D2["GET and verify the same<br/>Identity and Blueprint IDs"]
        D1 --> D2
    end

    subgraph PART3["<b>PART 3: COMPANION REGISTRATION</b> - rename"]
        direction TB
        E1["PATCH the Registration<br/>displayName"]
        E2["GET and verify the same<br/>Registration, source,<br/>Blueprint, and Identity IDs"]
        E1 --> E2
    end

    A9 --> B1
    B2 -->|Yes| C1
    C1 --> D1
    D2 --> E1
    E2 --> F1["Re-read Package inventory<br/>and observe propagation"]
    F1 --> F2["Persist the rename result<br/>in the durable mapping"]

    style DETECT fill:#fdf3e3,stroke:#b45309,stroke-width:3px,color:#7c2d12
    style GATE fill:#f8fafc,stroke:#475569,stroke-width:3px,color:#1e293b
    style PART1 fill:#e8f1fd,stroke:#1d4ed8,stroke-width:4px,color:#1e3a8a
    style PART2 fill:#f3ecfd,stroke:#6d28d9,stroke-width:4px,color:#4c1d95
    style PART3 fill:#e7f8f0,stroke:#047857,stroke-width:4px,color:#064e3b
```

No PATCH, POST, or DELETE is allowed on the default observation path until
the exact scoped provider source key is proven unchanged. A source-key change
is not treated as a cosmetic rename.

## Current boundaries

- A Registry Sync Package does not expose a documented Registration ID lookup.
- A same-source registration POST currently returns a backend permission
  denial for the sampled GCP records.
- One GCP fresh-companion POST using the DD-002 source ID returned `201`, and
  GET by the returned Registration ID succeeded.
- Recreating the tested GCP Registry Sync connection retained the exact
  provider source ID but produced a different connection ID and Package ID.
  The restored inventory contained exactly one matching target.
- The original Registry Sync Package remained unchanged after that create.
- A successful companion does not enrich the original Registry Sync Package
  or prove provider-runtime authentication or governance enforcement.
- Registry Sync connection creation and complete connection-detail retrieval
  remain manual or unavailable through the reviewed public interfaces.
- The add and delete flows above are implementation handling decisions derived
  from the experiment. They are not documented Microsoft lifecycle contracts.
- Microsoft documents `displayName` updates for both Agent Identity and Agent
  Registration, but Lab 20 has not yet run an end-to-end provider rename and
  companion-name reconciliation.

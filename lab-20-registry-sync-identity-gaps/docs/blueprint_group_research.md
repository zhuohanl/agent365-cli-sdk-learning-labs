# Registry Sync Blueprint grouping research

Research date: 2026-09-12.

This report determines useful Blueprint grouping inputs for Registry Sync
agents from Google Cloud, AWS, Salesforce Agentforce, and Anthropic Claude
Managed Agents. It refines, but does not replace, the lifecycle decisions in
[`design-decisions.md`](design-decisions.md).

This is a research recommendation. It is not authorization to create Entra
objects, and it does not establish that companion registrations are supported
for production.

## Contents

- [Executive recommendation](#executive-recommendation)
- [Relationship to the Lab 20 design](#relationship-to-the-lab-20-design)
- [What the identifiers mean](#what-the-identifiers-mean)
- [Runtime credential isolation comparison](#runtime-credential-isolation-comparison)
- [Google Cloud](#google-cloud)
  - [Active offering classification](#active-offering-classification)
  - [Runtime identity and credential isolation](#runtime-identity-and-credential-isolation)
  - [What does not change the offering classification](#what-does-not-change-the-offering-classification)
  - [Offerings not yet covered by the active mapping](#offerings-not-yet-covered-by-the-active-mapping)
- [AWS](#aws)
  - [Bedrock Agents Classic](#bedrock-agents-classic)
  - [AgentCore Runtime](#agentcore-runtime)
  - [AgentCore managed harness](#agentcore-managed-harness)
  - [Amazon Q](#amazon-q)
- [Salesforce Agentforce](#salesforce-agentforce)
  - [Runtime and outbound credential model](#runtime-and-outbound-credential-model)
- [Anthropic Claude Managed Agents](#anthropic-claude-managed-agents)
  - [Runtime and credential isolation](#runtime-and-credential-isolation)
- [How offering keys relate to Blueprint assignment](#how-offering-keys-relate-to-blueprint-assignment)
- [Can Package List reveal a Blueprint ID?](#can-package-list-reveal-a-blueprint-id)
  - [Short answer](#short-answer)
  - [Documented resolution paths](#documented-resolution-paths)
- [Microsoft-native examples](#microsoft-native-examples)
  - [Copilot Studio](#copilot-studio)
  - [Microsoft Foundry](#microsoft-foundry)
- [Observed tenant Blueprint inventory](#observed-tenant-blueprint-inventory)
  - [Interpretation of the observed Microsoft patterns](#interpretation-of-the-observed-microsoft-patterns)
  - [Public documentation corroboration and scope](#public-documentation-corroboration-and-scope)
- [Required validation before implementation](#required-validation-before-implementation)
- [Final decision](#final-decision)

## Executive recommendation

**Do not use one Blueprint per cloud vendor as an automatic rule.**

Microsoft defines a Blueprint as a credential boundary. Credentials and
inherited baseline permissions are shared by the Agent Identities created
from that Blueprint. Microsoft therefore recommends one Blueprint per
credential boundary, shared only by agents that can safely share those
credentials and permissions.

Source:
[Microsoft Agent 365 identity](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/identity#credentials).

Use two separate layers:

1. Classify each source into a stable **offering key** based on the provider
   service that owns the deployable agent.
2. Create a dedicated companion Blueprint for each source unless an
   authoritative shared assignment already exists before provisioning.

Registry Sync package metadata does not currently provide an authoritative
runtime trust-group claim for any of the four providers. The automatic
companion path therefore must not infer shared Blueprint membership from
platform, account, project, connection, environment, team, framework, or
display name.

The recommended starting offering catalog is:

| Provider | Candidate offering key | Current recommendation |
| --- | --- | --- |
| Google Cloud | `gcp-agent-runtime` | Covers Agent Runtime on Gemini Enterprise Agent Platform, formerly Vertex AI Agent Engine. Use a dedicated companion Blueprint by default. |
| AWS | `aws-bedrock-agents-classic` | Retain as a distinct legacy offering classification. Public documentation does not establish a universal execution-role sharing default. |
| AWS | `aws-agentcore-runtime` | Covers code-defined agents deployed to AgentCore Runtime. Each Runtime gets a workload identity, but execution roles remain configurable; use a dedicated companion Blueprint by default. |
| AWS | `aws-agentcore-harness` | Covers configuration-defined agents using the managed AgentCore harness. Do not infer credential sharing from the harness type. |
| Salesforce | `salesforce-agentforce` | One initial offering classification; runtime user and outbound credential sharing are configurable, so use a dedicated companion Blueprint by default. |
| Anthropic | `anthropic-claude-managed-agents` | Covers durable Claude Managed Agent definitions, not sessions. Public documentation does not establish a durable per-agent authentication principal; use a dedicated companion Blueprint by default. |

These six keys are local classifications. They are not Microsoft-issued
Blueprint IDs, do not prove Registry Sync cardinality, and do not prescribe
exactly six Entra Blueprint objects.

The practical automatic-provisioning model is:

```text
provider platform
-> offering classification
-> one dedicated Entra Blueprint application per scoped provider source
-> one Agent Identity per scoped provider source
-> one companion Registration per scoped provider source
```

A shared Blueprint remains possible only through a separate explicit
onboarding path that identifies all members before any of their companion
identities are created. It is not a blocking decision point in the automatic
Registry Sync path.

## Relationship to the Lab 20 design

The following existing decisions remain valid:

- The companion source ID is derived from the exact provider source ID.
- Package ID and Registry Sync connection ID are provenance and inventory
  pointers, not the durable agent identity.
- One active companion Registration maps to one scoped provider source.
- Blueprint preparation occurs outside the per-source loop.
- Agent Identity and companion Registration reconciliation occurs once for
  each scoped provider source.

DD-004 records Blueprint assignment and grouping as its own decision. The
provider evidence below narrows the safe automatic behavior: a source that
does not already belong to an explicitly approved shared onboarding set
should receive a dedicated Blueprint rather than waiting for a grouping
decision.

A platform or offering may contain multiple Blueprint groups, but platform
metadata cannot establish their membership. Shared groups remain an explicit
exception handled outside the automatic Registry Sync path.

## What the identifiers mean

| Value | Meaning |
| --- | --- |
| Provider family | The existing `gcp`, `aws`, `salesforce`, or `anthropic` namespace used in companion source IDs. |
| Offering key | Local classification of the provider service or control plane that owns the deployable agent. |
| `blueprintGroup` | Customer-defined policy label for sources approved to share a Blueprint boundary. |
| Blueprint application ID | The Entra Blueprint `appId`; this is the parent identifier stored by an Agent Identity. |
| Blueprint object ID | The Entra application object's `id`; it is different from `appId`. |
| Blueprint principal ID | The tenant-local Blueprint service-principal object ID. |
| Agent Identity ID | The per-source Entra Agent Identity object ID. |
| Companion Registration ID | The ID returned by the separately managed Agent Registration. |

Microsoft documents that one Blueprint can create many Agent Identities and
that Blueprint credentials are shared by those identities:

- [Agent 365 identity](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/identity)
- [Agent identity Blueprint resource](https://learn.microsoft.com/en-us/graph/api/resources/agentidentityblueprint?view=graph-rest-1.0)
- [Agent Identity resource](https://learn.microsoft.com/en-us/graph/api/resources/agentidentity?view=graph-rest-1.0)

`blueprintGroup` is therefore a local policy concept. It is not a property
returned by Package Details, a Microsoft 365 group, or a Graph resource that
can be resolved by name.

A useful conceptual key for an explicitly approved shared group is:

```text
(tenant, credentialController, authenticationMaterial,
 sharedAccessBoundary, trustBoundary, shard)
```

The actual label may be simpler, but its approved policy record should retain
those decisions.

Illustrative labels:

```text
gcp-agent-runtime-customer-support-s01
aws-agentcore-runtime-claims-processing-s01
salesforce-agentforce-service-operations-s01
anthropic-claude-managed-agents-research-s01
```

These examples are not Microsoft identifiers.

## Runtime credential isolation comparison

This comparison concerns the source agent's runtime identity and outbound
credentials. It does not concern the credential used by the Microsoft Agent
365 Registry Sync connector to inventory the provider.

| Platform or offering | Documented runtime identity or credential behavior | Evidence confidence | Automatic companion Blueprint default |
| --- | --- | --- | --- |
| GCP Agent Studio or Agent Runtime with Google Agent Identity | Each deployed Agent Runtime has a unique SPIFFE identity tied to its `reasoningEngines` resource. Google states that Agent Identities are not shared by multiple workloads by default. | High | Dedicated |
| GCP Agent Runtime using shared service-account behavior | A Google-managed service agent or customer-selected service account can authorize multiple workloads. The exact arrangement is deployment-specific. | High for the mechanism; sharing scope is customer-specific | Dedicated unless an explicit shared onboarding set exists |
| AWS Bedrock Agents Classic | Each agent is associated with an execution service role, but AWS allows an existing role to be selected. Public documentation does not establish whether customers normally use one role per agent or reuse roles. | High for the mechanism; default unresolved | Dedicated |
| AWS AgentCore Runtime | Runtime deployment automatically creates a workload identity. The deployment also requires an IAM execution role, which can be reused or separated by the customer. | High | Dedicated |
| AWS AgentCore managed harness | The harness is deployed with an explicitly supplied execution role and runs on AgentCore Runtime. Public documentation does not establish a universal role-sharing default. | High for the mechanism; default unresolved | Dedicated |
| Salesforce Agentforce | Execution can use the agent-assigned user or the token-associated user. Outbound Named Credentials can use a shared named principal or per-user principals. A universal per-agent credential default is not documented. | High for the mechanisms; default unresolved | Dedicated |
| Anthropic Claude Managed Agents | Each cloud session receives an isolated sandbox, while environments and vault-backed outbound credentials can be reused. Public documentation does not establish a durable, unique authentication principal per managed-agent definition. | High for session isolation; durable agent identity unresolved | Dedicated |

Across all four providers, the available Registry Sync metadata does not
establish a safe shared-credential group. A provider may support either
isolated or shared runtime authorities, but that configurability is not an
authoritative instruction to share an additional Entra Blueprint.

## Google Cloud

### Active offering classification

Use:

```text
gcp-agent-runtime
```

Google renamed **Vertex AI Agent Engine** to **Agent Runtime on Gemini
Enterprise Agent Platform**. The deployed-agent resource continues to use the
`reasoningEngines` resource family. Microsoft's Registry Sync connector is
still named **Google Vertex AI** and requests these permissions:

```text
aiplatform.reasoningEngines.list
aiplatform.reasoningEngines.get
aiplatform.reasoningEngines.delete
```

This establishes a direct correspondence between the current Microsoft
connector and Agent Runtime resources.

Sources:

- [Google: Gemini Enterprise Agent Platform name changes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/vertex-ai-name-changes)
- [Google: Manage deployed agents](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/manage-deployed-agents)
- [Microsoft: Google Vertex AI connected platform](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/connected-platforms#google-vertex-ai)

### Runtime identity and credential isolation

Agent Studio, ADK, Agents CLI, SDK, source, and container deployment are
different authoring or deployment paths to Agent Runtime. Once deployed, the
managed resource remains a `reasoningEngines` resource; the authoring path
does not create a separate identity model or justify a separate offering key.

When Google Agent Identity is enabled, each Agent Runtime receives a unique
SPIFFE-formatted principal tied to the exact project, location, and
`reasoningEngines` resource:

```text
principal://agents.global.org-<organization-id>.system.id.goog/
resources/aiplatform/projects/<project-number>/locations/<location>/
reasoningEngines/<agent-engine-id>
```

Google states that these Agent Identities are not shared by multiple
workloads by default, cannot be impersonated, and use automatically managed
X.509 credentials. Agent Studio also exposes a unique identity for each saved
agent and uses the same `reasoningEngines` identity format.

This is strong evidence against a platform-wide shared companion Blueprint.
For Agent Runtime sources using Google Agent Identity, preserve the
source-level isolation with one dedicated companion Blueprint per scoped
`reasoningEngines` source.

Google also documents service-account-based runtime access. A Google-managed
service agent or a customer-selected service account can authorize multiple
workloads, so older or explicitly configured deployments may share a GCP
runtime authority. That fact does not establish that the same workloads
should share an Entra Blueprint: the Registry Sync Package does not
authoritatively expose the runtime credential relationship, and sharing an
additional Entra credential would increase the Microsoft-side blast radius.

Sources:

- [Google: Agent Identity overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview)
- [Google: Use Agent Identity with Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-identity)
- [Google: Design agents in Agent Studio](https://docs.cloud.google.com/gemini-enterprise-agent-platform/agent-studio/design-agents)
- [Google: Set up Agent Runtime identity and permissions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/setup)

### What does not change the offering classification

- The framework used to build an agent, such as ADK, does not by itself create
  a different offering when the agent is deployed through the same Agent
  Runtime service.
- Registering the same deployed ADK agent in Gemini Enterprise does not create
  another runtime resource. Google states that Agent Runtime processes the
  registered agent's queries and uses the existing `reasoningEngines`
  resource.
- Project, region, and Registry Sync connection remain important scope and
  provenance fields, but they neither create another offering classification
  nor prove that separate sources can share a Blueprint.

Source:
[Google: Register and manage an ADK agent](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent).

### Offerings not yet covered by the active mapping

Keep these outside the current automatic mapping until Microsoft documents
support or Package evidence proves that Registry Sync imports them:

| Google offering | Treatment |
| --- | --- |
| Gemini Enterprise Workflow Builder agents | Candidate future offering classification. Do not assume `reasoningEngines` coverage. |
| Managed Agents API on Gemini Enterprise Agent Platform | Candidate separate control-plane classification. Do not assume it is covered by the current Google Vertex AI connector. |
| Google-provided or gallery agents | Do not create companion identities unless Registry Sync exposes them as independently governed source agents. |

Sources:

- [Google: Gemini Enterprise agents overview](https://docs.cloud.google.com/gemini/enterprise/docs/agents-overview)
- [Google: Workflow Builder](https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder)
- [Google: Managed Agents API](https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/managed-agents)

## AWS

Microsoft's Amazon Bedrock connector now explicitly covers both traditional
Bedrock agent resources and AgentCore harnesses and runtimes. AWS therefore
needs more than one offering classification.

Source:
[Microsoft: Amazon Bedrock connected platform](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/connected-platforms#amazon-bedrock).

### Bedrock Agents Classic

Use:

```text
aws-bedrock-agents-classic
```

AWS renamed the original service **Amazon Bedrock Agents Classic**. It is no
longer open to new customers as of July 30, 2026, but existing agents remain
relevant to inventory and governance.

Classic has agent, version, and alias resources. An alias points to a version
for deployment. Those subordinate resources do not automatically require a
Blueprint each.

Sources:

- [AWS: Bedrock Agents Classic maintenance mode](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-classic-maintenance-mode.html)
- [AWS: Deploy an agent with an alias](https://docs.aws.amazon.com/bedrock/latest/userguide/deploy-agent.html)
- [AWS: Create and configure a Bedrock agent](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-create.html)
- [AWS: Bedrock agent service-role permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-permissions.html)

Bedrock Agents Classic associates an execution service role with the agent.
The console can create a role or use an existing role, so the mechanism allows
either per-agent roles or role reuse. Public documentation does not establish
a universal default across customer deployments. An AWS account, agent type,
version, or alias therefore cannot be used to infer shared credentials.

Use a dedicated companion Blueprint for automatic provisioning. A shared
execution role is relevant evidence for a separately approved shared
onboarding set, but it is not sufficient by itself: sharing an additional
Entra credential still expands the Microsoft-side compromise boundary.

### AgentCore Runtime

Use:

```text
aws-agentcore-runtime
```

This classification covers code-defined agent deployments where the
developer owns the orchestration loop and deploys it to AgentCore Runtime.
AgentCore Runtime also hosts tools, so not every returned runtime resource
should automatically be treated as an agent. Package evidence must establish
what Microsoft Registry Sync represents as a source agent.

Sources:

- [AWS: Host agents and tools with AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)
- [AWS: Runtime versions and endpoints](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agent-runtime-versioning.html)
- [AWS: Understanding AgentCore workload identities](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/understanding-agent-identities.html)
- [AWS: CreateAgentRuntime API](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateAgentRuntime.html)

AgentCore Runtime automatically creates and associates a workload identity
with each deployed Runtime. The `CreateAgentRuntime` request separately
requires a `roleArn` that supplies AWS permissions. The workload identity is
therefore per Runtime, while the execution role can be unique or reused
according to customer configuration.

AWS also supports AgentCore Runtime Instances that can host multiple agents.
AWS documents that agents colocated on one instance do not have a security
boundary between them and must be mutually trusted. This is an explicit
deployment choice, not a reason to group separately isolated Runtime
resources.

The safe automatic companion default remains dedicated. Registry Sync would
need authoritative runtime, workload-identity, execution-role, and isolation
information before any shared Entra Blueprint could be evaluated.

Sources:

- [AWS: Manage credentials in AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/security-credentials-management.html)
- [AWS: Scope credential-provider access](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/scope-credential-provider-access.html)
- [AWS: Runtime Instances security](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-instances-security.html)

### AgentCore managed harness

Use:

```text
aws-agentcore-harness
```

The AgentCore harness provides the orchestration loop, while a code-defined
Runtime deployment owns its orchestration. AWS and Microsoft both expose
harness and Runtime concepts separately, so preserve the distinction in the
offering catalog.

Sources:

- [AWS: Harness compared with Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-vs-runtime.html)
- [Microsoft: Amazon Bedrock connected platform](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/connected-platforms#amazon-bedrock)

Harness creation supplies an `executionRoleArn`, and the harness runs through
AgentCore Runtime. Public documentation does not establish that every harness
receives a unique role or that customers normally reuse one. The managed
orchestration loop therefore does not establish a different credential
sharing rule from AgentCore Runtime.

Sources:

- [AWS: AgentCore harness security](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-security.html)
- [AWS: CreateHarness API](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_CreateHarness.html)

Before provisioning companions, observe whether Registry Sync represents a
harness and its backing Runtime as one source or multiple sources. The
durable provider source ID, rather than the offering key, remains the
one-to-one companion anchor.

### Amazon Q

Do not add Amazon Q Business or Amazon Q Developer to the current Blueprint
mapping merely because they are AWS products.

Amazon Q uses different product and resource abstractions. A Q Developer
channel can invoke an existing Bedrock agent alias, but that integration
surface is not another deployment identity for the Bedrock agent. Microsoft's
current Amazon Bedrock connector documentation does not establish Amazon Q
inventory coverage.

Sources:

- [AWS: Amazon Q Business concepts](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/concepts-terms.html)
- [AWS: Amazon Q Developer overview](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/what-is.html)
- [AWS: Invoke Bedrock agents from Amazon Q Developer chat](https://docs.aws.amazon.com/chatbot/latest/adminguide/connect-bedrock-agents.html)

## Salesforce Agentforce

Use the initial offering classification:

```text
salesforce-agentforce
```

Microsoft documents one Salesforce Agentforce connected-platform integration,
authenticated through a Salesforce domain, OAuth client credentials, and an
API-enabled run-as user. The public connector documentation does not define
separate Registry Sync contracts for each Agentforce template.

Source:
[Microsoft: Salesforce Agentforce connected platform](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/connected-platforms#salesforce-agentforce).

Salesforce exposes several agent types or templates, including:

- Agentforce Service Agent
- Agentforce Employee Agent
- Agentforce Engagement
- Agentforce Sales Coach

Sources:

- [Salesforce: Agentforce APIs and SDKs](https://developer.salesforce.com/docs/ai/agentforce/guide/get-started-agents.html)
- [Salesforce: Create Employee Agents](https://trailhead.salesforce.com/content/learn/projects/quick-start-create-employee-agents-in-agentforce/create-two-employee-agents)
- [Salesforce: Configure Agentforce Engagement](https://trailhead.salesforce.com/content/learn/modules/agentforce-sdr-setup-and-customization/configure-and-activate-your-sdr-agent)
- [Salesforce: Configure Agentforce Sales Coach](https://trailhead.salesforce.com/content/learn/modules/agentforce-for-sales-coaching-setup-and-customization/enable-and-set-up-sales-coach)

### Runtime and outbound credential model

Agentforce execution identity is configurable rather than universally
per-agent. The Agent API can run a session as the user assigned to the agent
or as the user associated with the caller's token. Salesforce also provides
an agent-user creation flow that produces a distinct username, but public
documentation does not establish that every Agentforce agent must have a
unique assigned user.

Outbound integrations add another independent choice. Salesforce Named
Credentials can use a **named principal**, whose credential is shared by all
authorized callers, or **per-user principals**, whose tokens differ by user.
A compromised agent may therefore exercise a shared callout capability even
when the underlying secret is protected from direct extraction.

The public model supports both shared and separated authorities, but does not
publish one universal default that Registry Sync can rely on. Use a dedicated
companion Blueprint automatically. Treat a customer-provided agent user,
execution context, or Named Credential relationship only as evidence for a
separate explicit shared onboarding review.

Sources:

- [Salesforce: Agent API execution context](https://developer.salesforce.com/docs/ai/agentforce/guide/agent-api-get-started.html)
- [Salesforce CLI: Create an Agentforce agent user](https://developer.salesforce.com/docs/platform/salesforce-cli-reference/guide/cli_reference_org_create_agent-user.html)
- [Salesforce: Named Credentials](https://developer.salesforce.com/docs/platform/named-credentials/guide/get-started.html)
- [Salesforce: Named Credential principal types](https://developer.salesforce.com/docs/platform/named-credentials/references/named-credentials-reference/nc-glossary.html)

Retain the type or template as an attribute. Do not automatically turn every
template into a separate offering group.

Service and Employee agent types may have different execution contexts and
access needs, but the type name alone does not prove credential sharing or
isolation.

Do not create offering groups for Agentforce Builder, Agent Script, SDKs,
Slack, messaging channels, or UI components. Those are authoring,
integration, or exposure surfaces rather than separate deployable-agent
control planes.

## Anthropic Claude Managed Agents

Use:

```text
anthropic-claude-managed-agents
```

Microsoft explicitly supports **Claude Managed Agents** and requires a
dedicated Anthropic workspace ID and workspace-scoped API key. Microsoft
marks this connector as preview because Anthropic's Managed Agents APIs are
beta.

Source:
[Microsoft: Anthropic Claude Managed Agents connected platform](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/connected-platforms#anthropic-claude-managed-agents).

Anthropic distinguishes:

- reusable, versioned agent configurations;
- execution environments;
- sessions; and
- scheduled deployments.

Use the durable source-agent record exposed by Registry Sync as the companion
anchor. Do not create a Blueprint, Agent Identity, or companion Registration
per session.

Sources:

- [Anthropic: Managed Agents overview](https://platform.claude.com/docs/en/managed-agents/overview)
- [Anthropic: Agent setup](https://platform.claude.com/docs/en/managed-agents/agent-setup)
- [Anthropic: Sessions](https://platform.claude.com/docs/en/managed-agents/sessions)
- [Anthropic: Scheduled deployments](https://platform.claude.com/docs/en/managed-agents/scheduled-deployments)

Managed Agents supports managed cloud sandboxes and self-hosted sandboxes.
Execution placement is an important security attribute and may require
separate Blueprint groups, but it remains within the same offering
classification.

Source:
[Anthropic: Self-hosted sandboxes](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes).

### Runtime and credential isolation

Anthropic documents a fresh isolated cloud sandbox for every session, even
when multiple sessions reference the same reusable environment. This is
session isolation, not proof of a durable unique authentication principal for
each managed-agent definition.

Managed Agent definitions can declare MCP servers, while sessions receive
outbound credentials through vault references. Vault secrets are write-only
and can be substituted at egress, but workspace-authorized control-plane
credentials can manage sessions and reference workspace vaults. Self-hosted
sandboxes additionally use environment-scoped service keys and make the
customer responsible for runtime isolation.

Public documentation therefore does not establish a universal per-agent
credential boundary or a universal shared-agent credential boundary. Neither
a common Anthropic workspace nor separate session sandboxes provide enough
evidence to assign a shared Entra Blueprint. Use a dedicated companion
Blueprint automatically.

Sources:

- [Anthropic: Cloud environments and session isolation](https://platform.claude.com/docs/en/managed-agents/environments)
- [Anthropic: MCP authentication](https://platform.claude.com/docs/en/managed-agents/mcp-connector)
- [Anthropic: Vault security and scope](https://platform.claude.com/docs/en/managed-agents/vaults)
- [Anthropic: Self-hosted sandbox security](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes-security)

Do not conflate this connector with Claude Agent SDK, Claude Code, Cowork, or
the Claude Enterprise plan. Those are separate SDK, product, or commercial
surfaces and are not established as Registry Sync source offerings.

## How offering keys relate to Blueprint assignment

An offering key classifies the provider product. It does not identify a
shared credential boundary and must not delay automatic companion
provisioning while a person searches the tenant for a reusable Blueprint.

For the automatic Registry Sync path:

1. Create a deterministic single-member `dedicated` group for each new scoped
   provider source.
2. Create or reconcile one Blueprint for that group.
3. Create one Agent Identity and one companion Registration for the source.
4. Use `unassigned` only for an explicit hold, missing authorization,
   incomplete source identity, conflicting durable state, or another
   condition that makes any write unsafe.

A `shared` group is a separate explicit onboarding path. Its complete source
membership and Blueprint binding must be approved before any member receives
a companion identity. The automatic path does not wait for that possibility,
and an already provisioned dedicated source is not automatically migrated
later merely to reduce object count.

Do not infer sharing from:

- provider, offering, account, project, connection, environment, team, region,
  framework, deployment tool, or display name;
- a shared provider execution role or outbound credential without a complete
  review of the resulting Entra credential blast radius; or
- similarity of required downstream permissions.

Configuration consistency across dedicated Blueprints should be provided by
an external desired-state template and batch reconciliation, not by expanding
the Blueprint credential boundary.

The durable invariants should be:

```text
one scoped provider source -> one dedicated Blueprint group by default
one (tenant, blueprintGroup) -> one active Blueprint binding
one scoped provider source -> one active Agent Identity
one scoped provider source -> one active companion Registration
```

For the optional shared-onboarding path, if a Blueprint reaches an applicable
capacity limit, create an explicitly approved shard such as `s02`; do not
silently bind one group label to multiple active Blueprints.

Microsoft documents a 250-Agent-Identity Blueprint limit for the app-only
provisioning scenario and notes that soft-deleted identities continue to
consume capacity. Confirm which limit applies to the chosen provisioning
model before creating shards.

Source:
[Microsoft: Agent identity deletion and quota considerations](https://learn.microsoft.com/en-us/entra/agent-id/concept-agent-identity-deletion#orphaned-objects-and-quota-considerations).

## Can Package List reveal a Blueprint ID?

### Short answer

`GET /v1.0/copilot/admin/catalog/packages` does not document a direct,
typed Blueprint field or Blueprint relationship.

The documented Package resource contains `appId`, but that property is an
associated application-registration identifier. It is not documented as a
universal Agent Identity Blueprint ID. Package Details documents no
relationships.

Sources:

- [Microsoft: List packages](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/package/copilotpackages-list)
- [Microsoft: Package resource](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/package/resources/copilotpackage)
- [Microsoft: Package Details resource](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/package/resources/copilotpackagedetail)

The public v1.0 and beta Graph metadata include nullable `agentIdentityId`,
`appId`, and JSON `governanceMetadata` fields on `copilotPackage`, but no
typed `agentIdentityBlueprintId` property. The beta `agentRegistration`
resource contains both `agentIdentityId` and `agentIdentityBlueprintId`.

Sources:

- [Microsoft Graph v1.0 metadata](https://graph.microsoft.com/v1.0/$metadata)
- [Microsoft Graph beta metadata](https://graph.microsoft.com/beta/$metadata)

Therefore, a populated Package `agentIdentityId` can be an indirect lookup
input, but the Package API does not provide a universal direct Blueprint-ID
lookup.

### Documented resolution paths

| Starting value | Documented operation | Result |
| --- | --- | --- |
| Agent Identity object ID | `GET /v1.0/servicePrincipals/{id}/microsoft.graph.agentIdentity` | Read `agentIdentityBlueprintId`, which is the parent Blueprint `appId`. |
| Blueprint `appId` | `GET /v1.0/servicePrincipals(appId='{appId}')/microsoft.graph.agentIdentityBlueprintPrincipal` | Resolve the tenant-local Blueprint principal. |
| Blueprint object ID | `GET /v1.0/applications/{id}/microsoft.graph.agentIdentityBlueprint` | Read and verify the typed Blueprint application. |
| No known Blueprint ID | `GET /v1.0/applications/microsoft.graph.agentIdentityBlueprint` | List Blueprints in the Blueprint application's home tenant; follow pagination. |
| Known Agent Registration ID | `GET /beta/copilot/agentRegistrations/{id}` | Read the Registration's stored identity-link fields. |

Sources:

- [Get Agent Identity](https://learn.microsoft.com/en-us/graph/api/agentidentity-get?view=graph-rest-1.0)
- [Get Blueprint principal](https://learn.microsoft.com/en-us/graph/api/agentidentityblueprintprincipal-get?view=graph-rest-1.0)
- [Get Blueprint](https://learn.microsoft.com/en-us/graph/api/agentidentityblueprint-get?view=graph-rest-1.0)
- [List Blueprints](https://learn.microsoft.com/en-us/graph/api/agentidentityblueprint-list?view=graph-rest-1.0)
- [Get Agent Registration](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/agent-registration/agentregistration-get)

A multitenant Microsoft-owned Blueprint application can reside outside the
customer tenant while its Blueprint principal exists locally. Absence from
the customer's application list therefore does not prove that no Blueprint
exists.

Source:
[Microsoft: Blueprint principals and multitenancy](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-blueprint#agent-identity-blueprint-principals).

No reviewed public documentation establishes:

- a universal Package-ID-to-Registration lookup;
- a Registration lookup by `sourceAgentId`;
- a rule that Package `appId` always equals a Blueprint `appId`; or
- an API that returns a customer-defined `blueprintGroup`.

## Microsoft-native examples

### Copilot Studio

Microsoft publishes a global Blueprint for new Copilot Studio agents:

```text
Name: Microsoft Copilot Studio agent identity blueprint
Blueprint ID: 25664c89-cea5-4ab6-b924-a54fd8a19ae0
```

Each new Copilot Studio agent receives its own Entra Agent ID as a child of
that global Blueprint. The agent's Entra Agent ID is available in Copilot
Studio under **Settings > Advanced > Metadata**.

Source:
[Microsoft: Manage Entra Agent IDs in Copilot Studio](https://learn.microsoft.com/en-us/microsoft-copilot-studio/admin-use-entra-agent-identities#understanding-blueprint-principals).

Older agents may still use legacy app registrations. A Microsoft-native
Package therefore does not guarantee that an Agent Identity or Blueprint link
is present.

The published Copilot Studio Blueprint ID is a product-specific value to
verify. It is not permission to attach external companion identities to
Microsoft's Blueprint.

### Microsoft Foundry

Foundry's current identity model is not one Blueprint for every Foundry
agent:

- legacy unpublished agents can share project identity and Blueprint;
- legacy Agent Applications receive their own identity and Blueprint;
- new-model agents receive a unique Blueprint and Agent Identity by default;
  and
- bring-your-own Blueprint is supported as an explicit alternative.

Source:
[Microsoft Foundry: Migrate Agent Applications](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/migrate-agent-applications).

Resolve Foundry identity information from the actual Foundry agent or
application record, then verify the IDs through typed Graph reads. Do not
infer the Blueprint from a Package display name or assume that the Copilot
Studio sharing model applies to Foundry.

## Observed tenant Blueprint inventory

Observation date: 2026-09-12.

This is an exact tenant-local snapshot produced by
[`scripts/report_blueprint_inventory.py`](../scripts/report_blueprint_inventory.py).
The operator explicitly approved recording the exact Blueprint names and IDs
in this tracked research document. These values describe the inspected tenant
at the observation time and are not general Microsoft product identifiers,
except where a Microsoft-owned global Blueprint is independently documented.

The **Blueprint name** column is the tenant-local Blueprint principal's
`displayName`. The **Blueprint ID** column is the parent Blueprint application
`appId` returned through the Agent Identity relationship.

| Microsoft platform | Blueprint name | Blueprint ID | Number of agent identities under this Blueprint |
| --- | --- | --- | ---: |
| Copilot Studio | Microsoft Copilot Studio agent identity blueprint | 25664c89-cea5-4ab6-b924-a54fd8a19ae0 | 7 |
| fabrikam | Fabrikam Production in Azure | 2c18e795-2df1-4da8-87df-963be80ff92e | 2 |
| Foundry | fdry-shared-agents-development-4qxhllplfn-prj-shared-agents-development-agent-06-manager-conversation-coach-f22b0-AgentIdentityBlueprint | 2e561630-9abf-49d2-8135-3e27f9d19de8 | 1 |
| Foundry | fdry-shared-agents-development-4qxhllplfn-prj-shared-agents-development-agent-07-employment-contract-compensation-reviewer-72bdf-AgentIdentityBlueprint | 26e14e84-c5e3-40b9-b71f-933916dea7cc | 1 |
| Foundry | foundry-east-us-2-20260701-proj-foundry-east-us-2-20260701-workflow-definition-schema-drafting-af8c9-AgentIdentityBlueprint | 8e7ac447-5028-46e5-bff1-f5313c5769d9 | 1 |
| Foundry | foundry-project-sweden--resource-foundry-project-sweden-central-2026-05-06-Refund-agent-eabaf-AgentIdentityBlueprint | b68efce1-d5bd-475b-bb92-f34347ecb735 | 1 |
| Foundry | foundry-project-sweden--resource-foundry-project-sweden-central-2026-05-06-workiq-tester-agent-98661-AgentIdentityBlueprint | 1a3b3502-3915-4153-bb3a-cbf2bde99f7a | 1 |
| Foundry | foundry-resource-20260112-proj-20260112-japan-meeting-agent-8e742-AgentIdentityBlueprint | 94092247-b1cb-4afc-b24a-e8496a8b1cb5 | 1 |
| Foundry | foundry-resource-20260112-proj-20260112-test-copilot-studio-agent-a2a-5fdd4-AgentIdentityBlueprint | 90fdb6cf-abdd-4e7c-b3cc-c29892983347 | 1 |
| Foundry | foundry-resource-20260112-proj-20260112-travel-planner-aggregator-66db5-AgentIdentityBlueprint | c8554bc4-89f6-43da-ac90-45083a7480bd | 1 |
| Foundry | foundry-resource-20260112-proj-20260112-travel-planner-dining-50787-AgentIdentityBlueprint | e1ecb06c-4a81-4a54-86a4-78d2d3567dee | 1 |
| Foundry | foundry-resource-20260112-proj-20260112-travel-planner-events-a80f3-AgentIdentityBlueprint | 7c074491-8104-49c3-a0b7-76c5ad9950c4 | 1 |
| Foundry | foundry-resource-20260112-proj-20260112-travel-planner-poi-8abf6-AgentIdentityBlueprint | 85a3f6a7-c125-4e7a-a163-36f9aa39993d | 1 |
| Foundry | foundry-resource-20260112-proj-20260112-travel-planner-route-e859c-AgentIdentityBlueprint | ea086d01-92de-4ecc-9314-54cc1b3caf33 | 1 |
| Foundry | foundry-resource-20260112-proj-20260112-travel-planner-stay-f0094-AgentIdentityBlueprint | d05d8bde-2d9c-465e-aa26-087066818416 | 1 |
| Foundry | foundry-resource-20260112-proj-20260112-travel-planner-transport-87b25-AgentIdentityBlueprint | 236847fd-909e-4b49-a244-b69009d16ebe | 1 |
| Foundry | foundry-resource-20260112-proj-20260112-travel-planner-weather-proxy-9b396-AgentIdentityBlueprint | 20ebf5f5-a82e-4c0e-8c27-b3d544511347 | 1 |
| Foundry | foundry-sg-dev-viu5a2-proj-sg-dev-viu5a2-mca-allocator-1180d-AgentIdentityBlueprint | afc43fef-105c-4f40-a80d-f45450975f5c | 1 |
| Foundry | foundry-sg-dev-viu5a2-proj-sg-dev-viu5a2-mca-correspondence-41a2e-AgentIdentityBlueprint | b80d20bc-1cd8-4628-9e3a-644fab8e484c | 1 |
| Foundry | foundry-sg-dev-viu5a2-proj-sg-dev-viu5a2-mca-precedent-ac17f-AgentIdentityBlueprint | e9c9d5d9-227c-495d-9997-74680f4005f4 | 1 |
| Foundry | foundry-sg-dev-viu5a2-proj-sg-dev-viu5a2-mca-prefill-626a0-AgentIdentityBlueprint | 57b411b1-a773-4a12-a1b7-717f111c084a | 1 |
| Foundry | foundry-sg-dev-viu5a2-proj-sg-dev-viu5a2-mca-template-227b4-AgentIdentityBlueprint | 64476391-e88c-429c-8250-dd30e37fae53 | 1 |
| Foundry | foundry-sg-dev-viu5a2-proj-sg-dev-viu5a2-mca-triage-e217b-AgentIdentityBlueprint | 205ff437-fbde-462f-8f10-92c335c7fe78 | 1 |
| Foundry | foundry-sg-dev-viu5a2-proj-sg-dev-viu5a2-prev-corro-retrieval-agent-a6ce8-AgentIdentityBlueprint | 3206fe61-b687-4585-b9ea-a4c4128f8b7d | 1 |
| Foundry | foundry-sg-dev-viu5a2-proj-sg-dev-viu5a2-solid-guacamole-correspondence-agent-10f59-AgentIdentityBlueprint | a7549156-9d31-46a4-9fc3-5d8f65f50011 | 1 |
| Foundry | foundry-sg-dev-viu5a2-proj-sg-dev-viu5a2-test-365cb-AgentIdentityBlueprint | a1fcb471-7b9a-48b5-bdd0-f7c8b52563f3 | 1 |
| Foundry | foundry-sg-dev-viu5a2-proj-sg-dev-viu5a2-triage-agent-90e95-AgentIdentityBlueprint | 2dc18789-ccb0-4b46-aa6b-999e2b41c8b0 | 1 |
| Foundry | foundry-sg-dev-viu5a2-proj-sg-dev-viu5a2-triage-pathway-classifier-agent-d1fcc-AgentIdentityBlueprint | 2d0e6806-fe97-434d-bb58-d59effd02166 | 1 |
| GoogleVertexAI | GoogleVertexAI - test-v2-dev - disposable Blueprint | b16c35b8-4f3f-4ae8-9a64-4329d12c6287 | 1 |
| Not Available | A365RegistryLab Blueprint | 2491c79c-2bcb-471b-893c-fd436cb49b9f | 1 |
| Not Available | Activity Demo Coordinator Blueprint | 1157336a-09c4-4f1d-b8c5-00b8a1422d09 | 1 |
| Not Available | Activity Demo Specialist Blueprint | 9c5c5f15-d7c8-40e5-860f-233d6cee717a | 1 |
| Not Available | AskBot Blueprint | c70f9f79-cee8-409f-ae92-90dc4daf443c | 1 |
| Not Available | Travel Assistance & Claims Agent Blueprint | 778e1885-563b-45ea-8e0a-b884ff073c2e | 1 |

Run summary:

```text
Packages read: 368
Unique package-linked Agent Identities resolved: 41
Packages without an Agent Identity: 324
Resolution failures: 3
```

The totals reconcile: `324 + 41 + 3 = 368`. The 41 resolved identities
include 7 under the shared Copilot Studio Blueprint, 2 under the
tenant-specific `fabrikam` Blueprint, 26 Foundry identities each using a
distinct Blueprint in this snapshot, 1 Google Vertex AI companion identity,
and 5 Packages whose platform value was not available.

The three resolution failures are retained in the ignored enriched evidence:

```text
evidence\blueprint-inventory\enriched-packages.json
```

They are not included in the Blueprint table because Graph could not resolve
their Agent Identity or Blueprint relationship. They must not be counted as
Packages without an Agent Identity.

### Interpretation of the observed Microsoft patterns

- **Copilot Studio:** the observed seven-to-one relationship matches
  Microsoft's documented global shared-Blueprint model.
- **Foundry:** the observed 26 one-to-one relationships match the current
  Foundry default in which new-model agents receive unique Blueprints and
  Agent Identities. This tenant snapshot does not prove that every Foundry
  configuration uses one Blueprint per agent because shared and
  bring-your-own Blueprint models also exist.
- **GoogleVertexAI:** the one row is the Lab 20 disposable companion
  Blueprint. It is evidence of the local experiment, not evidence that
  Registry Sync automatically supplies a Google Blueprint.
- **`fabrikam` and `Not Available`:** these are returned Package platform
  labels from this tenant. Blueprint names alone are insufficient to infer a
  supported product classification, so these rows remain unclassified.

### Public documentation corroboration and scope

Checked against current Microsoft Learn documentation on 2026-09-12.

- **Copilot Studio:** Microsoft explicitly publishes the global
  **Microsoft Copilot Studio agent identity blueprint**, ID
  `25664c89-cea5-4ab6-b924-a54fd8a19ae0`, and states that all Agent
  Identities are children of the Copilot Studio global Blueprint. The article
  explicitly applies to the standard harness. Since May 2026, every newly
  created agent receives its own Entra Agent ID, with no opt-out. Older agents
  can still use app-registration identities pending migration, so this does
  not mean every historical Copilot Studio agent already has an Agent
  Identity.
  [Microsoft Learn: Manage Entra Agent IDs in Copilot Studio](https://learn.microsoft.com/en-us/microsoft-copilot-studio/admin-use-entra-agent-identities#understanding-blueprint-principals).
- **Foundry legacy model:** unpublished agents in the same project share an
  Entra Agent Identity and Blueprint. Publishing creates a dedicated identity
  and Blueprint bound to the Agent Application resource. This behavior belongs
  to the legacy Agent Application publishing model.
  [Microsoft Learn: Foundry agent identity](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-identity#foundry-integration).
- **Foundry new model:** newly created agents receive a unique Entra Agent
  Blueprint and Agent Identity by default, at creation, instead of acquiring
  them through a separate Agent Application publishing step. Microsoft also
  supports bring-your-own Entra Agent Blueprint as a nondefault alternative.
  Bringing a Blueprint does not by itself prove that the Blueprint is shared.
  [Microsoft Learn: Migrate Agent Applications to the new Foundry agent model](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/migrate-agent-applications#overview-of-the-change).

The tenant observation is therefore strongly corroborated but must remain
qualified:

- The seven Copilot Studio Agent Identities under one Blueprint match
  Microsoft's explicitly documented global Blueprint model.
- The 26 Foundry Agent Identities each referencing a different Blueprint match
  the new-model default and are also compatible with dedicated legacy Agent
  Application Blueprints.
- The snapshot does not identify which Foundry creation model produced each
  row, establish tenant-wide completeness, or prove a universal rule that
  every Foundry agent must always have its own Blueprint.

## Required validation before implementation

| Gap | Validation |
| --- | --- |
| Automatic dedicated provisioning | Confirm tenant-level authorization, deterministic naming, idempotency, credential setup, and object-count limits before enabling automatic writes. |
| Optional Blueprint sharing safety | For the separate shared-onboarding path, approve complete membership, credential ownership, inherited permissions, sponsors, policies, and disable/delete blast radius before creating any member identity. |
| AWS cardinality | Observe how Registry Sync represents Classic agents, aliases, versions, harnesses, backing runtimes, gateways, and tools. |
| AWS runtime authority | Capture representative workload identity and execution-role relationships; public documentation permits configurable role reuse. |
| Salesforce cardinality | Observe the exact source records and type fields imported for Service, Employee, Engagement, and Sales Coach agents. |
| Salesforce runtime authority | Determine whether each imported source uses a distinct agent-assigned user, a shared user, or another execution context, and identify its outbound Named Credential principals. |
| Anthropic cardinality | Confirm that Registry Sync imports durable agent definitions rather than sessions, environments, or deployments as separate agents. |
| Anthropic runtime authority | Determine whether a durable managed-agent definition has an independently enforceable principal or only session, workspace, environment, and vault-scoped controls. |
| Google coverage | Confirm that current packages remain `reasoningEngines` resources after the Google product rename. |
| Google runtime authority | Record whether each source uses Google Agent Identity or a service-account-based mode; do not infer this from project or connection alone. |
| Cross-provider source stability | Repeat the rename and connection-recreation experiment independently for AWS, Salesforce, and Anthropic. |
| Package identity data | Read representative Microsoft-native and external Packages and distinguish absent, null, and populated `agentIdentityId` values. |
| Blueprint resolution | Verify Agent Identity object ID -> Blueprint `appId` -> tenant-local Blueprint principal, storing each ID separately. |
| Companion association | Read back the Registration and verify that the Agent Identity's actual parent matches the selected Blueprint. |
| Original synced Package | Re-read it independently; do not assume companion creation enriches or replaces it. |
| Production support | Obtain Microsoft confirmation before production companion rollout. |
| Runtime enforcement | Prove token acquisition and downstream authorization separately from inventory and identity association. |

The Agent Registration API remains beta and its documentation states that it
is not supported for production use.

Source:
[Microsoft: Agent Registration resource](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/agent-registration/resources/agentregistration).

## Final decision

Adopt the six offering keys as the starting classification catalog:

```text
gcp-agent-runtime
aws-bedrock-agents-classic
aws-agentcore-runtime
aws-agentcore-harness
salesforce-agentforce
anthropic-claude-managed-agents
```

Use the offering key for classification and provider-specific source handling,
not to choose a shared Blueprint.

This preserves the Lab's intended architecture:

- automatic provisioning creates one dedicated Blueprint per scoped provider
  source;
- each scoped provider source receives its own Agent Identity;
- each scoped provider source receives one companion Registration; and
- the companion stays in a one-to-one relationship with the original
  Registry Sync agent.

The provider evidence does not support automatic shared-Blueprint inference:

- GCP Agent Identity explicitly isolates each Agent Runtime identity.
- AWS AgentCore creates a workload identity per Runtime, while execution-role
  reuse remains customer-configurable.
- Bedrock Agents Classic and AgentCore harness roles are configurable rather
  than governed by a universal sharing rule.
- Salesforce supports both shared and per-user execution or outbound
  credentials.
- Anthropic isolates sessions but does not publicly establish a durable
  per-agent credential principal.

Therefore, the safe automatic rule is:

```text
one Registry Sync source
-> one dedicated companion Blueprint
-> one Agent Identity
-> one companion Registration
```

Shared Blueprint onboarding remains an explicit separate workflow completed
before identity creation. No universal "one vendor equals one Blueprint" rule
is supported.

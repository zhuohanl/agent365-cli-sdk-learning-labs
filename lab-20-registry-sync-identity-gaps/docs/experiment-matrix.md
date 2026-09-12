# Registry Sync identity gaps experiment matrix

Do not record names, identifiers, tenant values, endpoints, tokens, or raw
responses in this file.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| supported | The documented request completed successfully. |
| unavailable | The required approved record or environment does not exist. |
| permission-denied | The API is documented, but the active principal cannot call it. |
| not-applicable | The operation requires an object or capability that is absent by design. |
| inconclusive | The observation cannot distinguish the possible explanations. |

## Single GCP sample walkthrough

| Step | Observation | Result | Status |
| --- | --- | --- | --- |
| 1 | Device-code request | `200 OK` | supported |
| 2 | Interactive sign-in | Completed | supported |
| 3 | Token exchange with `CopilotPackages.Read.All` | `200 OK` | supported |
| 4 | Package inventory list | `200 OK`; 354 records; no `@odata.nextLink` | supported |
| 4 | Existing non-production GCP sample found | Found locally in the complete list response | supported |
| 5 | Selected package details | `200 OK` | supported |
| 5 | Package ID matches selected list record | Yes | supported |
| 5 | Platform field present | Yes | supported |
| 5 | Connected Platform registration marker present | Yes | supported |
| 5 | Google Vertex AI provider marker present | Yes | supported |
| 5 | Top-level asset ID present | No; value is null | supported |
| 5 | Top-level owner metadata present | No; owner ID is null | supported |
| 5 | Top-level source agent ID present | No | supported |
| 5 | Source agent ID present in nested platform metadata | Yes | supported |
| 5 | Blueprint ID present | No | supported |
| 5 | Entra Agent ID present | No; value is null | supported |
| 5 | Top-level managed-by application ID present | No | supported |
| 5 | Managed-by reference present in nested platform metadata | Yes; semantics not yet established | inconclusive |
| 5 | Originating store present | No | supported |
| 5 | Agent Registration ID exposed | No documented field observed | inconclusive |

## Interpretation checkpoint

Do not proceed to identity creation or registration update until the read-only
walkthrough answers:

1. Which identity and source fields are actually present?
2. Is any returned field documented as an Agent Registration ID?
3. If no registration ID is exposed, which supported API can establish the
   package-to-registration relationship?

## Documented API boundary

| Question | Result | Status |
| --- | --- | --- |
| Can inventory be listed and inspected programmatically? | Yes, through Package List and Package Details | supported |
| Does Package Details expose the provider-native source agent ID? | Yes, in nested Connected Platform metadata rather than the top-level field | supported |
| Does the selected record have a Blueprint ID? | No observed field | supported |
| Does the selected record have an Entra Agent ID? | No; the field value is null | supported |
| Does Agent Registration API provide a list operation? | No operation is documented | unavailable |
| Is a Package ID to Agent Registration ID mapping documented? | No | inconclusive |
| Can the proposed registration PATCH be addressed safely? | No supported target identifier has been established | unavailable |

## Agent Registration collection probe

| Step | Observation | Result | Status |
| --- | --- | --- | --- |
| R1 | Device-code request for `AgentRegistration.Read.All` | Completed | supported |
| R2 | Interactive sign-in | Completed | supported |
| R3 | Token exchange | Completed | supported |
| R4 | `GET /beta/copilot/agentRegistrations` | `404 Not Found` with no collection | unsupported |
| R4 | Collection endpoint documented by Microsoft | No | unsupported |

## Disposable registration correlation experiment

| Step | Observation | Result | Status |
| --- | --- | --- | --- |
| C1 | Disposable GCP agent prepared | Yes | supported |
| C2 | Registry Sync package visible before create | Package List and Package Details returned `200 OK` | supported |
| C2 | Baseline Package ID and nested source metadata captured locally | Saved in ignored evidence; required fields and provider markers present | supported |
| C3 | Initial create request validation | `400 Bad Request`; local timestamp conversion was not ISO 8601; no registration created | inconclusive |
| C3 | App-managed create attempt | Rejected because the caller was not permitted to create a registration for the submitted `managedByAppId`; no registration ID returned | permission-denied |
| C3 | Registration created with the same provider-native `SourceAgentId` | `201 Created`; new Registration ID returned and stored only in ignored local config | supported |
| C4 | Read newly created registration | `200 OK`; source ID matches the Registry Sync source ID; owner and originating store are present | supported |
| C4 | Package inventory after create | `200 OK`; 356 records; two packages share the disposable agent display name | supported |
| C4 | Original Registry Sync package after create | Still present with the same Package ID and source metadata; no identity fields added | supported |
| C4 | New registration represented in Package inventory | Yes; a second package has an ID equal to the new Registration ID | supported |
| C4 | Outcome: conflict, merge, duplicate, or no inventory change | Duplicate: the API-created registration produced a parallel package instead of updating the Registry Sync package | supported |
| C4 | Read API-created Package Details using Registration ID | `200 OK`; Package ID equals Registration ID | supported |
| C5 | Created registration deleted | Not run; cleanup deferred by experiment owner | blocked |
| C5 | Original Registry Sync state restored | Not run because the created registration remains | blocked |

## Notebook identity-association attempt

This attempt is independent of the earlier correlation experiment: its exact
source ID differs from that earlier successful registration. Neither record
can be substituted for the other. No identifier values are recorded here.

| Observation | Result | Status |
| --- | --- | --- |
| Part 3.2 registration POST with identity links | HTTP `500`, Graph `UnknownError`, and an embedded backend permission-denial message; no Registration ID recovered | permission-denied |
| Required delegated write scope in the failed request's decoded token | Present; reported by the local diagnostic, not a new authorization grant | supported |
| Caller matches the submitted creator and an owner | Both comparisons true in the captured request | supported |
| Identity fields allowed in the published create contract | Both are shown in the first-party [create reference](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/agent-registration/agentregistration-create) | supported |
| Precise backend authorization failure | Not established by the error or token/ownership comparisons | inconclusive |
| Whether the failed POST changed any remote object | Not established; pending-write evidence retained | inconclusive |
| Identity association successfully stored or resolved | Not demonstrated | inconclusive |
| One explicitly approved REST Client replay of the captured request | User reported the same HTTP `500`, `UnknownError`, and backend permission-denial message | permission-denied |
| Captured replay compared with notebook state before sending | Exact source, platform, Blueprint reference, Agent Identity reference, and creator matched; both identity fields present and managing-app field absent | supported |
| Replay authentication context | Captured token was unexpired and contained the required delegated scope; caller matched the submitted creator and an owner | supported |
| Notebook-specific HTTP transport as the explanation | The same denial was reproduced with REST Client; this does not validate the payload or explain backend authorization | inconclusive |

The error's use of "update" does not establish that POST performed an update
or upsert. Do not treat the documented identity fields as unsupported because
this request failed. Changing HTTP clients did not resolve the denial. The
earlier no-identity success used a different exact source ID, so it does not
isolate the identity fields as the cause.

### Fresh deterministic-source companion

This later experiment did not reuse the Registry Sync provider source ID. It
used the versioned DD-002 companion source-ID format and retained all real
values in local state.

| Observation | Result | Status |
| --- | --- | --- |
| Earlier same-source pending result reconciled | Recorded as the already observed HTTP `500` permission-denial result | supported |
| Fresh companion source differs from provider source | Yes; the experiment used the now-legacy `committed-fleet:companion:v1` format | supported |
| Current companion namespace | New companions use `agent-governance:companion:v1`; the existing experimental Registration retains its exact legacy value | design decision |
| Fresh companion registration POST | User reported `201 Created` and a returned Registration ID | supported |
| GET by returned Registration ID | User reported successful readback | supported |
| Blueprint and Agent Identity fields on readback | Matched the submitted Entra object IDs | supported |
| Original Registry Sync Package after create | Read successfully; identity field remained equal to the pre-write value | supported |
| Durable mapping | Provider source, Package, companion source, Registration, Blueprint, and Agent Identity references saved in local state | supported |
| Provider runtime authentication | Not tested | inconclusive |
| Governance enforcement | Not tested | inconclusive |
| Cross-provider applicability | Only the selected GCP source was observed | inconclusive |
| Fresh companion cleanup | Not yet reported | blocked |

The successful result supports a separately managed companion pattern for
further evaluation. It does not turn the companion into the Registry Sync
record, make the Package ID a Registration ID, or establish production API
support.

After the failed replay, further writes were paused and pending-write evidence
retained. The current
boundary is backend authorization for the submitted association, not a proven
missing scope, wrong caller, unsupported field, or working identity-assignment
path. If separately approved, controlled observations cannot identify the
rejected condition, use protected diagnostic evidence with the authorized
product-support channel. Do not add broader permissions or substitute
identifiers merely to get past the denial. No notebook-state reconciliation, remote
cleanup, or further retry has been performed.

### Identity-free baseline and known-registration read control

The experiment owner chose to omit both identity fields from the next POST
while preserving the other JSON values, then consider adding one field at a
time only after a successful create and readback. This is a baseline
comparison, not a one-field isolation test or a demonstrated fix.

| Observation | Result | Status |
| --- | --- | --- |
| POST with both identity fields omitted | User reported HTTP `500`, `UnknownError`, and the same backend permission-denial message | permission-denied |
| GET a user-supplied known registration with the captured token | HTTP `200`; returned ID matches the requested ID | supported |
| Ownership of the known registration | Caller is both creator and an owner; no managing-app value present | supported |
| Identity fields on the known registration | Neither identity reference has a nonempty value | supported |
| Relationship to the notebook selection | Same platform, but a different exact source ID | supported |
| Can read success establish create permission for the selected source? | No; these are different operations and different registration targets | inconclusive |
| Authentication mode for yesterday's HTTP flow and the current notebook/replay | Both are delegated user flows through the same public-client app and tenant; the current token has an `scp` claim and no application `roles` claim | supported |
| Documented delegated create permission | `AgentRegistration.ReadWrite.All` | supported |
| Required delegated create scope in the current failed token | Present, along with the read scope; Microsoft Graph is the token audience | supported |
| Is another or higher Agent Registration permission documented for create? | No higher privileged permission is listed in the current create reference | unavailable |
| Would adding the same delegated permission again explain or resolve this failure? | No; the failed request already carried that scope, and yesterday's successful flow requested the same write scope | not-applicable |
| Login-app permission configuration | User-provided portal evidence shows delegated `AgentRegistration.ReadWrite.All` configured with admin consent granted | supported |
| Is configured consent missing from the issued token? | No; the captured token contains the same write scope | supported |

The denial still occurs without the two identity fields, so their presence
alone cannot explain it. This does not prove the remaining payload is correct
or irrelevant to authorization: source and management relationships may affect
which object a service authorizes. The exact rejected condition remains
unresolved.

The phrase "user permission" should be read precisely here: Microsoft Entra
issued a token to the registered public client **on behalf of** the signed-in
user. The client ID still identifies the login application, but the token is
not an app-only token. The API can enforce both the delegated scope granted to
that client and user/object-specific authorization. Current evidence satisfies
the documented scope check but does not reveal the failing backend condition.
Do not add application permission, a broader directory role, or another
consent grant merely to bypass this result.

The current synchronized package and yesterday's successful disposable source
also do not have identical nested source metadata shapes. The current record
contains a nested originating-store field under its source identifiers that
was not present in the earlier source evidence. This does not establish an
authorization rule, but it reinforces that the two provider records are not
interchangeable controls even though both report the same top-level platform.

No Entra object was deleted, no POST followed the successful GET, and the
original request body and notebook pending state are retained. Do not use the
known control registration as the selected agent's companion or associate the
selected agent's identity with it.

### Prepared authentication-flow control (not yet sent)

A private ignored copy of
`experiments/02-provider-source-registration-create/experiment.http`
was prepared under
`evidence/notebook-pilot/` for today's selected source. It preserves
the earlier successful device-code
delegated authentication flow, registration write scope, `/me` creator/owner
binding, and identity-free user-owned POST shape. Today's exact package,
source, source timestamps, display metadata, and platform were substituted
from private captured evidence. The earlier created Registration ID was
removed, and no bearer token is stored in the file before authentication.

The generated POST body was compared with today's captured identity-free body
and matches it. No request has been sent. This control changes the token
acquisition flow while retaining the selected source and request body. A
successful result would show a difference associated with the newly acquired
authentication context or timing, not automatically prove which authorization
property changed. The device-code, token, `/me`, and create requests must be
run individually; do not use **Send All**.

The experiment owner subsequently reported that this copied device-code flow
was also blocked at its POST step. Together with the configured consent and
token-scope evidence, this makes a general missing delegated scope an
unsupported explanation. The strongest remaining hypothesis is an
object/source-specific authorization decision or backend defect: the service
may resolve the selected `sourceAgentId` and store to an existing or
connector-managed internal registration and reject the implied update. The
word "update" in the create error supports testing this hypothesis but does
not prove that an object was found or changed.

### Delete/recreate control

GET and a description-only PATCH both succeeded against yesterday's retained,
user-owned disposable registration, while another create attempt remained
blocked. The experiment owner explicitly approved permanently deleting that
registration and accepted that a failed recreate could leave no replacement.

The prepared sequence is:

1. Save a final GET of the retained registration.
2. DELETE its known Registration ID once; expect `204`.
3. GET the deleted ID; expect `404`.
4. POST the exact earlier successful, identity-free user-owned body once.
5. On `201`, GET only the newly returned ID and replace the private saved ID.

The recreate body was mechanically compared with the original C3.3 body and
matches it.

| Observation | Result | Status |
| --- | --- | --- |
| Read retained registration before deletion | GET succeeded | supported |
| Update retained registration description | PATCH succeeded | supported |
| Delete retained registration | `204 No Content` | supported |
| Read deleted Registration ID | `404 Not Found` | supported |
| Recreate with the exact original successful body | HTTP `500`, `UnknownError`, and the same backend permission-denial message; no replacement ID returned | permission-denied |
| Old registration after the experiment | Permanently deleted | supported |
| Replacement registration | Not created by the observed response | unavailable |
| Failed recreate remote write outcome | No ID returned; a hidden or delayed outcome cannot be established | inconclusive |

An active, addressable old registration is therefore not sufficient to
explain the create denial. The result is state-dependent: initial create once
succeeded, GET/PATCH/DELETE subsequently worked, but recreate after confirmed
deletion failed with an update-oriented authorization message. Possible
explanations include a retained source-level mapping or tombstone, a separate
Registry Sync backing record, delayed deletion propagation, or a beta API
defect. The available APIs cannot distinguish them safely.

Do not use delete-and-recreate as recovery and do not automatically retry a
failed create. Preserve a known Registration ID and PATCH the existing
registration when available. If no supported source-to-registration lookup or
known ID exists, stop at the unresolved boundary rather than guessing,
creating another companion, or treating the 500 message as proof that adding
permissions will help.

### Four-source GCP create probe

Four existing GCP Registry Sync sources were evaluated independently. Exact
source identifiers and source timestamps remained in ignored evidence. Every
current POST used the same delegated user context, `GoogleVertexAI` store,
real source timestamps, user creator/owner, and no managing app, Blueprint ID,
Agent Identity ID, agent card, or optional description.

| Probe | Current create observation | Result |
| --- | --- | --- |
| 1 | The source that historically returned `201` was deleted (`204`), confirmed absent (`404`), then recreated with its original successful body | `500`; same backend permission-denial message |
| 2 | Selected notebook source, tested without either identity field | `500`; same backend permission-denial message |
| 3 | Additional existing GCP source, using verified Package Details metadata | `500`; same backend permission-denial message |
| 4 | Additional existing GCP source in another observed region, using verified Package Details metadata | `500`; same backend permission-denial message |

No current probe returned a Registration ID. Probes 3 and 4 therefore created
no confirmed cleanup object. Probe 1's historical registration remains
permanently deleted.

This establishes a bounded result for these four sources in this tenant and
time window: **new Agent Registration POSTs for the sampled Registry Sync
sources are permission-denied by the backend despite the documented delegated
scope and valid user ownership fields.** It does not establish that all GCP
sources, tenants, times, or future product versions behave the same way.

The common failure across distinct sources weakens a single-source collision
explanation. Combined with successful GET, PATCH, and DELETE on a known owned
registration, it indicates a create-specific backend authorization or service
state boundary. Current public evidence cannot distinguish an undocumented
create policy from a beta API defect.

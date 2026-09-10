# Lab 20: Observe Registry Sync identity gaps

The experiment's connection-name, companion source-ID, and durable mapping
conventions are recorded in
[Lab 20 design decisions](design-decisions.md).

## Experiment question

For an existing third-party Registry Sync inventory record, which identity
fields are visible through the supported Package Management API, and does that
API expose a documented identifier for the separate Agent Registration API?

## Entry points

This lab has two independent entry points. Use whichever matches what you
are trying to learn or demonstrate; they document the same API surface
from different angles and do not need to be run together.

1. **Trial 1: HTTP experiments and demos** -
   [`http-experiments.md`](http-experiments.md) is the entry
   point. It separates four Registry Sync identity experiments, one additional
   interaction-history experiment, and three companion lifecycle demos into
   independent folders. The first experiment is read-only. Every later write
   remains behind an explicit stop checkpoint. When the demos use the same
   companion, run add, then rename, then delete; deletion is last because it
   removes the object required by the rename demo. No Python, fixture, or
   hidden matching logic is involved; every HTTP request and response is
   inspected by hand, one step at a time.
2. **Trial 2: notebook pilot** -
   [`registry_sync_identity_walkthrough.ipynb`](notebook-pilot/registry_sync_identity_walkthrough.ipynb),
   an opt-in, explicitly-gated, offline-tested Python walkthrough of the
   full 16-step interim solution documented in
   [`identity-assignment-research.md`](identity-assignment-research.md#best-available-interim-solution-step-by-step),
   with the Python and API calls directly in each notebook step. See
   [Notebook walkthrough (opt-in control-plane pilot)](#notebook-walkthrough-opt-in-control-plane-pilot)
   below for its own setup, defaults, and boundary.

Both entry points retain the lab's non-production, approval, privacy, and
cleanup boundaries. The [Stop condition](#stop-condition) below ends the
initial read-only HTTP path; progressing to the separate notebook pilot
is **not** implied authorization to write. Review the notebook's top-level
switches before running it. The current #113 working copy enables the approved
fresh-companion experiment while keeping the earlier same-source
`CREATE_COMPANION` path disabled.

## Current boundary (read-only HTTP walkthrough)

The first walkthrough is read-only and uses one existing approved
non-production GCP sample. It stops after retrieving that package's details.
It does not create or update a Connected platforms connection, blueprint,
Agent Identity, package, or agent registration.

## Prerequisites

- VS Code with the REST Client extension.
- The existing single-tenant public-client app named
  `A365 Registry Experiment`.
- Public client flow enabled for that app.
- Delegated `CopilotPackages.Read.All` with the previously approved admin
  consent.
- An approved user who can inspect Agent 365 packages.
- One existing non-production GCP Registry Sync agent.

## Local configuration

Create `lab-20-registry-sync-identity-gaps/.env`:

```dotenv
A365_TENANT_ID=<directory-tenant-id>
A365_CLIENT_ID=<A365-Registry-Experiment-client-id>
A365_SAMPLE_PACKAGE_ID=
A365_SAMPLE_SOURCE_AGENT_ID_PATH=
```

The repository ignores `.env`. Never put real values into
the tracked files under `experiments/` or `demos/`,
tracked Markdown, chat, an issue, or a screenshot.

The fresh-companion customer demo uses additional `A365_DEMO_*` values listed
at the top of
[`demos/01-add-companion/demo.http`](demos/01-add-companion/demo.http).
Keep them in the same ignored `.env`. For the already-created companion, run
the file's read-only route and skip its Part 3B POST. The installed REST Client
uses its cached `aadV2Token` helper: the normal route requests only read
permissions, while the optional POST and DELETE request write permission only
when sent. The helper opens a browser and handles the token, but its delegated
flow still uses a device code internally. Use the notebook when an actual
localhost browser-callback login is required.

## Walkthrough

Open
[`experiments/01-package-registration-lookup/experiment.http`](experiments/01-package-registration-lookup/experiment.http)
and run one request at a time:

1. Start device-code authentication.
2. Complete sign-in in the browser.
3. Exchange the device code for an access token.
4. List packages and locally select one known GCP Registry Sync sample.
5. Put that sample's package ID in the ignored `.env`.
6. Get details for exactly that package ID and copy the provider source ID into
   the path-safe `.env` variable.
7. Try the Package ID and provider source ID independently as Registration IDs.
8. Stop and interpret the results before running a write experiment.

After completing that supported inventory walkthrough, use
[`undocumented-collection-probe.http`](experiments/01-package-registration-lookup/undocumented-collection-probe.http)
only for the separate,
read-only negative probe of the undocumented registration collection endpoint.
That probe requires delegated `AgentRegistration.Read.All`.

The disposable correlation experiment is defined in
[`experiments/02-provider-source-registration-create/experiment.http`](experiments/02-provider-source-registration-create/experiment.http).
It first creates a registration with the same provider-native `SourceAgentId`
but no identity fields. Run the create request only once and stop immediately
after recording its response.

Each request documents:

- the exact URL;
- the request method, headers, and body;
- the expected HTTP status and response shape;
- the values that must remain local; and
- the boundary on what the response can prove.

## Interpretation

The Package Management API documents:

```http
GET /v1.0/copilot/admin/catalog/packages
GET /v1.0/copilot/admin/catalog/packages/{id}
```

The Agent Registration API is a separate API:

```http
GET /beta/copilot/agentRegistrations/{id}
PATCH /beta/copilot/agentRegistrations/{id}
```

Do not pass a package ID to the Agent Registration API unless a supported
source explicitly establishes that relationship.

## Stop condition

Stop after Package Details if the response does not expose a documented Agent
Registration ID. Do not guess the ID, match by display name across APIs,
inspect undocumented portal calls, create a duplicate registration, or add
write permission.

## Cleanup (read-only HTTP walkthrough)

The read-only walkthrough creates no remote object. When the observation is
complete:

1. Close the REST Client response tabs containing tokens or real identifiers.
2. Delete the local `.env`.
3. Remove the delegated `AgentRegistration.Read.All` permission and its admin
   consent if they were added only for the completed collection probe.
4. Do not save token responses or raw package responses.

## Notebook walkthrough (opt-in control-plane pilot)

[`registry_sync_identity_walkthrough.ipynb`](notebook-pilot/registry_sync_identity_walkthrough.ipynb)
is a separate, **opt-in control-plane pilot** based on the interim solution in
[`identity-assignment-research.md`](identity-assignment-research.md), with all
logic in the notebook. There is no separate workflow class or Python module.
It is organized as **Prerequisites -> Prep -> Part 1 (platform/Blueprint groups)
-> Part 2 (agent identity) -> Part 3 (registration) -> Cleanup**. The research
report retains its detailed 16-step reference; the notebook has its own
three-part structure. It is **not** Registry Sync enrichment of the original
synchronized package and **not** a runtime-enforcement mechanism.

### Setup

From the repository root, enter the lab and create the environment using
[`pyproject.toml`](notebook-pilot/pyproject.toml) (Python >=3.12;
`requests`, `msal`,
`ipykernel`; test extras `nbformat`, `nbclient`). The project declares
`[tool.uv] package = false`, so use `uv sync`, not an editable
`pip install -e .` (there is no installable package to build):

```powershell
cd lab-20-registry-sync-identity-gaps\notebook-pilot

uv sync --extra test --index-url https://packagefeedproxy.microsoft.io/pypi/simple/
```

### Open flow

Never edit the tracked template in place. Copy it into the git-ignored
workspace, then open and run the copy, selecting Trial 2's own `.venv`
Python interpreter as the kernel (no separate `ipykernel install` into a
global user location is required):

```powershell
New-Item -ItemType Directory -Force -Path .\workspace | Out-Null
if (-not (Test-Path .\workspace\registry_sync_identity_walkthrough_three_parts.ipynb)) {
    Copy-Item .\registry_sync_identity_walkthrough.ipynb `
      .\workspace\registry_sync_identity_walkthrough_three_parts.ipynb
}
```

Open `workspace\registry_sync_identity_walkthrough_three_parts.ipynb` and
restart the kernel. The latest executed notebook, including its outputs and
temporary diagnostic cells, is preserved in
`workspace\registry_sync_identity_walkthrough_live.ipynb`. The earlier
pre-restructure run remains in
`workspace\registry_sync_identity_walkthrough_before_three_parts.ipynb`.
Older working copies remain for reference. Do not run them concurrently with
the clean three-part copy; they share the notebook's private state.
Back up any working copy before intentionally refreshing it. Private evidence
paths are relative to the lab root, not necessarily the kernel's current
working directory.

Use a trusted local kernel, not a shared or publicly exposed notebook
server. Do not enable verbose HTTP logging or print private response/state
objects while tokens are in memory.

For browser sign-in, use a tenant-owned, single-tenant public-client app. In
**Microsoft Entra admin center > App registrations > the login app >
Authentication**, register the exact `http://localhost` redirect under
**Mobile and desktop applications** (not Web or SPA), and set **Allow public
client flows** to **Yes** under Advanced settings. No client secret is needed.
Copy the **Application (client) ID** and **Directory (tenant) ID** from
Overview; do not confuse the client ID with the app's Object ID.

Under **API permissions**, add Microsoft Graph **Delegated permissions**, not
Application permissions. The notebook's Prerequisites section lists each
read, create, registration, and cleanup permission and whether admin consent
is required. Confirm the granted status before running. If a beta Agent
Identity permission is not visible, stop and use the tenant administrator's
approved permission process rather than substituting a broader permission.
See the official
[desktop app configuration](https://learn.microsoft.com/entra/identity-platform/scenario-desktop-app-configuration)
and [Microsoft Graph permissions reference](https://learn.microsoft.com/graph/permissions-reference).
Run the browser and kernel on the same local computer.

Prep creates one MSAL client for the kernel and requests the normal workflow
scopes once, including the create/write scopes only when `RUN_WRITES = True`.
Later phase calls reuse the unexpired token directly or use the same in-memory
MSAL cache before opening the browser. The account chooser is forced only for
the first interactive sign-in. Cleanup-only permissions, token expiry, MFA,
Conditional Access, or another Entra challenge can still require one more
browser interaction. The cache is memory-only: restarting the kernel or
rerunning `setup-code` requires a new sign-in, and no refresh token is saved to
disk.

### Run the three-part notebook

| Section | What to do |
| --- | --- |
| Prerequisites | Prepare Python/uv and a workspace copy; validate the single-tenant public-client app, localhost desktop redirect, public-client flow, delegated Graph permissions, and admin consent. |
| Prep | Configure targets, groups, and Graph paths in `configuration-variables`; configure approvals, create switches, and cleanup switches in `configuration-switches`; then run `setup-code`, complete the one normal-workflow browser sign-in, and read every visible Package List page. |
| Part 1 | Group the existing List packages results by `platform`, with no per-package detail calls. Manually confirm `REGISTRY_SYNC_PLATFORMS` using approved setup/portal context, define `BLUEPRINT_GROUPS`, and approve the plan with `GROUPS_APPROVED`. Read/create each group's Blueprint application and principal. |
| Part 2 | Read the selected agent's details, take `platform` directly from that response, and extract its exact source agent ID. Use `SELECTED_BLUEPRINT_GROUP`, approve membership with `AGENT_GROUP_APPROVED`, and resolve Part 1's saved binding. Read/create the Agent Identity using the Blueprint's `appId`. |
| Part 3 | GET the known companion registration and PATCH its identity fields. Use POST only for an explicitly confirmed first companion, not after a failed GET or lost ID. Read back the links and compare packages. |
| Cleanup | Retain by default. After separate approval, retire only a specifically selected, newly created object; check dependencies and any Blueprint/principal cascade. |

Keep `RUN_WRITES = False` for inspection. Enable it and only the required
`CREATE_BLUEPRINT`, `CREATE_PRINCIPAL`, `CREATE_IDENTITY`, or
`CREATE_COMPANION` switches after approval. Ordinary settings and action
switches are kept in two separate cells at the start; later cells consume them
without resetting them. Routine POST/PATCH operations no longer ask for `APPLY` by
default; set `CONFIRM_EACH_WRITE = True` in Prep
to restore per-write prompts. Deletion always asks for `APPLY`, and a first
companion registration always requires `FIRST`.
Use `CREATE_COMPANION = False` when a companion is already known for the exact
selected source, and recover its Registration ID. Choose this mode in
`configuration-switches` before running 3.1.
The earlier retained HTTP companion has a different exact source ID from the
current notebook selection; do not reuse it for this selection.

Cell 1.2 defaults the sponsor to the signed-in operator without asking for an
ID. It preserves any valid sponsor already saved, including a different
approved sponsor. Group-plan approval must include this sponsorship choice.
For an override, set `state['sponsor_id']` privately before running 1.2;
never paste a real ID into a tracked cell.
An override requires the approved sponsor's **Entra user Object ID** (Users >
the sponsor > Overview), not an app/client ID, tenant ID, or placeholder such
as `tbc`. An invalid saved value prompts again; invalid new input is rejected
before saving. This is a GUID-format check, not proof of user existence or
sponsorship approval. Creation payloads also reject malformed sponsor IDs
before POST, including when an older kernel still holds an invalid value.
Correcting the sponsor does not clear or resolve a previous failed write.

When creation is explicitly selected, the notebook no longer asks whether
an existing Blueprint, Agent Identity, or registration ID is available.
Saved objects are always read/reused first. In reuse mode, a missing saved
ID still prompts privately because the notebook must not guess it.
Only select creation after confirming the object has not already been
created; a lost ID or failed read is not evidence of absence.
Tenant/client IDs are requested only when not saved. Later phases normally
reuse the Prep sign-in, while new cleanup scopes, expiry, and tenant-required
MFA or Conditional Access can still reopen the browser. Selection between
ambiguous packages also remains.

The inventory groups all visible platforms, but a platform label alone does
not establish Registry Sync origin. Part 1.1 uses only the List response;
Part 1.2 requires manual confirmation of the relevant Registry Sync platforms.
Part 2 fetches details only for the selected agent's matching candidates and
inspects their source metadata. The observed GCP markers are not a universal
provider contract. Failed reads or missing/ambiguous source metadata stop
that agent's path, not trigger automatic creation. Connections remain
provenance only, never a platform/group lookup.

`BLUEPRINT_GROUPS` is an explicit group-level plan, not an instruction to create
an identity for every package. This notebook scopes group labels by platform.
Part 2 assigns only one approved source agent, using the saved
`blueprint_bindings[platform][group]`. An existing group's IDs are reused;
the earlier flat single-group state can be imported without re-creation.

### Private values and basic safeguards

Use an OS-protected local folder: `.gitignore` is not access control.
The notebook saves returned IDs and relevant responses in
`evidence\notebook-pilot\state.json`; ambiguous candidates, if any,
are available in `candidates.json` in the same directory. Part 1 no longer
creates `inventory-details.json`; any existing copy is historical evidence,
not an input to this notebook. Tokens are kept only in
kernel memory. Do not print raw responses or paste IDs into tracked cells.

A small `pending_write` entry is saved before each mutation. If a request
fails or its result is uncertain, stop and reconcile it; do not delete that
entry just to retry a POST. Successful results are saved immediately so a
rerun can reuse actual IDs. Run only one copy/kernel against this file.

The simple notebook does not read, overwrite, or delete the previous
helper-based notebook's `evidence\notebook-test-v2\` directory, the HTTP
experiment's `.env`, or its evidence. If you previously created objects,
recover their existing IDs rather than assuming the new state means they
do not exist. The research report still describes broader grouping and
migration considerations; this notebook prepares explicitly chosen groups,
then assigns one approved agent rather than processing a fleet.

### Replay a failed notebook POST in REST Client

The observed Part 3.2 failure returned HTTP `500` / `UnknownError` with a
backend permission-denial message. The failed request's decoded token
contained `AgentRegistration.ReadWrite.All`; its caller matched the submitted
creator and an owner. These observations do not establish that every backend
authorization check passed, that the identity fields caused the failure, or
that the POST made no change.

Use
[`registration-identity-replay-template.http`](notebook-pilot/registration-identity-replay-template.http)
as an export template, not as a request to send directly. The current notebook
helper retains the most recent unexpected HTTP response as `failed_response`
in kernel memory. Immediately after the failed Part 3.2 request, run this
temporary cell. It copies the actual prepared request rather than reconstructing
it from possibly changed notebook variables or the earlier HTTP sample:

```python
assert failed_response is not None, 'No captured HTTP failure is available in this kernel.'
req = failed_response.request
assert req.method == 'POST' and req.url == 'https://graph.microsoft.com/beta/copilot/agentRegistrations', 'Not the expected registration POST.'
body = req.body.decode('utf-8') if isinstance(req.body, bytes) else req.body
assert isinstance(body, str) and isinstance(json.loads(body), dict), 'Expected a JSON request body.'
text = (LAB_ROOT / 'notebook-pilot' / 'registration-identity-replay-template.http').read_text(encoding='utf-8')
captured = {
    'capturedAuthorization': req.headers['Authorization'],
    'capturedContentType': req.headers['Content-Type'],
    'capturedAccept': req.headers['Accept'],
    'capturedODataVersion': req.headers['OData-Version'],
    'capturedRequestBody': body,
}
for name, value in captured.items():
    marker = '{{' + name + '}}'
    assert text.count(marker) == 1, 'Unexpected replay template.'
    text = text.replace(marker, value)
with (PRIVATE / 'registration-create-replay.http').open('x', encoding='utf-8', newline='\n') as output:
    output.write(text)
print({'private_replay_file_created': True, 'request_sent': False})
```

If `failed_response` is undefined or `None`, the failed request came from an
older helper version, the kernel was restarted, or another cell cleared the
in-memory response. Rerunning Part 3.2 only to recreate that variable is not
safe. If an explicitly approved replay is still required, prepare the current
request without sending it:

```python
assert access_token and identity_verified and CREATE_COMPANION, 'Current authenticated creation context is required.'
assert state.get('pending_write', {}).get('record') == 'registration', 'Expected the unresolved registration marker.'
for timestamp in (source.get('CreatedDateTime'), source.get('LastModifiedDateTime')):
    assert isinstance(timestamp, str) and datetime.fromisoformat(timestamp).tzinfo is not None, 'Invalid source timestamp.'
replay_body = {
    'displayName': f'{TARGET_NAME} - identity companion',
    'description': 'Disposable companion; original Registry Sync record retained',
    'createdBy': state['operator_id'],
    'ownerIds': [state['operator_id']],
    'sourceAgentId': state['source_agent_id'],
    'originatingStore': agent_platform,
    'sourceCreatedDateTime': source['CreatedDateTime'],
    'sourceLastModifiedDateTime': source['LastModifiedDateTime'],
    'agentIdentityBlueprintId': blueprint['appId'],
    'agentIdentityId': agent_identity['id'],
}
req = requests.Request(
    'POST',
    GRAPH + REGISTRATIONS,
    headers={
        'Authorization': 'Bearer ' + access_token,
        'Accept': 'application/json',
        'OData-Version': '4.0',
    },
    json=replay_body,
).prepare()
body = req.body.decode('utf-8') if isinstance(req.body, bytes) else req.body
text = (LAB_ROOT / 'notebook-pilot' / 'registration-identity-replay-template.http').read_text(encoding='utf-8')
captured = {
    'capturedAuthorization': req.headers['Authorization'],
    'capturedContentType': req.headers['Content-Type'],
    'capturedAccept': req.headers['Accept'],
    'capturedODataVersion': req.headers['OData-Version'],
    'capturedRequestBody': body,
}
for name, value in captured.items():
    marker = '{{' + name + '}}'
    assert text.count(marker) == 1, 'Unexpected replay template.'
    text = text.replace(marker, value)
destination = PRIVATE / 'registration-create-replay.http'
assert not destination.exists(), 'A private replay file already exists; inspect it instead of overwriting it.'
with destination.open('x', encoding='utf-8', newline='\n') as output:
    output.write(text)
print({'private_replay_file_created': True, 'request_sent': False, 'source': 'reconstructed current context'})
```

This fallback is a reconstruction of the current notebook variables, not proof
that every header and value matches the earlier failed request. Record that
difference as a new experiment condition.

The generated file is
`evidence\notebook-pilot\registration-create-replay.http`.
It contains a live bearer token and real identifiers: keep it local, do not
print its contents, and remove its bearer value or delete the file when the
approved diagnostic sequence is finished. This is an
explicit, temporary exception to the notebook's normal memory-only token
handling. The cell refuses to overwrite an existing capture and does not
change `state.json` or send a request.

REST Client does not run the notebook's pending-write safeguards. Before
sending, reconcile the earlier outcome or obtain explicit approval for one
disposable replay acknowledging possible duplication. Do not clear
`pending_write` just to retry. Preserve the captured body and token so only the
HTTP client changes; if the token expired, stop and record any subsequent
re-authentication as a separate condition.

After approval, open the generated file and select **Send Request** once.
Save the status and response only in the same ignored directory, using
`registration-create-replay-response.json` for the response body. A `201`
must be followed by a GET using its returned Registration ID and reconciliation
with the notebook before resuming Part 3.2. Another error is a stop, not an
automatic retry. Do not guess IDs, substitute the earlier companion, or remove
identity fields as an assumed fix.

The approved REST Client replay also returned HTTP `500` / `UnknownError`
with the same backend denial. It did not resolve the failure. The captured
token was unexpired, and the source, identity references, creator, and
permission/owner comparisons matched the notebook. This isolates neither a
bad identity reference nor a backend authorization rule as the cause; it only
shows that changing clients did not help. No further automatic writes are
allowed; an additional disposable condition requires an explicit decision.

### Identity-free baseline after the failed replay

The experiment owner selected a separate baseline: remove both
`agentIdentityBlueprintId` and `agentIdentityId` from the POST body together,
keeping every other JSON value unchanged. This removes request fields, not
the actual Entra Blueprint or Agent Identity objects. The restored private
`registration-create-replay.http` is now this baseline, with request name
`createIdentityFreeBaseline`; the original captured body remains unchanged in
`registration-create-replay-request.json`.

Retain the original token while valid and send the baseline at most once
after approval. A successful identity-free create would demonstrate that
baseline only; it would not identify which omitted field affected the earlier
failure. Save its response separately as
`registration-create-baseline-response.json`. On `201`, preserve the returned
Registration ID and GET that exact registration before considering a
separately approved PATCH adding one identity field at a time. Do not create
another registration to add a field. On another error, stop and retain the
pending-write evidence. The HTTP experiment does not automatically reconcile
or clear the notebook's state.

The identity-free baseline also returned HTTP `500` with the same denial.
A subsequent GET of an explicitly supplied known registration, using the
captured token, returned `200`: the caller is its creator and an owner, it
has no nonempty managing-app or identity references, and it belongs to a
different exact source on the same platform. This confirms read access to
that control, not permission to create the selected source's registration.
No POST followed that GET. Do not substitute the control ID into the notebook
or attach the selected agent's identity to that other registration.

Both yesterday's device-code HTTP flow and the current browser/replay flow are
delegated user flows through the same public-client app and tenant. The current
token contains `AgentRegistration.ReadWrite.All`, which is the least-privileged
delegated permission documented for create; it also contains the registration
read scope. It has an `scp` claim rather than an application `roles` claim.
Therefore, do not add the same permission again, switch to application
permission, or grant a broader directory role as a speculative workaround.
The public client still has a client ID: "delegated" means the app calls Graph
on behalf of the signed-in user, not that the app registration is absent.

If a future environment genuinely lacks the write scope, configure it on the
existing login app under **Microsoft Entra admin center > App registrations >
the login app > API permissions > Add a permission > Microsoft Graph >
Delegated permissions > AgentRegistration.ReadWrite.All**, obtain the required
consent, and sign in again so a newly issued token includes the scope. That is
not required for the captured failure because the scope is already present.
Portal evidence also shows that the existing login app has delegated
`AgentRegistration.ReadWrite.All` configured with admin consent granted.
Because the issued token contains that same scope, there is no configuration
or token-delivery gap to fix by adding the permission again.

### Reuse the earlier successful HTTP authentication flow

The ignored file
`evidence\notebook-pilot\registration-create-current-agent-correlation.http`
is a private copy of
`experiments\02-provider-source-registration-create\experiment.http`
configured for
today's selected agent. It retains the earlier device-code delegated flow,
the same `AgentRegistration.ReadWrite.All` scope request, and `/me` as creator
and owner. It replaces the old package/source settings with the selected
agent's captured values and removes the earlier created Registration ID. Its
POST intentionally omits `managedByAppId`, `agentIdentityBlueprintId`, and
`agentIdentityId`, matching both the earlier successful shape and today's
identity-free baseline body.

No bearer token is embedded before sign-in and no request was sent while
preparing the file. Run only these requests, one at a time:

1. `currentAgentDeviceCode`
2. `currentAgentToken`, after completing the browser sign-in
3. `currentAgentUser`; require `200`
4. `createCurrentAgentRegistration`, at most once after separate write approval

Do not select **Send All**. Stop after the create response. On `201`, save the
returned Registration ID privately and read that exact registration before
any identity PATCH. On any error, do not resend automatically. The notebook's
existing pending-write record remains unresolved throughout this HTTP control.

The experiment owner reported that the copied device-code flow was again
blocked at the create step. Do not add more permissions in response: the
configured delegated consent and actual token scope have both been verified.
Treat the remaining boundary as source/object-specific backend authorization
or an API defect until a controlled test or product diagnostics distinguish
them.

### Notebook local artifacts and cleanup

Leave `DELETE_OBJECT = None` in `configuration-switches` to preserve the
earlier retention decision. Optional deletion is limited to objects created by
this notebook, one at a time, after dependency review and confirmation. It does
not delete provider agents, Registry Sync connections, or reused objects. For
Blueprint cleanup, `CLEANUP_PLATFORM` and `CLEANUP_GROUP` select any newly
created Part 1 group, not necessarily the selected agent's group. Review all
children first.
If only a principal was created for a reused Blueprint, request owner-led
retirement of that principal; do not delete the reused Blueprint.

Keep `state.json` while objects or uncertain outcomes need its mappings.
After the retention decision, clear notebook outputs and restart/stop the
kernel. Remove only files no longer needed: the simple run's `state.json`,
`inventory-details.json`, `candidates.json`, and an interrupted `state.tmp`
after reconciliation; the exact working notebook, preserved pre-restructure
notebook, and their checkpoints; or this lab's `.venv` and
`uv.lock` when finished. Do not delete the whole workspace, shared package
caches, or the older experiment's state. No tracker or sibling-checkout
changes are part of this notebook.
Keep `registration-create-replay.http` while the approved diagnostic sequence
is active. At the end, remove its bearer value or delete that specific file.
Preserve a token-free JSON body capture if needed for investigation; do not
overwrite the original `registration-create-replay-request.json` with a later
experiment condition.
Keep that request capture, `registration-create-error.json`, the safe
`registration-create-replay-result.json` summary, and any
`registration-create-replay-response.json` or
`registration-create-baseline-response.json` only while needed for
reconciliation, then delete those specific files. A safe summary of a
user-reported response is not a raw response capture. The baseline's safe
summary is `registration-create-baseline-result.json`. The read control adds
`registration-known-id-get-input.json` (private target),
`registration-known-id-get-response.json` (raw response), and
`registration-known-id-get-result.json` (safe comparisons); retain these only
for the investigation and remove those specific files afterward. Remove temporary
recovery, token-diagnostic, and export cells from the working copy, clear their
outputs, and stop the kernel when the investigation is complete.
The current-agent correlation copy contains real identifiers and, after its
authentication steps run, REST Client response variables can expose a token
in the editor session. Keep the file and response tabs private, then delete
that specific ignored file and close its response tabs after reconciliation.

### Delete/recreate control for the retained correlation registration

The experiment owner explicitly approved deleting yesterday's retained,
user-owned disposable registration and accepted that the operation cannot be
undone. If the following recreate fails, there might be no replacement.

In
`experiments\02-provider-source-registration-create\experiment.http`,
run the prepared requests individually:

1. `getCreatedRegistrationAfterDescriptionUpdate`; save its latest body.
2. `deleteCreatedRegistration`; require `204`.
3. `getDeletedRegistration`; require `404`.
4. `recreateCorrelationRegistrationAfterDelete`; send once and stop.
5. Only after `201`, run `getRecreatedRegistration` using the returned ID.

The recreate body matches the original successful C3.3 body and omits
`managedByAppId`, `agentIdentityBlueprintId`, and `agentIdentityId`. Do not
use **Send All**, do not repeat DELETE or POST automatically, and do not run
the recreate before both deletion checks complete. After a successful
readback, replace `A365_CREATED_REGISTRATION_ID` in the ignored `.env` with
the new ID before any later cleanup. If recreate fails, retain the response
and stop; the old registration is permanently deleted.

Observed result: the pre-delete GET and description PATCH succeeded, DELETE
returned `204`, and the deleted ID returned `404`. Recreating with the exact
original successful body then returned HTTP `500` with the same backend
permission-denial message and no replacement ID. Do not run the DELETE or
recreate requests again. Clear the deleted ID from
`A365_CREATED_REGISTRATION_ID`; retain its historical value only in protected
evidence already captured before deletion.

This rules out an active, addressable old registration as the complete
explanation, but it does not prove immediate removal of every backend
source-level mapping. Treat retained tombstones, Registry Sync backing state,
eventual consistency, and beta API defects as unresolved. The practical rule
is to PATCH a known existing registration and never use delete-and-recreate
as recovery. When no known Registration ID or supported source lookup exists,
stop and escalate with protected request identifiers rather than retrying POST
or adding broader permissions.

### Four-source GCP create result

Four existing GCP Registry Sync source identifiers were tested independently
with the same delegated user context. Each current create request used real
Package Details timestamps, the signed-in user as creator and owner, and no
description, managing app, Blueprint ID, Agent Identity ID, or agent card.

All four current create observations returned HTTP `500` with the same backend
permission-denial message and no Registration ID. Two were already established
by the deleted-source recreate and Test V2 baseline; two additional source
probes reproduced the result. Do not run any of the four POSTs again.

This is a bounded tenant/time-window result, not a universal GCP claim.
Successful GET/PATCH/DELETE on a known owned registration still demonstrates
that existing-object operations can remain valid while create is blocked.
Treat new companion registration as unavailable for the sampled Registry Sync
sources. No new cleanup object was confirmed for probes 2-4; the probe 1
registration remains permanently deleted.

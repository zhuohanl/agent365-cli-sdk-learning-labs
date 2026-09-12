# Demo 3 mapping lifecycle model

> Status: exercised by Demo 3 and adopted as the Lab 20 experimental mapping
> model. See `findings.md` for the sanitized observations and
> `docs/design-decisions.md` for the resulting handling rule.

## Question

Can one durable mapping support:

- temporary Registry Sync Package disappearance;
- relocation of the same provider source to a new Package ID;
- confirmed provider-source deletion;
- ordered companion Registration, companion Package, and Agent Identity
  retirement;
- resumable partial cleanup;
- dedicated Blueprint garbage collection;
- retention of shared Blueprints; and
- a permanent tombstone that preserves former identifiers?

The prototype should maintain the mapping from explicit observations and
approved actions. It must not call Microsoft Graph, a provider API, or mutate
any remote object.

## Separate lifecycle concerns

The mapping has three independent status dimensions:

1. `lifecycleStatus` describes retirement of one scoped provider source and
   its source-owned managed objects. `lifecycleReason` explains why that
   aggregate workflow is in its current state.
2. `nameSyncStatus` continues to describe display-name reconciliation.
3. `blueprintCleanup.status` describes cleanup of the Blueprint group after
   source retirement.

Name synchronization must not be inferred from retirement state. Blueprint
cleanup must not prevent a source from becoming retired when a shared
Blueprint still has active members.

## Common object state

Every tracked object uses the same fields:

```json
{
  "status": "pending",
  "reason": "awaiting-removal-propagation",
  "lastCheckedAt": "2026-09-13T00:00:00Z",
  "statusChangedAt": "2026-09-13T00:00:00Z",
  "retiredAt": null
}
```

The fields mean:

| Field | Meaning |
| --- | --- |
| `status` | Current object lifecycle state. |
| `reason` | Observable fact or safety gate that explains the current state. |
| `lastCheckedAt` | Most recent time evidence for this object was evaluated. |
| `statusChangedAt` | Time at which `status` last changed. |
| `retiredAt` | Time retirement was verified; null before retirement. |

`statusChangedAt` remains unchanged when a later observation confirms the same
status. `lastCheckedAt` advances on every evaluated observation.

## Status vocabulary

Per-object status uses only:

| Status | Meaning |
| --- | --- |
| `active` | Verified to exist and expected to remain in use. |
| `pending` | Waiting for evidence, propagation, approval, or a safe next action. |
| `retired` | Verified to be absent from active use; historical IDs remain in the mapping. |
| `blocked` | Cleanup cannot safely continue without intervention. |

`partial` is not a per-object status. It is an aggregate status showing that
some, but not all, required objects have retired.

The source-level `lifecycleStatus` uses:

| Status | Meaning |
| --- | --- |
| `active` | The provider source is present and retirement has not started. |
| `pending` | Absence or deletion is being confirmed, but no source-owned managed object has retired. |
| `partial` | At least one source-owned managed object has retired and cleanup is incomplete. |
| `retired` | Source retirement and all required source-owned cleanup are verified. |
| `blocked` | A required source-retirement step cannot safely continue. |

`blocked` takes precedence over `partial`.

## Tracked objects

Source retirement tracks:

- `providerSource`;
- `registrySyncPackage`;
- `companionRegistration`;
- `companionPackage`; and
- `agentIdentity`.

`registrySyncPackage` is the Agent 365 inventory representation of the
provider source. It is not named `providerPackage`, because the third-party
provider does not own the Registry Sync Package.

Blueprint group cleanup separately tracks:

- `blueprint`; and
- `blueprintPrincipal`.

This separation matters because an Agent Identity and Registration belong to
one source, while a shared Blueprint belongs to a group. A shared Blueprint
can remain active after one member source is retired.

## Proposed mapping extension

The current identifiers, relationships, names, and former IDs remain
unchanged. The prototype replaces the ambiguous top-level `status` field with
`lifecycleStatus`; keeping both would allow contradictory values such as
`status: active` and `lifecycleStatus: retired`.

The prototype adds:

```json
{
  "lifecycleStatus": "active",
  "lifecycleReason": "source-active",
  "retirement": {
    "missingSince": null,
    "sourceRetirementApprovedAt": null,
    "companionRegistrationRetirementApprovedAt": null,
    "agentIdentityRetirementApprovedAt": null,
    "gracePeriodEndsAt": null,
    "providerSource": {
      "status": "active",
      "reason": "observed-via-registry-sync",
      "lastCheckedAt": "2026-09-13T00:00:00Z",
      "statusChangedAt": "2026-09-13T00:00:00Z",
      "retiredAt": null
    },
    "registrySyncPackage": {
      "status": "active",
      "reason": "observed-in-inventory",
      "lastCheckedAt": "2026-09-13T00:00:00Z",
      "statusChangedAt": "2026-09-13T00:00:00Z",
      "retiredAt": null
    },
    "companionRegistration": {
      "status": "active",
      "reason": "verified-present",
      "lastCheckedAt": "2026-09-13T00:00:00Z",
      "statusChangedAt": "2026-09-13T00:00:00Z",
      "retiredAt": null
    },
    "companionPackage": {
      "status": "active",
      "reason": "verified-present",
      "lastCheckedAt": "2026-09-13T00:00:00Z",
      "statusChangedAt": "2026-09-13T00:00:00Z",
      "retiredAt": null
    },
    "agentIdentity": {
      "status": "active",
      "reason": "verified-present",
      "lastCheckedAt": "2026-09-13T00:00:00Z",
      "statusChangedAt": "2026-09-13T00:00:00Z",
      "retiredAt": null
    }
  },
  "blueprintCleanup": {
    "status": "active",
    "reason": "source-active",
    "blueprint": {
      "status": "active",
      "reason": "verified-present",
      "lastCheckedAt": "2026-09-13T00:00:00Z",
      "statusChangedAt": "2026-09-13T00:00:00Z",
      "retiredAt": null
    },
    "blueprintPrincipal": {
      "status": "active",
      "reason": "verified-present",
      "lastCheckedAt": "2026-09-13T00:00:00Z",
      "statusChangedAt": "2026-09-13T00:00:00Z",
      "retiredAt": null
    }
  }
}
```

## Candidate transitions

The Python prototype should apply named events rather than allow arbitrary
status editing:

Each event also has an owner. A scheduled reconciler may record observations,
but it must never create an approval event. Reaching a deadline means "ready
for a decision", not "approved".

| Event | Owner | Expected result |
| --- | --- | --- |
| `source-missing` | Scheduled reconciler | Mark the source and Registry Sync Package pending; record `missingSince` from a complete healthy inventory observation. |
| `configure-simulation-grace` | Human experiment operator | Record an explicitly approved shortened disposable-experiment grace period while preserving the production candidate duration. This event is not part of normal production reconciliation. |
| `source-relocated` | Scheduled reconciler | Record the replacement Package ID found through the same scoped provider source key and return source observation to active. |
| `source-retirement-approved` | Human approver | After the deadline and a fresh healthy inventory observation, record the explicit decision to retire the source mapping and mark the Registration pending its own approval. The reconciler may prepare the evidence but cannot emit this event. |
| `registration-retirement-approved` | Human approver | Record the separate approval to retire the companion Registration; keep it pending until deletion is verified. |
| `registration-retired` | System verifier | After an approved action runner sends the Registration DELETE, record retirement only when a read of the same ID verifies absence. Mark the companion Package pending propagation. |
| `companion-package-pending` | Scheduled reconciler | Record another complete inventory observation while the companion Package is still present or propagation remains incomplete. |
| `companion-package-retired` | Scheduled reconciler | Retire the companion Package after complete healthy inventory verifies its absence; mark the Agent Identity pending dependency review and approval. |
| `identity-retirement-approved` | Human approver | Record the separate approval to retire the Agent Identity; keep it pending until deletion is verified. |
| `identity-retired` | System verifier | After an approved action runner sends the Agent Identity DELETE, record retirement only when the active-resource read verifies absence. |
| `block-object` | Reconciler or human reviewer | Record a concrete permission, dependency, policy, or verification failure. Automated code may use this only for an observed failure; a human may use it for a reviewed dependency or safety concern. |
| `blueprint-cleanup-started` | Human approver | Record the separate decision to clean up a confirmed-empty dedicated Blueprint group. A scheduler may identify a cleanup candidate but cannot start cleanup. |
| `blueprint-retired` | System verifier | After the approved Blueprint DELETE, record retirement only when the Blueprint active-resource read verifies absence. |
| `blueprint-principal-retired` | Scheduled reconciler or system verifier | Record retirement only when the principal read verifies the cascade has completed. Do not infer it only from Blueprint absence. |

The prototype should reject unsafe ordering. For example, it should not retire
the Agent Identity while the companion Registration is still active, and it
should not begin dedicated Blueprint cleanup before source retirement is
complete.

## Reconciler, approval, action, and verification boundaries

The production-shaped workflow has four separate responsibilities:

1. **Scheduled reconciler:** periodically reads complete Package inventory and
   mapped objects. It records observed presence, absence, relocation,
   propagation, deadlines, and failures. It may move objects between
   `active`, `pending`, `retired`, and `blocked` only when the transition is
   based on verified read evidence.
2. **Human approver:** reviews the collected evidence and records explicit
   approval for source retirement, Registration retirement, Agent Identity
   retirement, or dedicated Blueprint cleanup. These approvals are separate
   decisions and must include actor and time in the durable audit record.
3. **Action runner:** sends a destructive remote request only after the
   matching approval field is present. It uses the locked mapped ID and does
   not update the object to `retired` merely because DELETE returned success.
4. **System verifier:** re-reads the exact object and complete inventory as
   required. Only verified absence produces a `*-retired` event. Timeout,
   permission failure, or an unexpected response leaves the object pending or
   blocked for later reconciliation.

For example, the scheduled reconciler can detect that the source has remained
absent beyond `gracePeriodEndsAt` and set
`lifecycleReason: awaiting-source-retirement-approval`. It must stop there.
Only a human decision can populate `sourceRetirementApprovedAt`. Likewise,
companion Package disappearance can be recorded automatically, but it can
only make the Agent Identity ready for review; it cannot approve or delete the
Identity.

The local Python prototype represents these decisions and observations as
events, but it does not authenticate an approver, schedule reconciliation, or
call remote APIs. A production implementation must keep those capabilities in
separate interfaces so that a scheduled job cannot impersonate a human
approval.

The simulation event must derive its deadline from the real `missingSince`
timestamp. It must not accept a fabricated future event time as a substitute
for waiting. A simulation mapping records:

```json
{
  "retirementPolicy": {
    "mode": "experiment-simulation",
    "gracePeriod": "PT15M",
    "productionCandidateGracePeriod": "P14D",
    "reason": "validate-disposable-delete-lifecycle",
    "configuredAt": "2026-09-13T00:00:00Z"
  }
}
```

The shortened period validates state transitions only. It does not establish
the correct production grace period.

The first prototype deliberately requires companion Package retirement before
Agent Identity retirement. This is a testable conservative rule, not yet a
final design decision. Demo 3 evidence may show that independent observation
is sufficient instead.

## Reason vocabulary

Reasons explain why an object has its current status. Initial candidates are:

```text
observed-in-inventory
observed-via-registry-sync
provider-presence-unconfirmed
verified-present
not-observed-in-complete-inventory
package-details-inconclusive-dependency-failure
retired-by-sustained-registry-absence-policy
absence-confirmed-after-grace-period
approval-required
retirement-approved
awaiting-removal-propagation
dependency-found
shared-group-not-empty
permission-denied
deletion-verified
```

Workflow reasons such as `source-active`, `awaiting-healthy-sync`,
`awaiting-grace-period`, `companion-retirement-pending`,
`companion-retirement-in-progress`, `required-step-blocked`, and
`source-retired` belong in `lifecycleReason`, not in an individual object's
`reason`.

Blueprint group workflow reasons such as `source-active`,
`source-retirement-incomplete`, `source-retired-awaiting-cleanup`, and
`shared-group-not-empty` belong in `blueprintCleanup.reason`.

The prototype may expose a free-form reason for blocked states because the
experiment cannot enumerate every permission, dependency, or policy failure.

## Tombstone behavior

Retirement updates status and timestamps but never removes:

- the scoped provider source key;
- former Package IDs;
- companion Registration ID;
- companion Package ID;
- Agent Identity ID;
- Blueprint IDs;
- historical display names; or
- assignment and approval references.

If a Package is relocated before deletion is confirmed, the current
`packageId` changes and the previous value is appended to
`previousPackageIds`.

After `lifecycleStatus` reaches `retired`, a reappearing provider source must
not automatically reactivate the mapping or create a replacement companion.
That case remains an explicit reconciliation question for the final design.

## Results from the prototype and Demo 3

1. `lifecycleStatus` avoided conflict with `nameSyncStatus` and replaced the
   old ambiguous top-level `status`.
2. Process-level timestamps recorded the first missing observation, grace
   deadline, and separate approvals. Per-object timestamps independently
   recorded observation and retirement progress.
3. The common `pending` state remained usable because `reason` distinguished
   propagation, approval, and dependency-review waits.
4. The conservative Demo 3 order required verified companion Package absence
   before Agent Identity approval and deletion. Registration deletion removed
   the Package by the first subsequent complete inventory, but did not remove
   the Agent Identity.
5. Dedicated Blueprint cleanup remained separate from source retirement and
   began only after the dedicated group was confirmed empty. Shared Blueprint
   cleanup remains prohibited for one source.
6. In this run, deleting the dedicated Blueprint also removed its principal by
   the first follow-up read. The mapping still tracked and verified both
   objects independently.
7. Automatic reactivation of a retired tombstone remains prohibited. A
   reappearing source requires an explicit future reconciliation decision.

## Running the local prototype

The prototype reads one mapping, applies one transition, and writes a complete
replacement mapping. It never calls a remote API.

Initialize the current Demo 2 mapping:

```powershell
python demos\03-delete-companion\prototype_retirement_mapping.py `
  --mapping evidence\demos\02-rename-companion\mapping-after-rename.json `
  --output evidence\demos\03-delete-companion\mapping.json `
  initialize
```

Apply one observed event:

```powershell
python demos\03-delete-companion\prototype_retirement_mapping.py `
  --mapping evidence\demos\03-delete-companion\mapping.json `
  --output evidence\demos\03-delete-companion\mapping.json `
  event source-missing `
  --grace-period-ends-at "2026-09-14T00:00:00Z"
```

The same file can be used as input and output because the complete input is
validated and loaded before the replacement file is written. Use `--at` to
provide a fixed timestamp for reproducible walkthroughs.

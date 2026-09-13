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
- automatic empty-Blueprint garbage collection;
- retention of non-empty Blueprints; and
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
    "lastHealthyAbsenceObservedAt": null,
    "lastSourceObservation": "present",
    "lastSourceObservedAt": "2026-09-13T00:00:00Z",
    "retirementApprovedAt": null,
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
    "remainingAgentIdentities": null,
    "pendingIdentityReservations": null,
    "lastCheckedAt": null,
    "membershipEvidence": null,
    "eligibilityInvalidatedAt": null,
    "blueprintDelete": {
      "status": "not-started",
      "startedAt": null,
      "verifiedAt": null
    },
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
  },
  "reconciliationHold": {
    "status": "clear",
    "reason": null,
    "observedAt": null,
    "resolvedAt": null
  },
  "safetyWatermarkAt": "2026-09-13T00:00:00Z"
}
```

## Candidate transitions

The Python prototype should apply named events rather than allow arbitrary
status editing:

Each event also has an owner. A scheduled reconciler may record observations,
but it must never create the single approval event. Reaching a deadline means
"ready for a decision", not "approved".

| Event | Owner | Expected result |
| --- | --- | --- |
| `source-missing` | Scheduled reconciler | Mark the source and Registry Sync Package pending; record `missingSince` from a complete healthy inventory observation. |
| `configure-simulation-grace` | Human experiment operator | Record an explicitly approved shortened disposable-experiment grace period while preserving the production candidate duration. This event is not part of normal production reconciliation. |
| `source-relocated` | Scheduled reconciler | Record the replacement Package ID found through the same scoped provider source key and return source observation to active. |
| `source-reappeared` | Scheduled reconciler | If the source returns after retirement approval, preserve completed object states and the tombstone, then create a separate reconciliation hold that blocks all remaining destructive work. |
| `source-reappearance-cleared` | Human reviewer or reconciler with authoritative evidence | Clear only a false-positive or stale-observation hold while preserving approval and completed retirement timestamps. A genuine reappearance remains blocked for explicit lifecycle reconciliation. |
| `retirement-approved` | Human approver | After the deadline, a fresh healthy inventory observation, and dependency review, approve one retirement plan covering the source, companion Registration, dedicated Agent Identity, and automatic cleanup of the Blueprint if it becomes empty. The reconciler may prepare the evidence but cannot emit this event. |
| `registration-retired` | System verifier | After an approved action runner sends the Registration DELETE, record retirement only when a read of the same ID verifies absence. Mark the companion Package pending propagation. |
| `companion-package-pending` | Scheduled reconciler | Record another complete inventory observation while the companion Package is still present or propagation remains incomplete. |
| `companion-package-retired` | Scheduled reconciler | Retire the companion Package after complete healthy inventory verifies its absence; mark the Agent Identity ready for automatic deletion under the existing retirement approval. |
| `identity-retired` | System verifier | After an approved action runner sends the Agent Identity DELETE, record retirement only when the active-resource read verifies absence. |
| `block-object` | Reconciler or human reviewer | Record a concrete permission, dependency, policy, or verification failure. Automated code may use this only for an observed failure; a human may use it for a reviewed dependency or safety concern. |
| `block-resolved` | Scheduled reconciler or human reviewer | Resume a blocked object only after a new successful observation or reviewed dependency resolution. The implementation derives the safe pending or active state and preserves the original approval and retirement timestamps. |
| `blueprint-membership-observed` | Scheduled reconciler | Under a group-level onboarding exclusion, completely enumerate every Agent Identity page for the exact Blueprint app ID and check pending identity-creation reservations. Any remaining identity or reservation retains the Blueprint. Verified zero counts start automatic cleanup under the existing retirement approval. |
| `blueprint-delete-started` | Action runner | Persist that the approved Blueprint DELETE is about to be sent while fresh empty-group eligibility and the onboarding exclusion are present. This separates pre-delete eligibility from later exact-ID outcome verification. |
| `blueprint-retired` | System verifier | After the approved Blueprint DELETE, record retirement only when the Blueprint active-resource read verifies absence. |
| `blueprint-principal-retired` | Scheduled reconciler or system verifier | Record retirement only when the principal read verifies the cascade has completed. Do not infer it only from Blueprint absence. |

The prototype should reject unsafe ordering. For example, it should not retire
the Agent Identity while the companion Registration is still active, and it
should not begin Blueprint cleanup before source retirement is complete and a
verified membership count reaches zero.

Blocked state is sticky. An approval or unrelated successful observation must
not clear it. Only `block-resolved` may resume that object, and the resolution
must name the evidence or dependency change that made progress safe. Resolving
a Blueprint object block invalidates all earlier membership counts and
exclusion evidence; cleanup returns to `awaiting-group-membership-check`.
After the Blueprint DELETE has already been verified, a principal verification
block is different: resolving it returns only the principal to pending
cascade verification and never resets the retired Blueprint.

## Reconciler, approval, action, and verification boundaries

The production-shaped workflow has four separate responsibilities but only one
human gate:

1. **Scheduled reconciler:** periodically reads complete Package inventory and
   mapped objects. It records observed presence, absence, relocation,
   propagation, deadlines, and failures. It may move objects between
   `active`, `pending`, `retired`, and `blocked` only when the transition is
   based on verified read evidence. It records
   `lastHealthyAbsenceObservedAt` for each complete healthy absence scan.
2. **Human approver:** reviews the collected evidence and approves one
   retirement plan. That approval covers the source, companion Registration,
   dedicated Agent Identity, and Blueprint cleanup if the Blueprint is later
   verified empty. The audit record must include actor, time, scope, and the
   evidence snapshot that was approved.
3. **Action runner:** sends a destructive remote request only after the
   matching approval field is present. It uses the locked mapped ID and does
   not update the object to `retired` merely because DELETE returned success.
   A timeout or lost DELETE response is an unknown outcome, not a failure that
   restarts the workflow.
4. **System verifier:** re-reads the exact object and complete inventory as
   required. Only verified absence produces a `*-retired` event. Timeout,
   permission failure, or an unexpected response leaves the object pending or
   blocked for later reconciliation. On resume it verifies first: absence
   completes the step, presence permits a guarded retry, and another uncertain
   result remains pending or blocked.

For example, the scheduled reconciler can detect that the source has remained
absent beyond `gracePeriodEndsAt` and set
`lifecycleReason: awaiting-source-retirement-approval`. It must stop there.
Only a human decision can populate `retirementApprovedAt`. After that single
approval, the action runner may delete and verify the Registration, wait for
companion Package disappearance, delete and verify the Agent Identity, and
check Blueprint membership without returning for more approvals. If no other
active or pending Agent Identity remains, it may automatically delete and
verify the Blueprint and principal. If another identity remains, it retains
the Blueprint.

`retirement-approved` requires
`lastHealthyAbsenceObservedAt >= gracePeriodEndsAt`; elapsed time alone is not
sustained-absence evidence. It also requires
`lastHealthyAbsenceObservedAt <= retirementApprovedAt`, and the configured
maximum observation age must not have elapsed. The grace deadline must itself
be later than `missingSince`. Demo 3 uses 60 minutes only as an experiment
input; deployment policy owns the production freshness window. Legacy
source-deletion confirmations or object-specific approvals remain audit
history and must never be promoted into the broader retirement-plan approval.
The explicit `retirement-approved` event can authorize an already-progressed
legacy mapping without resetting any verified retirement.

Blueprint emptiness requires more than a count supplied by a caller. The
reconciler must:

1. acquire a Blueprint-group onboarding exclusion that prevents new identity
   reservations, direct directory creation, restore, and every other approved
   writer path through deletion;
2. use the supported server-side `agentIdentityBlueprintId` filter with the
   locked `blueprintId`, enumerate every returned page, and verify every
   returned Identity still matches that Blueprint;
3. check the mapping journal for active, pending, unresolved, or timed-out
   identity creation reservations;
4. bind the counts, Blueprint ID, completeness result, and observation time
   into `blueprintCleanup.membershipEvidence`; and
5. retain or block the Blueprint whenever enumeration, reservation review, or
   exclusion control is incomplete.

The exclusion stays held from the zero-count observation through Blueprint
deletion. If any writer or restore path cannot participate in that exclusion,
automatic Blueprint deletion is blocked. Authentication delay, exclusion
interruption, or block recovery invalidates the earlier zero; enumeration and
reservation review must run again immediately before DELETE.

Before enumeration begins, every create or restore operation already accepted
for that Blueprint must either reach a terminal result or remain represented
by a pending or unresolved reservation. After the exclusion is acquired, the
reconciler applies the configured directory-visibility barrier and repeats the
complete enumeration. An implementation may use two matching complete scans
separated by the configured consistency interval, or a stronger documented
consistent-read mechanism. It must not interpret one immediate empty page as
proof that all accepted writes are visible.

Membership observations, source-reappearance holds, and hold clearances are
monotonic. An event older than the latest observation, invalidation, or hold
cannot replace newer safety evidence. A source-reappearance hold invalidates
pre-delete Blueprint eligibility. If DELETE has not been issued, clearing a
verified stale hold requires a fresh membership observation. If DELETE was
already issued, exact-ID absence verification may complete that action, but a
retry against a still-present Blueprint requires fresh eligibility. Once
Blueprint deletion is verified, post-delete principal verification no longer
depends on pre-delete membership eligibility.

`safetyWatermarkAt` is the shared monotonic clock for all lifecycle safety
events, including observations, blocks, resolutions, approval, and verified
outcomes. Source presence and absence share one ordered history through
`lastSourceObservation` and `lastSourceObservedAt`. A presence observation
clears the previous absence episode, so delayed absence evidence cannot retire
a source that was seen more recently.

If Blueprint DELETE times out or its response is lost,
`blueprintDelete.status: pending` preserves the issued-action checkpoint.
Exact-ID absence can complete that pending phase without reconstructing
pre-delete membership evidence. If the Blueprint is still present, any DELETE
retry requires a fresh zero/zero observation under the current exclusion.
Blocking either the Blueprint or its principal invalidates eligibility and
prevents initial deletion or retry until the block is explicitly resolved.
Repeated approval is an idempotent replay: the original approval timestamp and
freshness policy remain the authorization record.

The local Python prototype represents these decisions and observations as
events, but it does not authenticate an approver, schedule reconciliation, or
call remote APIs. Its Blueprint event therefore requires the production
reconciler to attest that enumeration was complete, no pending reservation
exists, the observed Blueprint matches the locked mapping, and the onboarding
exclusion is held. A production implementation must keep those capabilities
in separate interfaces so that a scheduled job cannot impersonate a human
approval.

The simulation event must derive its deadline from the real `missingSince`
timestamp. It must not accept a fabricated future event time as a substitute
for waiting. A simulation mapping records:

```json
{
  "retirementPolicy": {
    "mode": "experiment-simulation",
    "gracePeriod": "PT5M",
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
retirement-approved
awaiting-removal-propagation
dependency-found
group-not-empty
permission-denied
deletion-verified
```

Workflow reasons such as `source-active`, `awaiting-healthy-sync`,
`awaiting-grace-period`, `companion-retirement-pending`,
`companion-retirement-in-progress`, `required-step-blocked`, and
`source-retired` belong in `lifecycleReason`, not in an individual object's
`reason`.

Blueprint group workflow reasons such as `source-active`,
`source-retirement-incomplete`, `awaiting-group-membership-check`,
`group-not-empty`, and `group-empty-automatic-cleanup` belong in
`blueprintCleanup.reason`.

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

If the source reappears after approval or retirement, the reconciler blocks
the mapping, stops any remaining destructive work, records the new Package ID
without erasing the tombstone, and requires explicit reconciliation. It must
not automatically reactivate the mapping or create a replacement companion.

## Results from the prototype and Demo 3

1. `lifecycleStatus` avoided conflict with `nameSyncStatus` and replaced the
   old ambiguous top-level `status`.
2. Process-level timestamps recorded the first missing observation, grace
   deadline, and approval. Per-object timestamps independently recorded
   observation and retirement progress. The experiment used multiple manual
   gates, but the scalable design consolidates them into one retirement plan.
3. The common `pending` state remained usable because `reason` distinguished
   propagation, approval, and dependency-review waits.
4. The conservative Demo 3 order required verified companion Package absence
   before Agent Identity deletion. Registration deletion removed the Package
   by the first subsequent complete inventory, but did not remove the Agent
   Identity. This verification remains automatic rather than becoming another
   human gate.
5. Blueprint cleanup begins automatically when post-retirement reconciliation
   verifies that no other active or pending Agent Identity uses the Blueprint.
   A non-empty Blueprint is retained without requiring a human decision.
6. In this run, deleting the dedicated Blueprint also removed its principal by
   the first follow-up read. The mapping still tracked and verified both
   objects independently.
7. Automatic reactivation of a retired tombstone remains prohibited. A
   reappearing source blocks remaining cleanup and requires an explicit future
   reconciliation decision.

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
validated and loaded before a sibling staging file is flushed and atomically
replaces the destination. A failed staging write leaves the previous mapping
checkpoint intact. Use `--at` to provide a fixed timestamp for reproducible
walkthroughs.

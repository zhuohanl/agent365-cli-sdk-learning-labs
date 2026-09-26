# Demo 3 retirement automation rubber-duck review

## Review configuration

- Documents:
  - `lab-20-registry-sync-identity-gaps/demos/03-delete-companion/prototype_retirement_mapping.py`
  - `lab-20-registry-sync-identity-gaps/demos/03-delete-companion/demo.http`
  - `lab-20-registry-sync-identity-gaps/demos/03-delete-companion/proposal.md`
- Repository context:
  - `lab-20-registry-sync-identity-gaps/docs/CONTEXT.md`
  - `lab-20-registry-sync-identity-gaps/docs/design-decisions.md`
- Reviewer model: `gpt-6-astra`
- Maximum rounds: 5
- Stop conditions: reviewer clears the documents with no high blockers and
  the response requires no material document edit, or the maximum round count
  is reached.

## Round 1 - gpt-6-astra - 2026-09-13

### Review

#### Overall opinion

**Not cleared** — safety blocks and approval scope can be bypassed, and
sustained-absence and Blueprint-emptiness evidence are insufficiently
enforced.

#### Findings

| ID | Severity | Location | Reviewer opinion | Impact | Recommended correction |
| --- | --- | --- | --- | --- | --- |
| R1-H1 | High | `prototype_retirement_mapping.py:345-363,388-400` | Unrelated transitions overwrite blocked Registration or Agent Identity state. | An unresolved dependency can become deletion-ready without evidence that the block was resolved. | Preserve blocked states and require an explicit evidence-backed resolution event. |
| R1-H2 | High | `prototype_retirement_mapping.py:219-226`; `proposal.md:230-235,321-331` | Legacy source-only evidence is promoted to full retirement-plan approval and historical fields are removed. | Older mappings could authorize Identity and Blueprint deletion without a full-plan approval and lose audit history. | Never infer full approval from legacy fields; preserve them as history and require an explicit full-plan approval. |
| R1-H3 | High | `demo.http:819-878`; `prototype_retirement_mapping.py:450-500`; `proposal.md:212,248-253` | Blueprint emptiness is represented only by an unbound scalar count. | Incomplete enumeration or concurrent onboarding could cause deletion of a Blueprint that still has a child Identity. | Require complete paginated Identity enumeration, mapping-journal reservations, Blueprint-bound evidence, group-level exclusion, and immediate revalidation. |
| R1-H4 | High | `prototype_retirement_mapping.py:228-238,328-345`; `demo.http:579-582` | Approval checks elapsed time but not a fresh healthy grace-end absence observation. | Waiting alone can be mistaken for sustained-absence evidence. | Record and require a complete healthy absence observation at or after the validated grace deadline. |
| R1-M1 | Medium | `prototype_retirement_mapping.py:373-377,388-405,421-445,465-500`; `proposal.md:16,239-242` | Blocked cleanup has no supported recovery and verified events are not idempotent. | Transient failures strand the workflow or encourage manual state edits. | Add evidence-backed block resolution and idempotent verification replay while preserving original retirement timestamps. |
| R1-M2 | Medium | `demo.http:663,790`; `proposal.md:237-242` | Verification GETs require a known `204` DELETE result. | A successful DELETE followed by a client timeout cannot be reconciled safely. | Permit exact-ID verification after unknown outcomes and during resume. |

#### Questions

| ID | Reviewer question |
| --- | --- |
| R1-Q1 | What happens if the provider source reappears after approval but before cleanup finishes? |
| R1-Q2 | Does “no other active mapping references either object” exclude the Blueprint so a shared member can retire? |

### Response

#### Overall response

Accepted all six findings. The mapping now requires fresh grace-end evidence,
keeps blocks sticky until explicit evidence-backed resolution, preserves
legacy approval history without promoting it, supports idempotent resume after
unknown DELETE outcomes, and binds Blueprint cleanup to complete enumeration,
reservation checks, and an onboarding exclusion.

#### Findings

| ID | Disposition and fix |
| --- | --- |
| R1-H1 | **Accepted.** Approval now requires Registration state to be active or pending, and companion Package retirement rejects a blocked Identity. Only `block-resolved` may resume a blocked object. |
| R1-H2 | **Accepted.** Legacy approval fields move to `legacyApprovalHistory`; they never populate `retirementApprovedAt`. |
| R1-H3 | **Accepted.** `blueprint-membership-observed` now requires the exact Blueprint app ID, complete paginated enumeration, zero pending creation reservations, and a held onboarding exclusion. The HTTP flow includes the Agent Identity enumeration request and mapping-journal check. |
| R1-H4 | **Accepted.** `source-missing` records `lastHealthyAbsenceObservedAt`; approval requires it to be at or after a grace deadline that is later than `missingSince`. |
| R1-M1 | **Accepted.** Added `block-resolved` with a derived safe resume state and made retirement verification events idempotent while preserving the first `retiredAt`. |
| R1-M2 | **Accepted.** Registration and Identity verification reads now run after `204`, timeout, or lost response. Absence completes the step; presence permits guarded retry. |

#### Question resolutions

| ID | Resolution |
| --- | --- |
| R1-Q1 | Added `source-reappeared`: it records the new Package ID, blocks the source states, preserves the tombstone, and stops remaining destructive work. |
| R1-Q2 | Clarified that the uniqueness check applies to the Registration and Agent Identity, not the Blueprint. Blueprint sharing is evaluated later by complete membership enumeration. |

#### Validation

- Targeted retirement and HTTP structure suite: 84 tests passed.
- Stale multi-approval event and gate search: no matches in the reviewed documents.
- Diff whitespace check: passed.

## Round 5

### Review

#### Findings

##### R5-H1 — High — Stale eligibility survives issued-DELETE recovery

- **Location:** `prototype_retirement_mapping.py:813-830,950-965`;
  contradicts `proposal.md:318-322,348-352` and `demo.http:996-999`.
- **Opinion:** The pending-DELETE recovery branch skips eligibility
  invalidation. Zero-count evidence can survive an exclusion interruption and
  authorize a later retry without fresh enumeration.
- **Impact:** A retry could delete a Blueprint containing an Agent Identity
  created during the exclusion interruption.
- **Correction:** Invalidate eligibility on interruption or recovery
  regardless of issued-action state. Preserve exact-ID verification
  separately, but require fresh zero/zero evidence before any retry.
- **Classification:** Regressed R2-H2/R3-H2 through the R4-M1 recovery change.

##### R5-H2 — High — Principal block does not prevent cascading deletion

- **Location:** `prototype_retirement_mapping.py:941-965`;
  `demo.http:945-951,1007-1009`.
- **Opinion:** `blueprint-delete-started` checks only the Blueprint object's
  pending state. Blocking `blueprintPrincipal` can still permit the cascading
  Blueprint DELETE.
- **Impact:** Blueprint deletion could cascade-delete an explicitly blocked
  principal.
- **Correction:** Require both Blueprint objects and the cleanup aggregate to
  satisfy the action gate. A principal block prohibits initial DELETE and
  retries until resolved and eligibility is revalidated.
- **Classification:** New.

##### R5-M1 — Medium — Hold clearance strands an already-issued DELETE

- **Location:** `prototype_retirement_mapping.py:215-234,548-549,981-1002`;
  contradicts `proposal.md:348-352`.
- **Opinion:** Eligibility invalidation can reset both Blueprint objects to
  active after DELETE has already been issued, preventing exact-ID absence
  from completing the pending operation.
- **Impact:** Unknown-outcome recovery can require artificial transitions
  after the remote Blueprint is already gone.
- **Correction:** Separate eligibility invalidation from issued-DELETE and
  cascade-verification progress; preserve an exact-ID completion path.
- **Classification:** Incomplete R4-M1.

##### R5-M2 — Medium — Blueprint verification replay is no longer idempotent

- **Location:** `prototype_retirement_mapping.py:981-984,1000-1002`.
- **Opinion:** Replaying `blueprint-retired` after it is already verified is
  rejected.
- **Impact:** A safely repeated verification checkpoint fails after an
  uncertain local acknowledgement.
- **Correction:** Accept consistent verified replay without replacing original
  retirement or verification timestamps.
- **Classification:** Regressed R1-M1.

##### R5-M3 — Medium — Repeated holds corrupt source-observation restoration

- **Location:** `prototype_retirement_mapping.py:529-545,563-570`;
  `proposal.md:341-346`.
- **Opinion:** A repeated `source-reappeared` event replaces the saved pre-hold
  observation with the first hold's presence observation.
- **Impact:** Clearing a stale hold can lose the original validated absence
  baseline and leave contradictory source history.
- **Correction:** Preserve the baseline only when opening the hold and account
  for all newer presence observations during clearance.
- **Classification:** Incomplete R4-H2.

#### Questions

##### R5-Q1

Should repeated `retirement-approved` be an idempotent replay or a separately
audited superseding approval? It currently replaces the original approval
timestamp and freshness policy without retaining history.

#### Overall opinion

**Not cleared.** R5-H1 permits deletion retries with invalidated eligibility,
and R5-H2 permits cascading deletion despite an unresolved principal block.

### Response

#### Overall response

Accepted all Round 5 findings. The issued-action checkpoint is now independent
from deletion eligibility: interruption invalidates the old zero-count
evidence, exact-ID absence may still verify an issued DELETE, and a retry
requires fresh eligibility. Blueprint and principal blocks both prohibit the
cascading action.

#### Findings

| ID | Disposition and fix |
| --- | --- |
| R5-H1 | **Accepted.** Blueprint interruption and block events now invalidate membership evidence even after DELETE was issued. The issued checkpoint remains pending for exact-ID verification; another DELETE cannot start without fresh zero/zero evidence. |
| R5-H2 | **Accepted.** `blueprint-delete-started` now rejects a blocked cleanup aggregate and requires both Blueprint object states to be pending. A principal block therefore prevents the cascading DELETE. |
| R5-M1 | **Accepted.** Eligibility invalidation no longer resets pending Blueprint object progress after DELETE has been issued. Hold clearance can proceed directly to exact-ID outcome verification. |
| R5-M2 | **Accepted.** Replayed verified `blueprint-retired` events are idempotent and preserve the original retirement and verification timestamps. |
| R5-M3 | **Accepted.** Repeated source-presence observations update the active hold without replacing its original pre-hold source observation baseline. |

#### Question resolutions

##### R5-Q1

Repeated `retirement-approved` is an idempotent replay. The first approval
timestamp and its evidence-freshness policy remain authoritative; later replay
does not replace them.

#### Validation

- Full Lab 20 suite: 147 tests passed.
- Python compilation: passed.
- Diff whitespace check: passed.

## Final status

**Maximum rounds reached.** All high and medium findings reported within the
five-round limit were addressed. No known high blocker remains in the reviewed
Python prototype, HTTP walkthrough, or proposal.

## Round 4 - gpt-6-astra - 2026-09-13

### Review

#### Overall opinion

**Not cleared** — stale evidence can still cross event types and authorize
unsafe retirement.

#### Findings

| ID | Severity | Location | Reviewer opinion | Impact | Recommended correction |
| --- | --- | --- | --- | --- | --- |
| R4-H1 | High | `prototype_retirement_mapping.py:165-174,441-465,675-735,745-767`; `proposal.md:317-323` | Chronology checks are local to event types and can rewind through a hold or block. | Delayed events can erase a known child or clear a newer safety restriction. | Add a monotonic safety watermark shared by observations, holds, blocks, resolutions, and approval. |
| R4-H2 | High | `prototype_retirement_mapping.py:316-337,408-432` | Presence and absence observations are not one ordered source history. | A delayed absence can retire a source that was more recently observed present. | Track the latest source observation, reject older events, and clear the previous absence episode on relocation. |
| R4-M1 | Medium | `prototype_retirement_mapping.py:715-727,851-871`; `demo.http:1012-1034`; `proposal.md:252-262` | Blueprint recovery does not distinguish pre-delete eligibility from an already-issued DELETE with unknown outcome. | A successful remote deletion can be stranded when its verification initially fails. | Persist a Blueprint DELETE-started phase and allow exact-ID absence to complete it without rebuilding pre-delete eligibility. |
| R4-L1 | Low | `prototype_retirement_mapping.py:893-911` | The staging pathname is captured too late for cleanup after write, flush, or fsync failure. | Partial staging files can accumulate during storage failures. | Capture the pathname immediately after file creation and test failure cleanup. |

#### Questions

None.

### Response

#### Overall response

Accepted all Round 4 findings. Lifecycle safety now uses one monotonic
watermark and one ordered source presence/absence history. Blueprint DELETE
has a persisted issued-action phase distinct from eligibility, and failed
staging writes clean up correctly.

#### Findings

| ID | Disposition and fix |
| --- | --- |
| R4-H1 | **Accepted.** Added `safetyWatermarkAt` across observations, holds, blocks, resolutions, approval, and verified outcomes. Older cross-event evidence is rejected. |
| R4-H2 | **Accepted.** Added `lastSourceObservation` and `lastSourceObservedAt`. Presence clears the prior absence episode; approval requires the current latest source observation to be absent. |
| R4-M1 | **Accepted.** Added `blueprint-delete-started` and `blueprintDelete.status`. Exact-ID absence can complete an already-issued DELETE after verification recovery without rebuilding eligibility. |
| R4-L1 | **Accepted.** The staging pathname is captured immediately after creation, so write, flush, or fsync failures remove the partial staging file while preserving the original mapping. |

#### Question resolutions

None.

#### Validation

- Targeted retirement and HTTP structure suite: 97 tests passed.
- Python compilation: passed.
- Diff whitespace check: passed.

## Round 3 - gpt-6-astra - 2026-09-13

### Review

#### Overall opinion

**Not cleared** — partial-cleanup recovery remains broken, and stale or
out-of-order evidence can restore Blueprint deletion eligibility.

#### Findings

| ID | Severity | Location | Reviewer opinion | Impact | Recommended correction |
| --- | --- | --- | --- | --- | --- |
| R3-H1 | High | `prototype_retirement_mapping.py:672-681,740-760,771-792`; `demo.http:1062-1064`; `proposal.md:227-231` | Principal block recovery after Blueprint deletion resets pre-delete eligibility and cannot resume verification. | A permission failure after successful Blueprint deletion permanently strands cleanup. | Separate pre-delete eligibility recovery from post-delete verification recovery. |
| R3-H2 | High | `prototype_retirement_mapping.py:408-438,771-783`; `proposal.md:299-303`; `demo.http:652-659` | Clearing a source-reappearance hold preserves old zero-count evidence. | Destructive work can resume with stale Blueprint eligibility. | Invalidate pre-delete eligibility on holds and require fresh evidence after clearance while preserving post-delete progress. |
| R3-H3 | High | `prototype_retirement_mapping.py:430-438,724-760`; `proposal.md:63-65` | Older membership or hold-clear events can overwrite newer evidence. | Delayed events can defeat a known child Identity or newer reappearance observation. | Enforce monotonic event chronology against the latest observation and invalidation. |
| R3-M1 | Medium | `prototype_retirement_mapping.py:205-213`; `demo.http:935-938` | Reservation-only retention is overwritten with the wrong reason. | Automated stop logic cannot recognize a valid non-empty outcome. | Include pending reservations when deriving `group-not-empty`. |
| R3-M2 | Medium | `prototype_retirement_mapping.py:809-811`; `proposal.md:444-445` | Direct `write_text()` is not crash-safe for in-place mapping updates. | A partial write can destroy the only resume checkpoint after remote deletion. | Flush a sibling staging file and atomically replace the mapping. |

#### Questions

| ID | Reviewer question |
| --- | --- |
| R3-Q1 | What drains already-accepted create or restore operations and accounts for directory visibility delay before emptiness enumeration? |

### Response

#### Overall response

Accepted all Round 3 findings. Pre-delete Blueprint eligibility and
post-delete principal verification now have separate recovery paths, safety
events are monotonic, reservation-only retention is represented correctly,
and mapping persistence uses atomic replacement.

#### Findings

| ID | Disposition and fix |
| --- | --- |
| R3-H1 | **Accepted.** When the Blueprint is already retired, resolving a principal block returns only the principal to pending cascade verification and does not invalidate completed Blueprint state. |
| R3-H2 | **Accepted.** A source-reappearance hold invalidates pre-delete Blueprint counts and evidence. Clearing the hold requires a fresh membership observation before Blueprint deletion. |
| R3-H3 | **Accepted.** Membership, hold, and hold-clearance events reject timestamps older than the latest observation, invalidation, or hold. Membership must also follow Agent Identity retirement. |
| R3-M1 | **Accepted.** `recalculate()` now treats either remaining identities or pending reservations as `group-not-empty`. |
| R3-M2 | **Accepted.** Mapping writes now flush a sibling staging file and atomically replace the destination, cleaning up failed staging files. |

#### Question resolutions

| ID | Resolution |
| --- | --- |
| R3-Q1 | Under the onboarding exclusion, every accepted create or restore must reach a terminal result or remain represented by a reservation. The reconciler then applies the configured visibility barrier and requires repeated matching complete scans unless a stronger consistent-read mechanism exists. |

#### Validation

- Targeted retirement and HTTP structure suite: 93 tests passed.
- Python compilation: passed.
- Diff whitespace check: passed.

## Round 2 - gpt-6-astra - 2026-09-13

### Review

#### Overall opinion

**Not cleared** — full-plan approval can be bypassed for Blueprint cleanup,
stale emptiness evidence can regain deletion eligibility, and
source-reappearance recovery can strand the workflow.

#### Findings

| ID | Severity | Location | Reviewer opinion | Impact | Recommended correction |
| --- | --- | --- | --- | --- | --- |
| R2-H1 | High | `prototype_retirement_mapping.py:588-647,657-684` | Blueprint readiness and retirement do not require `retirementApprovedAt`. | A progressed legacy mapping can delete a Blueprint without full-plan approval. | Require the explicit plan approval and allow the same approval event to authorize already-progressed legacy mappings without resetting completed work. |
| R2-H2 | High | `prototype_retirement_mapping.py:562-579,625-629,635-654,663-668` | Blueprint block recovery reuses old zero-count evidence and exclusion state. | Stale eligibility can be revived after another Identity appears. | Invalidate counts and evidence on recovery, return to awaiting recheck, then require fresh bound enumeration under exclusion. |
| R2-H3 | High | `demo.http:876-906,939-985`; `proposal.md:279-290` | The HTTP sequence acquires onboarding exclusion after enumeration. | A concurrent creation can race between the scan and exclusion. | Acquire exclusion before enumeration and revalidate immediately before DELETE after any interruption. |
| R2-H4 | High | `prototype_retirement_mapping.py:77-80,349-374,375-404,426-428,528-532` | Source reappearance overwrites retired object history and has no safe recovery. | Original retirement timestamps are lost and the workflow becomes impossible to resume. | Represent reappearance as a separate reconciliation hold and provide an evidence-backed stale-observation clearance path that preserves completed work. |
| R2-M1 | Medium | `prototype_retirement_mapping.py:240-244,375-400` | Approval can be timestamped before its supporting observation. | Reproducible walkthroughs can persist impossible chronology. | Enforce `missingSince < deadline <= absence observation <= approval`. |

#### Questions

| ID | Reviewer question |
| --- | --- |
| R2-Q1 | What enforces onboarding exclusion against directory writers or restores outside the mapping journal? |
| R2-Q2 | What maximum age makes a post-grace absence observation fresh at approval? |

### Response

#### Overall response

Accepted all Round 2 findings. Full-plan approval is now required for
Blueprint readiness and deletion, source reappearance uses a separate hold,
Blueprint block recovery invalidates eligibility, and the evidence chronology
and freshness window are enforced.

#### Findings

| ID | Disposition and fix |
| --- | --- |
| R2-H1 | **Accepted.** Blueprint membership and retirement events require `retirementApprovedAt`. The same explicit approval event supports progressed legacy mappings while preserving completed object states. |
| R2-H2 | **Accepted.** Resolving a Blueprint block clears counts and membership evidence and returns cleanup to a fresh membership check. |
| R2-H3 | **Accepted.** The HTTP flow now acquires onboarding exclusion before enumeration and requires fresh re-enumeration immediately before DELETE after authentication or any interruption. |
| R2-H4 | **Accepted.** `source-reappeared` now creates a separate reconciliation hold without modifying retired object state. `source-reappearance-cleared` clears only a verified stale-observation hold and preserves all completed timestamps. |
| R2-M1 | **Accepted.** Approval enforces `missingSince < gracePeriodEndsAt <= lastHealthyAbsenceObservedAt <= retirementApprovedAt`. |

#### Question resolutions

| ID | Resolution |
| --- | --- |
| R2-Q1 | Automatic Blueprint deletion requires an exclusion covering onboarding, direct directory creation, restore, and every approved writer path. Any writer outside that mechanism blocks cleanup. |
| R2-Q2 | Approval now requires a configured maximum observation age. Demo 3 uses 60 minutes as an experiment input; deployment policy must choose the production value. |

#### Validation

- Targeted retirement and HTTP structure suite: 88 tests passed.
- Diff whitespace check: passed.

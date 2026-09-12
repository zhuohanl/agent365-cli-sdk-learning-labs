# Demo 03 findings: companion retirement

## Result

The disposable Google Vertex AI provider agent was removed and a complete
Registry Sync inventory no longer contained either its previous Package ID or
its scoped provider source key. After the simulation-only grace period and
separate approvals, the companion Registration, companion Package, dedicated
Agent Identity, dedicated Blueprint, and Blueprint principal were retired in
dependency order.

The final durable mapping reached:

```text
lifecycleStatus: retired
blueprintCleanup.status: retired
```

All former source and object identifiers remain in the mapping as a tombstone.

## Observed behavior

| Object or check | Observation |
| --- | --- |
| Registry Sync inventory | The inventory count decreased by one after provider deletion. The previous provider Package ID and scoped provider source key were absent both immediately after sync and at the grace-boundary recheck. No replacement Package was found. |
| Previous provider Package ID | Package Details returned an outer `UnknownError` containing a Title Preview `424`. Complete inventory, not this inconclusive details response, supplied the absence evidence. |
| Retirement grace | The local prototype derived a 15-minute experiment deadline from the real first-missing timestamp and retained `P14D` only as an unvalidated production candidate. A fresh complete inventory was captured after the experiment deadline. |
| Companion Registration | The Registration still existed after provider-source retirement. After separate approval, DELETE succeeded and a read of the same ID returned an inner `404 Not Found`. |
| Companion Package | The first complete inventory captured after Registration deletion no longer contained the mapped companion Package. The inventory count decreased by one. |
| Agent Identity | The Agent Identity still existed with the same ID and Blueprint relationship after Registration deletion. It did not cascade with the Registration. Direct app-role assignments and direct directory memberships were both empty in the approved dependency reads. After separate approval and soft deletion, the active-resource read returned `Request_ResourceNotFound`. |
| Dedicated Blueprint | The Blueprint still existed unchanged after source and Agent Identity retirement. It was cleaned up only after source retirement completed and the dedicated group was confirmed empty. The active-resource read then returned `Request_ResourceNotFound`. |
| Blueprint principal | The principal still existed before dedicated Blueprint cleanup. The first read after Blueprint deletion returned `Request_ResourceNotFound`; no separate principal DELETE was required in this run. |
| Durable mapping | The common per-object `active`, `pending`, `retired`, and `blocked` vocabulary represented the full run. Aggregate `lifecycleStatus` used `partial` during managed-object cleanup and finished as `retired`. Blueprint cleanup progressed independently and also finished as `retired`. |

No authentication response or credential value is stored in the Demo 03
evidence directory. Blueprint response schemas contain standard credential
metadata fields, but no credential material was present.

## Handling rule supported by this run

1. Treat a missing Package ID as a reconciliation signal, not deletion proof.
2. Read complete healthy inventory and search for the scoped provider source
   key before deciding whether the source disappeared or moved to a new
   Package ID.
3. Require a grace-boundary recheck and explicit source-retirement approval
   before retiring the provider source and Registry Sync Package states.
4. Retire the companion Registration first under its own approval. Verify the
   same Registration ID is absent, then independently re-read complete Package
   inventory.
5. Treat companion Package disappearance as an observed propagation result,
   not an assumed synchronous effect of Registration deletion.
6. Keep the Agent Identity until Registration retirement, companion Package
   absence, dependency review, and a separate Identity approval are complete.
7. Keep Blueprint cleanup independent from source retirement. Never delete a
   shared Blueprint for one source. For a confirmed-empty dedicated group,
   require a separate cleanup decision and verify both the Blueprint and its
   principal.
8. Preserve all former IDs and timestamps in a tombstone. Do not automatically
   reactivate a retired mapping if the provider source later reappears.

## Boundary

This is one disposable Google Vertex AI observation. It does not establish a
cross-provider contract, a production grace period, a propagation-time
guarantee, or production support for the beta Agent Registration API.

The observed Registration-to-Package removal and Blueprint-to-principal
cascade must be verified in every run. The empty app-role and membership reads
also do not prove that an Agent Identity has no runtime, OAuth, policy,
ownership, external credential, or other dependency.

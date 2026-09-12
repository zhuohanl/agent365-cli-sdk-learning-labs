# Demo 02 findings: companion name synchronization

## Result

The disposable Google Vertex AI provider agent was renamed without replacing
its Registry Sync Package or changing its stable provider source key. The
existing dedicated Agent 365 objects were then renamed in place and the final
mapping reached `nameSyncStatus: in-sync`.

## Observed behavior

| Object | Observation |
| --- | --- |
| Provider-owned Registry Sync Package | The display name changed while the Package ID, platform, provider scope, exact source ID, and source creation time remained unchanged. The provider source modification time advanced. |
| Dedicated Blueprint | The display name changed in place. Its object ID and application ID remained unchanged. |
| Blueprint principal | A read after the Blueprint rename already returned the new Blueprint name in both `displayName` and `appDisplayName`. No separate principal rename was required in this run. Its object ID, application ID, and enabled state remained unchanged. |
| Agent Identity | The display name changed in place. Its object ID, Blueprint relationship, and enabled state remained unchanged. |
| Companion Registration | The display name and provider source modification time changed in place. Its Registration ID, source ID, platform, owners, Blueprint ID, and Agent Identity ID remained unchanged. |
| Companion Package | The Registration display name propagated to the existing companion Package. Its Package ID, platform, source, and Agent Identity relationship remained unchanged. |
| Package inventory | The total inventory count remained stable. Exactly one provider Package and one companion Package remained for the mapping; no old-name duplicate remained. |
| Durable mapping | All identity and relationship IDs remained unchanged. The six observed display-name fields matched their expected values and `nameSyncStatus` became `in-sync`. |

No authentication response or credential value is stored in the Demo 02
evidence directory.

## Handling rule supported by this run

1. Treat the provider-owned Package display name as the name source.
2. Use the mapped Package ID for the fast read, but verify the stable platform,
   provider scope, and exact source ID before classifying a change as rename.
3. Set `nameSyncStatus` to `pending` when no managed target name has been
   applied, `partial` when only some names match, and `in-sync` only when every
   in-scope name matches.
4. For a dedicated assignment, rename the Blueprint first and then read both
   the Blueprint and principal. Do not PATCH the principal when it has already
   followed the Blueprint.
5. Rename and verify the Agent Identity and companion Registration without
   changing their IDs or relationships.
6. Poll the existing companion Package until the Registration name propagates.
   Do not PATCH the Package or repeat an already successful Registration
   update.
7. For a shared assignment, keep the approved group-level Blueprint and
   principal names; synchronize only the source-specific objects.

## Boundary

This is one disposable Google Vertex AI observation. It does not establish a
cross-provider contract, a propagation time guarantee, or production support
for the beta Agent Registration update API. A future run must still read and
verify the Blueprint principal and companion Package rather than assume either
name propagation behavior.

# Lab 4 expected observations

This lab tests control boundaries. Treat these results as hypotheses to verify,
not values to force.

## Baseline

With Registry **Unblocked** and Enterprise Agent Identity **Enabled**:

| Probe | Expected safe category |
| --- | --- |
| `/chat` | Working |
| `/identity-check` | Token acquired |
| `/manager-role-check` | Authorized when `AgentIdentity.CreateAsManager` is present |
| `/graph-check` | Authorization denied without application `Organization.Read.All` |

## Registry Block with identity enabled

| Probe | Expected boundary |
| --- | --- |
| `/chat` | Still working because the local endpoint has no Microsoft 365 channel dependency |
| Fresh token acquisition | Record the actual result; Registry Block is not an Entra identity-disable action |
| Manager-role Graph call | Follows the fresh-token and application-role results |

This scenario does not prove that every Microsoft 365 host ignores Registry
Block. It tests only the local third-party runtime and sidecar path.

## Registry Unblocked with identity disabled

| Probe | Expected boundary |
| --- | --- |
| `/chat` | Still working because it does not request the identity token |
| Fresh token acquisition | Expected to fail after the identity state propagates |
| Manager-role Graph call | Cannot reach Graph when token acquisition fails |

If a fresh token still succeeds immediately after disable, stop the run, allow
time for propagation, and start another fresh sidecar. Do not use a token from
an earlier run as evidence of new token issuance.

## Restored state

Finish with:

```text
Registry state: Unblocked
Enterprise Agent Identity state: Enabled
Local sidecar: Stopped
Local runtime: Stopped
```

Run one fresh baseline after re-enable. Token acquisition can require time to
recover after an administrative state change.

# Lab 4 interpretation example

This is an interpretation reference. Replace hypotheses with your observed
safe results.

## Experiment interpretation

| Scenario | Registry state | Agent Identity state | Fresh sidecar | `/chat` | Token acquisition | Manager-role Graph call | Interpretation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline | Unblocked | Enabled | Yes | Working | Acquired | Authorized when role is present | All tested paths are available |
| Registry control | Blocked | Enabled | Yes | Working | Record actual result | Follows token and role result | Registry state does not stop local compute; record whether this token path depends on it |
| Identity control | Unblocked | Disabled | Yes | Working | Expected to be denied | Not reached when token is denied | Identity disable reaches authentication but not local compute |
| Restored baseline | Unblocked | Enabled | Yes | Working | Acquired after propagation | Authorized when role is present | The identity path recovers after re-enable |

## Control classification

| Control | Visibility | Identity | Administrative control | Runtime enforcement | Evidence |
| --- | --- | --- | --- | --- | --- |
| Registry Block | Registry item remains visible with blocked state | Does not itself define the Entra principal state | Changes channel or availability state on supported Microsoft surfaces | Does not stop the local `/chat` process | Admin state plus endpoint observations |
| Enterprise Agent Identity Disable | Registry item can remain visible | Disables the selected Entra principal | Stops new token issuance after propagation | Blocks runtime operations that require a new token; does not stop token-independent code | Fresh token result plus `/chat` result |
| Third-party compute stop | Not a visibility control | Not an identity control | Requires the hosting platform or operator | Stops the Python process and all its paths | Host process or platform state |

## Capability matrix answer key

| Capability or control | CLI registration alone | Agent 365 SDK required | Microsoft 365 Agents SDK or adapter required | Other product, licence, or preview required | Third-party runtime change required | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Registry visibility and ownership | Yes | No | No | Appropriate tenant and admin roles | No | Lab 1 and CLI registration docs |
| Blueprint and Enterprise Agent Identity | Yes | No | No | Entra roles | No | Labs 1 and 3 |
| Permission inheritance and inspection | Yes | No | No | Consent and directory roles can be required | No | Labs 1 and 3; CLI query commands |
| Update, disable, revoke, and delete lifecycle | Partial: publish and cleanup; no CLI identity-disable command | No | No | Entra or Microsoft 365 admin surfaces for some actions | Credential rotation requires runtime configuration update | CLI help and Entra disable docs |
| Application or channel access blocking | Registration alone does not block the local runtime | No | A channel must exist for channel blocking to affect invocation | Microsoft 365 or Entra administrative control | No change for the control itself | Lab 4 and agent-actions docs |
| Observability in Microsoft administrative surfaces | No | Yes, or the supported Microsoft OpenTelemetry integration | No for instrumentation itself | Tenant onboarding, licence, and ingestion conditions | Yes | Lab 2 and observability docs |
| Governed Microsoft 365 tool access | Permissions can be prepared, but no tool executes | Yes for Agent 365 tooling | User-context flows can require an adapter | Work IQ and current preview/licence conditions | Yes | Agent 365 SDK docs |
| Notifications and agent-user resources | No | Notifications package required | Yes for Activity routing | Agent-user resources, licence, and preview conditions | Yes | Agent 365 SDK docs |
| Runtime stop or quarantine | No for externally hosted third-party compute | No | No | Hosting platform control; some first-party platforms have separate stop controls | No Microsoft registration change can stop arbitrary compute | Lab 4 and agent-actions docs |
| Prompt, model, tool, and data-policy enforcement | No general enforcement inside third-party runtime | No general prompt or model enforcement | No | Resource APIs and third-party controls can enforce their own boundaries | Yes where the third-party runtime implements policy | Labs 1-4 |
| Third-party-native audit and authorization | No | No | No | Third-party platform IAM and audit | Depends on that platform | Platform-native evidence |

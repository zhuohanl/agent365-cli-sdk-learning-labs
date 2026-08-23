# Lab 4 governance evidence

Record only safe categories. Do not record identifiers, tokens, claims, account
names, or raw administrative output.

## Experiment observations

| Scenario | Registry state | Agent Identity state | Fresh sidecar | `/chat` | Token acquisition | Manager-role Graph call | What this proves |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline | Unblocked | Enabled | Yes |  |  |  |  |
| Registry control | Blocked | Enabled | Yes |  |  |  |  |
| Identity control | Unblocked | Disabled | Yes |  |  |  |  |
| Restored baseline | Unblocked | Enabled | Yes |  |  |  |  |

## Control classification

Use these terms:

- **Visibility**: an administrator can find the agent and its metadata.
- **Identity**: a principal can authenticate.
- **Administrative control**: an administrator can change access or lifecycle
  state.
- **Runtime enforcement**: a control constrains an executing operation or
  process.
- **Evidence**: a record shows what happened.

| Control | Visibility | Identity | Administrative control | Runtime enforcement observed | Evidence |
| --- | --- | --- | --- | --- | --- |
| Registry Block |  |  |  |  |  |
| Enterprise Agent Identity Disable |  |  |  |  |  |
| Third-party compute stop |  |  |  |  |  |

## Capability and governance matrix

Fill this matrix from Labs 1-4 and the primary sources in `INSTRUCTION.md`.

| Capability or control | CLI registration alone | Agent 365 SDK required | Microsoft 365 Agents SDK or adapter required | Other product, licence, or preview required | Third-party runtime change required | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Registry visibility and ownership |  |  |  |  |  |  |
| Blueprint and Enterprise Agent Identity |  |  |  |  |  |  |
| Permission inheritance and inspection |  |  |  |  |  |  |
| Update, disable, revoke, and delete lifecycle |  |  |  |  |  |  |
| Application or channel access blocking |  |  |  |  |  |  |
| Observability in Microsoft administrative surfaces |  |  |  |  |  |  |
| Governed Microsoft 365 tool access |  |  |  |  |  |  |
| Notifications and agent-user resources |  |  |  |  |  |  |
| Runtime stop or quarantine |  |  |  |  |  |  |
| Prompt, model, tool, and data-policy enforcement |  |  |  |  |  |  |
| Third-party-native audit and authorization |  |  |  |  |  |  |

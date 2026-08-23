# Component boundaries

Use these boundaries when you interpret a lab result.

| Component | Main responsibility | Does not prove |
| --- | --- | --- |
| Third-party runtime or agent framework | Runs the reasoning or application loop | Agent 365 registration or governance |
| Microsoft Agent Framework | Provides one possible agent framework | Agent 365 registration |
| Microsoft 365 Agents SDK | Hosts and validates an Activity endpoint, such as `/api/messages` | Agent 365 SDK observability or third-party compute control |
| Microsoft Agent 365 SDK | Adds capabilities such as observability, governed tools, and notifications | Registration by importing a package |
| Agent 365 CLI | Creates and manages control-plane and Entra objects | Control of an arbitrary third-party process |
| Entra Auth SDK sidecar | Brokers resource tokens for an Enterprise Agent Identity | Registry creation or compute lifecycle control |

## Five platform responsibilities

Use this list to assess how much binding a platform can automate:

1. Agent creation
2. Hosting workload identity
3. Enterprise Agent Identity
4. Token acquisition
5. Runtime execution

A token path can connect a runtime operation to an Enterprise Agent Identity.
It does not automatically bind the model, prompt, every tool, every endpoint,
or the process lifecycle.

## Control terms

- **Visibility**: an administrator can find the agent and its metadata.
- **Identity**: a principal can authenticate.
- **Administrative control**: an administrator can change access or lifecycle
  state.
- **Runtime enforcement**: a control constrains an executing operation or
  process.
- **Evidence**: a record shows what happened.

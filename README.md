# Agent 365 CLI and SDK learning labs

These guided labs build a small third-party Python runtime one layer at a
time. They separate Agent 365 registration, Agent 365 SDK observability, and
Entra Agent Identity token use.

The labs use a starter-first method. Do not run the solution first.

## Learning path

| Lab | Start state | Change | Observable result |
| --- | --- | --- | --- |
| [Lab 1](lab-01-registration-only/INSTRUCTION.md) | Local echo runtime | Register with Agent 365 CLI | A registry record and Entra objects exist, but the runtime does not change |
| [Lab 2](lab-02-local-observability/INSTRUCTION.md) | The same echo runtime | Add Agent 365 observability | The runtime emits a local agent span |
| [Lab 3](lab-03-enterprise-agent-identity/INSTRUCTION.md) | The observable echo runtime | Add an Entra Auth SDK sidecar token path | The runtime gets an Agent Identity token and Graph enforces operation permissions |
| [Lab 4](lab-04-governance-control-boundaries/INSTRUCTION.md) | The Lab 3 identity-bound path | Change Registry and Entra administrative state | Control-plane block, token enforcement, and local compute behavior are separated |

## Independent experiments

Lab 20 starts a separate experiment series. It is not the next required
lesson in the guided learning path.

| Lab | Question |
| --- | --- |
| [Lab 20](lab-20-registry-sync-identity-gaps/docs/INSTRUCTION.md) | Which identity fields and operations are available for third-party Registry Sync inventory records? |

Lab 20 separates its HTTP correlation work under `trial-1-http-tests/` from
its notebook identity-association work under `trial-2-jupyter-notebook/`.

## Key lessons

| Lab | Key lesson |
| --- | --- |
| Lab 1 | Agent 365 CLI creates control-plane and Entra objects. Registration does not connect Agent 365 to an arbitrary local runtime. |
| Lab 2 | Agent 365 observability instruments the runtime and produces structured OpenTelemetry spans. A local span does not prove Microsoft backend ingestion or runtime governance. |
| Lab 3 | An Enterprise Agent Identity can obtain a resource token. When the runtime requests and presents that token, only the tested outbound resource call is bound to the identity. The full runtime is not automatically bound or controlled. |
| Lab 4 | A Registry block, an identity disable action, and a compute stop are different controls. A control affects the real runtime only where execution depends on the controlled gate. |

Each guided lab contains:

- `starter/`: the pre-lab files to copy and edit.
- `solution/`: the completed reference files.
- `expected-output.md`: safe results and their meaning.
- `INSTRUCTION.md`: the guided steps and a comprehension checkpoint.

## Working method

From one lab directory, copy the starter:

```powershell
Copy-Item .\starter .\workspace -Recurse
Set-Location .\workspace
```

The repository ignores every `workspace/` directory. Generated identifiers,
credentials, virtual environments, and local changes stay outside Git.

After each checkpoint:

1. Explain the result in your own words.
2. Compare only the relevant files with `solution/`.
3. Correct your model before you continue.

## Safety rules

- Never commit `a365.config.json` or `a365.generated.config.json`.
- Never print or paste a token, credential, tenant identifier, application
  identifier, service principal identifier, or private endpoint.
- Enter credentials only in the interactive prompt that needs them.
- Keep the sidecar bound to `127.0.0.1`.
- Stop each process and run the cleanup steps when a lab ends.
- Use only a disposable learning registration.

See [Security and cleanup](docs/security-and-cleanup.md) before you start.

## Prerequisites

- Python 3.12
- `uv`
- Agent 365 CLI (`a365`)
- Azure CLI (`az`)
- Docker Desktop with Docker Compose
- VS Code REST Client extension for the `.http` files
- A permitted test tenant and the roles listed by current `a365 --help`

Lab 1 needs the Agent 365 CLI and Azure CLI authentication. Lab 2 needs Python
and `uv`. Lab 3 also needs Docker. Lab 4 needs permission to change the
disposable Registry and Enterprise Agent Identity states.

## Component model

Read [Component boundaries](docs/component-boundaries.md) if two components
appear to have the same responsibility.

## Source baseline

The learning sequence was developed from Microsoft-owned documentation and
source at these commits:

- `microsoft/Agent365-Samples`: `87dca88dfc73bc386f6a93602f911ef112231976`
- `microsoft/Agent365-devTools`: `1e611b2cb3219aea5d78711a9ef436358416572f`
- `microsoft/Agent365-python`: `8f0b60160a63bc5f22e90233672224067bb82131`
- `Microsoft/Agents-for-python`: `8ff0ac3b5d35a063a6e03af054f042da28d4c3d9`
- `microsoft/entra-agentid-samples`: `ce211acbb1781de04882eda398e7d5187f6832d1`

CLI behavior can change. Always compare the commands in these labs with the
installed CLI `--help`.

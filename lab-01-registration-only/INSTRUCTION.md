# Lab 1: Registration without Agent 365 SDK

## Learning objective

Register an already-running third-party runtime without importing an Agent 365
SDK package.

## Key lesson

Agent 365 CLI creates the blueprint, Enterprise Agent Identity, registry
registration, and permission configuration. These are control-plane and Entra
objects.

The CLI does not modify `agent.py` or connect the registry entry to the local
Python process. Registration gives visibility and identity objects, not
runtime binding.

## What this lab proves

- Agent 365 CLI can create a blueprint, Enterprise Agent Identity, and registry
  registration.
- Registration does not modify or stop the local runtime.
- A registry record is visibility and administrative state, not a runtime
  binding.

## What this lab does not prove

- Microsoft 365 channel invocation
- Agent 365 SDK observability
- Resource-token use by the runtime
- Hosting workload identity
- Control of the Python process

## How to use `expected-output.md`

Keep [`expected-output.md`](expected-output.md) open while you run the lab.
After each observation, compare only the safe result and its meaning.

The file is an evidence guide, not a source-code solution. It omits generated
identifiers, credentials, and environment-specific values. If your result is
different, inspect the current CLI plan and tenant state. Do not change the
environment only to make it match the example.

## Components

| Component | Responsibility in this lab |
| --- | --- |
| `agent.py` | Owns the local HTTP runtime |
| Agent 365 CLI | Creates and inspects control-plane and Entra objects |
| Agent 365 SDK | Absent |
| Microsoft 365 Agents SDK | Absent |

## Prerequisites

- Complete the current `a365 setup requirements` checks.
- Sign in to Azure CLI for the permitted test tenant.
- Have the Azure and Entra roles reported by the installed CLI.

`setup all` can include Azure infrastructure in some CLI versions and
configurations. The dry-run is the source of truth for this lab.

## 1. Create a working copy

From this lab directory:

```powershell
Copy-Item .\starter .\workspace -Recurse
Set-Location .\workspace
```

## 2. Run the baseline

Terminal A:

```powershell
python .\agent.py
```

Use `requests.http` from VS Code, or run:

```powershell
Invoke-RestMethod `
    -Method Post `
    -Uri 'http://127.0.0.1:8080/chat' `
    -ContentType 'application/json' `
    -Body '{"message":"hello"}'
```

Expected result:

```json
{"reply":"Echo: hello"}
```

Stop the runtime before the next step.

## 3. Inspect current CLI requirements

```powershell
a365 --help
a365 setup requirements --help
a365 setup all --help
```

Run the requirements checks that the current CLI lists. Do not paste the raw
output into an issue or chat because it can contain environment identifiers.

## 4. Preview registration

Do not add `--m365`. This lab has no Activity endpoint.

```powershell
a365 setup all `
    --agent-name "A365LearningLab" `
    --dry-run
```

Identify these planned objects:

- Blueprint
- Enterprise Agent Identity
- Registry registration

Record whether the plan includes Azure infrastructure or a messaging endpoint.
With the current non-M365 path, the messaging endpoint is expected to be
skipped. Do not continue if the plan contains an unexpected resource.

## 5. Create the registration

```powershell
a365 setup all --agent-name "A365LearningLab"
```

For the strict registration-only experiment, decline optional observability
permission if the current CLI offers it.

Do not print or commit the generated config files. Treat them as sensitive
local state. Save any generated credential only in an approved secret store.

## 6. Inspect the objects

The generated config lets the CLI find the lab objects:

```powershell
a365 query-entra blueprint-scopes
a365 query-entra inheritance
a365 query-entra instance-scopes
```

Check the installed CLI help if a command has changed.

Record only safe facts, such as:

```text
blueprint_reference_present=true
agent_identity_reference_present=true
registration_reference_present=true
```

## 7. Run the same runtime again

```powershell
python .\agent.py
```

Send the same `/chat` request. The result must still be:

```json
{"reply":"Echo: hello"}
```

Compare `starter/agent.py` and `solution/agent.py`. They are intentionally
identical. Registration happened outside the Python runtime.

## Comprehension checkpoint

Explain why a visible registry entry does not prove that Agent 365 controls
the `/chat` endpoint or Python process.

Correct model:

> Registration creates control-plane and identity objects. It does not insert
> code into an arbitrary third-party runtime.

## Cleanup

Do not clean up yet if you will continue to Lab 3. Lab 3 uses the generated
registration state and the securely saved blueprint credential.

When the full learning sequence ends, use
[Security and cleanup](../docs/security-and-cleanup.md).

## Primary sources

- [Agent 365 CLI reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/)
- [`microsoft/Agent365-devTools`](https://github.com/microsoft/Agent365-devTools)
- [Entra agent blueprint](https://learn.microsoft.com/en-us/entra/agent-id/agent-blueprint)

# Lab 2: Add local Agent 365 observability

## Learning objective

Add only the Agent 365 observability package to the same local runtime. Export
the span to the local console before you configure any Microsoft ingestion
surface.

## Key lesson

OpenTelemetry provides the span pipeline. Agent 365 observability adds
agent-specific scopes and semantic attributes.

The observed console span proves that the runtime is instrumented. It does not
prove Microsoft backend ingestion, Enterprise Agent Identity use, or runtime
governance.

## What this lab proves

- Agent 365 SDK observability is runtime code.
- The SDK adds agent-specific OpenTelemetry scopes and semantic attributes.
- Registration and observability are separate.

## What this lab does not prove

- Microsoft backend ingestion
- Visibility in an admin, security, or compliance portal
- Enterprise Agent Identity token use
- Microsoft 365 channel invocation
- Runtime lifecycle control

## Components

| Component | Responsibility in this lab |
| --- | --- |
| `agent.py` | Owns the echo runtime and creates an invocation scope |
| OpenTelemetry SDK | Owns the provider, span pipeline, and export model |
| Agent 365 observability core | Adds agent scopes and `gen_ai` semantics |
| Agent 365 CLI | Not used for local span creation |

## 1. Create a working copy

```powershell
Copy-Item .\starter .\workspace -Recurse
Set-Location .\workspace
```

The starter is the completed Lab 1 runtime.

## 2. Confirm the baseline

```powershell
uv run python .\agent.py
```

Send the `/chat` request from `requests.http`. Confirm that the response is:

```json
{"reply":"Echo: hello"}
```

No Agent 365 span is present.

## 3. Add the packages

Replace `pyproject.toml` with:

```toml
[project]
name = "agent365-learning-lab"
version = "0.1.0"
description = "Agent 365 CLI and SDK learning lab"
requires-python = "==3.12.*"
dependencies = [
    "microsoft-agents-a365-observability-core==1.0.0",
    "opentelemetry-sdk==1.44.0",
]

[[tool.uv.index]]
name = "microsoft-package-feed-proxy"
url = "https://packagefeedproxy.microsoft.io/pypi/simple"
default = true
```

Then lock and sync:

```powershell
uv lock
uv sync
```

The Microsoft package feed proxy is the only configured package index in this
lab.

## 4. Enable span creation but disable Microsoft export

Add these environment settings before the Agent 365 package import:

```python
os.environ["ENABLE_A365_OBSERVABILITY"] = "true"
os.environ["ENABLE_A365_OBSERVABILITY_EXPORTER"] = "false"
```

These switches are independent:

- `ENABLE_A365_OBSERVABILITY` creates the spans.
- `ENABLE_A365_OBSERVABILITY_EXPORTER` controls the Microsoft exporter.

Configure the OpenTelemetry provider:

```python
provider = TracerProvider(
    resource=Resource.create({SERVICE_NAME: "a365-learning-lab"})
)
trace.set_tracer_provider(provider)
```

Configure Agent 365 observability:

```python
if not configure(
    service_name="a365-learning-lab",
    service_namespace="guided-labs",
    token_resolver=lambda agent_id, tenant_id: None,
):
    raise RuntimeError("Agent 365 observability configuration failed")
```

The token resolver returns no token because this lab does not export to a
Microsoft backend.

## 5. Wrap only the agent invocation

Create local agent details:

```python
AGENT = AgentDetails(
    agent_id="local-echo-agent",
    agent_name="A365LearningLab",
)
```

Wrap the response code:

```python
with InvokeAgentScope.start(
    request=Request(content=[message]),
    scope_details=InvokeAgentScopeDetails(endpoint=None),
    agent_details=AGENT,
) as invoke_scope:
    reply = f"Echo: {message}"
    invoke_scope.record_response(reply)
```

After the scope ends and before you send the HTTP response, force one export
so that this short lab produces a deterministic console result:

```python
provider.force_flush()
```

Production services normally let the batch processor export on its schedule.

Do not use a real environment identifier as `agent_id` in this local-only
experiment.

## 6. Run and observe

```powershell
uv run python .\agent.py
```

Send the `/chat` request again.

Observe both results:

1. The echo response is unchanged.
2. The console shows one structured span with `gen_ai` attributes.

The exact trace and span identifiers will be different on each run. Do not
record them.

## Comprehension checkpoint

Explain what changed when the package was added.

Correct model:

> The Agent 365 SDK added structured instrumentation to the runtime. It did
> not register the agent, issue an identity token, or prove backend ingestion.

## Compare with the solution

After you complete the lab:

```powershell
code --diff .\agent.py ..\solution\agent.py
code --diff .\pyproject.toml ..\solution\pyproject.toml
```

## Primary sources

- [`microsoft/Agent365-python`](https://github.com/microsoft/Agent365-python)
- [`python/observability-with-otlp`](https://github.com/microsoft/Agent365-Samples/tree/main/python/observability-with-otlp)
- [OpenTelemetry Python documentation](https://opentelemetry.io/docs/languages/python/)

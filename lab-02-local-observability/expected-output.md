# Lab 2 expected observations

| Check | Safe observation |
| --- | --- |
| `/chat` response | `Echo: hello` |
| Agent 365 observability enabled | Yes |
| Microsoft exporter enabled | No |
| Local structured span | One invocation span |
| `gen_ai` attributes | Present |
| Microsoft backend ingestion | Not proved |
| Enterprise Agent Identity token | Absent |

The span proves local instrumentation. It does not prove that Microsoft
received or displayed the telemetry.

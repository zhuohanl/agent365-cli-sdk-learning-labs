# Lab 1 expected observations

| Check | Safe observation |
| --- | --- |
| Baseline `/chat` | `Echo: hello` |
| Blueprint reference | Present |
| Enterprise Agent Identity reference | Present |
| Registry registration reference | Present |
| Messaging endpoint | Record the dry-run result; expected to be skipped for the current non-M365 path |
| Azure infrastructure | Record the dry-run result and clean up any created resources |
| Agent 365 SDK import | Absent |
| `/chat` after registration | `Echo: hello` |

The important result is not that the echo works. The important result is that
the runtime behavior is the same before and after registration.

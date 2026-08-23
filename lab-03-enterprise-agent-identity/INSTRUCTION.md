# Lab 3: Bind one runtime path to an Enterprise Agent Identity

## Learning objective

Connect one outbound path in the Python runtime to an Enterprise Agent
Identity. Observe token acquisition and Microsoft Graph authorization as two
separate checks.

## Key lesson

The Enterprise Agent Identity is an Entra principal, not only an item shown in
the Agent Registry. The sidecar can obtain a resource token that represents
this identity.

When `agent.py` requests and presents that token, the tested outbound resource
call becomes bound to the Enterprise Agent Identity. This is a partial
binding. It does not bind the full process, model, prompt, endpoint, or every
tool.

## What this lab proves

- A sidecar can request an app-only resource token that represents an
  Enterprise Agent Identity.
- The Python runtime becomes connected to that identity only when it requests
  and uses the token.
- Microsoft Graph authorizes each operation from the application roles in the
  token.
- A token can be valid but lack permission for one Graph operation.

## What this lab does not prove

- Hosting workload identity
- Workload identity federation
- Delegated or on-behalf-of access
- Microsoft 365 channel invocation
- Control of the model, prompt, every tool, or Python process
- Cryptographic JWT validation by the local validator

## Components

| Component | Responsibility in this lab |
| --- | --- |
| Blueprint credential | Authenticates the blueprint client to Entra |
| Enterprise Agent Identity | Is the principal represented by the resource token |
| Entra Auth SDK sidecar | Requests and returns the resource authorization header |
| `agent.py` | Chooses when to request and use the header |
| Microsoft Graph | Validates the token and enforces operation permissions |
| Registry record | Does not participate in this token request |

## Prerequisites

- Complete Lab 1 and keep its disposable registration.
- Keep the generated config files only in the ignored Lab 1 workspace.
- Keep the blueprint credential in an approved secret store.
- Complete Lab 2 or understand its local observability result.
- Sign in to Azure CLI for the test tenant.
- Start Docker Desktop.

## 1. Create a working copy

From this lab directory:

```powershell
Copy-Item .\starter .\workspace -Recurse
Copy-Item `
    ..\lab-01-registration-only\workspace\a365.generated.config.json `
    .\workspace\
Set-Location .\workspace
```

The repository ignores the workspace and generated config file. The run
script gets the tenant context from the active Azure CLI account.

## 2. Confirm the observable runtime baseline

```powershell
uv sync
uv run python .\agent.py
```

Send the `/chat` request from `requests.http`. Confirm:

- The response is `Echo: hello`.
- One local invocation span appears.
- No sidecar or identity token is involved.

Stop the runtime.

## 3. Inspect inherited permission types

```powershell
a365 query-entra inheritance
a365 query-entra instance-scopes
```

Separate these two lists:

- Delegated scopes are used by a user-context or OBO token.
- Application roles are used by an app-only token.

This lab requests an app-only token. Microsoft Graph checks its `roles` claim,
not its delegated `scp` claim.

## Checkpoint A: Token acquisition outside the runtime

### 4. Add the sidecar

Create `sidecar/compose.yaml` from the solution. Important settings:

```yaml
DownstreamApis__graph-app__Scopes__0: https://graph.microsoft.com/.default
DownstreamApis__graph-app__RequestAppToken: "true"
```

`.default` includes permissions that are already granted and consented. It
does not grant a new permission.

The local port must stay restricted:

```yaml
ports:
  - "127.0.0.1:5000:5000"
```

### 5. Add the safe validator

Create `sidecar/validate.py` from the solution. It reports only booleans and a
resource category.

The validator decodes the JWT payload only to support this controlled
experiment. It does not verify the JWT signature. A protected API, such as
Microsoft Graph, is the enforcement point that validates the token.

### 6. Add the run script

Create `sidecar/run.ps1` from the solution.

The script:

1. Reads generated identifiers without printing them.
2. Prompts for the blueprint secret.
3. Starts a fixed sidecar image.
4. Runs the validator.
5. Removes the secret and unrelated identifiers from the parent environment.
6. Starts the Python runtime.
7. Cleans the containers, network, and environment in a `finally` block.

Run it:

```powershell
.\sidecar\run.ps1
```

Expected safe validator results include:

```text
token_acquired=True
jwt_decodable=True
idtyp_is_app=True
identity_matches_requested_agent=True
audience_category=microsoft-graph
has_create_as_manager_role=True
VALIDATION_COMPLETE=True
```

If `has_create_as_manager_role=False`, continue and record it. The later
manager-role probe is then expected to return `authorization-denied`. This is
a valid result that shows the role did not enter the app-only token. Inspect
the current CLI permission setup and consent state before you change it.

At this point, `validate.py` has proved token acquisition. `agent.py` has not
yet participated.

## Checkpoint B: Connect the real runtime path

### 7. Add a sidecar client to `agent.py`

Add:

```python
SIDECAR_URL = os.environ.get("SIDECAR_URL", "http://127.0.0.1:5000")
AGENT_CLIENT_ID = os.environ.get("AGENT_CLIENT_ID")
```

Add a function that requests:

```text
/AuthorizationHeaderUnauthenticated/graph-app
    ?AgentIdentity=<Enterprise Agent Identity client ID>
```

Use the full `acquire_graph_authorization_header()` implementation from the
solution only after you try to write it. It must:

- Fail if `AGENT_CLIENT_ID` is absent.
- Set `Host: localhost`.
- Use a timeout.
- Accept only a string that starts with `Bearer `.
- Never print or return the token to the HTTP caller.

Add `/identity-check`. Its public result contains only:

```json
{"token_acquired":true,"token_disclosed":false}
```

Send this request from `requests.http`.

You can now state:

> One explicit path in the real runtime can acquire a resource token that
> represents the Enterprise Agent Identity.

You cannot state that the whole Python process is governed.

## Checkpoint C: Let the resource enforce permissions

### 8. Add the organization permission probe

Use the returned authorization header for:

```http
GET https://graph.microsoft.com/v1.0/organization?$select=id&$top=1
```

Read and discard the response body. Return only a result category:

- `authorized`
- `authentication-rejected`
- `authorization-denied`

The expected default result is:

```json
{
  "token_acquired": true,
  "graph_result": "authorization-denied",
  "graph_data_disclosed": false
}
```

The expected `403` means:

- Entra issued a token.
- Graph received the token.
- The app-only token lacks application `Organization.Read.All`.

An inherited delegated `User.Read.All` scope cannot satisfy an app-only
operation.

### 9. Add the manager-role probe

Use the same token for this safe single-object read:

```http
GET /v1.0/servicePrincipals/{object-id}/microsoft.graph.agentIdentity?$select=id
```

The run script resolves the service principal object ID without printing it.
The runtime reads and discards the Graph body.

Expected result:

```json
{
  "manager_role_result": "authorized",
  "graph_data_disclosed": false
}
```

This operation accepts the `AgentIdentity.CreateAsManager` application role.
It is safer than the create operation, which would create a persistent Entra
object.

If the validator reported `has_create_as_manager_role=False`, expect
`authorization-denied` here instead.

## 10. Confirm that the original runtime path still works

Send `/chat` again:

```json
{"reply":"Echo: hello"}
```

The `/chat` path still does not need the Enterprise Agent Identity token.

## Comprehension checkpoint

Explain why `/organization` can return `403` while the manager-role endpoint
returns `200` with the same token.

Correct model:

> Graph checks the application role required by each operation. The token has
> `AgentIdentity.CreateAsManager`, but it does not have application
> `Organization.Read.All`.

## Stop and clean local resources

Press `Ctrl+C` in the terminal that runs `run.ps1`. The `finally` block removes
the containers and private network.

Confirm:

```powershell
docker compose -f .\sidecar\compose.yaml ps
```

No lab container must remain.

If a container remains, run:

```powershell
docker compose `
    -f .\sidecar\compose.yaml `
    down --remove-orphans
```

## Compare with the solution

After all checkpoints:

```powershell
code --diff .\agent.py ..\solution\agent.py
code --diff .\requests.http ..\solution\requests.http
```

Keep the remote registration only if you will continue with a governance
control experiment. Otherwise, use
[Security and cleanup](../docs/security-and-cleanup.md).

## Primary sources

- [`microsoft/entra-agentid-samples`](https://github.com/microsoft/entra-agentid-samples)
- [Create agentIdentity](https://learn.microsoft.com/en-us/graph/api/agentidentity-post?view=graph-rest-1.0)
- [Get agentIdentity](https://learn.microsoft.com/en-us/graph/api/agentidentity-get?view=graph-rest-1.0)
- [Microsoft Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Entra agent blueprint](https://learn.microsoft.com/en-us/entra/agent-id/agent-blueprint)

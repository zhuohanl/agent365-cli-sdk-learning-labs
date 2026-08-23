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

## How to use `expected-output.md`

Keep [`expected-output.md`](expected-output.md) open while you run the lab.
After each checkpoint, compare the safe output categories with that file.

The file is an evidence and interpretation guide, not a source-code solution.
It never contains tokens or environment identifiers. Permission-dependent
results can differ. For example, the manager-role probe is expected to be
denied when `AgentIdentity.CreateAsManager` is absent. Record the difference;
do not grant a permission only to make the output match.

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
- Keep the generated config file only in the ignored Lab 1 workspace.
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

## Checkpoint A: Acquire a token outside the runtime

Checkpoint A uses only the sidecar and a validator:

```text
validator -> sidecar -> Entra ID -> resource token

agent.py is not involved
Microsoft Graph is not called
```

### 4. Create the complete Compose file

Create the directory:

```powershell
New-Item -ItemType Directory .\sidecar
```

Create `sidecar/compose.yaml`:

```yaml
services:
  sidecar:
    image: mcr.microsoft.com/entra-sdk/auth-sidecar:1.0.0-azurelinux3.0-distroless
    environment:
      AzureAd__Instance: https://login.microsoftonline.com/
      AzureAd__TenantId: ${TENANT_ID}
      AzureAd__ClientId: ${BLUEPRINT_APP_ID}
      AzureAd__ClientCredentials__0__SourceType: ClientSecret
      AzureAd__ClientCredentials__0__ClientSecret: ${BLUEPRINT_CLIENT_SECRET}
      DownstreamApis__graph-app__BaseUrl: https://graph.microsoft.com/v1.0/
      DownstreamApis__graph-app__Scopes__0: https://graph.microsoft.com/.default
      DownstreamApis__graph-app__RequestAppToken: "true"
      ASPNETCORE_ENVIRONMENT: Production
      ASPNETCORE_URLS: http://+:5000
      AllowedHosts: "*"
    networks:
      - identity-lab
    ports:
      - "127.0.0.1:5000:5000"

  validator:
    image: mcr.microsoft.com/azure-cli:2.77.0
    depends_on:
      - sidecar
    environment:
      SIDECAR_URL: http://sidecar:5000
      AGENT_CLIENT_ID: ${AGENT_CLIENT_ID}
    volumes:
      - ./validate.py:/validate.py:ro
    command: ["python3", "/validate.py"]
    networks:
      - identity-lab

networks:
  identity-lab:
    driver: bridge
```

Read the boundaries in this file:

- `AzureAd__ClientId` is the blueprint application ID.
- `AzureAd__ClientCredentials__0__ClientSecret` proves that the sidecar holds
  the blueprint credential.
- `AGENT_CLIENT_ID` is the Enterprise Agent Identity that the validator asks
  the sidecar to represent.
- `.default` includes permissions that are already granted and consented. It
  does not grant a new permission.
- `RequestAppToken: "true"` selects an app-only token. Graph will inspect
  application roles, not delegated scopes.
- The host port is restricted to `127.0.0.1`. Do not change it to `5000:5000`.

### 5. Create the complete safe validator

Create `sidecar/validate.py`:

```python
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


SIDECAR_URL = os.environ["SIDECAR_URL"]
AGENT_CLIENT_ID = os.environ["AGENT_CLIENT_ID"]


def decode_payload(authorization_header: str) -> dict[str, object]:
    if not authorization_header.startswith("Bearer "):
        raise ValueError("Unexpected authorization scheme")

    token = authorization_header.removeprefix("Bearer ")
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Unexpected JWT shape")

    payload = parts[1]
    padded = payload + "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def audience_category(audience: object) -> str:
    if isinstance(audience, str) and audience in {
        "https://graph.microsoft.com",
        "00000003-0000-0000-c000-000000000000",
    }:
        return "microsoft-graph"
    return "other"


def request_token() -> str | None:
    query = urllib.parse.urlencode({"AgentIdentity": AGENT_CLIENT_ID})
    url = (
        f"{SIDECAR_URL}/AuthorizationHeaderUnauthenticated/graph-app"
        f"?{query}"
    )

    for _ in range(12):
        try:
            request = urllib.request.Request(
                url,
                headers={"Host": "localhost"},
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                body = json.loads(response.read())
                value = body.get("authorizationHeader")
                return value if isinstance(value, str) else None
        except (
            json.JSONDecodeError,
            TimeoutError,
            urllib.error.URLError,
        ):
            time.sleep(5)

    return None


authorization_header = request_token()
print(f"token_acquired={bool(authorization_header)}")

if not authorization_header:
    print("VALIDATION_COMPLETE=False")
    raise SystemExit(1)

try:
    claims = decode_payload(authorization_header)
except (ValueError, KeyError, json.JSONDecodeError):
    print("jwt_decodable=False")
    print("VALIDATION_COMPLETE=False")
    raise SystemExit(1)

roles = claims.get("roles", [])
has_manager_role = (
    isinstance(roles, list)
    and "AgentIdentity.CreateAsManager" in roles
)
token_identity = claims.get("appid") or claims.get("azp")

print("jwt_decodable=True")
print(f"idtyp_is_app={claims.get('idtyp') == 'app'}")
print(f"identity_matches_requested_agent={token_identity == AGENT_CLIENT_ID}")
print(f"audience_category={audience_category(claims.get('aud'))}")
print(f"has_expiry_claim={'exp' in claims}")
print(f"has_create_as_manager_role={has_manager_role}")
print("VALIDATION_COMPLETE=True")
```

This program never prints the authorization header, token, full claims,
identifiers, or role list. It prints only safe categories and booleans.

The validator decodes the JWT payload only for this controlled experiment. It
does not verify the JWT signature. A protected API, such as Microsoft Graph,
is the enforcement point that validates the token.

### 6. Create the Checkpoint A run script

Create `sidecar/run.ps1` with this Checkpoint A version. It starts the sidecar,
runs only the validator, and removes the containers. It does not start
`agent.py`.

```powershell
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$labRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $PSScriptRoot 'compose.yaml'
$generatedPath = Join-Path $labRoot 'a365.generated.config.json'

$secureSecret = $null
$secretPointer = [IntPtr]::Zero

function Get-RequiredConfigValue {
    param(
        [Parameter(Mandatory)]
        [object]$Config,

        [Parameter(Mandatory)]
        [string]$Name
    )

    $property = $Config.PSObject.Properties[$Name]
    if (
        $null -eq $property -or
        [string]::IsNullOrWhiteSpace([string]$property.Value)
    ) {
        throw (
            "$Name not found in a365.generated.config.json. " +
            'Check the field names written by the installed CLI. ' +
            'Do not paste their values.'
        )
    }

    return [string]$property.Value
}

try {
    $generated = Get-Content $generatedPath -Raw | ConvertFrom-Json

    $tenantId = az account show --query tenantId --output tsv
    if (
        $LASTEXITCODE -ne 0 -or
        [string]::IsNullOrWhiteSpace($tenantId)
    ) {
        throw 'Could not resolve the tenant from the active Azure CLI account.'
    }

    $env:TENANT_ID = [string]$tenantId
    $env:BLUEPRINT_APP_ID = Get-RequiredConfigValue `
        -Config $generated `
        -Name 'agentBlueprintId'
    $env:AGENT_CLIENT_ID = Get-RequiredConfigValue `
        -Config $generated `
        -Name 'agenticAppId'

    $secureSecret = Read-Host `
        'Enter the saved blueprint client secret' `
        -AsSecureString
    $secretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR(
        $secureSecret
    )
    $env:BLUEPRINT_CLIENT_SECRET =
        [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer)

    $required = @(
        $env:TENANT_ID
        $env:BLUEPRINT_APP_ID
        $env:BLUEPRINT_CLIENT_SECRET
        $env:AGENT_CLIENT_ID
    )

    if ($required.Where({ [string]::IsNullOrWhiteSpace($_) }).Count -ne 0) {
        throw 'One or more required local values are missing.'
    }

    docker compose -f $composeFile up -d sidecar
    if ($LASTEXITCODE -ne 0) {
        throw 'The sidecar did not start.'
    }

    docker compose -f $composeFile run --rm validator
    if ($LASTEXITCODE -ne 0) {
        throw 'The validator did not complete successfully.'
    }
}
finally {
    # Compose needs values during interpolation, but cleanup does not use
    # these placeholders to authenticate.
    $env:TENANT_ID = 'cleanup-placeholder'
    $env:BLUEPRINT_APP_ID = 'cleanup-placeholder'
    $env:BLUEPRINT_CLIENT_SECRET = 'cleanup-placeholder'
    docker compose -f $composeFile down --remove-orphans

    Remove-Item Env:TENANT_ID -ErrorAction SilentlyContinue
    Remove-Item Env:BLUEPRINT_APP_ID -ErrorAction SilentlyContinue
    Remove-Item Env:BLUEPRINT_CLIENT_SECRET -ErrorAction SilentlyContinue
    Remove-Item Env:AGENT_CLIENT_ID -ErrorAction SilentlyContinue

    if ($secretPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
    }
    if ($null -ne $secureSecret) {
        $secureSecret.Dispose()
    }
}
```

Run:

```powershell
.\sidecar\run.ps1
```

Expected safe output:

```text
token_acquired=True
jwt_decodable=True
idtyp_is_app=True
identity_matches_requested_agent=True
audience_category=microsoft-graph
has_expiry_claim=True
has_create_as_manager_role=True
VALIDATION_COMPLETE=True
```

If `has_create_as_manager_role=False`, continue and record it. This means that
the role did not enter the app-only token. Do not change permissions only to
make the output match this document.

At this checkpoint, `validate.py` has proved token acquisition. `agent.py` has
not participated, and Microsoft Graph has not validated the token.

## Checkpoint B: Connect the real runtime path

Checkpoint B changes the caller:

```text
agent.py -> sidecar -> Entra ID -> resource token

Microsoft Graph is still not called
```

### 7. Extend `run.ps1` to start the runtime

In `sidecar/run.ps1`, insert this block immediately after the validator
exit-code check and before the outer `finally`:

```powershell
    # The Python runtime needs the Agent Identity ID. It does not need the
    # blueprint credential or tenant configuration.
    Remove-Item Env:TENANT_ID -ErrorAction SilentlyContinue
    Remove-Item Env:BLUEPRINT_APP_ID -ErrorAction SilentlyContinue
    Remove-Item Env:BLUEPRINT_CLIENT_SECRET -ErrorAction SilentlyContinue

    Push-Location $labRoot
    try {
        $env:SIDECAR_URL = 'http://127.0.0.1:5000'
        Write-Host 'Use requests.http from a second terminal.'
        uv run python .\agent.py
    }
    finally {
        Pop-Location
        Remove-Item Env:SIDECAR_URL -ErrorAction SilentlyContinue
    }
```

The cleanup placeholders are already present in the Checkpoint A script, so
Compose can still parse the file after the real secret is removed.

### 8. Add the complete token client delta to `agent.py`

Add these standard-library imports near the top:

```python
import urllib.error
import urllib.parse
import urllib.request
```

After the `AGENT` definition, add:

```python
SIDECAR_URL = os.environ.get("SIDECAR_URL", "http://127.0.0.1:5000")
AGENT_CLIENT_ID = os.environ.get("AGENT_CLIENT_ID")
```

Below those constants, add:

```python
def acquire_graph_authorization_header() -> str:
    if not AGENT_CLIENT_ID:
        raise RuntimeError("AGENT_CLIENT_ID is not configured")

    query = urllib.parse.urlencode({"AgentIdentity": AGENT_CLIENT_ID})
    url = (
        f"{SIDECAR_URL}/AuthorizationHeaderUnauthenticated/graph-app"
        f"?{query}"
    )
    request = urllib.request.Request(url, headers={"Host": "localhost"})

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as error:
        error.close()
        raise RuntimeError(
            f"Sidecar returned HTTP {error.code}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError("Sidecar is unavailable") from error

    authorization_header = body.get("authorizationHeader")
    if not isinstance(authorization_header, str):
        raise RuntimeError("Sidecar response has no authorization header")
    if not authorization_header.startswith("Bearer "):
        raise RuntimeError("Sidecar returned an unexpected authorization scheme")

    return authorization_header
```

This function returns the authorization header only to code inside
`agent.py`. It does not print it.

In `AgentHandler`:

1. Rename the existing `do_POST` method to `handle_post`.
2. Add these two methods before `handle_post`:

```python
    def send_json(self, status: int, value: dict[str, object]) -> None:
        response = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_POST(self) -> None:
        try:
            self.handle_post()
        except RuntimeError as error:
            self.send_json(502, {"error": str(error)})
```

At the start of `handle_post`, before the `/chat` path check, add:

```python
        if self.path == "/identity-check":
            authorization_header = acquire_graph_authorization_header()
            self.send_json(
                200,
                {
                    "token_acquired": bool(authorization_header),
                    "token_disclosed": False,
                },
            )
            return
```

Replace the existing `InvokeAgentScope` and response block at the end of the
`/chat` path with this complete block:

```python
        with InvokeAgentScope.start(
            request=Request(content=[message]),
            scope_details=InvokeAgentScopeDetails(endpoint=None),
            agent_details=AGENT,
        ) as invoke_scope:
            reply = f"Echo: {message}"
            invoke_scope.record_response(reply)

        # Make the one-request learning result visible without waiting for the
        # batch processor schedule.
        provider.force_flush()
        self.send_json(200, {"reply": reply})
```

Do not return or print `authorization_header`.

### 9. Add the Checkpoint B REST request

Append to `requests.http`:

```http
### Runtime-to-sidecar token acquisition
# Expected: {"token_acquired":true,"token_disclosed":false}
POST {{baseUrl}}/identity-check
Accept: application/json
```

Run:

```powershell
.\sidecar\run.ps1
```

While the script keeps `agent.py` running, send `/identity-check` from VS Code
REST Client.

Expected result:

```json
{"token_acquired":true,"token_disclosed":false}
```

You can now state:

> One explicit path in the real runtime can acquire a resource token that
> represents the Enterprise Agent Identity.

You cannot state that Graph accepted the token or that the whole Python
process is governed.

## Checkpoint C: Let Microsoft Graph enforce permissions

Checkpoint C adds the protected resource:

```text
agent.py -> sidecar -> Entra ID -> resource token -> Microsoft Graph
                                                   -> 200, 401, or 403
```

### 10. Resolve the Agent Identity object ID

The token request uses the Enterprise Agent Identity client ID. The safe
single-object Graph endpoint uses its service principal object ID. These are
different identifiers.

In `sidecar/run.ps1`, add this block after `AGENT_CLIENT_ID` is loaded and
before the secret prompt:

```powershell
    $agentObjectId = az ad sp show `
        --id $env:AGENT_CLIENT_ID `
        --query id `
        --output tsv

    if (
        $LASTEXITCODE -ne 0 -or
        [string]::IsNullOrWhiteSpace($agentObjectId)
    ) {
        throw 'Could not resolve the Agent Identity service principal.'
    }

    $env:AGENT_OBJECT_ID = [string]$agentObjectId
```

Add `$env:AGENT_OBJECT_ID` to the `$required` array:

```powershell
    $required = @(
        $env:TENANT_ID
        $env:BLUEPRINT_APP_ID
        $env:BLUEPRINT_CLIENT_SECRET
        $env:AGENT_CLIENT_ID
        $env:AGENT_OBJECT_ID
    )
```

Add this line to the outer `finally`:

```powershell
    Remove-Item Env:AGENT_OBJECT_ID -ErrorAction SilentlyContinue
```

Do not print the object ID.

### 11. Add shared Graph status handling

In `agent.py`, add these constants after `AGENT_CLIENT_ID`:

```python
AGENT_OBJECT_ID = os.environ.get("AGENT_OBJECT_ID")
GRAPH_PROBE_URL = (
    "https://graph.microsoft.com/v1.0/organization"
    "?$select=id&$top=1"
)
```

After `acquire_graph_authorization_header()`, add:

```python
def request_graph_status(url: str) -> int:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": acquire_graph_authorization_header(),
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        return status
    except urllib.error.URLError as error:
        raise RuntimeError("Microsoft Graph is unavailable") from error


def graph_result(status: int) -> str:
    if status == 200:
        return "authorized"
    if status == 401:
        return "authentication-rejected"
    if status == 403:
        return "authorization-denied"
    raise RuntimeError(f"Graph returned unexpected HTTP status {status}")
```

`response.read()` consumes and discards the Graph response. The lab endpoint
returns no Graph object data.

### 12. Add the organization permission probe

At the start of `handle_post`, after `/identity-check`, add:

```python
        if self.path == "/graph-check":
            result = graph_result(request_graph_status(GRAPH_PROBE_URL))
            self.send_json(
                200,
                {
                    "token_acquired": True,
                    "graph_result": result,
                    "graph_data_disclosed": False,
                },
            )
            return
```

Append to `requests.http`:

```http
### Graph operation without the required application permission
# Expected by default: authorization-denied
POST {{baseUrl}}/graph-check
Accept: application/json
```

This path calls:

```http
GET https://graph.microsoft.com/v1.0/organization?$select=id&$top=1
```

Expected default result:

```json
{
  "token_acquired": true,
  "graph_result": "authorization-denied",
  "graph_data_disclosed": false
}
```

The expected `403` means:

- Entra issued a token.
- Graph received and validated the token.
- The app-only token lacks application `Organization.Read.All`.

An inherited delegated `User.Read.All` scope cannot satisfy an app-only
operation.

### 13. Add the manager-role probe

After `graph_result()`, add:

```python
def check_manager_role() -> str:
    if not AGENT_OBJECT_ID:
        raise RuntimeError("AGENT_OBJECT_ID is not configured")

    object_id = urllib.parse.quote(AGENT_OBJECT_ID, safe="")
    url = (
        "https://graph.microsoft.com/v1.0/servicePrincipals/"
        f"{object_id}/microsoft.graph.agentIdentity"
        "?$select=id"
    )
    return graph_result(request_graph_status(url))
```

At the start of `handle_post`, after `/graph-check`, add:

```python
        if self.path == "/manager-role-check":
            self.send_json(
                200,
                {
                    "manager_role_result": check_manager_role(),
                    "graph_data_disclosed": False,
                },
            )
            return
```

Append to `requests.http`:

```http
### Graph operation authorized by AgentIdentity.CreateAsManager
# Expected when the role is present: authorized
POST {{baseUrl}}/manager-role-check
Accept: application/json
```

This path calls:

```http
GET /v1.0/servicePrincipals/{object-id}/microsoft.graph.agentIdentity?$select=id
```

The runtime reads and discards the Graph body.

Expected result when `AgentIdentity.CreateAsManager` is in the token:

```json
{
  "manager_role_result": "authorized",
  "graph_data_disclosed": false
}
```

If the validator reported `has_create_as_manager_role=False`, expect
`authorization-denied` instead. That is a valid result.

This read operation accepts the `AgentIdentity.CreateAsManager` application
role. It is safer than the create operation, which would create a persistent
Entra object.

## 14. Confirm that the original runtime path still works

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

Only after all checkpoints:

```powershell
code --diff .\agent.py ..\solution\agent.py
code --diff .\requests.http ..\solution\requests.http
code --diff .\sidecar\run.ps1 ..\solution\sidecar\run.ps1
code --diff .\sidecar\validate.py ..\solution\sidecar\validate.py
code --diff .\sidecar\compose.yaml ..\solution\sidecar\compose.yaml
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

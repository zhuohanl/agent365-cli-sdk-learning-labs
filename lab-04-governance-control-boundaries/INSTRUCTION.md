# Lab 4: Test governance control boundaries

## Learning objective

Separate three controls that are easy to call "block":

1. Block the Registry entry.
2. Disable the Enterprise Agent Identity.
3. Stop the third-party compute.

Use the same Lab 3 runtime and change one administrative state at a time.

## Key lesson

A control affects the real runtime only where execution depends on the gate
that the control owns.

- Registry Block is an administrative availability control on supported
  Microsoft surfaces.
- Enterprise Agent Identity Disable is an Entra authentication control.
- Compute stop is a hosting-platform control.

These controls are not interchangeable.

## What this lab proves

- Whether Registry Block changes this local token path.
- Whether Enterprise Agent Identity Disable changes fresh token acquisition.
- Whether either control stops the token-independent `/chat` path.
- How to classify visibility, identity, administrative control, runtime
  enforcement, and evidence.

## What this lab does not prove

- Universal behavior for every Microsoft 365 agent host.
- Instant revocation of tokens that were issued before a state change.
- Conditional Access behavior.
- Microsoft 365 Activity channel blocking.
- A hosting-platform stop or quarantine operation.
- Prompt, model, or internal-tool governance.

## How to use `expected-output.md`

Keep [`expected-output.md`](expected-output.md) open during the lab. It contains
the expected boundary and the safe result categories.

It is not a requirement to make every result match. Administrative state can
take time to propagate, and permissions differ between environments. Record
the actual safe category in `governance-matrix.md`. Never record a token,
identifier, account name, or raw administrative response.

## Components

| Component | Responsibility in this lab |
| --- | --- |
| Agent Registry | Stores visibility and administrative availability state |
| Enterprise Agent Identity | Owns the Entra principal state used for token issuance |
| Entra Auth SDK sidecar | Requests a new resource token |
| Microsoft Graph | Enforces token and application-role requirements |
| `agent.py` | Owns the local `/chat` and outbound token paths |
| Local host | Owns the Python process lifecycle |

## Prerequisites

- Complete Labs 1-3.
- Finish Lab 3 with the Registry entry **Unblocked**.
- Finish Lab 3 with the Enterprise Agent Identity **Enabled**.
- Keep the disposable registration and generated config file.
- Keep the blueprint credential in an approved secret store.
- Have permission to block and unblock the test Registry entry.
- Have permission to disable and enable the test Enterprise Agent Identity.
- Start Docker Desktop.

Do not use a production agent for this lab.

## 1. Create the Lab 4 workspace

From the Lab 4 directory:

```powershell
New-Item -ItemType Directory .\workspace

Copy-Item `
    ..\lab-03-enterprise-agent-identity\solution\* `
    .\workspace `
    -Recurse

Copy-Item `
    ..\lab-03-enterprise-agent-identity\solution\.python-version `
    .\workspace `
    -Force

Copy-Item .\starter\* .\workspace -Recurse -Force

Copy-Item `
    ..\lab-01-registration-only\workspace\a365.generated.config.json `
    .\workspace\

Set-Location .\workspace
uv sync
```

The workspace now contains:

- The completed Lab 3 runtime and sidecar.
- A Lab 4 REST request file.
- A blank governance evidence matrix.
- The ignored generated config file.

## 2. Understand why Lab 4 needs a different runner

The Lab 3 runner executes the validator before it starts `agent.py`. If token
acquisition fails, the validator exits and the runtime never starts.

That behavior is correct for Lab 3, but it would hide the Lab 4 question:

> Does identity failure stop the token-independent `/chat` path?

Lab 4 therefore starts a fresh sidecar and the Python runtime without making
validator success a prerequisite.

## 3. Create the governance runner

Create `sidecar/run-governance-check.ps1` with this complete content:

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
        $env:AGENT_OBJECT_ID
    )

    if ($required.Where({ [string]::IsNullOrWhiteSpace($_) }).Count -ne 0) {
        throw 'One or more required local values are missing.'
    }

    # Remove any previous sidecar so that this run cannot reuse its token cache.
    docker compose -f $composeFile down --remove-orphans
    docker compose -f $composeFile up --force-recreate -d sidecar
    if ($LASTEXITCODE -ne 0) {
        throw 'The sidecar did not start.'
    }

    # The Python runtime needs the Agent Identity references, not the
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
}
finally {
    Remove-Item Env:BLUEPRINT_CLIENT_SECRET -ErrorAction SilentlyContinue

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
    Remove-Item Env:AGENT_OBJECT_ID -ErrorAction SilentlyContinue

    if ($secretPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
    }
    if ($null -ne $secureSecret) {
        $secureSecret.Dispose()
    }
}
```

The important change is the absence of:

```powershell
docker compose -f $composeFile run --rm validator
```

The runtime starts even when a later token request is denied.

Each script run also uses `--force-recreate`. Stop the previous run before you
change an administrative state. This prevents the next observation from using
the previous sidecar container and its token cache.

## Checkpoint A: Establish the baseline

### 4. Confirm both administrative states

Before you run the baseline:

- Agent Registry state: **Unblocked**
- Enterprise Agent Identity state: **Enabled**

Use display names to locate the disposable objects. Do not copy identifiers
into the worksheet.

### 5. Start a fresh run

Terminal A:

```powershell
.\sidecar\run-governance-check.ps1
```

Terminal B or VS Code REST Client:

1. Send `/chat`.
2. Send `/identity-check`.
3. Send `/manager-role-check`.
4. Optionally send `/graph-check` to reconfirm the permission boundary.

Record only these categories in `governance-matrix.md`:

```text
chat=working|not-working
token=acquired|denied
manager-role=authorized|authorization-denied|token-not-acquired
```

If `AgentIdentity.CreateAsManager` was not present in Lab 3, the manager-role
result remains `authorization-denied`. Token acquisition is the primary
identity signal.

Stop Terminal A with `Ctrl+C`. Confirm that no sidecar remains:

```powershell
docker compose -f .\sidecar\compose.yaml ps
```

## Checkpoint B: Block the Registry entry

### 6. Change only Registry state

Keep the Enterprise Agent Identity **Enabled**.

In the current Microsoft 365 admin center:

1. Open the Agent Registry or All agents view.
2. Locate the disposable learning agent by display name.
3. Select **Block**.
4. Confirm that the Registry state is **Blocked**.

The exact navigation labels can change. Do not disable the Entra identity in
this checkpoint.

### 7. Start another fresh run

```powershell
.\sidecar\run-governance-check.ps1
```

Repeat the three probes:

1. `/chat`
2. `/identity-check`
3. `/manager-role-check`

Record the actual categories. Do not infer token behavior from the blocked
label alone.

Interpret each path separately:

```text
/chat
  depends on local Python compute
  does not depend on Registry routing

/identity-check
  depends on sidecar and Entra token issuance

/manager-role-check
  depends on token acquisition and Graph authorization
```

Stop the run.

### 8. Restore Registry state

In the same administrative view, select **Unblock**. Confirm that the Registry
state is **Unblocked** before you continue.

Do not leave the learning agent blocked.

## Checkpoint C: Disable the Enterprise Agent Identity

### 9. Change only identity state

Keep the Registry entry **Unblocked**.

In the current Microsoft Entra admin center:

1. Open **Agents**, then **Agent identities**. If this view is not available,
   use **Enterprise applications**.
2. Locate the disposable Enterprise Agent Identity by display name.
3. Confirm that you selected the Agent Identity, not the blueprint.
4. Open its properties.
5. Set the sign-in or account-enabled state to **Disabled**.
6. Save and confirm the disabled state.

The exact property label can change. The control must set the service
principal `accountEnabled` state to false.

### 10. Start another fresh run

```powershell
.\sidecar\run-governance-check.ps1
```

Send `/chat` first. This establishes whether the Python process still runs
without a token.

Then send `/identity-check`. A denied token request can return HTTP `502` from
the local lab endpoint because `agent.py` converts the sidecar failure into a
safe error response. Do not paste the raw response or sidecar logs. Record:

```text
token=denied
```

Do not treat a failed `/manager-role-check` as a separate Graph authorization
result when token acquisition failed. Record:

```text
manager-role=token-not-acquired
```

If a fresh token still succeeds immediately:

1. Stop the run.
2. Confirm that the identity is disabled.
3. Allow time for administrative-state propagation.
4. Start a new run with another fresh sidecar.

Do not use a token from an earlier run as evidence of new token issuance.

Stop the run.

### 11. Restore identity state and verify recovery

Re-enable the same Enterprise Agent Identity. Confirm:

- Registry state: **Unblocked**
- Enterprise Agent Identity state: **Enabled**

After the state propagates, start one final fresh run and repeat:

1. `/chat`
2. `/identity-check`
3. `/manager-role-check`

Record the restored baseline, then stop the run.

## Checkpoint D: Build the governance matrix

### 12. Classify the two tested controls

In `governance-matrix.md`, classify:

- Registry Block
- Enterprise Agent Identity Disable
- Third-party compute stop

Use the observed dependency, not the control name.

Example reasoning:

```text
If /chat remains available:
  the tested control did not stop local compute

If fresh token acquisition fails:
  the tested control reached Entra authentication

If Graph cannot be reached because no token exists:
  Graph authorization was not the failing gate
```

### 13. Complete the capability and governance matrix

Use Labs 1-4 and the primary sources below. Do not run every capability.

For each row, answer:

1. Does CLI registration alone provide it?
2. Is Agent 365 SDK runtime code required?
3. Is Microsoft 365 Agents SDK or another adapter required?
4. Is another product, licence, admin role, or preview required?
5. Must the third-party runtime change?
6. What evidence supports the answer?

Keep these distinctions:

- Permission inheritance is not a permission grant for every operation.
- Observability is evidence; it is not general runtime enforcement.
- Tool permission is not tool execution.
- Channel blocking is not compute stop.
- Identity disable is not prompt or model policy.
- Third-party-native audit and IAM remain third-party controls.

After you complete the matrix, compare it with
`solution/governance-matrix.example.md`.

## Comprehension checkpoint

Explain why this result is possible:

```text
Registry: Blocked
Enterprise Agent Identity: Enabled
Local /chat: Working
Fresh token: Acquired
```

Correct model:

> The Registry, Entra identity system, and local host own different gates. A
> Registry Block does not automatically disable the Enterprise Agent Identity
> or terminate externally hosted Python compute.

Then explain the inverse:

```text
Registry: Unblocked
Enterprise Agent Identity: Disabled
Local /chat: Working
Fresh token: Denied
```

Correct model:

> Identity Disable reaches the token-dependent resource path. The local echo
> path still runs because it does not require that token.

## Final state and cleanup

Do not finish the lab until:

```text
Registry state: Unblocked
Enterprise Agent Identity state: Enabled
Local sidecar: Stopped
Local runtime: Stopped
```

If a container remains:

```powershell
docker compose `
    -f .\sidecar\compose.yaml `
    down --remove-orphans
```

Keep the remote registration only if you will continue the full learning
sequence. Otherwise, use
[Security and cleanup](../docs/security-and-cleanup.md).

## Compare with the solution

Only after all checkpoints:

```powershell
code --diff `
    .\sidecar\run-governance-check.ps1 `
    ..\solution\sidecar\run-governance-check.ps1

code --diff `
    .\governance-matrix.md `
    ..\solution\governance-matrix.example.md
```

## Primary sources

- [Manage agents in the Microsoft 365 admin center](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/agent-actions)
- [Disable Microsoft Entra agent identities](https://learn.microsoft.com/en-us/entra/agent-id/disable-agent-identities)
- [Agent 365 CLI reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/)
- [Agent 365 SDK](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-sdk)
- [Agent 365 observability](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/observability)
- [`microsoft/Agent365-devTools` at the source baseline](https://github.com/microsoft/Agent365-devTools/tree/1e611b2cb3219aea5d78711a9ef436358416572f)

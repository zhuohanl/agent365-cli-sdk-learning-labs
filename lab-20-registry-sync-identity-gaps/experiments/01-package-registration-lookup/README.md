# Read a companion registration with the connector application identity

Use `Get-CompanionRegistration.ps1` to check whether the deployed connector's
Graph application identity can read one companion registration. On success,
the script shows HTTP 200 and selected registration fields. On failure, it
shows the HTTP status and the available Graph error code and message.

The script gets an application token and makes this read-only request:

```http
GET https://graph.microsoft.com/beta/copilot/agentRegistrations/{registrationId}
```

It does not create, update, or delete registrations. It does not save
credentials, tokens, or response files. The registration API is a preview API.

## Prerequisites

- PowerShell 7 or later (`pwsh`).
- Network access to `login.microsoftonline.com` and `graph.microsoft.com`.
- The Graph tenant and application IDs from the active Azure Container Apps
  revision: `GRAPH_TENANT_ID` and `GRAPH_CLIENT_ID`.
- The existing client secret value for that application, obtained through an
  approved secret-access path. For the connector deployment, the ACA
  `graph-client-secret` reference uses the Key Vault secret with the same name.
- The exact `registeredAgentId` from the connector's mapping record. The
  default Cosmos database is `cust-conn-db` and the container is
  `registered_agents`; deployment settings can override these names.

The token uses the application's existing, consented Graph permissions.
The documented GET permission is `AgentRegistration.Read.All`. Do not create
a new credential or change permissions just to run this probe.

This script does not use your browser login or the ACA managed identity.

## 1. Set the tenant and application IDs

Set these entries in the single ignored `.env` at the Lab 20 root:

```dotenv
A365_TENANT_ID=<value-of-ACA-GRAPH_TENANT_ID>
A365_CLIENT_ID=<value-of-ACA-GRAPH_CLIENT_ID>
```

Both values must be non-empty GUIDs. The script reads only these two settings
from the file. It does not use process environment variables as a fallback.
Missing or invalid settings stop the script before authentication.

The default file location is:

```text
lab-20-registry-sync-identity-gaps\.env
```

The path is relative to the script, not to your current working directory.
Changing this shared file also changes the identity selected by other lab
experiments. Do not copy the `.env` into this experiment directory.

## 2. Get the registration ID

Find the companion's mapping in `registered_agents` and copy the
`registeredAgentId` value exactly.

Do not substitute `sourcePlatformAgentId`, a Copilot package ID, or a value
constructed by adding `companion:` to a source ID. Conversely, do not reject
a stored registration ID only because it starts with `companion:`.

Pass the unencoded value. The script encodes it for the URL path.

## 3. Run the script

Open an interactive PowerShell 7 terminal. From the Lab 20 root:

```powershell
Set-Location .\experiments\01-package-registration-lookup
.\Get-CompanionRegistration.ps1 -RegistrationId '<registeredAgentId>'
```

At the hidden prompt, enter the application's **client secret value**, not
its secret ID. Do not put the secret in a command, screenshot, or tracked file.

To select another existing, approved `.env` file:

```powershell
.\Get-CompanionRegistration.ps1 `
  -RegistrationId '<registeredAgentId>' `
  -EnvFile 'C:\approved-local-path\.env'
```

Each HTTP request has a 30-second timeout by default. To change it:

```powershell
.\Get-CompanionRegistration.ps1 `
  -RegistrationId '<registeredAgentId>' `
  -TimeoutSeconds 60
```

The allowed timeout is 1 to 120 seconds per request. There are two requests:
token acquisition and registration GET. The script does not retry them.

## 4. Read the result

| Result | Meaning |
| --- | --- |
| HTTP 200 and JSON output | The selected application identity read the registration, and its returned `id` exactly matches the requested ID. |
| Token request failure | Authentication did not complete. No registration GET was sent. |
| Registration GET failure | The script reports the status and available Graph error. A permission message, including one in an HTTP 500 response, does not by itself establish the cause. |
| HTTP 200 with a different or missing `id` | The script rejects the response instead of treating it as a successful lookup. |
| Network or timeout failure | No usable HTTP response was available for that request. |

Successful JSON output includes `httpStatus`, the selected tenant and client
IDs, and registration fields such as `id`, `sourceAgentId`, `displayName`,
`originatingStore`, `createdBy`, `managedByAppId`, and identity IDs.
Optional fields can be null.

Keep any captured output under the lab's ignored
`evidence\experiments\01-package-registration-lookup` directory. Do not commit
real identifiers or raw evidence. Do not share tokens or authentication
responses, or upload them to public token-decoding websites.

No platform cleanup is required because the probe makes no platform writes.

## References

- [Get agentRegistration](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/admin-settings/agent-registration/agentregistration-get)
- Lab overview: `..\..\docs\http-experiments.md`

# Security and cleanup

These labs create local processes and can create persistent Entra and Agent
365 objects.

## Never store these values

- Tenant identifiers
- Blueprint or application identifiers
- Service principal identifiers
- Registration identifiers
- Client secrets
- Access tokens
- Private endpoints

The repository ignores the common generated files, but ignore rules are not a
security boundary. Check staged files before every commit.

Treat both Agent 365 config files as sensitive local state. Their fields and
secret-handling behavior can change between CLI versions. Do not assume that a
generated file is safe because one version omitted a credential.

## Client-secret limitation

Lab 3 uses a client secret because it is the smallest local sidecar
experiment. A client secret is portable. It does not prove that one approved
host is the only workload that can request the token.

A production design should use a supported hosting workload identity and
workload identity federation where possible.

## Local sidecar

Lab 3 binds the sidecar port to `127.0.0.1`. The sample sidecar endpoint is
unauthenticated. Do not bind it to all network interfaces.

Any process on the local host can call this endpoint while it runs. Stop the
sidecar as soon as the checkpoint ends.

Do not share output from `docker inspect` or `docker compose config`. Container
environment output can contain the blueprint credential.

The run script:

1. Reads the secret with a secure interactive prompt.
2. Starts the sidecar.
3. Removes the secret from the environment before it starts the Python
   runtime.
4. Deletes the containers and network in a `finally` block.
5. Clears temporary environment variables.

## Remote cleanup

Inspect current help before cleanup:

```powershell
a365 cleanup azure --help
a365 cleanup instance --help
a365 cleanup blueprint --help
```

If the Lab 1 dry-run created Azure infrastructure, inspect and run its cleanup:

```powershell
a365 cleanup azure --agent-name "A365LearningLab" --dry-run
a365 cleanup azure --agent-name "A365LearningLab"
```

Then remove the disposable registration and blueprint:

```powershell
a365 cleanup instance --agent-name "A365LearningLab"
a365 cleanup blueprint --agent-name "A365LearningLab"
```

Confirm that the registry entry, Enterprise Agent Identity, and blueprint no
longer exist. Current CLI help or dry-run output can show less detail than the
actual cleanup implementation, so verify the result in the administrative
surfaces.

## Local cleanup

After remote cleanup, remove only the known lab workspaces:

```powershell
Remove-Item .\lab-01-registration-only\workspace -Recurse -Force
Remove-Item .\lab-02-local-observability\workspace -Recurse -Force
Remove-Item .\lab-03-enterprise-agent-identity\workspace -Recurse -Force
```

Run these commands from the repository root. Confirm each path before you
remove it.

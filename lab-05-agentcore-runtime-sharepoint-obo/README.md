# Lab 5: AgentCore Runtime delegated SharePoint OBO

This lab proves delegated user assertion forwarding, child Agent Identity OBO,
bounded SharePoint retrieval, and OPA enforcement before protected content is
downloaded.

Follow [INSTRUCTION.md](INSTRUCTION.md) for the complete workflow and
[expected-output.md](expected-output.md) for the public-safe acceptance
evidence.

## Mandatory Gate 4 prerequisite: publish the Purview label map

Gate 4 is configuration-first. A Purview administrator must publish the
current sensitivity-label ID-to-display-name mapping before every initial
deployment and after labels are added, replaced, renamed, retired, or
republished.

Run:

```powershell
pwsh -NoProfile -File .\scripts\Export-Gate4LabelDefinitions.ps1 `
  -BindingPath .\binding.local.yaml
```

The command:

- signs in as the current Azure user unless `-UserPrincipalName` is supplied;
- requires a Purview administrator who can run `Get-Label`;
- performs no Purview write;
- verifies that the configured protected label resolves exactly once; and
- writes `gate4-labels.local.json`, which is ignored by Git.

`Deploy-Gate2Azure.ps1` refuses to deploy Gate 4 when this file is missing,
empty, or does not contain the configured protected label.

At runtime, an extracted label ID is resolved in this order:

1. the published local mapping;
2. Microsoft Graph v1.0
   `/security/dataSecurityAndGovernance/sensitivityLabels/{labelId}` using the
   Container App managed identity and application `SensitivityLabel.Read`;
3. the legacy delegated beta endpoint for diagnostic compatibility.

If an ID remains unresolved, the controller fails closed and does not request
file content.

## Publication ownership and cadence

The Purview administration owner is responsible for refreshing the mapping.
Refresh it:

- before the first Gate 4 deployment;
- after any sensitivity-label lifecycle or publication-policy change;
- before a proof run when the last publication time cannot be established;
  and
- on the production policy-bundle reconciliation cadence.

The ignored mapping is environment state, not source code. Do not commit label
IDs, tenant identifiers, administrator identities, or generated mapping
content.

## Reproducible label-definition probes

Run the ordinary delegated-user diagnostic for the legacy beta API:

```powershell
uv run python -u .\scripts\diagnose_label_definition_delegated.py `
  --binding .\binding.local.yaml
```

It verifies the Graph audience and delegated scopes, then probes `/me`, the
legacy beta label collection, and the sibling beta policy-settings endpoint.
It records only statuses, response types, gateway/error-shape flags, and
correlation-header presence under ignored `evidence/`.

Run the supported v1.0 managed-identity diagnostic against the configured
protected label:

```powershell
pwsh -NoProfile -File .\scripts\Test-Gate4V1LabelDefinition.ps1 `
  -BindingPath .\binding.local.yaml
```

The container-local diagnostic verifies `SensitivityLabel.Read`, calls the
v1.0 `dataSecurityAndGovernance` endpoint, and reports whether the returned
name matches the Purview-admin snapshot. It does not print the label ID,
access token, or response body.

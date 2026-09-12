# Registry Sync identity findings

Agent 365 inventory and agent registration are separate public API resources
within the broader Agent Registry product.

| Concern | Package / inventory | Agent registration |
| --- | --- | --- |
| Purpose | Organization-wide agent catalog | Registration lifecycle record |
| Resource | `copilotPackage` | `agentRegistration` |
| Identifier | Package ID | Registration ID |
| List | `GET /v1.0/copilot/admin/catalog/packages` | Not documented; collection probe returned `404` |
| Get | `GET /v1.0/copilot/admin/catalog/packages/{id}` | `GET /beta/copilot/agentRegistrations/{id}` |
| Create | Not documented | `POST /beta/copilot/agentRegistrations` |
| Update | `PATCH /beta/copilot/admin/catalog/packages/{id}` | `PATCH /beta/copilot/agentRegistrations/{id}` |
| Delete | Not documented | `DELETE /beta/copilot/agentRegistrations/{id}` |
| Other operations | Block, unblock, reassign | None documented |
| Identity links | Not documented | Blueprint ID and Entra Agent ID |
| Source metadata | Limited inventory metadata | Source agent, store, and managing app |

These are separate API resources, but their identifier values are not always
different. In the API-created control, the Registration ID also appeared as
the new Package ID. The Registry Sync package still exposed no documented way
to obtain a corresponding Registration ID.

For the observed Google Vertex AI Registry Sync record:

- Package List and Package Details succeeded.
- Connected Platform and Google Vertex AI markers were present.
- The provider-native agent ID existed only in nested platform metadata.
- No Blueprint ID was present, and the Entra Agent ID was null.
- No documented Agent Registration ID was exposed.

Registry Sync therefore exposes the agent through the Package API, but the
current public APIs do not expose its corresponding `agentRegistration`. This
does not prove that no internal registration exists.

The proposed identity update remains blocked for Registry Sync because
`PATCH /beta/copilot/agentRegistrations/{id}` requires an addressable
registration. The Registry Sync Package ID, provider source ID, and nested
`ManagedBy` metadata have not been documented as valid substitutes.

## Fresh companion experiment

On 2026-09-08, the experiment owner reported successful completion of the
notebook's fresh-companion path:

- the companion used a distinct deterministic source ID rather than the
  provider-native `SourceAgentId`;
- `POST /beta/copilot/agentRegistrations` returned `201`;
- GET by the returned Registration ID succeeded;
- the original Registry Sync Package remained unchanged; and
- the source-to-package-to-registration mapping was saved in local state.

This distinguishes the result from the failed same-source requests. It proves
that one separately named, caller-managed companion could be created and read
in the current experiment. It does not enrich the synchronized Package or
establish production support, runtime authentication, governance enforcement,
or a general cross-provider contract.
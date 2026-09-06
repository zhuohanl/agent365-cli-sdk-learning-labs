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

## Next bounded experiment

A registration created with the same provider-native `SourceAgentId` produced
a second Package instead of updating the Registry Sync Package. The original
record remained unchanged. Creating a parallel registration is therefore not
a supported enrichment mechanism for the synchronized record.
# Lab 20 expected HTTP results

| Step | Request | Expected success | What it proves |
| --- | --- | --- | --- |
| 1 | `POST /{tenant}/oauth2/v2.0/devicecode` | `200 OK` with a short-lived device code | The public client can start delegated authentication |
| 3 | `POST /{tenant}/oauth2/v2.0/token` | `200 OK` with a token whose scope includes `CopilotPackages.Read.All` | The approved user and app can obtain the required delegated scope |
| 4 | `GET /v1.0/copilot/admin/catalog/packages` | `200 OK` with a `value` collection | Package inventory is readable |
| 5 | `GET /v1.0/copilot/admin/catalog/packages/{id}` | `200 OK` with one package-detail object | The selected package's documented detail fields are readable |

## Error interpretation

| Result | Classification |
| --- | --- |
| `401 Unauthorized` | authentication-denied |
| `403 Forbidden` | permission-denied |
| `404 Not Found` for the selected package | unavailable |
| OAuth `authorization_pending` | sign-in is not complete; retry after the stated interval |
| Successful response without an identity field | field absent in this response, not automatically unsupported |
| No documented package-to-registration identifier | identity enrichment feasibility remains inconclusive |

## Required observation after Step 5

Record only field presence, without values:

```text
package_detail_status=<supported|permission-denied|unavailable|inconclusive>
package_id_matches=<true|false|inconclusive>
platform_present=<true|false>
asset_id_present=<true|false>
owner_metadata_present=<true|false>
source_agent_id_present=<true|false>
blueprint_id_present=<true|false>
entra_agent_id_present=<true|false>
registration_id_exposed=<true|false|not-documented>
```

Do not record the agent name, package ID, asset ID, tenant ID, client ID,
token, endpoint, owner ID, or raw response.

## Selected GCP sample observation

```text
package_detail_status=supported
package_id_matches=true
platform_present=true
connected_platform_marker_present=true
google_vertex_ai_provider_marker_present=true
asset_id_present=false
owner_metadata_present=false
top_level_source_agent_id_present=false
nested_source_agent_id_present=true
blueprint_id_present=false
entra_agent_id_present=false
top_level_managed_by_app_id_present=false
nested_managed_by_reference_present=true
originating_store_present=false
registration_id_exposed=not-documented
```

The nested source identifier proves that Registry Sync retains a correlation
to the provider-native agent. It does not prove that the value is an Entra
Agent ID or Agent Registration ID.

## Agent Registration collection probe

```text
authentication_status=supported
requested_scope=AgentRegistration.Read.All
collection_request=GET /beta/copilot/agentRegistrations
collection_response=404
registration_collection_available=false
registration_list_operation=supported=false
```

The `404` is not an empty registration collection. It means no usable
collection endpoint was observed at that route. The experiment must not
replace it with guessed identifiers or undocumented portal calls.

## Current Agent Registration create boundary

For the four sampled GCP Registry Sync sources in the completed live probe:

```text
delegated_write_scope_present=true
caller_supplied_as_creator_and_owner=true
identity_fields_supplied=false
managing_app_supplied=false
package_source_timestamps_verified=true
new_registration_post_success_count=0
new_registration_post_permission_denied_count=4
confirmed_new_registration_ids=0
```

One source had historically returned `201`. Its known registration supported
GET and description PATCH, was permanently deleted with `204`, and then
returned the same `500` backend permission denial when recreated with the
original successful body. This is a create-specific observed boundary, not
evidence that the delegated scope is missing or that Blueprint fields are
required.

Do not automatically retry POST or use delete-and-recreate as recovery. PATCH
a known owned registration when available. Without a supported lookup and a
known Registration ID, classify association as blocked and retain protected
diagnostic evidence for product investigation.

## Fresh companion observation

For the later GCP experiment using a deterministic source ID that did not
equal the Registry Sync provider source ID:

```text
companion_source_differs_from_provider_source=true
companion_source_format=committed-fleet:companion:v1
registration_create_status=supported
registration_readback_status=supported
original_package_identity_unchanged=true
mapping_saved_locally=true
runtime_binding=not-tested
governance_enforcement=not-tested
cross_provider_result=inconclusive
cleanup_status=retained
```

This is evidence for one separately managed companion, not evidence that the
original synchronized Package was updated.

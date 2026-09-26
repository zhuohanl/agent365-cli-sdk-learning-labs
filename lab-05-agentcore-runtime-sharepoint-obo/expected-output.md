# Lab 5 expected observations

## Local validation

```text
24 passed
ARM64_IMAGE_BUILD=True
AMD64_MCP_IMAGE_BUILD=True
LOCAL_VALIDATION_COMPLETE=True
```

## Gate 1

Public-safe evidence records booleans and result classes only:

```json
{
  "gate": 1,
  "valid_token_delivered": true,
  "invalid_token_rejected": true,
  "raw_token_in_logs": false,
  "raw_token_in_response": false,
  "two_subjects_distinct": true,
  "two_sessions_distinct": true,
  "cross_session_state_reuse": false
}
```

A Runtime response may contain process-local safe subject and session
references. It must not contain a token, claim value, tenant value, user
identifier, application identifier, Runtime identifier, or endpoint.

## Gate 2

```json
{
  "gate": 2,
  "runtime_was_network_caller": true,
  "container_app_managed_identity_used": true,
  "blueprint_federation_used": true,
  "human_subject_present": true,
  "child_actor_present": true,
  "graph_audience_valid": true,
  "delegated_sites_selected_present": true,
  "fixed_site_metadata_http_status": 200,
  "expected_site_matched": true,
  "unauthorized_user_denied": true,
  "microsoft_token_returned_to_aws": false,
  "two_subjects_distinct": true,
  "two_runtime_sessions_distinct": true,
  "two_correlations_distinct": true,
  "cross_user_cache_reuse": false
}
```

Token issuance without the fixed Graph HTTP 200 result does not pass Gate 2.
At least one test user must receive the fixed-site HTTP 200. A second user
who lacks SharePoint access may receive HTTP 403; that denial is valid
isolation evidence when the Graph token subject still matches that user.

## Gate 3

```json
{
  "gate": 3,
  "model_selected_bounded_tool": true,
  "deterministic_code_attached_credentials": true,
  "model_visible_credentials": false,
  "safe_tool_result_returned": true,
  "grounded_answer_present": true,
  "raw_token_in_response": false,
  "raw_token_in_runtime_logs": false,
  "raw_token_in_aca_logs": false
}
```

## Gate 4

```json
{
  "gate": 4,
  "source_catalog_bounded": true,
  "readable_content_returned": true,
  "readable_citation_returned": true,
  "protected_label_resolved": true,
  "policy_enforcer": "opa",
  "protected_outcome": "denied",
  "protected_content_request_sent": false,
  "protected_content_returned": false,
  "policy_failure_mode": "fail-closed",
  "native_copilot_dlp_claimed_as_enforcer": false,
  "model_visible_credentials": false
}
```

The implementation produces this result. Live HTTP 200 evidence first
disproved native Copilot DLP enforcement for the custom Graph path. The
revised proof then used live label extraction, a Purview-admin-published
label-definition snapshot, and OPA denial before any protected `/content`
request. A successfully extracted empty label set is an explicit
`unlabeled_allowed` decision; extraction or definition failures remain
fail-closed.

The Purview-admin mapping is a mandatory deployment prerequisite. Unknown
label IDs fall back to the verified Microsoft Graph v1.0
`dataSecurityAndGovernance/sensitivityLabels/{labelId}` API with managed
identity application `SensitivityLabel.Read`. The older beta API remains only
as a diagnostic compatibility attempt.

## Failure classes

| Result | Meaning |
| --- | --- |
| `configuration-failure` | A required approved value or exact object binding is missing |
| `token-failure` | JWT validation or OBO token issuance failed |
| `mcp-failure` | Runtime could not call or authenticate to the fixed MCP probe |
| `graph-authorization-failure` | Graph or SharePoint rejected the fixed-site request |

After two distinct fixes for the same failure class, stop and preserve only
public-safe evidence.

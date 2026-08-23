# Lab 3 expected observations

## Validator

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

The validator decodes claims but does not verify the token signature.
If the manager role is absent in your permission setup, the safe value is
`False` and the manager-role request is expected to be denied.

## Runtime endpoints

| Endpoint | Expected safe result | Meaning |
| --- | --- | --- |
| `/chat` | `Echo: hello` | The original runtime path still works without the identity token |
| `/identity-check` | `token_acquired=true` | The real runtime can request the Agent Identity token |
| `/graph-check` | `authorization-denied` by default | Token issuance does not grant `Organization.Read.All` |
| `/manager-role-check` | `authorized` | Graph accepts `AgentIdentity.CreateAsManager` for this operation |

The result binds only the tested outbound paths. It does not bind or control
the full runtime.

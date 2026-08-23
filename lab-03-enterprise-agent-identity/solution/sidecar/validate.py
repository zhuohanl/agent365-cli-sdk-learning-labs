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
            request = urllib.request.Request(url, headers={"Host": "localhost"})
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

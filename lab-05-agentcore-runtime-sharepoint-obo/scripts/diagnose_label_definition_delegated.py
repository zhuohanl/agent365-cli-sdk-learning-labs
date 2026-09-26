from __future__ import annotations

import argparse
import base64
import json
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from invoke_gate1 import acquire_token, read_yaml_scalars


def token_claims(token: str) -> dict[str, object]:
    segment = token.split(".")[1]
    segment += "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(segment))


def probe(url: str, token: str) -> dict[str, object]:
    client_request_id = str(uuid.uuid4())
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Agent365Lab05/1.0",
            "Client-Request-Id": client_request_id,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            return {
                "http_status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "request_id_present": bool(
                    response.headers.get("request-id")
                ),
                "client_request_id_returned": (
                    response.headers.get("client-request-id")
                    == client_request_id
                ),
            }
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        return {
            "http_status": error.code,
            "content_type": error.headers.get("Content-Type"),
            "server": error.headers.get("Server"),
            "request_id_present": bool(error.headers.get("request-id")),
            "client_request_id_returned": (
                error.headers.get("client-request-id")
                == client_request_id
            ),
            "gateway_html": (
                "Microsoft-Azure-Application-Gateway" in body
            ),
            "graph_json_error": body.lstrip().startswith("{"),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", required=True, type=Path)
    args = parser.parse_args()

    binding = read_yaml_scalars(args.binding)
    state = json.loads(
        args.binding.with_name("state.local.json").read_text(
            encoding="utf-8"
        )
    )
    token = acquire_token(
        binding["entra.tenant_id"],
        state["entra"]["publicClientAppId"],
        binding["entra.public_client_redirect_uri"],
        (
            "https://graph.microsoft.com/User.Read "
            "https://graph.microsoft.com/InformationProtectionPolicy.Read"
        ),
    )
    try:
        claims = token_claims(token)
        scopes = str(claims.get("scp", "")).split()
        result = {
            "graph_audience_valid": claims.get("aud")
            in (
                "00000003-0000-0000-c000-000000000000",
                "https://graph.microsoft.com",
            ),
            "user_read_scope_valid": "User.Read" in scopes,
            "information_protection_scope_valid": (
                "InformationProtectionPolicy.Read" in scopes
            ),
            "me": probe(
                "https://graph.microsoft.com/v1.0/me?$select=id",
                token,
            ),
            "legacy_beta_labels": probe(
                "https://graph.microsoft.com/beta/me/security/"
                "informationProtection/sensitivityLabels",
                token,
            ),
            "legacy_beta_policy_settings": probe(
                "https://graph.microsoft.com/beta/me/security/"
                "informationProtection/labelPolicySettings",
                token,
            ),
        }
    finally:
        token = ""

    evidence_path = (
        args.binding.parent
        / "evidence"
        / "label-definition-delegated-diagnostic.json"
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()

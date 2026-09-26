from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid


def main() -> None:
    mapping = json.loads(
        base64.b64decode(
            os.environ["LABEL_NAMES_B64"],
            validate=True,
        ).decode("utf-8")
    )
    protected_name = os.environ["PROTECTED_LABEL_NAME"]
    label_ids = [
        label_id
        for label_id, label_name in mapping.items()
        if label_name == protected_name
    ]
    if len(label_ids) != 1:
        raise RuntimeError("protected-label-id-not-unique")

    endpoint = os.environ["IDENTITY_ENDPOINT"]
    separator = "&" if "?" in endpoint else "?"
    identity_url = endpoint + separator + urllib.parse.urlencode(
        {
            "resource": "https://graph.microsoft.com",
            "api-version": "2019-08-01",
        }
    )
    identity_request = urllib.request.Request(
        identity_url,
        headers={
            "X-IDENTITY-HEADER": os.environ["IDENTITY_HEADER"],
            "Metadata": "true",
        },
    )
    with urllib.request.urlopen(identity_request, timeout=30) as response:
        token = json.load(response)["access_token"]

    segment = token.split(".")[1]
    segment += "=" * (-len(segment) % 4)
    claims = json.loads(base64.urlsafe_b64decode(segment))
    client_request_id = str(uuid.uuid4())
    url = (
        "https://graph.microsoft.com/v1.0/security/"
        "dataSecurityAndGovernance/sensitivityLabels/"
        + urllib.parse.quote(label_ids[0], safe="")
    )
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
            payload = json.load(response)
            result = {
                "http_status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "sensitivity_label_read_role_valid": (
                    "SensitivityLabel.Read" in claims.get("roles", [])
                ),
                "name_matches_config": (
                    payload.get("name") or payload.get("displayName")
                )
                == protected_name,
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
        result = {
            "http_status": error.code,
            "content_type": error.headers.get("Content-Type"),
            "server": error.headers.get("Server"),
            "sensitivity_label_read_role_valid": (
                "SensitivityLabel.Read" in claims.get("roles", [])
            ),
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
    finally:
        token = ""
    print(json.dumps(result))


if __name__ == "__main__":
    main()

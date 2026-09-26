from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from functools import lru_cache

import boto3


class Gate2CallError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_mcp_key() -> str:
    secret_id = os.environ.get("GATE2_SECRET_ID", "")
    if not secret_id:
        raise Gate2CallError("gate2-secret-not-configured")
    response = boto3.client("secretsmanager").get_secret_value(
        SecretId=secret_id
    )
    value = response.get("SecretString")
    if not isinstance(value, str) or not value:
        raise Gate2CallError("gate2-secret-empty")
    return value


def invoke_mcp_tool(
    user_assertion: str,
    correlation_reference: str,
    tool_name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    endpoint = os.environ.get("GATE2_MCP_URL", "")
    if not endpoint:
        raise Gate2CallError("gate2-endpoint-not-configured")
    body = {
        "jsonrpc": "2.0",
        "id": correlation_reference,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }
    request = urllib.request.Request(
        endpoint,
        method="POST",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": " ".join(("Bearer", user_assertion)),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-mcp-key": get_mcp_key(),
            "x-correlation-reference": correlation_reference,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        error.close()
        raise Gate2CallError(f"gate2-http-{error.code}") from error
    result = payload.get("result")
    if not isinstance(result, dict):
        raise Gate2CallError("gate2-result-missing")
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        raise Gate2CallError("gate2-structured-result-missing")
    return structured


def invoke_fixed_site_metadata(
    user_assertion: str,
    correlation_reference: str,
) -> dict[str, object]:
    return invoke_mcp_tool(
        user_assertion,
        correlation_reference,
        "sharepoint.fixed_site_metadata",
        {},
    )

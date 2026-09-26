from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import jwt


def read_yaml_scalars(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    parents: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indentation = len(raw_line) - len(raw_line.lstrip())
        if ":" not in raw_line:
            continue
        key, value = raw_line.strip().split(":", 1)
        level = indentation // 2
        parents = parents[:level]
        parents.append(key.strip())
        value = value.strip().strip("\"'")
        if value:
            values[".".join(parents)] = value
    return values


class CallbackHandler(BaseHTTPRequestHandler):
    result: dict[str, str] = {}
    expected_state = ""

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        state = query.get("state", [""])[0]
        if state != self.expected_state:
            self.send_response(400)
            self.end_headers()
            return
        type(self).result = {
            "code": query.get("code", [""])[0],
            "error": query.get("error", [""])[0],
        }
        body = b"Authentication complete. Return to the terminal."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def handle_callback_requests(server: HTTPServer, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    server.timeout = min(0.5, timeout)
    while not CallbackHandler.result and time.monotonic() < deadline:
        server.handle_request()


def post_form(url: str, values: dict[str, str]) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(values).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def acquire_token(
    tenant_id: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
) -> str:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    state = secrets.token_urlsafe(24)
    CallbackHandler.result = {}
    CallbackHandler.expected_state = state

    parsed_redirect = urllib.parse.urlparse(redirect_uri)
    server = HTTPServer(
        (parsed_redirect.hostname or "localhost", parsed_redirect.port or 80),
        CallbackHandler,
    )
    thread = threading.Thread(
        target=handle_callback_requests,
        args=(server, 180),
        daemon=True,
    )
    thread.start()

    authorize_url = (
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize?"
        + urllib.parse.urlencode(
            {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "response_mode": "query",
                "scope": scope,
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "prompt": "login",
            }
        )
    )
    webbrowser.open(authorize_url)
    thread.join(timeout=180)
    server.server_close()

    if thread.is_alive():
        raise RuntimeError("Interactive authorization callback timed out.")
    oauth_error = CallbackHandler.result.get("error", "")
    if oauth_error:
        raise RuntimeError(
            f"Interactive authorization failed with OAuth error: {oauth_error}."
        )
    code = CallbackHandler.result.get("code", "")
    if not code:
        raise RuntimeError("Interactive authorization did not return a code.")

    token_response = post_form(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        {
            "client_id": client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "code_verifier": verifier,
        },
    )
    access_token = token_response.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError("Token endpoint returned no access token.")
    return access_token


def invoke_runtime(
    runtime_arn: str,
    region: str,
    access_token: str,
    operation: str = "gate1-check",
    payload: dict[str, object] | None = None,
    timeout_seconds: int = 180,
) -> dict[str, object]:
    escaped_arn = urllib.parse.quote(runtime_arn, safe="")
    url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/"
        f"{escaped_arn}/invocations?qualifier=DEFAULT"
    )
    session_id = secrets.token_urlsafe(32)
    request_payload = {"operation": operation}
    if payload:
        request_payload.update(payload)
    request = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(request_payload).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        },
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            body = json.load(response)
            return {
                "http_status": response.status,
                "runtime_session_id": session_id,
                "token_received": body.get("token_received") is True,
                "token_validated": body.get("token_validated") is True,
                "token_disclosed": body.get("token_disclosed") is True,
                "subject_reference": body.get("subject_reference"),
                "session_reference": body.get("session_reference"),
                "graph_http_status": body.get("graph_http_status"),
                "site_matched": body.get("site_matched"),
                "graph_audience_valid": body.get("graph_audience_valid"),
                "graph_actor_valid": body.get("graph_actor_valid"),
                "graph_subject_matches": body.get("graph_subject_matches"),
                "sites_selected_scope_valid": body.get(
                    "sites_selected_scope_valid"
                ),
                "user_reference": body.get("user_reference"),
                "correlation_reference": body.get("correlation_reference"),
                "microsoft_token_returned": body.get(
                    "microsoft_token_returned"
                ),
                "answer": body.get("answer"),
                "tool_calls": body.get("tool_calls"),
                "tool_observations": body.get("tool_observations"),
                "model_input_safe": body.get("model_input_safe"),
            }
    except urllib.error.HTTPError as error:
        error.close()
        return {"http_status": error.code}


def summarize_token_validation(
    access_token: str,
    *,
    expected_issuer: str,
    expected_audience: str,
    expected_client: str,
    expected_scope: str,
) -> dict[str, bool]:
    claims = jwt.decode(
        access_token,
        options={
            "verify_signature": False,
            "verify_aud": False,
            "verify_exp": False,
        },
    )
    audience = claims.get("aud")
    authorized_client = claims.get("azp") or claims.get("appid")
    scopes = claims.get("scp")
    return {
        "issuer_matches": claims.get("iss") == expected_issuer,
        "audience_matches": audience == expected_audience,
        "authorized_client_matches": authorized_client == expected_client,
        "scope_matches": (
            isinstance(scopes, str) and expected_scope in scopes.split()
        ),
        "subject_present": isinstance(claims.get("sub"), str),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--label", required=True, choices=["user-a", "user-b"])
    args = parser.parse_args()

    binding = read_yaml_scalars(args.binding)
    state = json.loads(
        args.binding.with_name("state.local.json").read_text(encoding="utf-8")
    )
    entra = state["entra"]
    aws = state["aws"]
    scope = (
        f"api://{entra['blueprintAppId']}/"
        f"{binding['entra.required_scope']}"
    )

    access_token = acquire_token(
        binding["entra.tenant_id"],
        entra["publicClientAppId"],
        binding["entra.public_client_redirect_uri"],
        scope,
    )
    try:
        token_validation = summarize_token_validation(
            access_token,
            expected_issuer=(
                "https://login.microsoftonline.com/"
                f"{binding['entra.tenant_id']}/v2.0"
            ),
            expected_audience=entra["blueprintAppId"],
            expected_client=entra["publicClientAppId"],
            expected_scope=binding["entra.required_scope"],
        )
        result = invoke_runtime(
            aws["runtimeArn"],
            binding["aws.region"],
            access_token,
        )
    finally:
        access_token = ""

    if result.get("runtime_session_id"):
        state.setdefault("sessions", {})[args.label] = result["runtime_session_id"]
        args.binding.with_name("state.local.json").write_text(
            json.dumps(state, indent=2),
            encoding="utf-8",
        )

    evidence = {
        "gate": 1,
        "user_label": args.label,
        "http_status": result.get("http_status"),
        "token_received": result.get("token_received", False),
        "token_validated": result.get("token_validated", False),
        "token_disclosed": result.get("token_disclosed", False),
        "subject_reference": result.get("subject_reference"),
        "session_reference": result.get("session_reference"),
        "token_claim_validation": token_validation,
    }
    evidence_path = args.binding.parent / "evidence" / f"gate1-{args.label}.json"
    evidence_path.parent.mkdir(exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "user_label": args.label,
                "http_status": evidence["http_status"],
                "token_validated": evidence["token_validated"],
                "token_disclosed": evidence["token_disclosed"],
                "token_claim_validation": token_validation,
            }
        )
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import jwt

from scripts.invoke_gate1 import (
    CallbackHandler,
    handle_callback_requests,
    summarize_token_validation,
)


LAB_ROOT = Path(__file__).resolve().parents[1]


def test_callback_handler_records_authorization_code() -> None:
    CallbackHandler.result = {}
    CallbackHandler.expected_state = "expected-state"
    server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:"
            f"{server.server_port}/?code=authorization-code"
            "&state=expected-state",
            timeout=5,
        ) as response:
            assert response.status == 200
    finally:
        thread.join(timeout=5)
        server.server_close()

    assert CallbackHandler.result == {
        "code": "authorization-code",
        "error": "",
    }


def test_callback_server_ignores_stale_state_then_accepts_valid_code() -> None:
    CallbackHandler.result = {}
    CallbackHandler.expected_state = "current-state"
    server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
    thread = threading.Thread(
        target=handle_callback_requests,
        args=(server, 5),
    )
    thread.start()

    try:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/"
                "?code=stale-code&state=stale-state",
                timeout=5,
            )
        except urllib.error.HTTPError as error:
            assert error.code == 400
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/"
            "?code=current-code&state=current-state",
            timeout=5,
        ) as response:
            assert response.status == 200
    finally:
        thread.join(timeout=5)
        server.server_close()

    assert CallbackHandler.result["code"] == "current-code"


def test_agentcore_authorizer_matches_entra_azp_claim() -> None:
    template = (LAB_ROOT / "infrastructure" / "template.yaml").read_text(
        encoding="utf-8"
    )

    assert "          AllowedClients:" not in template
    assert "InboundTokenClaimName: azp" in template
    assert "MatchValueString: !Ref AllowedClient" in template


def test_token_diagnostics_report_matches_without_disclosing_claims() -> None:
    token = jwt.encode(
        {
            "iss": "https://issuer.example/v2.0",
            "aud": "resource-client",
            "azp": "public-client",
            "scp": "access_agent",
            "sub": "user-subject",
        },
        key="",
        algorithm="none",
    )

    result = summarize_token_validation(
        token,
        expected_issuer="https://issuer.example/v2.0",
        expected_audience="resource-client",
        expected_client="public-client",
        expected_scope="access_agent",
    )

    assert result == {
        "issuer_matches": True,
        "audience_matches": True,
        "authorized_client_matches": True,
        "scope_matches": True,
        "subject_present": True,
    }
    assert "user-subject" not in str(result)

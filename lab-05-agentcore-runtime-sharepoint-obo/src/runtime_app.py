from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Mapping

from .gate2_client import Gate2CallError, invoke_fixed_site_metadata
from .model_loop import ModelLoopError, run_model_loop
from .token_validation import (
    OidcTokenValidator,
    SafeReferenceFactory,
    TokenRejectedError,
    TokenValidator,
    ValidationSettings,
    extract_bearer_token,
    get_header,
)


LOGGER = logging.getLogger("gate1")
logging.basicConfig(level=logging.INFO, format="%(message)s")

SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"
REFERENCES = SafeReferenceFactory()


def process_invocation(
    headers: Mapping[str, str],
    payload: object,
    validator: TokenValidator,
    references: SafeReferenceFactory = REFERENCES,
) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("unsupported-request")

    token = extract_bearer_token(headers)
    try:
        identity = validator.validate(token)
        session_id = get_header(headers, SESSION_HEADER)
        if not session_id:
            raise ValueError("runtime-session-missing")
        if payload.get("operation") == "gate2-check":
            correlation = references.create("correlation", session_id)
            result = invoke_fixed_site_metadata(token, correlation)
            return {
                "gate": 2,
                **result,
                "token_received": True,
                "token_validated": True,
                "token_disclosed": False,
                "subject_reference": references.create(
                    "subject",
                    f"{identity.issuer}|{identity.subject}",
                ),
                "session_reference": references.create(
                    "session", session_id
                ),
            }
        if payload.get("operation") in {"gate3-check", "gate4-check"}:
            mode = "gate3" if payload["operation"] == "gate3-check" else "gate4"
            user_message = payload.get("message")
            if not isinstance(user_message, str):
                raise ValueError("user-message-missing")
            correlation = references.create("correlation", session_id)
            loop = run_model_loop(
                mode=mode,
                user_message=user_message,
                user_assertion=token,
                correlation_reference=correlation,
            )
            return {
                "gate": 3 if mode == "gate3" else 4,
                "answer": loop.answer,
                "tool_calls": list(loop.tool_calls),
                "tool_observations": list(loop.tool_observations),
                "model_input_safe": loop.model_input_safe,
                "token_received": True,
                "token_validated": True,
                "token_disclosed": False,
                "subject_reference": references.create(
                    "subject",
                    f"{identity.issuer}|{identity.subject}",
                ),
                "session_reference": references.create(
                    "session", session_id
                ),
                "correlation_reference": correlation,
            }
        if payload.get("operation") != "gate1-check":
            raise ValueError("unsupported-request")
        return {
            "gate": 1,
            "token_received": True,
            "token_validated": True,
            "token_disclosed": False,
            "subject_reference": references.create(
                "subject",
                f"{identity.issuer}|{identity.subject}",
            ),
            "session_reference": references.create("session", session_id),
        }
    finally:
        token = ""


class Gate1Handler(BaseHTTPRequestHandler):
    validator: TokenValidator

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, status: int, value: dict[str, object]) -> None:
        response = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self) -> None:
        if self.path != "/ping":
            self.send_json(404, {"error": "not-found"})
            return
        self.send_json(200, {"status": "Healthy"})

    def do_POST(self) -> None:
        if self.path != "/invocations":
            self.send_json(404, {"error": "not-found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096:
                raise ValueError("invalid-content-length")
            payload = json.loads(self.rfile.read(length))
            result = process_invocation(
                headers={key: value for key, value in self.headers.items()},
                payload=payload,
                validator=self.validator,
            )
            LOGGER.info(f"gate{result.get('gate')}_invocation_complete")
            self.send_json(200, result)
        except TokenRejectedError:
            LOGGER.info("gate1_rejected_assertion")
            self.send_json(401, {"error": "invalid-user-assertion"})
        except (json.JSONDecodeError, ValueError):
            LOGGER.info("gate1_rejected_request")
            self.send_json(400, {"error": "invalid-request"})
        except Gate2CallError:
            LOGGER.info("gate2_call_failed")
            self.send_json(502, {"error": "gate2-downstream-failed"})
        except ModelLoopError:
            LOGGER.info("model_loop_failed")
            self.send_json(502, {"error": "model-loop-failed"})


def run() -> None:
    Gate1Handler.validator = OidcTokenValidator(
        ValidationSettings.from_environment()
    )
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Gate1Handler)
    LOGGER.info("gate1_runtime_started")
    server.serve_forever()


if __name__ == "__main__":
    run()

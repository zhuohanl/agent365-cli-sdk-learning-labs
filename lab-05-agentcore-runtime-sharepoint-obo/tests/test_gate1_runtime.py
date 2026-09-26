from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src import runtime_app
from src.model_loop import ModelLoopResult
from src.runtime_app import SESSION_HEADER, process_invocation
from src.token_validation import (
    OidcTokenValidator,
    SafeReferenceFactory,
    TokenRejectedError,
    ValidationSettings,
    ValidatedIdentity,
    extract_bearer_token,
)


class FakeValidator:
    def validate(self, token: str) -> ValidatedIdentity:
        if token == "rejected-token":
            raise TokenRejectedError("rejected")
        return ValidatedIdentity(
            subject=f"subject-for-{token}",
            issuer="https://issuer.example",
        )


class FakeSigningKey:
    def __init__(self, key: object) -> None:
        self.key = key


class FakeJwkClient:
    def __init__(self, public_key: object) -> None:
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
        return FakeSigningKey(self._public_key)


def create_real_validator() -> tuple[OidcTokenValidator, object]:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    settings = ValidationSettings(
        discovery_url="https://issuer.example/.well-known/openid-configuration",
        issuer="https://issuer.example",
        audience="api://blueprint",
        authorized_client="public-client",
        required_scope="invoke",
    )
    validator = object.__new__(OidcTokenValidator)
    validator._settings = settings
    validator._jwk_client = FakeJwkClient(private_key.public_key())
    return validator, private_key


def create_token(
    private_key: object,
    *,
    issuer: str = "https://issuer.example",
    audience: str = "api://blueprint",
    authorized_client: str = "public-client",
    scope: str = "invoke",
    expires_in: timedelta = timedelta(minutes=5),
) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "azp": authorized_client,
            "scp": scope,
            "sub": "user-subject",
            "iat": now,
            "exp": now + expires_in,
        },
        private_key,
        algorithm="RS256",
    )


def invoke(token: str, session_id: str) -> dict[str, object]:
    return process_invocation(
        headers={
            "Authorization": f"Bearer {token}",
            SESSION_HEADER: session_id,
        },
        payload={"operation": "gate1-check"},
        validator=FakeValidator(),
        references=SafeReferenceFactory(b"test-key"),
    )


def test_valid_token_returns_only_safe_gate_result() -> None:
    result = invoke("user-a-token", "a" * 33)

    assert result["token_received"] is True
    assert result["token_validated"] is True
    assert result["token_disclosed"] is False
    assert "user-a-token" not in str(result)
    assert "subject-for-user-a-token" not in str(result)


def test_forwarded_headers_are_case_insensitive() -> None:
    result = process_invocation(
        headers={
            "authorization": " ".join(("Bearer", "user-a-token")),
            SESSION_HEADER.lower(): "a" * 33,
        },
        payload={"operation": "gate1-check"},
        validator=FakeValidator(),
        references=SafeReferenceFactory(b"test-key"),
    )

    assert result["token_validated"] is True


def test_gate2_forwards_token_outside_model_visible_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def fake_gate2(token: str, correlation: str) -> dict[str, object]:
        captured["token"] = token
        captured["correlation"] = correlation
        return {
            "graph_http_status": 200,
            "site_matched": True,
            "microsoft_token_returned": False,
        }

    monkeypatch.setattr(runtime_app, "invoke_fixed_site_metadata", fake_gate2)
    result = process_invocation(
        headers={
            "authorization": " ".join(("Bearer", "user-a-token")),
            SESSION_HEADER.lower(): "a" * 33,
        },
        payload={"operation": "gate2-check"},
        validator=FakeValidator(),
        references=SafeReferenceFactory(b"test-key"),
    )

    assert captured["token"] == "user-a-token"
    assert captured["token"] not in str(result)
    assert result["site_matched"] is True
    assert result["microsoft_token_returned"] is False
    assert result["token_disclosed"] is False


def test_gate3_attaches_token_after_model_tool_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_loop(**kwargs: object) -> ModelLoopResult:
        captured.update(kwargs)
        return ModelLoopResult(
            answer="The configured policy site is available.",
            tool_calls=("sharepoint_fixed_site_metadata",),
            tool_observations=(
                {
                    "tool": "sharepoint_fixed_site_metadata",
                    "graph_http_status": 200,
                    "site_matched": True,
                },
            ),
            model_input_safe=True,
        )

    monkeypatch.setattr(runtime_app, "run_model_loop", fake_loop)
    result = process_invocation(
        headers={
            "Authorization": " ".join(("Bearer", "user-a-token")),
            SESSION_HEADER: "a" * 33,
        },
        payload={
            "operation": "gate3-check",
            "message": "Is the policy site available?",
        },
        validator=FakeValidator(),
        references=SafeReferenceFactory(b"test-key"),
    )

    assert captured["user_assertion"] == "user-a-token"
    assert captured["mode"] == "gate3"
    assert result["model_input_safe"] is True
    assert result["tool_calls"] == ["sharepoint_fixed_site_metadata"]
    assert "user-a-token" not in str(result)


def test_invalid_token_is_rejected() -> None:
    with pytest.raises(TokenRejectedError):
        invoke("rejected-token", "a" * 33)


def test_missing_bearer_token_is_rejected() -> None:
    with pytest.raises(TokenRejectedError):
        extract_bearer_token({})


def test_two_concurrent_sessions_keep_identity_state_separate() -> None:
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(invoke, "user-a-token", "a" * 33),
            executor.submit(invoke, "user-b-token", "b" * 33),
        ]
        first, second = [future.result() for future in futures]

    assert first["subject_reference"] != second["subject_reference"]
    assert first["session_reference"] != second["session_reference"]
    assert "user-a-token" not in str(second)
    assert "user-b-token" not in str(first)


def test_session_identifier_is_required() -> None:
    with pytest.raises(ValueError, match="runtime-session-missing"):
        process_invocation(
            headers={"Authorization": "Bearer user-a-token"},
            payload={"operation": "gate1-check"},
            validator=FakeValidator(),
            references=SafeReferenceFactory(b"test-key"),
        )


def test_signed_token_with_expected_claims_is_accepted() -> None:
    validator, private_key = create_real_validator()

    identity = validator.validate(create_token(private_key))

    assert identity.subject == "user-subject"
    assert identity.issuer == "https://issuer.example"


@pytest.mark.parametrize(
    ("claim", "value"),
    [
        ("issuer", "https://wrong-issuer.example"),
        ("audience", "api://wrong-audience"),
        ("authorized_client", "wrong-client"),
        ("scope", "wrong-scope"),
        ("expires_in", timedelta(minutes=-5)),
    ],
)
def test_signed_token_with_invalid_gate_claim_is_rejected(
    claim: str,
    value: object,
) -> None:
    validator, private_key = create_real_validator()

    with pytest.raises(TokenRejectedError):
        validator.validate(create_token(private_key, **{claim: value}))

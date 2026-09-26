from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Protocol

import jwt
from jwt import PyJWKClient


class TokenRejectedError(ValueError):
    """Raised when the forwarded user assertion is invalid."""


@dataclass(frozen=True)
class ValidatedIdentity:
    subject: str
    issuer: str


class TokenValidator(Protocol):
    def validate(self, token: str) -> ValidatedIdentity:
        """Validate a bearer token and return only the required identity."""


@dataclass(frozen=True)
class ValidationSettings:
    discovery_url: str
    issuer: str
    audience: str
    authorized_client: str
    required_scope: str

    @classmethod
    def from_environment(cls) -> "ValidationSettings":
        values = {
            "discovery_url": os.environ.get("OIDC_DISCOVERY_URL", ""),
            "issuer": os.environ.get("EXPECTED_ISSUER", ""),
            "audience": os.environ.get("EXPECTED_AUDIENCE", ""),
            "authorized_client": os.environ.get("EXPECTED_CLIENT_ID", ""),
            "required_scope": os.environ.get("REQUIRED_SCOPE", ""),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError(
                "Missing token-validation configuration: "
                + ", ".join(sorted(missing))
            )
        return cls(**values)


class OidcTokenValidator:
    def __init__(self, settings: ValidationSettings) -> None:
        self._settings = settings
        with urllib.request.urlopen(settings.discovery_url, timeout=15) as response:
            discovery = json.load(response)
        jwks_uri = discovery.get("jwks_uri")
        discovered_issuer = discovery.get("issuer")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise RuntimeError("OIDC discovery returned no JWKS URI")
        if discovered_issuer != settings.issuer:
            raise RuntimeError("OIDC discovery issuer does not match configuration")
        self._jwk_client = PyJWKClient(jwks_uri, cache_keys=True)

    def validate(self, token: str) -> ValidatedIdentity:
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._settings.audience,
                issuer=self._settings.issuer,
                options={
                    "require": ["aud", "exp", "iat", "iss", "sub"],
                    "verify_signature": True,
                },
            )
        except jwt.PyJWTError as error:
            raise TokenRejectedError("token-validation-failed") from error

        authorized_client = claims.get("azp") or claims.get("appid")
        if authorized_client != self._settings.authorized_client:
            raise TokenRejectedError("authorized-client-rejected")

        scopes = claims.get("scp")
        if not isinstance(scopes, str):
            raise TokenRejectedError("scope-missing")
        if self._settings.required_scope not in scopes.split():
            raise TokenRejectedError("scope-rejected")

        subject = claims.get("sub")
        issuer = claims.get("iss")
        if not isinstance(subject, str) or not isinstance(issuer, str):
            raise TokenRejectedError("identity-claims-missing")
        return ValidatedIdentity(subject=subject, issuer=issuer)


class SafeReferenceFactory:
    def __init__(self, key: bytes | None = None) -> None:
        self._key = key or secrets.token_bytes(32)

    def create(self, category: str, value: str) -> str:
        digest = hmac.new(
            self._key,
            f"{category}:{value}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return digest[:16]


def extract_bearer_token(headers: Mapping[str, str]) -> str:
    authorization = get_header(headers, "Authorization")
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        raise TokenRejectedError("bearer-token-missing")
    return token


def get_header(headers: Mapping[str, str], name: str) -> str:
    expected = name.casefold()
    for key, value in headers.items():
        if key.casefold() == expected:
            return value
    return ""

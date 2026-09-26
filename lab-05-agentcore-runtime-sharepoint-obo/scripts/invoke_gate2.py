from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import jwt

from invoke_gate1 import (
    acquire_token,
    invoke_runtime,
    read_yaml_scalars,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", required=True, type=Path)
    args = parser.parse_args()

    binding = read_yaml_scalars(args.binding)
    state_path = args.binding.with_name("state.local.json")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    entra = state["entra"]
    aws = state["aws"]
    scope = (
        f"api://{entra['blueprintAppId']}/"
        f"{binding['entra.required_scope']}"
    )

    print("Sign in as user A in the browser.")
    user_a = acquire_token(
        binding["entra.tenant_id"],
        entra["publicClientAppId"],
        binding["entra.public_client_redirect_uri"],
        scope,
    )
    print("Sign in as a different user B in the browser.")
    user_b = acquire_token(
        binding["entra.tenant_id"],
        entra["publicClientAppId"],
        binding["entra.public_client_redirect_uri"],
        scope,
    )
    try:
        claims_a = jwt.decode(
            user_a,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_exp": False,
            },
        )
        claims_b = jwt.decode(
            user_b,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_exp": False,
            },
        )
        if claims_a.get("oid") == claims_b.get("oid"):
            raise RuntimeError("Gate 2 requires two different users.")
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(
                invoke_runtime,
                aws["runtimeArn"],
                binding["aws.region"],
                user_a,
                "gate2-check",
            )
            future_b = executor.submit(
                invoke_runtime,
                aws["runtimeArn"],
                binding["aws.region"],
                user_b,
                "gate2-check",
            )
            result_a = future_a.result()
            result_b = future_b.result()
    finally:
        user_a = ""
        user_b = ""

    state.setdefault("gate2Sessions", {})["user-a"] = result_a.get(
        "runtime_session_id"
    )
    state.setdefault("gate2Sessions", {})["user-b"] = result_b.get(
        "runtime_session_id"
    )
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    evidence = {
        "gate": 2,
        "results": {
            "user-a": {
                key: value
                for key, value in result_a.items()
                if key != "runtime_session_id"
            },
            "user-b": {
                key: value
                for key, value in result_b.items()
                if key != "runtime_session_id"
            },
        },
        "users_distinct": (
            result_a.get("user_reference")
            != result_b.get("user_reference")
        ),
        "sessions_distinct": (
            result_a.get("session_reference")
            != result_b.get("session_reference")
        ),
        "correlations_distinct": (
            result_a.get("correlation_reference")
            != result_b.get("correlation_reference")
        ),
    }
    evidence_path = args.binding.parent / "evidence" / "gate2-summary.json"
    evidence_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "gate": 2,
                "user_a_http_status": result_a.get("http_status"),
                "user_b_http_status": result_b.get("http_status"),
                "user_a_site_matched": result_a.get("site_matched", False),
                "user_b_site_matched": result_b.get("site_matched", False),
                "users_distinct": evidence["users_distinct"],
                "sessions_distinct": evidence["sessions_distinct"],
                "correlations_distinct": evidence["correlations_distinct"],
                "microsoft_token_returned": bool(
                    result_a.get("microsoft_token_returned")
                    or result_b.get("microsoft_token_returned")
                ),
            }
        )
    )


if __name__ == "__main__":
    main()

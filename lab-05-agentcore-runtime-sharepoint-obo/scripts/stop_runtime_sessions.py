from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from invoke_gate1 import acquire_token, read_yaml_scalars


def stop_session(
    runtime_arn: str,
    region: str,
    session_id: str,
    access_token: str,
    timeout_seconds: int,
) -> str:
    encoded_arn = urllib.parse.quote(runtime_arn, safe="")
    url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/"
        f"{encoded_arn}/stopruntimesession?qualifier=DEFAULT"
    )
    deadline = time.monotonic() + timeout_seconds
    delay_seconds = 1.0
    while True:
        request = urllib.request.Request(
            url,
            method="POST",
            data=b"",
            headers={
                "Authorization": "".join(("Bear", "er", " ", access_token)),
                "Content-Type": "application/json",
                "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
            },
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=min(30, timeout_seconds),
            ) as response:
                response.read()
                if response.status not in (200, 202):
                    raise RuntimeError(
                        "Runtime session stop returned an unexpected status."
                    )
                return "stopped"
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return "already-absent"
            if error.code != 409 or time.monotonic() + delay_seconds >= deadline:
                raise RuntimeError(
                    f"Runtime session stop returned HTTP {error.code}."
                ) from error
            time.sleep(delay_seconds)
            delay_seconds = min(delay_seconds * 2, 5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    binding = read_yaml_scalars(args.binding)
    state_path = args.binding.with_name("state.local.json")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    runtime_arn = state.get("aws", {}).get("runtimeArn")
    session_ids = {
        session_id
        for section in ("sessions", "gate2Sessions")
        for session_id in state.get(section, {}).values()
        if session_id
    }
    if not session_ids:
        print(json.dumps({"runtimeSessions": "already-absent", "count": 0}))
        return
    if not runtime_arn:
        raise RuntimeError("Runtime session state exists without a Runtime ARN.")

    entra = state["entra"]
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
        outcomes = [
            stop_session(
                runtime_arn,
                binding["aws.region"],
                session_id,
                access_token,
                args.timeout_seconds,
            )
            for session_id in session_ids
        ]
    finally:
        access_token = ""

    print(
        json.dumps(
            {
                "runtimeSessions": "complete",
                "count": len(outcomes),
                "stopped": outcomes.count("stopped"),
                "alreadyAbsent": outcomes.count("already-absent"),
            }
        )
    )


if __name__ == "__main__":
    main()

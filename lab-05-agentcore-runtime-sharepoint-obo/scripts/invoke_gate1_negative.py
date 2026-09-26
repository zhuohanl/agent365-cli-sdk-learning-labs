from __future__ import annotations

import argparse
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


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


def invoke(
    runtime_arn: str,
    region: str,
    authorization: str | None,
) -> int:
    escaped_arn = urllib.parse.quote(runtime_arn, safe="")
    url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/"
        f"{escaped_arn}/invocations?qualifier=DEFAULT"
    )
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": (
            secrets.token_urlsafe(32)
        ),
    }
    if authorization is not None:
        headers["Authorization"] = authorization
    request = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps({"operation": "gate1-check"}).encode(),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as error:
        error.close()
        return error.code


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", required=True, type=Path)
    args = parser.parse_args()

    binding = read_yaml_scalars(args.binding)
    state = json.loads(
        args.binding.with_name("state.local.json").read_text(encoding="utf-8")
    )
    runtime_arn = state["aws"]["runtimeArn"]
    region = binding["aws.region"]
    evidence = {
        "gate": 1,
        "missing_token_http_status": invoke(runtime_arn, region, None),
        "malformed_token_http_status": invoke(
            runtime_arn,
            region,
            "Bearer not-a-jwt",
        ),
    }
    evidence_path = args.binding.parent / "evidence" / "gate1-negative.json"
    evidence_path.parent.mkdir(exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()

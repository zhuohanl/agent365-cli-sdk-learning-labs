from __future__ import annotations

import argparse
import json
from pathlib import Path

from invoke_gate1 import acquire_token, invoke_runtime, read_yaml_scalars


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", required=True, type=Path)
    args = parser.parse_args()

    binding = read_yaml_scalars(args.binding)
    state = json.loads(
        args.binding.with_name("state.local.json").read_text(encoding="utf-8")
    )
    entra = state["entra"]
    scope = (
        f"api://{entra['blueprintAppId']}/"
        f"{binding['entra.required_scope']}"
    )
    token = acquire_token(
        binding["entra.tenant_id"],
        entra["publicClientAppId"],
        binding["entra.public_client_redirect_uri"],
        scope,
    )
    try:
        result = invoke_runtime(
            state["aws"]["runtimeArn"],
            binding["aws.region"],
            token,
            "gate3-check",
            {"message": "Is the configured policy site available?"},
        )
    finally:
        token = ""

    answer = result.pop("answer", None)
    evidence = {
        **result,
        "gate": 3,
        "grounded_answer_present": (
            isinstance(answer, str) and bool(answer.strip())
        ),
    }
    evidence_path = args.binding.parent / "evidence" / "gate3-summary.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(evidence, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()

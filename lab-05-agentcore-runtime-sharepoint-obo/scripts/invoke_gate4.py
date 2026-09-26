from __future__ import annotations

import argparse
import json
from pathlib import Path

from invoke_gate1 import acquire_token, invoke_runtime, read_yaml_scalars


PROMPTS = {
    "readable": "Tell me the working policies.",
    "protected": "Tell me the individuals who have an exception.",
}


def summarize(label: str, result: dict[str, object]) -> dict[str, object]:
    answer = result.pop("answer", None)
    observations = result.get("tool_observations")
    read_observation = None
    if isinstance(observations, list):
        read_observation = next(
            (
                item
                for item in reversed(observations)
                if isinstance(item, dict)
                and item.get("tool") == "policy_source_read"
            ),
            None,
        )
    return {
        **result,
        "label": label,
        "grounded_answer_present": (
            isinstance(answer, str) and bool(answer.strip())
        ),
        "read_status": (
            read_observation.get("status")
            if isinstance(read_observation, dict)
            else None
        ),
        "fixture_role": (
            read_observation.get("fixture_role")
            if isinstance(read_observation, dict)
            else None
        ),
        "graph_relationships_valid": (
            all(
                read_observation.get(key) is True
                for key in (
                    "graph_audience_valid",
                    "graph_actor_valid",
                    "graph_subject_matches",
                    "sites_selected_scope_valid",
                )
            )
            if isinstance(read_observation, dict)
            else False
        ),
        "upstream_http_status": (
            read_observation.get("upstream_http_status")
            if isinstance(read_observation, dict)
            else None
        ),
        "content_returned": (
            read_observation.get("content_returned")
            if isinstance(read_observation, dict)
            else None
        ),
        "citation_returned": (
            read_observation.get("citation_returned")
            if isinstance(read_observation, dict)
            else None
        ),
        "files_read_all_scope_valid": (
            read_observation.get("files_read_all_scope_valid")
            if isinstance(read_observation, dict)
            else None
        ),
        "information_protection_scope_valid": (
            read_observation.get("information_protection_scope_valid")
            if isinstance(read_observation, dict)
            else None
        ),
        "label_resolved": (
            read_observation.get("label_resolved")
            if isinstance(read_observation, dict)
            else None
        ),
        "policy_enforcer": (
            read_observation.get("policy_enforcer")
            if isinstance(read_observation, dict)
            else None
        ),
        "policy_reason": (
            read_observation.get("policy_reason")
            if isinstance(read_observation, dict)
            else None
        ),
        "content_request_sent": (
            read_observation.get("content_request_sent")
            if isinstance(read_observation, dict)
            else None
        ),
    }


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
        results = {
            label: summarize(
                label,
                invoke_runtime(
                    state["aws"]["runtimeArn"],
                    binding["aws.region"],
                    token,
                    "gate4-check",
                    {"message": prompt},
                ),
            )
            for label, prompt in PROMPTS.items()
        }
    finally:
        token = ""

    evidence = {"gate": 4, "results": results}
    evidence_path = args.binding.parent / "evidence" / "gate4-summary.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(evidence, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()

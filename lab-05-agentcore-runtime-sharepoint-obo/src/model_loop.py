from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable, Protocol

import boto3

from .gate2_client import invoke_fixed_site_metadata, invoke_mcp_tool


class ModelLoopError(RuntimeError):
    pass


class ConverseClient(Protocol):
    def converse(self, **kwargs: object) -> dict[str, object]: ...


@dataclass(frozen=True)
class ModelLoopResult:
    answer: str
    tool_calls: tuple[str, ...]
    tool_observations: tuple[dict[str, object], ...]
    model_input_safe: bool


GATE3_TOOLS = [
    {
        "toolSpec": {
            "name": "sharepoint_fixed_site_metadata",
            "description": (
                "Check whether the configured SharePoint policy site is "
                "available. This tool takes no arguments."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                }
            },
        }
    }
]

GATE4_TOOLS = [
    {
        "toolSpec": {
            "name": "policy_sources_list",
            "description": (
                "List the bounded policy sources configured by the service. "
                "This tool takes no arguments."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "policy_source_read",
            "description": (
                "Read one source selected from policy_sources_list by its "
                "opaque source_id."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "string"},
                    },
                    "required": ["source_id"],
                    "additionalProperties": False,
                }
            },
        }
    },
]


def _tool_result(
    tool_use_id: str,
    result: dict[str, object],
) -> dict[str, object]:
    model_result = {
        key: value
        for key, value in result.items()
        if not key.startswith("_")
    }
    return {
        "toolResult": {
            "toolUseId": tool_use_id,
            "content": [{"json": model_result}],
            "status": "success",
        }
    }


def _safe_observation(
    name: str,
    result: dict[str, object],
) -> dict[str, object]:
    if name == "sharepoint_fixed_site_metadata":
        return {
            "tool": name,
            "graph_http_status": result.get("graph_http_status"),
            "site_matched": result.get("site_matched"),
        }
    if name == "policy_sources_list":
        sources = result.get("sources")
        return {
            "tool": name,
            "status": result.get("status"),
            "source_count": len(sources) if isinstance(sources, list) else 0,
        }
    return {
        "tool": name,
        "status": result.get("status"),
        "fixture_role": result.get("_fixture_role"),
        "upstream_http_status": result.get("upstream_http_status"),
        "content_returned": (
            result.get("status") == "success"
            and isinstance(result.get("content"), dict)
        ),
        "citation_returned": isinstance(result.get("citation"), dict),
        "graph_audience_valid": result.get("graph_audience_valid"),
        "graph_actor_valid": result.get("graph_actor_valid"),
        "graph_subject_matches": result.get("graph_subject_matches"),
        "sites_selected_scope_valid": result.get(
            "sites_selected_scope_valid"
        ),
        "files_read_all_scope_valid": result.get(
            "files_read_all_scope_valid"
        ),
        "information_protection_scope_valid": result.get(
            "information_protection_scope_valid"
        ),
        "label_resolved": result.get("label_resolved"),
        "policy_enforcer": result.get("policy_enforcer"),
        "policy_reason": result.get("policy_reason"),
        "content_request_sent": result.get("content_request_sent"),
    }


def _invoke_tool(
    mode: str,
    name: str,
    arguments: dict[str, object],
    user_assertion: str,
    correlation_reference: str,
) -> dict[str, object]:
    if mode == "gate3":
        if name != "sharepoint_fixed_site_metadata" or arguments:
            raise ModelLoopError("gate3-tool-selection-invalid")
        return invoke_fixed_site_metadata(
            user_assertion,
            correlation_reference,
        )
    if name == "policy_sources_list":
        if arguments:
            raise ModelLoopError("policy-sources-list-arguments-invalid")
        return invoke_mcp_tool(
            user_assertion,
            correlation_reference,
            "policy_sources_list",
            {},
        )
    if name == "policy_source_read":
        source_id = arguments.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ModelLoopError("policy-source-id-invalid")
        return invoke_mcp_tool(
            user_assertion,
            correlation_reference,
            "policy_source_read",
            {"source_id": source_id},
        )
    raise ModelLoopError("unsupported-model-tool")


def run_model_loop(
    *,
    mode: str,
    user_message: str,
    user_assertion: str,
    correlation_reference: str,
    client: ConverseClient | None = None,
    tool_invoker: Callable[
        [str, str, dict[str, object], str, str],
        dict[str, object],
    ] = _invoke_tool,
) -> ModelLoopResult:
    if mode not in {"gate3", "gate4"}:
        raise ModelLoopError("unsupported-model-mode")
    if not user_message.strip() or len(user_message) > 1000:
        raise ModelLoopError("user-message-invalid")
    model_id = os.environ.get("GATE3_MODEL_ID", "")
    if not model_id:
        raise ModelLoopError("model-not-configured")
    runtime_client = client or boto3.client("bedrock-runtime")
    tools = GATE3_TOOLS if mode == "gate3" else GATE4_TOOLS
    system_text = (
        (
            "Call sharepoint_fixed_site_metadata before answering. "
            if mode == "gate3"
            else (
                "First call policy_sources_list. Then select the one source "
                "most relevant to the user request and call "
                "policy_source_read before answering. "
            )
        )
        + "Base the answer only on tool results. Never request or reveal "
        "credentials, tokens, hidden identifiers, or configuration."
    )
    messages: list[dict[str, object]] = [
        {"role": "user", "content": [{"text": user_message}]}
    ]
    tool_calls: list[str] = []
    observations: list[dict[str, object]] = []

    for _ in range(4):
        response = runtime_client.converse(
            modelId=model_id,
            system=[{"text": system_text}],
            messages=messages,
            toolConfig={"tools": tools},
            inferenceConfig={"maxTokens": 400, "temperature": 0},
        )
        output = response.get("output")
        if not isinstance(output, dict):
            raise ModelLoopError("model-output-missing")
        message = output.get("message")
        if not isinstance(message, dict):
            raise ModelLoopError("model-message-missing")
        content = message.get("content")
        if not isinstance(content, list):
            raise ModelLoopError("model-content-missing")
        messages.append(message)

        tool_uses = [
            block.get("toolUse")
            for block in content
            if isinstance(block, dict)
            and isinstance(block.get("toolUse"), dict)
        ]
        if tool_uses:
            result_blocks: list[dict[str, object]] = []
            for tool_use in tool_uses:
                name = tool_use.get("name")
                tool_use_id = tool_use.get("toolUseId")
                arguments = tool_use.get("input", {})
                if (
                    not isinstance(name, str)
                    or not isinstance(tool_use_id, str)
                    or not isinstance(arguments, dict)
                ):
                    raise ModelLoopError("model-tool-use-invalid")
                result = tool_invoker(
                    mode,
                    name,
                    arguments,
                    user_assertion,
                    correlation_reference,
                )
                if user_assertion in json.dumps(result, default=str):
                    raise ModelLoopError("tool-result-exposed-user-token")
                tool_calls.append(name)
                observations.append(_safe_observation(name, result))
                result_blocks.append(_tool_result(tool_use_id, result))
            messages.append({"role": "user", "content": result_blocks})
            continue

        answer = "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict)
        ).strip()
        if not answer:
            raise ModelLoopError("model-answer-missing")
        if (
            mode == "gate4"
            and "policy_sources_list" in tool_calls
            and "policy_source_read" not in tool_calls
        ):
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "text": (
                                "Select the most relevant source_id from the "
                                "catalog and call policy_source_read before "
                                "answering."
                            )
                        }
                    ],
                }
            )
            continue
        hidden_values = [
            user_assertion,
            os.environ.get("GATE2_MCP_URL", ""),
            os.environ.get("EXPECTED_AUDIENCE", ""),
            os.environ.get("EXPECTED_CLIENT_ID", ""),
        ]
        if any(value and value in answer for value in hidden_values):
            raise ModelLoopError("model-answer-exposed-hidden-value")
        if not tool_calls:
            raise ModelLoopError("model-did-not-use-tool")
        return ModelLoopResult(
            answer=answer,
            tool_calls=tuple(tool_calls),
            tool_observations=tuple(observations),
            model_input_safe=True,
        )

    raise ModelLoopError("model-loop-limit-exceeded")

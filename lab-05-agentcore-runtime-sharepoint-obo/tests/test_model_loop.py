from __future__ import annotations

import json

from src.model_loop import run_model_loop


class FakeConverseClient:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def converse(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return self.responses.pop(0)


def model_message(content: list[dict[str, object]]) -> dict[str, object]:
    return {"output": {"message": {"role": "assistant", "content": content}}}


def test_gate3_model_selects_tool_without_credential_visibility(
    monkeypatch,
) -> None:
    hidden = {
        "token": "user-token-secret",
        "endpoint": "https://hidden-mcp.example/mcp",
        "blueprint": "hidden-blueprint-id",
        "client": "hidden-client-id",
        "key": "hidden-endpoint-key",
    }
    monkeypatch.setenv(
        "GATE3_MODEL_ID",
        "anthropic.claude-3-haiku-20240307-v1:0",
    )
    monkeypatch.setenv("GATE2_MCP_URL", hidden["endpoint"])
    monkeypatch.setenv("EXPECTED_AUDIENCE", hidden["blueprint"])
    monkeypatch.setenv("EXPECTED_CLIENT_ID", hidden["client"])
    client = FakeConverseClient(
        [
            model_message(
                [
                    {
                        "toolUse": {
                            "toolUseId": "tool-1",
                            "name": "sharepoint_fixed_site_metadata",
                            "input": {},
                        }
                    }
                ]
            ),
            model_message(
                [{"text": "The configured policy site is available."}]
            ),
        ]
    )
    invocations: list[tuple[object, ...]] = []

    def invoke(*args: object) -> dict[str, object]:
        invocations.append(args)
        return {
            "site_matched": True,
            "graph_http_status": 200,
            "microsoft_token_returned": False,
        }

    result = run_model_loop(
        mode="gate3",
        user_message="Is the policy site available?",
        user_assertion=hidden["token"],
        correlation_reference="safe-correlation",
        client=client,
        tool_invoker=invoke,
    )

    first_model_request = json.dumps(client.calls[0])
    for value in hidden.values():
        assert value not in first_model_request
    assert invocations[0][3] == hidden["token"]
    assert result.tool_calls == ("sharepoint_fixed_site_metadata",)
    assert result.model_input_safe is True


def test_gate4_denial_result_reaches_model_without_protected_content(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "GATE3_MODEL_ID",
        "anthropic.claude-3-haiku-20240307-v1:0",
    )
    client = FakeConverseClient(
        [
            model_message(
                [
                    {
                        "toolUse": {
                            "toolUseId": "tool-list",
                            "name": "policy_sources_list",
                            "input": {},
                        }
                    }
                ]
            ),
            model_message(
                [{"text": "The source catalog is available."}]
            ),
            model_message(
                [
                    {
                        "toolUse": {
                            "toolUseId": "tool-read",
                            "name": "policy_source_read",
                            "input": {"source_id": "opaque-protected"},
                        }
                    }
                ]
            ),
            model_message(
                [
                    {
                        "text": (
                            "Microsoft 365 denied access to the selected "
                            "source."
                        )
                    }
                ]
            ),
        ]
    )

    def invoke(
        mode: str,
        name: str,
        arguments: dict[str, object],
        token: str,
        correlation: str,
    ) -> dict[str, object]:
        if name == "policy_sources_list":
            return {
                "status": "success",
                "sources": [
                    {
                        "source_id": "opaque-protected",
                        "title": "Protected source",
                    }
                ],
            }
        return {
            "status": "denied",
            "_fixture_role": "protected",
            "source": {
                "source_id": arguments["source_id"],
                "title": "Protected source",
            },
            "message": "Microsoft 365 denied access to this source.",
        }

    result = run_model_loop(
        mode="gate4",
        user_message="Tell me the protected details.",
        user_assertion="user-token",
        correlation_reference="safe-correlation",
        client=client,
        tool_invoker=invoke,
    )

    second_tool_result = json.dumps(client.calls[3]["messages"])
    assert "protected content" not in second_tool_result.lower()
    assert "_fixture_role" not in second_tool_result
    assert result.tool_calls == (
        "policy_sources_list",
        "policy_source_read",
    )
    assert result.tool_observations[-1]["fixture_role"] == "protected"

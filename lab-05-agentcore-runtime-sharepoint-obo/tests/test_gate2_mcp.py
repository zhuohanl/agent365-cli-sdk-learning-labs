from __future__ import annotations

import base64
import io
import json

import jwt
from docx import Document

from gate2 import mcp_app


def unsigned_token(claims: dict[str, object]) -> str:
    return jwt.encode(claims, key="", algorithm="none")


def test_fixed_site_result_contains_no_microsoft_token(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AGENT_CLIENT_ID", "child-agent")
    monkeypatch.setenv("SITE_ID", "fixed-site")
    user_token = unsigned_token({"oid": "user-a", "sub": "subject-a"})
    graph_token = unsigned_token(
        {
            "aud": "https://graph.microsoft.com",
            "azp": "child-agent",
            "oid": "user-a",
            "scp": (
                "Sites.Selected Files.Read.All "
                "InformationProtectionPolicy.Read"
            ),
        }
    )
    monkeypatch.setattr(
        mcp_app,
        "call_sidecar",
        lambda assertion: graph_token,
    )
    monkeypatch.setattr(
        mcp_app,
        "request_json",
        lambda url, headers: (200, {"id": "fixed-site"}),
    )

    result = mcp_app.fixed_site_metadata(
        user_token,
        correlation_reference="correlation-a",
    )

    assert result["graph_http_status"] == 200
    assert result["site_matched"] is True
    assert result["graph_actor_valid"] is True
    assert result["graph_subject_matches"] is True
    assert result["sites_selected_scope_valid"] is True
    assert result["microsoft_token_returned"] is False
    assert graph_token not in str(result)
    assert user_token not in str(result)


def configure_gate4(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_CLIENT_ID", "child-agent")
    monkeypatch.setenv("SITE_ID", "fixed-site")
    monkeypatch.setenv("DOCUMENT_LIBRARY_NAME", "Documents")
    monkeypatch.setenv("FOLDER_PATH", "Policies")
    monkeypatch.setenv("READABLE_FILE_NAME", "Readable.docx")
    monkeypatch.setenv(
        "SECONDARY_READABLE_FILE_NAME",
        "Secondary.docx",
    )
    monkeypatch.setenv("PROTECTED_FILE_NAME", "Protected.docx")
    monkeypatch.setenv(
        "LABEL_NAMES_B64",
        base64.b64encode(
            json.dumps(
                {
                    "protected-label-id": (
                        "Confidential (Personal Data)"
                    ),
                    "readable-label-id": "Internal Use Only",
                }
            ).encode()
        ).decode(),
    )


def metadata(file_name: str) -> dict[str, object]:
    return {
        "id": f"item-{file_name}",
        "name": file_name,
        "webUrl": f"https://sharepoint.example/{file_name}",
        "file": {
            "mimeType": (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
        },
        "parentReference": {"driveId": "drive-id"},
    }


def test_policy_catalog_returns_only_configured_opaque_sources(
    monkeypatch,
) -> None:
    configure_gate4(monkeypatch)
    user_token = unsigned_token({"oid": "user-a"})
    graph_token = unsigned_token(
        {
            "oid": "user-a",
            "aud": "https://graph.microsoft.com",
            "azp": "child-agent",
            "scp": (
                "Sites.Selected Files.Read.All "
                "InformationProtectionPolicy.Read"
            ),
        }
    )
    monkeypatch.setattr(
        mcp_app,
        "call_sidecar",
        lambda assertion: graph_token,
    )

    def request(url: str, headers: dict[str, str]):
        if url.endswith("drives?%24select=id%2Cname"):
            return 200, {
                "value": [{"id": "drive-id", "name": "Documents"}]
            }
        file_name = next(
            name
            for name in mcp_app.configured_files()
            if name.replace(" ", "%20") in url
        )
        return 200, metadata(file_name)

    monkeypatch.setattr(mcp_app, "request_json", request)

    result = mcp_app.policy_sources_list(
        user_token,
        correlation_reference="correlation",
    )

    assert result["status"] == "success"
    assert len(result["sources"]) == 3
    assert all(
        source["source_id"] not in mcp_app.configured_files()
        for source in result["sources"]
    )
    assert graph_token not in str(result)
    assert user_token not in str(result)


def test_opa_denies_protected_source_before_content_request(
    monkeypatch,
) -> None:
    configure_gate4(monkeypatch)
    user_token = unsigned_token({"oid": "user-a"})
    graph_token = unsigned_token(
        {
            "oid": "user-a",
            "aud": "https://graph.microsoft.com",
            "azp": "child-agent",
            "scp": (
                "Sites.Selected Files.Read.All "
                "InformationProtectionPolicy.Read"
            ),
        }
    )
    monkeypatch.setattr(
        mcp_app,
        "call_sidecar",
        lambda assertion: graph_token,
    )
    monkeypatch.setattr(
        mcp_app,
        "resolve_fixture",
        lambda token, correlation, name: (200, metadata(name)),
    )
    monkeypatch.setattr(
        mcp_app,
        "resolve_sensitivity_labels",
        lambda token, correlation, drive, item: [
            "Confidential (Personal Data)"
        ],
    )
    monkeypatch.setattr(
        mcp_app,
        "evaluate_label_policy",
        lambda labels: {
            "decision": "deny",
            "reason": "protected_label_denied",
        },
    )
    content_requests: list[str] = []
    monkeypatch.setattr(
        mcp_app,
        "request_bytes",
        lambda url, headers: (
            content_requests.append(url) or 200,
            b"protected-body-must-not-pass",
        ),
    )
    source_id = mcp_app.source_reference("Protected.docx")

    result = mcp_app.policy_source_read(
        user_token,
        source_id=source_id,
        correlation_reference="correlation",
    )

    assert result["status"] == "denied"
    assert result["policy_enforcer"] == "opa"
    assert result["label_resolved"] is True
    assert result["content_request_sent"] is False
    assert "content" not in result
    assert b"protected-body-must-not-pass".decode() not in str(result)
    assert content_requests == []


def test_readable_docx_returns_bounded_text_and_citation(
    monkeypatch,
) -> None:
    configure_gate4(monkeypatch)
    user_token = unsigned_token({"oid": "user-a"})
    graph_token = unsigned_token(
        {
            "oid": "user-a",
            "aud": "https://graph.microsoft.com",
            "azp": "child-agent",
            "scp": (
                "Sites.Selected Files.Read.All "
                "InformationProtectionPolicy.Read"
            ),
        }
    )
    document = Document()
    document.add_paragraph("Readable policy content.")
    payload = io.BytesIO()
    document.save(payload)
    monkeypatch.setattr(
        mcp_app,
        "call_sidecar",
        lambda assertion: graph_token,
    )
    monkeypatch.setattr(
        mcp_app,
        "resolve_fixture",
        lambda token, correlation, name: (200, metadata(name)),
    )
    monkeypatch.setattr(
        mcp_app,
        "resolve_sensitivity_labels",
        lambda token, correlation, drive, item: ["Internal Use Only"],
    )
    monkeypatch.setattr(
        mcp_app,
        "evaluate_label_policy",
        lambda labels: {
            "decision": "allow",
            "reason": "label_allowed",
        },
    )
    monkeypatch.setattr(
        mcp_app,
        "request_bytes",
        lambda url, headers: (200, payload.getvalue()),
    )
    source_id = mcp_app.source_reference("Readable.docx")

    result = mcp_app.policy_source_read(
        user_token,
        source_id=source_id,
        correlation_reference="correlation",
    )

    assert result["status"] == "success"
    assert result["policy_enforcer"] == "opa"
    assert result["label_resolved"] is True
    assert result["content_request_sent"] is True
    assert result["content"]["text"] == "Readable policy content."
    assert result["citation"]["title"] == "Readable.docx"


def test_label_resolution_failure_fails_closed(
    monkeypatch,
) -> None:
    configure_gate4(monkeypatch)
    user_token = unsigned_token({"oid": "user-a"})
    graph_token = unsigned_token(
        {
            "oid": "user-a",
            "aud": "https://graph.microsoft.com",
            "azp": "child-agent",
            "scp": (
                "Sites.Selected Files.Read.All "
                "InformationProtectionPolicy.Read"
            ),
        }
    )
    monkeypatch.setattr(
        mcp_app,
        "call_sidecar",
        lambda assertion: graph_token,
    )
    monkeypatch.setattr(
        mcp_app,
        "resolve_fixture",
        lambda token, correlation, name: (200, metadata(name)),
    )
    monkeypatch.setattr(
        mcp_app,
        "resolve_sensitivity_labels",
        lambda token, correlation, drive, item: (
            (_ for _ in ()).throw(RuntimeError("label-failed"))
        ),
    )
    content_requests: list[str] = []
    monkeypatch.setattr(
        mcp_app,
        "request_bytes",
        lambda url, headers: (
            content_requests.append(url) or 200,
            b"must-not-download",
        ),
    )
    source_id = mcp_app.source_reference("Protected.docx")

    result = mcp_app.policy_source_read(
        user_token,
        source_id=source_id,
        correlation_reference="correlation",
    )

    assert result["status"] == "denied"
    assert result["policy_reason"] == "label-failed"
    assert result["label_resolved"] is False
    assert result["content_request_sent"] is False
    assert content_requests == []


def test_label_extraction_accepts_live_top_level_shape(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LABEL_NAMES_B64",
        base64.b64encode(
            json.dumps(
                {"label-id": "Confidential (Personal Data)"}
            ).encode()
        ).decode(),
    )
    monkeypatch.setattr(
        mcp_app,
        "request_json",
        lambda url, headers, method="GET": (
            (
                200,
                {
                    "labels": [
                        {"sensitivityLabelId": "label-id"}
                    ]
                },
            )
            if method == "POST"
            else (200, {"name": "Confidential (Personal Data)"})
        ),
    )

    labels = mcp_app.resolve_sensitivity_labels(
        "graph-token",
        "correlation",
        "drive-id",
        "item-id",
    )

    assert labels == ["Confidential (Personal Data)"]


def test_successful_empty_label_extraction_is_confirmed_unlabeled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        mcp_app,
        "request_json",
        lambda url, headers, method="GET": (
            200,
            {"value": {"labels": []}},
        ),
    )

    labels = mcp_app.resolve_sensitivity_labels(
        "graph-token",
        "correlation",
        "drive-id",
        "item-id",
    )

    assert labels == []


def test_label_definition_falls_back_to_managed_identity(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LABEL_NAMES_B64",
        base64.b64encode(
            json.dumps({"known-label": "Internal Use Only"}).encode()
        ).decode(),
    )
    calls: list[str] = []
    app_token = unsigned_token(
        {
            "aud": "https://graph.microsoft.com",
            "roles": ["SensitivityLabel.Read"],
        }
    )
    monkeypatch.setattr(
        mcp_app,
        "acquire_managed_identity_graph_token",
        lambda: app_token,
    )

    def request(
        url: str,
        headers: dict[str, str],
        method: str = "GET",
    ):
        calls.append(url)
        if method == "POST":
            return 200, {
                "value": {
                    "labels": [
                        {"sensitivityLabelId": "label-id"}
                    ]
                }
            }
        if "/dataSecurityAndGovernance/" in url:
            return 200, {"name": "Confidential (Personal Data)"}
        return 403, {}

    monkeypatch.setattr(mcp_app, "request_json", request)

    labels = mcp_app.resolve_sensitivity_labels(
        "delegated-graph-token",
        "correlation",
        "drive-id",
        "item-id",
    )

    assert labels == ["Confidential (Personal Data)"]
    assert any(
        "/v1.0/security/dataSecurityAndGovernance/sensitivityLabels/"
        in url
        for url in calls
    )
    assert not any("/beta/me/" in url for url in calls)

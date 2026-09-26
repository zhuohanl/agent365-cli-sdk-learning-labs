from __future__ import annotations

import base64
import hmac
import io
import json
import logging
import os
import secrets
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import jwt
from docx import Document

from src.token_validation import (
    OidcTokenValidator,
    SafeReferenceFactory,
    TokenRejectedError,
    ValidationSettings,
    extract_bearer_token,
    get_header,
)


LOGGER = logging.getLogger("gate2")
logging.basicConfig(level=logging.INFO, format="%(message)s")
REFERENCES = SafeReferenceFactory()
SOURCE_LOCK = threading.Lock()
SOURCE_MAP: dict[str, str] = {}
GRAPH_AUDIENCES = {
    "00000003-0000-0000-c000-000000000000",
    "https://graph.microsoft.com",
}


def required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"missing-{name.lower()}")
    return value


def request_json(
    url: str,
    *,
    headers: dict[str, str],
    method: str = "GET",
) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        url,
        headers=headers,
        data=b"" if method == "POST" else None,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        try:
            payload = json.load(error)
        except (ValueError, json.JSONDecodeError):
            payload = {}
        status = error.code
        error.close()
        return status, payload


def request_bytes(
    url: str,
    *,
    headers: dict[str, str],
) -> tuple[int, bytes]:
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(
            self,
            req: urllib.request.Request,
            fp: object,
            code: int,
            msg: str,
            headers: object,
            newurl: str,
        ) -> None:
            return None

    request = urllib.request.Request(url, headers=headers)
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        if error.code in {301, 302, 303, 307, 308}:
            location = error.headers.get("Location", "")
            error.close()
            if not location:
                return 502, b""
            download = urllib.request.Request(
                location,
                headers={"Accept": "application/octet-stream"},
            )
            try:
                with urllib.request.urlopen(
                    download,
                    timeout=30,
                ) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as download_error:
                payload = download_error.read()
                status = download_error.code
                download_error.close()
                return status, payload
        payload = error.read()
        status = error.code
        error.close()
        return status, payload


def call_sidecar(user_assertion: str) -> str:
    child_id = required("AGENT_CLIENT_ID")
    query = urllib.parse.urlencode({"AgentIdentity": child_id})
    status, payload = request_json(
        f"http://localhost:5000/AuthorizationHeader/graph?{query}",
        headers={
            "Authorization": " ".join(("Bearer", user_assertion)),
            "Accept": "application/json",
        },
    )
    header = payload.get("authorizationHeader")
    if status != 200 or not isinstance(header, str) or not header:
        raise RuntimeError("sidecar-obo-failed")
    scheme, separator, token = header.partition(" ")
    if separator != " " or scheme.casefold() != "bearer" or not token:
        raise RuntimeError("sidecar-header-invalid")
    return token


def acquire_managed_identity_graph_token() -> str:
    endpoint = required("IDENTITY_ENDPOINT")
    identity_header = required("IDENTITY_HEADER")
    separator = "&" if "?" in endpoint else "?"
    status, payload = request_json(
        endpoint
        + separator
        + urllib.parse.urlencode(
            {
                "resource": "https://graph.microsoft.com",
                "api-version": "2019-08-01",
            }
        ),
        headers={
            "X-IDENTITY-HEADER": identity_header,
            "Metadata": "true",
        },
    )
    token = payload.get("access_token")
    if status != 200 or not isinstance(token, str) or not token:
        raise RuntimeError("managed-identity-graph-token-failed")
    claims = jwt.decode(
        token,
        options={
            "verify_signature": False,
            "verify_aud": False,
            "verify_exp": False,
        },
    )
    roles = claims.get("roles")
    if (
        claims.get("aud") not in GRAPH_AUDIENCES
        or not isinstance(roles, list)
        or "SensitivityLabel.Read" not in roles
    ):
        raise RuntimeError("managed-identity-label-role-invalid")
    return token


def configured_label_names() -> dict[str, str]:
    encoded = required("LABEL_NAMES_B64")
    try:
        payload = json.loads(
            base64.b64decode(encoded, validate=True).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("configured-label-map-invalid") from error
    if not isinstance(payload, dict) or not payload:
        raise RuntimeError("configured-label-map-empty")
    result: dict[str, str] = {}
    for label_id, label_name in payload.items():
        if (
            not isinstance(label_id, str)
            or not label_id
            or not isinstance(label_name, str)
            or not label_name.strip()
        ):
            raise RuntimeError("configured-label-map-invalid")
        result[label_id.casefold()] = label_name.strip()
    return result


def fixed_site_metadata(
    user_assertion: str,
    *,
    correlation_reference: str,
) -> dict[str, object]:
    user_claims = jwt.decode(
        user_assertion,
        options={
            "verify_signature": False,
            "verify_aud": False,
            "verify_exp": False,
        },
    )
    graph_token = call_sidecar(user_assertion)
    try:
        graph_claims = jwt.decode(
            graph_token,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_exp": False,
            },
        )
        site_id = required("SITE_ID")
        status, payload = request_json(
            "https://graph.microsoft.com/v1.0/sites/"
            f"{urllib.parse.quote(site_id, safe='')}?%24select=id",
            headers={
                "Authorization": " ".join(("Bearer", graph_token)),
                "Accept": "application/json",
                "client-request-id": correlation_reference,
                "return-client-request-id": "true",
            },
        )
        scopes = graph_claims.get("scp")
        actor = graph_claims.get("azp") or graph_claims.get("appid")
        return {
            "graph_http_status": status,
            "site_matched": status == 200 and payload.get("id") == site_id,
            "graph_audience_valid": (
                graph_claims.get("aud") in GRAPH_AUDIENCES
            ),
            "graph_actor_valid": actor == required("AGENT_CLIENT_ID"),
            "graph_subject_matches": (
                graph_claims.get("oid") == user_claims.get("oid")
            ),
            "sites_selected_scope_valid": (
                isinstance(scopes, str)
                and "Sites.Selected" in scopes.split()
            ),
            "user_reference": REFERENCES.create(
                "user",
                str(user_claims.get("oid") or user_claims.get("sub")),
            ),
            "correlation_reference": correlation_reference,
            "microsoft_token_returned": False,
        }
    finally:
        graph_token = ""


def graph_headers(
    graph_token: str,
    correlation_reference: str,
) -> dict[str, str]:
    return {
        "Authorization": " ".join(("Bearer", graph_token)),
        "Accept": "application/json",
        "client-request-id": correlation_reference,
        "return-client-request-id": "true",
    }


def graph_relationships(
    user_assertion: str,
    graph_token: str,
) -> dict[str, bool]:
    user_claims = jwt.decode(
        user_assertion,
        options={
            "verify_signature": False,
            "verify_aud": False,
            "verify_exp": False,
        },
    )
    graph_claims = jwt.decode(
        graph_token,
        options={
            "verify_signature": False,
            "verify_aud": False,
            "verify_exp": False,
        },
    )
    scopes = graph_claims.get("scp")
    actor = graph_claims.get("azp") or graph_claims.get("appid")
    return {
        "graph_audience_valid": (
            graph_claims.get("aud") in GRAPH_AUDIENCES
        ),
        "graph_actor_valid": actor == required("AGENT_CLIENT_ID"),
        "graph_subject_matches": (
            graph_claims.get("oid") == user_claims.get("oid")
        ),
        "sites_selected_scope_valid": (
            isinstance(scopes, str)
            and "Sites.Selected" in scopes.split()
        ),
        "files_read_all_scope_valid": (
            isinstance(scopes, str)
            and "Files.Read.All" in scopes.split()
        ),
        "information_protection_scope_valid": (
            isinstance(scopes, str)
            and "InformationProtectionPolicy.Read" in scopes.split()
        ),
    }


def configured_files() -> tuple[str, str, str]:
    names = (
        required("READABLE_FILE_NAME"),
        required("SECONDARY_READABLE_FILE_NAME"),
        required("PROTECTED_FILE_NAME"),
    )
    if len(set(names)) != len(names):
        raise RuntimeError("fixture-names-not-distinct")
    return names


def encode_drive_path(*parts: str) -> str:
    segments: list[str] = []
    for part in parts:
        segments.extend(
            segment for segment in part.replace("\\", "/").split("/") if segment
        )
    return "/".join(urllib.parse.quote(segment, safe="") for segment in segments)


def resolve_drive(
    graph_token: str,
    correlation_reference: str,
) -> str:
    site_id = required("SITE_ID")
    library_name = required("DOCUMENT_LIBRARY_NAME")
    status, payload = request_json(
        "https://graph.microsoft.com/v1.0/sites/"
        f"{urllib.parse.quote(site_id, safe='')}/drives"
        "?%24select=id%2Cname",
        headers=graph_headers(graph_token, correlation_reference),
    )
    if status != 200:
        raise RuntimeError("drive-list-failed")
    matches = [
        item
        for item in payload.get("value", [])
        if isinstance(item, dict) and item.get("name") == library_name
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("id"), str):
        raise RuntimeError("configured-drive-not-found")
    return str(matches[0]["id"])


def resolve_fixture(
    graph_token: str,
    correlation_reference: str,
    file_name: str,
) -> tuple[int, dict[str, object]]:
    drive_id = resolve_drive(graph_token, correlation_reference)
    path = encode_drive_path(required("FOLDER_PATH"), file_name)
    return request_json(
        "https://graph.microsoft.com/v1.0/drives/"
        f"{urllib.parse.quote(drive_id, safe='')}/root:/{path}"
        "?%24select=id%2Cname%2CwebUrl%2Cfile%2CparentReference",
        headers=graph_headers(graph_token, correlation_reference),
    )


def source_reference(file_name: str) -> str:
    source_id = REFERENCES.create("source", file_name)
    with SOURCE_LOCK:
        SOURCE_MAP[source_id] = file_name
    return source_id


def policy_sources_list(
    user_assertion: str,
    *,
    correlation_reference: str,
) -> dict[str, object]:
    graph_token = call_sidecar(user_assertion)
    try:
        relationships = graph_relationships(user_assertion, graph_token)
        sources: list[dict[str, object]] = []
        for file_name in configured_files():
            status, item = resolve_fixture(
                graph_token,
                correlation_reference,
                file_name,
            )
            if status != 200:
                raise RuntimeError("fixture-metadata-failed")
            source_id = source_reference(file_name)
            sources.append(
                {
                    "source_id": source_id,
                    "title": item.get("name"),
                    "media_type": (
                        item.get("file", {}).get("mimeType")
                        if isinstance(item.get("file"), dict)
                        else ""
                    ),
                    "url": item.get("webUrl"),
                }
            )
        return {
            "status": "success",
            "sources": sources,
            "microsoft_token_returned": False,
            "correlation_reference": correlation_reference,
            **relationships,
        }
    finally:
        graph_token = ""


def extract_docx_text(payload: bytes) -> str:
    if not payload:
        raise RuntimeError("fixture-content-empty")
    try:
        document = Document(io.BytesIO(payload))
    except Exception as error:
        raise RuntimeError("fixture-content-undecodable") from error
    text = "\n".join(
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    )
    if not text:
        raise RuntimeError("fixture-content-empty")
    return text[:12000]


def resolve_sensitivity_labels(
    graph_token: str,
    correlation_reference: str,
    drive_id: str,
    item_id: str,
) -> list[str]:
    status, payload = request_json(
        "https://graph.microsoft.com/v1.0/drives/"
        f"{urllib.parse.quote(drive_id, safe='')}/items/"
        f"{urllib.parse.quote(item_id, safe='')}/extractSensitivityLabels",
        headers=graph_headers(graph_token, correlation_reference),
        method="POST",
    )
    if status != 200:
        raise RuntimeError("sensitivity-label-extraction-failed")
    assignments = payload.get("labels")
    if not isinstance(assignments, list):
        value = payload.get("value")
        assignments = (
            value.get("labels")
            if isinstance(value, dict)
            else None
        )
    if not isinstance(assignments, list):
        raise RuntimeError("sensitivity-label-unresolved")
    if not assignments:
        return []

    configured_names = configured_label_names()
    labels: list[str] = []
    for assignment in assignments:
        label_id = (
            assignment.get("sensitivityLabelId")
            if isinstance(assignment, dict)
            else None
        )
        if not isinstance(label_id, str) or not label_id:
            raise RuntimeError("sensitivity-label-id-invalid")
        label_name = configured_names.get(label_id.casefold())
        definition_statuses: list[str] = []
        if label_name is None:
            app_token = acquire_managed_identity_graph_token()
            try:
                app_status, app_definition = request_json(
                    "https://graph.microsoft.com/v1.0/security/"
                    "dataSecurityAndGovernance/sensitivityLabels/"
                    f"{urllib.parse.quote(label_id, safe='')}",
                    headers=graph_headers(
                        app_token,
                        correlation_reference,
                    ),
                )
            finally:
                app_token = ""
            definition_statuses.append(f"app_v1:{app_status}")
            app_candidate = app_definition.get(
                "name"
            ) or app_definition.get("displayName")
            if (
                app_status == 200
                and isinstance(app_candidate, str)
                and app_candidate.strip()
            ):
                label_name = app_candidate.strip()
        if label_name is None:
            definition_status, definition = request_json(
                "https://graph.microsoft.com/beta/me/security/"
                "informationProtection/sensitivityLabels/"
                f"{urllib.parse.quote(label_id, safe='')}",
                headers=graph_headers(graph_token, correlation_reference),
            )
            definition_statuses.append(
                f"delegated_beta:{definition_status}"
            )
            candidate = definition.get("name") or definition.get(
                "displayName"
            )
            if (
                definition_status == 200
                and isinstance(candidate, str)
                and candidate.strip()
            ):
                label_name = candidate.strip()
        if label_name is None:
            raise RuntimeError(
                "sensitivity-label-definition-failed-"
                + "-".join(definition_statuses)
            )
        labels.append(label_name)
    return labels


def evaluate_label_policy(labels: list[str]) -> dict[str, str]:
    protected_label = required("PROTECTED_LABEL_NAME")
    policy_path = Path(
        os.environ.get(
            "OPA_POLICY_PATH",
            "/app/gate2/policies/gate4.rego",
        )
    )
    request = {
        "labels": labels,
        "protected_label": protected_label,
    }
    try:
        completed = subprocess.run(
            [
                "opa",
                "eval",
                "--data",
                str(policy_path),
                "--stdin-input",
                "--format",
                "json",
                "data.gate4.decision",
            ],
            input=json.dumps(request),
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError("opa-unavailable") from error
    if completed.returncode != 0:
        raise RuntimeError("opa-evaluation-failed")
    try:
        output = json.loads(completed.stdout)
        decision = output["result"][0]["expressions"][0]["value"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("opa-result-invalid") from error
    if (
        not isinstance(decision, dict)
        or decision.get("decision") not in {"allow", "deny"}
        or not isinstance(decision.get("reason"), str)
    ):
        raise RuntimeError("opa-decision-invalid")
    return {
        "decision": str(decision["decision"]),
        "reason": str(decision["reason"]),
    }


def policy_source_read(
    user_assertion: str,
    *,
    source_id: str,
    correlation_reference: str,
) -> dict[str, object]:
    with SOURCE_LOCK:
        file_name = SOURCE_MAP.get(source_id)
    if not file_name or file_name not in configured_files():
        raise ValueError("source-id-invalid")
    graph_token = call_sidecar(user_assertion)
    try:
        relationships = graph_relationships(user_assertion, graph_token)
        metadata_status, item = resolve_fixture(
            graph_token,
            correlation_reference,
            file_name,
        )
        if metadata_status != 200:
            raise RuntimeError("fixture-metadata-failed")
        parent = item.get("parentReference")
        drive_id = (
            parent.get("driveId")
            if isinstance(parent, dict)
            else None
        )
        item_id = item.get("id")
        if not isinstance(drive_id, str) or not isinstance(item_id, str):
            raise RuntimeError("fixture-identity-missing")
        source = {
            "source_id": source_id,
            "title": item.get("name"),
            "url": item.get("webUrl"),
        }
        fixture_role = {
            required("READABLE_FILE_NAME"): "readable",
            required("SECONDARY_READABLE_FILE_NAME"): "secondary-readable",
            required("PROTECTED_FILE_NAME"): "protected",
        }[file_name]
        try:
            labels = resolve_sensitivity_labels(
                graph_token,
                correlation_reference,
                drive_id,
                item_id,
            )
            decision = evaluate_label_policy(labels)
        except RuntimeError as error:
            return {
                "status": "denied",
                "source": source,
                "message": "The source policy could not be evaluated.",
                "policy_enforcer": "policy-controller",
                "policy_reason": str(error),
                "label_resolved": False,
                "content_request_sent": False,
                "microsoft_token_returned": False,
                "correlation_reference": correlation_reference,
                "_fixture_role": fixture_role,
                **relationships,
            }
        if decision["decision"] == "deny":
            return {
                "status": "denied",
                "source": source,
                "message": "Policy denies this source.",
                "policy_enforcer": "opa",
                "policy_reason": decision["reason"],
                "label_resolved": True,
                "content_request_sent": False,
                "microsoft_token_returned": False,
                "correlation_reference": correlation_reference,
                "_fixture_role": fixture_role,
                **relationships,
            }
        status, payload = request_bytes(
            "https://graph.microsoft.com/v1.0/drives/"
            f"{urllib.parse.quote(drive_id, safe='')}/items/"
            f"{urllib.parse.quote(item_id, safe='')}/content",
            headers=graph_headers(graph_token, correlation_reference),
        )
        if status in {401, 403}:
            return {
                "status": "denied",
                "source": source,
                "message": "Microsoft 365 denied access to this source.",
                "upstream_http_status": status,
                "policy_enforcer": "sharepoint",
                "policy_reason": "upstream_authorization_denied",
                "label_resolved": True,
                "content_request_sent": True,
                "microsoft_token_returned": False,
                "correlation_reference": correlation_reference,
                "_fixture_role": fixture_role,
                **relationships,
            }
        if status != 200:
            raise RuntimeError("fixture-download-failed")
        return {
            "status": "success",
            "source": source,
            "content": {
                "format": "text/plain",
                "text": extract_docx_text(payload),
            },
            "citation": {
                "title": item.get("name"),
                "url": item.get("webUrl"),
            },
            "upstream_http_status": status,
            "policy_enforcer": "opa",
            "policy_reason": decision["reason"],
            "label_resolved": True,
            "content_request_sent": True,
            "microsoft_token_returned": False,
            "correlation_reference": correlation_reference,
            "_fixture_role": fixture_role,
            **relationships,
        }
    finally:
        graph_token = ""


def call_tool(
    name: str,
    arguments: dict[str, object],
    user_assertion: str,
    correlation_reference: str,
) -> dict[str, object]:
    if name == "sharepoint.fixed_site_metadata" and not arguments:
        return fixed_site_metadata(
            user_assertion,
            correlation_reference=correlation_reference,
        )
    if name == "policy_sources_list" and not arguments:
        return policy_sources_list(
            user_assertion,
            correlation_reference=correlation_reference,
        )
    if name == "policy_source_read":
        source_id = arguments.get("source_id")
        if isinstance(source_id, str) and len(arguments) == 1:
            return policy_source_read(
                user_assertion,
                source_id=source_id,
                correlation_reference=correlation_reference,
            )
    raise ValueError("unsupported-operation")


class McpHandler(BaseHTTPRequestHandler):
    validator: OidcTokenValidator
    endpoint_key: str

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, status: int, value: dict[str, object]) -> None:
        response = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_json(404, {"error": "not-found"})
            return
        self.send_json(200, {"status": "Healthy"})

    def do_POST(self) -> None:
        if self.path != "/mcp":
            self.send_json(404, {"error": "not-found"})
            return
        try:
            supplied_key = get_header(self.headers, "x-mcp-key")
            if not hmac.compare_digest(supplied_key, self.endpoint_key):
                self.send_json(403, {"error": "transport-rejected"})
                return
            user_assertion = extract_bearer_token(self.headers)
            self.validator.validate(user_assertion)
            length = int(get_header(self.headers, "Content-Length"))
            request = json.loads(self.rfile.read(length))
            params = request.get("params", {})
            if (
                request.get("jsonrpc") != "2.0"
                or request.get("method") != "tools/call"
                or not isinstance(params, dict)
                or not isinstance(params.get("name"), str)
                or not isinstance(params.get("arguments", {}), dict)
            ):
                raise ValueError("unsupported-operation")
            correlation = get_header(
                self.headers, "x-correlation-reference"
            ) or secrets.token_hex(8)
            result = call_tool(
                params["name"],
                params.get("arguments", {}),
                user_assertion,
                correlation,
            )
            LOGGER.info("gate2_graph_request_complete")
            self.send_json(
                200,
                {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    result,
                                    separators=(",", ":"),
                                ),
                            }
                        ],
                        "structuredContent": result,
                        "isError": False,
                    },
                },
            )
        except TokenRejectedError:
            LOGGER.info("gate2_user_assertion_rejected")
            self.send_json(401, {"error": "invalid-user-assertion"})
        except (ValueError, json.JSONDecodeError):
            LOGGER.info("gate2_request_rejected")
            self.send_json(400, {"error": "invalid-request"})
        except RuntimeError:
            LOGGER.info("gate2_downstream_failed")
            self.send_json(502, {"error": "downstream-failed"})


def run() -> None:
    McpHandler.validator = OidcTokenValidator(
        ValidationSettings.from_environment()
    )
    McpHandler.endpoint_key = required("MCP_ENDPOINT_KEY")
    server = ThreadingHTTPServer(("0.0.0.0", 8080), McpHandler)
    LOGGER.info("gate2_mcp_started")
    server.serve_forever()


if __name__ == "__main__":
    run()

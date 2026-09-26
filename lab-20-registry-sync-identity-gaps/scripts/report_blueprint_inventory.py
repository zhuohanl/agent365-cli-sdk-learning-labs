"""Report package-linked Agent Identities grouped by platform and Blueprint."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from typing import Any, Callable, Iterable
from urllib.parse import quote


GRAPH_BASE_URL = "https://graph.microsoft.com"
LAB = Path(__file__).resolve().parents[1]
DEFAULT_ENV = LAB / ".env"
DEFAULT_ENRICHED_OUTPUT = (
    LAB / "evidence" / "blueprint-inventory" / "enriched-packages.json"
)
DEFAULT_TABLE_OUTPUT = (
    LAB / "evidence" / "blueprint-inventory" / "blueprint-summary.md"
)
SCOPES = [
    f"{GRAPH_BASE_URL}/CopilotPackages.Read.All",
    f"{GRAPH_BASE_URL}/AgentIdentity.Read.All",
    f"{GRAPH_BASE_URL}/AgentIdentityBlueprintPrincipal.Read.All",
]


class ReportError(RuntimeError):
    """Raised when the report cannot be completed safely."""


class GraphRequestError(ReportError):
    """Raised when Microsoft Graph returns an unsuccessful response."""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        request_id: str | None,
    ) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.graph_message = message
        self.request_id = request_id
        suffix = f" Request ID: {request_id}." if request_id else ""
        super().__init__(
            f"Graph request failed: {error_code}: {message}.{suffix}"
        )


@dataclass(frozen=True)
class PackageIdentity:
    platform: str
    identity_id: str


@dataclass(frozen=True)
class Blueprint:
    principal_id: str | None
    app_id: str
    display_name: str | None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "id": self.principal_id,
            "appId": self.app_id,
            "displayName": self.display_name,
        }


@dataclass(frozen=True)
class ReportRow:
    platform: str
    blueprint_name: str
    blueprint_id: str
    identity_count: int


class GraphClient:
    def __init__(self, access_token: str, session: Any) -> None:
        self._session = session
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    def get(self, url: str) -> dict[str, Any]:
        for attempt in range(5):
            response = self._session.get(url, headers=self._headers, timeout=60)
            if response.status_code not in {429, 500, 502, 503, 504}:
                break
            if attempt == 4:
                break
            retry_after = response.headers.get("Retry-After", "2")
            try:
                delay = max(1, min(int(retry_after), 30))
            except ValueError:
                delay = 2
            time.sleep(delay)

        if not response.ok:
            try:
                error = response.json().get("error", {})
            except ValueError:
                error = {}
            code = error.get("code")
            if not isinstance(code, str) or not code:
                code = f"HTTP {response.status_code}"
            message = error.get("message")
            if not isinstance(message, str) or not message:
                message = response.reason
            request_id = response.headers.get("request-id")
            raise GraphRequestError(
                response.status_code, code, message, request_id
            )

        try:
            payload = response.json()
        except ValueError as error:
            raise ReportError("Graph returned a non-JSON response") from error
        if not isinstance(payload, dict):
            raise ReportError("Graph returned an unexpected response shape")
        return payload


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def require_setting(env: dict[str, str], name: str) -> str:
    value = os.environ.get(name) or env.get(name)
    if not value or value.startswith("<"):
        raise ReportError(f"Set {name} in the environment or {DEFAULT_ENV}")
    return value


def acquire_access_token(tenant_id: str, client_id: str) -> str:
    try:
        import msal
    except ImportError as error:
        raise ReportError(
            "msal is not installed. Run this script through the notebook-pilot "
            "environment as documented in docs/INSTRUCTION.md."
        ) from error

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    application = msal.PublicClientApplication(client_id, authority=authority)
    flow = application.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        description = flow.get("error_description", "device-code flow failed")
        raise ReportError(f"Could not start device-code authentication: {description}")

    print(flow["message"], file=sys.stderr)
    token = application.acquire_token_by_device_flow(flow)
    access_token = token.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        code = token.get("error", "authentication_failed")
        description = token.get("error_description", "No access token returned")
        raise ReportError(f"Authentication failed: {code}: {description}")
    return access_token


def paged_values(
    first_url: str, get: Callable[[str], dict[str, Any]]
) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    url: str | None = first_url
    seen_urls: set[str] = set()

    while url:
        if url in seen_urls:
            raise ReportError("Graph pagination returned a repeated nextLink")
        seen_urls.add(url)
        payload = get(url)
        page = payload.get("value")
        if not isinstance(page, list):
            raise ReportError("A paged Graph response did not contain a value array")
        values.extend(item for item in page if isinstance(item, dict))
        next_link = payload.get("@odata.nextLink")
        if next_link is not None and not isinstance(next_link, str):
            raise ReportError("Graph returned an invalid @odata.nextLink")
        url = next_link

    return values


def package_with_identity(
    package: dict[str, Any], get: Callable[[str], dict[str, Any]]
) -> tuple[dict[str, Any], PackageIdentity | None]:
    enriched_source = dict(package)
    platform_value = enriched_source.get("platform")
    platform = (
        platform_value
        if isinstance(platform_value, str) and platform_value
        else "<missing>"
    )

    identity_value = enriched_source.get("agentIdentityId")
    if "agentIdentityId" not in enriched_source:
        package_id = enriched_source.get("id")
        if not isinstance(package_id, str) or not package_id:
            raise ReportError("A Package without agentIdentityId also has no id")
        encoded_id = quote(package_id, safe="")
        details = get(
            f"{GRAPH_BASE_URL}/v1.0/copilot/admin/catalog/packages/{encoded_id}"
        )
        enriched_source.update(details)
        detail_platform = details.get("platform")
        if isinstance(detail_platform, str) and detail_platform:
            platform = detail_platform
        identity_value = details.get("agentIdentityId")

    if identity_value is None or identity_value == "":
        return enriched_source, None
    if not isinstance(identity_value, str):
        raise ReportError("A Package returned a non-string agentIdentityId")
    return (
        enriched_source,
        PackageIdentity(platform=platform, identity_id=identity_value),
    )


def read_agent_identity(
    identity_id: str, get: Callable[[str], dict[str, Any]]
) -> tuple[dict[str, Any], str]:
    encoded_id = quote(identity_id, safe="")
    select = (
        "?$select=id,appId,displayName,servicePrincipalType,accountEnabled,"
        "agentIdentityBlueprintId"
    )
    try:
        identity = get(
            f"{GRAPH_BASE_URL}/v1.0/servicePrincipals/{encoded_id}"
            f"/microsoft.graph.agentIdentity{select}"
        )
        if identity.get("id") != identity_id:
            raise ReportError(
                f"Agent Identity {identity_id} returned a different object id"
            )
        lookup_key = "objectId"
    except GraphRequestError as object_id_error:
        if not is_resource_not_found(object_id_error):
            raise
        escaped_app_id = identity_id.replace("'", "''")
        try:
            identity = get(
                f"{GRAPH_BASE_URL}/v1.0/servicePrincipals"
                f"(appId='{escaped_app_id}')"
                f"/microsoft.graph.agentIdentity{select}"
            )
        except GraphRequestError as app_id_error:
            if is_resource_not_found(app_id_error):
                raise object_id_error
            raise
        if identity.get("appId") != identity_id:
            raise ReportError(
                f"Agent Identity lookup for appId {identity_id} returned "
                "a different appId"
            )
        lookup_key = "appId"

    blueprint_id = identity.get("agentIdentityBlueprintId")
    if not isinstance(blueprint_id, str) or not blueprint_id:
        raise ReportError(
            f"Agent Identity {identity_id} has no agentIdentityBlueprintId"
        )
    return identity, lookup_key


def read_blueprint(
    blueprint_app_id: str, get: Callable[[str], dict[str, Any]]
) -> Blueprint:
    escaped_app_id = blueprint_app_id.replace("'", "''")
    principal = get(
        f"{GRAPH_BASE_URL}/v1.0/servicePrincipals"
        f"(appId='{escaped_app_id}')"
        "/microsoft.graph.agentIdentityBlueprintPrincipal"
        "?$select=id,appId,displayName"
    )
    returned_app_id = principal.get("appId")
    if returned_app_id != blueprint_app_id:
        raise ReportError(
            f"Blueprint principal for {blueprint_app_id} returned a different appId"
        )
    display_name = principal.get("displayName")
    if display_name is not None and not isinstance(display_name, str):
        raise ReportError(
            f"Blueprint principal for {blueprint_app_id} has an invalid displayName"
        )
    principal_id = principal.get("id")
    if not isinstance(principal_id, str) or not principal_id:
        raise ReportError(f"Blueprint principal for {blueprint_app_id} has no id")
    return Blueprint(
        principal_id=principal_id,
        app_id=blueprint_app_id,
        display_name=display_name or None,
    )


def is_resource_not_found(error: GraphRequestError) -> bool:
    return (
        error.status_code == 404
        and error.error_code == "Request_ResourceNotFound"
    )


def not_found_resolution(resource: str) -> dict[str, str]:
    return {
        "status": "notFound",
        "errorCode": "Request_ResourceNotFound",
        "message": (
            f"The Package references {resource} that Graph could not resolve."
        ),
    }


def build_report(
    packages: Iterable[dict[str, Any]],
    get: Callable[[str], dict[str, Any]],
) -> tuple[list[ReportRow], list[dict[str, Any]], int, int, int]:
    resolved_packages: list[tuple[dict[str, Any], PackageIdentity | None]] = []
    packages_without_identity = 0

    for package in packages:
        resolved_package, association = package_with_identity(package, get)
        resolved_packages.append((resolved_package, association))
        if association is None:
            packages_without_identity += 1

    identities: dict[str, tuple[dict[str, Any], str]] = {}
    blueprints: dict[str, Blueprint] = {}
    grouped_identity_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
    enriched_packages: list[dict[str, Any]] = []
    resolution_failures = 0

    for package, association in resolved_packages:
        enriched = dict(package)
        if association is None:
            enriched["resolvedAgentIdentity"] = None
            enriched["resolvedBlueprint"] = None
            enriched["identityResolution"] = {"status": "notPresent"}
            enriched["blueprintResolution"] = {"status": "notApplicable"}
            enriched_packages.append(enriched)
            continue

        identity_result = identities.get(association.identity_id)
        if identity_result is None:
            try:
                identity_result = read_agent_identity(
                    association.identity_id, get
                )
            except GraphRequestError as error:
                if not is_resource_not_found(error):
                    raise
                enriched["resolvedAgentIdentity"] = None
                enriched["resolvedBlueprint"] = None
                enriched["identityResolution"] = not_found_resolution(
                    "an Agent Identity"
                )
                enriched["blueprintResolution"] = {"status": "notApplicable"}
                enriched_packages.append(enriched)
                resolution_failures += 1
                continue
            identities[association.identity_id] = identity_result
        identity, identity_lookup_key = identity_result
        blueprint_app_id = identity["agentIdentityBlueprintId"]
        if blueprint_app_id not in blueprints:
            try:
                blueprints[blueprint_app_id] = read_blueprint(
                    blueprint_app_id, get
                )
            except GraphRequestError as error:
                if not is_resource_not_found(error):
                    raise
                blueprints[blueprint_app_id] = Blueprint(
                    principal_id=None,
                    app_id=blueprint_app_id,
                    display_name=None,
                )
        enriched["resolvedAgentIdentity"] = identity
        enriched["resolvedBlueprint"] = blueprints[blueprint_app_id].as_dict()
        enriched["identityResolution"] = {
            "status": "resolved",
            "lookupKey": identity_lookup_key,
        }
        if blueprints[blueprint_app_id].principal_id is None:
            enriched["blueprintResolution"] = not_found_resolution(
                "a Blueprint principal"
            )
            resolution_failures += 1
        else:
            enriched["blueprintResolution"] = {"status": "resolved"}
        enriched_packages.append(enriched)
        grouped_identity_ids[
            (association.platform, blueprint_app_id)
        ].add(association.identity_id)

    rows = [
        ReportRow(
            platform=platform,
            blueprint_name=(
                blueprints[blueprint_app_id].display_name or "<not available>"
            ),
            blueprint_id=blueprint_app_id,
            identity_count=len(identity_ids),
        )
        for (platform, blueprint_app_id), identity_ids in grouped_identity_ids.items()
    ]
    rows.sort(
        key=lambda row: (
            row.platform.casefold(),
            row.blueprint_name.casefold(),
            row.blueprint_id,
        )
    )
    return (
        rows,
        enriched_packages,
        len(identities),
        packages_without_identity,
        resolution_failures,
    )


def write_enriched_packages(
    path: Path, packages: list[dict[str, Any]], package_list_url: str
) -> None:
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": package_list_url,
        "count": len(packages),
        "value": packages,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f"{path.name}.", suffix=".tmp", text=True
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as temporary:
            json.dump(payload, temporary, ensure_ascii=True, indent=2)
            temporary.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def markdown_table(rows: Iterable[ReportRow]) -> str:
    lines = [
        "| Microsoft platform | Blueprint name | Blueprint ID | Number of agent identities under this Blueprint |",
        "| --- | --- | --- | ---: |",
    ]
    for row in rows:
        platform = row.platform.replace("|", r"\|")
        blueprint_name = row.blueprint_name.replace("|", r"\|")
        blueprint_id = row.blueprint_id.replace("|", r"\|")
        lines.append(
            f"| {platform} | {blueprint_name} | {blueprint_id} | "
            f"{row.identity_count} |"
        )
    if len(lines) == 2:
        lines.append(
            "| _No package-linked Agent Identities found_ | - | - | 0 |"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "List all Agent 365 Packages, resolve their Agent Identities to "
            "Blueprints, and print a Markdown summary."
        )
    )
    parser.add_argument(
        "--env",
        type=Path,
        default=DEFAULT_ENV,
        help=f"Path to the ignored environment file (default: {DEFAULT_ENV})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_TABLE_OUTPUT,
        help=(
            "Write the Markdown table to this local file "
            f"(default: {DEFAULT_TABLE_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--enriched-output",
        type=Path,
        default=DEFAULT_ENRICHED_OUTPUT,
        help=(
            "Write the enriched Package list to this local JSON file "
            f"(default: {DEFAULT_ENRICHED_OUTPUT})"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = read_env(args.env)
    tenant_id = require_setting(env, "A365_TENANT_ID")
    client_id = require_setting(env, "A365_CLIENT_ID")
    access_token = acquire_access_token(tenant_id, client_id)

    try:
        import requests
    except ImportError as error:
        raise ReportError(
            "requests is not installed. Run this script through the "
            "notebook-pilot environment as documented in docs/INSTRUCTION.md."
        ) from error

    client = GraphClient(access_token, requests.Session())
    package_list_url = f"{GRAPH_BASE_URL}/v1.0/copilot/admin/catalog/packages"
    packages = paged_values(package_list_url, client.get)
    (
        rows,
        enriched_packages,
        unique_identity_count,
        packages_without_identity,
        resolution_failures,
    ) = build_report(
        packages, client.get
    )
    write_enriched_packages(
        args.enriched_output, enriched_packages, package_list_url
    )
    table = markdown_table(rows)
    print(table)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(table + "\n", encoding="utf-8")
    print(
        f"\nPackages read: {len(packages)}; "
        f"unique package-linked Agent Identities: {unique_identity_count}; "
        f"Packages without an Agent Identity: {packages_without_identity}; "
        f"resolution failures: {resolution_failures}.",
        file=sys.stderr,
    )
    print(f"Wrote {args.enriched_output}", file=sys.stderr)
    print(f"Wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReportError as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error

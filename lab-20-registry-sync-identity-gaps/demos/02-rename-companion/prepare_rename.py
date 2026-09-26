"""Build the ignored rename mapping from verified Demo 2 evidence."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


LAB = Path(__file__).resolve().parents[2]
ADD_EVIDENCE = LAB / "evidence" / "demos" / "01-add-companion"
RENAME_EVIDENCE = LAB / "evidence" / "demos" / "02-rename-companion"
DEFAULT_MAPPING = ADD_EVIDENCE / "mapping.json"
DEFAULT_OUTPUT = RENAME_EVIDENCE / "mapping-after-rename.json"
PLATFORM = "GoogleVertexAI"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def provider_definition(package: dict[str, Any]) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for detail in package.get("elementDetails") or []:
        if not isinstance(detail, dict):
            continue
        for element in detail.get("elements") or []:
            if not isinstance(element, dict):
                continue
            raw = element.get("definition")
            if not isinstance(raw, str):
                continue
            definition = json.loads(raw)
            source_ids = definition.get("SourceIds")
            if (
                isinstance(source_ids, dict)
                and source_ids.get("mac.agentRegistrationProviderType")
                == PLATFORM
            ):
                matches.append(definition)
    if len(matches) != 1:
        raise ValueError(
            f"Expected one {PLATFORM} provider definition; found {len(matches)}"
        )
    return matches[0]


def newest_existing(preferred: Path, fallback: Path) -> Path:
    return preferred if preferred.exists() else fallback


def expected_names(package_name: str) -> dict[str, str]:
    return {
        "blueprintDisplayName": (
            f"{package_name} - dedicated disposable Blueprint"
        ),
        "blueprintPrincipalDisplayName": (
            f"{package_name} - dedicated disposable Blueprint"
        ),
        "agentIdentityDisplayName": (
            f"{package_name} - managed Agent Identity"
        ),
        "companionRegistrationDisplayName": (
            f"{package_name} - managed companion"
        ),
        "companionPackageDisplayName": (
            f"{package_name} - managed companion"
        ),
    }


def mapping_values(
    base: dict[str, Any],
    provider_package: dict[str, Any],
    blueprint: dict[str, Any],
    principal: dict[str, Any],
    identity: dict[str, Any],
    registration: dict[str, Any],
    companion_package: dict[str, Any],
) -> dict[str, Any]:
    provider = provider_definition(provider_package)
    provider_source = provider.get("SourceAgentId")
    package_name = provider_package.get("displayName")
    if (
        provider_package.get("platform") != base.get("platform")
        or provider_source != base.get("providerSourceAgentId")
    ):
        raise ValueError("Provider Package no longer matches the mapped source")
    if not isinstance(package_name, str) or not package_name:
        raise ValueError("Provider Package has no displayName")
    if blueprint.get("id") != base.get("blueprintObjectId"):
        raise ValueError("Blueprint object ID changed")
    if blueprint.get("appId") != base.get("blueprintId"):
        raise ValueError("Blueprint app ID changed")
    if (
        principal.get("id") != base.get("blueprintPrincipalId")
        or principal.get("appId") != base.get("blueprintId")
    ):
        raise ValueError("Blueprint principal relationship changed")
    if (
        identity.get("id") != base.get("agentIdentityId")
        or identity.get("agentIdentityBlueprintId") != base.get("blueprintId")
    ):
        raise ValueError("Agent Identity relationship changed")
    if (
        registration.get("id") != base.get("companionRegistrationId")
        or registration.get("sourceAgentId")
        != base.get("companionSourceAgentId")
        or registration.get("agentIdentityId") != base.get("agentIdentityId")
        or registration.get("agentIdentityBlueprintId") != base.get("blueprintId")
    ):
        raise ValueError("Companion Registration relationship changed")
    if (
        companion_package.get("id") != base.get("companionPackageId")
        or companion_package.get("agentIdentityId") != base.get("agentIdentityId")
    ):
        raise ValueError("Companion Package relationship changed")

    names = {
        "packageDisplayName": package_name,
        "blueprintDisplayName": blueprint.get("displayName"),
        "blueprintPrincipalDisplayName": principal.get("displayName"),
        "agentIdentityDisplayName": identity.get("displayName"),
        "companionRegistrationDisplayName": registration.get("displayName"),
        "companionPackageDisplayName": companion_package.get("displayName"),
    }
    missing = [
        key for key, value in names.items()
        if not isinstance(value, str) or not value
    ]
    if missing:
        raise ValueError("Evidence is missing display names: " + ", ".join(missing))

    expected = expected_names(package_name)
    compared = {
        key: names[key] == value
        for key, value in expected.items()
    }
    if base.get("assignmentMode") == "shared":
        compared.pop("blueprintDisplayName")
        compared.pop("blueprintPrincipalDisplayName")

    result = deepcopy(base)
    result.pop("targetName", None)
    result.update(names)
    result["packageId"] = provider_package.get("id")
    result["sourceLastModifiedDateTime"] = provider.get(
        "LastModifiedDateTime"
    )
    result["lastObservedAt"] = datetime.now(timezone.utc).isoformat()
    matched_count = sum(compared.values())
    if matched_count == len(compared):
        result["nameSyncStatus"] = "in-sync"
    elif matched_count:
        result["nameSyncStatus"] = "partial"
    else:
        result["nameSyncStatus"] = "pending"
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    result.add_argument(
        "--provider-package",
        type=Path,
        default=RENAME_EVIDENCE / "provider-package-after-rename.json",
    )
    result.add_argument(
        "--blueprint",
        type=Path,
        default=newest_existing(
            RENAME_EVIDENCE / "blueprint-after-name-sync.json",
            RENAME_EVIDENCE / "blueprint-before-rename.json",
        ),
    )
    result.add_argument(
        "--principal",
        type=Path,
        default=newest_existing(
            RENAME_EVIDENCE / "blueprint-principal-after-name-sync.json",
            RENAME_EVIDENCE / "blueprint-principal-before-rename.json",
        ),
    )
    result.add_argument(
        "--identity",
        type=Path,
        default=newest_existing(
            RENAME_EVIDENCE / "agent-identity-after-name-sync.json",
            RENAME_EVIDENCE / "agent-identity-before-rename.json",
        ),
    )
    result.add_argument(
        "--registration",
        type=Path,
        default=newest_existing(
            RENAME_EVIDENCE / "companion-registration-after-name-sync.json",
            RENAME_EVIDENCE / "companion-registration-before-rename.json",
        ),
    )
    result.add_argument(
        "--companion-package",
        type=Path,
        default=newest_existing(
            RENAME_EVIDENCE / "companion-package-after-name-sync.json",
            ADD_EVIDENCE / "companion-package-after-create.json",
        ),
    )
    result.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    result.add_argument(
        "--blocked",
        action="store_true",
        help="Record that a required name update cannot safely run.",
    )
    return result


def main() -> None:
    args = parser().parse_args()
    try:
        mapping = mapping_values(
            load_json(args.mapping),
            load_json(args.provider_package),
            load_json(args.blueprint),
            load_json(args.principal),
            load_json(args.identity),
            load_json(args.registration),
            load_json(args.companion_package),
        )
        if args.blocked:
            mapping["nameSyncStatus"] = "blocked"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(mapping, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"Saved {args.output} with nameSyncStatus="
            f"{mapping['nameSyncStatus']}"
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"Preparation failed: {error}") from error


if __name__ == "__main__":
    main()

"""Prototype local-only lifecycle transitions for the Demo 3 mapping."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any


SOURCE_OBJECTS = (
    "providerSource",
    "registrySyncPackage",
    "companionRegistration",
    "companionPackage",
    "agentIdentity",
)
MANAGED_SOURCE_OBJECTS = (
    "companionRegistration",
    "companionPackage",
    "agentIdentity",
)
BLUEPRINT_OBJECTS = ("blueprint", "blueprintPrincipal")
OBJECT_STATUSES = {"active", "pending", "retired", "blocked"}


def timestamp(value: str | None = None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    return validated_timestamp(value, "--at")


def parsed_timestamp(value: str, field: str) -> datetime:
    if not value or "<" in value or ">" in value:
        raise ValueError(f"{field} must be a real ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(
            f"{field} must be a real ISO 8601 timestamp"
        ) from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def validated_timestamp(value: str, field: str) -> str:
    parsed_timestamp(value, field)
    return value


def object_state(status: str, reason: str, at: str) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "lastCheckedAt": at,
        "statusChangedAt": at,
        "retiredAt": at if status == "retired" else None,
    }


def set_object_state(
    state: dict[str, Any],
    status: str,
    reason: str,
    at: str,
) -> None:
    if status not in OBJECT_STATUSES:
        raise ValueError(f"Unsupported object status: {status}")
    if state.get("status") != status:
        state["statusChangedAt"] = at
    state["status"] = status
    state["reason"] = reason
    state["lastCheckedAt"] = at
    if status == "retired" and not state.get("retiredAt"):
        state["retiredAt"] = at
    elif status != "retired":
        state["retiredAt"] = None


def initialize(mapping: dict[str, Any], at: str) -> dict[str, Any]:
    if "retirement" in mapping or "blueprintCleanup" in mapping:
        raise ValueError("Mapping already contains retirement prototype state")
    result = deepcopy(mapping)
    result.pop("status", None)
    result["lifecycleStatus"] = "active"
    result["lifecycleReason"] = "source-active"
    result["retirement"] = {
        "missingSince": None,
        "sourceRetirementApprovedAt": None,
        "companionRegistrationRetirementApprovedAt": None,
        "agentIdentityRetirementApprovedAt": None,
        "gracePeriodEndsAt": None,
        "providerSource": object_state(
            "active", "observed-via-registry-sync", at
        ),
        "registrySyncPackage": object_state(
            "active", "observed-in-inventory", at
        ),
        "companionRegistration": object_state(
            "active", "verified-present", at
        ),
        "companionPackage": object_state("active", "verified-present", at),
        "agentIdentity": object_state("active", "verified-present", at),
    }
    cleanup_reason = (
        "source-active"
        if result.get("assignmentMode") == "dedicated"
        else "shared-group-not-empty"
    )
    result["blueprintCleanup"] = {
        "status": "active",
        "reason": cleanup_reason,
        "blueprint": object_state("active", "verified-present", at),
        "blueprintPrincipal": object_state("active", "verified-present", at),
    }
    return result


def require_state(
    mapping: dict[str, Any],
    object_name: str,
    allowed: set[str],
) -> dict[str, Any]:
    retirement = mapping.get("retirement")
    if not isinstance(retirement, dict):
        raise ValueError("Initialize the mapping before applying events")
    state = retirement.get(object_name)
    if not isinstance(state, dict):
        raise ValueError(f"Missing retirement state for {object_name}")
    if state.get("status") not in allowed:
        expected = ", ".join(sorted(allowed))
        raise ValueError(
            f"{object_name} must be {expected}; found {state.get('status')}"
        )
    return state


def require_blueprint_state(
    mapping: dict[str, Any],
    object_name: str,
    allowed: set[str] | None = None,
) -> dict[str, Any]:
    cleanup = mapping.get("blueprintCleanup")
    if not isinstance(cleanup, dict):
        raise ValueError("Initialize the mapping before applying events")
    state = cleanup.get(object_name)
    if not isinstance(state, dict):
        raise ValueError(f"Missing Blueprint cleanup state for {object_name}")
    if allowed is not None and state.get("status") not in allowed:
        expected = ", ".join(sorted(allowed))
        raise ValueError(
            f"{object_name} must be {expected}; found {state.get('status')}"
        )
    return state


def recalculate(mapping: dict[str, Any]) -> None:
    retirement = mapping["retirement"]
    source_states = [retirement[name]["status"] for name in SOURCE_OBJECTS]
    managed_states = [
        retirement[name]["status"] for name in MANAGED_SOURCE_OBJECTS
    ]
    if "blocked" in source_states:
        mapping["lifecycleStatus"] = "blocked"
        mapping["lifecycleReason"] = "required-step-blocked"
    elif all(status == "retired" for status in source_states):
        mapping["lifecycleStatus"] = "retired"
        mapping["lifecycleReason"] = "source-retired"
    elif any(status == "retired" for status in managed_states):
        mapping["lifecycleStatus"] = "partial"
        mapping["lifecycleReason"] = "companion-retirement-in-progress"
    elif any(status != "active" for status in source_states):
        mapping["lifecycleStatus"] = "pending"
        mapping.setdefault("lifecycleReason", "reconciliation-pending")
    else:
        mapping["lifecycleStatus"] = "active"
        mapping["lifecycleReason"] = "source-active"

    cleanup = mapping["blueprintCleanup"]
    cleanup_states = [cleanup[name]["status"] for name in BLUEPRINT_OBJECTS]
    if "blocked" in cleanup_states:
        cleanup["status"] = "blocked"
    elif all(status == "retired" for status in cleanup_states):
        cleanup["status"] = "retired"
    elif any(status == "retired" for status in cleanup_states):
        cleanup["status"] = "partial"
    elif any(status == "pending" for status in cleanup_states):
        cleanup["status"] = "pending"
    else:
        cleanup["status"] = "active"

    if cleanup["status"] == "active":
        if mapping.get("assignmentMode") == "shared":
            cleanup["reason"] = "shared-group-not-empty"
        elif mapping["lifecycleStatus"] == "active":
            cleanup["reason"] = "source-active"
        elif mapping["lifecycleStatus"] == "retired":
            cleanup["reason"] = "source-retired-awaiting-cleanup"
        else:
            cleanup["reason"] = "source-retirement-incomplete"


def apply_event(
    mapping: dict[str, Any],
    event: str,
    at: str,
    *,
    reason: str | None = None,
    package_id: str | None = None,
    grace_period_ends_at: str | None = None,
    object_name: str | None = None,
    simulation_grace_minutes: int | None = None,
    production_candidate_grace_period: str | None = None,
) -> dict[str, Any]:
    result = deepcopy(mapping)
    retirement = result.get("retirement")
    if not isinstance(retirement, dict):
        raise ValueError("Initialize the mapping before applying events")
    event_time = parsed_timestamp(at, "event timestamp")
    if "sourceDeletionConfirmedAt" in retirement:
        retirement.setdefault(
            "sourceRetirementApprovedAt",
            retirement.pop("sourceDeletionConfirmedAt"),
        )
    retirement.setdefault("companionRegistrationRetirementApprovedAt", None)
    retirement.setdefault("agentIdentityRetirementApprovedAt", None)

    if event == "source-missing":
        require_state(result, "providerSource", {"active", "pending"})
        require_state(result, "registrySyncPackage", {"active", "pending"})
        retirement["missingSince"] = retirement.get("missingSince") or at
        if grace_period_ends_at is not None:
            retirement["gracePeriodEndsAt"] = validated_timestamp(
                grace_period_ends_at,
                "--grace-period-ends-at",
            )
        lifecycle_reason = reason
        if lifecycle_reason is None:
            deadline = retirement.get("gracePeriodEndsAt")
            if isinstance(deadline, str):
                lifecycle_reason = (
                    "awaiting-source-retirement-approval"
                    if event_time
                    >= parsed_timestamp(deadline, "gracePeriodEndsAt")
                    else "awaiting-grace-period"
                )
            else:
                lifecycle_reason = "awaiting-healthy-sync"
        result["lifecycleReason"] = lifecycle_reason
        set_object_state(
            retirement["providerSource"],
            "pending",
            "provider-presence-unconfirmed",
            at,
        )
        set_object_state(
            retirement["registrySyncPackage"],
            "pending",
            "not-observed-in-complete-inventory",
            at,
        )
    elif event == "configure-simulation-grace":
        require_state(result, "providerSource", {"pending"})
        require_state(result, "registrySyncPackage", {"pending"})
        if (
            simulation_grace_minutes is None
            or simulation_grace_minutes <= 0
        ):
            raise ValueError(
                "configure-simulation-grace requires a positive "
                "--simulation-grace-minutes"
            )
        if not production_candidate_grace_period:
            raise ValueError(
                "configure-simulation-grace requires "
                "--production-candidate-grace-period"
            )
        missing_since = retirement.get("missingSince")
        if not isinstance(missing_since, str):
            raise ValueError(
                "configure-simulation-grace requires missingSince"
            )
        deadline = parsed_timestamp(
            missing_since,
            "missingSince",
        ) + timedelta(minutes=simulation_grace_minutes)
        retirement["gracePeriodEndsAt"] = deadline.isoformat()
        result["retirementPolicy"] = {
            "mode": "experiment-simulation",
            "gracePeriod": f"PT{simulation_grace_minutes}M",
            "productionCandidateGracePeriod": (
                production_candidate_grace_period
            ),
            "reason": reason or "validate-disposable-delete-lifecycle",
            "configuredAt": at,
        }
        result["lifecycleReason"] = (
            "awaiting-grace-end-recheck"
            if event_time >= deadline
            else "awaiting-grace-period"
        )
    elif event == "source-relocated":
        if not package_id:
            raise ValueError("source-relocated requires --package-id")
        require_state(result, "providerSource", {"active", "pending"})
        require_state(result, "registrySyncPackage", {"active", "pending"})
        old_package_id = result.get("packageId")
        if old_package_id and old_package_id != package_id:
            previous = result.setdefault("previousPackageIds", [])
            if old_package_id not in previous:
                previous.append(old_package_id)
        result["packageId"] = package_id
        retirement["missingSince"] = None
        retirement["gracePeriodEndsAt"] = None
        result["lifecycleReason"] = "source-active"
        set_object_state(
            retirement["providerSource"],
            "active",
            "observed-via-registry-sync",
            at,
        )
        set_object_state(
            retirement["registrySyncPackage"],
            "active",
            "observed-in-inventory",
            at,
        )
    elif event == "source-retirement-approved":
        require_state(result, "providerSource", {"pending"})
        require_state(result, "registrySyncPackage", {"pending"})
        grace_period_ends_at = retirement.get("gracePeriodEndsAt")
        if not isinstance(grace_period_ends_at, str):
            raise ValueError(
                "source-retirement-approved requires a grace-period deadline"
            )
        grace_deadline = parsed_timestamp(
            grace_period_ends_at,
            "gracePeriodEndsAt",
        )
        if event_time < grace_deadline:
            raise ValueError(
                "source-retirement-approved rejected: "
                "the grace period has not ended"
            )
        retirement["sourceRetirementApprovedAt"] = at
        result["lifecycleReason"] = "companion-retirement-pending"
        set_object_state(
            retirement["providerSource"],
            "retired",
            reason or "retired-by-sustained-registry-absence-policy",
            at,
        )
        set_object_state(
            retirement["registrySyncPackage"],
            "retired",
            "absence-confirmed-after-grace-period",
            at,
        )
        set_object_state(
            retirement["companionRegistration"],
            "pending",
            "approval-required",
            at,
        )
    elif event == "registration-retirement-approved":
        require_state(result, "providerSource", {"retired"})
        require_state(result, "registrySyncPackage", {"retired"})
        registration = require_state(
            result, "companionRegistration", {"pending"}
        )
        retirement["companionRegistrationRetirementApprovedAt"] = at
        result["lifecycleReason"] = "companion-retirement-approved"
        set_object_state(
            registration,
            "pending",
            "retirement-approved",
            at,
        )
    elif event == "registration-retired":
        require_state(result, "providerSource", {"retired"})
        require_state(result, "registrySyncPackage", {"retired"})
        if not retirement.get(
            "companionRegistrationRetirementApprovedAt"
        ):
            raise ValueError(
                "Registration retirement approval must be recorded before "
                "registration-retired"
            )
        registration = require_state(
            result, "companionRegistration", {"active", "pending"}
        )
        companion_package = require_state(
            result, "companionPackage", {"active", "pending"}
        )
        set_object_state(
            registration, "retired", reason or "deletion-verified", at
        )
        set_object_state(
            companion_package,
            "pending",
            "awaiting-removal-propagation",
            at,
        )
    elif event == "companion-package-retired":
        require_state(result, "companionRegistration", {"retired"})
        companion_package = require_state(
            result, "companionPackage", {"pending"}
        )
        set_object_state(
            companion_package, "retired", reason or "deletion-verified", at
        )
        set_object_state(
            retirement["agentIdentity"],
            "pending",
            "approval-required",
            at,
        )
    elif event == "companion-package-pending":
        require_state(result, "companionRegistration", {"retired"})
        companion_package = require_state(
            result, "companionPackage", {"active", "pending"}
        )
        set_object_state(
            companion_package,
            "pending",
            reason or "awaiting-removal-propagation",
            at,
        )
    elif event == "identity-retirement-approved":
        require_state(result, "companionRegistration", {"retired"})
        require_state(result, "companionPackage", {"retired"})
        identity = require_state(result, "agentIdentity", {"pending"})
        retirement["agentIdentityRetirementApprovedAt"] = at
        set_object_state(
            identity,
            "pending",
            "retirement-approved",
            at,
        )
    elif event == "identity-retired":
        require_state(result, "companionRegistration", {"retired"})
        require_state(result, "companionPackage", {"retired"})
        if not retirement.get("agentIdentityRetirementApprovedAt"):
            raise ValueError(
                "Agent Identity retirement approval must be recorded before "
                "identity-retired"
            )
        identity = require_state(
            result, "agentIdentity", {"active", "pending"}
        )
        set_object_state(
            identity, "retired", reason or "deletion-verified", at
        )
    elif event == "block-object":
        if not object_name:
            raise ValueError("block-object requires --object")
        if object_name in SOURCE_OBJECTS:
            state = require_state(
                result,
                object_name,
                {"active", "pending", "blocked"},
            )
        elif object_name in BLUEPRINT_OBJECTS:
            state = require_blueprint_state(
                result,
                object_name,
                {"active", "pending", "blocked"},
            )
        else:
            raise ValueError(f"Unknown object: {object_name}")
        set_object_state(
            state,
            "blocked",
            reason or "manual-review-required",
            at,
        )
    elif event == "blueprint-cleanup-started":
        if result.get("assignmentMode") != "dedicated":
            raise ValueError("Shared Blueprint cleanup cannot start per source")
        if result.get("lifecycleStatus") != "retired":
            raise ValueError(
                "Source retirement must finish before Blueprint cleanup"
            )
        cleanup = result["blueprintCleanup"]
        for name in BLUEPRINT_OBJECTS:
            state = require_blueprint_state(
                result,
                name,
                {"active", "pending"},
            )
            if state.get("status") == "active":
                set_object_state(
                    state,
                    "pending",
                    reason or "deletion-approved",
                    at,
                )
        cleanup["reason"] = "dedicated-group-empty"
    elif event in {"blueprint-retired", "blueprint-principal-retired"}:
        if result.get("assignmentMode") != "dedicated":
            raise ValueError("Shared Blueprint objects remain group-owned")
        if result.get("lifecycleStatus") != "retired":
            raise ValueError(
                "Source retirement must finish before Blueprint cleanup"
            )
        name = (
            "blueprint"
            if event == "blueprint-retired"
            else "blueprintPrincipal"
        )
        state = require_blueprint_state(result, name, {"pending"})
        set_object_state(
            state, "retired", reason or "deletion-verified", at
        )
    else:
        raise ValueError(f"Unsupported event: {event}")

    recalculate(result)
    return result


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Prototype local-only Demo 3 mapping lifecycle transitions."
    )
    result.add_argument("--mapping", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--at", help="Explicit ISO timestamp for reproducible runs")
    subparsers = result.add_subparsers(dest="command", required=True)
    subparsers.add_parser("initialize")

    event_parser = subparsers.add_parser("event")
    event_parser.add_argument(
        "event",
        choices=(
            "source-missing",
            "configure-simulation-grace",
            "source-relocated",
            "source-retirement-approved",
            "registration-retirement-approved",
            "registration-retired",
            "companion-package-pending",
            "companion-package-retired",
            "identity-retirement-approved",
            "identity-retired",
            "block-object",
            "blueprint-cleanup-started",
            "blueprint-retired",
            "blueprint-principal-retired",
        ),
    )
    event_parser.add_argument("--reason")
    event_parser.add_argument("--package-id")
    event_parser.add_argument("--grace-period-ends-at")
    event_parser.add_argument("--simulation-grace-minutes", type=int)
    event_parser.add_argument("--production-candidate-grace-period")
    event_parser.add_argument(
        "--object",
        choices=SOURCE_OBJECTS + BLUEPRINT_OBJECTS,
    )
    return result


def main() -> None:
    args = parser().parse_args()
    try:
        current = load_json(args.mapping)
        at = timestamp(args.at)
        if args.command == "initialize":
            updated = initialize(current, at)
        else:
            updated = apply_event(
                current,
                args.event,
                at,
                reason=args.reason,
                package_id=args.package_id,
                grace_period_ends_at=args.grace_period_ends_at,
                object_name=args.object,
                simulation_grace_minutes=args.simulation_grace_minutes,
                production_candidate_grace_period=(
                    args.production_candidate_grace_period
                ),
            )
        save_json(args.output, updated)
        print(
            f"Saved {args.output} with lifecycleStatus="
            f"{updated['lifecycleStatus']} and blueprintCleanup.status="
            f"{updated['blueprintCleanup']['status']}"
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"Prototype failed: {error}") from error


if __name__ == "__main__":
    main()

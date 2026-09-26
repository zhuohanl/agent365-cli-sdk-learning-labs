"""Prototype local-only lifecycle transitions for the Demo 3 mapping."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
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
OBSERVATION_TIMESTAMP_FIELDS = {
    "lastCheckedAt",
    "statusChangedAt",
    "retiredAt",
    "missingSince",
    "lastHealthyAbsenceObservedAt",
    "retirementApprovedAt",
    "observedAt",
    "resolvedAt",
    "eligibilityInvalidatedAt",
    "lastSourceObservedAt",
}


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


def latest_observation_timestamp(value: Any) -> str | None:
    timestamps: list[tuple[datetime, str]] = []

    def collect(current: Any) -> None:
        if isinstance(current, dict):
            for key, nested in current.items():
                if (
                    key in OBSERVATION_TIMESTAMP_FIELDS
                    and isinstance(nested, str)
                ):
                    timestamps.append(
                        (parsed_timestamp(nested, key), nested)
                    )
                else:
                    collect(nested)
        elif isinstance(current, list):
            for nested in current:
                collect(nested)

    collect(value)
    if not timestamps:
        return None
    return max(timestamps, key=lambda item: item[0])[1]


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
        "lastHealthyAbsenceObservedAt": None,
        "lastSourceObservation": "present",
        "lastSourceObservedAt": at,
        "retirementApprovedAt": None,
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
    result["blueprintCleanup"] = {
        "status": "active",
        "reason": "source-active",
        "remainingAgentIdentities": None,
        "pendingIdentityReservations": None,
        "lastCheckedAt": None,
        "membershipEvidence": None,
        "eligibilityInvalidatedAt": None,
        "blueprintDelete": {
            "status": "not-started",
            "startedAt": None,
            "verifiedAt": None,
        },
        "blueprint": object_state("active", "verified-present", at),
        "blueprintPrincipal": object_state("active", "verified-present", at),
    }
    result["reconciliationHold"] = {
        "status": "clear",
        "reason": None,
        "observedAt": None,
        "packageId": None,
        "resolvedAt": None,
        "previousSourceObservation": None,
        "previousSourceObservedAt": None,
    }
    result["safetyWatermarkAt"] = at
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


def invalidate_blueprint_eligibility(
    mapping: dict[str, Any],
    at: str,
) -> None:
    cleanup = mapping["blueprintCleanup"]
    delete_pending = cleanup["blueprintDelete"]["status"] == "pending"
    cleanup["remainingAgentIdentities"] = None
    cleanup["pendingIdentityReservations"] = None
    cleanup["membershipEvidence"] = None
    cleanup["lastCheckedAt"] = at
    cleanup["eligibilityInvalidatedAt"] = at
    for name in BLUEPRINT_OBJECTS:
        state = cleanup[name]
        if state.get("status") == "pending" and not delete_pending:
            set_object_state(
                state,
                "active",
                "awaiting-membership-recheck",
                at,
            )


def recalculate(mapping: dict[str, Any]) -> None:
    retirement = mapping["retirement"]
    source_states = [retirement[name]["status"] for name in SOURCE_OBJECTS]
    managed_states = [
        retirement[name]["status"] for name in MANAGED_SOURCE_OBJECTS
    ]
    hold = mapping.get("reconciliationHold", {})
    if hold.get("status") == "blocked":
        mapping["lifecycleStatus"] = "blocked"
        mapping["lifecycleReason"] = hold.get(
            "reason",
            "source-reappearance-review-required",
        )
    elif "blocked" in source_states:
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
        if (
            (cleanup.get("remainingAgentIdentities") or 0) > 0
            or (cleanup.get("pendingIdentityReservations") or 0) > 0
        ):
            cleanup["reason"] = "group-not-empty"
        elif mapping["lifecycleStatus"] == "active":
            cleanup["reason"] = "source-active"
        elif mapping["lifecycleStatus"] == "retired":
            cleanup["reason"] = "awaiting-group-membership-check"
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
    remaining_agent_identities: int | None = None,
    pending_identity_reservations: int | None = None,
    blueprint_id: str | None = None,
    enumeration_complete: bool = False,
    onboarding_exclusion_held: bool = False,
    max_observation_age_minutes: int | None = None,
) -> dict[str, Any]:
    result = deepcopy(mapping)
    retirement = result.get("retirement")
    if not isinstance(retirement, dict):
        raise ValueError("Initialize the mapping before applying events")
    event_time = parsed_timestamp(at, "event timestamp")
    retirement.setdefault("retirementApprovedAt", None)
    retirement.setdefault("lastHealthyAbsenceObservedAt", None)
    legacy_approvals = {
        key: retirement.pop(key)
        for key in (
            "sourceDeletionConfirmedAt",
            "sourceRetirementApprovedAt",
            "companionRegistrationRetirementApprovedAt",
            "agentIdentityRetirementApprovedAt",
        )
        if key in retirement
    }
    if legacy_approvals:
        retirement.setdefault("legacyApprovalHistory", {}).update(
            legacy_approvals
        )
    hold = result.setdefault(
        "reconciliationHold",
        {
            "status": "clear",
            "reason": None,
            "observedAt": None,
            "packageId": None,
            "resolvedAt": None,
            "previousSourceObservation": None,
            "previousSourceObservedAt": None,
        },
    )
    watermark = result.get("safetyWatermarkAt")
    if not isinstance(watermark, str):
        watermark = latest_observation_timestamp(result)
    if isinstance(watermark, str) and event_time < parsed_timestamp(
        watermark,
        "safetyWatermarkAt",
    ):
        raise ValueError("event timestamp cannot move safety state backward")
    result["blueprintCleanup"].setdefault(
        "blueprintDelete",
        {
            "status": "not-started",
            "startedAt": None,
            "verifiedAt": None,
        },
    )
    if hold.get("status") == "blocked" and event in {
        "registration-retired",
        "companion-package-pending",
        "companion-package-retired",
        "identity-retired",
        "blueprint-membership-observed",
        "blueprint-delete-started",
        "blueprint-retired",
        "blueprint-principal-retired",
    }:
        raise ValueError(
            "Source reappearance hold must be cleared before cleanup resumes"
        )

    if event == "source-missing":
        provider_source = require_state(
            result,
            "providerSource",
            {"active", "pending", "retired"},
        )
        registry_package = require_state(
            result,
            "registrySyncPackage",
            {"active", "pending", "retired"},
        )
        previous_observation = retirement.get(
            "lastHealthyAbsenceObservedAt"
        )
        if isinstance(previous_observation, str) and event_time < (
            parsed_timestamp(
                previous_observation,
                "lastHealthyAbsenceObservedAt",
            )
        ):
            raise ValueError(
                "source-missing observation cannot move backward in time"
            )
        retirement["missingSince"] = retirement.get("missingSince") or at
        retirement["lastHealthyAbsenceObservedAt"] = at
        retirement["lastSourceObservation"] = "absent"
        retirement["lastSourceObservedAt"] = at
        if grace_period_ends_at is not None:
            deadline = validated_timestamp(
                grace_period_ends_at,
                "--grace-period-ends-at",
            )
            if parsed_timestamp(deadline, "--grace-period-ends-at") <= (
                parsed_timestamp(retirement["missingSince"], "missingSince")
            ):
                raise ValueError(
                    "--grace-period-ends-at must be after missingSince"
                )
            retirement["gracePeriodEndsAt"] = deadline
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
        if provider_source["status"] != "retired":
            set_object_state(
                provider_source,
                "pending",
                "provider-presence-unconfirmed",
                at,
            )
        if registry_package["status"] != "retired":
            set_object_state(
                registry_package,
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
        retirement["lastHealthyAbsenceObservedAt"] = None
        retirement["lastSourceObservation"] = "present"
        retirement["lastSourceObservedAt"] = at
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
    elif event == "source-reappeared":
        if not package_id:
            raise ValueError("source-reappeared requires --package-id")
        if not retirement.get("retirementApprovedAt"):
            raise ValueError(
                "Use source-relocated before retirement approval"
            )
        latest_hold_time = hold.get("resolvedAt") or hold.get("observedAt")
        if isinstance(latest_hold_time, str) and event_time < parsed_timestamp(
            latest_hold_time,
            "reconciliationHold timestamp",
        ):
            raise ValueError(
                "source-reappeared observation cannot move backward in time"
            )
        old_package_id = result.get("packageId")
        if old_package_id and old_package_id != package_id:
            previous = result.setdefault("previousPackageIds", [])
            if old_package_id not in previous:
                previous.append(old_package_id)
        result["packageId"] = package_id
        hold_was_blocked = hold.get("status") == "blocked"
        if not hold_was_blocked:
            hold["previousSourceObservation"] = retirement.get(
                "lastSourceObservation"
            )
            hold["previousSourceObservedAt"] = retirement.get(
                "lastSourceObservedAt"
            )
        retirement["lastSourceObservation"] = "present"
        retirement["lastSourceObservedAt"] = at
        hold.update(
            {
                "status": "blocked",
                "reason": "source-reappeared-during-retirement",
                "observedAt": at,
                "packageId": package_id,
                "resolvedAt": None,
            }
        )
        if result["blueprintCleanup"]["blueprint"]["status"] != "retired":
            invalidate_blueprint_eligibility(result, at)
    elif event == "source-reappearance-cleared":
        if hold.get("status") != "blocked" or not reason:
            raise ValueError(
                "source-reappearance-cleared requires an active hold and "
                "an evidence-backed --reason"
            )
        if event_time < parsed_timestamp(
            hold["observedAt"],
            "reconciliationHold.observedAt",
        ):
            raise ValueError(
                "source-reappearance clearance cannot precede the hold"
            )
        hold["status"] = "clear"
        hold["reason"] = f"cleared:{reason}"
        hold["resolvedAt"] = at
        retirement["lastSourceObservation"] = hold.get(
            "previousSourceObservation"
        )
        retirement["lastSourceObservedAt"] = hold.get(
            "previousSourceObservedAt"
        )
    elif event == "retirement-approved":
        provider_source = require_state(
            result,
            "providerSource",
            {"pending", "retired"},
        )
        registry_package = require_state(
            result,
            "registrySyncPackage",
            {"pending", "retired"},
        )
        grace_period_ends_at = retirement.get("gracePeriodEndsAt")
        if not isinstance(grace_period_ends_at, str):
            raise ValueError(
                "retirement-approved requires a grace-period deadline"
            )
        grace_deadline = parsed_timestamp(
            grace_period_ends_at,
            "gracePeriodEndsAt",
        )
        missing_since = parsed_timestamp(
            retirement.get("missingSince", ""),
            "missingSince",
        )
        if grace_deadline <= missing_since:
            raise ValueError(
                "retirement-approved requires missingSince before the "
                "grace deadline"
            )
        if event_time < grace_deadline:
            raise ValueError(
                "retirement-approved rejected: "
                "the grace period has not ended"
            )
        last_absence = retirement.get("lastHealthyAbsenceObservedAt")
        if not isinstance(last_absence, str) or parsed_timestamp(
            last_absence,
            "lastHealthyAbsenceObservedAt",
        ) < grace_deadline:
            raise ValueError(
                "retirement-approved requires a healthy complete absence "
                "observation at or after the grace deadline"
            )
        absence_observation = parsed_timestamp(
            last_absence,
            "lastHealthyAbsenceObservedAt",
        )
        if (
            retirement.get("lastSourceObservation") != "absent"
            or retirement.get("lastSourceObservedAt") != last_absence
        ):
            raise ValueError(
                "retirement-approved requires the current source "
                "observation to be absent"
            )
        if absence_observation > event_time:
            raise ValueError(
                "retirement approval cannot precede its absence observation"
            )
        if (
            max_observation_age_minutes is None
            or max_observation_age_minutes <= 0
        ):
            raise ValueError(
                "retirement-approved requires a positive "
                "--max-observation-age-minutes"
            )
        if event_time - absence_observation > timedelta(
            minutes=max_observation_age_minutes
        ):
            raise ValueError(
                "retirement-approved requires a fresh absence observation"
            )
        require_state(
            result,
            "companionRegistration",
            {"active", "pending", "retired"},
        )
        if not retirement.get("retirementApprovedAt"):
            retirement["retirementApprovedAt"] = at
            retirement["approvalObservationMaxAgeMinutes"] = (
                max_observation_age_minutes
            )
        result["lifecycleReason"] = "automatic-retirement-in-progress"
        if provider_source["status"] != "retired":
            set_object_state(
                provider_source,
                "retired",
                reason or "retired-by-sustained-registry-absence-policy",
                at,
            )
        if registry_package["status"] != "retired":
            set_object_state(
                registry_package,
                "retired",
                "absence-confirmed-after-grace-period",
                at,
            )
        registration = retirement["companionRegistration"]
        if registration["status"] != "retired":
            set_object_state(
                registration,
                "pending",
                "retirement-approved",
                at,
            )
    elif event == "registration-retired":
        require_state(result, "providerSource", {"retired"})
        require_state(result, "registrySyncPackage", {"retired"})
        if not retirement.get("retirementApprovedAt"):
            raise ValueError(
                "Retirement approval must be recorded before "
                "registration-retired"
            )
        registration = require_state(
            result,
            "companionRegistration",
            {"active", "pending", "retired"},
        )
        companion_package = require_state(
            result,
            "companionPackage",
            {"active", "pending", "retired"},
        )
        set_object_state(
            registration, "retired", reason or "deletion-verified", at
        )
        if companion_package["status"] != "retired":
            set_object_state(
                companion_package,
                "pending",
                "awaiting-removal-propagation",
                at,
            )
    elif event == "companion-package-retired":
        require_state(result, "companionRegistration", {"retired"})
        companion_package = require_state(
            result, "companionPackage", {"pending", "retired"}
        )
        set_object_state(
            companion_package, "retired", reason or "deletion-verified", at
        )
        identity = require_state(
            result,
            "agentIdentity",
            {"active", "pending", "retired"},
        )
        if identity["status"] != "retired":
            set_object_state(
                identity,
                "pending",
                "retirement-approved",
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
    elif event == "identity-retired":
        require_state(result, "companionRegistration", {"retired"})
        require_state(result, "companionPackage", {"retired"})
        if not retirement.get("retirementApprovedAt"):
            raise ValueError(
                "Retirement approval must be recorded before "
                "identity-retired"
            )
        identity = require_state(
            result, "agentIdentity", {"active", "pending", "retired"}
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
            invalidate_blueprint_eligibility(result, at)
        else:
            raise ValueError(f"Unknown object: {object_name}")
        set_object_state(
            state,
            "blocked",
            reason or "manual-review-required",
            at,
        )
    elif event == "block-resolved":
        if not object_name or not reason:
            raise ValueError(
                "block-resolved requires --object and an evidence-backed "
                "--reason"
            )
        if object_name in SOURCE_OBJECTS:
            state = require_state(result, object_name, {"blocked"})
            if object_name in {"providerSource", "registrySyncPackage"}:
                status = "pending"
                resolved_reason = "reconciliation-pending"
            elif object_name == "companionRegistration":
                status = (
                    "pending"
                    if retirement.get("retirementApprovedAt")
                    else "active"
                )
                resolved_reason = (
                    "retirement-approved"
                    if status == "pending"
                    else "verified-present"
                )
            elif object_name == "companionPackage":
                registration_status = retirement[
                    "companionRegistration"
                ]["status"]
                status = "pending" if registration_status == "retired" else "active"
                resolved_reason = (
                    "awaiting-removal-propagation"
                    if status == "pending"
                    else "verified-present"
                )
            else:
                package_status = retirement["companionPackage"]["status"]
                status = "pending" if package_status == "retired" else "active"
                resolved_reason = (
                    "retirement-approved"
                    if status == "pending"
                    else "verified-present"
                )
        elif object_name in BLUEPRINT_OBJECTS:
            state = require_blueprint_state(result, object_name, {"blocked"})
            delete_pending = (
                result["blueprintCleanup"]["blueprintDelete"]["status"]
                == "pending"
            )
            blueprint_retired = (
                result["blueprintCleanup"]["blueprint"]["status"]
                == "retired"
            )
            if object_name == "blueprintPrincipal" and blueprint_retired:
                status = "pending"
                resolved_reason = "awaiting-cascade-verification"
            elif object_name == "blueprint" and delete_pending:
                invalidate_blueprint_eligibility(result, at)
                status = "pending"
                resolved_reason = "awaiting-deletion-verification"
            else:
                invalidate_blueprint_eligibility(result, at)
                status = "active"
                resolved_reason = "awaiting-membership-recheck"
        else:
            raise ValueError(f"Unknown object: {object_name}")
        set_object_state(
            state,
            status,
            f"{resolved_reason}:{reason}",
            at,
        )
    elif event == "blueprint-membership-observed":
        if result.get("lifecycleStatus") != "retired":
            raise ValueError(
                "Source retirement must finish before Blueprint cleanup"
            )
        if not retirement.get("retirementApprovedAt"):
            raise ValueError(
                "Blueprint cleanup requires explicit retirement approval"
            )
        latest_evidence_time = result["blueprintCleanup"].get(
            "lastCheckedAt"
        )
        invalidated_at = result["blueprintCleanup"].get(
            "eligibilityInvalidatedAt"
        )
        for field, value in (
            ("blueprintCleanup.lastCheckedAt", latest_evidence_time),
            ("blueprintCleanup.eligibilityInvalidatedAt", invalidated_at),
            ("reconciliationHold.resolvedAt", hold.get("resolvedAt")),
        ):
            if isinstance(value, str) and event_time < parsed_timestamp(
                value,
                field,
            ):
                raise ValueError(
                    "blueprint membership observation cannot move backward "
                    "in time"
                )
        identity_retired_at = retirement["agentIdentity"].get("retiredAt")
        if not isinstance(identity_retired_at, str) or event_time < (
            parsed_timestamp(identity_retired_at, "agentIdentity.retiredAt")
        ):
            raise ValueError(
                "Blueprint membership must be observed after Agent Identity "
                "retirement"
            )
        if remaining_agent_identities is None or remaining_agent_identities < 0:
            raise ValueError(
                "blueprint-membership-observed requires a non-negative "
                "--remaining-agent-identities"
            )
        if (
            pending_identity_reservations is None
            or pending_identity_reservations < 0
        ):
            raise ValueError(
                "blueprint-membership-observed requires a non-negative "
                "--pending-identity-reservations"
            )
        if not blueprint_id or blueprint_id != result.get("blueprintId"):
            raise ValueError(
                "--blueprint-id must match the locked mapping Blueprint appId"
            )
        if not enumeration_complete:
            raise ValueError(
                "Blueprint membership enumeration must be complete"
            )
        if not onboarding_exclusion_held:
            raise ValueError(
                "Blueprint onboarding exclusion must remain held through "
                "deletion"
            )
        cleanup = result["blueprintCleanup"]
        cleanup["remainingAgentIdentities"] = remaining_agent_identities
        cleanup["pendingIdentityReservations"] = (
            pending_identity_reservations
        )
        cleanup["lastCheckedAt"] = at
        cleanup["membershipEvidence"] = {
            "blueprintId": blueprint_id,
            "observedAt": at,
            "enumerationComplete": True,
            "onboardingExclusionHeld": True,
        }
        if (
            remaining_agent_identities == 0
            and pending_identity_reservations == 0
        ):
            for name in BLUEPRINT_OBJECTS:
                state = require_blueprint_state(
                    result,
                    name,
                    {"active", "pending"},
                )
                set_object_state(
                    state,
                    "pending",
                    reason or "automatic-cleanup-ready",
                    at,
                )
            cleanup["reason"] = "group-empty-automatic-cleanup"
        else:
            for name in BLUEPRINT_OBJECTS:
                state = require_blueprint_state(
                    result,
                    name,
                    {"active", "pending"},
                )
                set_object_state(state, "active", "verified-present", at)
            cleanup["reason"] = "group-not-empty"
    elif event == "blueprint-delete-started":
        if result.get("lifecycleStatus") != "retired":
            raise ValueError(
                "Source retirement must finish before Blueprint deletion"
            )
        if not retirement.get("retirementApprovedAt"):
            raise ValueError(
                "Blueprint deletion requires explicit retirement approval"
            )
        cleanup = result["blueprintCleanup"]
        if cleanup.get("status") == "blocked":
            raise ValueError(
                "Blueprint deletion cannot start while cleanup is blocked"
            )
        if (
            cleanup.get("remainingAgentIdentities") != 0
            or cleanup.get("pendingIdentityReservations") != 0
            or not cleanup.get("membershipEvidence", {}).get(
                "onboardingExclusionHeld"
            )
        ):
            raise ValueError(
                "Blueprint deletion requires fresh empty-group eligibility"
            )
        require_blueprint_state(result, "blueprint", {"pending"})
        require_blueprint_state(result, "blueprintPrincipal", {"pending"})
        delete_state = cleanup["blueprintDelete"]
        if delete_state["status"] == "not-started":
            delete_state["status"] = "pending"
            delete_state["startedAt"] = at
    elif event in {"blueprint-retired", "blueprint-principal-retired"}:
        if result.get("lifecycleStatus") != "retired":
            raise ValueError(
                "Source retirement must finish before Blueprint cleanup"
            )
        if not retirement.get("retirementApprovedAt"):
            raise ValueError(
                "Blueprint cleanup requires explicit retirement approval"
            )
        cleanup = result["blueprintCleanup"]
        name = (
            "blueprint"
            if event == "blueprint-retired"
            else "blueprintPrincipal"
        )
        if name == "blueprint":
            delete_status = cleanup["blueprintDelete"]["status"]
            current_status = cleanup["blueprint"]["status"]
            if delete_status == "verified" and current_status == "retired":
                recalculate(result)
                result["safetyWatermarkAt"] = at
                return result
            if delete_status != "pending":
                raise ValueError(
                    "blueprint-retired requires blueprint-delete-started"
                )
        elif cleanup["blueprint"]["status"] != "retired":
            raise ValueError(
                "Blueprint principal retirement requires verified Blueprint "
                "retirement"
            )
        state = require_blueprint_state(
            result,
            name,
            {"pending", "retired"},
        )
        set_object_state(
            state, "retired", reason or "deletion-verified", at
        )
        if name == "blueprint":
            cleanup["blueprintDelete"]["status"] = "verified"
            cleanup["blueprintDelete"]["verifiedAt"] = at
    else:
        raise ValueError(f"Unsupported event: {event}")

    recalculate(result)
    result["safetyWatermarkAt"] = at
    return result


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, indent=2) + "\n"
    staging_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as staging:
            staging_path = Path(staging.name)
            staging.write(serialized)
            staging.flush()
            os.fsync(staging.fileno())
        os.replace(staging_path, path)
    finally:
        if staging_path is not None and staging_path.exists():
            staging_path.unlink()


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
            "source-reappeared",
            "source-reappearance-cleared",
            "retirement-approved",
            "registration-retired",
            "companion-package-pending",
            "companion-package-retired",
            "identity-retired",
            "block-object",
            "block-resolved",
            "blueprint-membership-observed",
            "blueprint-delete-started",
            "blueprint-retired",
            "blueprint-principal-retired",
        ),
    )
    event_parser.add_argument("--reason")
    event_parser.add_argument("--package-id")
    event_parser.add_argument("--grace-period-ends-at")
    event_parser.add_argument("--simulation-grace-minutes", type=int)
    event_parser.add_argument("--production-candidate-grace-period")
    event_parser.add_argument("--max-observation-age-minutes", type=int)
    event_parser.add_argument("--remaining-agent-identities", type=int)
    event_parser.add_argument("--pending-identity-reservations", type=int)
    event_parser.add_argument("--blueprint-id")
    event_parser.add_argument(
        "--enumeration-complete",
        action="store_true",
    )
    event_parser.add_argument(
        "--onboarding-exclusion-held",
        action="store_true",
    )
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
                remaining_agent_identities=args.remaining_agent_identities,
                pending_identity_reservations=(
                    args.pending_identity_reservations
                ),
                blueprint_id=args.blueprint_id,
                enumeration_complete=args.enumeration_complete,
                onboarding_exclusion_held=args.onboarding_exclusion_held,
                max_observation_age_minutes=(
                    args.max_observation_age_minutes
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

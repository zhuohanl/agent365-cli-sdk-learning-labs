"""Validate the local-only Demo 3 retirement mapping prototype."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


LAB = Path(__file__).resolve().parents[1]
HELPER = (
    LAB
    / "demos"
    / "03-delete-companion"
    / "prototype_retirement_mapping.py"
)
SPEC = spec_from_file_location("prototype_retirement_mapping", HELPER)
assert SPEC and SPEC.loader
prototype = module_from_spec(SPEC)
SPEC.loader.exec_module(prototype)


class RetirementMappingPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.mapping = prototype.initialize(
            {
                "assignmentMode": "dedicated",
                "blueprintId": "blueprint-app-id",
            },
            "2026-09-12T17:00:00+00:00",
        )

    def test_initial_mapping_separates_lifecycle_reason(self):
        self.assertEqual(self.mapping["lifecycleStatus"], "active")
        self.assertEqual(self.mapping["lifecycleReason"], "source-active")
        self.assertEqual(
            self.mapping["retirement"]["providerSource"]["reason"],
            "observed-via-registry-sync",
        )

    def test_source_missing_rejects_placeholder_grace_deadline(self):
        with self.assertRaisesRegex(ValueError, "real ISO 8601 timestamp"):
            prototype.apply_event(
                self.mapping,
                "source-missing",
                "2026-09-12T17:16:00+00:00",
                grace_period_ends_at="<approved-ISO-8601-deadline>",
            )

    def test_source_missing_rejects_timezone_free_grace_deadline(self):
        with self.assertRaisesRegex(ValueError, "include a timezone"):
            prototype.apply_event(
                self.mapping,
                "source-missing",
                "2026-09-12T17:16:00+00:00",
                grace_period_ends_at="2026-09-26T17:16:00",
            )

    def test_repeated_source_missing_preserves_existing_deadline(self):
        first = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
            grace_period_ends_at="2026-09-26T17:16:00+00:00",
        )
        second = prototype.apply_event(
            first,
            "source-missing",
            "2026-09-13T17:16:00+00:00",
        )

        self.assertEqual(
            second["retirement"]["gracePeriodEndsAt"],
            "2026-09-26T17:16:00+00:00",
        )
        self.assertEqual(
            second["retirement"]["providerSource"]["statusChangedAt"],
            "2026-09-12T17:16:00+00:00",
        )
        self.assertEqual(
            second["retirement"]["providerSource"]["lastCheckedAt"],
            "2026-09-13T17:16:00+00:00",
        )
        self.assertEqual(
            second["retirement"]["providerSource"]["reason"],
            "provider-presence-unconfirmed",
        )
        self.assertEqual(
            second["lifecycleReason"],
            "awaiting-grace-period",
        )
        self.assertEqual(
            second["retirement"]["registrySyncPackage"]["reason"],
            "not-observed-in-complete-inventory",
        )
        self.assertEqual(
            second["blueprintCleanup"]["reason"],
            "source-retirement-incomplete",
        )

    def test_source_relocation_restores_blueprint_cleanup_reason(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
        )
        relocated = prototype.apply_event(
            missing,
            "source-relocated",
            "2026-09-12T18:16:00+00:00",
            package_id="replacement-package",
        )

        self.assertEqual(relocated["lifecycleStatus"], "active")
        self.assertEqual(relocated["lifecycleReason"], "source-active")
        self.assertEqual(
            relocated["blueprintCleanup"]["reason"],
            "source-active",
        )

    def test_source_retirement_is_rejected_before_grace_deadline(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
            grace_period_ends_at="2026-09-26T17:16:00+00:00",
        )

        with self.assertRaisesRegex(ValueError, "grace period has not ended"):
            prototype.apply_event(
                missing,
                "retirement-approved",
                "2026-09-13T17:16:00+00:00",
                max_observation_age_minutes=60,
            )

    def test_retirement_approval_starts_automatic_cleanup(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
            grace_period_ends_at="2026-09-26T17:16:00+00:00",
        )
        rechecked = prototype.apply_event(
            missing,
            "source-missing",
            "2026-09-26T17:16:00+00:00",
        )
        approved = prototype.apply_event(
            rechecked,
            "retirement-approved",
            "2026-09-26T17:16:00+00:00",
            max_observation_age_minutes=60,
        )

        self.assertEqual(approved["lifecycleStatus"], "pending")
        self.assertEqual(
            approved["lifecycleReason"],
            "automatic-retirement-in-progress",
        )
        self.assertEqual(
            approved["retirement"]["providerSource"]["status"],
            "retired",
        )
        self.assertEqual(
            approved["retirement"]["providerSource"]["reason"],
            "retired-by-sustained-registry-absence-policy",
        )
        self.assertEqual(
            approved["retirement"]["registrySyncPackage"]["status"],
            "retired",
        )
        self.assertEqual(
            approved["retirement"]["companionRegistration"]["status"],
            "pending",
        )
        self.assertEqual(
            approved["retirement"]["companionRegistration"]["reason"],
            "retirement-approved",
        )
        self.assertEqual(
            approved["retirement"]["retirementApprovedAt"],
            "2026-09-26T17:16:00+00:00",
        )

    def test_single_approval_covers_registration_and_identity(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
            grace_period_ends_at="2026-09-26T17:16:00+00:00",
        )
        rechecked = prototype.apply_event(
            missing,
            "source-missing",
            "2026-09-26T17:16:00+00:00",
        )
        approved = prototype.apply_event(
            rechecked,
            "retirement-approved",
            "2026-09-26T17:16:00+00:00",
            max_observation_age_minutes=60,
        )
        registration_retired = prototype.apply_event(
            approved,
            "registration-retired",
            "2026-09-26T17:18:00+00:00",
        )
        self.assertEqual(
            registration_retired["retirement"]["companionRegistration"][
                "status"
            ],
            "retired",
        )
        package_retired = prototype.apply_event(
            registration_retired,
            "companion-package-retired",
            "2026-09-26T17:19:00+00:00",
        )
        self.assertEqual(
            package_retired["retirement"]["agentIdentity"]["reason"],
            "retirement-approved",
        )
        retired = prototype.apply_event(
            package_retired,
            "identity-retired",
            "2026-09-26T17:21:00+00:00",
        )
        self.assertEqual(
            retired["retirement"]["agentIdentity"]["status"],
            "retired",
        )

    def test_empty_blueprint_group_starts_automatic_cleanup(self):
        checked = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:22:00+00:00",
            remaining_agent_identities=0,
            pending_identity_reservations=0,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )

        self.assertEqual(checked["blueprintCleanup"]["status"], "pending")
        self.assertEqual(
            checked["blueprintCleanup"]["reason"],
            "group-empty-automatic-cleanup",
        )
        self.assertEqual(
            checked["blueprintCleanup"]["blueprint"]["reason"],
            "automatic-cleanup-ready",
        )

    def test_nonempty_blueprint_group_is_retained(self):
        checked = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:22:00+00:00",
            remaining_agent_identities=2,
            pending_identity_reservations=0,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )

        self.assertEqual(checked["blueprintCleanup"]["status"], "active")
        self.assertEqual(
            checked["blueprintCleanup"]["reason"],
            "group-not-empty",
        )

    def retired_source(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
            grace_period_ends_at="2026-09-26T17:16:00+00:00",
        )
        rechecked = prototype.apply_event(
            missing,
            "source-missing",
            "2026-09-26T17:16:00+00:00",
        )
        approved = prototype.apply_event(
            rechecked,
            "retirement-approved",
            "2026-09-26T17:16:00+00:00",
            max_observation_age_minutes=60,
        )
        registration = prototype.apply_event(
            approved,
            "registration-retired",
            "2026-09-26T17:18:00+00:00",
        )
        package = prototype.apply_event(
            registration,
            "companion-package-retired",
            "2026-09-26T17:19:00+00:00",
        )
        return prototype.apply_event(
            package,
            "identity-retired",
            "2026-09-26T17:21:00+00:00",
        )

    def test_approval_requires_grace_end_absence_observation(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
            grace_period_ends_at="2026-09-26T17:16:00+00:00",
        )

        with self.assertRaisesRegex(
            ValueError,
            "healthy complete absence observation",
        ):
            prototype.apply_event(
                missing,
                "retirement-approved",
                "2026-09-26T17:20:00+00:00",
                max_observation_age_minutes=60,
            )

    def test_legacy_source_approval_is_not_promoted(self):
        legacy = dict(self.mapping)
        legacy["retirement"] = dict(self.mapping["retirement"])
        legacy["retirement"].pop("retirementApprovedAt")
        legacy["retirement"]["sourceRetirementApprovedAt"] = (
            "2026-09-20T17:00:00+00:00"
        )

        updated = prototype.apply_event(
            legacy,
            "source-missing",
            "2026-09-20T18:00:00+00:00",
        )

        self.assertIsNone(updated["retirement"]["retirementApprovedAt"])
        self.assertEqual(
            updated["retirement"]["legacyApprovalHistory"][
                "sourceRetirementApprovedAt"
            ],
            "2026-09-20T17:00:00+00:00",
        )

    def test_approval_does_not_clear_blocked_registration(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
            grace_period_ends_at="2026-09-26T17:16:00+00:00",
        )
        rechecked = prototype.apply_event(
            missing,
            "source-missing",
            "2026-09-26T17:16:00+00:00",
        )
        blocked = prototype.apply_event(
            rechecked,
            "block-object",
            "2026-09-26T17:17:00+00:00",
            object_name="companionRegistration",
            reason="dependency-found",
        )

        with self.assertRaisesRegex(ValueError, "must be active, pending"):
            prototype.apply_event(
                blocked,
                "retirement-approved",
                "2026-09-26T17:18:00+00:00",
                max_observation_age_minutes=60,
            )

    def test_package_observation_does_not_clear_blocked_identity(self):
        mapping = self.retired_source()
        mapping["retirement"]["agentIdentity"] = prototype.object_state(
            "blocked",
            "dependency-found",
            "2026-09-26T17:22:00+00:00",
        )
        mapping["retirement"]["companionPackage"] = prototype.object_state(
            "pending",
            "awaiting-removal-propagation",
            "2026-09-26T17:22:00+00:00",
        )

        with self.assertRaisesRegex(
            ValueError,
            "agentIdentity must be active, pending, retired",
        ):
            prototype.apply_event(
                mapping,
                "companion-package-retired",
                "2026-09-26T17:23:00+00:00",
            )

    def test_block_resolution_resumes_from_verified_dependency_state(self):
        mapping = self.retired_source()
        mapping["retirement"]["agentIdentity"] = prototype.object_state(
            "blocked",
            "permission-denied",
            "2026-09-26T17:22:00+00:00",
        )
        resolved = prototype.apply_event(
            mapping,
            "block-resolved",
            "2026-09-26T17:23:00+00:00",
            object_name="agentIdentity",
            reason="permission-restored-and-read-succeeded",
        )

        self.assertEqual(
            resolved["retirement"]["agentIdentity"]["status"],
            "pending",
        )
        self.assertIn(
            "permission-restored-and-read-succeeded",
            resolved["retirement"]["agentIdentity"]["reason"],
        )

    def test_blueprint_cleanup_requires_bound_complete_evidence(self):
        mapping = self.retired_source()

        with self.assertRaisesRegex(ValueError, "enumeration must be complete"):
            prototype.apply_event(
                mapping,
                "blueprint-membership-observed",
                "2026-09-26T17:22:00+00:00",
                remaining_agent_identities=0,
                pending_identity_reservations=0,
                blueprint_id="blueprint-app-id",
                onboarding_exclusion_held=True,
            )

    def test_blueprint_cleanup_requires_full_plan_approval(self):
        mapping = self.retired_source()
        mapping["retirement"]["retirementApprovedAt"] = None

        with self.assertRaisesRegex(
            ValueError,
            "explicit retirement approval",
        ):
            prototype.apply_event(
                mapping,
                "blueprint-membership-observed",
                "2026-09-26T17:22:00+00:00",
                remaining_agent_identities=0,
                pending_identity_reservations=0,
                blueprint_id="blueprint-app-id",
                enumeration_complete=True,
                onboarding_exclusion_held=True,
            )

    def test_blueprint_block_resolution_invalidates_old_zero_count(self):
        eligible = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:22:00+00:00",
            remaining_agent_identities=0,
            pending_identity_reservations=0,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )
        blocked = prototype.apply_event(
            eligible,
            "block-object",
            "2026-09-26T17:23:00+00:00",
            object_name="blueprint",
            reason="onboarding-exclusion-lost",
        )
        resolved = prototype.apply_event(
            blocked,
            "block-resolved",
            "2026-09-26T17:24:00+00:00",
            object_name="blueprint",
            reason="exclusion-restored",
        )

        self.assertIsNone(
            resolved["blueprintCleanup"]["membershipEvidence"]
        )
        self.assertIsNone(
            resolved["blueprintCleanup"]["remainingAgentIdentities"]
        )
        with self.assertRaisesRegex(
            ValueError,
            "fresh empty-group eligibility",
        ):
            prototype.apply_event(
                resolved,
                "blueprint-delete-started",
                "2026-09-26T17:25:00+00:00",
            )

    def test_principal_verification_recovers_after_blueprint_retirement(self):
        eligible = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:22:00+00:00",
            remaining_agent_identities=0,
            pending_identity_reservations=0,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )
        delete_started = prototype.apply_event(
            eligible,
            "blueprint-delete-started",
            "2026-09-26T17:23:00+00:00",
        )
        blueprint_retired = prototype.apply_event(
            delete_started,
            "blueprint-retired",
            "2026-09-26T17:24:00+00:00",
        )
        blocked = prototype.apply_event(
            blueprint_retired,
            "block-object",
            "2026-09-26T17:25:00+00:00",
            object_name="blueprintPrincipal",
            reason="permission-denied",
        )
        resolved = prototype.apply_event(
            blocked,
            "block-resolved",
            "2026-09-26T17:26:00+00:00",
            object_name="blueprintPrincipal",
            reason="permission-restored",
        )
        completed = prototype.apply_event(
            resolved,
            "blueprint-principal-retired",
            "2026-09-26T17:27:00+00:00",
        )

        self.assertEqual(completed["blueprintCleanup"]["status"], "retired")

    def test_source_hold_invalidates_predelete_blueprint_eligibility(self):
        eligible = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:22:00+00:00",
            remaining_agent_identities=0,
            pending_identity_reservations=0,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )
        held = prototype.apply_event(
            eligible,
            "source-reappeared",
            "2026-09-26T17:23:00+00:00",
            package_id="replacement-package",
        )
        cleared = prototype.apply_event(
            held,
            "source-reappearance-cleared",
            "2026-09-26T17:24:00+00:00",
            reason="stale-inventory-entry",
        )

        self.assertIsNone(cleared["blueprintCleanup"]["membershipEvidence"])
        with self.assertRaisesRegex(
            ValueError,
            "fresh empty-group eligibility",
        ):
            prototype.apply_event(
                cleared,
                "blueprint-delete-started",
                "2026-09-26T17:25:00+00:00",
            )

    def test_membership_observation_cannot_move_backward(self):
        nonempty = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:30:00+00:00",
            remaining_agent_identities=1,
            pending_identity_reservations=0,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )

        with self.assertRaisesRegex(ValueError, "cannot move safety state backward"):
            prototype.apply_event(
                nonempty,
                "blueprint-membership-observed",
                "2026-09-26T17:22:00+00:00",
                remaining_agent_identities=0,
                pending_identity_reservations=0,
                blueprint_id="blueprint-app-id",
                enumeration_complete=True,
                onboarding_exclusion_held=True,
            )

    def test_cross_event_safety_watermark_cannot_move_backward(self):
        observed = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:30:00+00:00",
            remaining_agent_identities=1,
            pending_identity_reservations=0,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )

        with self.assertRaisesRegex(ValueError, "safety state backward"):
            prototype.apply_event(
                observed,
                "source-reappeared",
                "2026-09-26T17:15:00+00:00",
                package_id="replacement-package",
            )

    def test_presence_observation_invalidates_older_absence_episode(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
        )
        present = prototype.apply_event(
            missing,
            "source-relocated",
            "2026-09-12T17:40:00+00:00",
            package_id="replacement-package",
        )

        self.assertIsNone(
            present["retirement"]["lastHealthyAbsenceObservedAt"]
        )
        with self.assertRaisesRegex(ValueError, "safety state backward"):
            prototype.apply_event(
                present,
                "source-missing",
                "2026-09-12T17:20:00+00:00",
            )

    def test_unknown_blueprint_delete_can_resume_with_exact_absence(self):
        eligible = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:22:00+00:00",
            remaining_agent_identities=0,
            pending_identity_reservations=0,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )
        started = prototype.apply_event(
            eligible,
            "blueprint-delete-started",
            "2026-09-26T17:23:00+00:00",
        )
        blocked = prototype.apply_event(
            started,
            "block-object",
            "2026-09-26T17:24:00+00:00",
            object_name="blueprint",
            reason="verification-unavailable",
        )
        resolved = prototype.apply_event(
            blocked,
            "block-resolved",
            "2026-09-26T17:25:00+00:00",
            object_name="blueprint",
            reason="exact-id-read-restored",
        )
        retired = prototype.apply_event(
            resolved,
            "blueprint-retired",
            "2026-09-26T17:26:00+00:00",
        )

        self.assertEqual(
            retired["blueprintCleanup"]["blueprint"]["status"],
            "retired",
        )

    def test_blueprint_retry_requires_fresh_eligibility_after_interruption(self):
        eligible = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:22:00+00:00",
            remaining_agent_identities=0,
            pending_identity_reservations=0,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )
        started = prototype.apply_event(
            eligible,
            "blueprint-delete-started",
            "2026-09-26T17:23:00+00:00",
        )
        blocked = prototype.apply_event(
            started,
            "block-object",
            "2026-09-26T17:24:00+00:00",
            object_name="blueprint",
            reason="onboarding-exclusion-lost",
        )
        resolved = prototype.apply_event(
            blocked,
            "block-resolved",
            "2026-09-26T17:25:00+00:00",
            object_name="blueprint",
            reason="exclusion-restored",
        )

        self.assertIsNone(
            resolved["blueprintCleanup"]["membershipEvidence"]
        )
        self.assertEqual(
            resolved["blueprintCleanup"]["blueprintDelete"]["status"],
            "pending",
        )
        with self.assertRaisesRegex(
            ValueError,
            "fresh empty-group eligibility",
        ):
            prototype.apply_event(
                resolved,
                "blueprint-delete-started",
                "2026-09-26T17:26:00+00:00",
            )

    def test_principal_block_prevents_cascading_blueprint_delete(self):
        eligible = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:22:00+00:00",
            remaining_agent_identities=0,
            pending_identity_reservations=0,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )
        blocked = prototype.apply_event(
            eligible,
            "block-object",
            "2026-09-26T17:23:00+00:00",
            object_name="blueprintPrincipal",
            reason="dependency-found",
        )

        with self.assertRaisesRegex(
            ValueError,
            "cleanup is blocked",
        ):
            prototype.apply_event(
                blocked,
                "blueprint-delete-started",
                "2026-09-26T17:24:00+00:00",
            )

    def test_hold_clearance_preserves_issued_delete_verification(self):
        eligible = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:22:00+00:00",
            remaining_agent_identities=0,
            pending_identity_reservations=0,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )
        started = prototype.apply_event(
            eligible,
            "blueprint-delete-started",
            "2026-09-26T17:23:00+00:00",
        )
        held = prototype.apply_event(
            started,
            "source-reappeared",
            "2026-09-26T17:24:00+00:00",
            package_id="replacement-package",
        )
        cleared = prototype.apply_event(
            held,
            "source-reappearance-cleared",
            "2026-09-26T17:25:00+00:00",
            reason="stale-inventory-entry",
        )
        retired = prototype.apply_event(
            cleared,
            "blueprint-retired",
            "2026-09-26T17:26:00+00:00",
        )

        self.assertEqual(
            retired["blueprintCleanup"]["blueprint"]["status"],
            "retired",
        )

    def test_blueprint_retirement_verification_is_idempotent(self):
        eligible = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:22:00+00:00",
            remaining_agent_identities=0,
            pending_identity_reservations=0,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )
        started = prototype.apply_event(
            eligible,
            "blueprint-delete-started",
            "2026-09-26T17:23:00+00:00",
        )
        retired = prototype.apply_event(
            started,
            "blueprint-retired",
            "2026-09-26T17:24:00+00:00",
        )
        replayed = prototype.apply_event(
            retired,
            "blueprint-retired",
            "2026-09-26T17:25:00+00:00",
        )

        self.assertEqual(
            replayed["blueprintCleanup"]["blueprint"]["retiredAt"],
            "2026-09-26T17:24:00+00:00",
        )
        self.assertEqual(
            replayed["blueprintCleanup"]["blueprintDelete"]["verifiedAt"],
            "2026-09-26T17:24:00+00:00",
        )

    def test_repeated_source_hold_preserves_prehold_observation(self):
        mapping = self.retired_source()
        expected_observation = mapping["retirement"][
            "lastSourceObservation"
        ]
        expected_observed_at = mapping["retirement"][
            "lastSourceObservedAt"
        ]
        first = prototype.apply_event(
            mapping,
            "source-reappeared",
            "2026-09-26T17:22:00+00:00",
            package_id="replacement-package",
        )
        repeated = prototype.apply_event(
            first,
            "source-reappeared",
            "2026-09-26T17:23:00+00:00",
            package_id="replacement-package",
        )
        cleared = prototype.apply_event(
            repeated,
            "source-reappearance-cleared",
            "2026-09-26T17:24:00+00:00",
            reason="stale-inventory-entry",
        )

        self.assertEqual(
            cleared["retirement"]["lastSourceObservation"],
            expected_observation,
        )
        self.assertEqual(
            cleared["retirement"]["lastSourceObservedAt"],
            expected_observed_at,
        )

    def test_repeated_retirement_approval_preserves_original_approval(self):
        replayed = prototype.apply_event(
            self.retired_source(),
            "retirement-approved",
            "2026-09-26T17:30:00+00:00",
            max_observation_age_minutes=30,
        )

        self.assertEqual(
            replayed["retirement"]["retirementApprovedAt"],
            "2026-09-26T17:16:00+00:00",
        )
        self.assertEqual(
            replayed["retirement"]["approvalObservationMaxAgeMinutes"],
            60,
        )

    def test_pending_reservation_retains_blueprint(self):
        checked = prototype.apply_event(
            self.retired_source(),
            "blueprint-membership-observed",
            "2026-09-26T17:22:00+00:00",
            remaining_agent_identities=0,
            pending_identity_reservations=1,
            blueprint_id="blueprint-app-id",
            enumeration_complete=True,
            onboarding_exclusion_held=True,
        )

        self.assertEqual(
            checked["blueprintCleanup"]["reason"],
            "group-not-empty",
        )

    def test_reappearing_source_blocks_approved_cleanup(self):
        mapping = self.retired_source()
        reappeared = prototype.apply_event(
            mapping,
            "source-reappeared",
            "2026-09-26T17:22:00+00:00",
            package_id="replacement-package",
        )

        self.assertEqual(reappeared["lifecycleStatus"], "blocked")
        self.assertEqual(
            reappeared["lifecycleReason"],
            "source-reappeared-during-retirement",
        )
        self.assertEqual(
            reappeared["retirement"]["providerSource"]["retiredAt"],
            mapping["retirement"]["providerSource"]["retiredAt"],
        )

        cleared = prototype.apply_event(
            reappeared,
            "source-reappearance-cleared",
            "2026-09-26T17:23:00+00:00",
            reason="complete-inventory-confirmed-stale-observation",
        )
        self.assertEqual(cleared["lifecycleStatus"], "retired")
        self.assertEqual(
            cleared["retirement"]["providerSource"]["retiredAt"],
            mapping["retirement"]["providerSource"]["retiredAt"],
        )

    def test_verified_retirement_events_are_idempotent(self):
        mapping = self.retired_source()
        replayed = prototype.apply_event(
            mapping,
            "identity-retired",
            "2026-09-26T17:30:00+00:00",
        )

        self.assertEqual(
            replayed["retirement"]["agentIdentity"]["retiredAt"],
            "2026-09-26T17:21:00+00:00",
        )

    def test_save_json_atomically_replaces_same_mapping_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            path.write_text('{"old": true}\n', encoding="utf-8")

            prototype.save_json(path, {"new": True})

            self.assertEqual(
                prototype.load_json(path),
                {"new": True},
            )
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_save_json_cleans_failed_staging_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            original = '{"old": true}\n'
            path.write_text(original, encoding="utf-8")

            with patch.object(
                prototype.os,
                "fsync",
                side_effect=OSError("simulated storage failure"),
            ):
                with self.assertRaisesRegex(
                    OSError,
                    "simulated storage failure",
                ):
                    prototype.save_json(path, {"new": True})

            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_approval_cannot_precede_supporting_observation(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
            grace_period_ends_at="2026-09-26T17:16:00+00:00",
        )
        rechecked = prototype.apply_event(
            missing,
            "source-missing",
            "2026-09-26T17:30:00+00:00",
        )

        with self.assertRaisesRegex(
            ValueError,
            "cannot move safety state backward",
        ):
            prototype.apply_event(
                rechecked,
                "retirement-approved",
                "2026-09-26T17:20:00+00:00",
                max_observation_age_minutes=60,
            )

    def test_approval_requires_fresh_observation(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
            grace_period_ends_at="2026-09-26T17:16:00+00:00",
        )
        rechecked = prototype.apply_event(
            missing,
            "source-missing",
            "2026-09-26T17:16:00+00:00",
        )

        with self.assertRaisesRegex(ValueError, "fresh absence observation"):
            prototype.apply_event(
                rechecked,
                "retirement-approved",
                "2026-09-26T19:16:00+00:00",
                max_observation_age_minutes=60,
            )

    def test_simulation_grace_records_policy_without_faking_time(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
        )
        configured = prototype.apply_event(
            missing,
            "configure-simulation-grace",
            "2026-09-12T17:40:00+00:00",
            simulation_grace_minutes=5,
            production_candidate_grace_period="P14D",
            reason="validate-disposable-delete-lifecycle",
        )

        self.assertEqual(
            configured["retirement"]["gracePeriodEndsAt"],
            "2026-09-12T17:21:00+00:00",
        )
        self.assertEqual(
            configured["retirementPolicy"],
            {
                "mode": "experiment-simulation",
                "gracePeriod": "PT5M",
                "productionCandidateGracePeriod": "P14D",
                "reason": "validate-disposable-delete-lifecycle",
                "configuredAt": "2026-09-12T17:40:00+00:00",
            },
        )
        self.assertEqual(
            configured["lifecycleReason"],
            "awaiting-grace-end-recheck",
        )

    def test_grace_end_source_recheck_waits_for_retirement_approval(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
        )
        configured = prototype.apply_event(
            missing,
            "configure-simulation-grace",
            "2026-09-12T17:40:00+00:00",
            simulation_grace_minutes=5,
            production_candidate_grace_period="P14D",
            reason="validate-disposable-delete-lifecycle",
        )
        rechecked = prototype.apply_event(
            configured,
            "source-missing",
            "2026-09-12T17:45:00+00:00",
        )

        self.assertEqual(
            rechecked["lifecycleReason"],
            "awaiting-source-retirement-approval",
        )

if __name__ == "__main__":
    unittest.main()

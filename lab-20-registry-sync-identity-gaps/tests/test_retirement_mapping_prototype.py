"""Validate the local-only Demo 3 retirement mapping prototype."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


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
            {"assignmentMode": "dedicated"},
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
                "source-retirement-approved",
                "2026-09-13T17:16:00+00:00",
            )

    def test_source_retirement_after_grace_starts_companion_cleanup(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
            grace_period_ends_at="2026-09-26T17:16:00+00:00",
        )
        approved = prototype.apply_event(
            missing,
            "source-retirement-approved",
            "2026-09-26T17:16:00+00:00",
        )

        self.assertEqual(approved["lifecycleStatus"], "pending")
        self.assertEqual(
            approved["lifecycleReason"],
            "companion-retirement-pending",
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
            approved["retirement"]["sourceRetirementApprovedAt"],
            "2026-09-26T17:16:00+00:00",
        )

    def test_registration_retirement_requires_separate_approval(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
            grace_period_ends_at="2026-09-26T17:16:00+00:00",
        )
        source_approved = prototype.apply_event(
            missing,
            "source-retirement-approved",
            "2026-09-26T17:16:00+00:00",
        )

        with self.assertRaisesRegex(
            ValueError, "Registration retirement approval"
        ):
            prototype.apply_event(
                source_approved,
                "registration-retired",
                "2026-09-26T17:18:00+00:00",
            )

        registration_approved = prototype.apply_event(
            source_approved,
            "registration-retirement-approved",
            "2026-09-26T17:17:00+00:00",
        )
        self.assertEqual(
            registration_approved["retirement"][
                "companionRegistrationRetirementApprovedAt"
            ],
            "2026-09-26T17:17:00+00:00",
        )
        self.assertEqual(
            registration_approved["retirement"]["companionRegistration"][
                "reason"
            ],
            "retirement-approved",
        )

        retired = prototype.apply_event(
            registration_approved,
            "registration-retired",
            "2026-09-26T17:18:00+00:00",
        )
        self.assertEqual(
            retired["retirement"]["companionRegistration"]["status"],
            "retired",
        )

    def test_identity_retirement_requires_separate_approval(self):
        missing = prototype.apply_event(
            self.mapping,
            "source-missing",
            "2026-09-12T17:16:00+00:00",
            grace_period_ends_at="2026-09-26T17:16:00+00:00",
        )
        source_approved = prototype.apply_event(
            missing,
            "source-retirement-approved",
            "2026-09-26T17:16:00+00:00",
        )
        registration_approved = prototype.apply_event(
            source_approved,
            "registration-retirement-approved",
            "2026-09-26T17:17:00+00:00",
        )
        registration_retired = prototype.apply_event(
            registration_approved,
            "registration-retired",
            "2026-09-26T17:18:00+00:00",
        )
        package_retired = prototype.apply_event(
            registration_retired,
            "companion-package-retired",
            "2026-09-26T17:19:00+00:00",
        )

        with self.assertRaisesRegex(
            ValueError, "Agent Identity retirement approval"
        ):
            prototype.apply_event(
                package_retired,
                "identity-retired",
                "2026-09-26T17:21:00+00:00",
            )

        identity_approved = prototype.apply_event(
            package_retired,
            "identity-retirement-approved",
            "2026-09-26T17:20:00+00:00",
        )
        self.assertEqual(
            identity_approved["retirement"][
                "agentIdentityRetirementApprovedAt"
            ],
            "2026-09-26T17:20:00+00:00",
        )
        self.assertEqual(
            identity_approved["retirement"]["agentIdentity"]["reason"],
            "retirement-approved",
        )

        retired = prototype.apply_event(
            identity_approved,
            "identity-retired",
            "2026-09-26T17:21:00+00:00",
        )
        self.assertEqual(
            retired["retirement"]["agentIdentity"]["status"],
            "retired",
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
            simulation_grace_minutes=15,
            production_candidate_grace_period="P14D",
            reason="validate-disposable-delete-lifecycle",
        )

        self.assertEqual(
            configured["retirement"]["gracePeriodEndsAt"],
            "2026-09-12T17:31:00+00:00",
        )
        self.assertEqual(
            configured["retirementPolicy"],
            {
                "mode": "experiment-simulation",
                "gracePeriod": "PT15M",
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
            simulation_grace_minutes=15,
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

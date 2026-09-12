"""Validate the add-companion preparation helper with synthetic data."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import tempfile
import unittest


LAB = Path(__file__).resolve().parents[1]
HELPER = LAB / "demos" / "01-add-companion" / "prepare_demo.py"
SPEC = spec_from_file_location("prepare_demo", HELPER)
assert SPEC and SPEC.loader
prepare_demo = module_from_spec(SPEC)
SPEC.loader.exec_module(prepare_demo)


class DemoPreparationTests(unittest.TestCase):
    def setUp(self):
        self.target = "Selected GCP Agent"
        self.package_id = "fixture-package"
        self.source = (
            "projects%2ffixture%2flocations%2fus-central1"
            "%2freasoningEngines%2f123"
        )
        self.created = "2026-09-01T00:00:00Z"
        self.modified = "2026-09-02T00:00:00Z"
        self.blueprint_object_id = "00000000-0000-4000-8000-000000000001"
        self.blueprint_app_id = "00000000-0000-4000-8000-000000000002"
        self.identity_id = "00000000-0000-4000-8000-000000000003"
        self.registration_id = "fixture-registration"

    def package(self):
        definition = {
            "SourceIds": {
                "mac.agentRegistrationType": "ConnectedPlatform",
                "mac.agentRegistrationProviderType": "GoogleVertexAI",
            },
            "SourceAgentId": self.source,
            "CreatedDateTime": self.created,
            "LastModifiedDateTime": self.modified,
        }
        return {
            "id": self.package_id,
            "displayName": self.target,
            "platform": "GoogleVertexAI",
            "agentIdentityId": None,
            "elementDetails": [
                {"elements": [{"definition": json.dumps(definition)}]}
            ],
        }

    def test_select_requires_one_exact_gcp_name_match_across_pages(self):
        pages = [
            {
                "value": [
                    {
                        "id": "other",
                        "displayName": "Other",
                        "platform": "GoogleVertexAI",
                    }
                ]
            },
            {"value": [self.package()]},
        ]
        self.assertEqual(
            prepare_demo.package_values(pages, self.target),
            {"A365_DEMO_ORIGINAL_PACKAGE_ID": self.package_id},
        )

    def test_discovery_counts_packages_by_returned_platform(self):
        pages = [
            {
                "value": [
                    self.package(),
                    {"id": "aws-1", "platform": "AwsBedrock"},
                ]
            },
            {"value": [{"id": "gcp-2", "platform": "GoogleVertexAI"}]},
        ]
        self.assertEqual(
            prepare_demo.package_platform_counts(pages),
            {"GoogleVertexAI": 2, "AwsBedrock": 1},
        )

    def test_select_rejects_duplicate_display_names(self):
        with self.assertRaisesRegex(ValueError, "found 2"):
            prepare_demo.package_values(
                [{"value": [self.package(), self.package()]}], self.target
            )

    def test_prepare_extracts_exact_encoded_source_and_timestamps(self):
        values = prepare_demo.source_values(self.package(), self.target)
        self.assertEqual(values["A365_DEMO_ORIGINAL_PACKAGE_ID"], self.package_id)
        self.assertEqual(values["A365_DEMO_PROVIDER_SOURCE_AGENT_ID"], self.source)
        self.assertEqual(values["A365_DEMO_SOURCE_CREATED_AT"], self.created)
        self.assertEqual(values["A365_DEMO_SOURCE_MODIFIED_AT"], self.modified)

    def test_prepare_rejects_package_with_native_identity(self):
        package = self.package()
        package["agentIdentityId"] = self.identity_id
        with self.assertRaisesRegex(ValueError, "already has an Agent Identity"):
            prepare_demo.source_values(package, self.target)

    def test_blueprint_accepts_new_or_matching_reused_object(self):
        blueprint = {
            "id": self.blueprint_object_id,
            "appId": self.blueprint_app_id,
        }
        principal = {
            "id": "00000000-0000-4000-8000-000000000004",
            "appId": self.blueprint_app_id,
            "accountEnabled": True,
        }
        expected = {
            "A365_DEMO_BLUEPRINT_OBJECT_ID": self.blueprint_object_id,
            "A365_DEMO_BLUEPRINT_APP_ID": self.blueprint_app_id,
        }
        self.assertEqual(prepare_demo.blueprint_values(blueprint), expected)
        self.assertEqual(
            prepare_demo.blueprint_values(blueprint, self.blueprint_object_id),
            expected,
        )

    def test_blueprint_rejects_mismatched_reused_object(self):
        blueprint = {
            "id": self.blueprint_object_id,
            "appId": self.blueprint_app_id,
        }
        with self.assertRaisesRegex(ValueError, "does not match"):
            prepare_demo.blueprint_values(
                blueprint, "00000000-0000-4000-8000-000000000099"
            )

    def test_finalize_verifies_and_returns_durable_mapping(self):
        env = {
            "A365_DEMO_TARGET_NAME": self.target,
            "A365_DEMO_ORIGINAL_PACKAGE_ID": self.package_id,
            "A365_DEMO_PROVIDER_SOURCE_AGENT_ID": self.source,
            "A365_DEMO_BLUEPRINT_GROUP": "test-v2-dev",
            "A365_DEMO_BLUEPRINT_OBJECT_ID": self.blueprint_object_id,
            "A365_DEMO_BLUEPRINT_APP_ID": self.blueprint_app_id,
        }
        blueprint = {
            "id": self.blueprint_object_id,
            "appId": self.blueprint_app_id,
        }
        principal = {
            "id": "00000000-0000-4000-8000-000000000004",
            "appId": self.blueprint_app_id,
            "accountEnabled": True,
        }
        identity = {
            "id": self.identity_id,
            "agentIdentityBlueprintId": self.blueprint_app_id,
            "servicePrincipalType": "ServiceIdentity",
        }
        registration = {
            "id": self.registration_id,
            "sourceAgentId": prepare_demo.COMPANION_PREFIX + self.source,
            "originatingStore": "GoogleVertexAI",
            "agentIdentityBlueprintId": self.blueprint_app_id,
            "agentIdentityId": self.identity_id,
        }
        mapping = prepare_demo.mapping_values(
            env, blueprint, principal, identity, registration
        )
        self.assertEqual(mapping["companionRegistrationId"], self.registration_id)
        self.assertEqual(mapping["agentIdentityId"], self.identity_id)
        self.assertEqual(mapping["blueprintId"], self.blueprint_app_id)
        self.assertEqual(mapping["blueprintGroup"], "test-v2-dev")
        self.assertEqual(
            mapping["blueprintPrincipalId"],
            "00000000-0000-4000-8000-000000000004",
        )

    def test_env_updates_preserve_unrelated_values_and_avoid_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                "A365_TENANT_ID=tenant\n"
                "A365_DEMO_ORIGINAL_PACKAGE_ID=\n"
                "OTHER=value\n",
                encoding="utf-8",
            )
            prepare_demo.update_env(
                env_path,
                {
                    "A365_DEMO_ORIGINAL_PACKAGE_ID": self.package_id,
                    "A365_DEMO_PROVIDER_SOURCE_AGENT_ID": self.source,
                },
            )
            text = env_path.read_text(encoding="utf-8")
            self.assertIn("A365_TENANT_ID=tenant", text)
            self.assertIn("OTHER=value", text)
            self.assertEqual(
                text.count("A365_DEMO_ORIGINAL_PACKAGE_ID="), 1
            )
            self.assertEqual(
                text.count("A365_DEMO_PROVIDER_SOURCE_AGENT_ID="), 1
            )


if __name__ == "__main__":
    unittest.main()

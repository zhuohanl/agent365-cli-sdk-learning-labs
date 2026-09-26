"""Validate Demo 2 rename mapping state with synthetic evidence."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


LAB = Path(__file__).resolve().parents[1]
HELPER = LAB / "demos" / "02-rename-companion" / "prepare_rename.py"
SPEC = spec_from_file_location("prepare_rename", HELPER)
assert SPEC and SPEC.loader
prepare_rename = module_from_spec(SPEC)
SPEC.loader.exec_module(prepare_rename)


class RenamePreparationTests(unittest.TestCase):
    def setUp(self):
        self.old_name = "Old Agent"
        self.new_name = "Renamed Agent"
        self.source = "projects%2Ffixture%2Flocations%2Ftest%2Fagents%2F1"
        self.base = {
            "platform": "GoogleVertexAI",
            "assignmentMode": "dedicated",
            "targetName": self.old_name,
            "providerSourceAgentId": self.source,
            "packageId": "provider-package",
            "companionSourceAgentId": "companion-source",
            "companionRegistrationId": "registration",
            "companionPackageId": "companion-package",
            "blueprintObjectId": "blueprint-object",
            "blueprintId": "blueprint-app",
            "blueprintPrincipalId": "blueprint-principal",
            "agentIdentityId": "identity",
        }

    def provider_package(self):
        import json

        definition = {
            "SourceIds": {
                "mac.agentRegistrationProviderType": "GoogleVertexAI",
            },
            "SourceAgentId": self.source,
            "LastModifiedDateTime": "2026-09-13T00:00:00Z",
        }
        return {
            "id": "provider-package",
            "displayName": self.new_name,
            "platform": "GoogleVertexAI",
            "elementDetails": [
                {"elements": [{"definition": json.dumps(definition)}]}
            ],
        }

    def objects(self, name):
        blueprint_name = f"{name} - dedicated disposable Blueprint"
        companion_name = f"{name} - managed companion"
        return (
            {
                "id": "blueprint-object",
                "appId": "blueprint-app",
                "displayName": blueprint_name,
            },
            {
                "id": "blueprint-principal",
                "appId": "blueprint-app",
                "displayName": blueprint_name,
            },
            {
                "id": "identity",
                "agentIdentityBlueprintId": "blueprint-app",
                "displayName": f"{name} - managed Agent Identity",
            },
            {
                "id": "registration",
                "sourceAgentId": "companion-source",
                "agentIdentityId": "identity",
                "agentIdentityBlueprintId": "blueprint-app",
                "displayName": companion_name,
            },
            {
                "id": "companion-package",
                "agentIdentityId": "identity",
                "displayName": companion_name,
            },
        )

    def test_provider_rename_is_pending_until_all_names_follow(self):
        mapping = prepare_rename.mapping_values(
            self.base,
            self.provider_package(),
            *self.objects(self.old_name),
        )
        self.assertEqual(mapping["packageDisplayName"], self.new_name)
        self.assertEqual(mapping["nameSyncStatus"], "pending")
        self.assertNotIn("targetName", mapping)

    def test_all_verified_names_are_in_sync(self):
        mapping = prepare_rename.mapping_values(
            self.base,
            self.provider_package(),
            *self.objects(self.new_name),
        )
        self.assertEqual(mapping["nameSyncStatus"], "in-sync")
        self.assertEqual(
            mapping["companionPackageDisplayName"],
            f"{self.new_name} - managed companion",
        )

    def test_some_verified_names_are_partial(self):
        objects = list(self.objects(self.old_name))
        objects[0]["displayName"] = (
            f"{self.new_name} - dedicated disposable Blueprint"
        )
        objects[1]["displayName"] = (
            f"{self.new_name} - dedicated disposable Blueprint"
        )
        mapping = prepare_rename.mapping_values(
            self.base,
            self.provider_package(),
            *objects,
        )
        self.assertEqual(mapping["nameSyncStatus"], "partial")

    def test_shared_blueprint_names_are_not_renamed_per_agent(self):
        base = dict(self.base, assignmentMode="shared")
        objects = list(self.objects(self.new_name))
        objects[0]["displayName"] = "Support Team Blueprint"
        objects[1]["displayName"] = "Support Team Blueprint"
        mapping = prepare_rename.mapping_values(
            base,
            self.provider_package(),
            *objects,
        )
        self.assertEqual(mapping["nameSyncStatus"], "in-sync")

    def test_parser_accepts_blocked_status_flag(self):
        args = prepare_rename.parser().parse_args(["--blocked"])
        self.assertTrue(args.blocked)


if __name__ == "__main__":
    unittest.main()

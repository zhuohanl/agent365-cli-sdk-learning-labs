"""Validate the tracked REST Client companion demo without sending requests."""

from pathlib import Path
import re
import unittest


LAB = Path(__file__).resolve().parents[1]
DEMO = LAB / "trial-1-http-tests" / "companion-registration-demo.http"
RENAME_DEMO = (
    LAB / "trial-1-http-tests" / "companion-registration-demo-rename.http"
)
DELETE_DEMO = (
    LAB / "trial-1-http-tests" / "companion-registration-demo-delete.http"
)


def named_blocks(text):
    blocks = re.split(r"(?m)^###\s*$", text)
    return {
        match.group(1): block
        for block in blocks
        if (match := re.search(r"(?m)^# @name (\S+)$", block))
    }


class HttpCompanionDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DEMO.read_text(encoding="utf-8")

    def test_uses_rest_client_cached_delegated_token(self):
        self.assertIn("@readAccessToken = {{$aadV2Token scopes:", self.text)
        self.assertIn("@writeAccessToken = {{$aadV2Token new scopes:", self.text)
        self.assertIn("tenantId:{{tenantId}}", self.text)
        self.assertIn("clientId:{{clientId}}", self.text)
        self.assertNotIn("/oauth2/v2.0/devicecode", self.text)
        self.assertNotIn("/oauth2/v2.0/token", self.text)
        self.assertNotRegex(self.text, r"(?i)Authorization:\s+Bearer\s+eyJ")

    def test_read_only_route_does_not_request_write_token(self):
        blocks = named_blocks(self.text)
        write_requests = {"demoCreateFreshCompanion", "demoDeleteExistingCompanion"}

        for name, block in blocks.items():
            expected_token = "writeAccessToken" if name in write_requests else "readAccessToken"
            self.assertIn(f"Authorization: Bearer {{{{{expected_token}}}}}", block)

    def test_requests_follow_the_notebook_demo_order(self):
        names = re.findall(r"(?m)^# @name (\S+)$", self.text)
        expected = [
            "demoCurrentUser",
            "demoListPackages",
            "demoGetBlueprint",
            "demoGetBlueprintPrincipal",
            "demoGetOriginalPackageBefore",
            "demoGetAgentIdentity",
            "demoGetExistingCompanion",
            "demoCreateFreshCompanion",
            "demoGetNewCompanion",
            "demoGetOriginalPackageAfter",
            "demoDeleteExistingCompanion",
            "demoConfirmCompanionDeleted",
        ]
        self.assertEqual(names, expected)

    def test_create_uses_deterministic_companion_source(self):
        self.assertIn(
            '"sourceAgentId": "committed-fleet:companion:v1:gcp:{{providerSourceAgentId}}"',
            self.text,
        )
        self.assertIn('"agentIdentityBlueprintId": "{{blueprintAppId}}"', self.text)
        self.assertIn('"agentIdentityId": "{{agentIdentityId}}"', self.text)
        self.assertIn('"createdBy": "{{demoCurrentUser.response.body.$.id}}"', self.text)

    def test_write_requests_are_explicitly_optional(self):
        self.assertIn("DO NOT SEND THIS REQUEST during the normal customer demo.", self.text)
        self.assertIn("On timeout, 5xx, or another unexpected response, stop.", self.text)
        self.assertIn("Cleanup - OPTIONAL and irreversible", self.text)
        self.assertIn('Never use "Send All".', self.text)


class HttpCompanionRenameDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = RENAME_DEMO.read_text(encoding="utf-8")
        cls.blocks = named_blocks(cls.text)

    def test_requests_follow_capture_compare_rename_order(self):
        names = list(self.blocks)
        expected = [
            "renameCurrentUser",
            "renameListPackagesBefore",
            "renameGetPackageBefore",
            "renameGetIdentityBefore",
            "renameGetRegistrationBefore",
            "renameListPackagesAfter",
            "renameGetPackageAfter",
            "renamePatchIdentity",
            "renameGetIdentityAfter",
            "renamePatchRegistration",
            "renameGetRegistrationAfter",
            "renameListPackagesFinal",
            "renameRollbackIdentity",
            "renameRollbackRegistration",
        ]
        self.assertEqual(names, expected)

    def test_rename_is_gated_on_unchanged_source_key(self):
        stop = self.text.index("# Stop A - classify before sending any PATCH")
        first_patch = self.text.index("\nPATCH ")
        self.assertLess(stop, first_patch)
        self.assertIn("Same sourceAgentId and same provider scope", self.text)
        self.assertIn("Different sourceAgentId or provider scope", self.text)
        self.assertIn("Do not PATCH, POST, or DELETE", self.text)

    def test_rename_preserves_identity_fields(self):
        for name in (
            "renamePatchIdentity",
            "renamePatchRegistration",
            "renameRollbackIdentity",
            "renameRollbackRegistration",
        ):
            block = self.blocks[name]
            self.assertIn('"displayName":', block)
            self.assertNotIn('"sourceAgentId":', block)
            self.assertNotIn('"agentIdentityId":', block)
            self.assertNotIn('"agentIdentityBlueprintId":', block)

    def test_only_patch_requests_use_rename_write_token(self):
        write_requests = {
            "renamePatchIdentity",
            "renamePatchRegistration",
            "renameRollbackIdentity",
            "renameRollbackRegistration",
        }
        for name, block in self.blocks.items():
            expected_token = (
                "renameWriteToken" if name in write_requests else "readAccessToken"
            )
            self.assertIn(f"Authorization: Bearer {{{{{expected_token}}}}}", block)

    def test_rename_file_contains_no_literal_credentials(self):
        self.assertNotIn("/oauth2/v2.0/devicecode", self.text)
        self.assertNotIn("/oauth2/v2.0/token", self.text)
        self.assertNotRegex(self.text, r"(?i)Authorization:\s+Bearer\s+eyJ")
        self.assertIn('Never use "Send All".', self.text)


class HttpCompanionDeleteDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = DELETE_DEMO.read_text(encoding="utf-8")
        cls.blocks = named_blocks(cls.text)

    def test_requests_follow_proof_then_retirement_order(self):
        names = list(self.blocks)
        expected = [
            "deleteCurrentUser",
            "deleteListPackagesBefore",
            "deleteGetOriginalPackageBefore",
            "deleteGetRegistrationBefore",
            "deleteGetIdentityBefore",
            "deleteGetIdentityAppRoleAssignments",
            "deleteGetIdentityMemberships",
            "deleteListPackagesAfterSourceDeletion",
            "deleteGetOriginalPackageAfter",
            "deleteCompanionRegistration",
            "deleteGetRegistrationAfter",
            "deleteListPackagesAfterRegistrationDeletion",
            "deleteGetIdentityAfterRegistrationDeletion",
            "deleteAgentIdentity",
            "deleteGetIdentityAfter",
        ]
        self.assertEqual(names, expected)

    def test_delete_is_gated_and_registration_is_deleted_first(self):
        stop_a = self.text.index("# Stop A - confirm source retirement")
        registration_delete = self.text.index(
            "\nDELETE {{graphBaseUrl}}/beta/copilot/agentRegistrations/"
        )
        stop_b = self.text.index("# Stop B - separately approve Agent Identity")
        identity_delete = self.text.index(
            "\nDELETE {{graphBaseUrl}}/v1.0/servicePrincipals/"
        )
        self.assertLess(stop_a, registration_delete)
        self.assertLess(registration_delete, stop_b)
        self.assertLess(stop_b, identity_delete)

    def test_delete_tokens_are_scoped_to_destructive_requests(self):
        for name, block in self.blocks.items():
            if name == "deleteCompanionRegistration":
                token = "registrationDeleteToken"
            elif name == "deleteAgentIdentity":
                token = "identityDeleteToken"
            elif name == "deleteGetIdentityAppRoleAssignments":
                token = "dependencyReadToken"
            else:
                token = "readAccessToken"
            self.assertIn(f"Authorization: Bearer {{{{{token}}}}}", block)

    def test_delete_retains_blueprint_and_mapping_tombstone(self):
        self.assertNotRegex(
            self.text,
            r"(?m)^DELETE .*agentIdentityBlueprint",
        )
        self.assertIn("This file never deletes the platform Blueprint", self.text)
        self.assertIn("Do not erase the mapping.", self.text)
        self.assertIn("Agent Identity deletion is soft deletion", self.text)

    def test_delete_file_contains_no_literal_credentials(self):
        self.assertNotIn("/oauth2/v2.0/devicecode", self.text)
        self.assertNotIn("/oauth2/v2.0/token", self.text)
        self.assertNotRegex(self.text, r"(?i)Authorization:\s+Bearer\s+eyJ")
        self.assertIn('Never use "Send All".', self.text)


if __name__ == "__main__":
    unittest.main()

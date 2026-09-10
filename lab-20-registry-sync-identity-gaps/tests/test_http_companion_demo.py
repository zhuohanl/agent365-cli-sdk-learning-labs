"""Validate the tracked REST Client companion demo without sending requests."""

from pathlib import Path
import re
import unittest


LAB = Path(__file__).resolve().parents[1]
HTTP_ROOT = LAB
DEMO = HTTP_ROOT / "demos" / "01-add-companion" / "demo.http"
RENAME_DEMO = (
    HTTP_ROOT / "demos" / "02-rename-companion" / "demo.http"
)
DELETE_DEMO = (
    HTTP_ROOT / "demos" / "03-delete-companion" / "demo.http"
)
SOURCE_ID_STABILITY_DEMO = (
    HTTP_ROOT / "experiments" / "04-source-id-stability" / "experiment.http"
)
PACKAGE_LOOKUP_EXPERIMENT = (
    HTTP_ROOT / "experiments" / "01-package-registration-lookup" / "experiment.http"
)
PROVIDER_SOURCE_CREATE_EXPERIMENT = (
    HTTP_ROOT
    / "experiments"
    / "02-provider-source-registration-create"
    / "experiment.http"
)
COMPANION_SOURCE_CREATE_EXPERIMENT = (
    HTTP_ROOT
    / "experiments"
    / "03-companion-source-registration-create"
    / "experiment.http"
)


def named_blocks(text):
    blocks = re.split(r"(?m)^###\s*$", text)
    return {
        match.group(1): block
        for block in blocks
        if (match := re.search(r"(?m)^# @name (\S+)$", block))
    }


class HttpExperimentStructureTests(unittest.TestCase):
    def test_package_lookup_tries_both_candidate_ids(self):
        text = PACKAGE_LOOKUP_EXPERIMENT.read_text(encoding="utf-8")
        blocks = named_blocks(text)
        self.assertIn("getRegistrationUsingPackageIdNegativeProbe", blocks)
        self.assertIn("getRegistrationUsingProviderSourceIdNegativeProbe", blocks)
        self.assertIn("A365_SAMPLE_SOURCE_AGENT_ID_PATH", text)

    def test_provider_source_create_omits_identity_fields(self):
        text = PROVIDER_SOURCE_CREATE_EXPERIMENT.read_text(encoding="utf-8")
        create = named_blocks(text)["createCorrelationRegistration"]
        self.assertIn('"sourceAgentId": "{{sourceAgentId}}"', create)
        self.assertNotIn('"agentIdentityBlueprintId"', create)
        self.assertNotIn('"agentIdentityId"', create)

    def test_companion_source_create_includes_identity_fields(self):
        text = COMPANION_SOURCE_CREATE_EXPERIMENT.read_text(encoding="utf-8")
        create = named_blocks(text)["exp3CreateCompanion"]
        self.assertIn(
            '"sourceAgentId": "agent-governance:companion:v1:gcp:{{providerSourceAgentId}}"',
            create,
        )
        self.assertIn('"agentIdentityBlueprintId": "{{blueprintAppId}}"', create)
        self.assertIn('"agentIdentityId": "{{agentIdentityId}}"', create)

    def test_demo_order_keeps_delete_last(self):
        readme = (HTTP_ROOT / "http-experiments.md").read_text(encoding="utf-8")
        self.assertLess(
            readme.index("demos/01-add-companion"),
            readme.index("demos/02-rename-companion"),
        )
        self.assertLess(
            readme.index("demos/02-rename-companion"),
            readme.index("demos/03-delete-companion"),
        )


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
            '"sourceAgentId": "agent-governance:companion:v1:gcp:{{providerSourceAgentId}}"',
            self.text,
        )
        create_block = named_blocks(self.text)["demoCreateFreshCompanion"]
        self.assertNotIn("committed-fleet:companion", create_block)
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


class HttpCompanionSourceIdStabilityDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE_ID_STABILITY_DEMO.read_text(encoding="utf-8")
        cls.blocks = named_blocks(cls.text)

    def test_covers_control_rename_rematerialization_and_recreate(self):
        for heading in (
            "# Phase 0 - No-change control",
            "# Phase 1 - Rename and rename back",
            "# Phase 2 - Registry Sync rematerialization",
            "# Phase 3 - Delete and recreate the provider agent",
        ):
            self.assertIn(heading, self.text)

    def test_decisive_comparison_is_documented(self):
        self.assertIn(
            "same exact provider sourceAgentId + different Package ID",
            self.text,
        )
        self.assertIn(
            "Package identity depends on the import/connection representation",
            self.text,
        )
        self.assertIn(
            "Do not create a companion to test either candidate.",
            self.text,
        )

    def test_rename_back_requires_current_package_id(self):
        self.assertIn(
            "A365_STABILITY_AFTER_RENAME_BACK_PACKAGE_ID=<current-package-id>",
            self.text,
        )
        checkpoint = self.text.index(
            "# Before sending stabilityRenameBackPackage"
        )
        request = self.text.index("# @name stabilityRenameBackPackage")
        self.assertLess(checkpoint, request)

    def test_phase_two_gcp_read_has_token_refresh_guidance(self):
        checkpoint = self.text.index("# GCP token refresh checkpoint")
        request = self.text.index(
            "# @name stabilityPhase2GetGcpBeforeConnectionRecreate"
        )
        self.assertLess(checkpoint, request)
        self.assertIn("gcloud auth login", self.text[checkpoint:request])
        self.assertIn("gcloud auth print-access-token", self.text[checkpoint:request])
        self.assertIn("GCP_STABILITY_ACCESS_TOKEN", self.text[checkpoint:request])

    def test_destructive_requests_follow_explicit_stop_checkpoints(self):
        rename_stop = self.text.index("# Stop 1A - approve one provider display-name PATCH")
        rename_patch = self.text.index("\nPATCH {{gcpBaseUrl}}")
        connection_stop = self.text.index(
            "# Stop 2B - approve deletion of the existing experimental connection"
        )
        phase2_list = self.text.index(
            "# @name stabilityPhase2ListAfterConnectionDelete"
        )
        delete_stop = self.text.index(
            "# Stop 3A - irreversible provider deletion approval"
        )
        original_delete = self.text.index(
            "\nDELETE {{gcpBaseUrl}}/v1/projects/{{gcpProjectId}}"
        )
        create_stop = self.text.index(
            "# Stop 3D - manually create the replacement in Agent Studio"
        )
        replacement_get = self.text.index(
            "# @name stabilityGetReplacementGcpAgent"
        )

        self.assertLess(rename_stop, rename_patch)
        self.assertLess(connection_stop, phase2_list)
        self.assertLess(delete_stop, original_delete)
        self.assertLess(create_stop, replacement_get)

    def test_does_not_create_or_read_a_companion(self):
        self.assertNotIn("/agentRegistrations", self.text)
        self.assertNotIn("AgentRegistration.Read.All", self.text)
        self.assertIn(
            "Do not create a companion to test either candidate.",
            self.text,
        )

    def test_phase_two_does_not_invent_connection_endpoint(self):
        self.assertIn(
            "There is no reviewed public Graph or Agent 365 CLI operation",
            self.text,
        )
        self.assertNotRegex(
            self.text,
            r"(?m)^(POST|PATCH|DELETE) .*connected.?platform",
        )

    def test_recreate_uses_original_agent_studio_workflow(self):
        self.assertIn(
            "phase-3-portal-recreation-checklist.txt",
            self.text,
        )
        self.assertIn(
            "Google Cloud portal -> Agent Studio",
            self.text,
        )
        self.assertNotRegex(
            self.text,
            r"(?m)^POST .*reasoningEngines",
        )

    def test_every_request_states_whether_to_save_evidence(self):
        do_not_save = {
            "stabilityStartDeviceCode",
            "stabilityExchangeDeviceCode",
            "stabilityCurrentUser",
        }
        for name, block in self.blocks.items():
            marker = "DO NOT SAVE" if name in do_not_save else "SAVE REQUIRED"
            self.assertIn(marker, block, name)

    def test_file_contains_no_literal_credentials(self):
        self.assertNotRegex(self.text, r"(?i)Authorization:\s+Bearer\s+eyJ")
        self.assertIn("GCP_STABILITY_ACCESS_TOKEN", self.text)
        self.assertIn('Never use "Send All".', self.text)

    def test_uses_explicit_device_code_flow_for_graph(self):
        self.assertIn(
            "POST https://login.microsoftonline.com/{{tenantId}}/oauth2/v2.0/devicecode",
            self.text,
        )
        self.assertIn(
            "POST https://login.microsoftonline.com/{{tenantId}}/oauth2/v2.0/token",
            self.text,
        )
        self.assertIn("client_id={{clientId}}&scope={{graphReadScope}}", self.text)
        self.assertIn(
            "device_code={{stabilityStartDeviceCode.response.body.$.device_code}}",
            self.text,
        )
        self.assertIn(
            "{{stabilityExchangeDeviceCode.response.body.$.access_token}}",
            self.text,
        )
        self.assertNotIn("$aadV2Token", self.text)


if __name__ == "__main__":
    unittest.main()

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
RENAME_FINDINGS = (
    HTTP_ROOT / "demos" / "02-rename-companion" / "findings.md"
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
CLI_SETUP_ALL_EXPERIMENT = (
    HTTP_ROOT
    / "experiments"
    / "03a-cli-setup-all-companion-create"
    / "experiment.http"
)
PACKAGE_BLUEPRINT_LOOKUP_EXPERIMENT = (
    HTTP_ROOT
    / "experiments"
    / "06-package-blueprint-lookup"
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
    def test_custom_public_client_flows_do_not_use_aad_v2_token(self):
        for path in HTTP_ROOT.rglob("*.http"):
            if "evidence" in path.parts or path.name.endswith(".local.http"):
                continue
            self.assertNotIn(
                "$aadV2Token", path.read_text(encoding="utf-8"), path
            )

    def test_package_lookup_tries_both_candidate_ids(self):
        text = PACKAGE_LOOKUP_EXPERIMENT.read_text(encoding="utf-8")
        blocks = named_blocks(text)
        self.assertIn("getRegistrationUsingPackageIdNegativeProbe", blocks)
        self.assertIn("getRegistrationUsingProviderSourceIdNegativeProbe", blocks)
        self.assertIn("A365_SAMPLE_SOURCE_AGENT_ID_PATH", text)
        self.assertIn(
            "projects%252Fdemo%252Flocations%252Ftest"
            "%252FreasoningEngines%252F123",
            text,
        )
        self.assertIn(
            "the value was only single\n# encoded and was split into several URL segments",
            text,
        )
        self.assertIn(
            "[uri]::EscapeDataString((Read-Host 'Paste SourceAgentId').Trim()) "
            "| Set-Clipboard",
            text,
        )
        self.assertIn(
            "https://gchq.github.io/CyberChef/#help=URL_Encode",
            text,
        )
        self.assertIn(
            "Do not paste a real SourceAgentId",
            text,
        )

    def test_provider_source_create_omits_identity_fields(self):
        text = PROVIDER_SOURCE_CREATE_EXPERIMENT.read_text(encoding="utf-8")
        create = named_blocks(text)["createCorrelationRegistration"]
        self.assertIn('"sourceAgentId": "{{sourceAgentId}}"', create)
        self.assertNotIn('"agentIdentityBlueprintId"', create)
        self.assertNotIn('"agentIdentityId"', create)

    def test_provider_source_create_names_evidence_for_every_result(self):
        text = PROVIDER_SOURCE_CREATE_EXPERIMENT.read_text(encoding="utf-8")
        blocks = named_blocks(text)
        excluded = {"correlationDeviceCode", "correlationToken", "currentUser"}
        evidence_root = (
            "../../evidence/experiments/"
            "02-provider-source-registration-create/"
        )
        for name, block in blocks.items():
            if name in excluded:
                continue
            self.assertIn(evidence_root, block, name)
        self.assertIn(
            "Never save the device-code, token, or\n# /me responses.",
            text,
        )

    def test_every_experiment_names_evidence_for_observation_requests(self):
        cases = {
            PACKAGE_LOOKUP_EXPERIMENT: {
                "startDeviceCode",
                "exchangeDeviceCode",
            },
            PACKAGE_LOOKUP_EXPERIMENT.with_name(
                "undocumented-collection-probe.http"
            ): {
                "registrationDeviceCode",
                "registrationToken",
            },
            PROVIDER_SOURCE_CREATE_EXPERIMENT: {
                "correlationDeviceCode",
                "correlationToken",
                "currentUser",
            },
            COMPANION_SOURCE_CREATE_EXPERIMENT: {
                "exp3DeviceCode",
                "exp3Token",
                "exp3CurrentUser",
            },
            CLI_SETUP_ALL_EXPERIMENT: {
                "exp3aDeviceCode",
                "exp3aToken",
                "exp3aCurrentUser",
            },
            SOURCE_ID_STABILITY_DEMO: {
                "stabilityStartDeviceCode",
                "stabilityExchangeDeviceCode",
                "stabilityCurrentUser",
            },
            HTTP_ROOT
            / "experiments"
            / "05-enterprise-interaction-history"
            / "experiment.http": {
                "interactionHistoryStartDeviceCode",
                "interactionHistoryDelegatedToken",
                "interactionHistoryCurrentUser",
                "acquireEnterpriseInteractionsAppToken",
            },
            PACKAGE_BLUEPRINT_LOOKUP_EXPERIMENT: {
                "blueprintLookupStartDeviceCode",
                "blueprintLookupToken",
            },
        }
        for path, excluded in cases.items():
            text = path.read_text(encoding="utf-8")
            for name, block in named_blocks(text).items():
                if name in excluded:
                    continue
                self.assertTrue(
                    "evidence/experiments/" in block
                    or "SAVE REQUIRED" in block,
                    f"{path}: {name}",
                )

        stability = SOURCE_ID_STABILITY_DEMO.read_text(encoding="utf-8")
        self.assertNotIn("evidence/source-id-stability/", stability)
        self.assertIn(
            "evidence/experiments/04-source-id-stability/",
            stability,
        )

    def test_companion_source_create_includes_identity_fields(self):
        text = COMPANION_SOURCE_CREATE_EXPERIMENT.read_text(encoding="utf-8")
        create = named_blocks(text)["exp3CreateCompanion"]
        self.assertIn(
            '"sourceAgentId": "agent-governance:companion:v1:gcp:{{providerSourceAgentId}}"',
            create,
        )
        self.assertIn(
            '"agentIdentityBlueprintId": '
            '"{{exp3GetCreatedBlueprint.response.body.$.appId}}"',
            create,
        )
        self.assertIn(
            '"agentIdentityId": '
            '"{{exp3GetCreatedAgentIdentity.response.body.$.id}}"',
            create,
        )
        readback = named_blocks(text)["exp3GetCreatedCompanion"]
        self.assertIn(
            "GET {{graphBaseUrl}}/beta/copilot/agentRegistrations/"
            "{{createdRegistrationIdPath}}",
            readback,
        )
        self.assertIn(
            "[uri]::EscapeDataString((Read-Host 'Paste Registration id').Trim()) "
            "| Set-Clipboard",
            readback,
        )
        self.assertIn(
            "A365_EXP3_CREATED_REGISTRATION_ID_PATH="
            "<path-safe-created-registration-id>",
            readback,
        )
        self.assertIn(
            "Step 3.12 - Convert the returned Registration ID and read it back",
            readback,
        )

    def test_companion_source_create_discovers_package_before_preflight(self):
        text = COMPANION_SOURCE_CREATE_EXPERIMENT.read_text(encoding="utf-8")
        blocks = named_blocks(text)
        self.assertLess(
            list(blocks).index("exp3ListPackages"),
            list(blocks).index("exp3PackageBefore"),
        )
        list_block = blocks["exp3ListPackages"]
        self.assertIn(
            "../../evidence/experiments/03-companion-source-registration-create/"
            "package-list-page-1.json",
            list_block,
        )
        self.assertIn("@odata.nextLink", list_block)
        self.assertIn(
            "A365_EXP3_TARGET_NAME=<exact-selected-package-displayName>",
            list_block,
        )
        self.assertIn(
            "A365_EXP3_PACKAGE_ID=<exact-selected-package-id>",
            list_block,
        )
        package_block = blocks["exp3PackageBefore"]
        self.assertIn(
            "Before copying any value, save the complete response as:",
            package_block,
        )
        self.assertIn(
            "../../evidence/experiments/03-companion-source-registration-create/"
            "package-before-create.json",
            package_block,
        )
        for key in (
            "A365_EXP3_PROVIDER_SOURCE_AGENT_ID",
            "A365_EXP3_SOURCE_CREATED_AT",
            "A365_EXP3_SOURCE_MODIFIED_AT",
        ):
            self.assertIn(key, package_block)

    def test_companion_source_create_builds_complete_identity_chain(self):
        text = COMPANION_SOURCE_CREATE_EXPERIMENT.read_text(encoding="utf-8")
        blocks = named_blocks(text)
        names = list(blocks)
        expected_chain = [
            "exp3PackageBefore",
            "exp3CreateBlueprint",
            "exp3GetCreatedBlueprint",
            "exp3GetBlueprintPrincipal",
            "exp3CreateBlueprintPrincipal",
            "exp3VerifyBlueprintPrincipal",
            "exp3CreateAgentIdentity",
            "exp3GetCreatedAgentIdentity",
            "exp3CreateCompanion",
            "exp3GetCreatedCompanion",
            "exp3ListPackagesAfter",
            "exp3OriginalPackageAfter",
            "exp3CompanionPackageAfter",
        ]
        positions = [names.index(name) for name in expected_chain]
        self.assertEqual(positions, sorted(positions))
        self.assertIn(
            '"agentIdentityBlueprintId": '
            '"{{exp3GetCreatedBlueprint.response.body.$.appId}}"',
            blocks["exp3CreateAgentIdentity"],
        )
        self.assertIn(
            '"appId": "{{exp3GetCreatedBlueprint.response.body.$.appId}}"',
            blocks["exp3CreateBlueprintPrincipal"],
        )
        header = text[: text.index("@tenantId")]
        self.assertIn("A365_EXP3_BLUEPRINT_GROUP=", header)
        self.assertNotIn("A365_EXP3_BLUEPRINT_OBJECT_ID=", header)
        self.assertNotIn("A365_EXP3_BLUEPRINT_APP_ID=", header)
        self.assertNotIn("A365_EXP3_AGENT_IDENTITY_ID=", header)
        self.assertIn(
            "no approved reusable Blueprint is recorded",
            blocks["exp3CreateBlueprint"],
        )
        self.assertIn(
            "AgentIdentityBlueprintPrincipal.Create",
            text,
        )

    def test_companion_source_create_compares_both_packages(self):
        text = COMPANION_SOURCE_CREATE_EXPERIMENT.read_text(encoding="utf-8")
        blocks = named_blocks(text)
        package_list = blocks["exp3ListPackagesAfter"]
        self.assertIn(
            "package-list-after-create-page-1.json",
            package_list,
        )
        self.assertIn("@odata.nextLink", package_list)
        self.assertIn(
            "must not assume its Package ID equals the Registration ID",
            package_list,
        )
        self.assertIn(
            "A365_EXP3_CREATED_PACKAGE_ID=<new-companion-package-id>",
            package_list,
        )
        self.assertIn(
            "/packages/{{packageId}}",
            blocks["exp3OriginalPackageAfter"],
        )
        self.assertIn(
            "/packages/{{createdPackageId}}",
            blocks["exp3CompanionPackageAfter"],
        )

    def test_cli_setup_all_experiment_keeps_cli_source_id_opaque(self):
        text = CLI_SETUP_ALL_EXPERIMENT.read_text(encoding="utf-8")
        self.assertIn(
            "a365 setup all --agent-name $agentName --tenant-id $tenantId "
            "--authmode obo",
            text,
        )
        self.assertIn("--dry-run", text)
        self.assertIn("Do not modify the\n# sourceAgentId returned by the CLI.", text)
        self.assertNotIn(
            '"sourceAgentId": "agent-governance:companion',
            text,
        )
        self.assertNotRegex(
            text,
            r"(?im)^(POST|PATCH|DELETE)\s+\{\{graphBaseUrl\}\}",
        )

    def test_cli_setup_all_experiment_maps_original_and_cli_companion(self):
        text = CLI_SETUP_ALL_EXPERIMENT.read_text(encoding="utf-8")
        blocks = named_blocks(text)
        expected = [
            "exp3aListPackagesBefore",
            "exp3aOriginalPackageBefore",
            "exp3aGetBlueprint",
            "exp3aGetBlueprintPrincipal",
            "exp3aGetAgentIdentity",
            "exp3aGetRegistration",
            "exp3aListPackagesAfter",
            "exp3aOriginalPackageAfter",
            "exp3aCompanionPackageAfter",
        ]
        positions = [list(blocks).index(name) for name in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("A365_EXP3A_CLI_SOURCE_AGENT_ID", text)
        self.assertIn("A365_EXP3A_REGISTRATION_ID", text)
        self.assertNotIn("A365_EXP3A_REGISTRATION_ID_PATH", text)
        self.assertIn(
            "/agentRegistrations/{{registrationId}}",
            blocks["exp3aGetRegistration"],
        )
        self.assertIn(
            "Registration ID is a GUID and can be used directly",
            text,
        )
        self.assertIn("mapping.json", text)
        self.assertIn(
            "The mapping, not the CLI name or Registration sourceAgentId",
            text,
        )
        self.assertIn("a365 cleanup --agent-name $agentName", text)
        self.assertIn(
            "CLI summary labels the Blueprint application object ID",
            text,
        )
        self.assertIn(
            "Leave A365_EXP3A_BLUEPRINT_APP_ID empty until Step 3A.9",
            text,
        )
        self.assertIn(
            "different meanings even when their returned values happen to be equal",
            text,
        )
        self.assertIn(
            "`id`, `appId`, and the CLI summary's\n# Blueprint ID were equal",
            text,
        )

    def test_cli_setup_all_experiment_allows_explicit_paired_comparison(self):
        text = CLI_SETUP_ALL_EXPERIMENT.read_text(encoding="utf-8")
        self.assertIn(
            "same\n# approved disposable GCP source",
            text,
        )
        self.assertIn(
            "temporarily violates the normal\n"
            "# one-active-companion-per-scoped-source invariant",
            text,
        )
        self.assertIn(
            "Experiment 03 deterministic companion Package",
            text,
        )
        self.assertIn("comparisonControl", text)
        self.assertIn("comparison-only", text)
        self.assertIn(
            "must not\n# include the Experiment 03 control Blueprint",
            text,
        )

    def test_cli_setup_all_experiment_isolates_and_records_full_bundle(self):
        text = CLI_SETUP_ALL_EXPERIMENT.read_text(encoding="utf-8")
        self.assertIn(
            "03a-cli-setup-all-companion-create\\cli-workspace",
            text,
        )
        for effect in (
            "client secret",
            "federated identity credential",
            "managed identity",
            "Observability",
            "Power Platform",
            "appsettings.json",
        ):
            self.assertIn(effect, text)
        self.assertIn("evaluates the complete supported CLI", text)
        self.assertIn('"unexpectedResourceClasses": []', text)
        self.assertIn("operator accepts the displayed complete CLI bundle", text)

    def test_cli_experiment_validates_original_package_before_failure_classification(self):
        text = CLI_SETUP_ALL_EXPERIMENT.read_text(encoding="utf-8")
        block = named_blocks(text)["exp3aOriginalPackageAfter"]
        self.assertIn(
            "A365_EXP3A_PACKAGE_ID` exactly equals the `id` saved",
            block,
        )
        self.assertIn("If either check fails, do not send this request", block)
        self.assertIn("Title Preview", block)
        self.assertIn("inconclusive-dependency-failure", block)
        self.assertIn("invalid\n# observation", block)
        self.assertIn("Correct the local ID", block)
        self.assertIn("Do not rerun `a365 setup all`", block)

    def test_cli_experiment_is_listed_between_three_and_four(self):
        readme = (HTTP_ROOT / "docs" / "http-experiments.md").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            readme.index("03-companion-source-registration-create"),
            readme.index("03a-cli-setup-all-companion-create"),
        )
        self.assertLess(
            readme.index("03a-cli-setup-all-companion-create"),
            readme.index("04-source-id-stability"),
        )

    def test_package_blueprint_lookup_chains_response_ids(self):
        text = PACKAGE_BLUEPRINT_LOOKUP_EXPERIMENT.read_text(encoding="utf-8")
        blocks = named_blocks(text)
        self.assertIn("A365_BLUEPRINT_LOOKUP_PACKAGE_ID", text)
        self.assertIn(
            "{{blueprintLookupPackage.response.body.$.agentIdentityId}}",
            blocks["blueprintLookupAgentIdentityByObjectId"],
        )
        self.assertIn(
            "(appId='{{blueprintLookupPackage.response.body.$."
            "agentIdentityId}}')",
            blocks["blueprintLookupAgentIdentityByAppId"],
        )
        self.assertIn(
            "{{blueprintLookupAgentIdentityByObjectId.response.body.$."
            "agentIdentityBlueprintId}}",
            blocks["blueprintLookupPrincipalFromObjectId"],
        )
        self.assertIn(
            "{{blueprintLookupAgentIdentityByAppId.response.body.$."
            "agentIdentityBlueprintId}}",
            blocks["blueprintLookupPrincipalFromAppId"],
        )
        self.assertNotRegex(
            text, r"(?im)^(POST|PATCH|DELETE)\s+\{\{graphBaseUrl\}\}"
        )

    def test_demo_order_keeps_delete_last(self):
        readme = (HTTP_ROOT / "docs" / "http-experiments.md").read_text(
            encoding="utf-8"
        )
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

    def test_uses_explicit_device_code_with_configured_tenant_and_client(self):
        self.assertIn(
            "POST https://login.microsoftonline.com/{{tenantId}}"
            "/oauth2/v2.0/devicecode",
            self.text,
        )
        self.assertIn(
            "POST https://login.microsoftonline.com/{{tenantId}}"
            "/oauth2/v2.0/token",
            self.text,
        )
        self.assertIn("client_id={{clientId}}&scope={{demoScopes}}", self.text)
        self.assertIn(
            "device_code={{demoStartDeviceCode.response.body.$.device_code}}",
            self.text,
        )
        self.assertNotIn("$aadV2Token", self.text)
        self.assertNotRegex(self.text, r"(?i)Authorization:\s+Bearer\s+eyJ")

    def test_explains_manual_target_name_and_optional_pagination(self):
        self.assertIn(
            "Before Prep 1, open ../../.env and set:",
            self.text,
        )
        self.assertIn(
            "A365_DEMO_TARGET_NAME=<exact displayName of the selected GCP agent>",
            self.text,
        )
        self.assertIn(
            "If there is no @odata.nextLink, run:",
            self.text,
        )
        self.assertIn(
            "If @odata.nextLink exists, save each additional page",
            self.text,
        )

    def test_graph_requests_use_the_explicit_token_response(self):
        blocks = named_blocks(self.text)
        for name, block in blocks.items():
            if name in {"demoStartDeviceCode", "demoToken"}:
                continue
            self.assertIn(
                "Authorization: Bearer "
                "{{demoToken.response.body.$.access_token}}",
                block,
            )

    def test_requests_follow_the_notebook_demo_order(self):
        names = re.findall(r"(?m)^# @name (\S+)$", self.text)
        expected = [
            "demoStartDeviceCode",
            "demoToken",
            "demoCurrentUser",
            "demoListPackages",
            "demoGetSelectedPackage",
            "demoGetExistingBlueprint",
            "demoCreateBlueprint",
            "demoGetBlueprint",
            "demoGetBlueprintPrincipal",
            "demoCreateBlueprintPrincipal",
            "demoVerifyBlueprintPrincipal",
            "demoCreateAgentIdentity",
            "demoGetNewAgentIdentity",
            "demoCreateFreshCompanion",
            "demoGetNewCompanion",
            "demoListPackagesAfter",
            "demoGetOriginalPackageAfter",
            "demoGetCompanionPackageAfter",
        ]
        self.assertEqual(names, expected)

    def test_create_uses_deterministic_companion_source(self):
        self.assertIn(
            '"sourceAgentId": "agent-governance:companion:v1:gcp:{{providerSourceAgentId}}"',
            self.text,
        )
        create_block = named_blocks(self.text)["demoCreateFreshCompanion"]
        self.assertNotIn("committed-fleet:companion", create_block)
        self.assertIn(
            '"agentIdentityBlueprintId": "{{blueprintAppId}}"',
            create_block,
        )
        self.assertIn(
            '"agentIdentityId": '
            '"{{demoCreateAgentIdentity.response.body.$.id}}"',
            create_block,
        )
        self.assertIn('"createdBy": "{{demoCurrentUser.response.body.$.id}}"', self.text)

    def test_requires_only_target_then_generates_lab_assignment_metadata(self):
        header = self.text[: self.text.index("@tenantId")]
        self.assertIn("A365_DEMO_TARGET_NAME=", header)
        self.assertIn(
            "Do not set A365_DEMO_GROUPING_POLICY_VERSION or",
            header,
        )
        self.assertIn("experiment-only values", header)
        self.assertIn("helper generates a deterministic dedicated", header)
        for generated in (
            "A365_DEMO_ASSIGNMENT_MODE=",
            "A365_DEMO_BLUEPRINT_GROUP=",
            "A365_DEMO_GROUPING_POLICY_VERSION=",
            "A365_DEMO_APPROVAL_REFERENCE=",
            "A365_DEMO_ORIGINAL_PACKAGE_ID=",
            "A365_DEMO_PROVIDER_SOURCE_AGENT_ID=",
            "A365_DEMO_SOURCE_CREATED_AT=",
            "A365_DEMO_SOURCE_MODIFIED_AT=",
            "A365_DEMO_BLUEPRINT_APP_ID=",
            "A365_DEMO_AGENT_IDENTITY_ID=",
            "A365_DEMO_COMPANION_REGISTRATION_ID=",
        ):
            self.assertNotIn(generated, header)

    def test_identity_create_uses_blueprint_and_operator_as_sponsor(self):
        create = named_blocks(self.text)["demoCreateAgentIdentity"]
        self.assertIn(
            '"agentIdentityBlueprintId": "{{blueprintAppId}}"',
            create,
        )
        self.assertIn("{{demoCurrentUser.response.body.$.id}}", create)

    def test_blueprint_reuse_or_create_is_resolved_before_identity(self):
        reuse = self.text.index("# @name demoGetExistingBlueprint")
        blueprint_stop = self.text.index(
            "# Stop 1A - Approve creation of the dedicated assignment Blueprint"
        )
        blueprint_post = self.text.index("# @name demoCreateBlueprint")
        helper = self.text.index("prepare_demo.py blueprint")
        verified = self.text.index("# @name demoGetBlueprint")
        identity_post = self.text.index("# @name demoCreateAgentIdentity")
        self.assertLess(reuse, blueprint_stop)
        self.assertLess(blueprint_stop, blueprint_post)
        self.assertLess(blueprint_post, helper)
        self.assertLess(helper, verified)
        self.assertLess(verified, identity_post)

        create = named_blocks(self.text)["demoCreateBlueprint"]
        self.assertIn(
            '"displayName": "{{targetName}} - dedicated disposable Blueprint"',
            create,
        )
        self.assertIn('"sponsors@odata.bind":', create)
        self.assertIn('"owners@odata.bind":', create)

    def test_empty_blueprint_id_cannot_send_collection_query(self):
        reuse = named_blocks(self.text)["demoGetExistingBlueprint"]
        self.assertIn(
            "This request is disabled by default",
            reuse,
        )
        self.assertIn(
            "an empty ID can be normalized",
            reuse,
        )
        self.assertIn(
            "Blueprint collection query",
            reuse,
        )
        self.assertNotRegex(
            reuse,
            r"(?m)^GET \{\{graphBaseUrl\}\}/v1\.0/applications/",
        )
        self.assertIn(
            "# GET {{graphBaseUrl}}/v1.0/applications/"
            "{{blueprintObjectId}}/microsoft.graph.agentIdentityBlueprint",
            reuse,
        )

    def test_post_request_evidence_paths_are_adjacent_from_part_1_3(self):
        expected = [
            ("demoCreateBlueprint", "blueprint-create-response.json"),
            ("demoGetBlueprint", "blueprint.json"),
            (
                "demoGetBlueprintPrincipal",
                "blueprint-principal-before-create.json",
            ),
            (
                "demoCreateBlueprintPrincipal",
                "blueprint-principal-create-response.json",
            ),
            ("demoVerifyBlueprintPrincipal", "blueprint-principal.json"),
            ("demoCreateAgentIdentity", "agent-identity-create-response.json"),
            ("demoGetNewAgentIdentity", "agent-identity.json"),
            (
                "demoCreateFreshCompanion",
                "companion-registration-create-response.json",
            ),
            ("demoGetNewCompanion", "companion-registration.json"),
            ("demoListPackagesAfter", "package-list-after-create-page-1.json"),
            ("demoGetOriginalPackageAfter", "original-package-after-create.json"),
            (
                "demoGetCompanionPackageAfter",
                "companion-package-after-create.json",
            ),
        ]
        request_starts = [
            self.text.index(f"# @name {request_name}")
            for request_name, _ in expected
        ]
        for index, (request_name, evidence_name) in enumerate(expected):
            with self.subTest(request=request_name):
                end = (
                    request_starts[index + 1]
                    if index + 1 < len(request_starts)
                    else len(self.text)
                )
                request_and_follow_up = self.text[request_starts[index] : end]
                separator = request_and_follow_up.index("###")
                follow_up = request_and_follow_up[separator:]
                self.assertIn("# REQUIRED AFTER", follow_up)
                self.assertIn(evidence_name, follow_up)

    def test_blueprint_principal_has_read_create_verify_flow(self):
        read = self.text.index("# @name demoGetBlueprintPrincipal")
        stop = self.text.index(
            "# Stop 1B - Approve creation of the Blueprint principal"
        )
        create = self.text.index("# @name demoCreateBlueprintPrincipal")
        verify = self.text.index("# @name demoVerifyBlueprintPrincipal")
        self.assertLess(read, stop)
        self.assertLess(stop, create)
        self.assertLess(create, verify)
        self.assertIn(
            '"appId": "{{blueprintAppId}}"',
            named_blocks(self.text)["demoCreateBlueprintPrincipal"],
        )

    def test_write_requests_follow_separate_stop_gates(self):
        stop_two = self.text.index("# Stop 2 - Approve one Agent Identity creation")
        identity_post = self.text.index("# @name demoCreateAgentIdentity")
        stop_three = self.text.index(
            "# Stop 3 - Approve one companion Registration creation"
        )
        registration_post = self.text.index(
            "\nPOST {{graphBaseUrl}}/beta/copilot/agentRegistrations"
        )
        self.assertLess(stop_two, identity_post)
        self.assertLess(identity_post, stop_three)
        self.assertLess(stop_three, registration_post)
        self.assertGreaterEqual(
            self.text.count(
                "On timeout, 5xx, or another unexpected response, stop"
            ),
            4,
        )
        self.assertIn('Never use "Send All".', self.text)

    def test_finalize_persists_generated_ids(self):
        self.assertIn("prepare_demo.py registration", self.text)
        self.assertIn("prepare_demo.py finalize", self.text)
        self.assertIn("mapping.json", self.text)
        for generated in (
            "A365_DEMO_ASSIGNMENT_MODE",
            "A365_DEMO_BLUEPRINT_GROUP",
            "A365_DEMO_BLUEPRINT_OBJECT_ID",
            "A365_DEMO_BLUEPRINT_APP_ID",
            "A365_DEMO_BLUEPRINT_PRINCIPAL_ID",
            "A365_DEMO_AGENT_IDENTITY_ID",
            "A365_DEMO_COMPANION_SOURCE_AGENT_ID",
            "A365_DEMO_COMPANION_REGISTRATION_ID",
            "A365_DEMO_COMPANION_REGISTRATION_ID_PATH",
        ):
            self.assertIn(generated, self.text)

    def test_registration_readback_and_package_comparison_match_experiment_three(self):
        self.assertIn(
            "prepare_demo.py registration --registration "
            "evidence/demos/01-add-companion/"
            "companion-registration-create-response.json",
            self.text,
        )
        readback = named_blocks(self.text)["demoGetNewCompanion"]
        self.assertIn("{{companionRegistrationIdPath}}", readback)
        self.assertIn("companion-registration.json", self.text)
        self.assertNotIn("demoCreateFreshCompanion.response.body.$.id", readback)
        self.assertIn("demoListPackagesAfter", named_blocks(self.text))
        self.assertIn("demoGetOriginalPackageAfter", named_blocks(self.text))
        self.assertIn("demoGetCompanionPackageAfter", named_blocks(self.text))


class HttpCompanionRenameDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = RENAME_DEMO.read_text(encoding="utf-8")
        cls.blocks = named_blocks(cls.text)

    def test_requests_follow_capture_compare_rename_order(self):
        names = list(self.blocks)
        expected = [
            "renameStartDeviceCode",
            "renameToken",
            "renameCurrentUser",
            "renameListPackagesBefore",
            "renameGetPackageBefore",
            "renameGetBlueprintBefore",
            "renameGetBlueprintPrincipalBefore",
            "renameGetIdentityBefore",
            "renameGetRegistrationBefore",
            "renameListPackagesAfter",
            "renameGetPackageAfter",
            "renamePatchBlueprint",
            "renameGetBlueprintAfterNameSync",
            "renameGetBlueprintPrincipalAfterBlueprint",
            "renamePrincipalStartDeviceCode",
            "renamePrincipalToken",
            "renamePatchBlueprintPrincipal",
            "renameGetBlueprintPrincipalAfterNameSync",
            "renamePatchIdentity",
            "renameGetIdentityAfterNameSync",
            "renamePatchRegistration",
            "renameGetRegistrationAfterNameSync",
            "renameGetCompanionPackageAfterNameSync",
            "renameListPackagesFinal",
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
            "renamePatchBlueprint",
            "renamePatchBlueprintPrincipal",
            "renamePatchIdentity",
            "renamePatchRegistration",
        ):
            block = self.blocks[name]
            self.assertIn('"displayName":', block)
            self.assertNotIn('"sourceAgentId":', block)
            self.assertNotIn('"agentIdentityId":', block)
            self.assertNotIn('"agentIdentityBlueprintId":', block)

    def test_rename_uses_locked_assignment_and_path_safe_registration_id(self):
        self.assertIn("A365_DEMO_ASSIGNMENT_MODE=", self.text)
        self.assertIn("A365_DEMO_BLUEPRINT_GROUP=", self.text)
        self.assertIn("A365_DEMO_BLUEPRINT_OBJECT_ID=", self.text)
        self.assertIn("A365_DEMO_BLUEPRINT_PRINCIPAL_ID=", self.text)
        self.assertIn("A365_DEMO_COMPANION_SOURCE_AGENT_ID=", self.text)
        self.assertIn("A365_DEMO_COMPANION_REGISTRATION_ID_PATH=", self.text)
        for name in (
            "renameGetRegistrationBefore",
            "renamePatchRegistration",
            "renameGetRegistrationAfterNameSync",
        ):
            self.assertIn("{{companionRegistrationIdPath}}", self.blocks[name])

    def test_every_rename_observation_names_adjacent_evidence(self):
        expected = [
            (
                "renameListPackagesBefore",
                "package-list-before-provider-rename-page-1.json",
            ),
            (
                "renameGetPackageBefore",
                "original-package-before-provider-rename.json",
            ),
            ("renameGetBlueprintBefore", "blueprint-before-rename.json"),
            (
                "renameGetBlueprintPrincipalBefore",
                "blueprint-principal-before-rename.json",
            ),
            (
                "renameGetIdentityBefore",
                "agent-identity-before-rename.json",
            ),
            (
                "renameGetRegistrationBefore",
                "companion-registration-before-rename.json",
            ),
            (
                "renameListPackagesAfter",
                "package-list-after-provider-rename-page-1.json",
            ),
            (
                "renameGetPackageAfter",
                "provider-package-after-rename.json",
            ),
            (
                "renameGetBlueprintAfterNameSync",
                "blueprint-after-name-sync.json",
            ),
            (
                "renameGetBlueprintPrincipalAfterBlueprint",
                "blueprint-principal-after-name-sync.json",
            ),
            (
                "renameGetBlueprintPrincipalAfterNameSync",
                "blueprint-principal-after-name-sync.json",
            ),
            (
                "renameGetIdentityAfterNameSync",
                "agent-identity-after-name-sync.json",
            ),
            (
                "renameGetRegistrationAfterNameSync",
                "companion-registration-after-name-sync.json",
            ),
            (
                "renameGetCompanionPackageAfterNameSync",
                "companion-package-after-name-sync.json",
            ),
            (
                "renameListPackagesFinal",
                "package-list-after-name-sync-page-1.json",
            ),
        ]
        names = list(self.blocks)
        for request_name, evidence_name in expected:
            with self.subTest(request=request_name):
                start = self.text.index(f"# @name {request_name}")
                next_names = names[names.index(request_name) + 1 :]
                end = (
                    self.text.index(f"# @name {next_names[0]}")
                    if next_names
                    else len(self.text)
                )
                follow_up = self.text[start:end]
                self.assertIn("# REQUIRED AFTER", follow_up)
                self.assertIn(evidence_name, follow_up)

    def test_empty_patch_responses_use_verified_get_instead_of_fake_json(self):
        for name in (
            "renamePatchBlueprint",
            "renamePatchBlueprintPrincipal",
            "renamePatchIdentity",
            "renamePatchRegistration",
        ):
            with self.subTest(request=name):
                start = self.text.index(f"# @name {name}")
                names = list(self.blocks)
                next_names = names[names.index(name) + 1 :]
                end = (
                    self.text.index(f"# @name {next_names[0]}")
                    if next_names
                    else len(self.text)
                )
                follow_up = self.text[start:end]
                self.assertIn("# REQUIRED AFTER", follow_up)
                self.assertIn("Do not create a fake JSON", follow_up)

    def test_graph_requests_use_explicit_rename_token(self):
        for name, block in self.blocks.items():
            if name in {
                "renameStartDeviceCode",
                "renameToken",
                "renamePrincipalStartDeviceCode",
                "renamePrincipalToken",
                "renamePatchBlueprintPrincipal",
            }:
                continue
            self.assertIn(
                "Authorization: Bearer "
                "{{renameToken.response.body.$.access_token}}",
                block,
            )
        self.assertIn(
            "Authorization: Bearer "
            "{{renamePrincipalToken.response.body.$.access_token}}",
            self.blocks["renamePatchBlueprintPrincipal"],
        )

    def test_rename_records_all_display_names_and_refreshes_mapping(self):
        for field in (
            "packageDisplayName",
            "blueprintDisplayName",
            "blueprintPrincipalDisplayName",
            "agentIdentityDisplayName",
            "companionRegistrationDisplayName",
            "companionPackageDisplayName",
            "nameSyncStatus",
        ):
            self.assertIn(field, self.text)
        self.assertGreaterEqual(
            self.text.count(
                "python demos/02-rename-companion/prepare_rename.py"
            ),
            6,
        )
        self.assertIn("nameSyncStatus should be pending", self.text)
        self.assertIn("every in-scope name matches", self.text)

    def test_dedicated_blueprint_renames_but_shared_blueprint_does_not(self):
        self.assertIn("Dedicated example:", self.text)
        self.assertIn("Shared example:", self.text)
        self.assertIn("Skip Part 3 and continue to Part 4", self.text)
        blueprint = self.blocks["renamePatchBlueprint"]
        self.assertIn(
            "/applications/{{blueprintObjectId}}/"
            "microsoft.graph.agentIdentityBlueprint",
            blueprint,
        )
        self.assertIn(
            '"displayName": "{{newTargetName}} - dedicated disposable Blueprint"',
            blueprint,
        )

    def test_principal_update_is_separate_and_does_not_expand_default_scope(self):
        self.assertIn("AgentIdentityBlueprint.UpdateBranding.All", self.text)
        rename_scope_line = next(
            line for line in self.text.splitlines()
            if line.startswith("@renameScopes =")
        )
        self.assertNotIn("Application.ReadWrite.All", rename_scope_line)
        self.assertIn(
            "@principalRenameScopes = "
            "https%3A%2F%2Fgraph.microsoft.com%2FUser.Read%20"
            "https%3A%2F%2Fgraph.microsoft.com%2FApplication.ReadWrite.All",
            self.text,
        )
        principal_patch = self.blocks["renamePatchBlueprintPrincipal"]
        self.assertIn(
            '"@odata.type": '
            '"#microsoft.graph.agentIdentityBlueprintPrincipal"',
            principal_patch,
        )
        self.assertIn("Stop if sign-in asks for new tenant consent", self.text)

    def test_completed_run_findings_are_linked_without_removing_verification(self):
        findings = RENAME_FINDINGS.read_text(encoding="utf-8")
        self.assertIn("See findings.md", self.text)
        self.assertIn(
            "both displayName and\n# appDisplayName followed",
            self.text,
        )
        self.assertIn(
            "Continue to verify this on\n# every run",
            self.text,
        )
        self.assertIn(
            "No separate principal rename was required in this run",
            findings,
        )
        self.assertIn(
            "Registration display name propagated to the existing companion Package",
            findings,
        )
        self.assertIn(
            "does not establish a\ncross-provider contract",
            findings,
        )

    def test_rename_file_contains_no_literal_credentials(self):
        self.assertIn(
            "client_id={{clientId}}&scope={{renameScopes}}", self.text
        )
        self.assertIn(
            "device_code={{renameStartDeviceCode.response.body.$.device_code}}",
            self.text,
        )
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
            "deleteStartDeviceCode",
            "deleteToken",
            "deleteCurrentUser",
            "deleteListPackagesBefore",
            "deleteGetOriginalPackageBefore",
            "deleteGetBlueprintBefore",
            "deleteGetBlueprintPrincipalBefore",
            "deleteGetRegistrationBefore",
            "deleteGetIdentityBefore",
            "deleteGetIdentityAppRoleAssignments",
            "deleteGetIdentityMemberships",
            "deleteListPackagesAfterSourceDeletion",
            "deleteGetOriginalPackageAfter",
            "deleteListPackagesAtGraceEnd",
            "deleteGetOriginalPackageAtGraceEnd",
            "deleteCompanionRegistration",
            "deleteGetRegistrationAfter",
            "deleteListPackagesAfterRegistrationDeletion",
            "deleteGetIdentityAfterRegistrationDeletion",
            "deleteAgentIdentity",
            "deleteGetIdentityAfter",
            "deleteGetBlueprintBeforeCleanup",
            "deleteGetBlueprintPrincipalBeforeCleanup",
            "deleteBlueprintStartDeviceCode",
            "deleteBlueprintToken",
            "deleteDedicatedBlueprint",
            "deleteGetBlueprintAfter",
            "deleteGetBlueprintPrincipalAfter",
            "deleteListPackagesFinal",
        ]
        self.assertEqual(names, expected)

    def test_delete_is_gated_and_registration_is_deleted_first(self):
        stop_a1 = self.text.index(
            "# Stop A - approve source retirement after the grace period"
        )
        stop_a2 = self.text.index(
            "# Stop A2 - separately approve companion Registration retirement"
        )
        registration_approval = self.text.index(
            "event registration-retirement-approved"
        )
        registration_delete = self.text.index(
            "\nDELETE {{graphBaseUrl}}/beta/copilot/agentRegistrations/"
        )
        stop_b = self.text.index("# Stop B - separately approve Agent Identity")
        identity_approval = self.text.index(
            "event identity-retirement-approved"
        )
        identity_delete = self.text.index(
            "\nDELETE {{graphBaseUrl}}/v1.0/servicePrincipals/"
        )
        self.assertLess(stop_a1, stop_a2)
        self.assertLess(stop_a2, registration_approval)
        self.assertLess(registration_approval, registration_delete)
        self.assertLess(registration_delete, stop_b)
        self.assertLess(stop_b, identity_approval)
        self.assertLess(identity_approval, identity_delete)
        self.assertLess(stop_b, identity_delete)

    def test_graph_requests_use_explicit_delete_token(self):
        for name, block in self.blocks.items():
            if name in {
                "deleteStartDeviceCode",
                "deleteToken",
                "deleteBlueprintStartDeviceCode",
                "deleteBlueprintToken",
            }:
                continue
            expected_token = (
                "deleteBlueprintToken"
                if name
                in {
                    "deleteDedicatedBlueprint",
                    "deleteGetBlueprintAfter",
                    "deleteGetBlueprintPrincipalAfter",
                }
                else "deleteToken"
            )
            self.assertIn(
                "Authorization: Bearer "
                f"{{{{{expected_token}.response.body.$.access_token}}}}",
                block,
            )

    def test_dedicated_blueprint_cleanup_is_separately_gated(self):
        stop_c = self.text.index(
            "# Stop C - separately approve dedicated Blueprint group cleanup"
        )
        blueprint_delete = self.text.index(
            "\nDELETE {{graphBaseUrl}}/v1.0/applications/"
            "{{blueprintObjectId}}/microsoft.graph.agentIdentityBlueprint"
        )
        self.assertLess(stop_c, blueprint_delete)
        self.assertIn(
            "This file never deletes a shared Blueprint",
            self.text,
        )
        self.assertIn("Skip all remaining Part 5 requests for shared mode", self.text)
        self.assertNotRegex(
            self.text,
            r"(?m)^DELETE .*servicePrincipals.*blueprintPrincipal",
        )
        self.assertIn("Do not erase the mapping.", self.text)
        self.assertIn(
            "Agent Identity and Blueprint deletion are soft deletion",
            self.text,
        )
        self.assertIn(
            "AgentIdentityBlueprint.DeleteRestore.All",
            self.text,
        )

    def test_delete_flow_updates_the_mapping_after_verified_observations(self):
        self.assertIn(
            "prototype_retirement_mapping.py",
            self.text,
        )
        for event in (
            "configure-simulation-grace",
            "source-missing",
            "source-relocated",
            "source-retirement-approved",
            "registration-retirement-approved",
            "registration-retired",
            "companion-package-pending",
            "companion-package-retired",
            "identity-retirement-approved",
            "identity-retired",
            "blueprint-cleanup-started",
            "blueprint-retired",
            "blueprint-principal-retired",
        ):
            self.assertIn(f"event {event}", self.text)
        self.assertIn("lifecycleStatus=partial", self.text)
        self.assertIn("lifecycleReason=awaiting-grace-period", self.text)
        self.assertIn("blueprintCleanup.status=partial", self.text)
        self.assertIn("STOP HERE until gracePeriodEndsAt", self.text)

    def test_package_probe_classifies_observed_title_preview_424(self):
        self.assertIn("424 Failed Dependency", self.text)
        self.assertIn("Could not find Title Preview for given title", self.text)
        self.assertIn("inconclusive-dependency-failure", self.text)
        self.assertIn(
            "must not be treated as source-deletion proof",
            self.text,
        )

    def test_delete_flow_has_adjacent_private_evidence_instructions(self):
        expected = [
            (
                "deleteListPackagesBefore",
                "package-list-before-provider-deletion-page-1.json",
            ),
            (
                "deleteGetOriginalPackageBefore",
                "provider-package-before-deletion.json",
            ),
            ("deleteGetBlueprintBefore", "blueprint-before-deletion.json"),
            (
                "deleteGetBlueprintPrincipalBefore",
                "blueprint-principal-before-deletion.json",
            ),
            (
                "deleteGetRegistrationBefore",
                "companion-registration-before-deletion.json",
            ),
            (
                "deleteGetIdentityBefore",
                "agent-identity-before-deletion.json",
            ),
            (
                "deleteGetIdentityAppRoleAssignments",
                "agent-identity-app-role-assignments-before-deletion.json",
            ),
            (
                "deleteGetIdentityMemberships",
                "agent-identity-memberships-before-deletion.json",
            ),
            (
                "deleteListPackagesAfterSourceDeletion",
                "package-list-after-provider-deletion-page-1.json",
            ),
            (
                "deleteGetOriginalPackageAfter",
                "provider-package-after-deletion.json",
            ),
            (
                "deleteListPackagesAtGraceEnd",
                "package-list-at-grace-end-page-1.json",
            ),
            (
                "deleteGetOriginalPackageAtGraceEnd",
                "provider-package-at-grace-end.json",
            ),
            (
                "deleteGetRegistrationAfter",
                "companion-registration-after-deletion.json",
            ),
            (
                "deleteListPackagesAfterRegistrationDeletion",
                "package-list-after-registration-deletion-page-1.json",
            ),
            (
                "deleteGetIdentityAfterRegistrationDeletion",
                "agent-identity-after-registration-deletion.json",
            ),
            (
                "deleteGetIdentityAfter",
                "agent-identity-after-deletion.json",
            ),
            (
                "deleteGetBlueprintBeforeCleanup",
                "blueprint-before-cleanup.json",
            ),
            (
                "deleteGetBlueprintPrincipalBeforeCleanup",
                "blueprint-principal-before-cleanup.json",
            ),
            ("deleteGetBlueprintAfter", "blueprint-after-cleanup.json"),
            (
                "deleteGetBlueprintPrincipalAfter",
                "blueprint-principal-after-cleanup-01.json",
            ),
            ("deleteListPackagesFinal", "package-list-final-page-1.json"),
        ]
        request_starts = {
            name: self.text.index(f"# @name {name}\n")
            for name in self.blocks
        }
        ordered_starts = sorted(request_starts.values())
        for request_name, evidence_name in expected:
            with self.subTest(request=request_name):
                start = request_starts[request_name]
                later = [value for value in ordered_starts if value > start]
                end = min(later) if later else len(self.text)
                request_and_follow_up = self.text[start:end]
                self.assertIn("# REQUIRED AFTER", request_and_follow_up)
                self.assertIn(evidence_name, request_and_follow_up)

    def test_delete_uses_locked_assignment_and_path_safe_registration_id(self):
        self.assertIn("A365_DEMO_ASSIGNMENT_MODE=", self.text)
        self.assertIn("A365_DEMO_BLUEPRINT_GROUP=", self.text)
        self.assertIn("A365_DEMO_BLUEPRINT_OBJECT_ID=", self.text)
        self.assertIn("A365_DEMO_BLUEPRINT_PRINCIPAL_ID=", self.text)
        self.assertIn("A365_DEMO_COMPANION_SOURCE_AGENT_ID=", self.text)
        self.assertIn("A365_DEMO_COMPANION_REGISTRATION_ID_PATH=", self.text)
        for name in (
            "deleteGetRegistrationBefore",
            "deleteCompanionRegistration",
            "deleteGetRegistrationAfter",
        ):
            self.assertIn("{{companionRegistrationIdPath}}", self.blocks[name])

    def test_delete_file_contains_no_literal_credentials(self):
        self.assertIn(
            "client_id={{clientId}}&scope={{deleteScopes}}", self.text
        )
        self.assertIn(
            "device_code={{deleteStartDeviceCode.response.body.$.device_code}}",
            self.text,
        )
        self.assertIn(
            "client_id={{clientId}}&scope={{blueprintDeleteScopes}}",
            self.text,
        )
        self.assertIn(
            "device_code="
            "{{deleteBlueprintStartDeviceCode.response.body.$.device_code}}",
            self.text,
        )
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
            "phase-3-portal-recreation-checklist.json",
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

    def test_all_saved_experiment_results_are_json(self):
        for path in (HTTP_ROOT / "experiments").rglob("*.http"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?i)evidence.*\.txt")
            self.assertNotRegex(text, r"(?i)SAVE REQUIRED:[^\n]*\.txt")
            self.assertNotIn("or an ignored screenshot", text)
            self.assertNotIn("or ignored screenshots", text)

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

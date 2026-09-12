"""Tests for the Blueprint inventory report."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import tempfile
import unittest


LAB = Path(__file__).resolve().parents[1]
SCRIPT = LAB / "scripts" / "report_blueprint_inventory.py"
SPEC = spec_from_file_location("report_blueprint_inventory", SCRIPT)
assert SPEC and SPEC.loader
report = module_from_spec(SPEC)
sys.modules[SPEC.name] = report
SPEC.loader.exec_module(report)


class FakeGraph:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        response = self.responses.get(url)
        if response is None:
            raise AssertionError(f"Unexpected URL: {url}")
        return response


class BlueprintInventoryReportTests(unittest.TestCase):
    def test_paged_values_follows_every_next_link(self):
        graph = FakeGraph(
            {
                "page-1": {"value": [{"id": "one"}], "@odata.nextLink": "page-2"},
                "page-2": {"value": [{"id": "two"}]},
            }
        )

        self.assertEqual(
            report.paged_values("page-1", graph.get),
            [{"id": "one"}, {"id": "two"}],
        )
        self.assertEqual(graph.calls, ["page-1", "page-2"])

    def test_build_report_fetches_missing_details_and_deduplicates_identities(self):
        identity_one = "00000000-0000-4000-8000-000000000001"
        identity_two = "00000000-0000-4000-8000-000000000002"
        blueprint_one = "00000000-0000-4000-8000-000000000011"
        blueprint_two = "00000000-0000-4000-8000-000000000012"
        details_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/copilot/admin/catalog/packages/package-2"
        )
        identity_one_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/servicePrincipals/{identity_one}"
            "/microsoft.graph.agentIdentity"
            "?$select=id,appId,displayName,servicePrincipalType,accountEnabled,"
            "agentIdentityBlueprintId"
        )
        identity_two_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/servicePrincipals/{identity_two}"
            "/microsoft.graph.agentIdentity"
            "?$select=id,appId,displayName,servicePrincipalType,accountEnabled,"
            "agentIdentityBlueprintId"
        )
        blueprint_one_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/servicePrincipals"
            f"(appId='{blueprint_one}')"
            "/microsoft.graph.agentIdentityBlueprintPrincipal"
            "?$select=id,appId,displayName"
        )
        blueprint_two_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/servicePrincipals"
            f"(appId='{blueprint_two}')"
            "/microsoft.graph.agentIdentityBlueprintPrincipal"
            "?$select=id,appId,displayName"
        )
        graph = FakeGraph(
            {
                details_url: {
                    "id": "package-2",
                    "platform": "CopilotStudio",
                    "agentIdentityId": identity_one,
                },
                identity_one_url: {
                    "id": identity_one,
                    "agentIdentityBlueprintId": blueprint_one,
                },
                identity_two_url: {
                    "id": identity_two,
                    "agentIdentityBlueprintId": blueprint_two,
                },
                blueprint_one_url: {
                    "id": "principal-1",
                    "appId": blueprint_one,
                    "displayName": "Copilot Studio Blueprint",
                },
                blueprint_two_url: {
                    "id": "principal-2",
                    "appId": blueprint_two,
                    "displayName": "Foundry Blueprint",
                },
            }
        )
        packages = [
            {
                "id": "package-1",
                "platform": "CopilotStudio",
                "agentIdentityId": identity_one,
            },
            {"id": "package-2", "platform": "ignored-list-value"},
            {
                "id": "package-3",
                "platform": "CopilotStudio",
                "agentIdentityId": None,
            },
            {
                "id": "package-4",
                "platform": "MicrosoftFoundry",
                "agentIdentityId": identity_two,
            },
        ]

        (
            rows,
            enriched,
            unique_identities,
            without_identity,
            resolution_failures,
        ) = report.build_report(packages, graph.get)

        self.assertEqual(unique_identities, 2)
        self.assertEqual(without_identity, 1)
        self.assertEqual(resolution_failures, 0)
        self.assertEqual(
            rows,
            [
                report.ReportRow(
                    platform="CopilotStudio",
                    blueprint_name="Copilot Studio Blueprint",
                    blueprint_id=blueprint_one,
                    identity_count=1,
                ),
                report.ReportRow(
                    platform="MicrosoftFoundry",
                    blueprint_name="Foundry Blueprint",
                    blueprint_id=blueprint_two,
                    identity_count=1,
                ),
            ],
        )
        self.assertEqual(graph.calls.count(identity_one_url), 1)
        self.assertEqual(graph.calls.count(blueprint_one_url), 1)
        self.assertEqual(enriched[0]["resolvedAgentIdentity"]["id"], identity_one)
        self.assertEqual(
            enriched[0]["resolvedBlueprint"]["displayName"],
            "Copilot Studio Blueprint",
        )
        self.assertEqual(enriched[2]["resolvedAgentIdentity"], None)
        self.assertEqual(enriched[2]["resolvedBlueprint"], None)

    def test_same_identity_is_counted_once_per_platform_and_blueprint(self):
        identity_id = "00000000-0000-4000-8000-000000000001"
        blueprint_id = "00000000-0000-4000-8000-000000000011"
        identity_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/servicePrincipals/{identity_id}"
            "/microsoft.graph.agentIdentity"
            "?$select=id,appId,displayName,servicePrincipalType,accountEnabled,"
            "agentIdentityBlueprintId"
        )
        blueprint_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/servicePrincipals"
            f"(appId='{blueprint_id}')"
            "/microsoft.graph.agentIdentityBlueprintPrincipal"
            "?$select=id,appId,displayName"
        )
        graph = FakeGraph(
            {
                identity_url: {
                    "id": identity_id,
                    "agentIdentityBlueprintId": blueprint_id,
                },
                blueprint_url: {
                    "id": "principal",
                    "appId": blueprint_id,
                    "displayName": None,
                },
            }
        )

        (
            rows,
            enriched,
            unique_identities,
            without_identity,
            resolution_failures,
        ) = report.build_report(
            [
                {
                    "id": "one",
                    "platform": "CopilotStudio",
                    "agentIdentityId": identity_id,
                },
                {
                    "id": "two",
                    "platform": "CopilotStudio",
                    "agentIdentityId": identity_id,
                },
            ],
            graph.get,
        )

        self.assertEqual(
            rows,
            [
                report.ReportRow(
                    platform="CopilotStudio",
                    blueprint_name="<not available>",
                    blueprint_id=blueprint_id,
                    identity_count=1,
                )
            ],
        )
        self.assertEqual(unique_identities, 1)
        self.assertEqual(without_identity, 0)
        self.assertEqual(resolution_failures, 0)
        self.assertEqual(len(enriched), 2)

    def test_missing_agent_identity_is_recorded_without_aborting_other_packages(self):
        missing_identity = "a6d18df4-bc51-4faa-b008-d186fa28a8b3"
        valid_identity = "00000000-0000-4000-8000-000000000002"
        blueprint_id = "00000000-0000-4000-8000-000000000012"
        missing_identity_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/servicePrincipals/{missing_identity}"
            "/microsoft.graph.agentIdentity"
            "?$select=id,appId,displayName,servicePrincipalType,accountEnabled,"
            "agentIdentityBlueprintId"
        )
        missing_identity_app_id_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/servicePrincipals"
            f"(appId='{missing_identity}')"
            "/microsoft.graph.agentIdentity"
            "?$select=id,appId,displayName,servicePrincipalType,accountEnabled,"
            "agentIdentityBlueprintId"
        )
        valid_identity_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/servicePrincipals/{valid_identity}"
            "/microsoft.graph.agentIdentity"
            "?$select=id,appId,displayName,servicePrincipalType,accountEnabled,"
            "agentIdentityBlueprintId"
        )
        blueprint_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/servicePrincipals"
            f"(appId='{blueprint_id}')"
            "/microsoft.graph.agentIdentityBlueprintPrincipal"
            "?$select=id,appId,displayName"
        )

        class MissingIdentityGraph(FakeGraph):
            def get(self, url):
                if url in {missing_identity_url, missing_identity_app_id_url}:
                    raise report.GraphRequestError(
                        404,
                        "Request_ResourceNotFound",
                        f"Resource '{missing_identity}' does not exist",
                        "fixture-request-id",
                    )
                return super().get(url)

        graph = MissingIdentityGraph(
            {
                valid_identity_url: {
                    "id": valid_identity,
                    "agentIdentityBlueprintId": blueprint_id,
                },
                blueprint_url: {
                    "id": "principal",
                    "appId": blueprint_id,
                    "displayName": "Valid Blueprint",
                },
            }
        )

        (
            rows,
            enriched,
            unique_identities,
            without_identity,
            resolution_failures,
        ) = report.build_report(
            [
                {
                    "id": "stale-package",
                    "platform": "CopilotStudio",
                    "agentIdentityId": missing_identity,
                },
                {
                    "id": "valid-package",
                    "platform": "MicrosoftFoundry",
                    "agentIdentityId": valid_identity,
                },
            ],
            graph.get,
        )

        self.assertEqual(unique_identities, 1)
        self.assertEqual(without_identity, 0)
        self.assertEqual(resolution_failures, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            enriched[0]["identityResolution"],
            {
                "status": "notFound",
                "errorCode": "Request_ResourceNotFound",
                "message": (
                    "The Package references an Agent Identity that Graph "
                    "could not resolve."
                ),
            },
        )
        self.assertEqual(enriched[0]["resolvedAgentIdentity"], None)
        self.assertEqual(enriched[0]["resolvedBlueprint"], None)
        self.assertEqual(
            enriched[1]["identityResolution"],
            {"status": "resolved", "lookupKey": "objectId"},
        )

    def test_agent_identity_falls_back_to_app_id_lookup(self):
        package_identity_id = "00000000-0000-4000-8000-000000000021"
        identity_object_id = "00000000-0000-4000-8000-000000000022"
        blueprint_id = "00000000-0000-4000-8000-000000000023"
        object_id_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/servicePrincipals/"
            f"{package_identity_id}/microsoft.graph.agentIdentity"
            "?$select=id,appId,displayName,servicePrincipalType,accountEnabled,"
            "agentIdentityBlueprintId"
        )
        app_id_url = (
            f"{report.GRAPH_BASE_URL}/v1.0/servicePrincipals"
            f"(appId='{package_identity_id}')"
            "/microsoft.graph.agentIdentity"
            "?$select=id,appId,displayName,servicePrincipalType,accountEnabled,"
            "agentIdentityBlueprintId"
        )

        class AppIdFallbackGraph(FakeGraph):
            def get(self, url):
                if url == object_id_url:
                    raise report.GraphRequestError(
                        404,
                        "Request_ResourceNotFound",
                        "Object ID lookup failed",
                        "fixture-request-id",
                    )
                return super().get(url)

        graph = AppIdFallbackGraph(
            {
                app_id_url: {
                    "id": identity_object_id,
                    "appId": package_identity_id,
                    "agentIdentityBlueprintId": blueprint_id,
                }
            }
        )

        identity, lookup_key = report.read_agent_identity(
            package_identity_id, graph.get
        )

        self.assertEqual(identity["id"], identity_object_id)
        self.assertEqual(lookup_key, "appId")
        self.assertEqual(graph.calls, [app_id_url])

    def test_markdown_table_escapes_cell_delimiters(self):
        table = report.markdown_table(
            [
                report.ReportRow(
                    "Platform|One",
                    "Blueprint|One",
                    "blueprint|id",
                    3,
                )
            ]
        )
        self.assertIn(
            "| Platform\\|One | Blueprint\\|One | blueprint\\|id | 3 |",
            table,
        )

    def test_enriched_package_output_uses_package_list_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "enriched.json"
            report.write_enriched_packages(
                output,
                [
                    {
                        "id": "package-1",
                        "resolvedAgentIdentity": {"id": "identity-1"},
                        "resolvedBlueprint": {"appId": "blueprint-1"},
                    }
                ],
                "https://graph.microsoft.com/v1.0/copilot/admin/catalog/packages",
            )

            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["value"][0]["id"], "package-1")
            self.assertEqual(
                payload["value"][0]["resolvedBlueprint"]["appId"],
                "blueprint-1",
            )


if __name__ == "__main__":
    unittest.main()

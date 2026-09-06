"""Execute the inline notebook against synthetic HTTP responses, never a tenant."""

import ast
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock
from urllib.parse import quote
from uuid import UUID

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError


LAB = Path(__file__).resolve().parents[1]
NOTEBOOK = LAB / "trial-2-jupyter-notebook" / "registry_sync_identity_walkthrough.ipynb"

FIXTURE = r"""
import json, getpass, requests, msal
def uid(n):
    return f"00000000-0000-4000-8000-{n:012d}"
TENANT, CLIENT, OPERATOR, SPONSOR = [uid(n) for n in range(1, 5)]
BP, APP, PRINCIPAL, IDENTITY = [uid(n) for n in range(101, 105)]
ORIGINAL, COMPANION = "fixture-original", "fixture-companion"
SOURCE = "projects/demo-project/locations/us-central1/reasoningEngines/test%2Fv2"
API = "/v1.0/copilot/admin/catalog/packages"
REG = "/beta/copilot/agentRegistrations"
BP_ROOT = "/v1.0/applications"
SP_ROOT = "/v1.0/servicePrincipals"
BP_TYPE = "microsoft.graph.agentIdentityBlueprint"
PR_TYPE = "microsoft.graph.agentIdentityBlueprintPrincipal"
ID_TYPE = "microsoft.graph.agentIdentity"
def _fixture_detail(identifier, connected=True, identity=None):
    source_ids = {
        "ConnectionId": "fixture-connection", "mac.projectId": "demo-project",
        "mac.region": "us-central1", "mac.agentRegistrationType": "ConnectedPlatform",
        "mac.agentRegistrationProviderType": "GoogleVertexAI",
    } if connected else {}
    return {"id": identifier, "displayName": "Test V2", "platform": "GoogleVertexAI",
        "agentIdentityId": identity, "elementDetails": [{"elements": [{"definition": json.dumps({
            "SourceAgentId": SOURCE, "SourceIds": source_ids,
            "CreatedDateTime": "2026-09-01T00:00:00Z",
            "LastModifiedDateTime": "2026-09-02T00:00:00+00:00",
        })}]}]}
_packages = {ORIGINAL: _fixture_detail(ORIGINAL)}
for identifier, platform in (
    ("fixture-unconfirmed", "ExampleUnconfirmed"),
    ("fixture-denied", "ExampleDenied"),
    ("fixture-unavailable", "ExampleUnavailable"),
    ("fixture-null", "ExampleUnconfirmed"),
    ("fixture-bad-elements", "ExampleUnconfirmed"),
    ("fixture-missing-platform", None),
):
    _packages[identifier] = {"id": identifier, "displayName": "Other agent", "platform": platform}
_packages["fixture-unconfirmed"]["elementDetails"] = [{"elements": [{"definition": "not-json"}]}]
_packages["fixture-null"]["elementDetails"] = None
_packages["fixture-bad-elements"]["elementDetails"] = [{"elements": [None]}]
_objects = {}
_calls = []
_failure = None
_blueprint_count = 0
if not FIRST_COMPANION:
    _objects[REG + "/" + COMPANION] = {
        "id": COMPANION, "sourceAgentId": SOURCE, "originatingStore": "GoogleVertexAI",
        "ownerIds": [OPERATOR],
    }
    _packages[COMPANION] = _fixture_detail(COMPANION, connected=False)
if not WRITE:
    _objects[BP_ROOT + "/" + BP + "/" + BP_TYPE] = {"id": BP, "appId": APP}
    _objects[SP_ROOT + "/" + PRINCIPAL + "/" + PR_TYPE] = {"id": PRINCIPAL, "appId": APP, "accountEnabled": True}
    _objects[SP_ROOT + "/" + IDENTITY + "/" + ID_TYPE] = {
        "id": IDENTITY, "agentIdentityBlueprintId": APP, "servicePrincipalType": "ServiceIdentity",
    }
_initial_package_count = len(_packages)
_prompts = []
def fake_prompt(prompt):
    _prompts.append(prompt)
    if "Type APPLY" in prompt:
        return "cancel" if DENY_CONFIRMATION == "DELETE" and "DELETE" in prompt else "APPLY"
    if "Type FIRST" in prompt: return "cancel" if DENY_CONFIRMATION == "FIRST" else "FIRST"
    if "tenant ID" in prompt: return TENANT
    if "public-client ID" in prompt: return CLIENT
    if "sponsor user" in prompt: return SPONSOR
    if "Blueprint object ID" in prompt: return "" if WRITE else BP
    if "Agent Identity ID" in prompt: return "" if WRITE else IDENTITY
    if "Registration ID" in prompt: return "" if FIRST_COMPANION else COMPANION
    raise AssertionError("Unexpected fixture prompt.")
getpass.getpass = fake_prompt
_auth_calls = []
_silent_calls = []
_interactive_options = []
_accounts = []
_token_cache = []
_auth_failure = False
class FakeApplication:
    def __init__(self, client_id, *, authority, exclude_scopes):
        assert client_id == CLIENT
        assert authority == "https://login.microsoftonline.com/" + TENANT
        assert exclude_scopes == ["offline_access"]

    def get_accounts(self, username=None):
        return [account for account in _accounts if not username or account["username"] == username]

    def acquire_token_silent(self, scopes, account):
        _silent_calls.append(scopes)
        if _auth_failure:
            return None
        requested = set(scopes)
        for granted, result in reversed(_token_cache):
            if requested <= granted and account in _accounts:
                return {
                    "access_token": result["access_token"],
                    "expires_in": 3600,
                }
        return None

    def acquire_token_interactive(self, *, scopes, timeout, prompt=None, login_hint=None):
        assert timeout == 300
        assert scopes and all(scope.startswith("https://graph.microsoft.com/") for scope in scopes)
        _auth_calls.append(scopes)
        _interactive_options.append((prompt, login_hint))
        if login_hint:
            assert prompt is None
            assert login_hint == "operator@example.test"
        else:
            assert prompt == msal.Prompt.SELECT_ACCOUNT
        if _auth_failure:
            return {"error": "access_denied", "error_description": "fixture-sensitive-error"}
        account = {"username": "operator@example.test", "local_account_id": OPERATOR}
        _accounts[:] = [account]
        result = {
            "access_token": "fixture-access-token",
            "scope": " ".join(scopes),
            "expires_on": "4102444800",
            "id_token_claims": {"oid": OPERATOR, "preferred_username": account["username"]},
        }
        _token_cache.append((set(scopes), result))
        return dict(result)
msal.PublicClientApplication = FakeApplication
def reply(status, value=None):
    response = requests.Response()
    response.status_code = status
    response._content = b"" if value is None else json.dumps(value).encode()
    return response
def fake_request(method, url, **kwargs):
    global _blueprint_count
    from urllib.parse import urlsplit
    assert urlsplit(url).hostname == "graph.microsoft.com"
    assert kwargs["allow_redirects"] is False
    assert kwargs["headers"]["Author" + "ization"] == "Bearer" + " " + "fixture-access-token"
    path, body = urlsplit(url).path, kwargs.get("json")
    _calls.append((method, path, body))
    if _failure == method: return reply(403, {"error": "fixture-sensitive-error"})
    if method == "GET":
        if path == "/v1.0/me": return reply(200, {"id": OPERATOR})
        if path == API:
            values = [{k: p[k] for k in ("id", "displayName", "platform")} for p in _packages.values()]
            if urlsplit(url).query == "page=2": return reply(200, {"value": values[2:]})
            return reply(200, {"value": values[:2], "@odata.nextLink": "https://graph.microsoft.com" + API + "?page=2"})
        if path == API + "/fixture-denied": return reply(403, {"error": "fixture-sensitive-error"})
        if path == API + "/fixture-unavailable": return reply(404)
        if path == REG + "/" + COMPANION and REGISTRATION_FAILURE:
            return reply(REGISTRATION_FAILURE, {"error": "fixture-sensitive-error"})
        if path.startswith(API + "/"): value = _packages.get(path.rsplit("/", 1)[1])
        elif "(appId=" in path:
            app_id = path.split("'")[1]
            value = next((value for key, value in _objects.items() if key.endswith("/" + PR_TYPE) and value.get("appId") == app_id), None)
        else: value = _objects.get(path)
        return reply(404 if value is None else 200, value)
    if method == "POST":
        if path == BP_ROOT + "/" + BP_TYPE:
            identifier, app_id = uid(101 + 100 * _blueprint_count), uid(102 + 100 * _blueprint_count)
            _blueprint_count += 1
            target, value = BP_ROOT + "/" + identifier + "/" + BP_TYPE, {"id": identifier, "appId": app_id}
        elif path == SP_ROOT + "/" + PR_TYPE:
            identifier = uid(int(body["appId"].rsplit("-", 1)[1]) + 1)
            target, value = SP_ROOT + "/" + identifier + "/" + PR_TYPE, {"id": identifier, "appId": body["appId"], "accountEnabled": True}
        elif path == SP_ROOT + "/" + ID_TYPE:
            target, value = SP_ROOT + "/" + IDENTITY + "/" + ID_TYPE, {"id": IDENTITY, "agentIdentityBlueprintId": body["agentIdentityBlueprintId"], "servicePrincipalType": "ServiceIdentity"}
        elif path == REG:
            assert body["sourceAgentId"] == SOURCE
            assert body["sourceLastModifiedDateTime"] == "2026-09-02T00:00:00+00:00"
            assert "managedByAppId" not in body
            target, value = REG + "/" + COMPANION, {"id": COMPANION, **body}
            _packages[COMPANION] = _fixture_detail(COMPANION, connected=False, identity=IDENTITY)
        else: raise AssertionError("Unexpected fixture POST.")
        _objects[target] = value
        return reply(201, value)
    if method == "PATCH":
        assert path == REG + "/" + COMPANION
        _objects[path].update(body)
        _packages[COMPANION]["agentIdentityId"] = body["agentIdentityId"]
        return reply(200)
    if method == "DELETE":
        if path == REG + "/" + COMPANION:
            _objects.pop(path)
            _packages.pop(COMPANION)
        else:
            assert path == BP_ROOT + "/" + uid(201) + "/" + BP_TYPE
            _objects.pop(path)
            _objects.pop(SP_ROOT + "/" + uid(203) + "/" + PR_TYPE)
        return reply(204)
    raise AssertionError("Unexpected HTTP call.")
requests.request = fake_request
requests.Session.request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Real network disabled."))
"""


class NotebookTests(unittest.TestCase):
    def test_template_is_clean_and_self_contained(self):
        notebook = nbformat.read(NOTEBOOK, as_version=4)
        nbformat.validate(notebook)
        cells = {cell.id: cell for cell in notebook.cells}
        cell_ids = [cell.id for cell in notebook.cells]
        self.assertLess(cell_ids.index("configuration-variables"), cell_ids.index("configuration-switches"))
        self.assertLess(cell_ids.index("configuration-switches"), cell_ids.index("setup-code"))

        def assigned_names(cell_id):
            return {
                target.id
                for node in ast.parse(cells[cell_id].source).body
                if isinstance(node, ast.Assign)
                for target in node.targets
                if isinstance(target, ast.Name)
            }

        variable_names = {
            "TARGET_NAME", "PLATFORM", "REGISTRY_SYNC_PLATFORMS", "BLUEPRINT_GROUPS",
            "SELECTED_BLUEPRINT_GROUP", "GRAPH", "PACKAGES", "REGISTRATIONS",
        }
        switch_names = {
            "RUN_WRITES", "CONFIRM_EACH_WRITE", "GROUPS_APPROVED", "AGENT_GROUP_APPROVED",
            "CREATE_BLUEPRINT", "CREATE_PRINCIPAL", "CREATE_IDENTITY", "CREATE_COMPANION",
            "DELETE_OBJECT", "CONFIRMED_NO_DEPENDENTS", "CLEANUP_PLATFORM", "CLEANUP_GROUP",
        }
        self.assertEqual(assigned_names("configuration-variables"), variable_names)
        self.assertEqual(assigned_names("configuration-switches"), switch_names)
        self.assertFalse((variable_names | switch_names) & assigned_names("setup-code"))

        headings = []
        for cell in notebook.cells:
            if cell.cell_type == "code":
                self.assertIsNone(cell.execution_count)
                self.assertEqual(cell.outputs, [])
                ast.parse(cell.source)
                self.assertNotIn("registry_sync_workflow", cell.source)
                self.assertNotIn("Workflow(", cell.source)
                self.assertNotIn("initiate_device_flow", cell.source)
                self.assertNotIn("acquire_token_by_device_flow", cell.source)
                self.assertNotIn("tkinter", cell.source)
            else:
                headings.extend(re.findall(r"(?m)^## (.+)$", cell.source))
        self.assertEqual(headings, [
            "Prerequisites", "Prep - configure the run",
            "Part 1 - Prepare the Blueprint group",
            "Part 2 - Resolve the selected agent and Agent Identity",
            "Part 3 - Test the Agent Registration boundary", "Cleanup and limits",
        ])
        self.assertFalse((LAB / "registry_sync_workflow.py").exists())

    def test_read_only_reuse_path(self):
        self.execute(write=False)

    def test_cached_placeholder_sponsor_is_reprompted(self):
        sponsor_id = "00000000-0000-4000-8000-000000000004"
        pending = {"method": "POST", "record": "synthetic-pending"}
        context = self.sponsor_context({"sponsor_id": "tbc", "pending_write": pending.copy()}, sponsor_id)
        output = self.run_sponsor_cell(context)
        self.assertEqual(context["state"]["sponsor_id"], sponsor_id)
        self.assertIn("Previously saved sponsor ID", output)
        self.assertIn("'sponsor_saved_locally': True", output)
        self.assertNotIn(sponsor_id, output)
        context["getpass"].assert_called_once()
        context["save_state"].assert_called_once()
        self.assertEqual(context["state"]["pending_write"], pending)

    def test_valid_saved_sponsor_reports_success_without_prompting(self):
        sponsor_id = "00000000-0000-4000-8000-000000000004"
        context = self.sponsor_context({"sponsor_id": sponsor_id}, "unused")
        output = self.run_sponsor_cell(context)
        self.assertNotIn("invalid", output)
        self.assertIn("'sponsor_saved_locally': True", output)
        self.assertNotIn(sponsor_id, output)
        context["getpass"].assert_not_called()
        context["save_state"].assert_called_once()

    def test_new_sponsor_defaults_to_operator_without_prompting(self):
        context = self.sponsor_context({}, "unused")
        self.run_sponsor_cell(context)
        self.assertEqual(context["state"]["sponsor_id"], context["state"]["operator_id"])
        context["getpass"].assert_not_called()
        context["save_state"].assert_called_once()

    def test_invalid_saved_sponsor_replacement_is_rejected_before_saving(self):
        context = self.sponsor_context({"sponsor_id": "tbc"}, "tbc")
        with self.assertRaisesRegex(ValueError, "Object ID"):
            self.run_sponsor_cell(context)
        self.assertEqual(context["state"]["sponsor_id"], "tbc")
        context["save_state"].assert_not_called()

    def test_sponsor_bindings_reject_stale_placeholder_before_post(self):
        notebook = nbformat.read(NOTEBOOK, as_version=4)
        checked = 0
        for cell in notebook.cells:
            if cell.id not in ("part-1-blueprints-code", "part-2-identity-code"):
                continue
            for node in ast.walk(ast.parse(cell.source)):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == "request_graph" and len(node.args) > 2
                        and isinstance(node.args[2], ast.Dict)
                        and any(isinstance(key, ast.Constant) and key.value == "sponsors@odata.bind" for key in node.args[2].keys)):
                    continue
                with self.subTest(cell=cell.id):
                    checked += 1
                    request = Mock()
                    namespace = {
                        "request_graph": request, "UUID": UUID, "quote": quote,
                        "GRAPH": "https://graph.microsoft.com",
                        "TARGET_NAME": "Test V2",
                        "platform": "GoogleVertexAI", "group": "test-v2-dev",
                        "bp_record": "synthetic-blueprint",
                        "state": {"sponsor_id": "tbc", "operator_id": "00000000-0000-4000-8000-000000000003"},
                        "blueprint": {"appId": "00000000-0000-4000-8000-000000000102"},
                    }
                    with self.assertRaises(ValueError):
                        eval(compile(ast.Expression(node), "<sponsor-binding>", "eval"), namespace)
                    request.assert_not_called()
        self.assertEqual(checked, 2)

    @staticmethod
    def sponsor_context(state, entered_value):
        state.setdefault("operator_id", "00000000-0000-4000-8000-000000000003")
        return {
            "state": state, "packages_by_platform": {"GoogleVertexAI": []},
            "REGISTRY_SYNC_PLATFORMS": {"GoogleVertexAI"},
            "BLUEPRINT_GROUPS": {"GoogleVertexAI": ["test-v2-dev"]},
            "GROUPS_APPROVED": False,
            "getpass": Mock(return_value=entered_value), "save_state": Mock(),
        }

    @staticmethod
    def run_sponsor_cell(context):
        notebook = nbformat.read(NOTEBOOK, as_version=4)
        source = next(cell.source for cell in notebook.cells if cell.id == "part-1-groups-code")
        with redirect_stdout(StringIO()) as output:
            exec(compile(source, "<part-1-groups-code>", "exec"), context)
        return output.getvalue()

    def test_create_identities_and_patch_existing_companion(self):
        self.execute(write=True)

    def test_per_write_confirmation_can_be_enabled(self):
        self.execute(write=True, confirm_writes=True)

    def test_explicit_first_companion_create(self):
        self.execute(write=True, first_companion=True)

    def test_unknown_write_cannot_be_retried(self):
        self.execute(write=True, unknown_write=True)

    def test_cleanup_only_deletes_the_new_companion(self):
        self.execute(write=True, first_companion=True, cleanup=True)

    def test_required_confirmations_cannot_be_skipped(self):
        for confirmation in ("FIRST", "DELETE"):
            with self.subTest(confirmation=confirmation):
                self.execute(write=True, first_companion=True, cleanup=confirmation == "DELETE", deny_confirmation=confirmation)

    def test_browser_signin_failure_clears_the_previous_token(self):
        self.execute(write=False, auth_failure=True)

    def test_multiple_groups_use_the_manually_selected_parent(self):
        self.execute(write=True, multiple_groups=True, selected_group="support-dev", replay_groups=True)

    def test_legacy_binding_is_reused_without_creating_a_replacement(self):
        self.execute(write=False, legacy=True)

    def test_unavailable_cached_principal_blocks_identity_creation(self):
        self.execute(write=False, legacy=True, missing_principal=True)

    def test_cleanup_can_retire_another_new_blueprint_group(self):
        self.execute(write=True, multiple_groups=True, cleanup_blueprint=True)

    def test_failed_registration_reads_never_fall_through_to_post(self):
        for status in (403, 404):
            with self.subTest(status=status):
                self.execute(write=True, registration_failure=status)

    def execute(
        self, *, write, first_companion=False, unknown_write=False, cleanup=False,
        auth_failure=False, multiple_groups=False, selected_group="test-v2-dev",
        legacy=False, missing_principal=False, cleanup_blueprint=False,
        registration_failure=0, replay_groups=False, confirm_writes=False,
        deny_confirmation=None,
    ):
        notebook = nbformat.read(NOTEBOOK, as_version=4)
        original_bytes = NOTEBOOK.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            for cell in notebook.cells:
                if cell.cell_type != "code":
                    continue
                cell.source = cell.source.replace(
                    "PRIVATE = LAB_ROOT / 'evidence' / 'trial-2-jupyter-notebook'",
                    f"PRIVATE = Path({temporary!r})",
                ).replace("from getpass import getpass", "getpass = fake_prompt")
                if cell.id == "part-2-package-code":
                    cell.source = (
                        "assert not any(path.startswith(API + '/') for _, path, _ in _calls), 'Part 1 must not fetch Package Details.'\n"
                        + cell.source
                    )
                if write:
                    for name in ("RUN_WRITES", "GROUPS_APPROVED", "AGENT_GROUP_APPROVED", "CREATE_BLUEPRINT", "CREATE_PRINCIPAL", "CREATE_IDENTITY"):
                        cell.source = cell.source.replace(name + " = False", name + " = True")
                if confirm_writes:
                    cell.source = cell.source.replace("CONFIRM_EACH_WRITE = False", "CONFIRM_EACH_WRITE = True")
                if multiple_groups and cell.id == "configuration-variables":
                    cell.source = cell.source.replace("['test-v2-dev']", "['test-v2-dev', 'support-dev']")
                if cell.id == "configuration-variables":
                    cell.source = cell.source.replace("SELECTED_BLUEPRINT_GROUP = 'test-v2-dev'", f"SELECTED_BLUEPRINT_GROUP = {selected_group!r}")
                if first_companion or registration_failure:
                    cell.source = cell.source.replace("CREATE_COMPANION = False", "CREATE_COMPANION = True")
                if cleanup:
                    cell.source = cell.source.replace("DELETE_OBJECT = None", "DELETE_OBJECT = 'registration'")
                    cell.source = cell.source.replace("CONFIRMED_NO_DEPENDENTS = False", "CONFIRMED_NO_DEPENDENTS = True")
                if cleanup_blueprint:
                    cell.source = cell.source.replace("DELETE_OBJECT = None", "DELETE_OBJECT = 'blueprint'")
                    cell.source = cell.source.replace("CLEANUP_GROUP = None", "CLEANUP_GROUP = 'support-dev'")
                    cell.source = cell.source.replace("CONFIRMED_NO_DEPENDENTS = False", "CONFIRMED_NO_DEPENDENTS = True")
                if legacy and cell.id == "setup-code":
                    cell.source += """
state.update(
    blueprint={"id": BP, "appId": APP},
    principal={"id": PRINCIPAL, "appId": APP, "accountEnabled": True},
    blueprint_group="test-v2-dev",
    original_before=_packages[ORIGINAL],
)
save_state()
"""
                if registration_failure and cell.id == "setup-code":
                    cell.source += '\nstate["registration"] = {"id": COMPANION}\nsave_state()\n'
            notebook.cells.insert(0, nbformat.v4.new_code_cell(
                f"WRITE = {write!r}\nFIRST_COMPANION = {first_companion!r}\nREGISTRATION_FAILURE = {registration_failure!r}\nDENY_CONFIRMATION = {deny_confirmation!r}\n" + FIXTURE
                + ("\n_objects.pop(SP_ROOT + '/' + PRINCIPAL + '/' + PR_TYPE)\n" if missing_principal else ""),
            ))
            cleanup_index = next(index for index, cell in enumerate(notebook.cells) if cell.id == "cleanup-code")
            notebook.cells.insert(cleanup_index, nbformat.v4.new_code_cell("""
interactive_count = len(_auth_calls)
silent_count = len(_silent_calls)
sign_in(DISCOVERY_SCOPES)
assert len(_auth_calls) == interactive_count
assert len(_silent_calls) == silent_count
access_token_expires_at = 0
sign_in(DISCOVERY_SCOPES)
assert len(_auth_calls) == interactive_count
assert len(_silent_calls) == silent_count + 1
"""))
            expected_writes = [] if not write else ["POST", "POST"] * (2 if multiple_groups else 1) + ["POST", "POST" if first_companion else "PATCH"]
            if cleanup or cleanup_blueprint:
                expected_writes.append("DELETE")
            initial_scopes = [
                "User.Read",
                "CopilotPackages.Read.All",
                "AgentIdentityBlueprint.Read.All",
                "AgentIdentityBlueprintPrincipal.Read.All",
                "AgentIdentity.Read.All",
                "AgentRegistration.Read.All",
            ]
            if write:
                initial_scopes += [
                    "AgentIdentityBlueprint.Create",
                    "AgentIdentityBlueprintPrincipal.Create",
                    "AgentIdentity.Create.All",
                    "AgentRegistration.ReadWrite.All",
                ]
            expected_initial_scopes = [
                "https://graph.microsoft.com/" + scope for scope in sorted(set(initial_scopes))
            ]
            notebook.cells.append(nbformat.v4.new_code_cell(f"""
assert [method for method, _, _ in _calls if method != "GET"] == {expected_writes!r}
assert len(_auth_calls) == {2 if cleanup_blueprint else 1}
assert len(_silent_calls) == {2 if cleanup or cleanup_blueprint else 1}
assert _auth_calls[0] == {expected_initial_scopes!r}
assert _interactive_options[0] == (msal.Prompt.SELECT_ACCOUNT, None)
assert not {cleanup_blueprint!r} or _interactive_options[1] == (None, "operator@example.test")
assert state["original_id"] == ORIGINAL
assert not state.get("pending_write")
assert access_token is None
assert access_token_scopes == set()
assert access_token_expires_at == 0
assert auth_account is None
assert auth_client is None
assert "fixture-access-token" not in STATE_FILE.read_text()
assert state["sponsor_id"] == OPERATOR
assert not any("sponsor user" in prompt for prompt in _prompts)
assert sum("Type APPLY" in prompt for prompt in _prompts) == {len(expected_writes) if confirm_writes else int(cleanup or cleanup_blueprint)}
assert sum("Type FIRST" in prompt for prompt in _prompts) == {int(first_companion)}
assert sum("Registration ID" in prompt for prompt in _prompts) == {0 if first_companion else 1}
assert not {write!r} or not any("Blueprint object ID" in prompt or "Agent Identity ID" in prompt for prompt in _prompts)
assert sum(len(members) for members in packages_by_platform.values()) == _initial_package_count
assert set(packages_by_platform) == {{"GoogleVertexAI", "ExampleUnconfirmed", "ExampleDenied", "ExampleUnavailable", "(platform missing)"}}
assert len(packages_by_platform["(platform missing)"]) == 1
assert not (PRIVATE / "inventory-details.json").exists()
assert all(not path.startswith(API + "/") or path.rsplit("/", 1)[1] in (ORIGINAL, COMPANION) for _, path, _ in _calls)
assert agent_platform == original["platform"] == "GoogleVertexAI"
assert blueprint_group == {selected_group!r}
assert agent_identity["agentIdentityBlueprintId"] == state[bindings[agent_platform][blueprint_group]["blueprint_record"]]["appId"]
assert {2 if multiple_groups else 1} == len(bindings[agent_platform])
"""))
            if replay_groups:
                group_sources = "\n".join(cell.source for cell in notebook.cells if cell.id in ("part-1-groups-code", "part-1-blueprints-code"))
                notebook.cells.append(nbformat.v4.new_code_cell(
                    "_before_replay_writes = sum(method != 'GET' for method, _, _ in _calls)\n"
                    + group_sources
                    + "\nassert sum(method != 'GET' for method, _, _ in _calls) == _before_replay_writes\naccess_token = None\n",
                ))
            if legacy:
                notebook.cells.append(nbformat.v4.new_code_cell("""
assert bindings["GoogleVertexAI"]["test-v2-dev"] == {"blueprint_record": "blueprint", "principal_record": "principal"}
assert not state.get("created_here")
"""))
            if cleanup_blueprint:
                notebook.cells.append(nbformat.v4.new_code_cell("""
assert SP_ROOT + "/" + IDENTITY + "/" + ID_TYPE in _objects
assert SP_ROOT + "/" + PRINCIPAL + "/" + PR_TYPE in _objects
assert BP_ROOT + "/" + uid(201) + "/" + BP_TYPE not in _objects
assert SP_ROOT + "/" + uid(203) + "/" + PR_TYPE not in _objects
"""))
            if auth_failure:
                notebook.cells.append(nbformat.v4.new_code_cell("""
access_token = "fixture-stale-token"
access_token_scopes = {scope.lower() for scope in DISCOVERY_SCOPES}
access_token_expires_at = 0
_auth_failure = True
call_count = len(_calls)
interactive_count = len(_auth_calls)
try:
    sign_in(DISCOVERY_SCOPES)
except RuntimeError as error:
    assert "Browser sign-in did not complete" in str(error)
else:
    raise AssertionError("Failed browser sign-in must stop.")
assert access_token is None
assert access_token_scopes == set()
assert access_token_expires_at == 0
assert len(_auth_calls) == interactive_count + 1
assert len(_calls) == call_count
assert "fixture-sensitive-error" not in STATE_FILE.read_text()
"""))
            if unknown_write:
                notebook.cells.append(nbformat.v4.new_code_cell("""
access_token = "fixture-access-token"
_failure = "POST"
try:
    request_graph("POST", BP_ROOT + "/" + BP_TYPE, {}, record="uncertain")
except AssertionError as error:
    assert "403" in str(error)
else:
    raise AssertionError("Failed write must stop.")
assert state["pending_write"]["record"] == "uncertain"
call_count = len(_calls)
try:
    request_graph("POST", BP_ROOT + "/" + BP_TYPE, {}, record="uncertain")
except AssertionError:
    pass
else:
    raise AssertionError("Unknown write must not be repeated.")
assert len(_calls) == call_count
access_token = None
"""))
            client = NotebookClient(
                notebook, timeout=180, kernel_name="python3", resources={"metadata": {"path": str(LAB)}},
            )
            if missing_principal or registration_failure or deny_confirmation:
                with self.assertRaises(CellExecutionError) as raised:
                    client.execute()
                expected = (
                    "Creation not confirmed" if deny_confirmation == "FIRST"
                    else "Not approved" if deny_confirmation == "DELETE"
                    else "Blueprint and principal are not ready" if missing_principal
                    else f"HTTP {registration_failure}"
                )
                self.assertIn(expected, raised.exception.evalue)
                saved = json.loads((Path(temporary) / "state.json").read_text())
                if deny_confirmation == "DELETE":
                    self.assertIn("registration", saved["created_here"])
                    self.assertNotIn("deleted_registration", saved["completed_writes"])
                else:
                    self.assertNotIn("registration", saved.get("created_here", {}))
                self.assertNotIn("pending_write", saved)
                if missing_principal:
                    self.assertNotIn("agent_identity", saved)
                self.assertEqual(NOTEBOOK.read_bytes(), original_bytes)
                return
            client.execute()
            outputs = "\n".join(str(output) for cell in notebook.cells if cell.cell_type == "code" for output in cell.outputs)
            for value in ("00000000-0000-4000-8000-", "fixture-access-token", "fixture-stale-token", "fixture-original", "fixture-companion", "test%2Fv2", "fixture-sensitive-error"):
                self.assertNotIn(value, outputs)
        self.assertEqual(NOTEBOOK.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()

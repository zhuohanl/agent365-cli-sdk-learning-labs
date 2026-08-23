import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ["ENABLE_A365_OBSERVABILITY"] = "true"
os.environ["ENABLE_A365_OBSERVABILITY_EXPORTER"] = "false"

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider

from microsoft_agents_a365.observability.core import (
    AgentDetails,
    InvokeAgentScope,
    InvokeAgentScopeDetails,
    Request,
    configure,
)


provider = TracerProvider(
    resource=Resource.create({SERVICE_NAME: "a365-learning-lab"})
)
trace.set_tracer_provider(provider)

if not configure(
    service_name="a365-learning-lab",
    service_namespace="guided-labs",
    token_resolver=lambda agent_id, tenant_id: None,
):
    raise RuntimeError("Agent 365 observability configuration failed")

AGENT = AgentDetails(
    agent_id="local-echo-agent",
    agent_name="A365LearningLab",
)

SIDECAR_URL = os.environ.get("SIDECAR_URL", "http://127.0.0.1:5000")
AGENT_CLIENT_ID = os.environ.get("AGENT_CLIENT_ID")
AGENT_OBJECT_ID = os.environ.get("AGENT_OBJECT_ID")
GRAPH_PROBE_URL = (
    "https://graph.microsoft.com/v1.0/organization"
    "?$select=id&$top=1"
)


def acquire_graph_authorization_header() -> str:
    if not AGENT_CLIENT_ID:
        raise RuntimeError("AGENT_CLIENT_ID is not configured")

    query = urllib.parse.urlencode({"AgentIdentity": AGENT_CLIENT_ID})
    url = (
        f"{SIDECAR_URL}/AuthorizationHeaderUnauthenticated/graph-app"
        f"?{query}"
    )
    request = urllib.request.Request(url, headers={"Host": "localhost"})

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as error:
        error.close()
        raise RuntimeError(
            f"Sidecar returned HTTP {error.code}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError("Sidecar is unavailable") from error

    authorization_header = body.get("authorizationHeader")
    if not isinstance(authorization_header, str):
        raise RuntimeError("Sidecar response has no authorization header")
    if not authorization_header.startswith("Bearer "):
        raise RuntimeError("Sidecar returned an unexpected authorization scheme")

    return authorization_header


def request_graph_status(url: str) -> int:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": acquire_graph_authorization_header(),
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        return status
    except urllib.error.URLError as error:
        raise RuntimeError("Microsoft Graph is unavailable") from error


def graph_result(status: int) -> str:
    if status == 200:
        return "authorized"
    if status == 401:
        return "authentication-rejected"
    if status == 403:
        return "authorization-denied"
    raise RuntimeError(f"Graph returned unexpected HTTP status {status}")


def check_manager_role() -> str:
    if not AGENT_OBJECT_ID:
        raise RuntimeError("AGENT_OBJECT_ID is not configured")

    object_id = urllib.parse.quote(AGENT_OBJECT_ID, safe="")
    url = (
        "https://graph.microsoft.com/v1.0/servicePrincipals/"
        f"{object_id}/microsoft.graph.agentIdentity"
        "?$select=id"
    )
    return graph_result(request_graph_status(url))


class AgentHandler(BaseHTTPRequestHandler):
    def send_json(self, status: int, value: dict[str, object]) -> None:
        response = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_POST(self) -> None:
        try:
            self.handle_post()
        except RuntimeError as error:
            self.send_json(502, {"error": str(error)})

    def handle_post(self) -> None:
        if self.path == "/identity-check":
            authorization_header = acquire_graph_authorization_header()
            self.send_json(
                200,
                {
                    "token_acquired": bool(authorization_header),
                    "token_disclosed": False,
                },
            )
            return

        if self.path == "/graph-check":
            result = graph_result(request_graph_status(GRAPH_PROBE_URL))
            self.send_json(
                200,
                {
                    "token_acquired": True,
                    "graph_result": result,
                    "graph_data_disclosed": False,
                },
            )
            return

        if self.path == "/manager-role-check":
            self.send_json(
                200,
                {
                    "manager_role_result": check_manager_role(),
                    "graph_data_disclosed": False,
                },
            )
            return

        if self.path != "/chat":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        message = request["message"]

        with InvokeAgentScope.start(
            request=Request(content=[message]),
            scope_details=InvokeAgentScopeDetails(endpoint=None),
            agent_details=AGENT,
        ) as invoke_scope:
            reply = f"Echo: {message}"
            invoke_scope.record_response(reply)

        # Make the one-request learning result visible without waiting for the
        # batch processor schedule.
        provider.force_flush()
        self.send_json(200, {"reply": reply})


server = ThreadingHTTPServer(("127.0.0.1", 8080), AgentHandler)
print("Learning agent listening on http://127.0.0.1:8080")
server.serve_forever()

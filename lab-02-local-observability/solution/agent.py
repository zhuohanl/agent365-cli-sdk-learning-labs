import json
import os
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


class AgentHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
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

        response = json.dumps({"reply": reply}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


server = ThreadingHTTPServer(("127.0.0.1", 8080), AgentHandler)
print("Echo agent listening on http://127.0.0.1:8080/chat")
server.serve_forever()

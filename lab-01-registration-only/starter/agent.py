import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class AgentHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/chat":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        reply = f"Echo: {request['message']}"
        response = json.dumps({"reply": reply}).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)


server = ThreadingHTTPServer(("127.0.0.1", 8080), AgentHandler)
print("Echo agent listening on http://127.0.0.1:8080/chat")
server.serve_forever()

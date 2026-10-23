"""One-purpose loopback User-Agent echo; never reads or saves cookies."""
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer


class AgentProbe(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        body = (
            '<!doctype html><html lang="en"><title>Local browser version evidence</title>'
            '<main><h1>Reported browser User-Agent</h1><pre id="user-agent">'
            + escape(self.headers.get("User-Agent", "Unavailable"))
            + "</pre></main></html>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = HTTPServer(("127.0.0.1", 0), AgentProbe)
print(f"http://127.0.0.1:{server.server_port}/", flush=True)
server.serve_forever()

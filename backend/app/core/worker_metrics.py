"""Optional internal worker metrics server; never publish its port publicly."""

import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


def serve(port, token):
    if not port:
        return None
    if len(token) < 32:
        raise ValueError("Worker metrics require a generated METRICS_TOKEN")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.send_error(404)
                return
            if self.path != "/metrics":
                self.send_error(404)
                return
            body = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass  # Never include incoming headers or URLs in worker access logs.

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)  # nosec B104
    Thread(target=server.serve_forever, daemon=True).start()
    return server

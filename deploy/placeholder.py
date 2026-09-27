"""Answers on the web port while the entrypoint installs or upgrades Odoo.

Hosts that wait for an open port (Render gives up after a few minutes) keep the deploy alive, and
whoever opens the site meanwhile sees why it is not there yet instead of a connection error.
"""
import http.server
import sys

PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="20">
<title>Preparando o sistema</title>
<style>
body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #0f1115; color: #e5e7eb;
       font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
main { text-align: center; padding: 24px; }
h1 { font-size: 1.4rem; margin: 0 0 8px; }
p { color: #9ca3af; margin: 0; }
.spin { width: 44px; height: 44px; border-radius: 50%; border: 4px solid #2a2d35; border-top-color: #e8b21e;
        margin: 0 auto 20px; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style></head>
<body><main><div class="spin"></div><h1>Preparando o sistema</h1>
<p>Uma atualização está sendo instalada. Esta página recarrega sozinha.</p></main></body></html>
""".encode()


class Handler(http.server.BaseHTTPRequestHandler):

    def _answer(self, with_body):
        if self.path.startswith("/web/health"):
            status, body, kind = 200, b'{"status": "pass", "preparing": true}', "application/json"
        else:
            status, body, kind = 503, PAGE, "text/html; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Retry-After", "20")
        self.end_headers()
        if with_body:
            self.wfile.write(body)

    def do_GET(self):
        self._answer(with_body=True)

    def do_HEAD(self):
        self._answer(with_body=False)

    def do_POST(self):
        # A login or RPC sent meanwhile gets "try again later", not "not implemented".
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(min(length, 1_000_000))
        body = b'{"error": "preparing", "retry_after": 20}'
        self.send_response(503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Retry-After", "20")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", int(sys.argv[1])), Handler).serve_forever()

"""Disposable assets and a local webhook receiver; request bodies are never retained."""

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RECEIPTS: list[dict[str, str | int]] = []


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/receipts":
            payload = json.dumps(RECEIPTS).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            super().do_GET()

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        if not self.path.startswith("/action") or size > 1024 * 1024:
            self.send_error(413)
            return
        self.rfile.read(size)
        RECEIPTS.append({"method": "POST", "path": self.path, "bytes": size})
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()

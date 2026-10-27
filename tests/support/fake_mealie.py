"""Strict HTTP fixture server for upstream and Python contract comparisons."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import TracebackType
from typing import Any
from urllib.parse import parse_qs, urlsplit

from tests.support.contracts import _typed_json

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "compatibility"


class FakeMealie:
    def __init__(self, scenario: str | list[dict[str, Any]]) -> None:
        scenarios = json.loads((FIXTURES / "scenarios.json").read_text())
        self.pending = (
            scenarios[scenario]["requests"] if isinstance(scenario, str) else list(scenario)
        )
        self.recorded_requests: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self._lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                pass

            def handle_request(self) -> None:
                url = urlsplit(self.path)
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length)) if length else None
                received = {
                    "method": self.command,
                    "path": url.path,
                    "query": parse_qs(url.query, keep_blank_values=True),
                    "body": body,
                }
                with owner._lock:
                    owner.recorded_requests.append(received)
                    match = next(
                        (
                            spec
                            for spec in owner.pending
                            if _typed_json({key: spec.get(key) for key in received})
                            == _typed_json(received)
                        ),
                        None,
                    )
                    if match is None:
                        owner.errors.append(f"Unexpected fixture request: {received}")
                        status, response = 500, {"detail": "Unexpected fixture request"}
                    else:
                        owner.pending.remove(match)
                        status, response = match.get("status", 200), match.get("response")
                payload = json.dumps(response).encode() if status != 204 else b""
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = handle_request
            do_POST = handle_request
            do_PUT = handle_request
            do_PATCH = handle_request
            do_DELETE = handle_request

        self._server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
        port = self._server.server_port
        self.server_url = f"http://127.0.0.1:{port}"
        self.docker_url = f"http://dev:{port}"
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )

    def __enter__(self) -> FakeMealie:
        self._thread.start()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
        if kind is None:
            assert not self.errors, self.errors
            assert not self.pending, f"Unconsumed fixture requests: {self.pending}"

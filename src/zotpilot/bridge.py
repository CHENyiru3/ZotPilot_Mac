"""HTTP bridge between ZotPilot MCP tools and the ZotPilot Connector extension.

The bridge serves endpoints on localhost:
  GET  /pending       → returns next queued save command (or 204 No Content)
  POST /enqueue       → accepts a save command from MCP tools
  POST /result        → receives save results from the extension
  GET  /result/<id>   → returns result for a specific request_id (or 204)
  GET  /status        → health check

The Chrome extension polls GET /pending every 2 seconds.
MCP tools POST to /enqueue and poll GET /result/<id> for the outcome.

Uses ThreadingHTTPServer to avoid deadlock when the MCP tool is polling
/result while the extension tries to POST /result concurrently.
"""
import json
import logging
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PORT = 2619


class _BridgeHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the bridge."""

    def log_message(self, format, *args):
        logger.debug(format, *args)

    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/pending":
            cmd = self.server.bridge._dequeue()
            if cmd:
                body = json.dumps(cmd).encode()
                self.send_response(200)
                self._set_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(204)
                self._set_cors()
                self.end_headers()
        elif self.path.startswith("/result/"):
            request_id = self.path[len("/result/"):]
            result = self.server.bridge.get_result(request_id)
            if result:
                body = json.dumps(result).encode()
                self.send_response(200)
                self._set_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(204)
                self._set_cors()
                self.end_headers()
        elif self.path == "/status":
            body = json.dumps({"bridge": "running", "port": self.server.bridge.port}).encode()
            self.send_response(200)
            self._set_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/enqueue":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                command = json.loads(body)
                request_id = self.server.bridge.enqueue(command)
                resp = json.dumps({"request_id": request_id}).encode()
                self.send_response(200)
                self._set_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(resp)
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
        elif self.path == "/result":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                result = json.loads(body)
                self.server.bridge._store_result(result)
                self.send_response(200)
                self._set_cors()
                self.end_headers()
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


class BridgeServer:
    """HTTP bridge server for Chrome extension communication."""

    def __init__(self, port: int = DEFAULT_PORT):
        self._requested_port = port
        self._queue: list[dict] = []
        self._results: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port = port

    def enqueue(self, command: dict) -> str:
        """Add a save command to the queue. Returns request_id."""
        command = {**command}  # defensive copy — never mutate caller's dict
        if "request_id" not in command:
            command["request_id"] = uuid.uuid4().hex[:12]
        request_id = command["request_id"]
        with self._lock:
            self._queue.append(command)
        return request_id

    def get_result(self, request_id: str) -> dict[str, Any] | None:
        """Get a stored result without blocking."""
        with self._lock:
            return self._results.get(request_id)

    def _dequeue(self) -> dict | None:
        with self._lock:
            return self._queue.pop(0) if self._queue else None

    def _store_result(self, result: dict):
        request_id = result.get("request_id")
        if not request_id:
            return
        with self._lock:
            self._results[request_id] = result

    def start(self):
        """Start the HTTP server in a background thread."""
        self._server = ThreadingHTTPServer(("127.0.0.1", self._requested_port), _BridgeHandler)
        self._server.bridge = self  # type: ignore[attr-defined]
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"Bridge server listening on http://127.0.0.1:{self.port}")

    def stop(self):
        """Stop the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server = None

    @staticmethod
    def is_running(port: int = DEFAULT_PORT) -> bool:
        """Check if a bridge is already running on the given port."""
        import urllib.request
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=2)
            return resp.status == 200
        except Exception:
            return False

    @staticmethod
    def auto_start(port: int = DEFAULT_PORT) -> None:
        """Start bridge as a background subprocess if not already running."""
        if BridgeServer.is_running(port):
            return
        import time
        subprocess.Popen(
            [sys.executable, "-m", "zotpilot.cli", "bridge", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(10):
            time.sleep(0.5)
            if BridgeServer.is_running(port):
                return
        raise RuntimeError(
            f"Failed to auto-start bridge on port {port}. "
            "Ensure zotpilot is installed in the active Python environment."
        )

"""Tests for ZotPilot HTTP bridge server."""
from __future__ import annotations

import json
import urllib.request

from zotpilot.bridge import BridgeServer


class TestBridgeServer:
    def test_no_pending_returns_204(self):
        """GET /pending with no commands returns 204."""
        bridge = BridgeServer(port=0)
        bridge.start()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{bridge.port}/pending")
            resp = urllib.request.urlopen(req)
            assert resp.status == 204
        finally:
            bridge.stop()

    def test_enqueue_and_fetch(self):
        """Enqueue a command, GET /pending returns it with request_id."""
        bridge = BridgeServer(port=0)
        bridge.start()
        try:
            bridge.enqueue({
                "action": "save",
                "url": "https://example.com/paper",
            })
            req = urllib.request.Request(f"http://127.0.0.1:{bridge.port}/pending")
            resp = urllib.request.urlopen(req)
            data = json.loads(resp.read())
            assert data["action"] == "save"
            assert data["url"] == "https://example.com/paper"
            assert "request_id" in data
        finally:
            bridge.stop()

    def test_enqueue_via_http(self):
        """POST /enqueue accepts commands and returns request_id."""
        bridge = BridgeServer(port=0)
        bridge.start()
        try:
            command = json.dumps({"action": "save", "url": "https://example.com"}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{bridge.port}/enqueue",
                data=command,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req)
            data = json.loads(resp.read())
            assert "request_id" in data

            # Verify it's in the queue
            req2 = urllib.request.Request(f"http://127.0.0.1:{bridge.port}/pending")
            resp2 = urllib.request.urlopen(req2)
            queued = json.loads(resp2.read())
            assert queued["request_id"] == data["request_id"]
        finally:
            bridge.stop()

    def test_post_result_and_retrieve(self):
        """POST /result stores result, GET /result/<id> returns it."""
        bridge = BridgeServer(port=0)
        bridge.start()
        try:
            rid = bridge.enqueue({"action": "save", "url": "https://example.com"})
            result = {"request_id": rid, "success": True, "title": "Test Paper"}
            data = json.dumps(result).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{bridge.port}/result",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req)

            # Retrieve via GET /result/<id>
            req2 = urllib.request.Request(f"http://127.0.0.1:{bridge.port}/result/{rid}")
            resp2 = urllib.request.urlopen(req2)
            stored = json.loads(resp2.read())
            assert stored["success"] is True
            assert stored["title"] == "Test Paper"
        finally:
            bridge.stop()

    def test_result_not_found_returns_204(self):
        """GET /result/<nonexistent_id> returns 204."""
        bridge = BridgeServer(port=0)
        bridge.start()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{bridge.port}/result/nonexistent")
            resp = urllib.request.urlopen(req)
            assert resp.status == 204
        finally:
            bridge.stop()

    def test_status_endpoint(self):
        """GET /status returns running status."""
        bridge = BridgeServer(port=0)
        bridge.start()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{bridge.port}/status")
            resp = urllib.request.urlopen(req)
            data = json.loads(resp.read())
            assert data["bridge"] == "running"
        finally:
            bridge.stop()

    def test_queue_is_fifo(self):
        """Multiple commands dequeue in order."""
        bridge = BridgeServer(port=0)
        bridge.start()
        try:
            bridge.enqueue({"action": "save", "url": "https://first.com"})
            bridge.enqueue({"action": "save", "url": "https://second.com"})

            resp1 = urllib.request.urlopen(f"http://127.0.0.1:{bridge.port}/pending")
            data1 = json.loads(resp1.read())
            assert data1["url"] == "https://first.com"

            resp2 = urllib.request.urlopen(f"http://127.0.0.1:{bridge.port}/pending")
            data2 = json.loads(resp2.read())
            assert data2["url"] == "https://second.com"
        finally:
            bridge.stop()

    def test_enqueue_does_not_mutate_input(self):
        """enqueue() makes a defensive copy of the command dict."""
        bridge = BridgeServer(port=0)
        original = {"action": "save", "url": "https://example.com"}
        bridge.enqueue(original)
        assert "request_id" not in original

    def test_is_running_false_when_not_started(self):
        """is_running returns False for a port with no server."""
        assert BridgeServer.is_running(port=19999) is False

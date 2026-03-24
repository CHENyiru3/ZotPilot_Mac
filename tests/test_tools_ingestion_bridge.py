"""Tests for bridge-dependent ingestion paths.

Covers _discover_saved_item_key, _apply_bridge_result_routing,
save_from_url, and save_urls — all with mocked HTTP / bridge.
"""
from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastmcp.exceptions import ToolError

from zotpilot.tools.ingestion import (
    _apply_bridge_result_routing,
    _discover_saved_item_key,
    save_from_url,
    save_urls,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_writer():
    writer = MagicMock()
    writer.find_items_by_url_and_title.return_value = []
    writer.add_to_collection.return_value = None
    writer.add_item_tags.return_value = None
    return writer


def _make_config(api_key="TEST_API_KEY"):
    config = MagicMock()
    config.zotero_api_key = api_key
    return config


def _make_urlopen_response(body: dict, status: int = 200):
    """Return a mock that behaves like urllib response."""
    mock = MagicMock()
    mock.status = status
    mock.read.return_value = json.dumps(body).encode()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def _make_http_error(code: int, body: dict | None = None):
    """Return a urllib.error.HTTPError with optional JSON body."""
    body_bytes = json.dumps(body).encode() if body else b""
    err = urllib.error.HTTPError(
        url="http://127.0.0.1:9999/enqueue",
        code=code,
        msg="Error",
        hdrs=None,  # type: ignore[arg-type]
        fp=BytesIO(body_bytes),
    )
    return err


# ---------------------------------------------------------------------------
# TestDiscoverSavedItemKey
# ---------------------------------------------------------------------------

class TestDiscoverSavedItemKey:
    def test_known_key_returned_immediately(self):
        writer = _make_writer()
        result = _discover_saved_item_key(
            title="Some Title",
            url="https://example.com",
            known_key="KNOWN1",
            writer=writer,
        )
        assert result == "KNOWN1"
        writer.find_items_by_url_and_title.assert_not_called()

    def test_no_title_no_url_returns_none(self):
        writer = _make_writer()
        result = _discover_saved_item_key(
            title="",
            url="",
            known_key=None,
            writer=writer,
        )
        assert result is None
        writer.find_items_by_url_and_title.assert_not_called()

    def test_exactly_one_match_returns_it(self):
        writer = _make_writer()
        writer.find_items_by_url_and_title.return_value = ["KEY123"]
        result = _discover_saved_item_key(
            title="Test Paper",
            url="https://doi.org/10.1234/test",
            known_key=None,
            writer=writer,
        )
        assert result == "KEY123"

    def test_zero_matches_returns_none(self):
        writer = _make_writer()
        writer.find_items_by_url_and_title.return_value = []
        result = _discover_saved_item_key(
            title="Test Paper",
            url="https://doi.org/10.1234/test",
            known_key=None,
            writer=writer,
        )
        assert result is None

    def test_multiple_matches_returns_none(self):
        writer = _make_writer()
        writer.find_items_by_url_and_title.return_value = ["KEY1", "KEY2"]
        result = _discover_saved_item_key(
            title="Duplicate Title",
            url="https://example.com/paper",
            known_key=None,
            writer=writer,
        )
        assert result is None

    def test_exception_returns_none_logged(self):
        writer = _make_writer()
        writer.find_items_by_url_and_title.side_effect = Exception("API error")
        result = _discover_saved_item_key(
            title="Test",
            url="https://example.com",
            known_key=None,
            writer=writer,
        )
        assert result is None


# ---------------------------------------------------------------------------
# TestApplyBridgeResultRouting
# ---------------------------------------------------------------------------

class TestApplyBridgeResultRouting:
    def test_no_collection_no_tags_returns_unchanged(self):
        result = {"success": True, "url": "https://example.com", "title": "Test"}
        writer = _make_writer()
        config = _make_config(api_key="KEY")
        with patch("zotpilot.tools.ingestion._get_config", return_value=config), \
             patch("zotpilot.tools.ingestion._get_writer", return_value=writer), \
             patch("zotpilot.tools.ingestion.time.sleep"):
            out = _apply_bridge_result_routing(result, None, None)
        # No routing — no warning added
        assert "warning" not in out
        writer.add_to_collection.assert_not_called()
        writer.add_item_tags.assert_not_called()

    def test_item_key_discovered_routing_applied(self):
        result = {
            "success": True,
            "url": "https://example.com/paper",
            "title": "My Paper",
        }
        writer = _make_writer()
        writer.find_items_by_url_and_title.return_value = ["ITEM1"]
        config = _make_config(api_key="KEY")
        with patch("zotpilot.tools.ingestion._get_config", return_value=config), \
             patch("zotpilot.tools.ingestion._get_writer", return_value=writer), \
             patch("zotpilot.tools.ingestion.time.sleep"):
            out = _apply_bridge_result_routing(result, "COL1", ["tag1"])
        assert out.get("item_key") == "ITEM1"
        writer.add_to_collection.assert_called_once_with("ITEM1", "COL1")
        writer.add_item_tags.assert_called_once_with("ITEM1", ["tag1"])
        assert "warning" not in out

    def test_item_key_not_discovered_zero_matches_returns_warning(self):
        result = {
            "success": True,
            "url": "https://example.com/paper",
            "title": "Obscure Paper",
        }
        writer = _make_writer()
        writer.find_items_by_url_and_title.return_value = []
        config = _make_config(api_key="KEY")
        with patch("zotpilot.tools.ingestion._get_config", return_value=config), \
             patch("zotpilot.tools.ingestion._get_writer", return_value=writer), \
             patch("zotpilot.tools.ingestion.time.sleep"):
            out = _apply_bridge_result_routing(result, "COL1", None)
        assert "warning" in out
        assert "not found" in out["warning"]
        writer.add_to_collection.assert_not_called()

    def test_ambiguous_match_returns_warning(self):
        result = {
            "success": True,
            "url": "https://example.com/paper",
            "title": "Common Title",
        }
        writer = _make_writer()
        # First call (in _discover_saved_item_key) returns 2 items → None
        # Second call (in _apply_bridge_result_routing for count) also returns 2 items
        writer.find_items_by_url_and_title.return_value = ["KEY1", "KEY2"]
        config = _make_config(api_key="KEY")
        with patch("zotpilot.tools.ingestion._get_config", return_value=config), \
             patch("zotpilot.tools.ingestion._get_writer", return_value=writer), \
             patch("zotpilot.tools.ingestion.time.sleep"):
            out = _apply_bridge_result_routing(result, "COL1", None)
        assert "warning" in out
        assert "ambiguous" in out["warning"]

    def test_no_api_key_returns_warning_about_ignored_routing(self):
        result = {
            "success": True,
            "url": "https://example.com",
            "title": "Paper",
        }
        config = _make_config(api_key=None)
        with patch("zotpilot.tools.ingestion._get_config", return_value=config):
            out = _apply_bridge_result_routing(result, "COL1", ["tag1"])
        assert "warning" in out
        assert "ZOTERO_API_KEY" in out["warning"]

    def test_success_false_returns_result_as_is(self):
        result = {
            "success": False,
            "error_code": "translator_failed",
            "error_message": "No translator found",
        }
        out = _apply_bridge_result_routing(result, "COL1", ["tag"])
        assert out is result
        assert out["success"] is False

    def test_item_key_in_bridge_result_skips_sleep(self):
        """When bridge result already has item_key, time.sleep should not be called."""
        result = {
            "success": True,
            "url": "https://example.com",
            "title": "Paper",
            "item_key": "KNOWN_KEY",
        }
        writer = _make_writer()
        writer.find_items_by_url_and_title.return_value = ["KNOWN_KEY"]
        config = _make_config(api_key="KEY")
        with patch("zotpilot.tools.ingestion._get_config", return_value=config), \
             patch("zotpilot.tools.ingestion._get_writer", return_value=writer), \
             patch("zotpilot.tools.ingestion.time.sleep") as mock_sleep:
            _apply_bridge_result_routing(result, None, None)
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# TestSaveFromUrl
# ---------------------------------------------------------------------------

class TestSaveFromUrl:
    def _patch_bridge(self, is_running=True, auto_start_exc=None):
        patches = [
            patch("zotpilot.tools.ingestion.BridgeServer.is_running", return_value=is_running),
            patch("zotpilot.tools.ingestion.time.sleep"),
        ]
        if auto_start_exc:
            patches.append(
                patch("zotpilot.tools.ingestion.BridgeServer.auto_start", side_effect=auto_start_exc)
            )
        else:
            patches.append(
                patch("zotpilot.tools.ingestion.BridgeServer.auto_start", return_value=None)
            )
        return patches

    def test_successful_save_returns_result_with_title(self):
        enqueue_resp = _make_urlopen_response({"request_id": "req-001"})
        poll_resp = _make_urlopen_response(
            {"success": True, "url": "https://example.com", "title": "Great Paper", "request_id": "req-001"},
            status=200,
        )
        config = _make_config(api_key=None)

        call_count = [0]
        def fake_urlopen(req_or_url, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return enqueue_resp
            return poll_resp

        with patch("zotpilot.tools.ingestion.BridgeServer.is_running", return_value=True), \
             patch("zotpilot.tools.ingestion.BridgeServer.auto_start"), \
             patch("zotpilot.tools.ingestion.time.sleep"), \
             patch("zotpilot.tools.ingestion._get_config", return_value=config), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = save_from_url("https://example.com")

        assert result["success"] is True
        assert result["title"] == "Great Paper"

    def test_auto_start_raises_runtime_error_returns_error(self):
        with patch("zotpilot.tools.ingestion.BridgeServer.is_running", return_value=False), \
             patch("zotpilot.tools.ingestion.BridgeServer.auto_start",
                   side_effect=RuntimeError("Cannot start bridge")):
            result = save_from_url("https://example.com")

        assert result["success"] is False
        assert "Cannot start bridge" in result["error"]

    def test_enqueue_503_returns_extension_not_connected(self):
        err_body = {
            "error_code": "extension_not_connected",
            "error_message": "No heartbeat received.",
        }
        http_err = _make_http_error(503, err_body)

        with patch("zotpilot.tools.ingestion.BridgeServer.is_running", return_value=True), \
             patch("zotpilot.tools.ingestion.BridgeServer.auto_start"), \
             patch("urllib.request.urlopen", side_effect=http_err):
            result = save_from_url("https://example.com")

        assert result["success"] is False
        assert result.get("error_code") == "extension_not_connected"

    def test_poll_timeout_returns_timeout_error(self):
        enqueue_resp = _make_urlopen_response({"request_id": "req-timeout"})

        # Poll always raises (simulates 204 / no result)
        poll_error = urllib.error.URLError("connection refused")

        call_count = [0]
        def fake_urlopen(req_or_url, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return enqueue_resp
            raise poll_error

        # Make time.monotonic advance past the 90s deadline quickly
        mono_values = [0.0, 0.0] + [91.0] * 200

        with patch("zotpilot.tools.ingestion.BridgeServer.is_running", return_value=True), \
             patch("zotpilot.tools.ingestion.BridgeServer.auto_start"), \
             patch("zotpilot.tools.ingestion.time.sleep"), \
             patch("zotpilot.tools.ingestion.time.monotonic", side_effect=mono_values), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = save_from_url("https://example.com")

        assert result["success"] is False
        assert "Timeout" in result["error"]

    def test_enqueue_url_error_returns_error(self):
        url_err = urllib.error.URLError("Network unreachable")

        with patch("zotpilot.tools.ingestion.BridgeServer.is_running", return_value=True), \
             patch("zotpilot.tools.ingestion.BridgeServer.auto_start"), \
             patch("urllib.request.urlopen", side_effect=url_err):
            result = save_from_url("https://example.com")

        assert result["success"] is False
        assert "Failed to enqueue" in result["error"]

    def test_enqueue_returns_success_false_propagated(self):
        enqueue_resp = _make_urlopen_response({"request_id": "req-002"})
        poll_resp = _make_urlopen_response(
            {"success": False, "error": "translator_failed", "request_id": "req-002"},
            status=200,
        )
        config = _make_config(api_key=None)

        call_count = [0]
        def fake_urlopen(req_or_url, timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return enqueue_resp
            return poll_resp

        with patch("zotpilot.tools.ingestion.BridgeServer.is_running", return_value=True), \
             patch("zotpilot.tools.ingestion.BridgeServer.auto_start"), \
             patch("zotpilot.tools.ingestion.time.sleep"), \
             patch("zotpilot.tools.ingestion._get_config", return_value=config), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = save_from_url("https://example.com")

        assert result["success"] is False


# ---------------------------------------------------------------------------
# TestSaveUrls
# ---------------------------------------------------------------------------

class TestSaveUrls:
    def test_empty_urls_raises_tool_error(self):
        with pytest.raises(ToolError, match="cannot be empty"):
            save_urls([])

    def test_more_than_10_urls_raises_tool_error(self):
        urls = [f"https://example.com/{i}" for i in range(11)]
        with pytest.raises(ToolError, match="Too many URLs"):
            save_urls(urls)

    def test_auto_start_fails_returns_error(self):
        with patch("zotpilot.tools.ingestion.BridgeServer.is_running", return_value=False), \
             patch("zotpilot.tools.ingestion.BridgeServer.auto_start",
                   side_effect=RuntimeError("Bridge failed")):
            result = save_urls(["https://example.com/1"])

        assert result["success"] is False
        assert "Bridge failed" in result["error"]
        assert result["results"] == []

    def test_three_urls_all_succeed(self):
        urls = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
        ]
        config = _make_config(api_key=None)

        # Each enqueue returns a unique request_id; each poll returns success
        enqueue_counter = [0]
        poll_results = {
            "req-1": {"success": True, "url": urls[0], "title": "Paper 1", "request_id": "req-1"},
            "req-2": {"success": True, "url": urls[1], "title": "Paper 2", "request_id": "req-2"},
            "req-3": {"success": True, "url": urls[2], "title": "Paper 3", "request_id": "req-3"},
        }
        req_ids = ["req-1", "req-2", "req-3"]

        def fake_urlopen(req_or_url, timeout=None):
            url_str = req_or_url.full_url if hasattr(req_or_url, "full_url") else str(req_or_url)
            if "/enqueue" in url_str:
                idx = enqueue_counter[0]
                enqueue_counter[0] += 1
                return _make_urlopen_response({"request_id": req_ids[idx]})
            # Poll
            for rid, body in poll_results.items():
                if rid in url_str:
                    return _make_urlopen_response(body, status=200)
            raise urllib.error.URLError("not found")

        with patch("zotpilot.tools.ingestion.BridgeServer.is_running", return_value=True), \
             patch("zotpilot.tools.ingestion.BridgeServer.auto_start"), \
             patch("zotpilot.tools.ingestion.time.sleep"), \
             patch("zotpilot.tools.ingestion._get_config", return_value=config), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = save_urls(urls)

        assert result["total"] == 3
        assert result["succeeded"] == 3
        assert result["failed"] == 0
        assert len(result["results"]) == 3

    def test_mixed_results_enqueue_fail_and_one_success(self):
        """1 enqueue 503 + 1 poll success → succeeded=1, failed=1, total=2."""
        urls = [
            "https://example.com/fail-enqueue",
            "https://example.com/success",
        ]
        config = _make_config(api_key=None)

        enqueue_counter = [0]

        def fake_urlopen(req_or_url, timeout=None):
            url_str = req_or_url.full_url if hasattr(req_or_url, "full_url") else str(req_or_url)
            if "/enqueue" in url_str:
                idx = enqueue_counter[0]
                enqueue_counter[0] += 1
                if idx == 0:
                    raise _make_http_error(503, {
                        "error_code": "extension_not_connected",
                        "error_message": "No heartbeat.",
                    })
                else:
                    return _make_urlopen_response({"request_id": "req-success"})
            # Poll path — always return success for req-success
            if "req-success" in url_str:
                return _make_urlopen_response(
                    {"success": True, "url": urls[1], "title": "Success Paper", "request_id": "req-success"},
                    status=200,
                )
            raise urllib.error.URLError("unexpected")

        with patch("zotpilot.tools.ingestion.BridgeServer.is_running", return_value=True), \
             patch("zotpilot.tools.ingestion.BridgeServer.auto_start"), \
             patch("zotpilot.tools.ingestion.time.sleep"), \
             patch("zotpilot.tools.ingestion._get_config", return_value=config), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = save_urls(urls)

        assert result["total"] == 2
        assert result["succeeded"] == 1
        assert result["failed"] == 1
        assert any(r.get("error_code") == "extension_not_connected" for r in result["results"])

    def test_enqueue_503_url_appears_in_results(self):
        urls = ["https://example.com/only"]
        config = _make_config(api_key=None)

        def fake_urlopen(req_or_url, timeout=None):
            raise _make_http_error(503, {
                "error_code": "extension_not_connected",
                "error_message": "No heartbeat.",
            })

        with patch("zotpilot.tools.ingestion.BridgeServer.is_running", return_value=True), \
             patch("zotpilot.tools.ingestion.BridgeServer.auto_start"), \
             patch("zotpilot.tools.ingestion.time.sleep"), \
             patch("zotpilot.tools.ingestion._get_config", return_value=config), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = save_urls(urls)

        assert result["total"] == 1
        assert result["failed"] == 1
        assert result["results"][0]["url"] == "https://example.com/only"
        assert result["results"][0]["error_code"] == "extension_not_connected"

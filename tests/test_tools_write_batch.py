"""Tests for batch write operations (P2-12)."""
import pytest
from unittest.mock import MagicMock, patch

from zotpilot.tools.write_ops import (
    batch_add_tags, batch_set_tags, batch_remove_tags,
    batch_add_to_collection, batch_remove_from_collection,
    _BATCH_MAX,
)


@pytest.fixture
def mock_writer():
    writer = MagicMock()
    with patch("zotpilot.tools.write_ops._get_writer", return_value=writer):
        yield writer


class TestBatchAddTags:
    def test_happy(self, mock_writer):
        items = [
            {"item_key": "A", "tags": ["ml"]},
            {"item_key": "B", "tags": ["dl"]},
            {"item_key": "C", "tags": ["nlp"]},
        ]
        result = batch_add_tags(items)
        assert result["total"] == 3
        assert result["succeeded"] == 3
        assert result["failed"] == 0
        assert mock_writer.add_item_tags.call_count == 3

    def test_partial_fail(self, mock_writer):
        mock_writer.add_item_tags.side_effect = [None, Exception("API error")]
        items = [
            {"item_key": "A", "tags": ["ml"]},
            {"item_key": "B", "tags": ["dl"]},
        ]
        result = batch_add_tags(items)
        assert result["succeeded"] == 1
        assert result["failed"] == 1
        assert result["results"][1]["error"] == "API error"

    def test_empty(self, mock_writer):
        result = batch_add_tags([])
        assert result["total"] == 0
        assert result["succeeded"] == 0

    def test_over_limit(self, mock_writer):
        from zotpilot.state import ToolError
        items = [{"item_key": f"K{i}", "tags": ["t"]} for i in range(_BATCH_MAX + 1)]
        with pytest.raises(ToolError, match="exceeds limit"):
            batch_add_tags(items)

    def test_missing_field(self, mock_writer):
        items = [{"item_key": "A"}]  # missing tags
        result = batch_add_tags(items)
        assert result["results"][0]["success"] is False
        assert "Missing" in result["results"][0]["error"]


class TestBatchSetTags:
    def test_happy(self, mock_writer):
        items = [{"item_key": "A", "tags": ["new"]}]
        result = batch_set_tags(items)
        assert result["succeeded"] == 1
        mock_writer.set_item_tags.assert_called_once_with("A", ["new"])


class TestBatchRemoveTags:
    def test_happy(self, mock_writer):
        items = [{"item_key": "A", "tags": ["old"]}]
        result = batch_remove_tags(items)
        assert result["succeeded"] == 1
        mock_writer.remove_item_tags.assert_called_once_with("A", ["old"])


class TestBatchAddToCollection:
    def test_happy(self, mock_writer):
        result = batch_add_to_collection(item_keys=["A", "B"], collection_key="COL1")
        assert result["total"] == 2
        assert result["succeeded"] == 2
        assert mock_writer.add_to_collection.call_count == 2

    def test_over_limit(self, mock_writer):
        from zotpilot.state import ToolError
        keys = [f"K{i}" for i in range(_BATCH_MAX + 1)]
        with pytest.raises(ToolError, match="exceeds limit"):
            batch_add_to_collection(item_keys=keys, collection_key="COL1")

    def test_invalidates_cache(self, mock_writer):
        with patch("zotpilot.tools.write_ops._invalidate_collection_cache") as mock_inv:
            batch_add_to_collection(item_keys=["A"], collection_key="COL1")
            mock_inv.assert_called_once()


class TestBatchRemoveFromCollection:
    def test_happy(self, mock_writer):
        result = batch_remove_from_collection(item_keys=["A", "B"], collection_key="COL1")
        assert result["total"] == 2
        assert result["succeeded"] == 2

    def test_invalidates_cache(self, mock_writer):
        with patch("zotpilot.tools.write_ops._invalidate_collection_cache") as mock_inv:
            batch_remove_from_collection(item_keys=["A"], collection_key="COL1")
            mock_inv.assert_called_once()

"""Tests for profile_library MCP tool."""
import pytest
from unittest.mock import MagicMock, patch, mock_open


def _make_item(key, year, tags="", collections=""):
    """Create a minimal mock ZoteroItem."""
    item = MagicMock()
    item.item_key = key
    item.year = year
    item.tags = tags
    item.collections = collections
    return item


class TestProfileLibraryWithItems:
    @patch("zotpilot.tools.library._get_store_optional")
    @patch("zotpilot.tools.library._get_zotero")
    def test_profile_library_with_items(self, mock_get_zotero, mock_get_store_opt):
        from zotpilot.tools.library import profile_library

        mock_zotero = MagicMock()
        mock_zotero.get_all_items_with_pdfs.return_value = [
            _make_item("KEY1", 2023, tags="machine learning; NLP", collections="AI"),
            _make_item("KEY2", 2024, tags="NLP", collections="AI"),
            _make_item("KEY3", 2022, tags="machine learning", collections="Methods"),
        ]
        mock_zotero.get_all_tags.return_value = [
            {"name": "machine learning", "count": 2},
            {"name": "NLP", "count": 2},
        ]
        mock_zotero.get_all_collections.return_value = [
            {"key": "COL1", "name": "AI", "parent_key": None},
            {"key": "COL2", "name": "Methods", "parent_key": None},
        ]
        mock_get_zotero.return_value = mock_zotero

        mock_store = MagicMock()
        mock_store.get_indexed_doc_ids.return_value = {"KEY1", "KEY2"}
        mock_get_store_opt.return_value = mock_store

        result = profile_library()

        assert result["total_items"] == 3
        assert result["year_distribution"] == {"2022": 1, "2023": 1, "2024": 1}
        assert "machine learning" in result["top_tags"]
        assert "NLP" in result["top_tags"]
        assert len(result["top_collections"]) >= 1
        # AI collection has 2 items
        ai_col = next(c for c in result["top_collections"] if c["name"] == "AI")
        assert ai_col["count"] == 2
        assert ai_col["key"] == "COL1"
        assert result["topic_density"]["indexed"] is True
        assert result["topic_density"]["doc_count"] == 2


class TestProfileLibraryNoRagMode:
    @patch("zotpilot.tools.library._get_store_optional")
    @patch("zotpilot.tools.library._get_zotero")
    def test_profile_library_no_rag_mode(self, mock_get_zotero, mock_get_store_opt):
        from zotpilot.tools.library import profile_library

        mock_zotero = MagicMock()
        mock_zotero.get_all_items_with_pdfs.return_value = [
            _make_item("KEY1", 2023, tags="deep learning", collections="AI"),
        ]
        mock_zotero.get_all_tags.return_value = [
            {"name": "deep learning", "count": 1},
        ]
        mock_zotero.get_all_collections.return_value = [
            {"key": "COL1", "name": "AI", "parent_key": None},
        ]
        mock_get_zotero.return_value = mock_zotero

        # No-RAG mode: store is None
        mock_get_store_opt.return_value = None

        result = profile_library()

        assert result["topic_density"] == {"indexed": False}
        assert result["total_items"] == 1
        assert len(result["top_tags"]) >= 1


class TestProfileLibraryEmptyLibrary:
    @patch("zotpilot.tools.library._get_store_optional")
    @patch("zotpilot.tools.library._get_zotero")
    def test_profile_library_empty_library(self, mock_get_zotero, mock_get_store_opt):
        from zotpilot.tools.library import profile_library

        mock_zotero = MagicMock()
        mock_zotero.get_all_items_with_pdfs.return_value = []
        mock_zotero.get_all_tags.return_value = []
        mock_zotero.get_all_collections.return_value = []
        mock_get_zotero.return_value = mock_zotero
        mock_get_store_opt.return_value = None

        result = profile_library()

        assert result["total_items"] == 0
        assert result["year_distribution"] == {}
        assert result["top_tags"] == []
        assert result["top_collections"] == []


class TestProfileLibraryExistingProfile:
    @patch("zotpilot.tools.library._get_store_optional")
    @patch("zotpilot.tools.library._get_zotero")
    def test_profile_library_existing_profile(self, mock_get_zotero, mock_get_store_opt, tmp_path):
        from zotpilot.tools.library import profile_library

        mock_zotero = MagicMock()
        mock_zotero.get_all_items_with_pdfs.return_value = []
        mock_zotero.get_all_tags.return_value = []
        mock_zotero.get_all_collections.return_value = []
        mock_get_zotero.return_value = mock_zotero
        mock_get_store_opt.return_value = None

        profile_content = "# My Research Profile\n\nFocused on NLP and ML."
        profile_file = tmp_path / "ZOTPILOT.md"
        profile_file.write_text(profile_content, encoding="utf-8")

        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value=profile_content):
            result = profile_library()

        assert result["existing_profile"] == profile_content

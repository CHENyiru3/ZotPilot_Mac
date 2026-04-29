"""Tests for ChromaDB vector store."""

from unittest.mock import patch

import pytest

from zotpilot.vector_store import VectorStore


@pytest.fixture
def store(tmp_path, mock_embedder):
    """Create a VectorStore with in-memory ChromaDB."""
    return VectorStore(tmp_path / "chroma", mock_embedder)


@pytest.fixture
def populated_store(store, sample_chunks):
    """Store with some chunks added."""
    doc_meta = {
        "title": "Test Paper",
        "authors": "Test Author",
        "year": 2020,
        "citation_key": "test2020",
        "publication": "Test Journal",
        "doi": "10.1234/test",
        "tags": "ml; ai",
        "collections": "Test Collection",
        "journal_quartile": "Q1",
        "pdf_hash": "abc123",
        "quality_grade": "A",
    }
    store.add_chunks("TEST001", doc_meta, sample_chunks)
    return store


class TestVectorStore:
    def test_add_and_count(self, populated_store):
        assert populated_store.count() == 3

    def test_get_indexed_doc_ids(self, populated_store):
        ids = populated_store.get_indexed_doc_ids()
        assert "TEST001" in ids

    def test_delete_document(self, populated_store):
        populated_store.delete_document("TEST001")
        assert populated_store.count() == 0

    def test_get_document_meta(self, populated_store):
        meta = populated_store.get_document_meta("TEST001")
        assert meta is not None
        assert meta["doc_title"] == "Test Paper"
        assert meta["year"] == 2020

    def test_get_document_meta_not_found(self, store):
        meta = store.get_document_meta("NONEXISTENT")
        assert meta is None

    def test_get_adjacent_chunks(self, populated_store):
        chunks = populated_store.get_adjacent_chunks("TEST001", 1, window=1)
        assert len(chunks) >= 1
        # Should include the center and at least one neighbor
        indices = {c.metadata["chunk_index"] for c in chunks}
        assert 1 in indices

    def test_search(self, populated_store):
        results = populated_store.search("neural networks", top_k=3)
        assert len(results) <= 3
        for r in results:
            assert r.score >= 0

    def test_add_chunks_stores_unit_metadata_and_contextual_embedding(self, store, sample_chunks):
        doc_meta = {
            "title": "Layered Retrieval",
            "authors": "Chen, Y.",
            "year": 2026,
            "citation_key": "chen2026",
            "publication": "Test Journal",
        }

        store.add_chunks("DOC1", doc_meta, sample_chunks[:1])

        embedded_texts = store.embedder.embed.call_args.args[0]
        assert embedded_texts[0].startswith("Unit type: chunk\nTitle: Layered Retrieval")
        assert "Section: introduction" in embedded_texts[0]
        row = store.collection.get(ids=["DOC1_chunk_0000"], include=["metadatas"])
        metadata = row["metadatas"][0]
        assert metadata["unit_id"] == "DOC1_chunk_0000"
        assert metadata["unit_type"] == "chunk"
        assert metadata["content_type"] == "text"
        assert metadata["parent_article_id"] == "DOC1"

    def test_add_article_and_sections_are_document_units(self, store):
        doc_meta = {
            "title": "Layered Retrieval",
            "authors": "Chen, Y.",
            "year": 2026,
            "citation_key": "chen2026",
            "publication": "Test Journal",
        }
        section_text = "Results " + ("important finding " * 30)

        store.add_article("DOC1", doc_meta, "Article summary text")
        store.add_sections(
            "DOC1",
            doc_meta,
            [{
                "label": "results",
                "heading": "Results",
                "confidence": 0.9,
                "page_num": 3,
                "text": section_text,
            }],
        )

        rows = store.collection.get(
            ids=["DOC1_article", "DOC1_section_000"],
            include=["metadatas", "documents"],
        )
        by_id = dict(zip(rows["ids"], rows["metadatas"], strict=True))
        assert by_id["DOC1_article"]["unit_type"] == "article"
        assert by_id["DOC1_section_000"]["unit_type"] == "section"
        assert by_id["DOC1_section_000"]["parent_section_id"] == "DOC1_section_000"
        assert store.get_indexed_doc_ids() == {"DOC1"}

    def test_doc_id_parser_handles_layered_unit_ids(self):
        assert VectorStore._doc_id_from_chunk_id("ABC_article") == "ABC"
        assert VectorStore._doc_id_from_chunk_id("ABC_section_000") == "ABC"
        assert VectorStore._doc_id_from_chunk_id("ABC_chunk_0001") == "ABC"

    def test_empty_store_search(self, store):
        results = store.search("anything", top_k=5)
        assert results == []

    def test_corrupt_db_is_quarantined_when_probe_fails(self, tmp_path, mock_embedder):
        db_path = tmp_path / "chroma"
        db_path.mkdir()
        (db_path / "chroma.sqlite3").write_text("broken")

        with (
            patch("zotpilot.vector_store._probe_chroma_db_access", return_value=False),
        ):
            store = VectorStore(db_path, mock_embedder)

        backups = list(tmp_path.glob("chroma.corrupt-*"))
        assert len(backups) == 1
        assert store.db_path.exists()

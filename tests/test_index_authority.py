from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from zotpilot.index_authority import (
    authoritative_indexed_doc_ids,
    current_library_pdf_doc_ids,
    orphaned_index_doc_ids,
    reconcile_orphaned_index_docs,
)


def _item(key: str, has_pdf: bool = True):
    pdf_path = Path(f"/tmp/{key}.pdf") if has_pdf else None
    if pdf_path is not None:
        exists = MagicMock(return_value=True)
        pdf_path = SimpleNamespace(exists=exists)
    return SimpleNamespace(item_key=key, pdf_path=pdf_path)


def test_current_library_pdf_doc_ids_only_keeps_resolved_pdfs():
    zotero = MagicMock()
    zotero.get_all_items_with_pdfs.return_value = [
        _item("DOC1", has_pdf=True),
        _item("DOC2", has_pdf=False),
    ]

    assert current_library_pdf_doc_ids(zotero) == {"DOC1"}


def test_authoritative_indexed_doc_ids_excludes_orphans():
    store = MagicMock()
    store.get_indexed_doc_ids.return_value = {"DOC1", "DOC2", "DOC3"}

    assert authoritative_indexed_doc_ids(store, {"DOC1", "DOC3"}) == {"DOC1", "DOC3"}
    assert orphaned_index_doc_ids(store, {"DOC1", "DOC3"}) == {"DOC2"}


def test_reconcile_orphaned_index_docs_deletes_missing_docs():
    store = MagicMock()
    store.get_indexed_doc_ids.return_value = {"DOC1", "DOC2", "DOC3"}

    result = reconcile_orphaned_index_docs(store, {"DOC1"})

    assert result == {
        "orphaned_doc_ids": ["DOC2", "DOC3"],
        "deleted_count": 2,
    }
    store.delete_document.assert_any_call("DOC2")
    store.delete_document.assert_any_call("DOC3")

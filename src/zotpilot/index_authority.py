"""Helpers for reconciling Chroma index state with the current Zotero PDF library."""

from collections.abc import Iterable


def current_library_pdf_doc_ids(zotero) -> set[str]:
    """Return current Zotero item keys that still have resolved PDF files."""
    doc_ids: set[str] = set()
    for item in zotero.get_all_items_with_pdfs():
        if item.pdf_path and item.pdf_path.exists():
            doc_ids.add(item.item_key)
    return doc_ids


def authoritative_indexed_doc_ids(store, current_doc_ids: Iterable[str]) -> set[str]:
    """Return indexed doc IDs that still exist in the current Zotero PDF library."""
    current = set(current_doc_ids)
    return set(store.get_indexed_doc_ids()) & current


def orphaned_index_doc_ids(store, current_doc_ids: Iterable[str]) -> set[str]:
    """Return indexed doc IDs that are no longer present in the current Zotero PDF library."""
    current = set(current_doc_ids)
    return set(store.get_indexed_doc_ids()) - current


def reconcile_orphaned_index_docs(store, current_doc_ids: Iterable[str]) -> dict:
    """Delete orphaned indexed docs from Chroma and return a summary."""
    orphaned = sorted(orphaned_index_doc_ids(store, current_doc_ids))
    for doc_id in orphaned:
        store.delete_document(doc_id)
    return {
        "orphaned_doc_ids": orphaned,
        "deleted_count": len(orphaned),
    }

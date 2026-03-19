"""Library write operations via Pyzotero Web API."""
from typing import TypedDict

from ..state import mcp, _get_writer, ToolError
from .library import _invalidate_collection_cache


class TagItem(TypedDict):
    item_key: str
    tags: list[str]


_BATCH_MAX = 100


@mcp.tool()
def set_item_tags(item_key: str, tags: list[str]) -> dict:
    """
    Replace ALL tags on a Zotero item with a new set.

    WARNING: This overwrites existing tags completely.
    Use add_item_tags to append without removing existing tags.

    Args:
        item_key: Zotero item key (e.g. "FRF9ACAJ")
        tags: New tag list (replaces everything)

    Returns:
        {"success": true, "item_key": ..., "tags": [...]}
    """
    _get_writer().set_item_tags(item_key, tags)
    return {"success": True, "item_key": item_key, "tags": tags}


@mcp.tool()
def add_item_tags(item_key: str, tags: list[str]) -> dict:
    """
    Add tags to a Zotero item WITHOUT removing existing tags.

    Safe to call multiple times -- existing tags are preserved.

    Args:
        item_key: Zotero item key (e.g. "FRF9ACAJ")
        tags: Tags to add

    Returns:
        {"success": true, "item_key": ..., "added": [...]}
    """
    _get_writer().add_item_tags(item_key, tags)
    return {"success": True, "item_key": item_key, "added": tags}


@mcp.tool()
def remove_item_tags(item_key: str, tags: list[str]) -> dict:
    """
    Remove specific tags from a Zotero item.

    Tags not present on the item are silently ignored.

    Args:
        item_key: Zotero item key (e.g. "FRF9ACAJ")
        tags: Tags to remove

    Returns:
        {"success": true, "item_key": ..., "removed": [...]}
    """
    _get_writer().remove_item_tags(item_key, tags)
    return {"success": True, "item_key": item_key, "removed": tags}


@mcp.tool()
def add_to_collection(item_key: str, collection_key: str) -> dict:
    """
    Add a paper to a Zotero collection (folder).

    Non-destructive: paper remains in any collections it's already in.
    Use list_collections() to find collection keys.

    Args:
        item_key: Zotero item key (e.g. "FRF9ACAJ")
        collection_key: Target collection key (from list_collections)

    Returns:
        {"success": true, "item_key": ..., "collection_key": ...}
    """
    _get_writer().add_to_collection(item_key, collection_key)
    _invalidate_collection_cache()
    return {"success": True, "item_key": item_key, "collection_key": collection_key}


@mcp.tool()
def remove_from_collection(item_key: str, collection_key: str) -> dict:
    """
    Remove a paper from a Zotero collection.

    The paper remains in the library and any other collections it belongs to.

    Args:
        item_key: Zotero item key (e.g. "FRF9ACAJ")
        collection_key: Collection key to remove from (from list_collections)

    Returns:
        {"success": true, "item_key": ..., "collection_key": ...}
    """
    _get_writer().remove_from_collection(item_key, collection_key)
    _invalidate_collection_cache()
    return {"success": True, "item_key": item_key, "collection_key": collection_key}


@mcp.tool()
def create_collection(name: str, parent_key: str | None = None) -> dict:
    """
    Create a new Zotero collection (folder).

    Args:
        name: Display name for the new collection
        parent_key: Key of parent collection for nested folders (None = top-level)

    Returns:
        {"key": ..., "name": ..., "parent_key": ...}
    """
    result = _get_writer().create_collection(name, parent_key)
    _invalidate_collection_cache()
    return result


def _extract_tag_item(item) -> tuple[str | None, list[str] | None]:
    """Extract item_key and tags from a TagItem (dict at runtime)."""
    item_key = item.get("item_key") if isinstance(item, dict) else getattr(item, "item_key", None)
    tags = item.get("tags") if isinstance(item, dict) else getattr(item, "tags", None)
    return item_key, tags


def _batch_tag_result(items: list, operation):
    """Run a per-item tag operation and collect results."""
    if len(items) > _BATCH_MAX:
        raise ToolError(f"Batch size {len(items)} exceeds limit of {_BATCH_MAX}")
    writer = _get_writer()
    results = []
    for item in items:
        item_key, tags = _extract_tag_item(item)
        if not item_key or tags is None:
            results.append({"item_key": item_key or "unknown", "success": False, "error": "Missing item_key or tags"})
            continue
        try:
            operation(writer, item_key, tags)
            results.append({"item_key": item_key, "success": True})
        except Exception as e:
            results.append({"item_key": item_key, "success": False, "error": str(e)})
    succeeded = sum(1 for r in results if r["success"])
    return {"total": len(items), "succeeded": succeeded, "failed": len(items) - succeeded, "results": results}


@mcp.tool()
def batch_add_tags(items: list[dict]) -> dict:
    """Add tags to multiple items in one call.

    Partial failures are reported per-item (no rollback).
    Maximum 100 items per call.

    Args:
        items: List of {item_key, tags} objects

    Returns:
        {total, succeeded, failed, results: [{item_key, success, error?}]}
    """
    return _batch_tag_result(items, lambda w, k, t: w.add_item_tags(k, t))


@mcp.tool()
def batch_set_tags(items: list[dict]) -> dict:
    """Replace all tags on multiple items in one call.

    WARNING: This overwrites existing tags completely for each item.
    Partial failures are reported per-item (no rollback).
    Maximum 100 items per call.

    Args:
        items: List of {item_key, tags} objects

    Returns:
        {total, succeeded, failed, results: [{item_key, success, error?}]}
    """
    return _batch_tag_result(items, lambda w, k, t: w.set_item_tags(k, t))


@mcp.tool()
def batch_remove_tags(items: list[dict]) -> dict:
    """Remove specific tags from multiple items in one call.

    Tags not present on an item are silently ignored.
    Partial failures are reported per-item (no rollback).
    Maximum 100 items per call.

    Args:
        items: List of {item_key, tags} objects

    Returns:
        {total, succeeded, failed, results: [{item_key, success, error?}]}
    """
    return _batch_tag_result(items, lambda w, k, t: w.remove_item_tags(k, t))


@mcp.tool()
def batch_add_to_collection(item_keys: list[str], collection_key: str) -> dict:
    """Add multiple items to a collection in one call.

    Non-destructive: items remain in any collections they're already in.
    Partial failures are reported per-item (no rollback).
    Maximum 100 items per call.

    Args:
        item_keys: List of Zotero item keys
        collection_key: Target collection key

    Returns:
        {total, succeeded, failed, results: [{item_key, success, error?}]}
    """
    if len(item_keys) > _BATCH_MAX:
        raise ToolError(f"Batch size {len(item_keys)} exceeds limit of {_BATCH_MAX}")
    writer = _get_writer()
    results = []
    for key in item_keys:
        try:
            writer.add_to_collection(key, collection_key)
            results.append({"item_key": key, "success": True})
        except Exception as e:
            results.append({"item_key": key, "success": False, "error": str(e)})
    _invalidate_collection_cache()
    succeeded = sum(1 for r in results if r["success"])
    return {"total": len(item_keys), "succeeded": succeeded, "failed": len(item_keys) - succeeded, "results": results}


@mcp.tool()
def batch_remove_from_collection(item_keys: list[str], collection_key: str) -> dict:
    """Remove multiple items from a collection in one call.

    Items remain in the library and any other collections.
    Partial failures are reported per-item (no rollback).
    Maximum 100 items per call.

    Args:
        item_keys: List of Zotero item keys
        collection_key: Collection key to remove from

    Returns:
        {total, succeeded, failed, results: [{item_key, success, error?}]}
    """
    if len(item_keys) > _BATCH_MAX:
        raise ToolError(f"Batch size {len(item_keys)} exceeds limit of {_BATCH_MAX}")
    writer = _get_writer()
    results = []
    for key in item_keys:
        try:
            writer.remove_from_collection(key, collection_key)
            results.append({"item_key": key, "success": True})
        except Exception as e:
            results.append({"item_key": key, "success": False, "error": str(e)})
    _invalidate_collection_cache()
    succeeded = sum(1 for r in results if r["success"])
    return {"total": len(item_keys), "succeeded": succeeded, "failed": len(item_keys) - succeeded, "results": results}

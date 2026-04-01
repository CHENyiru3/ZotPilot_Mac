"""Library write operations via Pyzotero Web API."""
import json
import logging
from typing import Annotated, Literal, TypedDict

from pydantic import Field

from ..state import ToolError, _get_writer, _get_zotero, mcp
from .library import _invalidate_collection_cache

logger = logging.getLogger(__name__)


def _coerce_list(value) -> list:
    """Coerce a value to list, parsing JSON string if needed (Claude Code MCP client quirk)."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []


class TagItem(TypedDict):
    item_key: str
    tags: list[str]


_BATCH_MAX = 100


@mcp.tool()
def set_item_tags(
    item_key: Annotated[str, Field(description="Zotero item key")],
    tags: Annotated[list[str], Field(description="New tag list (replaces all existing)")],
) -> dict:
    """Replace ALL tags on an item (destructive). Use this after ingest to clear
    publisher auto-tags and set clean tags from library vocabulary.
    Call list_tags() first to see available tags."""
    tags = _coerce_list(tags)
    _get_writer().set_item_tags(item_key, tags)
    return {"success": True, "item_key": item_key, "tags": tags}


@mcp.tool()
def add_item_tags(
    item_key: Annotated[str, Field(description="Zotero item key")],
    tags: Annotated[list[str], Field(description="Tags to add")],
    allow_new: Annotated[
        bool,
        Field(description="When false, reject tags not already in the library vocabulary"),
    ] = False,
) -> dict:
    """Add tags to an item without removing existing ones.

    By default (allow_new=False), rejects tags not in the library's existing
    vocabulary. Call list_tags() first to see available tags. Set allow_new=True
    only with explicit user approval to create new tags.
    """
    tags = _coerce_list(tags)
    if not allow_new:
        existing_tags = {t["name"] for t in _get_zotero().get_all_tags()}
        new_tags = [tag for tag in tags if tag not in existing_tags]
        if new_tags:
            return {
                "success": False,
                "error": "new_tags_rejected",
                "rejected_tags": new_tags,
                "message": (
                    f"Tags {new_tags} not in library vocabulary. "
                    "Call list_tags() to see existing tags, or set allow_new=True "
                    "with explicit user approval to create new tags."
                ),
                "existing_tag_count": len(existing_tags),
            }
    _get_writer().add_item_tags(item_key, tags)
    return {"success": True, "item_key": item_key, "added": tags}


@mcp.tool()
def remove_item_tags(
    item_key: Annotated[str, Field(description="Zotero item key")],
    tags: Annotated[list[str], Field(description="Tags to remove")],
) -> dict:
    """Remove specific tags from an item. Missing tags silently ignored."""
    tags = _coerce_list(tags)
    _get_writer().remove_item_tags(item_key, tags)
    return {"success": True, "item_key": item_key, "removed": tags}


@mcp.tool()
def add_to_collection(
    item_key: Annotated[str, Field(description="Zotero item key")],
    collection_key: Annotated[str, Field(description="Target collection key from list_collections")],
    auto_cleanup_inbox: Annotated[
        bool,
        Field(description="When true, remove the paper from INBOX after adding to target collection"),
    ] = True,
) -> dict:
    """Add a paper to a collection. When auto_cleanup_inbox is True (default),
    automatically removes the paper from INBOX if it was there."""
    writer = _get_writer()
    writer.add_to_collection(item_key, collection_key)
    _invalidate_collection_cache()
    inbox_removed = False
    if auto_cleanup_inbox:
        try:
            item_collections = _get_zotero().get_item_collections(item_key)
            inbox_keys = [
                collection["key"]
                for collection in item_collections
                if collection.get("name", "").upper() == "INBOX" and collection["key"] != collection_key
            ]
            for inbox_key in inbox_keys:
                writer.remove_from_collection(item_key, inbox_key)
                inbox_removed = True
            _invalidate_collection_cache()
        except Exception as exc:
            logger.warning("INBOX auto-cleanup failed for %s: %s", item_key, exc)

    return {
        "success": True,
        "item_key": item_key,
        "collection_key": collection_key,
        "inbox_removed": inbox_removed,
        "_instruction": (
            "Paper moved to collection and removed from INBOX. Classify to deepest matching sub-collection."
            if inbox_removed
            else "Classify to the deepest matching sub-collection, not the root collection."
        ),
    }


@mcp.tool()
def remove_from_collection(
    item_key: Annotated[str, Field(description="Zotero item key")],
    collection_key: Annotated[str, Field(description="Collection key to remove from")],
) -> dict:
    """Remove a paper from a collection. Stays in library and other collections."""
    _get_writer().remove_from_collection(item_key, collection_key)
    _invalidate_collection_cache()
    return {"success": True, "item_key": item_key, "collection_key": collection_key}


@mcp.tool()
def create_collection(
    name: Annotated[str, Field(description="Display name for the collection")],
    parent_key: Annotated[str | None, Field(description="Parent collection key for nesting, None for top-level")] = None,  # noqa: E501
) -> dict:
    """Create a new Zotero collection (folder)."""
    result = _get_writer().create_collection(name, parent_key)
    _invalidate_collection_cache()
    return result


@mcp.tool()
def create_note(
    item_key: Annotated[str, Field(description="Parent item key")],
    content: Annotated[str, Field(description="Note content (plain text or HTML)")],
    title: Annotated[str | None, Field(description="Note title (prepended as heading)")] = None,
    tags: Annotated[list[str] | None, Field(description="Tags for the note")] = None,
) -> dict:
    """Create a child note on a Zotero item. Requires ZOTERO_API_KEY."""
    if tags is not None:
        tags = _coerce_list(tags) or None
    return _get_writer().create_note(item_key, content, title=title, tags=tags)


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
def batch_tags(
    action: Annotated[Literal["add", "set", "remove"], Field(description="add=append, set=replace all (destructive), remove=delete specific tags")],  # noqa: E501
    items: Annotated[list[dict], Field(description="List of {item_key, tags} objects. Max 100.")],
    allow_new: Annotated[
        bool,
        Field(description="When action='add', reject tags not already in the library vocabulary unless true"),
    ] = False,
) -> dict:
    """Batch tag operation on multiple items. Partial failures reported per-item."""
    items = _coerce_list(items)
    if len(items) > _BATCH_MAX:
        raise ToolError(f"Batch size {len(items)} exceeds limit of {_BATCH_MAX}")
    if action == "add" and not allow_new:
        existing_tags = {t["name"] for t in _get_zotero().get_all_tags()}
        validated_items = []
        rejected = []
        for item in items:
            item_key, tags = _extract_tag_item(item)
            if tags is None:
                rejected.append(
                    {
                        "item_key": item_key or "unknown",
                        "success": False,
                        "error": "Missing item_key or tags",
                    }
                )
                continue
            tags = _coerce_list(tags)
            new_tags = [tag for tag in tags if tag not in existing_tags]
            if new_tags:
                rejected.append(
                    {
                        "item_key": item_key or "unknown",
                        "success": False,
                        "error": "new_tags_rejected",
                        "rejected_tags": new_tags,
                    }
                )
                continue
            validated_items.append({"item_key": item_key, "tags": tags})
        batch_result = _batch_tag_result(validated_items, lambda w, k, t: w.add_item_tags(k, t))
        batch_result["results"].extend(rejected)
        batch_result["total"] = len(items)
        batch_result["succeeded"] = sum(1 for r in batch_result["results"] if r["success"])
        batch_result["failed"] = len(items) - batch_result["succeeded"]
        return batch_result
    ops = {
        "add": lambda w, k, t: w.add_item_tags(k, t),
        "set": lambda w, k, t: w.set_item_tags(k, t),
        "remove": lambda w, k, t: w.remove_item_tags(k, t),
    }
    return _batch_tag_result(items, ops[action])


@mcp.tool()
def batch_collections(
    action: Annotated[Literal["add", "remove"], Field(description="add=add to collection, remove=remove from collection")],  # noqa: E501
    item_keys: Annotated[list[str], Field(description="Zotero item keys. Max 100.")],
    collection_key: Annotated[str, Field(description="Target collection key")],
) -> dict:
    """Batch collection operation on multiple items. Partial failures reported per-item."""
    item_keys = _coerce_list(item_keys)
    if len(item_keys) > _BATCH_MAX:
        raise ToolError(f"Batch size {len(item_keys)} exceeds limit of {_BATCH_MAX}")
    writer = _get_writer()
    op = writer.add_to_collection if action == "add" else writer.remove_from_collection
    results = []
    for key in item_keys:
        try:
            op(key, collection_key)
            results.append({"item_key": key, "success": True})
        except Exception as e:
            results.append({"item_key": key, "success": False, "error": str(e)})
    _invalidate_collection_cache()
    succeeded = sum(1 for r in results if r["success"])
    return {"total": len(item_keys), "succeeded": succeeded, "failed": len(item_keys) - succeeded, "results": results}

"""Ingestion MCP tools: search_academic_databases + ingest_by_identifiers (v0.5.0)."""
from __future__ import annotations

import logging
import threading
from typing import Annotated, Literal

import httpx
from pydantic import Field

from ...bridge import DEFAULT_PORT, BridgeServer
from ...state import (
    ToolError,
    _get_config,
    _get_writer,
    _get_zotero,
    mcp,
    register_reset_callback,
)
from ..profiles import tool_tags
from . import connector, search

logger = logging.getLogger(__name__)
_writer_lock = threading.Lock()

# ---------------------------------------------------------------------------
# INBOX collection cache
# ---------------------------------------------------------------------------
_inbox_collection_key: str | None = None
_inbox_lock = threading.Lock()
_INBOX_COLLECTION_NAME = "INBOX"


def _clear_inbox_cache() -> None:
    global _inbox_collection_key
    _inbox_collection_key = None
    import sys as _sys
    _pkg = _sys.modules.get("zotpilot.tools.ingestion")
    if _pkg is not None and hasattr(_pkg, "_inbox_collection_key"):
        _pkg._inbox_collection_key = None  # type: ignore[attr-defined]


register_reset_callback(_clear_inbox_cache)


def _ensure_inbox_collection() -> str | None:
    """Return the INBOX collection key, creating it if absent when possible."""
    global _inbox_collection_key
    if _inbox_collection_key is not None:
        return _inbox_collection_key
    with _inbox_lock:
        if _inbox_collection_key is not None:
            return _inbox_collection_key
        try:
            writer = _get_writer()
        except Exception:
            return None
        if not _get_config().zotero_api_key:
            return None
        try:
            with _writer_lock:
                collections = writer._zot.collections()
            for coll in collections:
                data = coll.get("data", {})
                if data.get("name") == _INBOX_COLLECTION_NAME:
                    _inbox_collection_key = data.get("key") or coll.get("key")
                    return _inbox_collection_key
            with _writer_lock:
                response = writer._zot.create_collections([{"name": _INBOX_COLLECTION_NAME}])
            if response and "successful" in response:
                for value in response["successful"].values():
                    _inbox_collection_key = value.get("key") or value.get("data", {}).get("key")
                    if _inbox_collection_key:
                        return _inbox_collection_key
            with _writer_lock:
                collections = writer._zot.collections()
            for coll in collections:
                data = coll.get("data", {})
                if data.get("name") == _INBOX_COLLECTION_NAME:
                    _inbox_collection_key = data.get("key") or coll.get("key")
                    return _inbox_collection_key
        except Exception as exc:
            logger.warning("_ensure_inbox_collection failed: %s", exc)
    return None


def _lookup_local_item_key_by_doi(doi: str | None) -> str | None:
    """Check if a DOI already exists in the local Zotero library."""
    if not doi:
        return None
    try:
        _get_zotero()
        return _get_zotero().get_item_key_by_doi(doi)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# MCP Tool: search_academic_databases
# ---------------------------------------------------------------------------

@mcp.tool(tags=tool_tags("core", "ingestion"))
def search_academic_databases(
    query: Annotated[
        str,
        Field(description=(
            "Search query. MUST be structured (not fuzzy bag-of-words) UNLESS "
            "you also pass concepts/venue/institutions. Allowed forms: DOI "
            "('10.xxx/yyy'), author-anchored ('author:Radford CLIP'), "
            "quoted phrase ('\"visual instruction tuning\"'), boolean "
            "('\"LLaVA\" OR \"Flamingo\"'). Pass '' when filtering purely by "
            "concept/venue."
        )),
    ],
    limit: Annotated[int, Field(ge=1, le=100, description="Max results per page")] = 20,
    year_min: Annotated[int | None, Field(description="Minimum publication year")] = None,
    year_max: Annotated[int | None, Field(description="Maximum publication year")] = None,
    min_citations: Annotated[
        int | None,
        Field(description="Minimum citation count (use to cut long tail)"),
    ] = None,
    sort_by: Annotated[
        Literal["relevance", "citations", "date"],
        Field(description="Sort order"),
    ] = "relevance",
    oa_only: Annotated[
        bool,
        Field(description="Restrict to open access papers"),
    ] = False,
    concepts: Annotated[
        list[str] | None,
        Field(description=(
            "Concept/topic names (human-readable, resolved server-side). "
            "Examples: ['Computer vision', 'Natural language processing']. "
            "Use to anchor topic searches and escape bag-of-words rejection."
        )),
    ] = None,
    venue: Annotated[
        str | None,
        Field(description=(
            "Venue/journal/conference name (resolved server-side). "
            "Examples: 'CVPR', 'NeurIPS', 'IEEE TPAMI', 'ICLR'."
        )),
    ] = None,
    institutions: Annotated[
        list[str] | None,
        Field(description=(
            "Institution names (resolved server-side). "
            "Examples: ['Stanford University', 'MIT', 'Google DeepMind']."
        )),
    ] = None,
    cursor: Annotated[
        str | None,
        Field(description="Pagination cursor from previous call's next_cursor"),
    ] = None,
) -> dict:
    """Search OpenAlex with full filter suite (concepts/venue/institutions).

    Returns: {"results": [...], "next_cursor": str|None, "total_count": int,
    "unresolved_filters": [...]}. Fuzzy queries are rejected unless a
    structured filter narrows the space. Use concepts+venue+year_min for
    precise topic discovery; use DOI or quoted phrase for known papers.
    """
    config = _get_config()
    sort_map = {"relevance": "relevance", "citations": "citationCount", "date": "publicationDate"}
    return search.search_academic_databases_impl(
        config, query, limit=limit,
        year_min=year_min, year_max=year_max,
        sort_by=sort_map.get(sort_by, "relevance"),
        httpx_module=httpx, tool_error_cls=ToolError, logger=logger,
        min_citations=min_citations,
        oa_only=oa_only,
        concepts=concepts,
        institutions=institutions,
        venue=venue,
        cursor=cursor,
    )


# ---------------------------------------------------------------------------
# MCP Tool: ingest_by_identifiers
# ---------------------------------------------------------------------------

@mcp.tool(tags=tool_tags("core", "ingestion"))
def ingest_by_identifiers(
    identifiers: Annotated[
        list[str],
        Field(description=(
            "DOI, arXiv ID, or URL list. "
            "Examples: ['10.1234/abc', '2301.00001', 'https://...']"
        )),
    ],
) -> dict:
    """Ingest papers into Zotero's INBOX collection. Per-paper status, synchronous.

    Destination and tagging are **not** caller-controlled:
      - All new items land in the INBOX collection (auto-created on first use).
      - Tags are NEVER applied at save time. Topic tagging and reclassification
        happen in Phase 3 via `manage_tags` / `manage_collections` through the
        plan-then-execute workflow in ztp-research — this prevents drive-by
        tagging that bypasses user vocabulary review.

    Internal flow: normalize → dedup → connector check → preflight →
    sequential save+verify → API fallback on failure → PDF check.

    Statuses: saved_with_pdf, saved_metadata_only, blocked, duplicate, failed.
    When action_required is non-empty, surface to user and wait.
    """
    bridge_url = f"http://127.0.0.1:{DEFAULT_PORT}"
    get_writer = _get_writer
    _get_zotero()

    # Destination is hardcoded to INBOX. _ensure_inbox_collection auto-creates
    # it on first use; returns None only when ZOTERO_API_KEY is missing or the
    # writer init fails — in that case the tool cannot function at all.
    collection_key = _ensure_inbox_collection()
    if not collection_key:
        raise ToolError(
            "INBOX collection unavailable. ingest_by_identifiers requires "
            "ZOTERO_API_KEY and ZOTERO_USER_ID so it can create and route "
            "items into the INBOX collection. Configure credentials and retry."
        )

    # Step 1: Normalize identifiers → candidates
    candidates: list[dict] = []
    for ident in identifiers:
        ident = ident.strip()
        candidate: dict = {"identifier": ident, "url": None, "doi": None, "title": None}

        # DOI check
        doi = search.normalize_doi(ident)
        if doi:
            candidate["doi"] = doi
            # Resolve DOI → landing URL
            landing = connector.resolve_doi_to_landing_url(doi)
            if landing:
                candidate["url"] = landing

        # arXiv check
        elif ident.lower().startswith("arxiv:") or _looks_like_arxiv_id(ident):
            arxiv_id = ident.replace("arxiv:", "").strip()
            candidate["doi"] = f"10.48550/arxiv.{arxiv_id}"
            candidate["url"] = f"https://arxiv.org/abs/{arxiv_id}"

        # URL
        elif ident.startswith(("http://", "https://")):
            candidate["url"] = ident
            # Try to extract DOI from URL
            doi_from_url = search.is_doi_query(ident)
            if doi_from_url:
                candidate["doi"] = search.normalize_doi(doi_from_url)

        else:
            candidate["status"] = "failed"
            candidate["error"] = "unrecognized_identifier"

        candidates.append(candidate)

    # Step 2: Local dedup — check DOIs against Zotero
    for candidate in candidates:
        if candidate.get("status"):
            continue  # already failed
        doi = candidate.get("doi")
        if doi:
            existing_key = _lookup_local_item_key_by_doi(doi)
            if existing_key:
                candidate["status"] = "duplicate"
                candidate["item_key"] = existing_key

    # Step 3: Check Connector availability
    active_candidates = [c for c in candidates if not c.get("status") and c.get("url")]
    ext_ok = False
    if active_candidates:
        ext_ok, ext_error, _ = connector.check_connector_availability(
            active_candidates, DEFAULT_PORT, BridgeServer,
        )

    # Step 4: Preflight (if Connector online)
    if ext_ok and active_candidates:
        urls = [c["url"] for c in active_candidates if c.get("url")]
        if urls:
            remaining, preflight_failures, blocking = connector.run_preflight_check(
                [{"url": u} for u in urls], DEFAULT_PORT, BridgeServer, logger,
            )
            if blocking:
                return {
                    "total": len(identifiers),
                    "results": [
                        {**c, "status": c.get("status", "blocked"),
                         "error": "batch_halted_by_preflight"}
                        for c in candidates
                    ],
                    "action_required": [{
                        "type": "preflight_blocked",
                        "message": (
                            "Anti-bot protection detected. "
                            "Complete browser verification in Chrome, then retry."
                        ),
                        "blocked_urls": [f.get("url") for f in preflight_failures],
                    }],
                }

    # Step 5: Sequential save + verify
    results: list[dict] = []
    action_required: list[dict] = []
    for i, candidate in enumerate(candidates):
        # Already resolved (failed, duplicate)
        if candidate.get("status"):
            results.append(candidate)
            continue

        url = candidate.get("url")
        doi = candidate.get("doi")
        title = candidate.get("title")

        if ext_ok and url:
            # Connector route. tags=None is invariant — see tool docstring.
            result = connector.save_single_and_verify(
                url, doi, title,
                collection_key=collection_key, tags=None,
                bridge_url=bridge_url, get_writer=get_writer,
                writer_lock=_writer_lock, _logger=logger,
            )
        elif doi:
            # API-only route. tags=None is invariant — see tool docstring.
            result = connector._doi_api_fallback(
                doi, title, collection_key=collection_key, tags=None,
                get_writer=get_writer, writer_lock=_writer_lock, _logger=logger,
            )
        else:
            result = {
                "status": "failed", "error": "no_usable_identifier",
                "item_key": None, "has_pdf": False, "title": title or "",
                "action_required": None, "warning": None,
            }

        results.append({**result, "identifier": candidate.get("identifier", "")})

        # Anti-bot: halt remaining
        if result.get("status") == "blocked":
            action_required.append({
                "type": "anti_bot_detected",
                "message": result.get("action_required", ""),
                "identifier": candidate.get("identifier", ""),
            })
            # Mark remaining as blocked
            for rem in candidates[i + 1:]:
                if not rem.get("status"):
                    results.append({
                        "identifier": rem.get("identifier", ""),
                        "status": "blocked",
                        "error": "batch_halted_by_anti_bot",
                        "item_key": None, "has_pdf": False,
                        "title": rem.get("title", ""),
                        "action_required": None, "warning": None,
                    })
            break

    return {
        "total": len(identifiers),
        "results": results,
        "action_required": action_required,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ARXIV_ID_RE = __import__("re").compile(r"^\d{4}\.\d{4,5}(v\d+)?$")


def _looks_like_arxiv_id(s: str) -> bool:
    return bool(_ARXIV_ID_RE.match(s.strip()))

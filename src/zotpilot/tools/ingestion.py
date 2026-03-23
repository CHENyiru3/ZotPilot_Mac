"""MCP tools for academic paper ingestion into Zotero."""
from __future__ import annotations

from typing import Annotated, Literal

import httpx
from fastmcp.exceptions import ToolError
from pydantic import Field

from ..state import _get_config, _get_resolver, _get_writer, mcp


@mcp.tool()
def add_paper_by_identifier(
    identifier: Annotated[str, Field(description=(
        "Paper identifier: DOI (e.g. 10.1038/s41586-024...), "
        "arXiv ID (arxiv:2301.00001), arXiv URL (arxiv.org/abs/...), "
        "or doi.org URL."
    ))],
    collection_key: Annotated[str | None, Field(description="Zotero collection key to add the paper to")] = None,
    tags: Annotated[list[str] | None, Field(description="Tags to apply to the paper")] = None,
    attach_pdf: Annotated[bool, Field(description="Attempt to find and attach an open-access PDF")] = True,
) -> dict:
    """Add a single paper to Zotero by DOI or arXiv identifier.
    Fetches metadata automatically. Checks for duplicates before creating."""
    resolver = _get_resolver()
    writer = _get_writer()

    metadata = resolver.resolve(identifier)  # raises ToolError on unknown format

    if metadata.doi:
        existing = writer.check_duplicate_by_doi(metadata.doi)
        if existing:
            return {
                "success": True,
                "duplicate": True,
                "existing_key": existing,
                "title": metadata.title,
            }

    result = writer.create_item_from_metadata(
        metadata,
        collection_keys=[collection_key] if collection_key else None,
        tags=tags,
    )

    if not isinstance(result, dict) or not result.get("success"):
        raise ToolError(f"Failed to create Zotero item: {result}")

    item_key = next(iter(result["success"].values()))

    pdf_status = "skipped"
    if attach_pdf:
        pdf_status = writer.try_attach_oa_pdf(
            item_key=item_key,
            doi=metadata.doi,
            oa_url=metadata.oa_url,
            crossref_raw=getattr(resolver, "last_crossref_metadata", None),
            arxiv_id=metadata.arxiv_id,
        )

    return {
        "success": True,
        "duplicate": False,
        "item_key": item_key,
        "title": metadata.title,
        "item_type": metadata.item_type,
        "pdf": pdf_status,
    }


@mcp.tool()
def search_academic_databases(
    query: Annotated[str, Field(description="Search query for academic papers")],
    limit: Annotated[int, Field(ge=1, le=100, description="Number of results (1-100)")] = 20,
    year_min: Annotated[int | None, Field(description="Earliest publication year filter")] = None,
    year_max: Annotated[int | None, Field(description="Latest publication year filter")] = None,
    sort_by: Annotated[
        Literal["relevance", "citationCount", "publicationDate"],
        Field(description="Sort order: relevance (default), citationCount, or publicationDate")
    ] = "relevance",
) -> list[dict]:
    """Search Semantic Scholar for academic papers.
    Does NOT add to Zotero. Use ingest_papers to add selected results to your library."""
    config = _get_config()
    params: dict = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,externalIds,citationCount,abstract",
        "sort": sort_by,
    }
    if year_min or year_max:
        lo = str(year_min) if year_min else ""
        hi = str(year_max) if year_max else ""
        params["publicationDateOrYear"] = f"{lo}-{hi}"

    headers = {}
    if config.semantic_scholar_api_key:
        headers["x-api-key"] = config.semantic_scholar_api_key

    try:
        resp = httpx.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params,
            headers=headers,
            timeout=15.0,
        )
        resp.raise_for_status()
    except httpx.TimeoutException:
        raise ToolError("Semantic Scholar search timed out. Try again or reduce limit.")
    except httpx.HTTPStatusError as e:
        raise ToolError(f"Semantic Scholar search failed: {e.response.status_code}")

    papers = resp.json().get("data", [])
    return [
        {
            "title": p.get("title"),
            "authors": [a.get("name") for a in (p.get("authors") or [])[:5]],
            "year": p.get("year"),
            "doi": (p.get("externalIds") or {}).get("DOI"),
            "arxiv_id": (p.get("externalIds") or {}).get("ArXiv"),
            "s2_id": p.get("paperId"),
            "cited_by_count": p.get("citationCount"),
            "abstract_snippet": (p.get("abstract") or "")[:300],
        }
        for p in papers
    ]


@mcp.tool()
def ingest_papers(
    papers: Annotated[list[dict], Field(description=(
        "List of paper dicts, each with at least one of: doi, arxiv_id, s2_id. "
        "Typically from search_academic_databases results. Max 50 per call."
    ))],
    collection_key: Annotated[str | None, Field(description="Zotero collection key for all ingested papers")] = None,
    tags: Annotated[list[str] | None, Field(description="Tags to apply to all ingested papers")] = None,
    skip_duplicates: Annotated[bool, Field(description="Skip papers already in the library")] = True,
) -> dict:
    """Batch add papers to Zotero from search results.
    Each paper is processed independently — failures don't abort the batch."""
    if len(papers) > 50:
        raise ToolError(
            f"Batch size {len(papers)} exceeds maximum of 50. Split into smaller batches."
        )

    config = _get_config()
    warning = None
    if not config.semantic_scholar_api_key and len(papers) > 5:
        warning = (
            f"No S2_API_KEY configured. Estimated latency for {len(papers)} papers: "
            f"~{len(papers)}s (1 req/sec rate limit). "
            "Set S2_API_KEY environment variable for higher throughput."
        )

    results = []
    ingested = skipped = failed = 0

    for paper in papers:
        doi = paper.get("doi")
        arxiv_id = paper.get("arxiv_id")
        s2_id = paper.get("s2_id")

        if doi:
            identifier = doi
        elif arxiv_id:
            identifier = f"arxiv:{arxiv_id}"
        elif s2_id:
            identifier = s2_id
        else:
            results.append({"status": "failed", "error": "no usable identifier in paper dict"})
            failed += 1
            continue

        try:
            r = add_paper_by_identifier(identifier, collection_key, tags, attach_pdf=True)
            if r.get("duplicate") and skip_duplicates:
                skipped += 1
                results.append({
                    "identifier": identifier,
                    "status": "duplicate",
                    "existing_key": r.get("existing_key"),
                    "title": r.get("title"),
                })
            else:
                ingested += 1
                results.append({
                    "identifier": identifier,
                    "status": "ingested",
                    "item_key": r.get("item_key"),
                    "title": r.get("title"),
                    "pdf": r.get("pdf"),
                })
        except ToolError as e:
            failed += 1
            results.append({"identifier": identifier, "status": "failed", "error": str(e)})
        except Exception as e:
            failed += 1
            results.append({"identifier": identifier, "status": "failed", "error": str(e)})

    return {
        "total": len(papers),
        "ingested": ingested,
        "skipped_duplicates": skipped,
        "failed": failed,
        "warning": warning,
        "results": results,
    }


@mcp.tool()
def save_from_url(
    url: str,
    collection_key: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Save a paper from any publisher URL to Zotero via ZotPilot Connector.

    Opens the URL in the user's real browser (with institutional cookies),
    runs Zotero translators to extract metadata, downloads PDF, and saves to Zotero.

    Requires: ZotPilot Connector extension installed in Chrome.
    The bridge is auto-started if not already running.

    Note: collection_key and tags are accepted but not yet applied by the
    extension in this version — the paper saves to Zotero's default location.
    """
    import json
    import time
    import urllib.request

    from ..bridge import DEFAULT_PORT, BridgeServer

    bridge_url = f"http://127.0.0.1:{DEFAULT_PORT}"

    # Auto-start bridge if not running
    if not BridgeServer.is_running(DEFAULT_PORT):
        try:
            BridgeServer.auto_start(DEFAULT_PORT)
        except RuntimeError as e:
            return {"success": False, "error": str(e)}

    # POST command to bridge's /enqueue endpoint (pure HTTP client)
    command = {
        "action": "save",
        "url": url,
        "collection_key": collection_key,
        "tags": tags or [],
    }
    try:
        req = urllib.request.Request(
            f"{bridge_url}/enqueue",
            data=json.dumps(command).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=5)
        request_id = json.loads(resp.read())["request_id"]
    except Exception as e:
        return {"success": False, "error": f"Failed to enqueue: {e}"}

    # Poll GET /result/<request_id> until result arrives or timeout
    deadline = time.monotonic() + 90.0
    while time.monotonic() < deadline:
        time.sleep(2)
        try:
            resp = urllib.request.urlopen(
                f"{bridge_url}/result/{request_id}", timeout=5
            )
            if resp.status == 200:
                return json.loads(resp.read())
        except Exception:
            pass  # 204 or connection error — keep polling

    return {
        "success": False,
        "error": "Timeout (90s) — extension did not respond. "
                 "Ensure ZotPilot Connector is installed and Chrome is open.",
    }

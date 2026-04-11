"""Search backends for ingestion-related academic discovery (v0.5.0).

Merged from:
- tools/ingestion_search.py — OpenAlex search, DOI normalization, result formatting
- docs/_migrating_functions.py — query building, dedup, local duplicate annotation
"""
from __future__ import annotations

import re
from typing import Any, Literal

from ...openalex_client import OpenAlexClient

_OA_ARXIV_PREFIX = "https://doi.org/10.48550/arxiv."


# ---------------------------------------------------------------------------
# DOI / abstract utilities
# ---------------------------------------------------------------------------

def reconstruct_abstract(inverted_index: dict | None) -> str:
    """Reconstruct plain-text abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words))


def is_doi_query(query: str) -> str | None:
    """Return cleaned DOI for DOI-like queries, else None."""
    cleaned = query.strip()
    lowered = cleaned.lower()
    if lowered.startswith("doi:"):
        cleaned = cleaned[4:].strip()
    elif lowered.startswith("https://doi.org/"):
        cleaned = cleaned[len("https://doi.org/"):].strip()
    elif lowered.startswith("http://doi.org/"):
        cleaned = cleaned[len("http://doi.org/"):].strip()

    return cleaned if re.match(r"^10\.\d{4,}/\S+$", cleaned) else None


def normalize_doi(doi: str | None) -> str | None:
    """Return a normalized lowercase DOI without scheme/prefix, or None if invalid."""
    if not doi:
        return None
    prefixed = doi if doi.lower().startswith(("doi:", "http://", "https://")) else f"doi:{doi}"
    result = is_doi_query(prefixed)
    return result.lower() if result else None


# ---------------------------------------------------------------------------
# OpenAlex formatting
# ---------------------------------------------------------------------------

def format_openalex_paper(paper: dict) -> dict:
    """Format a single OpenAlex work dict into ZotPilot's result format."""
    doi_raw = paper.get("doi") or ""
    formatted_doi = doi_raw.replace("https://doi.org/", "").replace("http://doi.org/", "") or None
    oa_id = paper.get("id", "").replace("https://openalex.org/", "")
    authors = [
        author.get("author", {}).get("display_name")
        for author in (paper.get("authorships") or [])[:5]
        if author.get("author", {}).get("display_name")
    ]
    abstract = reconstruct_abstract(paper.get("abstract_inverted_index"))

    ids = paper.get("ids") or {}
    ids_doi = ids.get("doi") or ""
    arxiv_id = (
        ids_doi.lower()[len(_OA_ARXIV_PREFIX):]
        if ids_doi.lower().startswith(_OA_ARXIV_PREFIX.lower())
        else None
    )

    oa = paper.get("open_access") or {}
    primary = paper.get("primary_location") or {}
    source = primary.get("source") or {}
    summary_stats = source.get("summary_stats") or {}
    cited_by_count = int(paper.get("cited_by_count") or 0)
    venue_h_index = summary_stats.get("h_index")
    venue_two_yr_mean_citedness = summary_stats.get("2yr_mean_citedness")
    venue = {
        "display_name": source.get("display_name"),
        "h_index": venue_h_index,
        "two_yr_mean_citedness": venue_two_yr_mean_citedness,
    }

    return {
        "title": paper.get("display_name"),
        "authors": authors,
        "year": paper.get("publication_year"),
        "doi": formatted_doi,
        "arxiv_id": arxiv_id,
        "openalex_id": oa_id,
        "cited_by_count": cited_by_count,
        "is_retracted": bool(paper.get("is_retracted", False)),
        "type": paper.get("type"),
        "venue": venue,
        "top_venue": bool(
            (venue_h_index is not None and venue_h_index >= 100) or cited_by_count >= 500
        ),
        "abstract_snippet": abstract[:300],
        "is_oa": oa.get("is_oa", False),
        "oa_url": oa.get("oa_url"),
        "landing_page_url": primary.get("landing_page_url"),
        "journal": source.get("display_name"),
        "publisher": source.get("host_organization_name"),
        "relevance_score": paper.get("relevance_score"),
        "_source": "openalex",
    }


def fetch_openalex_by_doi(doi: str, client: OpenAlexClient) -> list[dict]:
    """Fetch a single OpenAlex work by DOI, with search fallback."""
    paper = client.get_work_details_by_doi(doi)
    if paper is not None:
        return [format_openalex_paper(paper)]

    try:
        data = client.search_works(f'"{doi}"', per_page=3)
        papers = data.get("results", [])
    except Exception:
        return []
    if not papers:
        return []
    return [format_openalex_paper(papers[0])]


def search_openalex(
    query: str,
    limit: int,
    year_min: int | None,
    year_max: int | None,
    sort_by: str,
    *,
    client: OpenAlexClient,
    high_quality: bool = True,
) -> list[dict]:
    """Single-path keyword search via OpenAlex /works?search=<query>."""
    sort_map = {
        "relevance": "relevance_score:desc",
        "publicationDate": "publication_date:desc",
        "citationCount": "cited_by_count:desc",
    }
    sort_value = sort_map.get(sort_by, "relevance_score:desc")

    min_citations = 10 if high_quality else None
    data = client.search_works(
        query,
        per_page=min(limit * 2, 200),
        min_citations=min_citations,
        year_min=year_min,
        year_max=year_max,
        sort=sort_value,
    )
    papers = data.get("results", [])
    results = [format_openalex_paper(p) for p in papers]
    _mark_top_venue_relative(results)
    return results[:limit]


_AUTHOR_PREFIX_RE = re.compile(r"^\s*author\s*:", re.IGNORECASE)
_DOI_LIKE_RE = re.compile(r"\b10\.\d{4,9}/\S+", re.IGNORECASE)


def _is_fuzzy_nl_query(query: str) -> bool:
    if not query or not query.strip():
        return False
    if _AUTHOR_PREFIX_RE.match(query):
        return False
    if _DOI_LIKE_RE.search(query):
        return False
    if query.strip().lower().startswith(("doi:", "https://doi.org/", "http://doi.org/")):
        return False
    if '"' in query or " AND " in query or " OR " in query:
        return False
    return True


def _mark_top_venue_relative(results: list[dict], *, percentile: float = 0.75) -> None:
    """Re-stamp ``top_venue`` based on batch-relative citation percentile."""
    if len(results) < 5:
        return
    cites = sorted(r.get("cited_by_count") or 0 for r in results)
    idx = int(len(cites) * percentile)
    threshold = max(cites[min(idx, len(cites) - 1)], 10)
    for r in results:
        if (r.get("cited_by_count") or 0) >= threshold:
            r["top_venue"] = True


def search_academic_databases_impl(
    config,
    query: str,
    limit: int,
    year_min: int | None,
    year_max: int | None,
    sort_by: str,
    high_quality: bool,
    httpx_module,
    tool_error_cls,
    logger,
) -> list[dict]:
    """Shared implementation for academic search tool."""
    client = OpenAlexClient(email=config.openalex_email)

    detected_doi = is_doi_query(query)
    try:
        if detected_doi:
            results = fetch_openalex_by_doi(detected_doi, client=client)
        else:
            results = search_openalex(
                query, limit, year_min, year_max, sort_by,
                client=client, high_quality=high_quality,
            )
    except httpx_module.TimeoutException:
        error = "timeout"
    except httpx_module.HTTPStatusError as exc:
        error = f"http_{exc.response.status_code}"
    except Exception as exc:
        error = str(exc)
    else:
        if _is_fuzzy_nl_query(query) and sort_by == "relevance" and results:
            results[0] = {
                **results[0],
                "_warnings": [
                    {
                        "code": "needs_structured_query_plan",
                        "message": (
                            "Fuzzy NL query detected. In the research workflow, "
                            "bag-of-words queries should be upgraded into a structured "
                            "query plan (DOI direct, author-anchored, or quoted/boolean "
                            "phrase queries) before running external discovery."
                        ),
                    }
                ],
            }
        return results

    logger.info("OpenAlex search failed (%s)", error)
    raise tool_error_cls(f"Academic search failed: OpenAlex ({error}).")


# ---------------------------------------------------------------------------
# URL classification helpers
# ---------------------------------------------------------------------------

_PDF_URL_RE = re.compile(
    r"(?:"
    r"\.pdf(?:[?#]|$)"
    r"|/pdf(?:[?/]|$)"
    r"|/content/pdf/"
    r"|pdf\.sciencedirect\.com"
    r")",
    re.IGNORECASE,
)
_DOI_REDIRECT_RE = re.compile(r"^https?://(?:dx\.)?doi\.org/10\.", re.IGNORECASE)


def is_pdf_or_doi_url(url: str | None) -> bool:
    """Return True if url is a direct PDF link or a doi.org redirect."""
    if not url:
        return False
    return bool(_PDF_URL_RE.search(url)) or bool(_DOI_REDIRECT_RE.match(url))


_LINKINGHUB_PII_RE = re.compile(
    r"^https?://linkinghub\.elsevier\.com/retrieve/pii/(S[0-9X]+)",
    re.IGNORECASE,
)


def normalize_landing_url(url: str) -> str:
    """Convert known intermediate redirectors to final landing pages."""
    m = _LINKINGHUB_PII_RE.match(url)
    if m:
        return f"https://www.sciencedirect.com/science/article/pii/{m.group(1)}"
    return url


def classify_ingest_candidate(
    paper: dict,
    normalized_doi: str | None,
    arxiv_id: str | None,
    landing_page_url: str | None,
) -> Literal["connector", "api", "reject"]:
    """Classify a paper candidate for routing."""
    if arxiv_id:
        return "connector"
    if landing_page_url and not is_pdf_or_doi_url(landing_page_url):
        return "connector"
    resolved_url = paper.get("_resolved_landing_url")
    if resolved_url and not is_pdf_or_doi_url(resolved_url):
        return "connector"
    if normalized_doi or (paper.get("doi") and not landing_page_url):
        return "api"
    return "reject"


# ---------------------------------------------------------------------------
# Migrated from research_workflow.py — query building and dedup helpers
# ---------------------------------------------------------------------------

def _normalize_title_key(title: str | None) -> str:
    if not title:
        return ""
    lowered = title.casefold()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def _infer_anchor_kind(query: str) -> str:
    if is_doi_query(query):
        return "doi"
    if query.strip().lower().startswith("author:"):
        return "author"
    return "phrase"


def build_structured_queries(
    *,
    query: str,
    request_class: Literal["known_item", "seminal_seed_set", "topic_survey"],
    anchors: list,
    strict_policy: bool,
    audit: dict[str, Any],
) -> tuple[list[dict[str, str]], Any]:
    """将搜索请求分解为精确子查询。"""
    structured_queries: list[dict[str, str]] = []

    if anchors:
        for anchor in anchors:
            normalized = anchor.normalized_query(topic=query)
            structured_queries.append({
                "label": anchor.source_label(topic=query),
                "query": normalized,
                "kind": anchor.kind,
            })
            if normalized != anchor.query.strip():
                audit["repaired_queries"].append({
                    "kind": anchor.kind,
                    "input": anchor.query,
                    "normalized": normalized,
                })
    elif not _is_fuzzy_nl_query(query):
        inferred_kind = _infer_anchor_kind(query)
        structured_queries.append({
            "label": inferred_kind,
            "query": query.strip(),
            "kind": inferred_kind,
        })

    if not strict_policy:
        return structured_queries or [{
            "label": "query",
            "query": query.strip(),
            "kind": _infer_anchor_kind(query),
        }], None

    if request_class == "known_item":
        if structured_queries:
            return structured_queries, None
        return [], None

    min_precise_queries = 1 if request_class == "seminal_seed_set" else 2
    if len(structured_queries) < min_precise_queries:
        return [], None
    return structured_queries, None


def paper_rank_tuple(paper: dict[str, Any]) -> tuple[int, int, float]:
    """论文排名元组（venue × citations）。"""
    return (
        int(paper.get("cited_by_count") or 0),
        int(bool(paper.get("top_venue"))),
        float(paper.get("relevance_score") or 0.0),
    )


def paper_dedup_key(paper: dict[str, Any]) -> tuple[str, str]:
    """论文去重 key（DOI 或 normalized title）。"""
    normalized_doi_val = normalize_doi(paper.get("doi"))
    if normalized_doi_val:
        return ("doi", normalized_doi_val)
    for field_name in ("openalex_id", "arxiv_id", "landing_page_url", "oa_url"):
        value = str(paper.get(field_name) or "").strip()
        if value:
            return (field_name, value)
    normalized_title = _normalize_title_key(paper.get("title"))
    if normalized_title:
        return ("title", normalized_title)
    fallback = paper.get("title") or paper.get("landing_page_url") or "candidate"
    return ("fallback", str(fallback))


def merge_search_hits(
    query_results: list[tuple[dict[str, str], list[dict[str, Any]]]],
    *,
    limit: int,
    audit: dict[str, Any],
) -> list[dict[str, Any]]:
    """合并多次搜索结果并去重。"""
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    raw_hits = 0
    for query_info, papers in query_results:
        raw_hits += len(papers)
        for paper in papers:
            key = paper_dedup_key(paper)
            existing = merged.get(key)
            candidate = dict(paper)
            candidate_sources = list(
                dict.fromkeys([*paper.get("_sources", []), query_info["label"]])
            )
            candidate["_sources"] = candidate_sources
            candidate["_source"] = (
                candidate_sources[0] if len(candidate_sources) == 1 else "multi_query"
            )
            if existing is None:
                merged[key] = candidate
                continue
            combined_sources = list(
                dict.fromkeys([*existing.get("_sources", []), *candidate_sources])
            )
            better = (
                candidate
                if paper_rank_tuple(candidate) > paper_rank_tuple(existing)
                else existing
            )
            better = dict(better)
            better["_sources"] = combined_sources
            better["_source"] = (
                combined_sources[0] if len(combined_sources) == 1 else "multi_query"
            )
            merged[key] = better

    merged_results = sorted(merged.values(), key=paper_rank_tuple, reverse=True)
    audit["dedup_stats"] = {
        "raw_hits": raw_hits,
        "unique_candidates": len(merged_results),
        "duplicates_removed": max(raw_hits - len(merged_results), 0),
    }
    return merged_results[:limit]


def annotate_local_duplicates(
    papers: list[dict[str, Any]],
    *,
    audit: dict[str, Any],
    lookup_by_doi,
    lookup_by_title,
) -> list[dict[str, Any]]:
    """标注本地已有的论文。"""
    annotated: list[dict[str, Any]] = []
    duplicate_hits: list[dict[str, Any]] = []
    for paper in papers:
        normalized_doi_val = normalize_doi(paper.get("doi"))
        exact_key = lookup_by_doi(normalized_doi_val)
        suspected = lookup_by_title(paper.get("title"), normalized_doi_val, limit=5)
        local_duplicate = {
            "status": "none",
            "item_keys": [],
            "matches": suspected,
        }
        if exact_key:
            local_duplicate["status"] = "exact"
            local_duplicate["item_keys"] = [exact_key]
        elif suspected:
            local_duplicate["status"] = "suspected"
            local_duplicate["item_keys"] = [
                match["item_key"] for match in suspected if match.get("item_key")
            ]
        if local_duplicate["status"] != "none":
            duplicate_hits.append({
                "doc_id": (
                    paper.get("openalex_id") or paper.get("doi") or paper.get("title")
                ),
                "status": local_duplicate["status"],
                "item_keys": local_duplicate["item_keys"],
            })
        annotated_paper = dict(paper)
        annotated_paper["local_duplicate"] = local_duplicate
        annotated.append(annotated_paper)
    audit["local_duplicate_hits"] = duplicate_hits
    return annotated

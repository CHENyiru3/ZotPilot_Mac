---
name: ztp-research
description: Literature discovery, ingest, indexing, and organization workflow
---

# ztp-research

Use this workflow for external discovery and collection building.

Requirements:

- Set `ZOTPILOT_TOOL_PROFILE=research`
- Prefer ZotPilot MCP tools over generic web search

Workflow:

1. Clarify the topic, scope, year range, and inclusion criteria.
2. Call `research_session(action="get")` to detect any active session.
3. If none exists, call `research_session(action="create", query=...)`.
4. Use `search_academic_databases` for candidate discovery.
5. Use `advanced_search` against the local library to detect duplicates.
6. Present ranked candidates and stop at checkpoint 1.
7. After explicit approval, call `research_session(action="approve", checkpoint="candidate-review")`.
8. Call `ingest_papers`, then poll `get_ingest_status` until terminal.
   - If the response contains `error_code: "connector_offline"`, **STOP
     immediately and surface the `error` and `remediation` fields verbatim
     to the user**. Do not silently fall back to any alternate path. Ask
     the user to fix Chrome/Connector and confirm before retrying.
9. Present ingest results and downstream plan, then stop at checkpoint 2.
   - **If `saved_metadata_only > 0`**, surface a clear warning: "N of M papers saved as metadata-only (no PDF attached). These cannot be indexed or semantically searched."
     List the affected titles from `pdf_missing_items` and ask the user to choose:
     (1) log in to institutional VPN/SSO and re-ingest those URLs, (2) keep as
     metadata-only references, or (3) delete the metadata-only entries. Do NOT
     silently proceed to indexing — the user must make a conscious choice.
10. After explicit approval, call `research_session(action="approve", checkpoint="post-ingest-review")`.
11. Run `index_library` as needed until `has_more=false`.
    - If the response includes `skipped_no_pdf_count > 0`, **do not treat this as
      success alone**: list the skipped titles from `skipped_no_pdf_items` and
      remind the user that those entries remain reference-only until PDFs are
      attached.
12. Use `browse_library`, `manage_collections`, `create_note(idempotent=True)`, and `manage_tags(action="add")` for post-ingest organization.
13. End with a per-paper report that separates success (with PDF), metadata-only, failure, and skipped items.

Hard rules:

- Do not replace `search_academic_databases` with generic web search.
- Do not call `ingest_papers` before checkpoint 1 approval.
- Do not run post-ingest writes before checkpoint 2 approval.
- Keep post-ingest writes idempotent.

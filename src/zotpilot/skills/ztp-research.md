---
name: ztp-research
description: >
  Literature discovery, ingest, indexing, and organization workflow
  for ZotPilot. Use this skill whenever the user mentions finding /
  importing / organizing papers, building a literature collection,
  doing a topic survey, or asks anything that involves
  search_academic_databases, ingest_papers, or post-ingest checkpoints
  — even if they don't explicitly say 'research workflow'. This skill
  enforces the user gates around ingestion that protect against
  partial-batch corruption (see 2026-04-08 incident).
---

# ztp-research

Use this workflow for external discovery and collection building.

Requirements:

- Set `ZOTPILOT_TOOL_PROFILE=research`
- Prefer ZotPilot MCP tools over generic web search

Workflow:

1. Clarify the topic, scope, year range, and inclusion criteria.
2. If the user already has a ZotPilot batch id, resume with `get_batch_status(batch_id=...)`.
3. **Local-first check**: Before external search, use `search_topic` or `advanced_search`
   to check what's already in the local library for this topic. Present results to the
   user: "Your library already has these papers on [topic]. Would you like to search
   for additional papers to supplement?" Then proceed to external search only if needed.
4. Use `search_academic_databases` for candidate discovery.

   ## §4 — Search SOP for effective discovery

   Always use `search_academic_databases` as the primary search entry point.
   For fuzzy natural-language topic queries, issue **multiple precise queries** to
   maximize recall. In `research` profile, if you cannot provide the minimum precise
   anchor set, treat the tool response as a **policy_violation** and repair the plan
   before retrying. Do not push a bag-of-words query through as the main path.

   ### Step 4.1 — Decompose the query into 3-5 precise searches
   Do NOT issue a single bare-NL query. Instead:
   - **DOI direct lookup**: If you know seminal DOIs, call `search_academic_databases("10.x/yyy")`. For classic / seminal / canonical requests, DOI-first is the default fastest path.
   - **Author-anchored**: `search_academic_databases("author:LastName | topic")` for key researchers.
   - **Phrase boolean**: `search_academic_databases('"exact phrase" AND (term1 OR term2)')` using domain-specific terms.
   Negative examples that should be repaired before retrying:
   - `CLIP learning transferable visual models from natural language supervision Radford`
   - `vision language pretraining align blip image text contrastive`
   These are bag-of-words prompts, not precise search plans.

   ### Step 4.2 — Merge client-side
   - Deduplicate by DOI
   - Sort by `cited_by_count` desc, then `top_venue` first
   - Note `_sources` of each paper (which query paths found it)

   ### Step 4.3 — Report transparently to the user
   Format: "Issued N structured queries; returned M raw hits; deduped to K unique candidates."

   ### Optional: WebFetch for context gathering
   If `search_academic_databases` returns insufficient results **and the user
   requests it**, you may use WebFetch to gather anchor DOIs and author names
   from an authoritative source (e.g. Wikipedia, survey paper). Then re-query
   with the extracted identifiers. This is **optional**, not required.

   ### When to skip multi-query decomposition
   - Query already contains `author:`, DOI, quoted phrase, or boolean operators (`AND`/`OR`/`NOT`) → user/agent already specified intent precisely; single-call is fine.
6. Use `advanced_search` against the local library to detect duplicates. This is a gate, not a memory-based guess.
7. Present ranked candidates and stop for user selection.
8. After explicit approval, call `confirm_candidates(batch_id=..., selected_ids=[...])`.
9. If preflight is clear, call `approve_ingest(batch_id=...)`. If preflight is blocked, call `resolve_preflight(batch_id=...)` only after the user completes browser verification.
10. Poll `get_batch_status(batch_id=...)` until the batch reaches `post_ingest_verified`.
   - If the response contains `error_code: "connector_offline"`, **STOP
     immediately and surface the `error` and `remediation` fields verbatim
     to the user**. Do not silently fall back to any alternate path. Ask
     the user to fix Chrome/Connector and confirm before retrying.
   **Why preflight blocks matter**: preflight 是为用户介入设计的闸门，不是路由
   提示。2026-04-08 的真实事故里，agent 收到 `preflight_blocked` 后改用
   `save_urls` + DOI 链接重试，结果只是把同一个 Cloudflare 墙撞了五次，并把部分
   成功部分失败的脏批次写进了库。preflight 阻塞 = 你停下，用户开浏览器，整批
   重试。降级路径不存在 —— 试图绕过 = 加重事故。

   If `ingest_papers` returns `error_code: "anti_bot_detected"` with
   `blocking_decisions[].decision_id == "preflight_blocked"`: STOP. Surface
   `blocking_decisions` verbatim to the user. Wait for browser verification
   confirmation. Retry `ingest_papers` with IDENTICAL inputs. Do not fall back
   to `save_urls` or DOI links.

11. After ingest verification, read `blocking_decisions` from the response.
   For each decision in the list, present it to the user **once** and wait for
   their choice before proceeding. The list is empty when no decisions need
   attention. The `pdf_missing_items` list is the canonical payload for any
   metadata-only items referenced by a decision.
12. After explicit approval, call `approve_post_ingest(batch_id=...)`.
13. Poll `get_batch_status(batch_id=...)` until the batch reaches `post_process_verified`.
14. Review the `final_report`. Treat `full_success_count`, `partial_count`, per-item `missing_steps`,
    and `reindex_eligible` as the source of truth. Do not infer note/tag/classification completion from prose.
    **`post_process_verified` only means the worker finished — not that all items are fully processed.**
    When `final_report.completion_status` is not `"complete"`, report the specific gaps per item.
    Do not tell the user "研究整理已完成" if `completion_status` is `"partial"` or `"degraded"`.
15. If the user accepts the verified report, call `approve_post_process(batch_id=...)`.
16. **Final verification** — why: tool "success" responses don't guarantee data
    integrity — verification catches silent failures before you report to the user.
    Before reporting, confirm the final batch state still matches the underlying tools:

    | Check | Tool | What to verify |
    |---|---|---|
    | PDF on disk | `browse_library` / `get_paper_details` | attachment present, not metadata-only |
    | Index coverage | `get_index_stats` / `search_topic` | new items reachable via semantic search |
    | Final report truth | `get_batch_status` | `final_report.items[].missing_steps` still matches batch item flags |
    | Degraded recovery | `reindex_degraded` | only for items listed in `reindex_eligible` |

    If any check fails, surface it in the report and ask the user how to proceed
    (retry, manual fix, or skip). Do not silently re-run write operations.

17. End with a per-paper report grouped as:
    - ✅ Full success (PDF + indexed + no missing post-process steps)
    - ⚠️ Metadata-only (no PDF — user decides whether to fetch manually)
    - ⚠️ Partial (follow `missing_steps` exactly; do not claim unfinished steps are done)
    - ❌ Failure / skipped

Hard rules:

- Do not replace `search_academic_databases` with generic web search.
- Do not call `confirm_candidates` until the user has selected candidates.
- Do not call `approve_ingest` until the user has approved the preflighted batch.
- Do not call `approve_post_ingest` until the user has reviewed the ingest result.
- Do not call `approve_post_process` until the user has reviewed the final verified report.
- Do not invent legacy session tools; the batch id is the workflow handle.
- Keep post-ingest writes truthful. If `missing_steps` is non-empty, report a partial outcome instead of claiming success.
- When `final_report.completion_status` is not `"complete"`, do not report "研究整理已完成". List each item with `missing_steps` explicitly.
- Use `ingest_by_identifiers` **only** when the user has provided explicit DOI / arXiv ID / URL identifiers. For fuzzy topic requests, always use `search_academic_databases → confirm_candidates` main path.
- **Polling strategy**: After calling `get_batch_status`, if the phase has not changed, pause briefly before retrying (the server-suggested interval is ~10s). Do not exceed 20 retries. Report current phase and progress to the user on each poll.

For incident history and detailed root causes, see
`references/post-ingest-incidents.md` (load when handling post-ingest
errors or designing similar gates).

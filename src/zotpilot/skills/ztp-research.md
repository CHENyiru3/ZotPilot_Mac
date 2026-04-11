---
name: ztp-research
description: >
  Literature discovery, ingestion, and post-processing workflow.
  Covers the full pipeline: search → select → ingest → tag → classify → index → verify.
---
# Research Workflow

## Phase 1 — Discovery

1. **Clarify**: Topic, scope, year range, inclusion criteria
2. **Local-first check**: `search_topic` / `advanced_search` → show what's already in library
   "Your library already has N papers on [topic]. Search for more?"
3. **External search**: `search_academic_databases` — see **Search SOP** below. Run 2-4 queries that anchor on DOI / venue / concept / quoted phrase. Merge results client-side, dedup by DOI, sort by cited_by_count.
4. **Dedup against local**: `advanced_search` by DOI to detect existing papers
5. **[USER_REQUIRED]** Show ranked candidates with scores, wait for user selection

## Phase 2 — Ingestion

6. **Pre-ingest institutional access check** [USER_REQUIRED]: Before calling `ingest_by_identifiers`, check the selected candidates' venues. If **any** of them is from a paywalled publisher (Springer / Elsevier / Wiley / IEEE / ACM / Nature Publishing Group / etc.) **and** `is_oa` is false, pause and ask the user **once**:
   > 本次入库包含付费出版社的论文（例如 Springer/IEEE），请确认你当前是否位于**校园网 / VPN / 有机构订阅**的环境。(Y/N)
   >
   > - **Y** → 直接继续入库
   > - **N** → 请先启用机构网络，再告诉我继续
   - Skip this check entirely when all selected candidates are arXiv-only, DOAJ-listed, or already marked `is_oa: true` — those papers are reachable without institutional access.
   - Plan C's Connector save uses the user's **current network context**. Paywalled papers without institutional access will come back as `saved_metadata_only`; this reminder avoids that failure mode before it happens.
7. **Ingest**: `ingest_by_identifiers(selected_identifiers)`
8. **Handle results**:
   - If `action_required` contains "anti_bot" → **STOP**, tell user to open browser, wait for confirmation, retry with IDENTICAL inputs
   - If `action_required` contains "connector_offline" → **STOP**, surface remediation to user
   - All saved → proceed to Phase 3
9. **[USER_REQUIRED]** Show ingest results table (title / status / has_pdf / item_key)

## Phase 3 — Post-processing

After user approves ingest results, execute post-processing for each ingested paper:

10. **Tag cleanup**: For each saved item, clean auto-generated publisher tags
    - `manage_tags(action="remove", item_keys=[...], tags=[auto-generated tags])`
    - Auto-generated tags come from arXiv, publisher sites (e.g., "Computer Science - Computation and Language")
11. **Tag assignment**: Apply user's existing tag vocabulary
    - Use `browse_library(view="tags")` to discover existing tags
    - Propose tags from existing vocabulary that match each paper's topic
    - `manage_tags(action="add", item_keys=[...], tags=[proposed_tags])`
    - **[USER_REQUIRED]** If proposing NEW tags not in existing vocabulary, list them and confirm
12. **Collection assignment**: Classify into collections
    - Use `browse_library(view="collections")` to discover existing collections
    - Propose collection placement based on topic match
    - `manage_collections(action="add", item_keys=[...], collection=...)`
    - If no matching collection exists, propose creating one with `manage_collections(action="create")`
    - **[USER_REQUIRED]** Confirm before creating new collections
13. **Note creation** (optional, if user requested):
    - `create_note(item_key, content)` — brief research note per paper
14. **Index update**: `index_library(item_keys=[newly_ingested_keys])`
15. **Verify**: `get_index_stats` + `search_topic` to confirm new papers are searchable

## Phase 4 — Final Report

16. **[USER_REQUIRED]** Present per-paper report:
    - ✅ Full success (PDF + indexed + tagged + classified)
    - ⚠️ Metadata-only (no PDF — note reason: paywall / OA mismatch)
    - ⚠️ Partial (missing: tag / collection / index — list specifically)
    - ❌ Failed / skipped (with reason)

## Cold Start — when the topic is unfamiliar

**WebFetch's role here is KEYWORD DISCOVERY, not literature search.** Its job is to convert the user's fuzzy intent into the vocabulary that `search_academic_databases` can consume (canonical English term, seminal DOIs, venues, concept names).

**Decision rule** — skip this section and go directly to structured search IF you can name, from internal knowledge, all four of:

1. The canonical English term for the topic
2. A seminal paper (by DOI, arXiv ID, or author+title)
3. A common venue (CVPR / NeurIPS / ICLR / TPAMI / ACL / etc.)
4. An OpenAlex concept that covers it ("Computer vision", "Natural language processing", …)

Otherwise — non-English input (`调研XX`), niche/new term, ambiguous acronym, or uncertainty — **run reconnaissance FIRST**. Do NOT ask the user to supply the plan; they invoked `/ztp-research` precisely because they do not know.

### Reconnaissance recipe

1. **WebFetch one reference page** (in order of preference):
   - `https://en.wikipedia.org/wiki/<Topic>` — best for established topics
   - `https://paperswithcode.com/search?q=<term>` — task taxonomies + leaderboards
   - `https://arxiv.org/list/<category>/<yyyy-mm>` — recent papers in a subfield

2. **Extract the search plan** from the page (not the full content):
   - **Canonical English term** → for quoted-phrase queries
   - **2-3 seminal paper DOIs / arXiv IDs** → for DOI-direct lookups
   - **Common venues** → for `venue=` filter
   - **Related concept names** → for `concepts=` filter

3. **Proceed to structured search** with the learned vocabulary via the Search SOP below.

### Anti-patterns

- Do NOT WebFetch when the canonical term is already known (e.g. user says "调研 CLIP" → skip reconnaissance, go DOI direct).
- Do NOT WebFetch to read full papers — that is what `get_paper_details` and `search_papers` are for after ingest.
- Do NOT reconnaissance-loop: one WebFetch is enough to extract a search plan; stop and use the plan.
- Do NOT fall back to bag-of-words queries on retry after a rejection — the guardrail is structural.

## Search SOP — `search_academic_databases`

The tool **hard-rejects** bag-of-words natural-language queries (e.g. `"vision language model survey benchmark"`) unless a structured filter narrows the search. Use one of the four precise query forms, optionally combined with OpenAlex-native filters.

### Query forms

| Form | Example | Use case |
|------|---------|---------|
| DOI direct | `query="10.48550/arxiv.2103.00020"` | Known seminal paper |
| Author-anchored | `query="author:Radford CLIP"` | Known author + topic token |
| Quoted phrase | `query='"visual instruction tuning"'` | Canonical topic term |
| Boolean | `query='"LLaVA" OR "Flamingo" OR "GPT-4V"'` | Method cluster |

### Filters (stack for precision)

| Param | Value | Effect |
|-------|-------|--------|
| `concepts` | `["Computer vision", "Natural language processing"]` | Restrict to OpenAlex concept hierarchy. Escapes fuzzy-query rejection. |
| `venue` | `"CVPR"` / `"NeurIPS"` / `"IEEE TPAMI"` / `"ICLR"` | Restrict to one publication venue. |
| `institutions` | `["Google DeepMind", "Stanford University"]` | Restrict to specific affiliations. |
| `min_citations` | `100` | Cut long tail; tune to topic age. |
| `oa_only` | `true` | Only papers with open-access PDF. |
| `year_min` / `year_max` | `2023` | Publication window. |
| `cursor` | from previous response | Next page (cursor-based pagination). |

### Recipes

- **Known seminal paper** → DOI direct. Fastest, zero noise.
- **Topic discovery on niche term** → `query='"vision-language model"'`, `venue="IEEE TPAMI"`, `year_min=2023`, `sort_by="citations"`.
- **Method cluster survey** → `query='"LLaVA" OR "MiniGPT-4" OR "InstructBLIP"'`, `year_min=2023`.
- **Concept-anchored browse** (bag-of-words becomes OK) → `query="instruction tuning"`, `concepts=["Computer vision"]`, `min_citations=50`.
- **Seed expansion** (after finding 1-2 anchors) → `get_citations(direction="citing", doc_id=<seed>)` to walk the citation graph.

### Response shape

`search_academic_databases` now returns a dict (not a list):
```json
{
  "results": [...],
  "next_cursor": "string|null",
  "total_count": 1234,
  "unresolved_filters": ["venue:Foobar"]   // names that failed name→ID resolution
}
```

If `unresolved_filters` is non-empty, correct the name and retry (e.g. `"TPAMI"` → `"IEEE Transactions on Pattern Analysis and Machine Intelligence"`).

## Hard Rules
- Never skip Phase 1 step 5 (user must select candidates before ingest)
- If `action_required` is non-empty → STOP, surface to user, do NOT work around
- Never substitute web search for `search_academic_databases`
- Post-processing tags must prefer existing vocabulary over inventing new tags
- Treat `manage_tags(action="set")` as destructive — use `add`/`remove` instead
- Do not report "完成" if any paper has missing post-processing steps

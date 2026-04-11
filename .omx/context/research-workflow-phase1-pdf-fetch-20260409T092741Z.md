Task statement:
Investigate, fix, and test Phase 1 of the research workflow: document fetch and PDF acquisition. Focus on why papers that should get PDFs do not end with one, without assuming the Connector itself is broken.

Desired outcome:
- Per-item ingest status explains route choice, save method, item discovery, PDF verification state, and concrete failure reason.
- PDF verification no longer collapses to a single boolean and no longer misreports late PDFs as missing.
- Research workflow reports can explain whether a paper was connector primary, API primary, or connector-to-API fallback.
- Focused tests cover the repaired Phase 1 behavior.

Known facts / evidence:
- Direct user testing suggests the Connector itself is healthy.
- Current legacy ingest path stores only boolean `has_pdf` in `IngestItemState`.
- Current PDF verification is a one-shot `check_has_pdf()` call after reconciliation.
- Current workflow/reporting cannot explain per-item why a PDF is missing.
- Current route contract exists implicitly across `ingestion_search.py`, `_ingest.py`, and `ingestion_bridge.py`.

Constraints:
- Limit implementation scope to Phase 1 fetch/PDF diagnosis, repair, and testing.
- Preserve batch-centric architecture.
- Do not revert to `research_session`.
- Use apply_patch for manual edits.
- Do not overwrite unrelated dirty worktree state.

Unknowns / open questions:
- Exact retry window that best balances async Zotero downloads vs user responsiveness.
- Whether legacy ingest state should carry tri-state PDF fields directly or via additive parallel fields.
- Which existing tests are easiest to extend vs replace.

Likely codebase touchpoints:
- `src/zotpilot/tools/ingestion/_ingest.py`
- `src/zotpilot/tools/ingestion_bridge.py`
- `src/zotpilot/tools/ingest_state.py`
- `src/zotpilot/tools/research_workflow.py`
- `src/zotpilot/workflow/batch.py`
- `src/zotpilot/workflow/worker.py`
- `src/zotpilot/zotero_writer.py`
- relevant ingestion and workflow tests under `tests/`

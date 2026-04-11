Task statement:
Implement Phase 2 of the research workflow repair: efficient duplicate-detection semantics and stable route semantics.

Desired outcome:
- Exact duplicates are still auto-resolved.
- High-confidence suspected duplicates are surfaced as advisory only and never block ingest.
- Agent-facing results distinguish duplicate vs suspected duplicate without subjective merging.
- Route semantics remain explicit and low-friction.

Known facts / evidence:
- Exact DOI duplicate handling already exists in `src/zotpilot/tools/ingestion/_ingest.py`.
- Phase 1 already introduced route visibility fields.
- The user wants to preserve agent efficiency; low-confidence duplicate checks must not block the workflow.

Constraints:
- Keep batch-centric architecture.
- Do not introduce expensive fuzzy matching or new dependencies.
- Use conservative, high-confidence collision detection only.
- Preserve exact duplicate behavior for library and batch DOI duplicates.

Unknowns / open questions:
- Whether candidate-stage suspected duplicate surfacing should be added later.
- Whether author/year should be folded into collision logic in a later pass.

Likely codebase touchpoints:
- `src/zotpilot/tools/ingestion/_shared.py`
- `src/zotpilot/tools/ingestion/_ingest.py`
- `src/zotpilot/tools/ingest_state.py`
- `tests/test_tools_ingestion.py`
- `tests/test_ingest_state.py`

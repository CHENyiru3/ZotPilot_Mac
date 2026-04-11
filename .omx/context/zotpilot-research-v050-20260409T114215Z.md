Task statement:
Polish ZotPilot's batch-centric research workflow to meet the planned v0.5.0 behavior, with emphasis on truthful post-ingest execution and release-grade E2E coverage.

Desired outcome:
- Research workflow is reliable end-to-end for the v0.5.0 contract.
- Post-process status reflects real work done, not inferred success.
- Release-gate mock E2E tests exist and pass.
- A real workflow replay reaches a stable terminal or clearly diagnosed checkpointed state.

Known facts / evidence:
- Existing v0.5.0 plans live in `.omx/plans/zotpilot-0.5.0-*.md`.
- Phase 1 and Phase 2 ingest semantics are already partially implemented in the current worktree.
- A real workflow replay successfully completed discovery, preflight, ingest, and post-ingest verification, then stalled in `post_processing`.
- `src/zotpilot/workflow/worker.py` currently marks `tagged=True` and `classified=True` from `_index_item()` without actually performing note/classify/tag operations.
- Current repository tests pass, but there is no dedicated `tests/e2e/` mock suite for the release scenarios.

Constraints:
- Stay batch-centric; do not reintroduce `research_session` as workflow authority.
- Prefer truthful, minimal behavior over speculative automation.
- No new dependencies.
- Keep compatibility with current tool surface unless a v0.5.0 canonicalization is explicitly required.

Unknowns / open questions:
- Whether post-process should fully automate note/classify/tag now, or stop at truthful indexing plus explicit partial reporting.
- Why the real post-process run stalled in `post_processing` for the observed batch.
- Which subset of the 18 planned E2E scenarios should become enforced automated release gates in this pass.

Likely codebase touchpoints:
- `src/zotpilot/workflow/worker.py`
- `src/zotpilot/tools/research_workflow.py`
- `src/zotpilot/workflow/batch.py`
- `src/zotpilot/tools/write_ops.py`
- `src/zotpilot/tools/library.py`
- `tests/test_research_workflow_smoke.py`
- `tests/test_post_process_gate.py`
- `tests/e2e/*`

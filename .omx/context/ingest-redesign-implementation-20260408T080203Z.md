Task statement:
Implement the ingest redesign from `.omc/specs/ingest-redesign-technical-doc.md` using a multi-agent execution approach and drive it to verified completion.

Desired outcome:
- New batch-centric research workflow replaces legacy `research_session` + `ingest_papers` gate model.
- Public MCP surface matches the spec's 10 workflow tools.
- Legacy session workflow code/tests are removed or neutralized per the spec.
- Fixtures/tests/lint/type checks pass with fresh evidence.

Known facts / evidence:
- New workflow skeleton files exist: `src/zotpilot/tools/research_workflow.py`, `src/zotpilot/workflow/batch.py`, `batch_store.py`, `worker.py`.
- Targeted checks already pass:
  - `uv run pytest --no-cov tests/test_state.py::TestMCPInstructions tests/test_tool_profiles.py tests/test_research_workflow_smoke.py -q`
- User-provided acceptance report says remaining issues include:
  - legacy session files/tests still present
  - full test suite not clean
  - ruff/mypy failures
  - P10 LOC / fixture obligations not met
- Dirty worktree exists in relevant files; must not overwrite unrelated in-progress user edits.

Constraints:
- Follow `/Users/zxd/ZotPilot/AGENTS.md`.
- No new dependencies.
- Use apply_patch for manual edits.
- Need end-to-end verified completion, not a partial skeleton.
- Ralph requires persistence, architect-grade verification, and no scope reduction.

Unknowns / open questions:
- Which existing dirty changes are user-owned vs prior agent-owned.
- Exact minimal deletion set that keeps the tree green while migrating old tests/docs.
- Whether current spec fixtures are intended to be built now or staged behind TODOs.

Likely codebase touchpoints:
- `src/zotpilot/tools/research_workflow.py`
- `src/zotpilot/workflow/{batch.py,batch_store.py,worker.py,__init__.py}`
- `src/zotpilot/tools/{ingestion.py,indexing.py,workflow.py,write_ops.py,admin.py,__init__.py}`
- `src/zotpilot/state.py`
- `src/zotpilot/skills/ztp-research.md`
- `SKILL.md`
- `tests/` workflow/session/index gate coverage files
- possibly `docs/` / `.omx/plans/` references if verification expects them

Risk tradeoff:
Proceeding without `docs/shared/agent-tiers.md` because it is absent in the workspace. Agent tiering will use the available built-in roster directly.

Task statement:
Produce a consensus remediation plan for the current ZotPilot research workflow drift, aligned to the latest batch-centric architecture and incident guardrail docs.

Desired outcome:
- A repair plan that supersedes stale partial-fix docs.
- Clear agent expected behavior for each workflow phase/checkpoint.
- Explicit verification and acceptance criteria for future implementation.

Known facts / evidence:
- `docs/architecture.md` declares batch-centric workflow as the current authority.
- `src/zotpilot/skills/references/post-ingest-incidents.md` records required code-level guardrails after the 2026-04-08 incident.
- Current implementation still has drift: fake `tagged/classified` success, no-op `index_library(session_id)` gate, stale `research_session` references in skills/docs/tests, and a PDF verification race.
- `docs/plan-ingestion-fix.md` is a narrower earlier patch plan and does not reflect the current target state.

Constraints:
- Keep batch-centric workflow as the target architecture.
- No implementation in this step; planning only.
- Plan must cover code, skills/docs, tests, and agent behavior.

Unknowns / open questions:
- Whether taxonomy authorization should be fully implemented now or hidden until producers exist.
- Whether agent-callable approve tools are sufficient, or must be further hardened / moved behind a stronger UX gate.
- Whether legacy ingest should stay visible in the `research` profile after the refactor.

Likely codebase touchpoints:
- `src/zotpilot/workflow/{batch.py,worker.py,batch_store.py}`
- `src/zotpilot/tools/{research_workflow.py,indexing.py,library.py}`
- `src/zotpilot/tools/ingestion/*`
- `src/zotpilot/skills/ztp-research.md`
- `SKILL.md`
- `docs/{architecture.md,tools-reference.md,e2e-v0.5.0.md,plan-ingestion-fix.md}`
- `tests/` workflow, ingest, and incident replay coverage

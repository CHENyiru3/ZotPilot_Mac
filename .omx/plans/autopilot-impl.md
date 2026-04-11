# Autopilot Implementation Brief: ZotPilot Research v0.5.0 Polish

## Workstreams

### A. Post-process truthfulness

- Audit `workflow/worker.py` and `tools/research_workflow.py`.
- Remove inferred success flags.
- Ensure persisted batch phase/report only reflect completed work.

### B. Canonical research workflow completion

- Make the batch-centric flow stable through:
  - candidate discovery
  - preflight
  - ingest
  - post-ingest verification
  - post-process verification
  - final approval

### C. Release-gate E2E tests

- Add mock E2E tests under `tests/e2e/` for the canonical research flow.
- Cover saved vs partial outcomes and persisted phase transitions.

### D. Real replay verification

- Re-run the actual research workflow after code changes.
- Capture the resulting batch phase, item state, and any remaining blockers.

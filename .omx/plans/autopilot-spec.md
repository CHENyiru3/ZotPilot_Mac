# Autopilot Spec: ZotPilot Research v0.5.0 Polish

## Scope

Deliver the batch-centric v0.5.0 research workflow to a release-ready state.

Primary goals:

1. Make post-ingest execution truthful and persistent.
2. Preserve the already-repaired ingest explainability semantics.
3. Add release-gate E2E coverage for canonical research flow.
4. Validate with both automated tests and a real workflow replay.

## Non-goals

- Reintroducing `research_session` as workflow authority
- Large architecture rewrites beyond the current batch-centric design
- Inventing speculative taxonomy automation without evidence or tests

## Required behavior

### Workflow truthfulness

- `post_processing` must mean real work is in progress.
- `post_process_verified` must only be reported when persisted item state matches work actually completed.
- `done` must only be reachable after a truthful post-process report exists.

### Per-item truth

- `indexed`, `tagged`, and `classified` cannot be inferred from unrelated work.
- Partial outcomes must remain partial instead of being promoted to full success.

### E2E coverage

- At minimum, automated E2E must cover:
  - canonical research flow
  - no false advance before ingest completion
  - truthful post-process completion
  - successful items only advance through downstream steps

## Acceptance Criteria

1. A real workflow replay reaches at least truthful `post_process_verified` or produces a concrete diagnosed blocker with persisted state.
2. Mock E2E tests exist for the canonical batch-centric research flow and pass.
3. `uv run pytest` passes.
4. `uv run mypy src` passes.

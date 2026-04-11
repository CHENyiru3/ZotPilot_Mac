# Research Workflow Repair Execution Plan

Status: proposed
Updated: 2026-04-09
Scope: batch-centric research workflow repair

## Purpose

This plan turns the current ralplan consensus into a locally executable technical plan.
The objective is to repair the research workflow without rolling back to `research_session`
or treating the Connector as the default root cause.

The dominant problems are:

1. agent call-path selection and fallback behavior
2. route and state interpretation for each ingested paper
3. duplicate-detection semantics
4. post-process completion being reported before persistence is verified

## Phase Roadmap

Execution is split into four phases so the highest-risk ambiguity is removed first.

### Phase 1: Document Fetch and PDF Acquisition

Goal:

- explain why a paper that should have a PDF does not end with one
- separate preflight outcome, connector save outcome, API fallback, item discovery, and PDF verification
- make fetch-path results auditable per item

Primary focus:

- `preflight`
- `connector primary`
- `api primary`
- `connector -> api fallback`
- `present / pending / missing`

### Phase 2: Duplicate and Route Semantics

Goal:

- define exact duplicate vs suspected duplicate
- stabilize route choice and fallback language

### Phase 3: Post-Process Truthfulness

Goal:

- make `index -> note -> classify -> tag -> verify` real
- stop reporting inferred success

### Phase 4: Docs, Tests, and Replay

Goal:

- align skills and docs to real workflow semantics
- lock repaired behavior with regression and replay coverage

## Authority

Current target state is defined by:

- `docs/architecture.md`
- `src/zotpilot/skills/references/post-ingest-incidents.md`

The following are historical reference only and must not define the new target state:

- `docs/plan-ingestion-fix.md`
- stale `research_session` references in docs or skills

## ADR

Decision:

- Keep `Batch` + phase state machine as the sole workflow authority.
- Do not reintroduce `research_session`.
- Do not treat Connector defects as the primary hypothesis unless new evidence appears.
- Move explainability and completion truthfulness into code, not prompt prose.

Drivers:

1. The latest architecture is batch-centric.
2. Incident handling requires code-level guardrails, not agent self-discipline.
3. User trust is currently damaged by false negatives on PDF presence and false positives on post-process completion.

Alternatives considered:

1. Patch only the PDF race
   Rejected: does not fix route semantics, false completion, or per-item explainability.
2. Roll back to `research_session`
   Rejected: conflicts with current architecture and would create dual workflow truth.
3. Keep legacy ingest as the default research path
   Rejected: preserves bypass paths and ambiguous behavior.

Consequences:

- Legacy ingest remains for compatibility, but not as the default research orchestration path.
- The state model and docs will both change.
- Tests must move from "worker ran" to "state is causally and persistently true".

## Design Goals

1. Every imported paper must be explainable.
2. PDF status must be tri-state: `present`, `pending`, or `missing`.
3. Route selection must be explicit and auditable.
4. Duplicate semantics must distinguish exact duplicates from possible collisions.
5. `post_process_verified` must mean persistence was verified, not merely that a worker finished.

## Per-Item Causal Model

Every workflow item should expose the following minimum fields in workflow status and final report:

- `route_selected`
- `save_method_used`
- `item_discovery_status`
- `pdf_verification_status`
- `reason_code`

### Field semantics

`route_selected`

- `connector_primary`
- `api_primary`

`save_method_used`

- `connector_primary`
- `api_primary`
- `connector_to_api_fallback`

`item_discovery_status`

- `known_item_key`
- `discovered_local`
- `discovered_web`
- `ambiguous`
- `not_found`

`pdf_verification_status`

- `present`
- `pending`
- `missing`

`reason_code`

Initial closed set:

- `connector_save_pending_pdf`
- `api_metadata_only`
- `oa_pdf_not_found`
- `pdf_attach_failed`
- `verification_timeout`
- `connector_item_not_found`
- `connector_save_failed`
- `api_resolution_failed`
- `duplicate_library_doi`
- `duplicate_batch_doi`
- `suspected_duplicate`

## Route Contract

### Selection rules

1. `arxiv_id` present -> `connector_primary`
2. valid landing page URL present -> `connector_primary`
3. DOI resolves to a valid landing page URL -> `connector_primary`
4. DOI present but no valid landing page URL -> `api_primary`
5. no usable identifier -> reject

### Fallback rules

1. `connector_to_api_fallback` is allowed only when connector save clearly fails.
2. Research agents must not replace a blocked or failed connector path with ad hoc `save_urls` retries.
3. `api_primary` or `connector_to_api_fallback` must never be described as equivalent to browser-backed PDF capture.

## Phase 1 Technical Scope

Phase 1 is intentionally narrow: it stops at the question "why did this paper end with `present`, `pending`, or `missing` PDF status?"

### Phase 1 objectives

1. make preflight outcomes explicit
2. make route selection explicit per item
3. make save-path outcome explicit per item
4. make item discovery outcome explicit per item
5. replace one-shot PDF checking with bounded verification

### Phase 1 implementation touchpoints

- `src/zotpilot/tools/ingestion/_ingest.py`
- `src/zotpilot/tools/ingestion_bridge.py`
- `src/zotpilot/tools/ingestion_search.py`
- `src/zotpilot/zotero_writer.py`
- `src/zotpilot/workflow/batch.py`
- `src/zotpilot/tools/research_workflow.py`

### Phase 1 required per-item fields

- `route_selected`
- `save_method_used`
- `item_discovery_status`
- `pdf_verification_status`
- `reason_code`

Optional fields if needed for observability:

- `preflight_status`
- `verification_attempts`
- `verification_window_s`

### Phase 1 failure taxonomy

At minimum, Phase 1 must distinguish these causes:

1. `preflight_blocked`
2. `connector_save_failed`
3. `connector_item_not_found`
4. `connector_save_pending_pdf`
5. `verification_timeout`
6. `api_metadata_only`
7. `oa_pdf_not_found`
8. `pdf_attach_failed`

### Phase 1 interpretation rules

1. `preflight_blocked` is a hard stop, not a degraded success.
2. `connector primary` + `pending` means "verification window still open", not "missing".
3. `api primary` or `connector_to_api_fallback` + `missing` should first be explained as metadata-only or OA attach unavailability.
4. A connector route that never yields a discoverable Zotero item must be reported as explicit failure, not silent degradation.

### Phase 1 deliverables

1. tri-state PDF verification
2. per-item fetch-path causal chain
3. reason-code mapping for fetch outcomes
4. focused tests proving:
   - late-arriving PDF is `pending` before `present`
   - API metadata-only cases end with the correct reason code
   - preflight blocked does not masquerade as success
   - connector-reported success without a discoverable item becomes explicit failure

## Duplicate Semantics

### Exact duplicates

- `library duplicate`: DOI-exact duplicate already in Zotero
- `batch duplicate`: DOI-exact duplicate within current batch

### Non-blocking collision

- `suspected duplicate`: title/URL collision without DOI-equivalent proof

Rules:

1. `suspected duplicate` is advisory only.
2. It must not silently block ingest.
3. It must not be auto-merged.
4. Agents must not collapse preprint, journal, or camera-ready variants unless the code has exact evidence.

## PDF Verification Standard

The current boolean `has_pdf` behavior is insufficient.

### Required behavior

1. After item save, PDF verification enters a bounded retry window.
2. During the window, the item may be `pending`.
3. If a PDF appears within the window, status becomes `present`.
4. If the window expires without a PDF, status becomes `missing`.

### Suggested initial parameters

- retry count: 3
- retry backoff: short bounded backoff
- total verification window: short enough for responsive review, long enough for async Zotero download

Exact values should be chosen in implementation and covered by tests.

### Reporting rules

1. `pending` must never be presented as `missing`.
2. `missing` must always carry a concrete `reason_code`.
3. `api_primary` and `connector_to_api_fallback` should preferentially explain `missing` as metadata-only or OA attach unavailable before blaming Connector.

## Post-Process Standard

### Canonical order

1. `index`
2. `note`
3. `classify`
4. `tag`
5. `verify`

### Persistence checks

Each step must verify persistence by reading the system of record:

- `index`: reachable via index metadata or search
- `note`: visible via `get_notes`
- `classify`: visible via collection membership
- `tag`: visible via `get_paper_details`

### Completion semantics

`post_process_verified` means final verification passed.

If needed, introduce `post_processing_done` for "execution finished but final verification has not passed".

No field should infer:

- `indexed == true` -> `tagged == true`
- `indexed == true` -> `classified == true`

Any failure after index must downgrade the item to `partial` or `degraded`.

## Agent Behavior Contract

### Candidate review

- show candidates
- show exact duplicates
- show suspected duplicates
- do not discuss PDF outcomes yet

### Ingest running

- only poll
- do not announce per-item PDF, tagging, or classification conclusions early

### Post-ingest review

Per item, the agent must present:

- `route`
- `pdf_verification_status`
- `reason_code`

Rules:

- `pending` is not `missing`
- `api_primary` and `connector_to_api_fallback` missing-PDF cases should not default to Connector blame

### Post-process

- execute only in canonical order
- downgrade to `partial` on any failed write-or-verify step

### Final acceptance

Per item category must be one of:

- `full_success`
- `metadata_only`
- `partial`
- `failure`

Each item must include a short causal summary.

## Execution Lanes

### Lane A: Core

Primary files:

- `src/zotpilot/tools/ingestion_search.py`
- `src/zotpilot/tools/ingestion_bridge.py`
- `src/zotpilot/tools/ingestion/_ingest.py`
- `src/zotpilot/workflow/worker.py`

Tasks:

1. codify route contract
2. codify save-method semantics
3. implement duplicate semantic split
4. remove fake post-process success propagation

### Lane B: State Model

Primary files:

- `src/zotpilot/workflow/batch.py`
- `src/zotpilot/tools/research_workflow.py`
- possibly `src/zotpilot/tools/ingest_state.py` for legacy compatibility shaping

Tasks:

1. add causal fields
2. replace boolean PDF semantics with tri-state model
3. define bounded pending window
4. refine workflow completion phases if necessary

### Lane C: Docs

Primary files:

- `src/zotpilot/skills/ztp-research.md`
- `SKILL.md`
- `docs/tools-reference.md`
- `docs/e2e-v0.5.0.md`

Tasks:

1. remove stale session-era instructions
2. document route contract
3. document PDF tri-state and reason codes
4. document post-process verify-only completion meaning

### Lane D: Tests

Primary files:

- `tests/test_research_workflow_smoke.py`
- add or update focused regression and integration coverage near workflow and ingestion tests

Required coverage:

1. PDF tri-state
2. connector primary / api primary / connector-to-api fallback
3. library duplicate / batch duplicate / suspected duplicate
4. post-process write-after-read
5. transcript-style replay for:
   - false missing-PDF due to early verification
   - reported tag/classify success without persistence
   - mis-grouped outlier item

## Suggested Sequence

1. core route and duplicate semantics
2. state-model changes for causal fields and PDF tri-state
3. post-process truthfulness changes
4. tests for the new semantics
5. docs alignment
6. transcript replay
7. real Zotero manual replay

## Verification Plan

### Focused regression

- route contract tests
- PDF tri-state tests
- duplicate semantic tests
- post-process truthfulness tests

### Integration

- full batch path from candidate confirmation to final review
- per-item causal chain presence
- write-after-read verification gates

### Manual replay

Required scenarios:

1. item reports `pending` then becomes `present`
2. item goes `api_primary` and ends `missing` with `api_metadata_only` or OA-related reason
3. outlier paper is preserved and not auto-merged by suspected-duplicate logic
4. post-process does not report classification/tagging success unless read-back confirms it

## Done Criteria

This plan is complete when:

1. a paper with late PDF arrival is not falsely reported as missing
2. every missing-PDF item has a concrete reason code
3. route choice is visible and explainable per item
4. duplicate and suspected-duplicate semantics are distinct
5. `post_process_verified` only occurs after successful read-back verification
6. skills, docs, and tests all describe the same workflow semantics

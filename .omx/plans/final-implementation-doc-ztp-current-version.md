# Final Implementation Document: ZotPilot Current-Version Workflow Refactor

## Status

This document is the current-version implementation source of truth.

Execution rule:
- if this document conflicts with older planning artifacts, this document wins for current-version implementation
- the test authority remains [test-spec-ztp-lifecycle-architecture.md](/Users/zxd/ZotPilot/.omx/plans/test-spec-ztp-lifecycle-architecture.md)
- deferred surfaces or ideas must not be reintroduced into current-version scope without updating this document first

Planning sources:
- [PRD](/Users/zxd/ZotPilot/.omx/plans/prd-ztp-lifecycle-architecture.md)
- [Test Spec](/Users/zxd/ZotPilot/.omx/plans/test-spec-ztp-lifecycle-architecture.md)
- [Execution Breakdown](/Users/zxd/ZotPilot/.omx/plans/execution-breakdown-ztp-lifecycle-architecture.md)
- [RALPLAN Draft](/Users/zxd/ZotPilot/.omx/plans/ztp-skill-mcp-architecture-ralplan-dr.md)

External-review support:
- [Claude consensus artifact](/Users/zxd/ZotPilot/.omx/artifacts/claude-ztp-architecture-consensus-20260401T173107Z.md)
- [Gemini consensus artifact](/Users/zxd/ZotPilot/.omx/artifacts/gemini-ztp-architecture-consensus-20260401T173107Z.md)

## Document Role

This document answers only four questions:

- what is in scope now
- what architectural contract must be implemented
- in what order implementation should proceed
- what must be true before each next stage starts

This document does not replace:
- detailed runtime-schema design
- detailed test cases
- commit-by-commit implementation notes

## Current-Version Scope

Implement in this version:
- `ztp-research`
- `ztp-setup`
- `ztp-review`
- `ztp-profile`
- root `zotpilot` compatibility shell reduction
- workflow runtime contract
- workflow-scoped capability packs
- minimum MCP repair needed to make `ztp-research` executable end to end

Defer to next version:
- `ztp-guider`

Keep as lifecycle contracts, not standalone user skills:
- `update`
- `development/release`

Out of scope:
- multiple MCP servers
- full MCP rewrite
- generic orchestration framework

## Version Goal

Ship a current version where explicit workflow invocation is reliable.

The primary proof target is:
- a user invokes `ztp-research`
- the system follows the declared research workflow
- generic web drift is blocked by default
- mandatory checkpoints are enforced
- post-ingest stages complete automatically after approval
- runtime state survives pause, restart, partial success, and library drift

Non-goals for this version:
- launching `ztp-guider`
- redesigning every MCP tool API
- removing `core` / `extended` / `all` immediately
- making `update` or `development/release` into direct user skills

## Final Product Surfaces

Specialized skills in this version:
- `ztp-research`
- `ztp-setup`
- `ztp-review`
- `ztp-profile`

Compatibility surface:
- root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md)

Deferred surface:
- `ztp-guider`

Canonical user paths in this version:
- literature discovery and ingest closure -> `ztp-research`
- install / config / register / first-index -> `ztp-setup`
- local-library review and synthesis -> `ztp-review`
- library/profile analysis -> `ztp-profile`
- legacy/vague entry -> compatibility shell, which must route and not re-implement

## Legacy-To-New Mapping

| Existing surface | Current-version destination |
| --- | --- |
| `External Discovery` | `ztp-research` |
| `Direct Ingest` | `ztp-research` subflow |
| `Local Search` | shared capability path used by `ztp-review`, `ztp-profile`, and `ztp-research` verification |
| `Organize` | absorbed into `ztp-research` post-ingest and `ztp-profile` recommendations |
| `Profile` | `ztp-profile` |
| setup guidance | `ztp-setup` |
| update guidance | lifecycle `update` contract |
| deep note / guided read | deferred to next-version `ztp-guider` or later `ztp-review` mode |
| root intent router | compatibility shell only |

## Architecture Contract

The implemented architecture must have exactly four layers:

1. Workflow skills
2. Workflow runtime contract
3. MCP capability packs
4. Internal domain services

Layer rules:
- workflow skills own stage order, checkpoints, and user-facing policy
- runtime owns state, resumability, failure semantics, and policy enforcement hooks
- MCP exposes capabilities, not hidden product workflows
- services own orchestration that should not stay in tool entrypoints

Hard constraints:
- one MCP server only
- workflow-scoped packs are the product contract
- `core` / `extended` / `all` are compatibility aliases only
- current-version implementation must prove `ztp-research` before broadening surface work

## Workflow Runtime Contract

This is the first implementation artifact and must be completed before deep MCP refactors.

Required outputs:
- runtime contract document
- state schema
- checkpoint schema
- failure-state schema
- policy ownership map
- workflow anchor design
- delta-check rules

Required runtime fields:
- `workflow_id`
- `workflow_type`
- `status`
- `stage`
- `active_checkpoint`
- `allowed_capability_pack`
- `resume_token`
- `blocker_reason`
- `next_resumable_action`
- `completed_outputs`
- `partial_failures`
- per-item state for multi-paper workflows

Required statuses:
- `running`
- `awaiting_user`
- `partial-success`
- `blocked`
- `restart-required`
- `resume-invalidated`
- `completed`
- `cancelled`
- `failed`

Required checkpoint ids:
- `candidate-review`
- `post-ingest-review`
- `restart-required`

Policy ownership must be explicit for:
- generic web drift blocking
- capability allow/deny checks
- checkpoint persistence
- partial-success progression
- resumed-run validity

## Native Workflow Anchor

Runtime state alone is not enough. The implementation must anchor active workflows back to Zotero state.

Accepted design direction:
- hidden workflow tag, tracking note, or equivalent durable marker linked to the active workflow

Must support:
- linking per-paper workflow state to library state
- pre-flight delta checks before expensive downstream work
- detection of manual library edits while the workflow is paused
- safe transition to `resume-invalidated` when drift breaks continuation

Mandatory delta-check stages:
- before `index`
- before `classify`
- before `note`
- before `tag`
- before resume after `restart-required`

## Capability Packs

Primary contract:
- workflow-scoped packs

Compatibility-only aliases:
- `core`
- `extended`
- `all`

### `research` pack

Required in this version:
- `search_academic_databases`
- `advanced_search`
- `get_paper_details`
- `ingest_papers`
- `get_ingest_status`
- `index_library`
- `browse_library`
- `manage_tags`
- `manage_collections`
- `create_note`

Optional later:
- `search_tables`
- `search_figures`
- `get_annotations`
- citation-expansion extras

Forbidden by default:
- generic web discovery when ZotPilot discovery is available for the active stage

### `setup` pack

Required:
- config validation
- diagnostics
- register/setup helpers
- index readiness checks

### `profile` pack

Required:
- library browse
- profile analysis
- topic search
- optional notes/annotations when available

## MCP Adaptation Strategy

### Reuse directly

- `search_academic_databases`
- `advanced_search`
- `get_paper_details`
- `ingest_papers`
- `get_ingest_status`

### Promote into default `research` path

- `index_library`
- `browse_library`
- `manage_tags`
- `manage_collections`
- `create_note`

### Repair internally

- [src/zotpilot/tools/profiles.py](/Users/zxd/ZotPilot/src/zotpilot/tools/profiles.py)
- [src/zotpilot/tools/ingestion.py](/Users/zxd/ZotPilot/src/zotpilot/tools/ingestion.py)
- runtime/state support under `src/zotpilot/`

Repair boundary:
- do not rewrite the whole tool suite
- do thin orchestration-heavy tools
- do preserve one server entrypoint
- do preserve stable external signatures where practical

## Workflow Definitions

### `ztp-research`

Stages:
- clarify query
- external discovery
- score candidates
- user review checkpoint
- ingest
- ingest verification
- post-ingest checkpoint
- index
- classify
- note
- tag
- final report

Intelligence zones:
- candidate scoring and explanation
- collection suggestion
- note synthesis
- tag selection from existing vocabulary

Deterministic zones:
- discovery source choice
- checkpoint enforcement
- ingest polling
- ingest verification
- post-ingest sequencing
- resume and drift handling

Must prove:
- no default generic web drift
- both checkpoints enforced
- downstream steps auto-run after approval
- final report is per-paper and stateful

### `ztp-setup`

Stages:
- detect environment
- choose provider
- write config
- register MCP
- restart-required
- initial-index-ready

Rules:
- preserve CLI authority for machine actions
- separate pre-MCP bootstrap from post-MCP readiness
- persist restart boundary

### `ztp-review`

Stages:
- clarify review topic
- local library scope
- cluster topic
- extract passages
- optional citation expansion
- outline
- synthesis
- refinement checkpoint
- final review

Rule:
- local-library-first

### `ztp-profile`

Stages:
- scan library
- infer themes
- dialogue checkpoint
- write/update profile artifact
- optional organization recommendations

Rule:
- broad write operations require explicit confirmation

## File Ownership And Likely Touchpoints

### Contracts and docs

- new implementation/runtime contract doc under `.omx/plans/` or `docs/`
- [README.md](/Users/zxd/ZotPilot/README.md)
- [docs/architecture.md](/Users/zxd/ZotPilot/docs/architecture.md)
- root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md)

### Runtime and service layer

- [src/zotpilot/state.py](/Users/zxd/ZotPilot/src/zotpilot/state.py)
- new workflow runtime/state service module(s) under `src/zotpilot/`
- new service module(s) for post-ingest orchestration and policy enforcement

### MCP adaptation

- [src/zotpilot/tools/profiles.py](/Users/zxd/ZotPilot/src/zotpilot/tools/profiles.py)
- [src/zotpilot/tools/ingestion.py](/Users/zxd/ZotPilot/src/zotpilot/tools/ingestion.py)
- related tool modules for indexing, library browse, write operations

### Skill surfaces

- new `ztp-research` skill asset
- new `ztp-setup` skill asset
- new `ztp-review` skill asset
- new `ztp-profile` skill asset

## Change Control

Before implementation broadens scope, all of the following must be updated together:
- this implementation document
- [test-spec-ztp-lifecycle-architecture.md](/Users/zxd/ZotPilot/.omx/plans/test-spec-ztp-lifecycle-architecture.md)
- the relevant compatibility or migration note if user-facing behavior changes

Scope changes that require an explicit document update:
- pulling `ztp-guider` back into this version
- broadening `core` into the primary product contract
- introducing a second MCP server
- changing the proof-first order

## Implementation Phases

### Phase A: Runtime contract

Deliver:
- runtime contract doc
- state and checkpoint model
- workflow anchor contract
- delta-check contract
- policy ownership map

Exit:
- no ambiguity remains on state ownership or drift handling

### Phase B: Capability matrix

Deliver:
- workflow-to-pack matrix
- pack-to-tool map
- compatibility alias policy

Exit:
- `ztp-research` pack closes the default loop

### Phase C: `ztp-research` proof

Deliver:
- research skill surface
- runtime-controlled stage progression
- checkpoints
- partial-success handling
- anchor-backed resume logic

Exit:
- canonical research flow works end to end

### Phase D: Compatibility shell reduction

Deliver:
- root shell reduced to routing and migration messaging
- sunset milestones for legacy shell behavior

Exit:
- root shell no longer re-implements product workflows

### Phase E: `ztp-setup`

Deliver:
- setup skill
- explicit bootstrap/restart flow

Exit:
- clean-machine setup is viable and resumable

### Phase F: `ztp-review` and `ztp-profile`

Deliver:
- both specialized skills
- shared runtime usage

Exit:
- both surfaces run without umbrella ambiguity

### Phase G: Service extraction and docs

Deliver:
- thin tool boundaries
- service extraction where needed
- README / architecture / migration updates

Exit:
- workflow logic is no longer stranded in prose or the wrong tool layer

## Verification Gates

### Gate 1

- runtime contract approved
- capability matrix approved

### Gate 2

- `ztp-research` proof passes:
  - checkpoint tests
  - capability policy tests
  - partial-success tests
  - resume-invalidated tests
  - drift detection tests

### Gate 3

- `ztp-setup` passes:
  - clean-machine setup
  - restart-required
  - post-restart readiness

### Gate 4

- `ztp-review` and `ztp-profile` run on the shared runtime

### Gate 5

- compatibility shell reduced
- docs aligned
- sunset milestones documented

Gate rule:
- no later gate may start until the current gate's exit conditions are met and linked evidence exists

## Required Test Coverage

Must be covered from the approved test spec:
- blocked generic web drift
- disallowed capability calls
- partial-success
- `restart-required`
- `resume-invalidated`
- `editable` / `uv` / `pip` update modes
- dirty-tree / symlink update safeguards
- native workflow anchor detecting Zotero-side drift
- legacy surface mapping remaining non-orphaned

## Definition Of Done

The current version is done only when all of the following are true:

- one MCP server remains
- `ztp-research` is the primary working proof workflow
- `ztp-setup`, `ztp-review`, and `ztp-profile` exist as specialized current-version surfaces
- `ztp-guider` is explicitly deferred and not half-implemented
- root shell routes rather than re-implements
- workflow runtime is the source of truth for stage/checkpoint state
- Zotero-linked workflow anchor exists and drift checks are enforced
- workflow-scoped packs, not `core`, are the real product contract
- promoted MCP tools close the default research loop
- docs and tests reflect the implemented architecture

Minimum release posture for this version:
- current-version scope complete
- deferred scope still deferred
- compatibility behavior documented
- no known contradiction remains between implementation and validation documents

## Immediate Next Document

The next document to write is:

- `workflow-runtime-contract-ztp-current-version.md`

That document should be implementation-level, not another planning summary.

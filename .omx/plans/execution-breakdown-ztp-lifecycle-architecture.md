# Execution Breakdown: ZotPilot Lifecycle Architecture Refactor

Superseded for current-version execution by:
- [final-implementation-doc-ztp-current-version.md](/Users/zxd/ZotPilot/.omx/plans/final-implementation-doc-ztp-current-version.md)

## Scope

Current-version implementation scope only:

- `ztp-research`
- `ztp-setup`
- `ztp-review`
- `ztp-profile`
- root `zotpilot` compatibility shell

Deferred to next version:

- `ztp-guider`

Out of scope for this breakdown:

- multi-server split
- full MCP suite rewrite
- release of a generic orchestration framework

## Execution Order

1. Runtime contract
2. Capability matrix and default `research` pack closure
3. `ztp-research` workflow proof
4. Compatibility shell reduction
5. `ztp-setup`
6. `ztp-review` and `ztp-profile`
7. Service extraction and MCP repair hardening
8. Docs, migration notes, and validation

This order is intentional: workflow correctness first, surface cleanup second.

## Work Package 1: Workflow Runtime Contract

Goal:
- create the implementation source of truth for workflow state, checkpoints, failure states, policy enforcement, and resume semantics

Deliverables:
- runtime contract doc
- state schema
- checkpoint schema
- failure-state schema
- policy ownership map
- native workflow anchor design
- pre-flight delta-check rules

Likely touchpoints:
- new runtime contract doc under `.omx/plans/` or `docs/`
- [src/zotpilot/state.py](/Users/zxd/ZotPilot/src/zotpilot/state.py)
- new runtime/service module under `src/zotpilot/`

Must define:
- `workflow_id`
- stage enum
- checkpoint enum
- `partial-success`
- `restart-required`
- `resume-invalidated`
- per-item state for multi-paper flows
- ownership of policy enforcement
- ownership of checkpoint persistence
- ownership of delta checks against Zotero state

Exit criteria:
- no remaining ambiguity about where workflow state lives
- no remaining ambiguity about who blocks generic web drift
- no remaining ambiguity about how paused workflows detect Zotero-side drift

## Work Package 2: Capability Matrix And Pack Closure

Goal:
- make the default `ztp-research` path actually executable

Deliverables:
- workflow-by-capability matrix
- current-tool-to-pack mapping
- default `research` pack definition
- compatibility mapping for `core` / `extended` / `all`

Direct reuse tools:
- `search_academic_databases`
- `advanced_search`
- `get_paper_details`
- `ingest_papers`
- `get_ingest_status`

Promoted into default `research` pack:
- `index_library`
- `browse_library`
- `manage_tags`
- `manage_collections`
- `create_note`

Internal repair candidates:
- [src/zotpilot/tools/profiles.py](/Users/zxd/ZotPilot/src/zotpilot/tools/profiles.py)
- [src/zotpilot/tools/ingestion.py](/Users/zxd/ZotPilot/src/zotpilot/tools/ingestion.py)
- related ingestion helper modules

Exit criteria:
- `ztp-research` can complete discovery -> ingest -> verify -> index -> classify -> note -> tag without leaving the declared pack
- `core` is no longer treated as the primary product contract

## Work Package 3: `ztp-research` Proof Workflow

Goal:
- prove the canonical workflow end to end under runtime control

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

Implementation tasks:
- define the skill surface and trigger contract
- wire stage progression to runtime state
- enforce user checkpoints
- enforce capability policy
- implement partial-success handling
- implement resume/resume-invalidated behavior
- add native workflow anchor and delta check before downstream stages

Likely touchpoints:
- new `ztp-research` skill asset
- root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md)
- [src/zotpilot/tools/profiles.py](/Users/zxd/ZotPilot/src/zotpilot/tools/profiles.py)
- [src/zotpilot/tools/ingestion.py](/Users/zxd/ZotPilot/src/zotpilot/tools/ingestion.py)
- write-op tools and indexing tools

Exit criteria:
- explicit workflow invocation no longer drifts to generic web by default
- both required checkpoints are enforced
- approval after post-ingest continues automatically through downstream steps
- final report reflects per-paper success, failure, or partial-success

## Work Package 4: Compatibility Shell Reduction

Goal:
- keep old entry behavior while shrinking business logic in the root shell

Tasks:
- reduce root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) to routing + compatibility messaging
- map legacy surfaces:
  - `External Discovery` -> `ztp-research`
  - `Direct Ingest` -> `ztp-research` subflow
  - `Local Search` -> shared capability path
  - `Organize` -> absorbed into post-ingest / profile recommendations
  - `Profile` -> `ztp-profile`
- add explicit deprecation/sunset milestones

Exit criteria:
- root shell routes rather than re-implements workflows
- no orphaned legacy workflow section remains

## Work Package 5: `ztp-setup`

Goal:
- turn setup/config/register/first-index into a real lifecycle workflow

Stages:
- detect environment
- choose provider
- write config
- register MCP
- restart-required
- initial-index-ready

Implementation tasks:
- separate pre-MCP bootstrap from post-MCP readiness
- preserve CLI authority for machine actions
- persist restart boundary and resume semantics
- verify clean-machine path

Likely touchpoints:
- setup skill asset
- [references/setup-guide.md](/Users/zxd/ZotPilot/references/setup-guide.md)
- [src/zotpilot/cli.py](/Users/zxd/ZotPilot/src/zotpilot/cli.py)

Exit criteria:
- setup works from a clean machine state
- restart boundary is explicit and resumable

## Work Package 6: `ztp-review` And `ztp-profile`

Goal:
- extract the two secondary current-version skills after runtime proof exists

`ztp-review` focus:
- local-library-first synthesis workflow

`ztp-profile` focus:
- library profile + organization recommendations

Tasks:
- define entry triggers
- define stage models
- define allowed intelligence zones
- map existing profile/search/organization references into the new surfaces

Likely touchpoints:
- [references/profiling-guide.md](/Users/zxd/ZotPilot/references/profiling-guide.md)
- library/search/write MCP tools

Exit criteria:
- both skills use the shared runtime contract
- neither depends on umbrella-skill ambiguity

## Work Package 7: Service Extraction And MCP Repair Hardening

Goal:
- clean up the minimum internal boundaries needed for workflow enforcement

Service targets:
- workflow state service
- ingest orchestration service
- post-ingest pipeline service
- taxonomy/routing service
- profile generation service

Rules:
- do not rewrite stable tools unnecessarily
- move orchestration out of tool entrypoints where workflow correctness depends on it
- preserve single MCP server and stable external contracts where practical

Exit criteria:
- capability tools are thinner
- runtime/service owns workflow-sensitive orchestration

## Work Package 8: Docs, Migration, And Validation

Goal:
- align docs and tests with the implemented workflow model

Tasks:
- update README
- update [docs/architecture.md](/Users/zxd/ZotPilot/docs/architecture.md)
- update root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md)
- add migration notes for compatibility shell and profile aliases
- add/update tests from the approved test spec

Validation focus:
- `editable` / `uv` / `pip` update modes
- dirty-tree / symlink guards
- blocked generic-web drift
- disallowed capability calls
- partial-success
- `restart-required`
- `resume-invalidated`
- Zotero-side drift detection via workflow anchor

Exit criteria:
- docs and runtime naming agree
- compatibility story is explicit
- current-version workflows have contract and validation coverage

## File-Oriented Initial Pass

Suggested first files to touch in implementation order:

1. new runtime contract doc
2. [src/zotpilot/tools/profiles.py](/Users/zxd/ZotPilot/src/zotpilot/tools/profiles.py)
3. new workflow runtime/state service module
4. new `ztp-research` skill asset
5. [src/zotpilot/tools/ingestion.py](/Users/zxd/ZotPilot/src/zotpilot/tools/ingestion.py)
6. root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md)
7. new `ztp-setup` skill asset
8. profile/review skill assets
9. README and architecture docs

## Verification Gates

Gate A: contract ready
- runtime contract and capability matrix approved

Gate B: research proof ready
- canonical `ztp-research` workflow passes checkpoint, policy, and resume tests

Gate C: setup ready
- clean-machine and restart-required path validated

Gate D: current-version extraction ready
- `ztp-review` and `ztp-profile` run on the shared runtime contract

Gate E: migration ready
- compatibility shell reduced and sunset schedule documented

## Risks To Watch During Breakdown

- runtime contract stays vague and leaks back into tools
- compatibility shell re-accumulates business logic
- `research` pack still misses one downstream tool and silently breaks post-ingest closure
- Zotero-side edits during pause/resume are not detected
- setup gets modeled as pure MCP even before MCP is available

## Recommended Immediate Next Task

Start with:

1. Draft `workflow runtime contract`
2. Draft `current tool -> capability pack -> owner layer` matrix
3. Only after those are approved, begin code changes

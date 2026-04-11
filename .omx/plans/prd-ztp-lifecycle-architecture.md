# PRD: ZotPilot Lifecycle Architecture Refactor

## Metadata

- Source spec: [deep-interview-ztp-skill-mcp-architecture.md](/Users/zxd/ZotPilot/.omx/specs/deep-interview-ztp-skill-mcp-architecture.md)
- Context snapshot: [ztp-skill-mcp-architecture-20260401T155800Z.md](/Users/zxd/ZotPilot/.omx/context/ztp-skill-mcp-architecture-20260401T155800Z.md)
- Plan mode: `ralplan --consensus`
- Scope: architecture plan only, no code changes

## Problem Statement

ZotPilot already contains most of the desired lifecycle knowledge for setup, research, post-ingest handling, profiling, and note generation, but the product surface is still centered on one umbrella [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) plus profile-gated MCP tools. The result is architectural drift:

- workflow contracts live mostly in prose, not enforceable execution surfaces
- the default `core` tool profile cannot actually complete the full workflow the root skill promises
- agent behavior is too discretionary for explicit workflow invocations
- lifecycle concerns are fragmented across README, references, CLI, and tools

The target is a single-server architecture where workflow skills become first-class product entrypoints and the MCP layer becomes a stable capability substrate.

## RALPLAN-DR Summary

### Principles

1. Workflow first: explicit skill invocations must behave like bounded protocols, not open-ended chats.
2. Single server: preserve one MCP server and refactor boundaries inside it.
3. Lifecycle coherence: install, update, use, and development paths should share the same architecture model.
4. Bootstrap realism: pre-MCP lifecycle steps must remain executable even before skill or server surfaces exist.
5. Capability minimalism: MCP tools should expose stable primitives, not hide product orchestration ambiguity.
6. Incremental migration: preserve a compatibility shell while specialized workflow skills take over.

### Decision Drivers

1. Reliability of end-to-end workflow execution for explicit skill calls.
2. Alignment between promised workflow surfaces and actual default capability availability.
3. Brownfield migration cost across docs, CLI, skill surfaces, and existing users.

### Viable Options

#### Option A: Harden the current umbrella skill + tool profiles

Keep the root skill as the main surface, add stricter prompts, revise tool profile exposure, and patch workflow gaps.

Why this option is genuinely viable:
- existing root skill and references already encode most workflows
- current CLI/update/docs shape would need the least disruption

Pros:
- lowest short-term migration cost
- preserves current documentation shape
- minimal renaming

Cons:
- keeps too much product logic inside one skill surface
- hidden lifecycle branching remains
- future workflows will continue to accrete into the umbrella
- weaker boundary repair for development and testing

#### Option B: One MCP server + workflow skills + capability packs + compatibility shell

Introduce dedicated workflow skills in proof-first order: `ztp-research` first, then `ztp-setup`, `ztp-review`, `ztp-profile`, and optionally `ztp-guider`. Keep one server and reframe MCP tools as smaller capability packs backed by domain services. Retain the root skill as a router/compatibility shell during migration.

Why this option is genuinely viable:
- it aligns with the clarified requirement that explicit workflow calls must behave deterministically
- it fixes the current mismatch between workflow promise and default capability sufficiency

Pros:
- matches the user's desired product semantics
- makes checkpoints, continuation, and allowed discretion explicit
- supports full lifecycle organization cleanly
- lets capabilities be shaped per workflow without server split

Cons:
- requires skill/documentation migration work
- needs a workflow state contract
- may force capability-pack or profile redesign
- risks premature taxonomy churn if secondary skills are introduced before the runtime contract is proven

#### Option C: Multiple MCP servers or per-lifecycle servers

Split setup/research/review/profile across separate servers or plugins.

Pros:
- hardest isolation between responsibilities

Cons:
- directly violates the clarified non-goal
- increases registration/update complexity
- multiplies installation and debugging burden

### Recommendation

Choose **Option B**.

It is the only option that treats explicit workflows as first-class product contracts without violating the single-server constraint. It also lets ZotPilot solve the real problem, which is workflow reliability, not merely prompt verbosity or module tidiness.

Implementation shape: adopt Option B in a **runtime-first migration order**:

1. define workflow contract + capability sufficiency matrix
2. prove one canonical `ztp-research` path against that contract
3. then extract the rest of the specialized workflow skills

This keeps the architecture change grounded in execution reliability instead of surface-only renaming.

## Architect Review

### Steelman Antithesis

The strongest argument against Option B is that it may overfit the product to a handful of named workflows before the true execution substrate is repaired. If the real defect is missing workflow enforcement and capability sufficiency, then splitting surfaces too early multiplies skill files, docs, update burden, and compatibility responsibilities without first proving that the runtime contract works. A lighter runtime-first repair inside the umbrella skill could plausibly deliver most of the benefit with less migration cost.

### Real Tension

- Option A optimizes migration cost.
- Option B optimizes product correctness and long-term clarity.

Given the user's stated priority, the design should accept migration work in exchange for enforceable workflow behavior.

### Synthesis

Adopt Option B, but preserve:

- one compatibility shell at [SKILL.md](/Users/zxd/ZotPilot/SKILL.md)
- one MCP server entrypoint
- phased migration where existing tools remain callable while workflow skills are introduced
- runtime-first execution: contract and capability sufficiency land before broad skill extraction
- workflow-scoped capability packs as the new primary contract; do not simply broaden `core` and call that the redesign

## Critic Evaluation

Verdict: `APPROVE`

Why:

- alternatives are real and bounded
- recommendation aligns with clarified user intent and non-goals
- risks are explicit
- acceptance criteria are testable
- lifecycle implications are concrete enough to hand off to execution

## External Advisor Consensus

Artifacts:
- [claude-ztp-architecture-consensus-20260401T173107Z.md](/Users/zxd/ZotPilot/.omx/artifacts/claude-ztp-architecture-consensus-20260401T173107Z.md)
- [gemini-ztp-architecture-consensus-20260401T173107Z.md](/Users/zxd/ZotPilot/.omx/artifacts/gemini-ztp-architecture-consensus-20260401T173107Z.md)

Shared conclusion:
- approve with caveats
- deterministic workflows plus workflow-scoped packs are the right direction
- the highest implementation risk is now runtime ownership, checkpoint persistence, and state drift rather than the top-level architecture choice

Consensus adjustments adopted:
- write the workflow runtime contract before deep MCP refactors
- assign explicit ownership for policy enforcement, checkpoint persistence, and partial-success recovery
- add a Zotero-linked workflow anchor plus pre-flight delta checks before expensive downstream stages
- time-bound the compatibility shell so it does not become permanent routing debt

## Target Architecture

### Layer 1: Workflow Skills

Agent-facing product entrypoints:

- `ztp-research`
- `ztp-setup`
- `ztp-review`
- `ztp-profile`
- `ztp-guider` deferred by default until the `ztp-research` contract is proven; later either extracted as a dedicated deep-read workflow or folded into `ztp-review`
- root `zotpilot` skill remains as compatibility router

Current-version scope:

- current-version specialized skills: `ztp-research`, `ztp-setup`, `ztp-review`, `ztp-profile`
- next-version candidate: `ztp-guider`
- retained compatibility shell: root `zotpilot`

Responsibilities:

- intent classification only when entering through the compatibility shell
- workflow stage order
- user checkpoint policy
- allowed intelligence zones
- failure / handoff / resume semantics

### Layer 2: Workflow Runtime Contract

A lightweight workflow contract shared across skills. This is not a second server or generic orchestration platform. It is a ZotPilot-specific state model with:

- workflow id / stage / status
- required checkpoints
- allowed capabilities for the active stage
- continuation rules
- recoverable blocker states
- final summary payload
- persisted state location and resume semantics

Recommended persistence:

- active workflow state under a ZotPilot-owned runtime store in the user's ZotPilot config/data area
- resumable identifiers stable across checkpoint pauses
- final summaries written as user-visible artifacts for long workflows
- OMX state may mirror progress for Codex-native sessions, but it is not the source of truth

### Layer 3: MCP Capability Packs

Keep one server, but reorganize MCP tools conceptually into stable packs:

- `discovery`: external search, candidate scoring inputs, dedupe checks
- `ingest`: ingest enqueue, status, save-via-connector, verification helpers
- `library-read`: search, context, notes, annotations, profile inputs
- `library-write`: tags, collections, notes
- `index-admin`: index, index stats, reranking config, vision costs, library switch

This may still compile to the existing `core` / `extended` / `all` runtime surface initially, but the architecture should no longer assume those profiles are the product contract.

Every workflow stage must have a capability sufficiency contract:

- stage name
- allowed capability pack(s)
- minimum required tool set
- fallback / blocker behavior when a capability is unavailable
- whether generic web use is forbidden, optional, or required

Minimum viable `research` pack:

- required in first implementation wave: external discovery, dedupe/verification via `advanced_search`, paper details, ingest, ingest status, indexing, collection browse, collection routing, tag write, note write
- optional after proof: table/figure search, annotations, citation expansion, richer profile-aware scoring
- non-default capability rule: if a stage needs a capability outside its declared pack, the workflow must surface that dependency explicitly and pause or downgrade visibly rather than silently improvising
- rejected as primary path: broadening `core` until it happens to be research-sufficient. `core` / `extended` / `all` remain compatibility aliases, not the long-term product contract.

## Legacy Surface Mapping

| Existing umbrella workflow/content | Planned destination |
| --- | --- |
| `External Discovery` in [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) | `ztp-research` primary workflow |
| `Direct Ingest` | `ztp-research` fast-path / subflow rather than standalone skill |
| `Local Search` | shared capability layer used mainly by `ztp-review`, `ztp-profile`, and `ztp-research` verification |
| `Organize` | absorbed into `ztp-research` post-ingest and `ztp-profile` organization recommendations |
| `Profile` | `ztp-profile` |
| setup guidance from [references/setup-guide.md](/Users/zxd/ZotPilot/references/setup-guide.md) | `ztp-setup` |
| update guidance from [references/setup-guide.md](/Users/zxd/ZotPilot/references/setup-guide.md) and CLI docs | lifecycle `update` contract, not standalone user skill |
| deep note / guided read flows from [references/note-analysis-prompt.md](/Users/zxd/ZotPilot/references/note-analysis-prompt.md) | next-version `ztp-guider` or future `ztp-review` mode |
| root intent router and legacy entry behavior | root compatibility shell |

## MCP Adaptation And Repair Plan

The current MCP layer is not being replaced wholesale. It is being adapted in place with targeted repair.

### Bucket 1: Reuse directly

These tools already fit the capability contract for the first `ztp-research` proof:

- `search_academic_databases`
- `advanced_search`
- `get_paper_details`
- `ingest_papers`
- `get_ingest_status`

### Bucket 2: Promote into the default `research` path

These tools exist today but are not available in the default `core` path that the current umbrella skill implicitly promises:

- `index_library`
- `browse_library`
- `manage_tags`
- `manage_collections`
- `create_note`

These become part of the workflow-scoped `research` pack in the new architecture.

### Bucket 3: Repair internally

These areas need architectural repair even if their external contract mostly survives:

- [profiles.py](/Users/zxd/ZotPilot/src/zotpilot/tools/profiles.py): keep `core` / `extended` / `all` as compatibility aliases, but move the product contract to workflow-scoped packs
- [ingestion.py](/Users/zxd/ZotPilot/src/zotpilot/tools/ingestion.py) and related ingest helpers: move workflow-sensitive orchestration into services/runtime so tools become thinner capability adapters
- workflow runtime support: add state, checkpoint, partial-success, restart-required, resume-invalidated, and capability-policy enforcement as first-class runtime concerns

### Repair boundary

- do not rewrite the full MCP suite
- do repair exposure contracts, tool boundaries, and runtime support where the current workflow cannot close end to end
- do preserve one server entrypoint and stable tool signatures where practical

### Layer 4: Domain Services

Internal Python services under the MCP boundary:

- setup/install service
- workflow state service
- research orchestration service
- post-ingest pipeline service
- library profiling service
- note generation service
- capability policy / availability service

Goal: move lifecycle orchestration out of tool entrypoints like [ingestion.py](/Users/zxd/ZotPilot/src/zotpilot/tools/ingestion.py) and out of prose-only references.

## Artifact Map

| Concern | Planned home |
| --- | --- |
| Specialized skill entrypoints (`ztp-*`) | skill files / workflow-facing docs layer |
| Root compatibility router | root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) |
| Workflow-state enforcement | dedicated workflow runtime/state service under ZotPilot runtime storage |
| Capability-policy enforcement | MCP capability-policy layer plus workflow-by-capability matrix |
| Domain orchestration | internal services under `src/zotpilot/` |

## Workflow State Model

### `ztp-setup`

Stages:
- detect environment
- choose provider
- write config
- register MCP
- restart-required
- initial-index-ready

Intelligence zones:
- provider recommendation
- troubleshooting fallback

Deterministic zones:
- environment checks
- config writing
- registration steps

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
- candidate scoring / ranking explanation
- collection suggestion
- note synthesis
- tag selection from existing vocabulary

Deterministic zones:
- use ZotPilot discovery first
- no generic web detour by default
- mandatory checkpoints after candidate list and after ingest verification
- approved downstream steps auto-run unless blocked

### `ztp-guider`

Stages:
- locate target paper/html
- fetch local context
- retrieve targeted sections
- synthesize guided read
- optional deep note writeback

Intelligence zones:
- key idea extraction
- relation to user profile
- reading guide synthesis

Deterministic zones:
- target selection
- retrieval and verification
- writeback only when requested

### `ztp-review`

Stages:
- clarify review topic
- local library scope
- topic clustering
- passage extraction
- citation expansion if needed
- outline
- synthesis
- user refinement checkpoint
- final review

Intelligence zones:
- thematic clustering
- synthesis
- gap analysis

Deterministic zones:
- prefer local indexed library first
- explicit citation expansion policy
- reproducible outline/finalization steps

### `ztp-profile`

Stages:
- scan library
- infer themes
- user dialogue checkpoint
- write/update profile artifact
- optional organization recommendations

Intelligence zones:
- profile hypothesis
- anomaly detection
- taxonomy suggestion

Deterministic zones:
- profile artifact lifecycle
- explicit user confirmation before broad write operations

## Persistence Contract

- Workflow runtime state persists in a dedicated ZotPilot workflow store under the user's ZotPilot config/data directory.
- OMX state may mirror workflow progress for Codex-native sessions, but it is not the cross-client source of truth.
- Every run gets a stable `workflow_id`; multi-paper workflows also persist per-item progress and failure state.
- Required persisted fields:
  - current stage
  - status
  - active checkpoint
  - allowed capability pack
  - completed outputs
  - partial failures
  - blocker reason
  - next resumable action
- Restart survivability:
  - `restart-required` and user-checkpoint states survive process exit and client restart
  - resumed runs must rebind to in-flight ingest/index work using durable identifiers such as `batch_id` and `item_key`
- Multi-client resume/handoff:
  - CLI-led setup/update can create and advance workflow state before MCP is available
  - later MCP/skill sessions must be able to discover resumable state and continue from the last checkpoint
- Resume invalidation:
  - if external state changes make safe continuation impossible, mark `resume-invalidated` and force a visible user decision
- Native workflow anchor:
  - every active workflow should maintain a Zotero-linked anchor such as a hidden workflow tag, tracking note, or equivalent durable marker
  - each expensive downstream stage should run a pre-flight delta check against current Zotero state before proceeding

## Failure-State Matrix

| Lifecycle area | Failure states | Recovery path |
| --- | --- | --- |
| Setup / config | `zotero-missing`, `provider-missing-key`, `register-failed`, `restart-not-done` | stop with actionable blocker, persist state, resume from last successful stage after fix |
| Update | `pypi-unreachable`, `installer-unknown`, `dirty-skill-tree`, `binary-locked`, `post-restart-mismatch` | downgrade to manual path or retry after restart; do not claim success before post-restart verification |
| Day-to-day research use | `discovery-empty`, `user-rejected`, `ingest-partial`, `ingest-failed`, `verify-mismatch`, `index-partial`, `write-partial`, `resume-invalidated` | preserve completed subset, retry only failed/partial subset, emit explicit partial-success or blocked report |
| Development / release | `verification-failed`, `version-unsynced`, `tag-failed`, `push-failed`, `release-ci-failed` | stop before next irreversible action, persist evidence, require explicit resume after remediation |

## Lifecycle Design

### Installation / Configuration

- `ztp-setup` becomes the dedicated setup surface.
- CLI remains authoritative for machine actions: `setup`, `register`, `doctor`, `status`.
- Skill should orchestrate CLI and MCP readiness as one workflow, rather than leaving setup split across README and references.
- Restart gating remains explicit.

Bootstrap boundary:

- before MCP registration or restart, `ztp-setup` is a CLI-led workflow with skill guidance
- after MCP becomes available, the same workflow can continue through readiness checks and initial indexing
- do not pretend setup is a pure MCP workflow from a clean machine state

### Update

- `zotpilot update` remains the mechanism for CLI + skill update.
- Architecture must treat skill files as versioned workflow surfaces, not just markdown sidecars.
- Compatibility shell should advertise deprecation/migration when new workflow skills land.

Update contract must explicitly model three install modes already present in CLI behavior:

- editable install
- `uv tool` install
- `pip` install

It must also preserve current safety guards for skill-dir dirty trees, symlinks, and repo identity checks.

### Everyday Use

- Users invoke named workflows directly when they want guarantees.
- Compatibility shell can still route vague requests, but should preferentially hand off to a specialized workflow skill.
- The default capability surface must be sufficient for the default workflow promise, or the workflow skill must declare the required surface explicitly.

### Development / Release

- Developers work against workflow contracts first, then capability contracts, then service internals.
- Planning, tests, and docs should be organized per workflow surface.
- Release notes must call out workflow-surface changes, capability-surface changes, and compatibility impacts separately.

Release architecture must also account for current repo realities:

- `pyproject.toml` remains the version source of truth for Python package and monorepo release coordination
- connector artifacts remain a bounded subsystem with separate build constraints
- branch/release policy (`dev` -> `main` PR flow, version sync, changelog, tag) must be preserved during the refactor

## Migration Strategy

### Phase 0: Compatibility Preservation

- Keep the root `zotpilot` skill.
- Reclassify it as a router/compatibility shell.
- Preserve current tool names initially.

### Phase 1: Workflow Skill Extraction

- Extract `ztp-research` first as the proof workflow.
- Extract `ztp-setup` next because install/config/register/first-index is a distinct user journey.
- Defer `ztp-review` and `ztp-profile` until the workflow runtime contract is proven on `ztp-research`.
- Keep `ztp-guider` deferred until a later product decision confirms it should stand alone rather than live under `ztp-review`.
- Before deep MCP refactors, write the workflow runtime contract as a dedicated implementation artifact covering:
  - state schema
  - checkpoint schema
  - policy-enforcement ownership
  - partial-success semantics
  - native workflow anchor / delta-check rules
- Each skill gets:
  - explicit trigger conditions
  - stage model
  - checkpoint rules
  - allowed capabilities
  - failure / resume behavior

### Phase 2: Capability Surface Repair

- Map existing tools to capability packs.
- Ensure default workflow paths have the tools they actually need.
- Adopt workflow-scoped capability packs as the primary contract.
- Keep `core` / `extended` / `all` as compatibility aliases during migration rather than broadening `core` into the new default product contract.

### Phase 3: Domain Service Extraction

- Pull post-ingest orchestration, workflow verification, and lifecycle rules out of tool modules and prose references into reusable services.

### Phase 4: Deprecation and Documentation Cleanup

- Reduce umbrella skill contents.
- Replace prose-only workflows with workflow skill references.
- Align README, architecture docs, and release notes with the new lifecycle model.
- Publish explicit compatibility milestones for:
  - root shell scope
  - `core` / `extended` / `all` reinterpretation
  - deprecated aliases and eventual removals
- Add an explicit sunset target for the compatibility shell/router so it stays bounded instead of accumulating permanent logic.

## Acceptance Criteria

### Product

- Explicit workflow invocations no longer drift to generic web research unless the workflow explicitly allows it.
- `ztp-research` can complete the intended research flow end to end with defined checkpoints.
- Setup/update flows have one canonical workflow surface each.
- The compatibility shell routes rather than re-implements the whole product.
- Setup is viable from a clean machine even before MCP tools are available.

### Architecture

- One MCP server remains.
- Workflow, capability, and service layers are distinct in docs and code structure.
- Default promised workflows are supported by actual available capabilities.
- Lifecycle docs map one-to-one to workflow surfaces.
- Every workflow stage has an explicit capability sufficiency definition and blocker policy.
- Workflow persistence and resume semantics are specified.

### Migration

- Existing users can still enter through the root skill during transition.
- Legacy tool profiles remain supported during migration, even if internally reinterpreted.
- Workflow surfaces have explicit deprecation and compatibility notes.
- Root shell scope reduction has named milestones instead of open-ended coexistence.

## Phased Implementation Plan

### Phase 1: Planning and contracts

Deliverables:
- workflow contract spec
- capability-pack map
- workflow-stage-to-capability matrix
- compatibility policy
- migration doc
- bootstrap boundary spec
- release/version compatibility note

Exit criteria:
- each workflow has stage definitions, checkpoints, and allowed intelligence zones
- capability sufficiency gaps are enumerated
- clean-machine setup path is modeled separately from post-registration MCP path

### Phase 2: Runtime proof and first workflow

Deliverables:
- workflow state handling skeleton
- capability policy enforcement hooks
- one canonical `ztp-research` path proven against the contract

Exit criteria:
- `ztp-research` has executable checkpoints and continuation semantics
- default workflow/capability mismatch is resolved for the canonical research flow

### Phase 3: Skill surface extraction

Deliverables:
- new specialized skills
- reduced root skill router
- updated README architecture section

Exit criteria:
- each lifecycle path has a canonical workflow entrypoint

### Phase 4: Runtime and service refactor

Deliverables:
- workflow state handling
- service extraction from orchestration-heavy modules
- profile/capability alignment changes

Exit criteria:
- workflow checkpoints are represented in code/runtime, not just prose

### Phase 5: Validation and migration hardening

Deliverables:
- regression tests
- end-to-end workflow tests
- compatibility docs
- release checklist updates

Exit criteria:
- legacy and new paths both verified

## Pre-mortem

### Scenario 1: Skill split happens, but capability mismatch remains

Risk:
- new skill names exist, but they still rely on unavailable default tools

Mitigation:
- add a capability sufficiency matrix per workflow before implementation

### Scenario 2: Workflow runtime becomes too generic and heavyweight

Risk:
- ZotPilot accidentally builds its own orchestration framework

Mitigation:
- keep runtime contract small and workflow-specific
- reject abstractions that do not directly serve named workflows

### Scenario 3: Compatibility shell never shrinks

Risk:
- old and new surfaces coexist indefinitely, reintroducing ambiguity

Mitigation:
- define explicit deprecation milestones and shell responsibilities up front

## ADR

### Decision

Refactor ZotPilot into specialized workflow skills backed by one MCP server, a lightweight workflow runtime contract, stable capability packs, and internal domain services. Retain the root skill only as a compatibility router during migration.

### Drivers

- workflow reliability
- single-server constraint
- lifecycle clarity
- brownfield migration safety

### Alternatives Considered

- Harden the umbrella skill only
- Split into multiple MCP servers

### Why Chosen

It best matches the user's clarified intent: deterministic workflow surfaces with selective intelligence, without adding multi-server complexity.

### Consequences

- more up-front design work
- skill/documentation migration required
- better long-term product clarity and testability

### Follow-ups

- design workflow state contract
- decide profile-to-capability migration
- design compatibility shell behavior
- convert lifecycle docs into workflow-owned docs

## Available Agent Types Roster

- `planner`: contract shaping, phase planning
- `architect`: boundaries, lifecycle design, migration strategy
- `critic`: plan quality, risk, acceptance criteria, verification rigor
- `executor`: implementation of skill/runtime/capability refactor
- `test-engineer`: workflow regression design and e2e validation
- `writer`: README / docs / migration-note alignment
- `qa-tester`: interactive workflow validation
- `git-master`: release sequencing and commit hygiene for multi-phase rollout

## Staffing Guidance

### If executing via `ralph`

- Lane 1: `executor` with high reasoning for workflow/runtime refactor
- Lane 2: `test-engineer` medium reasoning for contract and e2e tests
- Lane 3: `writer` medium reasoning for docs and migration notes
- Verification owner: `verifier` or `critic`-style pass at each milestone

### If executing via `$team`

- Lead: `architect` or `planner`
- Worker 1: `executor` for workflow skill extraction
- Worker 2: `executor` or `build-fixer` for capability/profile refactor
- Worker 3: `test-engineer` for contract/e2e tests
- Worker 4: `writer` for lifecycle docs and migration notes

Suggested reasoning levels by lane:
- architecture / workflow runtime: high
- capability mapping: medium-high
- docs / migration: medium
- regression/e2e verification: medium-high

Launch hints:

```text
$team /Users/zxd/ZotPilot/.omx/plans/prd-ztp-lifecycle-architecture.md
```

or

```text
omx team run /Users/zxd/ZotPilot/.omx/plans/prd-ztp-lifecycle-architecture.md
```

## Team Verification Path

1. Verify setup workflow on a fresh config path.
2. Verify update workflow for uv / pip / editable installs.
3. Verify `ztp-research` on one canonical "latest research in X" case.
4. Verify post-ingest continuation through index, classification, note, and tag steps.
5. Verify compatibility shell still routes old entry behavior correctly.
6. Verify developer lifecycle docs match the implemented surfaces.

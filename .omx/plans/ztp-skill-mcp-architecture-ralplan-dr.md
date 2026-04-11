# RALPLAN-DR Draft: ZotPilot Skill + MCP Workflow Refactor

**Requirements source:** [/Users/zxd/ZotPilot/.omx/specs/deep-interview-ztp-skill-mcp-architecture.md](/Users/zxd/ZotPilot/.omx/specs/deep-interview-ztp-skill-mcp-architecture.md)
**Plan type:** Architecture refactor plan only
**Code changes:** None in this draft

## Principles

1. Keep **one MCP server** and move product orchestration out of ad hoc tool flows.
2. Make **workflow skills deterministic by default**; use agent judgment only at explicitly designated decision nodes.
3. Treat **workflow checkpoints as enforced gates**, not advisory prompt text.
4. Separate **workflow surface**, **MCP capability surface**, and **internal domain/service logic** so each layer has one job.
5. Preserve compatibility where practical: existing umbrella skill, current tool contracts, and current profiles should degrade cleanly during migration.

## Decision Drivers

1. The current umbrella [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) encodes multiple workflows, which increases branchiness and agent drift.
2. The default `core` profile exposes only 8 tools, while the promised post-ingest path needs capabilities such as indexing, note creation, collection routing, and tagging.
3. Current checkpoints in [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) and [references/post-ingest-guide.md](/Users/zxd/ZotPilot/references/post-ingest-guide.md) are documented, but not enforced by runtime architecture.
4. Ingestion-facing modules already mix capability and orchestration concerns, especially around the current tool surface documented in [docs/architecture.md](/Users/zxd/ZotPilot/docs/architecture.md).
5. The target must cover the full lifecycle: setup/config, update, day-to-day use, and development/release.

## Options

### Option A: Keep umbrella skill, tighten prose and tool docs

- Improve `SKILL.md`, references, and prompts without changing architecture boundaries.
- Keep current tool profiles and advisory checkpoint style.

**Pros**
- Lowest migration cost.
- Minimal compatibility risk.

**Cons**
- Does not solve workflow enforcement.
- Leaves post-ingest coverage mismatch in the default runtime surface.
- Keeps workflow reliability dependent on agent compliance.

### Option B: Single server with explicit workflow skills over capability packs

- Replace the umbrella-first experience with dedicated workflow skills where routing materially helps:
  prove `ztp-research` first, then extract `ztp-setup`, `ztp-review`, `ztp-profile`, and optionally `ztp-guider`.
- Keep one MCP server.
- Recast MCP tools as stable domain capabilities.
- Add a workflow runtime contract with enforced stages, allowed-tool sets, and mandatory checkpoints.
- Keep root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) as a compatibility router.

**Pros**
- Directly addresses determinism, checkpoint enforcement, and lifecycle coverage.
- Keeps the single-server constraint intact.
- Preserves reuse of existing docs and tool contracts while clarifying boundaries.

**Cons**
- Requires profile redesign and migration work.
- Needs an explicit workflow-state contract before surface extraction scales.
- Risks premature taxonomy churn if secondary skills are introduced before `ztp-research` is proven.

### Option C: Push workflow orchestration down into MCP tools

- Keep one skill surface, but create larger orchestration-heavy tools that run end-to-end flows internally.
- Use the MCP server as both capability and workflow layer.

**Pros**
- Could enforce sequencing inside tools.
- Fewer skill entrypoints to manage.

**Cons**
- Blurs product workflow and capability boundaries further.
- Makes tools less stable and harder to compose or test.
- Increases coupling between user interaction checkpoints and MCP contracts.

## Recommendation

Adopt **Option B**.

It is the smallest architectural change that solves the real failure mode: declared workflows exist, but execution is not a first-class contract. Option B preserves the single-server architecture, makes workflow reliability enforceable, and aligns the product around bounded entrypoints instead of one broad umbrella skill. The concrete synthesis is a proof-first `B1` rollout:

- make `ztp-research` the first-class explicit workflow skill first
- keep `ztp-setup` as a user-facing lifecycle workflow because install/config/register/first-index is a real user journey
- defer `ztp-guider` until the `ztp-research` runtime contract is proven; do not let an unresolved taxonomy block the core reliability refactor
- keep `update` and `development/release` as explicit lifecycle contracts backed by CLI/docs rather than forcing them into standalone skills

## ADR

**Decision**
- Refactor ZotPilot into a **workflow-skill layer** on top of a **single capability-oriented MCP server**, backed by a clearer **domain/service layer**.
- Treat lifecycle contracts as first-class architecture: `setup/config`, `update`, `day-to-day use`, and `development/release` each need explicit state, pause/resume boundaries, and completion proof.

**Drivers**
- Deterministic workflow execution is more important than maximum agent freedom.
- The default runtime surface must actually support the promised workflow path.
- Brownfield compatibility matters for tools, docs, and user habits.

**Alternatives considered**
- Option A: rejected because it preserves advisory-only workflow control.
- Option C: rejected because it deepens tool-level orchestration coupling and weakens capability stability.
- Broaden `core` until it becomes research-sufficient: rejected as the primary contract because it keeps generic profile tiers as the product surface. The chosen direction is workflow-scoped packs first, with `core` / `extended` / `all` retained only as compatibility aliases during migration.

**Why chosen**
- Best fit for the explicit constraints.
- Highest leverage on workflow reliability without requiring multiple servers or new dependencies.

**Consequences**
- The product surface becomes more explicit and less improvisational.
- Tool profile strategy must shift from generic breadth tiers to workflow-executable capability packs.
- Some existing docs and skill entrypoints will become compatibility shims during migration.
- Lifecycle restart boundaries and release operations must be modeled directly instead of living only in README prose.

**Follow-ups**
- Define workflow state model and gate semantics.
- Define capability pack exposure for each workflow.
- Define compatibility and deprecation schedule for umbrella skill and current profiles.
- Define lifecycle-state matrix and runtime-availability proof before implementation.

## External Advisor Consensus

External reviews captured in:
- [claude-ztp-architecture-consensus-20260401T173107Z.md](/Users/zxd/ZotPilot/.omx/artifacts/claude-ztp-architecture-consensus-20260401T173107Z.md)
- [gemini-ztp-architecture-consensus-20260401T173107Z.md](/Users/zxd/ZotPilot/.omx/artifacts/gemini-ztp-architecture-consensus-20260401T173107Z.md)

Consensus points:
- The architectural direction is correct: deterministic workflows, workflow-scoped packs, and a ZotPilot-owned runtime store are the right foundation.
- The next implementation document should be the workflow runtime contract, before deep repair of `profiles.py` or `ingestion.py`.
- The current "internal repair" bucket must assign explicit ownership for:
  - policy enforcement
  - checkpoint persistence
  - partial-success and mid-batch failure handling
- Runtime state must be anchored back to native Zotero state to detect drift across pauses, manual edits, and resume events.
- The root compatibility shell needs an explicit sunset/deprecation schedule so it does not become permanent debt.

Consensus-driven additions to the execution plan:
- Write a first-class workflow runtime contract before service extraction.
- Add a native workflow anchor or equivalent Zotero-linked tracking mechanism plus pre-flight delta checks before expensive downstream stages.
- Add explicit ownership decisions for policy enforcement and failure recovery in the first implementation phase.

## Target Architecture

### 1. Workflow Skills Layer

Primary entrypoints:
- `ztp-research` as the first-class explicit workflow skill
- `ztp-setup` as the installation / configuration / registration / first-index workflow
- `ztp-review`, `ztp-profile` as secondary explicit skills, introduced after the runtime contract is proven on `ztp-research`
- `ztp-guider` deferred by default; either extracted later as a dedicated deep-read workflow or folded into `ztp-review` after proof data exists

Current-version delivery scope:
- new workflow skills in the current version: `ztp-research`, `ztp-setup`, `ztp-review`, `ztp-profile`
- next-version candidate: `ztp-guider`
- compatibility surface retained in the current version: root `zotpilot` skill as router/shell

Responsibilities:
- Own stage sequence.
- Own enforced user checkpoints.
- Restrict allowed tool usage per stage.
- Specify where intelligence is allowed.
- Own resume / continue / handoff semantics.

Default intelligence nodes:
- candidate scoring and ranking
- profile interpretation
- note synthesis
- collection selection when multiple plausible homes exist
- tag selection from existing vocabulary

Default deterministic nodes:
- setup checks
- config validation
- profile/tool exposure resolution
- ingest polling
- ingest verification
- post-ingest confirmation gate
- index scheduling
- post-ingest step execution order
- release checklist validation

Compatibility:
- Root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) remains as an umbrella compatibility shell that routes to the new workflow skills.

## Legacy Skill Decomposition

| Current umbrella content | Target destination |
| --- | --- |
| `External Discovery` | `ztp-research` primary workflow |
| `Direct Ingest` | `ztp-research` fast-path / subflow, not a standalone skill |
| `Local Search` | shared capability used mainly by `ztp-review`, `ztp-profile`, and `ztp-research` verification |
| `Organize` | absorbed into `ztp-research` post-ingest and `ztp-profile` organization recommendations |
| `Profile` | `ztp-profile` |
| setup/update guidance from references | `ztp-setup` plus lifecycle contracts for `update` |
| deep-note / guided read prompt flows | deferred to `ztp-guider` next version or folded into `ztp-review` later |
| root intent router | stays in root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) as compatibility shell |

### 2. MCP Capability Layer

Keep one server, but organize the exposed surface by stable capability groups:
- discovery
- library search / context
- ingest / ingest status
- indexing
- notes
- taxonomy and organization
- profile and diagnostics
- admin/config

Refactor goal:
- MCP tools should expose reusable primitives, not own user-facing workflow branching where avoidable.

Profile direction:
- Keep `core` / `extended` / `all` as backward-compatible aliases during migration.
- Introduce canonical **workflow-executable capability packs** as the new architecture contract.
- Make the default skill-driven surface equivalent to the `research` pack so the advertised `ztp-research` path is executable by default.
- Keep `extended` and `all` for diagnostics, power use, and compatibility, but treat them as legacy breadth tiers rather than the primary product contract.

Initial pack decision:

| Pack | Required capabilities |
| --- | --- |
| `research` | discovery, `advanced_search`, paper details, ingest, ingest status, indexing, collection browse, tag/manage, note creation, collection routing |
| `setup` | diagnostics, config validation, register/setup helpers, index readiness checks |
| `profile` | library browse, profile generation, topic search, notes/annotations when available |

Rule:
- Every workflow must ship with an explicit workflow-by-capability matrix proving that its expected runtime surface is sufficient to complete the advertised path.
- Non-default capabilities must be escalated explicitly: if a stage needs a capability outside its pack, the workflow must either declare that dependency up front, pause with a blocker, or route through the compatibility shell with a visible downgrade notice.

Minimum viable `research` pack:
- required from day 1: external discovery, dedupe/verification via `advanced_search`, ingest, ingest status, indexing, collection browse, collection routing, tag write, note write, paper details
- optional later: table/figure search, annotations, citation expansion, full-profile inference
- forbidden by default: generic web discovery when ZotPilot discovery is available for the stage

## MCP Adaptation And Repair Strategy

Current MCP surface should be treated in three buckets:

1. Reuse directly
   - `search_academic_databases`
   - `advanced_search`
   - `get_paper_details`
   - `ingest_papers`
   - `get_ingest_status`

2. Promote into the default `research` capability pack
   - `index_library`
   - `browse_library`
   - `manage_tags`
   - `manage_collections`
   - `create_note`

3. Repair internally while preserving a stable external contract where practical
   - [ingestion.py](/Users/zxd/ZotPilot/src/zotpilot/tools/ingestion.py) and related ingest helpers should be thinned so workflow orchestration moves into services/runtime instead of staying in tool entrypoints
   - profile/tool exposure logic in [profiles.py](/Users/zxd/ZotPilot/src/zotpilot/tools/profiles.py) should be reinterpreted so workflow-scoped packs become the primary contract and `core` / `extended` / `all` remain compatibility aliases
   - runtime support must exist for workflow state, partial success, restart-required, resume-invalidated, and policy enforcement, even if that state is not exposed as broad user-facing tools

MCP repair scope for the current version:
- do not rewrite the whole tool suite
- do make the default `ztp-research` path executable end to end
- do extract workflow-sensitive orchestration out of tool modules into services/runtime where needed
- do preserve the single-server entrypoint and existing tool signatures unless a contract gap forces an adapter layer

### 3. Domain / Service Layer

Extract reusable service boundaries under the MCP layer:
- workflow state + checkpoint service
- ingest orchestration service
- post-ingest pipeline service
- taxonomy / routing service
- profile generation service
- lifecycle setup/update/release service helpers

Rule:
- Service layer can contain reusable orchestration and validation logic.
- Workflow policy stays in workflow skills.
- MCP contract remains capability-oriented.

## Lifecycle Contract Matrix

| Lifecycle area | Primary entrypoint | Actor | State transitions | Pause / resume boundary | Completion proof |
| --- | --- | --- | --- | --- | --- |
| Setup / config | `ztp-setup` plus `zotpilot setup` / `register` | user + agent | `unconfigured -> configured -> registered -> restart-required -> post-restart-index-pending -> ready` | hard pause at `restart-required`; resume after client restart | successful `doctor` / config validation + index readiness proof |
| Update | `zotpilot update` with skill compatibility guidance | user + agent | `version-checked -> upgraded -> restart-required -> post-restart-verified` | hard pause at `restart-required`; resume after client restart | new version active + post-restart MCP/skill verification |
| Day-to-day research use | `ztp-research`, `ztp-guider`, `ztp-review`, `ztp-profile` | agent with user checkpoints | `discover -> score -> user-review -> ingest -> verify -> post-ingest-approved -> index -> classify -> note -> tags -> final-report` | user-review and post-ingest-approved are explicit gates; otherwise auto-continue | final report with per-paper status and no silent drop-off |
| Development / release | planning + implementation workflow, then release contract | maintainer + agent | `plan-approved -> implementation-ready -> verified -> version-synced -> tag-created -> pushed -> release-verified` | pause at approval gates and before irreversible release operations | tests/lint/typecheck pass, version sync holds, tag pushed, CI release path green |

Lifecycle rules:
- Restart boundaries are architectural, not incidental.
- A workflow cannot claim completion without its lifecycle-specific completion proof.
- `development/release` remains an explicit contract, not a user-facing skill, unless a later plan proves a separate skill adds value.

## Failure-State Matrix

| Lifecycle area | Failure states | Recovery path |
| --- | --- | --- |
| Setup / config | `zotero-missing`, `provider-missing-key`, `register-failed`, `restart-not-done` | stop with actionable blocker, persist state, resume from last successful stage after fix |
| Update | `pypi-unreachable`, `installer-unknown`, `dirty-skill-tree`, `binary-locked`, `post-restart-mismatch` | downgrade to manual path or retry after restart; never claim updated until post-restart verification passes |
| Day-to-day research use | `discovery-empty`, `user-rejected`, `ingest-partial`, `ingest-failed`, `verify-mismatch`, `index-partial`, `write-partial`, `resume-invalidated` | pause with explicit per-paper state, retry only failed/partial subset, preserve completed subset, emit final partial-success report |
| Development / release | `verification-failed`, `version-unsynced`, `tag-failed`, `push-failed`, `release-ci-failed` | stop before next irreversible action, keep state and evidence, require explicit resume after remediation |

## Persistence Contract

- Workflow state lives in a ZotPilot-owned runtime store under the user's ZotPilot config/data directory, not in OMX-specific state.
- OMX state may mirror progress for Codex-native workflows, but it is not the source of truth for multi-client resume/handoff.
- Each run gets a stable `workflow_id` and per-item state payload when the workflow operates on multiple papers.
- Persisted fields: current stage, checkpoint status, allowed capability pack, completed outputs, partial failures, blocker reason, and next resumable action.
- Restart survivability:
  - `restart-required` states survive process exit and client restart.
  - resumed runs must rebind to in-flight ingest/index work via durable identifiers such as `batch_id`, `item_key`, or equivalent persisted linkage.
- Resume invalidation:
  - if required external state has changed and safe continuation is impossible, mark `resume-invalidated` and force a visible user decision instead of silently restarting.
- Multi-client semantics:
  - CLI-led setup/update may create or advance workflow state before MCP is available.
  - a later MCP/skill session must be able to discover resumable state, present the last checkpoint, and continue without assuming an OMX-only runtime.

## Artifact Map

| Concern | Planned home |
| --- | --- |
| Specialized skill entrypoints (`ztp-*`) | skill files / workflow-facing docs layer |
| Root compatibility router | root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) |
| Workflow-state enforcement | dedicated workflow runtime/state service under ZotPilot runtime storage |
| Capability-policy enforcement | MCP capability-policy layer plus workflow-by-capability matrix |
| Domain orchestration | internal services under `src/zotpilot/` |

## Phased Plan

### Phase 0: Architecture contract and inventory

- Inventory current workflow promises across [SKILL.md](/Users/zxd/ZotPilot/SKILL.md), [references/setup-guide.md](/Users/zxd/ZotPilot/references/setup-guide.md), [references/post-ingest-guide.md](/Users/zxd/ZotPilot/references/post-ingest-guide.md), [references/profiling-guide.md](/Users/zxd/ZotPilot/references/profiling-guide.md), and [references/note-analysis-prompt.md](/Users/zxd/ZotPilot/references/note-analysis-prompt.md).
- Map current tools and profiles to each promised lifecycle flow.
- Identify exact gaps between advertised flow and executable runtime surface.

**Acceptance criteria**
- Every promised workflow step is mapped to a current tool, doc, or missing capability.
- The post-ingest gap in the default surface is explicitly documented.

### Phase 1: Workflow contract design

- Define the stage machine for each workflow skill.
- Define mandatory checkpoints, auto-run continuation rules, and resume semantics.
- Define designated intelligence nodes and prohibited drift behavior.

**Acceptance criteria**
- Each workflow has a concrete stage list, gate list, and completion definition.
- `ztp-research` explicitly covers discovery → scoring → review → ingest → verify → post-ingest confirmation → index → classify → note → tags → final report.

### Phase 2: Capability-surface redesign

- Redesign tool exposure around workflow-executable packs while preserving one server.
- Introduce canonical packs (`research`, `setup`, `profile`) while keeping `core` / `extended` / `all` as compatibility aliases during migration.
- Define compatibility treatment for deprecated or alias surfaces.

**Acceptance criteria**
- The runtime surface for each workflow is sufficient to complete it end to end.
- The default skill-driven runtime surface is proven sufficient for `ztp-research`.
- A documented compatibility story exists for current `core` / `extended` / `all` users.
- The chosen default-surface migration is explicit: workflow-scoped packs are the primary contract; `core` is not broadened into the new product contract.

### Phase 3: Service-boundary extraction plan

- Define which logic remains in workflow skills, which moves into services, and which stays as thin MCP tools.
- Prioritize ingestion and post-ingest services first, since that is the highest-value failure path.

**Acceptance criteria**
- Each major module has a target boundary and owner layer.
- No target design requires multiple MCP servers or new dependencies.

### Phase 4: Lifecycle coverage plan

- Define how setup/config, update, day-to-day research, and development/release map into the new architecture.
- Include doc updates, migration notes, restart-boundary semantics, and release checklist changes needed to keep behavior aligned with architecture.
- Expand development/release into an explicit operational contract covering version sync, connector coupling, tag/push/release automation, and deprecation milestones.

**Acceptance criteria**
- All four lifecycle areas are covered with a named workflow or explicit non-workflow contract.
- Development/release docs reflect the new skill and capability model.
- Setup/update restart boundaries are modeled and testable.
- Update acceptance is explicit for `editable`, `uv`, and `pip` install modes, including dirty-tree, symlink, and post-restart verification behavior.
- Development/release acceptance is explicit for version sync, tag/push gating, and release verification boundaries.

### Phase 5: Migration and rollout

- Sequence compatibility router changes, new workflow skill introduction, profile/capability migration, and documentation cutover.
- Define deprecation windows and observable milestones.

**Acceptance criteria**
- A user on the umbrella skill still reaches the correct workflow path.
- The team can measure whether workflow drift and post-ingest drop-off have been reduced.

## Pre-Mortem

1. **Failure:** New workflow skills still behave like prompt prose, not enforced runtime contracts.
   **Mitigation:** Make stage/gate state explicit and testable; do not rely on prompt wording alone.

2. **Failure:** Default tool exposure still cannot execute the full post-ingest chain.
   **Mitigation:** Define workflow-executable capability packs before migration.

3. **Failure:** Too much intelligence leaks into deterministic stages and reintroduces drift.
   **Mitigation:** Mark intelligence nodes positively and treat all other stages as constrained.

4. **Failure:** Compatibility shims become permanent and preserve old ambiguity.
   **Mitigation:** Add a time-bounded migration and deprecation plan with explicit cutover criteria.

5. **Failure:** Service extraction becomes a broad cleanup effort instead of a reliability refactor.
   **Mitigation:** Extract only boundaries needed for workflow enforcement and capability clarity.

6. **Failure:** Setup/update and development/release remain doc-only side paths outside the architecture.
   **Mitigation:** Treat lifecycle flows as first-class architecture surfaces in the same plan.

7. **Failure:** Compatibility aliases (`core` / `extended` / `all`) outlive their migration window and keep the old ambiguity in place.
   **Mitigation:** define a sunset policy, compatibility telemetry, and a named cutover milestone before implementation starts.

## Verification Plan

### Architecture verification

- Review each workflow skill spec against the requirements source and current docs.
- Confirm every lifecycle area has a defined entrypoint, state model, and completion semantics.
- Confirm only one MCP server remains in the target design.
- Confirm the lifecycle matrix covers restart-required states and irreversible release boundaries.

### Workflow verification

- Tabletop-run `ztp-research` from prompt to final report and verify all gates are explicit.
- Tabletop-run `ztp-setup`, `ztp-profile`, and `ztp-review` to ensure they do not depend on umbrella-skill ambiguity.
- Verify post-ingest continuation is mandatory once the user approves continuation.
- Verify the ordered downstream contract stays `post-ingest confirmation -> index -> classify -> note -> tags`.
- Negative-control proof: verify generic-web discovery is blocked by default when the `research` pack is sufficient.
- Negative-control proof: verify disallowed capability calls fail as policy violations rather than silently degrading.

### Surface verification

- Build a matrix: workflow skill × required capability × exposed runtime surface.
- Verify the default supported path exposes all required capabilities for the advertised workflow.
- Verify canonical packs and compatibility aliases map cleanly, without leaving `ztp-research` under-provisioned by default.

### Compatibility verification

- Verify the umbrella root skill routes cleanly into specialized workflows.
- Verify existing tool users retain a documented migration path.
- Verify docs, references, and release notes tell one consistent story.
- Verify development/release guidance still matches repo rules for version sync, tagging, push, and connector coupling.
- Verify `restart-required`, `resume-invalidated`, and per-paper partial-success behavior all emit visible, resumable outcomes.

## Open Questions

- After `ztp-research` proof, should `ztp-guider` stand alone or fold into `ztp-review`? This is intentionally deferred and must not block the first migration wave.

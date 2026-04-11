# Deep Interview Spec: ZotPilot Skill + MCP Workflow Refactor

## Metadata

- Slug: `ztp-skill-mcp-architecture`
- Profile: `standard`
- Rounds: `5`
- Final ambiguity: `0.08`
- Threshold: `0.20`
- Context type: `brownfield`
- Transcript: [ztp-skill-mcp-architecture-20260401T161301Z.md](/Users/zxd/ZotPilot/.omx/interviews/ztp-skill-mcp-architecture-20260401T161301Z.md)
- Context snapshot: [ztp-skill-mcp-architecture-20260401T155800Z.md](/Users/zxd/ZotPilot/.omx/context/ztp-skill-mcp-architecture-20260401T155800Z.md)

## Clarity Breakdown

| Dimension | Score |
| --- | ---: |
| Intent clarity | 0.94 |
| Outcome clarity | 0.91 |
| Scope clarity | 0.87 |
| Constraint clarity | 0.86 |
| Success criteria clarity | 0.84 |
| Brownfield context clarity | 0.89 |

## Intent

Make ZotPilot reliable as a workflow-driven product. When a user invokes a specific skill, the agent should complete the intended research workflow accurately instead of improvising across unrelated tools or leaving the job half-finished.

## Desired Outcome

ZotPilot should behave as a set of explicit workflow skills on top of one MCP server. A workflow invocation such as `ztp-research` should drive a stable, checkpointed, end-to-end process with limited and intentional use of agent discretion.

## In Scope

- Redesign ZotPilot around multiple workflow-focused skills rather than one umbrella skill.
- Keep one MCP server, but shrink and clarify its role into stable capabilities instead of mixed product/workflow entrypoints.
- Separate:
  - workflow surface
  - MCP capability surface
  - internal domain/service logic
- Make workflow checkpoints explicit and enforceable, especially for external discovery and post-ingest continuation.
- Ensure the "research latest work in X" path is closed-loop:
  - external discovery
  - candidate scoring
  - user review
  - ingest
  - post-ingest confirmation
  - index
  - classify
  - note
  - tags
- Constrain agent behavior so explicit workflow invocations do not drift into generic web research or unrelated agent behavior.

## Out of Scope / Non-goals

- Do not split ZotPilot into multiple MCP servers.
- Do not optimize first for code aesthetics alone; the priority is workflow execution reliability.
- Do not treat this as a generic orchestration platform problem unless that is required later by the approved plan.

## Decision Boundaries

- Workflow skills should be deterministic by default.
- Agent intelligence should be introduced only at designated steps where judgment materially improves outcomes.
- When a workflow skill is explicitly invoked, the agent should not freely reroute to generic web research.
- Mandatory user checkpoints are acceptable and desirable where the workflow requires approval.
- After user approval to continue, downstream steps should auto-run to completion unless a real blocker occurs.

## Constraints

- Single MCP server architecture must remain.
- Brownfield repository with existing docs, users, tool contracts, and compatibility concerns.
- Current product already exposes a default `core` tool profile and broader `extended` / `all` profiles.
- Existing root skill and docs encode valuable workflow knowledge that should be preserved or refactored, not discarded blindly.
- No new dependencies without explicit request.

## Testable Acceptance Criteria

- When a user invokes `ztp-research` for "latest research in X", the agent follows the prescribed workflow rather than using generic web fetch by default.
- The workflow pauses at the intended user review checkpoints and not at arbitrary internal points.
- Once the user approves ingest and post-ingest continuation, the agent proceeds through indexing, classification, note generation, and tagging without silently stopping.
- The tools required by a workflow are actually available to that workflow's expected runtime surface.
- Workflow state and continuation behavior are explicit enough that exit, resume, and user handoff behavior are predictable.
- The current umbrella [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) can either remain as a compatibility shell or route cleanly into the new specialized workflow skills.

## Proposed Skill Surfaces

- `ztp-setup`
  - install, configure, register, first index, readiness checks
- `ztp-research`
  - external discovery, scoring, user review, ingest, post-ingest continuation
- `ztp-guider`
  - deep paper/html guidance and note-oriented reading workflow
- `ztp-review`
  - topic review based on indexed local library
- `ztp-profile`
  - library overview, personal research profile, classification advice

These are aligned with the user's proposal and fit the observed current repository responsibilities.

## Architectural Direction

Recommended target shape:

1. Workflow skills
   - Product entrypoints with strict, stage-based contracts
   - Own user checkpoints, continuation rules, and allowed tool set
2. MCP capabilities
   - Smaller, stable primitives grouped by domain capability rather than by one giant umbrella workflow
   - Should not contain product-level orchestration logic when avoidable
3. Domain/service layer
   - Internal orchestration, validation, and reusable business logic under the MCP boundary
   - Removes workflow branching from tool entrypoints such as ingestion-heavy modules

## Brownfield Evidence vs Inference

### Evidence

- The root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) already includes:
  - External Discovery
  - Direct Ingest
  - Organize
  - Profile
- [references/post-ingest-guide.md](/Users/zxd/ZotPilot/references/post-ingest-guide.md) already defines the desired gated post-ingest sequence.
- [references/setup-guide.md](/Users/zxd/ZotPilot/references/setup-guide.md) already contains `ztp-setup`-like behavior.
- [references/profiling-guide.md](/Users/zxd/ZotPilot/references/profiling-guide.md) already contains `ztp-profile`-like behavior.
- [references/note-analysis-prompt.md](/Users/zxd/ZotPilot/references/note-analysis-prompt.md) already contains `ztp-guider`-like note/deep-read behavior.
- [docs/architecture.md](/Users/zxd/ZotPilot/docs/architecture.md) documents the current single-server, profile-gated architecture.
- The default tool surface documented in [docs/architecture.md](/Users/zxd/ZotPilot/docs/architecture.md) does not fully cover the post-ingest steps promised by the root skill.

### Inference

- The current failure is not lack of workflow design, but lack of executable workflow enforcement.
- Splitting the umbrella skill into explicit workflow skills is likely to improve reliability more than adding more tool prose.
- Tool profiles may need redesign or workflow-scoped availability so the promised path is actually runnable.

## Assumptions Exposed and Resolutions

- Assumption: the main issue is code mess alone.
  - Resolution: false; the dominant issue is workflow unreliability and agent drift.
- Assumption: a broad generic skill can safely encode many workflows.
  - Resolution: likely false; the umbrella shape increases branchiness, hidden dependencies, and agent discretion.
- Assumption: more intelligence is always better.
  - Resolution: false; intelligence should appear only at high-value decision nodes, otherwise deterministic flow should win.

## Pressure-pass Findings

- Reframed from "architecture is messy" to "workflow is not a first-class contract."
- The strongest failure pattern is not a missing feature but the mismatch between declared workflow and executable behavior.

## Technical Context Findings

- [src/zotpilot/server.py](/Users/zxd/ZotPilot/src/zotpilot/server.py) remains a thin single-server entrypoint.
- [src/zotpilot/tools/__init__.py](/Users/zxd/ZotPilot/src/zotpilot/tools/__init__.py) imports all tool modules by side effect.
- [src/zotpilot/tools/profiles.py](/Users/zxd/ZotPilot/src/zotpilot/tools/profiles.py) gates visibility by `core` / `extended` / `all`.
- [src/zotpilot/tools/ingestion.py](/Users/zxd/ZotPilot/src/zotpilot/tools/ingestion.py) still mixes low-level capability code with workflow-sensitive orchestration concerns.

## Residual Risks

- Backward compatibility policy for existing tool names and the umbrella skill shell is not fully specified.
- The exact mapping from current tool profiles to workflow-specific capability packs is not yet designed.
- The degree of internal service extraction needed from existing tool modules remains a planning task, not a clarified requirement.

## Recommended Handoff

Recommended next step: `$ralplan`

Use this spec as the requirements source of truth for a planning pass that should produce:

- target architecture boundaries
- workflow state model
- migration strategy from umbrella skill to workflow skills
- capability-surface redesign
- compatibility plan for existing users and docs

Suggested invocation:

```text
$plan --consensus --direct /Users/zxd/ZotPilot/.omx/specs/deep-interview-ztp-skill-mcp-architecture.md
```

Other valid handoffs:

- `$autopilot` if you want direct planning + execution
- `$ralph` if you want persistent sequential execution pressure
- `$team` if you want coordinated parallel design / implementation lanes

# Deep Interview Transcript Summary

- Slug: `ztp-skill-mcp-architecture`
- Timestamp (UTC): `20260401T161301Z`
- Profile: `standard`
- Context type: `brownfield`
- Final ambiguity: `0.08`
- Threshold: `0.20`

## Context Snapshot

- Snapshot: [ztp-skill-mcp-architecture-20260401T155800Z.md](/Users/zxd/ZotPilot/.omx/context/ztp-skill-mcp-architecture-20260401T155800Z.md)

## Condensed Transcript

### Round 1

- Target: outcome / scope
- Q: If this redesign could solve only one core problem, what should ZotPilot become?
- A: The agent currently cannot follow user needs through the intended workflow; the goal is for an explicitly invoked skill workflow to complete tasks efficiently and accurately.

### Round 2

- Target: scope / success
- Q: Give one canonical failing example.
- A: For "research the latest work in X", the expected flow is external discovery -> filtering -> user review -> ingest -> user confirmation -> index -> classify -> note -> tags. Current agents may use generic web fetch, ingest unreliably, fail to continue, and break exit / user handoff behavior.

### Round 3

- Target: brownfield grounding
- Q: Review the current project skill first.
- A: Reviewed the root skill and referenced guides. The desired workflow already exists in prose, but it is packed into one umbrella skill. Post-ingest depends on tools outside the default core surface, and workflow checkpoints are advisory rather than enforceable.

### Round 4

- Target: decision boundaries
- Q: Should workflow skills enter a strong-constraint mode?
- A: Yes. Introduce intelligence only where needed; otherwise follow the process.

### Round 5

- Target: non-goals
- Q: What should the redesign explicitly avoid?
- A: Do not split ZotPilot into multiple MCP servers. Split skill/workflow surfaces and internal capability layers only.

## Pressure Pass Findings

- Early hypothesis challenged: the main issue might be "messy architecture" in the abstract.
- Revised conclusion after pressure: the real failure is that workflow is not treated as a first-class product contract. Skill guidance exists, but it is not strong enough to prevent agents from bypassing the intended path.

## Brownfield Findings

- Evidence-backed findings:
  - The root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) already defines external discovery, direct ingest, organize, and profile workflows.
  - [references/post-ingest-guide.md](/Users/zxd/ZotPilot/references/post-ingest-guide.md) defines the exact post-ingest sequence the user wants.
  - [docs/architecture.md](/Users/zxd/ZotPilot/docs/architecture.md) claims a `SKILL -> MCP Tools -> references` architecture.
  - The default `core` tool surface does not include several tools required by the promised end-to-end research workflow.
- Inference:
  - The redesign should focus on making workflows executable and enforceable, not merely better documented.

Task statement

ZotPilot has improved after recent refactors, but the architecture still feels too mixed and hard to reason about. The user is considering a redesign inspired by oh-my-claudecode: split the product into multiple skill-facing workflows backed by a cleaner MCP capability layer.

Desired outcome

Clarify whether ZotPilot should evolve toward a skill + MCP layered architecture, what the target product surface should be, and which responsibilities belong to skill entrypoints versus MCP tools versus lower-level domain modules.

Stated solution

Candidate skill surfaces proposed by the user:
- `ztp-setup`: installation guide + configuration
- `ztp-research`: external database discovery by topic, ingest, index, classify, tag, note workflow
- `ztp-guider`: deep HTML/paper reading guidance
- `ztp-review`: topic review based on indexed local library
- `ztp-profile`: generate/update library overview and personal profile

Probable intent hypothesis

The user does not only want cleaner code. They likely want a clearer product architecture where agent-facing workflows are explicit, composable, and easier to maintain than the current mixed "tool modules + one broad SKILL.md + some workflow logic inside tool entrypoints" shape.

Known facts / evidence

- Local architecture doc already claims a three-layer model: `SKILL.md -> MCP Tools -> references/`.
- Current runtime still centers on one MCP server entrypoint (`src/zotpilot/server.py`) importing all tools by side effect.
- Tool exposure is profile-based (`core` / `extended` / `all`) rather than capability-pack or workflow-pack based.
- Current root [SKILL.md](/Users/zxd/ZotPilot/SKILL.md) is a broad intent router containing multiple workflows: external discovery, local search, ingest, organize, profile.
- `tools/ingestion.py` still carries orchestration responsibilities beyond a thin capability boundary.
- Local docs explicitly say architecture remains centered on tool modules, with skill-first exposure layered on top rather than decomposed into multiple dedicated skills.
- External reference [oh-my-claudecode docs](https://yeachan-heo.github.io/oh-my-claudecode-website/docs.html) emphasize separation between skills/modes, MCP tools, state/memory, and agent roles.

Constraints

- Brownfield repo with existing users, docs, CLI, MCP contracts, and backward-compatibility concerns.
- No new dependencies should be introduced without explicit request.
- Existing behavior and current tool contracts likely need migration or compatibility strategy.
- The user asked for a deep interview, so this turn should clarify requirements, not implement the redesign directly.

Unknowns / open questions

- Is the goal primarily developer-facing maintainability, user-facing product clarity, or both?
- Should the redesign preserve one monolithic MCP server with cleaner internal domains, or split capability registration/output by workflow?
- Are the proposed `ztp-*` skills intended as separate published entrypoints, or internal documentation/workflow packs on top of one shared core?
- Which current surfaces are acceptable to deprecate or rename?
- What degree of backward compatibility is required for existing `zotpilot` users, tool names, and SKILL.md behavior?
- Does the user want a full product/interaction redesign or mainly internal architecture cleanup with the same user-facing behavior?

Decision-boundary unknowns

- May OMX/Codex decide the exact skill/tool boundaries autonomously, or only propose them?
- Can MCP tool names/signatures change, or must they remain stable behind adapters?
- Can the current single `SKILL.md` be replaced by multiple skills, or must it remain as a compatibility umbrella?

Likely codebase touchpoints

- `SKILL.md`
- `README.md`
- `docs/architecture.md`
- `src/zotpilot/server.py`
- `src/zotpilot/state.py`
- `src/zotpilot/tools/__init__.py`
- `src/zotpilot/tools/profiles.py`
- `src/zotpilot/tools/ingestion.py`
- `src/zotpilot/tools/library.py`
- `src/zotpilot/tools/write_ops.py`

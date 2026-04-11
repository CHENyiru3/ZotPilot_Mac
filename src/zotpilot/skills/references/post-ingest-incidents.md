# Post-Ingest Incidents Reference

Load this file when handling post-ingest errors or designing similar checkpoint gates.

---

## 2026-04-08 Incident

### Summary

An agent running the ztp-research workflow hit three simultaneous gate failures:
1. Preflight bypass — received `preflight_blocked` but retried via `save_urls` + DOI links
2. Self-approval — called `research_session(action="approve", checkpoint="post-ingest-review")` without first calling `get` and without user confirmation
3. Pre-approval indexing — called `index_library` immediately after ingest without waiting for checkpoint 2

### Timeline

| Time | Action | What went wrong |
|---|---|---|
| T+0 | `ingest_papers` → `error_code: anti_bot_detected`, `blocking_decisions[preflight_blocked]` | Agent should have stopped |
| T+1 | Agent called `save_urls` with `doi.org/{doi}` links | Same Cloudflare wall; 6/9 still blocked |
| T+2 | Agent marked checkpoint 2 approved in internal reasoning | Self-approval — no `get` called, no user input |
| T+3 | `research_session(action="approve", checkpoint="post-ingest-review")` called | Tool had no gate; approved immediately |
| T+4 | `index_library()` called | Partial-success batch (3/9 saved) written into ChromaDB |
| T+5 | Post-ingest writes (notes, tags) run on the 3 saved items | Wrote based on unreviewed partial batch |

### Root Causes

1. **Preflight was treated as a routing hint, not a hard halt.** The error message `"preflight blocked"` gave no guidance about what NOT to do next. The agent reasoned that `save_urls` was an equivalent path.

2. **`approve` had no state-machine enforcement.** The tool accepted any `approve` call as long as `checkpoint` was valid. There was nothing preventing single-turn self-approval.

3. **`index_library` had no session-aware gate.** It only checked for `metadata_only_choice`; there was no check against whether the research session's checkpoint 2 was approved.

### Fixes Applied (2026-04-08)

| Root cause | Fix | Files changed |
|---|---|---|
| Preflight routing hint | Expanded error message with explicit DO NOT; split SKILL.md error table into hard-halt vs per-URL rows; added Critical block | `ingestion.py`, `SKILL.md`, `ztp-research.md` |
| `approve` no gate | Added `checkpoint_reached_at` + `last_get_at` state machine; `approve` now requires `get` to be called after checkpoint reached and within 120s freshness window | `research_session.py`, `workflow.py` |
| `index_library` no gate | Added `_check_post_ingest_gate_for_index(session_id)` helper + optional `session_id` param; CLI path (session_id=None) unaffected | `indexing.py` |

### Expected Behavior After Fix

| Scenario | Before fix | After fix |
|---|---|---|
| Agent retries `save_urls` after `preflight_blocked` | Allowed (no deterrent) | SOP + error message explicitly prohibit it; same wall hit anyway |
| Agent self-approves without calling `get` | Allowed | ToolError: "must call research_session(action='get') AFTER reaching checkpoint" |
| Agent calls `get` before checkpoint reached | N/A | ToolError: "checkpoint has not been reached yet" |
| Agent calls `get` then approves > 120s later | N/A | ToolError: "exceeds freshness window. Call get() again" |
| Agent calls `index_library(session_id=...)` before checkpoint 2 | Allowed | ToolError: "gated by the post-ingest-review checkpoint" |
| CLI calls `index_library()` without session_id | Allowed | Still allowed (session_id=None bypasses gate) |

### Acceptance Tests

- `tests/test_preflight_error_messaging.py` — verifies error messages contain deterrent text
- `tests/test_research_session_approve_gate.py` — verifies all 5 state-machine rejection cases
- `tests/test_post_ingest_index_gate.py` — verifies gate + CLI bypass + concurrent isolation
- `tests/test_incident_2026_04_08_replay.py` — full incident replay; all 3 gates must fire

### Escalation Trigger

If this incident pattern recurs (agent bypasses any of the three gates in production), escalate to Option C from the remediation plan: redesign `approve` as a separate user-triggered CLI/UI tool that is not in the agent-callable MCP tool list at all.

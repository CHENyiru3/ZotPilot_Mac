# Original user task

Use Claude as an external advisor to review the current ZotPilot architecture plan and help form consensus on the skill split, MCP adaptation strategy, and proof-first rollout.

# Final prompt sent to Claude CLI

```text
You are reviewing an architecture plan for ZotPilot, a Zotero MCP server + skill project. Give a concise verdict on whether the plan is coherent and what should change. Answer in English with 4 sections only: 1) Verdict (approve / approve with caveats / not yet), 2) What is strongest about the plan, 3) Biggest risk or flaw, 4) One concrete adjustment you would make now.

Context summary:
- Keep exactly one MCP server; no multi-server split.
- New product architecture: workflow skills + workflow runtime contract + workflow-scoped capability packs + internal domain services.
- Root zotpilot SKILL remains only as a compatibility shell/router.
- Proof-first rollout: first prove ztp-research, then ztp-setup, then ztp-review and ztp-profile. ztp-guider is explicitly deferred to the next version.
- Current-version specialized skills: ztp-research, ztp-setup, ztp-review, ztp-profile.
- Research workflow must be deterministic by default: clarify query -> external discovery -> score candidates -> user review checkpoint -> ingest -> ingest verification -> post-ingest checkpoint -> index -> classify -> note -> tag -> final report.
- Intelligence is only allowed at selected nodes like candidate scoring, collection suggestion, note synthesis, and tag selection; generic web drift should be blocked by default.
- Legacy umbrella workflow mapping:
  - External Discovery -> ztp-research
  - Direct Ingest -> ztp-research subflow
  - Local Search -> shared capability for ztp-review / ztp-profile / ztp-research verification
  - Organize -> absorbed into ztp-research post-ingest and ztp-profile recommendations
  - Profile -> ztp-profile
- MCP adaptation strategy:
  - Reuse directly: search_academic_databases, advanced_search, get_paper_details, ingest_papers, get_ingest_status
  - Promote into default research pack: index_library, browse_library, manage_tags, manage_collections, create_note
  - Internal repair: profiles.py exposure contract, ingestion.py orchestration boundaries, workflow runtime state/policy enforcement
- Workflow-scoped packs become the primary contract. core / extended / all remain compatibility aliases only.
- Workflow state should live in a ZotPilot-owned runtime store under the user's ZotPilot config/data directory; OMX may mirror but is not the cross-client source of truth.
- Lifecycle contract must cover setup/config, update, day-to-day use, and development/release, including failure states like partial-success, restart-required, and resume-invalidated.

Please be direct and critical.
```

# Claude output (raw)

```text
## 1) Verdict
**Approve with caveats** — The architecture is coherent and strategically sound, but has one critical ambiguity and two execution risks that need resolution before implementation begins.

---

## 2) What is Strongest

- **Deterministic workflow by default** — Explicit checkpoints (user review before ingest, verification before indexing) prevent silent failures and give users control over what enters their library. This directly addresses the "false success when bridge lies" bug from recent history.

- **Workflow-scoped packs as primary contract** — Shifting from `core/extended/all` to workflow-specific capability packs (`ztp-research` pack, `ztp-setup` pack) is the right abstraction. It aligns MCP tool exposure with actual user tasks and makes deprecation boundaries clean.

- ** ZotPilot-owned runtime store** — Keeping workflow state in ZotPilot's config directory (not relying on OMX as source of truth) is correct. This prevents cross-client coupling and gives ZotPilot full control over resume/rollback semantics.

---

## 3) Biggest Risk

**The "internal repair" bucket is underspecified and will become a integration sink.** Three modules (`profiles.py`, `ingestion.py`, workflow runtime) all need boundary changes, but the plan doesn't name:
- Which module owns **policy enforcement** (e.g., blocking generic web drift)?
- Where **checkpoint state** is persisted during a multi-step workflow (e.g., after user review, before ingest)?
- What happens if `ingestion.py` succeeds but `profiles.py` tagging fails mid-batch?

Without explicit ownership, these will become cross-cutting concerns that leak into every tool module — exactly the pattern that caused the "zombie functions" and "doc_id convergence" bugs in the v0.4.1 remediation.

**Secondary risk:** The "compatibility shell" router at root `SKILL.md` will accumulate conditional logic for every deprecated alias. Without a sunset deadline (v0.6.0 is mentioned but not enforced), the router becomes technical debt.

---

## 4) One Concrete Adjustment

**Write the workflow runtime contract first** — before touching `profiles.py` or `ingestion.py`. A single document (200-300 lines) that defines:

```markdown
# Workflow Runtime Contract (draft)

## State Schema
- checkpoint_id: str (enum: pre_ingest, post_ingest, indexed, tagged)
- batch_id: str (UUID for multi-paper operations)
- policy: { allow_web_drift: bool, require_user_review: bool }
- resume_token: str (opaque, invalid on config change)

## Policy Enforcement Points
- ingestion.ingest_papers(): check allow_web_drift before connector fallback
- profiles.apply_tags(): validate against user's existing tag vocabulary
- All tools: read-only if resume_token invalid

## Failure Semantics
- partial-success: batch_id returned, checkpoint persisted, user prompted
- restart-required: explicit state flag, resume_token invalidated
```

This forces the hard decisions about ownership and state management upfront, and becomes the reference for all three "internal repair" modules. Without it, you're refactoring into ambiguity.
```

# Concise summary

Claude agrees with the overall direction. The strongest endorsement is for deterministic workflows, workflow-scoped packs, and ZotPilot-owned runtime state. The main warning is that the current "internal repair" bucket is still too vague, especially around policy enforcement, checkpoint persistence, and mid-batch failure ownership.

# Action items / next steps

- Write the workflow runtime contract before changing `profiles.py` or `ingestion.py`.
- Assign clear ownership for policy enforcement, checkpoint persistence, and partial-success recovery.
- Add a sunset/deprecation deadline for the compatibility shell so it does not become permanent debt.

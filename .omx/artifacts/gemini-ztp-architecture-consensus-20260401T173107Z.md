# Original user task

Use Gemini as an external advisor to review the current ZotPilot architecture plan and help form consensus on the skill split, MCP adaptation strategy, and proof-first rollout.

# Final prompt sent to Gemini CLI

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

# Gemini output (raw)

```text
### 1) Verdict
**Approve with caveats.** The architectural shift from "naked tools" to "lifecycle-managed workflows" is essential for a reliable RAG system, but the state synchronization model requires stricter guardrails.

### 2) What is strongest about the plan
The **Stateful Workflow Runtime** and the **Workflow-Scoped Capability Packs**. By forcing the LLM to operate within a deterministic pipeline (e.g., `clarify` -> `discover` -> `score` -> `checkpoint`), you eliminate the "black box" failure modes and tool-selection fatigue common in agentic RAG. Defining "packs" as the primary contract (instead of a flat list of 20+ tools) significantly improves prompt stability and intent alignment.

### 3) Biggest risk or flaw
**Dual-Source-of-Truth Drift.** Storing workflow state in a ZotPilot-owned runtime store while the primary data lives in Zotero's SQLite/Cloud creates a critical consistency gap. If a user manually deletes, moves, or retags items in the Zotero GUI while a `ztp-research` workflow is at the "Post-Ingest Checkpoint," the ZotPilot state becomes a "phantom" that will cause subsequent indexing or note-synthesis steps to fail or hallucinate.

### 4) One concrete adjustment you would make now
Implement a **"Native Workflow Anchor"**: For any active workflow, ZotPilot must write a hidden `_ztp_workflow_id` tag or a synced "Workflow Tracking Note" directly into the Zotero collection. This ensures that the ZotPilot runtime can perform a **Pre-Flight Delta Check** at every node, verifying that the library state hasn't drifted before proceeding with expensive operations like indexing or synthesis.
```

# Concise summary

Gemini also agrees with the overall direction. Its strongest emphasis is on the workflow runtime and capability-pack contract. The main risk it sees is drift between ZotPilot's runtime state and the actual Zotero library state when users modify the library outside the workflow.

# Action items / next steps

- Add a native workflow anchor between runtime state and the Zotero library.
- Define pre-flight delta checks before expensive downstream stages like indexing and note synthesis.
- Explicitly handle external library drift during paused workflows and resume paths.

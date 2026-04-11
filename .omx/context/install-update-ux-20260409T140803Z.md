Task statement:
Design an aligned plan for ZotPilot installation and update UX so users get close to one-click update/maintenance, with better developer ergonomics and less mismatch between code, deployed skills, MCP registration, and client runtime state.

Desired outcome:
- A concrete consensus plan for making ZotPilot update/maintenance feel one-step for users.
- Clear explanation of the current gaps versus OMC/OMX.
- A phased implementation path that is low-risk and preserves current functionality.

Known facts / evidence:
- ZotPilot currently has separate concerns for CLI/package update, skill deployment, MCP registration, and client restart.
- Recent fixes added content-hash-based skill deployment and made `register` actually deploy split skills.
- `status` now reports detected clients, registered clients, and skill directories.
- Historically, the system could report "up-to-date" when the version was unchanged but skill contents had drifted.
- OMC/OMX feel like one-click updates because they treat runtime assets as a single system and re-run setup/update as an idempotent reconcile step.

Constraints:
- Preserve support for both packaged installs and editable/source installs.
- Do not break existing cross-platform client registration flows.
- Keep update flows honest about the need to restart clients.
- Favor a simple user mental model over exposing internal deployment layers.

Unknowns / open questions:
- Whether `zotpilot update` should automatically re-register all detected clients by default.
- How to preserve previously injected MCP config env vars/credentials during automatic re-registration.
- Whether a new top-level command like `sync` or `refresh` is better than overloading `update`.

Likely codebase touchpoints:
- `src/zotpilot/cli.py`
- `src/zotpilot/_platforms.py`
- `scripts/platforms.py`
- `README.md`
- `docs/supported-clients.md`
- `tests/test_cli_update.py`
- `tests/test_cli_config.py`

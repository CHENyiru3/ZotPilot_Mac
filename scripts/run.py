#!/usr/bin/env python3
"""ZotPilot skill bootstrap — ensures zotpilot CLI is installed, then delegates.

Usage by AI agent (via SKILL.md):
    python scripts/run.py status --json
    python scripts/run.py setup --non-interactive --provider local
    python scripts/run.py index --limit 10
"""
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent  # repo root


def _ensure_uv() -> str:
    """Return path to uv, or exit with helpful message."""
    uv = shutil.which("uv")
    if uv:
        return uv
    print(
        "ERROR: uv is not installed.\n"
        "Install it: curl -LsSf https://astral.sh/uv/install.sh | sh",
        file=sys.stderr,
    )
    sys.exit(1)


def _ensure_zotpilot(uv: str) -> None:
    """Install or upgrade zotpilot CLI if needed."""
    if shutil.which("zotpilot"):
        return
    print("ZotPilot CLI not found. Installing...", file=sys.stderr)
    result = subprocess.run(
        [uv, "tool", "install", "--force", "--reinstall", str(SKILL_DIR)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Installation failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("ZotPilot CLI installed successfully.", file=sys.stderr)


def main():
    uv = _ensure_uv()
    _ensure_zotpilot(uv)

    args = sys.argv[1:]
    # Always use uv tool run for reliability — handles PATH issues
    # after fresh install where the current shell may not see the new binary.
    sys.exit(subprocess.run([uv, "tool", "run", "zotpilot"] + args).returncode)


if __name__ == "__main__":
    main()

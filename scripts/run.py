#!/usr/bin/env python3
"""ZotPilot skill bootstrap — ensures zotpilot CLI is installed, then delegates.

Usage by AI agent (via SKILL.md):
    python scripts/run.py status --json
    python scripts/run.py setup --non-interactive --provider local
    python scripts/run.py index --limit 10
    python scripts/run.py register [--platform <name>] [--gemini-key <k>] ...
"""
import argparse
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


def _handle_register(argv: list[str]) -> int:
    """Handle the 'register' subcommand for cross-platform MCP registration."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "platforms", Path(__file__).resolve().parent / "platforms.py"
    )
    platforms_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(platforms_mod)
    register = platforms_mod.register
    PLATFORMS = platforms_mod.PLATFORMS

    parser = argparse.ArgumentParser(
        prog="run.py register",
        description="Register ZotPilot MCP server on AI agent platforms.",
    )
    parser.add_argument(
        "--platform", action="append", dest="platforms",
        choices=list(PLATFORMS.keys()),
        help="Platform to register on (repeatable). Auto-detects if omitted.",
    )
    parser.add_argument("--gemini-key", help="Gemini API key for embeddings")
    parser.add_argument("--dashscope-key", help="DashScope API key for embeddings")
    parser.add_argument("--zotero-api-key", help="Zotero Web API key (for write ops)")
    parser.add_argument("--zotero-user-id", help="Zotero numeric user ID (for write ops)")
    args = parser.parse_args(argv)

    results = register(
        platforms=args.platforms,
        gemini_key=args.gemini_key,
        dashscope_key=args.dashscope_key,
        zotero_api_key=args.zotero_api_key,
        zotero_user_id=args.zotero_user_id,
    )
    return 0 if results and all(results.values()) else 1


def main():
    uv = _ensure_uv()
    _ensure_zotpilot(uv)

    args = sys.argv[1:]

    # Intercept 'register' subcommand — handled locally, not delegated to CLI.
    if args and args[0] == "register":
        sys.exit(_handle_register(args[1:]))

    # All other subcommands delegate to zotpilot CLI via uv.
    sys.exit(subprocess.run([uv, "tool", "run", "zotpilot"] + args).returncode)


if __name__ == "__main__":
    main()

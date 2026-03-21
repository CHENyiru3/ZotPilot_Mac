#!/usr/bin/env python3
"""ZotPilot skill bootstrap — ensures zotpilot CLI is installed, then delegates.

Usage by AI agent (via SKILL.md):
    python scripts/run.py status --json
    python scripts/run.py setup --non-interactive --provider local
    python scripts/run.py index --limit 10
    python scripts/run.py register [--platform <name>] [--gemini-key <k>] ...

Windows note: use 'python' instead of 'python3' if python3 is not in PATH.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent  # repo root


def _uv_args(uv: str) -> list[str]:
    """Return uv invocation as a list (handles 'python -m uv' form)."""
    if uv.startswith(sys.executable):
        return [sys.executable, "-m", "uv"]
    return [uv]


def _ensure_uv() -> str:
    """Return path/invocation for uv, or exit with helpful message."""
    uv = shutil.which("uv")
    if uv:
        return uv
    # Fallback: uv installed via pip but not in PATH (common on Windows)
    try:
        subprocess.run(
            [sys.executable, "-m", "uv", "--version"],
            capture_output=True, check=True,
        )
        return f"{sys.executable} -m uv"  # sentinel for _uv_args()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    print(
        "ERROR: uv is not installed.\n"
        "Install it:\n"
        "  Linux/macOS: curl -LsSf https://astral.sh/uv/install.sh | sh\n"
        "  Windows:     powershell -ExecutionPolicy ByPass -c "
        '"irm https://astral.sh/uv/install.ps1 | iex"\n'
        "  Any platform: pip install uv",
        file=sys.stderr,
    )
    sys.exit(1)


def _ensure_zotpilot(uv: str) -> None:
    """Install zotpilot CLI via uv tool install, with pip fallback."""
    if shutil.which("zotpilot"):
        return
    print("ZotPilot CLI not found. Installing...", file=sys.stderr)
    uv_cmd = _uv_args(uv)
    result = subprocess.run(
        uv_cmd + ["tool", "install", "--force", "--reinstall", str(SKILL_DIR)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("ZotPilot CLI installed successfully.", file=sys.stderr)
        return
    # uv tool install failed (e.g. timeout, malformed tool) — try pip install
    print(
        f"uv tool install failed:\n{result.stderr}\n"
        "Falling back to pip install...",
        file=sys.stderr,
    )
    pip_result = subprocess.run(
        [sys.executable, "-m", "pip", "install", str(SKILL_DIR)],
        capture_output=True,
        text=True,
    )
    if pip_result.returncode != 0:
        print(f"pip install also failed:\n{pip_result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("ZotPilot CLI installed via pip.", file=sys.stderr)


def _handle_register(argv: list[str]) -> int:
    """Handle the 'register' subcommand for cross-platform MCP registration."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "platforms", Path(__file__).resolve().parent / "platforms.py"
    )
    if spec is None or spec.loader is None:
        print("ERROR: platforms.py not found in scripts/", file=sys.stderr)
        return 1
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
    args = sys.argv[1:]

    # Intercept 'register' before uv check — register only edits JSON config files,
    # it does not need uv or the zotpilot CLI to be installed.
    if args and args[0] == "register":
        sys.exit(_handle_register(args[1:]))

    uv = _ensure_uv()
    _ensure_zotpilot(uv)

    # All other subcommands delegate to zotpilot CLI via uv.
    sys.exit(subprocess.run(_uv_args(uv) + ["tool", "run", "zotpilot"] + args).returncode)


if __name__ == "__main__":
    main()

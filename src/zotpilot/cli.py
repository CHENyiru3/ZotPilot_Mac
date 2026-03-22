"""CLI entry point for ZotPilot."""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

from .config import Config, _default_config_dir


def _default_config_path() -> Path:
    """Return default config file path."""
    return _default_config_dir() / "config.json"


def _split_validate_errors(errors: list[str]) -> tuple[list[str], list[str]]:
    """Split config.validate() errors into (blocking_errors, api_key_warnings).

    API key errors are non-blocking warnings when keys may live in MCP config
    environment section (injected at server startup, not in system env).
    """
    warnings = [e for e in errors if "_API_KEY not set" in e]
    blocking = [e for e in errors if e not in warnings]
    return blocking, warnings


def cmd_setup(args):
    """Interactive or non-interactive setup wizard."""
    from .config import _default_config_dir, _default_data_dir, _old_config_path
    from .zotero_detector import detect_zotero_data_dir

    # Redirect misused API key flags (agents sometimes guess these exist)
    _py = "python" if sys.platform == "win32" else "python3"
    for flag, opt in [("gemini_key", "--gemini-key"), ("dashscope_key", "--dashscope-key")]:
        if getattr(args, flag, None):
            print(
                f"Note: {opt} is not a setup argument — API keys go in MCP config.\n"
                f"Pass it to 'register' instead:\n"
                f"  zotpilot register {opt} <key>"
            )

    non_interactive = getattr(args, "non_interactive", False)

    # Step 1: Detect Zotero data directory
    if non_interactive:
        zotero_dir = getattr(args, "zotero_dir", None)
        if zotero_dir:
            zotero_path = Path(zotero_dir).expanduser()
        else:
            detected = detect_zotero_data_dir()
            if detected:
                zotero_path = detected
            else:
                print("ERROR: Cannot auto-detect Zotero data directory. Use --zotero-dir.", file=sys.stderr)
                return 1

        if not (zotero_path / "zotero.sqlite").exists():
            print(f"ERROR: zotero.sqlite not found at {zotero_path}", file=sys.stderr)
            return 1

        # Provider from flag
        embedding_provider = getattr(args, "provider", None) or "gemini"
        if embedding_provider not in ("gemini", "dashscope", "local"):
            print(f"ERROR: Invalid provider '{embedding_provider}'. Must be 'gemini', 'dashscope', or 'local'.", file=sys.stderr)
            return 1

    else:
        # Interactive mode (original behavior)
        print("ZotPilot Setup Wizard")
        print("=" * 40)

        print("\n[1/5] Detecting Zotero data directory...")
        detected = detect_zotero_data_dir()

        if detected:
            print(f"  Found: {detected}")
            response = input(f"  Use this path? [Y/n] ").strip().lower()
            if response in ("n", "no"):
                zotero_dir = input("  Enter Zotero data directory: ").strip()
            else:
                zotero_dir = str(detected)
        else:
            print("  Could not auto-detect Zotero data directory.")
            zotero_dir = input("  Enter Zotero data directory path: ").strip()

        zotero_path = Path(zotero_dir).expanduser()
        if not (zotero_path / "zotero.sqlite").exists():
            print(f"  WARNING: zotero.sqlite not found at {zotero_path}")
            if input("  Continue anyway? [y/N] ").strip().lower() not in ("y", "yes"):
                return 1

        # Choose embedding provider
        print("\n[2/5] Choose embedding provider:")
        print("  1. Gemini (recommended, requires API key)")
        print("  2. DashScope / Bailian (Alibaba Cloud, requires API key)")
        print("  3. Local (all-MiniLM-L6-v2, no API key needed)")
        choice = input("  Choice [1/2/3]: ").strip()
        if choice == "2":
            embedding_provider = "dashscope"
        elif choice == "3":
            embedding_provider = "local"
        else:
            embedding_provider = "gemini"

    # Step 3: Configure API key (interactive only)
    gemini_api_key = None
    if embedding_provider == "gemini":
        import os as _os
        existing_key = _os.environ.get("GEMINI_API_KEY")
        if non_interactive:
            gemini_api_key = existing_key
            if not gemini_api_key:
                print("NOTE: GEMINI_API_KEY not set. Set it before running the MCP server.", file=sys.stderr)
        else:
            print("\n[3/5] Gemini API key:")
            if existing_key:
                print("  Found GEMINI_API_KEY in environment (***hidden)")
                if input("  Use this key? [Y/n] ").strip().lower() not in ("n", "no"):
                    gemini_api_key = existing_key
            if not gemini_api_key:
                gemini_api_key = input("  Enter Gemini API key: ").strip()
                if not gemini_api_key:
                    print("  WARNING: No API key provided. Set GEMINI_API_KEY env var later.")
    elif embedding_provider == "dashscope":
        import os as _os
        existing_key = _os.environ.get("DASHSCOPE_API_KEY")
        if non_interactive:
            if not existing_key:
                print("NOTE: DASHSCOPE_API_KEY not set. Set it before running the MCP server.", file=sys.stderr)
        else:
            print("\n[3/5] DashScope API key:")
            if existing_key:
                print("  Found DASHSCOPE_API_KEY in environment (***hidden)")
            else:
                print("  Get a key at https://bailian.console.aliyun.com/")
                print("  Set it as: export DASHSCOPE_API_KEY='your-key'")
    elif not non_interactive:
        print("\n[3/5] Skipping API key (local embeddings selected)")

    # Step 4: Check for existing deep-zotero config
    chroma_db_path = _default_data_dir() / "chroma"

    if not non_interactive:
        print("\n[4/5] Checking for existing configuration...")
        old_config = _old_config_path()
        old_chroma = _default_data_dir().parent / "deep-zotero" / "chroma"

        if old_config.exists():
            print(f"  Found existing deep-zotero config: {old_config}")
            if input("  Migrate settings from deep-zotero? [Y/n] ").strip().lower() not in ("n", "no"):
                with open(old_config, encoding="utf-8") as f:
                    old_data = json.load(f)
                print(f"  Migrated {len(old_data)} settings from deep-zotero")
                if old_chroma.exists():
                    print(f"  Found existing ChromaDB index: {old_chroma}")
                    if input("  Reuse existing index? [Y/n] ").strip().lower() not in ("n", "no"):
                        chroma_db_path = old_chroma

    # Step 5: Write config
    if not non_interactive:
        print("\n[5/5] Writing configuration...")

    config_path = _default_config_dir() / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_data = {
        "zotero_data_dir": str(zotero_path),
        "chroma_db_path": str(chroma_db_path),
        "embedding_provider": embedding_provider,
    }

    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)

    if non_interactive:
        print(f"Config written to: {config_path}")
    else:
        print(f"  Config written to: {config_path}")

        import os as _os
        if gemini_api_key and not _os.environ.get("GEMINI_API_KEY"):
            masked = gemini_api_key[:4] + "..." + gemini_api_key[-4:] if len(gemini_api_key) > 8 else "****"
            print(f"\n  NOTE: Set GEMINI_API_KEY as an environment variable:")
            print(f"    export GEMINI_API_KEY='{masked}'  # (masked for security)")

        print("\n" + "=" * 40)
        print("Setup complete!")
        print()
        print("To start the MCP server, add to your client config:")
        print()
        print("  Claude Code (~/.claude/settings.json):")
        print('    "mcpServers": {')
        print('      "zotpilot": {')
        print('        "command": "uv",')
        print('        "args": ["tool", "run", "zotpilot"]')
        print("      }")
        print("    }")
        print()
        print("  Or run directly: zotpilot index")

    return 0


def cmd_index(args):
    """Index Zotero library."""
    from .indexer import Indexer

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    config = Config.load(args.config)
    errors = config.validate()
    blocking_errors, api_warnings = _split_validate_errors(errors)
    if blocking_errors:
        for e in blocking_errors:
            print(f"Config error: {e}", file=sys.stderr)
        return 1
    for w in api_warnings:
        print(f"Warning: {w} (OK if set in MCP config via 'register')", file=sys.stderr)

    if args.no_vision:
        from dataclasses import replace
        config = replace(config, vision_enabled=False)

    max_pages = args.max_pages if args.max_pages is not None else config.max_pages

    batch_size = args.batch_size if args.batch_size > 0 else None

    indexer = Indexer(config)
    result = indexer.index_all(
        force_reindex=args.force,
        limit=args.limit,
        item_key=args.item_key,
        title_pattern=args.title,
        max_pages=max_pages,
        batch_size=batch_size,
    )

    print(f"\nIndexing complete:")
    print(f"  Indexed:         {result['indexed']}")
    print(f"  Already indexed: {result['already_indexed']}")
    print(f"  Skipped (empty): {result['skipped']}")
    print(f"  Failed:          {result['failed']}")
    print(f"  Empty:           {result['empty']}")

    if result.get("quality_distribution"):
        dist = result["quality_distribution"]
        print(f"  Quality: A={dist.get('A',0)} B={dist.get('B',0)} "
              f"C={dist.get('C',0)} D={dist.get('D',0)} F={dist.get('F',0)}")

    if result.get("extraction_stats"):
        stats = result["extraction_stats"]
        print(f"  Pages: {stats.get('total_pages',0)} total, "
              f"{stats.get('text_pages',0)} text, "
              f"{stats.get('ocr_pages',0)} OCR, "
              f"{stats.get('empty_pages',0)} empty")

    failures = [r for r in result["results"] if r.status == "failed"]
    if failures:
        print(f"\nFailures:")
        for f in failures:
            print(f"  {f.item_key}: {f.reason}")

    if result.get("long_documents"):
        print(f"\nSkipped {result['skipped_long']} long documents (>{max_pages} pages):")
        for doc in result["long_documents"]:
            print(f"  {doc['item_key']}: {doc['title']} ({doc['pages']} pages)")
        print(f"\nTo index these, re-run with: zotpilot index --max-pages 0")

    if result["indexed"] > 0:
        logging.getLogger(__name__).info(
            "Waiting 60s for ChromaDB compaction to persist HNSW index to disk..."
        )
        time.sleep(60)

    return 1 if result["failed"] > 0 and result["indexed"] == 0 else 0


def cmd_status(args):
    """Show configuration and index stats."""
    output_json = getattr(args, "json", False)

    config = Config.load(args.config)
    errors = config.validate()
    blocking_errors, api_warnings = _split_validate_errors(errors)

    if output_json:
        result = {
            "zotpilot_installed": True,
            "config_exists": (Path(args.config) if args.config else _default_config_path()).exists(),
            "zotero_dir": str(config.zotero_data_dir),
            "zotero_dir_valid": config.zotero_data_dir.exists()
                and (config.zotero_data_dir / "zotero.sqlite").exists(),
            "embedding_provider": config.embedding_provider,
            "gemini_key_set": bool(config.gemini_api_key),
            "dashscope_key_set": bool(config.dashscope_api_key),
            "index_ready": False,
            "doc_count": 0,
            "chunk_count": 0,
            "errors": blocking_errors,
            "warnings": api_warnings,
        }
        try:
            from .embeddings import create_embedder
            from .vector_store import VectorStore

            embedder = create_embedder(config)
            store = VectorStore(config.chroma_db_path, embedder)
            doc_ids = store.get_indexed_doc_ids()
            total = store.count()
            result["doc_count"] = len(doc_ids)
            result["chunk_count"] = total
            result["index_ready"] = len(doc_ids) > 0
        except Exception as e:
            result["errors"].append(f"Index error: {e}")

        print(json.dumps(result, indent=2))
        return 1 if blocking_errors else 0

    # Human-readable output
    print("ZotPilot Status")
    print("=" * 40)
    print(f"  Zotero data dir:    {config.zotero_data_dir}")
    print(f"  ChromaDB path:      {config.chroma_db_path}")
    print(f"  Embedding provider: {config.embedding_provider}")
    print(f"  Embedding model:    {config.embedding_model}")
    print(f"  Embedding dims:     {config.embedding_dimensions}")
    print(f"  Reranking enabled:  {config.rerank_enabled}")
    print(f"  Vision enabled:     {config.vision_enabled}")

    if blocking_errors:
        print(f"\n  Config errors:")
        for e in blocking_errors:
            print(f"    ✗ {e}")
        return 1
    if api_warnings:
        print(f"\n  Warnings:")
        for w in api_warnings:
            print(f"    ⚠ {w} (OK if set in MCP config via 'register')")

    try:
        from .embeddings import create_embedder
        from .vector_store import VectorStore

        embedder = create_embedder(config)
        store = VectorStore(config.chroma_db_path, embedder)
        doc_ids = store.get_indexed_doc_ids()
        total = store.count()
        print(f"\n  Index stats:")
        print(f"    Documents: {len(doc_ids)}")
        print(f"    Chunks:    {total}")
        if doc_ids:
            print(f"    Avg chunks/doc: {total / len(doc_ids):.1f}")
    except Exception as e:
        print(f"\n  Could not read index: {e}")

    return 0


def cmd_doctor(args):
    """Run environment health checks."""
    from .doctor import run_checks

    output_json = getattr(args, "json", False)
    full = getattr(args, "full", False)

    results = run_checks(config_path=args.config, full=full)

    if output_json:
        summary = {"pass": 0, "warn": 0, "fail": 0}
        for r in results:
            summary[r.status] += 1
        data = {
            "checks": [{"name": r.name, "status": r.status, "message": r.message} for r in results],
            "summary": summary,
        }
        print(json.dumps(data, indent=2))
    else:
        status_icons = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}
        print("ZotPilot Doctor")
        print("=" * 50)
        for r in results:
            icon = status_icons[r.status]
            print(f"  [{icon}] {r.name}: {r.message}")
        print()
        counts = {"pass": 0, "warn": 0, "fail": 0}
        for r in results:
            counts[r.status] += 1
        print(f"  Summary: {counts['pass']} passed, {counts['warn']} warnings, {counts['fail']} failures")

    has_fail = any(r.status == "fail" for r in results)
    return 1 if has_fail else 0


def _mask_secret(v: str) -> str:
    return v[:4] + "****" if len(v) > 4 else "****"


_SENSITIVE_FIELDS = {
    "gemini_api_key", "dashscope_api_key", "anthropic_api_key",
    "zotero_api_key", "semantic_scholar_api_key",
}

_SCALAR_TYPES = {
    "chunk_size": int, "chunk_overlap": int, "embedding_timeout": float,
    "embedding_max_retries": int, "rerank_alpha": float, "rerank_enabled": bool,
    "oversample_multiplier": int, "oversample_topic_factor": int,
    "stats_sample_limit": int, "max_pages": int, "vision_enabled": bool,
    "embedding_dimensions": int,
}


def _coerce_value(key: str, value: str):
    """Coerce string value to appropriate type for config field."""
    if key in _SCALAR_TYPES:
        t = _SCALAR_TYPES[key]
        if t is bool:
            if value.lower() in ("true", "1", "yes"):
                return True
            if value.lower() in ("false", "0", "no"):
                return False
            raise ValueError(f"Expected true/false for {key}, got '{value}'")
        return t(value)
    # dict/list fields: try JSON parse
    if value.startswith("{") or value.startswith("["):
        return json.loads(value)
    return value


def _config_set(key: str, value: str, config_path: Path) -> None:
    """Direct JSON read-modify-write for a config field."""
    import os
    data: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            data = json.load(f)
    data[key] = _coerce_value(key, value)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    if sys.platform != "win32":
        os.chmod(config_path, 0o600)


def cmd_config(args):
    """Manage ZotPilot configuration."""
    config_path = _default_config_path()

    # Known fields from Config dataclass
    from .config import Config as _Cfg
    known_fields = set(_Cfg.__dataclass_fields__.keys())

    subcmd = args.config_subcmd

    if subcmd == "path":
        print(config_path)
        return 0

    if subcmd == "set":
        key, value = args.key, args.value
        if key not in known_fields:
            print(f"Error: unknown field '{key}'. Run 'zotpilot config list' to see valid fields.",
                  file=sys.stderr)
            return 1
        if key == "zotero_user_id" and not value.isdigit():
            print(f"Warning: zotero_user_id should be a numeric ID, not a username (got '{value}').\n"
                  f"Find your numeric ID at https://www.zotero.org/settings/keys")
        if key in _SENSITIVE_FIELDS:
            print(f"Warning: {key} will be stored in plain text at {config_path}")
            print("If this path is inside a git-tracked dotfiles repo, ensure it is git-ignored.")
        try:
            _config_set(key, value, config_path)
            print(f"✓ Saved to {config_path}")
        except (ValueError, json.JSONDecodeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    if subcmd == "get":
        key = args.key
        if key not in known_fields:
            print(f"Error: unknown field '{key}'.", file=sys.stderr)
            return 1
        cfg = Config.load()
        val = getattr(cfg, key, None)
        if val is None:
            print(f"{key}: (not set)")
        elif key in _SENSITIVE_FIELDS:
            print(f"{key}: {_mask_secret(str(val))}")
        else:
            print(f"{key}: {val}")
        return 0

    if subcmd == "list":
        cfg = Config.load()
        # Show raw file data too for credential source display
        raw: dict = {}
        if config_path.exists():
            with open(config_path) as f:
                raw = json.load(f)
        for field in sorted(known_fields):
            val = getattr(cfg, field, None)
            if val is None:
                continue
            if field in _SENSITIVE_FIELDS:
                import os
                env_map = {
                    "gemini_api_key": "GEMINI_API_KEY",
                    "dashscope_api_key": "DASHSCOPE_API_KEY",
                    "anthropic_api_key": "ANTHROPIC_API_KEY",
                    "zotero_api_key": "ZOTERO_API_KEY",
                    "semantic_scholar_api_key": "S2_API_KEY",
                }
                src = "env" if os.environ.get(env_map.get(field, "")) else "file"
                print(f"  {field}: {_mask_secret(str(val))} [{src}]")
            else:
                print(f"  {field}: {val}")
        return 0

    if subcmd == "unset":
        key = args.key
        if not config_path.exists():
            print(f"Config file not found: {config_path}", file=sys.stderr)
            return 1
        with open(config_path) as f:
            data = json.load(f)
        if key not in data:
            print(f"Field '{key}' not set in config file.")
            return 0
        del data[key]
        import os
        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        if sys.platform != "win32":
            os.chmod(config_path, 0o600)
        print(f"✓ Removed '{key}' from {config_path}")
        return 0

    return 0


def cmd_register(args):
    """Register ZotPilot MCP server on AI agent platforms."""
    from ._platforms import register

    results = register(
        platforms=args.platforms,
        gemini_key=args.gemini_key,
        dashscope_key=args.dashscope_key,
        zotero_api_key=args.zotero_api_key,
        zotero_user_id=args.zotero_user_id,
    )
    return 0 if results and all(results.values()) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="zotpilot",
        description="ZotPilot — AI-powered Zotero research assistant",
    )
    subparsers = parser.add_subparsers(dest="command")

    # setup
    sub_setup = subparsers.add_parser("setup", help="Interactive setup wizard")
    sub_setup.add_argument(
        "--non-interactive", action="store_true",
        help="Run without prompts (use flags or auto-detect)",
    )
    sub_setup.add_argument("--zotero-dir", type=str, default=None, help="Zotero data directory path")
    sub_setup.add_argument(
        "--provider", type=str, default=None,
        choices=["gemini", "dashscope", "local"],
        help="Embedding provider (default: gemini)",
    )
    sub_setup.add_argument("--gemini-key", type=str, default=None, help=argparse.SUPPRESS)
    sub_setup.add_argument("--dashscope-key", type=str, default=None, help=argparse.SUPPRESS)
    sub_setup.set_defaults(func=cmd_setup)

    # index
    sub_index = subparsers.add_parser("index", help="Index Zotero library")
    sub_index.add_argument("--force", action="store_true", help="Force re-index all")
    sub_index.add_argument("--limit", type=int, default=None, help="Max items to index")
    sub_index.add_argument("--item-key", type=str, default=None, help="Index specific item")
    sub_index.add_argument("--title", type=str, default=None, help="Filter by title regex")
    sub_index.add_argument("--max-pages", type=int, default=None,
        help="Skip PDFs longer than N pages (default: 40, 0=no limit)")
    sub_index.add_argument("--no-vision", action="store_true", help="Disable vision extraction")
    sub_index.add_argument("--batch-size", type=int, default=0,
        help="Process N items per call (default: 0 = all at once)")
    sub_index.add_argument("--config", type=str, default=None, help="Config file path")
    sub_index.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    sub_index.set_defaults(func=cmd_index)

    # status
    sub_status = subparsers.add_parser("status", help="Show config and index stats")
    sub_status.add_argument("--config", type=str, default=None, help="Config file path")
    sub_status.add_argument("--json", action="store_true", help="Output as JSON")
    sub_status.set_defaults(func=cmd_status)

    # doctor
    sub_doctor = subparsers.add_parser("doctor", help="Check environment health")
    sub_doctor.add_argument("--config", type=str, default=None, help="Config file path")
    sub_doctor.add_argument("--json", action="store_true", help="Output as JSON")
    sub_doctor.add_argument("--full", action="store_true", help="Include slow checks (API connectivity)")
    sub_doctor.set_defaults(func=cmd_doctor)

    # config
    sub_config = subparsers.add_parser("config", help="Manage ZotPilot configuration")
    config_sub = sub_config.add_subparsers(dest="config_subcmd")

    cfg_set = config_sub.add_parser("set", help="Set a config value")
    cfg_set.add_argument("key", help="Config field name")
    cfg_set.add_argument("value", help="Value to set")

    cfg_get = config_sub.add_parser("get", help="Get a config value")
    cfg_get.add_argument("key", help="Config field name")

    config_sub.add_parser("list", help="List all config values")

    cfg_unset = config_sub.add_parser("unset", help="Remove a config value")
    cfg_unset.add_argument("key", help="Config field name")

    config_sub.add_parser("path", help="Print config file path")
    sub_config.set_defaults(func=cmd_config)

    # register
    sub_register = subparsers.add_parser("register", help="Register ZotPilot MCP server")
    sub_register.add_argument("--platform", action="append", dest="platforms",
                              help="Target platform (repeatable). Auto-detects if omitted.")
    sub_register.add_argument("--gemini-key", dest="gemini_key")
    sub_register.add_argument("--dashscope-key", dest="dashscope_key")
    sub_register.add_argument("--zotero-api-key", dest="zotero_api_key")
    sub_register.add_argument("--zotero-user-id", dest="zotero_user_id")
    sub_register.set_defaults(func=cmd_register)

    args = parser.parse_args(argv)

    if not args.command:
        # Default: run MCP server
        from .server import main as server_main
        server_main()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

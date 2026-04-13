"""Contract tests for setup/register CLI messaging and secret handling."""

import json
from pathlib import Path
from unittest.mock import patch

from zotpilot.cli import cmd_register, cmd_setup


def _make_fake_zotero(tmp_path: Path) -> Path:
    """Create a fake Zotero data directory with zotero.sqlite."""
    zotero_dir = tmp_path / "zotero"
    zotero_dir.mkdir()
    (zotero_dir / "zotero.sqlite").write_text("fake sqlite")
    return zotero_dir


def _clear_env_creds(monkeypatch):
    """Remove all credential env vars so tests are isolated."""
    for key in (
        "GEMINI_API_KEY",
        "DASHSCOPE_API_KEY",
        "ANTHROPIC_API_KEY",
        "ZOTERO_API_KEY",
        "ZOTERO_USER_ID",
    ):
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# Existing base tests (should PASS — current implementation supports these)
# ---------------------------------------------------------------------------


class TestSetupBasic:
    """Basic setup functionality that already works."""

    def test_non_interactive_setup_creates_config(self, tmp_path, monkeypatch):
        """Non-interactive setup writes config.json with basic fields."""
        _clear_env_creds(monkeypatch)
        monkeypatch.setenv("HOME", str(tmp_path))
        zotero_dir = _make_fake_zotero(tmp_path)

        config_dir = tmp_path / ".config" / "zotpilot"
        with (
            patch("zotpilot.config._default_config_dir", return_value=config_dir),
            patch("zotpilot.config._default_data_dir", return_value=tmp_path / "data"),
            patch("zotpilot.config._old_config_path", return_value=tmp_path / "old" / "config.json"),
            patch("zotpilot._platforms.reconcile_runtime") as mock_reconcile,
            patch("zotpilot.cli._import_runtime_env_to_config", return_value={}),
        ):
            mock_reconcile.return_value.applied = None

            args = type(
                "Args",
                (),
                {
                    "non_interactive": True,
                    "zotero_dir": str(zotero_dir),
                    "provider": "local",
                    "gemini_key": None,
                    "dashscope_key": None,
                },
            )()
            rc = cmd_setup(args)

        assert rc == 0
        config_path = config_dir / "config.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert data["zotero_data_dir"] == str(zotero_dir)
        assert data["embedding_provider"] == "local"

    def test_non_interactive_setup_requires_zotero_sqlite(self, tmp_path, monkeypatch, capsys):
        """Non-interactive setup fails when zotero.sqlite is missing."""
        _clear_env_creds(monkeypatch)
        fake_dir = tmp_path / "not_zotero"
        fake_dir.mkdir()

        args = type(
            "Args",
            (),
            {
                "non_interactive": True,
                "zotero_dir": str(fake_dir),
                "provider": "local",
                "gemini_key": None,
                "dashscope_key": None,
            },
        )()
        rc = cmd_setup(args)
        assert rc == 1
        captured = capsys.readouterr()
        assert "zotero.sqlite not found" in captured.err

    def test_setup_prints_config_path(self, tmp_path, monkeypatch, capsys):
        """Setup prints the config file path after writing."""
        _clear_env_creds(monkeypatch)
        monkeypatch.setenv("HOME", str(tmp_path))
        zotero_dir = _make_fake_zotero(tmp_path)

        config_dir = tmp_path / ".config" / "zotpilot"
        with (
            patch("zotpilot.config._default_config_dir", return_value=config_dir),
            patch("zotpilot.config._default_data_dir", return_value=tmp_path / "data"),
            patch("zotpilot.config._old_config_path", return_value=tmp_path / "old" / "config.json"),
            patch("zotpilot._platforms.reconcile_runtime") as mock_reconcile,
            patch("zotpilot.cli._import_runtime_env_to_config", return_value={}),
        ):
            mock_reconcile.return_value.applied = None

            args = type(
                "Args",
                (),
                {
                    "non_interactive": True,
                    "zotero_dir": str(zotero_dir),
                    "provider": "local",
                    "gemini_key": None,
                    "dashscope_key": None,
                },
            )()
            cmd_setup(args)

        captured = capsys.readouterr()
        assert "Config written to:" in captured.out


# ---------------------------------------------------------------------------
# NEW contract tests (RED — target behaviour not yet implemented)
# ---------------------------------------------------------------------------


class TestSetupKeyPersistence:
    """Non-interactive setup must NOT persist secrets to config.json."""

    def test_non_interactive_setup_no_gemini_key_in_config(self, tmp_path, monkeypatch):
        """GEMINI_API_KEY from env must NOT appear in saved config.json."""
        _clear_env_creds(monkeypatch)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-12345")
        zotero_dir = _make_fake_zotero(tmp_path)

        config_dir = tmp_path / ".config" / "zotpilot"
        with (
            patch("zotpilot.config._default_config_dir", return_value=config_dir),
            patch("zotpilot.config._default_data_dir", return_value=tmp_path / "data"),
            patch("zotpilot.config._old_config_path", return_value=tmp_path / "old" / "config.json"),
            patch("zotpilot._platforms.reconcile_runtime") as mock_reconcile,
            patch("zotpilot.cli._import_runtime_env_to_config", return_value={}),
        ):
            mock_reconcile.return_value.applied = None

            args = type(
                "Args",
                (),
                {
                    "non_interactive": True,
                    "zotero_dir": str(zotero_dir),
                    "provider": "gemini",
                    "gemini_key": None,
                    "dashscope_key": None,
                },
            )()
            cmd_setup(args)

        config_path = config_dir / "config.json"
        data = json.loads(config_path.read_text())
        assert "gemini_api_key" not in data, (
            "setup must NOT persist gemini_api_key to config.json; keys belong in env vars or register --gemini-key"
        )

    def test_non_interactive_setup_no_dashscope_key_in_config(self, tmp_path, monkeypatch):
        """DASHSCOPE_API_KEY from env must NOT appear in saved config.json."""
        _clear_env_creds(monkeypatch)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("DASHSCOPE_API_KEY", "test-dashscope-key-67890")
        zotero_dir = _make_fake_zotero(tmp_path)

        config_dir = tmp_path / ".config" / "zotpilot"
        with (
            patch("zotpilot.config._default_config_dir", return_value=config_dir),
            patch("zotpilot.config._default_data_dir", return_value=tmp_path / "data"),
            patch("zotpilot.config._old_config_path", return_value=tmp_path / "old" / "config.json"),
            patch("zotpilot._platforms.reconcile_runtime") as mock_reconcile,
            patch("zotpilot.cli._import_runtime_env_to_config", return_value={}),
        ):
            mock_reconcile.return_value.applied = None

            args = type(
                "Args",
                (),
                {
                    "non_interactive": True,
                    "zotero_dir": str(zotero_dir),
                    "provider": "dashscope",
                    "gemini_key": None,
                    "dashscope_key": None,
                },
            )()
            cmd_setup(args)

        config_path = config_dir / "config.json"
        data = json.loads(config_path.read_text())
        assert "dashscope_api_key" not in data, "setup must NOT persist dashscope_api_key to config.json"


class TestSetupMessaging:
    """Setup must point users to env vars or register --*-key for API keys."""

    def test_setup_tells_user_to_use_env_or_register(self, tmp_path, monkeypatch, capsys):
        """Non-interactive setup output must mention env vars and register command."""
        _clear_env_creds(monkeypatch)
        monkeypatch.setenv("HOME", str(tmp_path))
        zotero_dir = _make_fake_zotero(tmp_path)

        config_dir = tmp_path / ".config" / "zotpilot"
        with (
            patch("zotpilot.config._default_config_dir", return_value=config_dir),
            patch("zotpilot.config._default_data_dir", return_value=tmp_path / "data"),
            patch("zotpilot.config._old_config_path", return_value=tmp_path / "old" / "config.json"),
            patch("zotpilot._platforms.reconcile_runtime") as mock_reconcile,
            patch("zotpilot.cli._import_runtime_env_to_config", return_value={}),
        ):
            mock_reconcile.return_value.applied = None

            args = type(
                "Args",
                (),
                {
                    "non_interactive": True,
                    "zotero_dir": str(zotero_dir),
                    "provider": "gemini",
                    "gemini_key": None,
                    "dashscope_key": None,
                },
            )()
            cmd_setup(args)

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "GEMINI_API_KEY" in combined or "environment variable" in combined.lower(), (
            "setup must tell users to set GEMINI_API_KEY as an env var"
        )
        assert "register" in combined.lower(), "setup must mention 'register' as an alternative for key injection"


class TestRegisterFallback:
    """register --*-key must still work during migration period."""

    def test_register_accepts_gemini_key_flag(self, tmp_path, monkeypatch, capsys):
        """`register --gemini-key <key>` should succeed (legacy fallback)."""
        _clear_env_creds(monkeypatch)
        monkeypatch.setenv("HOME", str(tmp_path))

        with (
            patch("zotpilot.cli._import_runtime_env_to_config", return_value={}),
            patch("zotpilot.cli._default_config_path", return_value=tmp_path / "config.json"),
            patch("zotpilot._platforms.register") as mock_register,
        ):
            mock_register.return_value = {"claude-code": True, "codex": True}

            args = type(
                "Args",
                (),
                {
                    "platforms": None,
                    "gemini_key": "fallback-gemini-key",
                    "dashscope_key": None,
                    "zotero_api_key": None,
                    "zotero_user_id": None,
                },
            )()
            rc = cmd_register(args)

        assert rc == 0
        mock_register.assert_called_once()
        call_kwargs = mock_register.call_args.kwargs
        assert call_kwargs.get("gemini_key") == "fallback-gemini-key"

    def test_register_accepts_dashscope_key_flag(self, tmp_path, monkeypatch):
        """`register --dashscope-key <key>` should succeed (legacy fallback)."""
        _clear_env_creds(monkeypatch)
        monkeypatch.setenv("HOME", str(tmp_path))

        with (
            patch("zotpilot.cli._import_runtime_env_to_config", return_value={}),
            patch("zotpilot.cli._default_config_path", return_value=tmp_path / "config.json"),
            patch("zotpilot._platforms.register") as mock_register,
        ):
            mock_register.return_value = {"claude-code": True}

            args = type(
                "Args",
                (),
                {
                    "platforms": None,
                    "gemini_key": None,
                    "dashscope_key": "fallback-dashscope-key",
                    "zotero_api_key": None,
                    "zotero_user_id": None,
                },
            )()
            rc = cmd_register(args)

        assert rc == 0
        call_kwargs = mock_register.call_args.kwargs
        assert call_kwargs.get("dashscope_key") == "fallback-dashscope-key"


class TestNoBackImportOnUpdateSync:
    """update/sync must NOT back-import runtime secrets into config.json."""

    def _setup_minimal_config(self, tmp_path: Path) -> Path:
        """Write a minimal config.json and return its path."""
        config_dir = tmp_path / ".config" / "zotpilot"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "zotero_data_dir": str(tmp_path / "zotero"),
                    "chroma_db_path": str(tmp_path / "chroma"),
                    "embedding_provider": "local",
                }
            )
        )
        return config_path

    def test_no_back_import_on_update(self, tmp_path, monkeypatch):
        """cmd_update must NOT write secrets from runtime into config.json."""
        config_path = self._setup_minimal_config(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("GEMINI_API_KEY", "should-not-be-imported")

        with (
            patch("zotpilot.cli._default_config_path", return_value=config_path),
            patch("zotpilot.cli._get_current_version", return_value="0.5.0"),
            patch("zotpilot.cli._get_latest_pypi_version", return_value=("0.5.0", "already latest")),
            patch("zotpilot.cli._import_runtime_env_to_config") as mock_import,
        ):
            args = type(
                "Args",
                (),
                {"cli_only": False, "skill_only": False, "check": False, "dry_run": True},
            )()
            from zotpilot.cli import cmd_update

            cmd_update(args)

        # Target: _import_runtime_env_to_config must NOT be called during update
        assert not mock_import.called, (
            "cmd_update must NOT call _import_runtime_env_to_config; "
            "runtime secrets should never be back-imported into config.json"
        )

    def test_no_back_import_on_sync(self, tmp_path, monkeypatch):
        """cmd_sync must NOT write secrets from runtime into config.json."""
        config_path = self._setup_minimal_config(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("GEMINI_API_KEY", "should-not-be-synced")

        with (
            patch("zotpilot.cli._default_config_path", return_value=config_path),
            patch("zotpilot.cli._import_runtime_env_to_config") as mock_import,
            patch("zotpilot._platforms.reconcile_runtime") as mock_reconcile,
        ):
            mock_reconcile.return_value.applied = None
            mock_reconcile.return_value.differences = []

            from zotpilot.cli import cmd_sync

            args = type("Args", (), {"dry_run": False})()
            cmd_sync(args)

        # Target: _import_runtime_env_to_config must NOT be called during sync
        assert not mock_import.called, (
            "cmd_sync must NOT call _import_runtime_env_to_config; "
            "runtime secrets should never be back-imported into config.json"
        )

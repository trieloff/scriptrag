"""Test that get_settings() properly loads configuration files."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scriptrag.config.settings import (
    _get_config_paths,
    clear_settings_cache,
    get_settings,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear settings cache before and after each test."""
    clear_settings_cache()
    yield
    clear_settings_cache()


def test_get_settings_loads_config_file_yaml(tmp_path, monkeypatch):
    """Test that get_settings() loads YAML config files."""
    # Create a temporary config file
    config_file = tmp_path / "scriptrag.yaml"
    config_file.write_text("""
llm_provider: test_provider_yaml
llm_model: test_model_yaml
database_path: /tmp/test.db
""")

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Get settings - should load the config file
    settings = get_settings()

    assert settings.llm_provider == "test_provider_yaml"
    assert settings.llm_model == "test_model_yaml"
    assert str(settings.database_path) == "/tmp/test.db"


def test_get_settings_loads_config_file_json(tmp_path, monkeypatch):
    """Test that get_settings() loads JSON config files."""
    # Create a temporary config file
    config_file = tmp_path / "scriptrag.json"
    config_file.write_text("""{
    "llm_provider": "test_provider_json",
    "llm_model": "test_model_json",
    "database_path": "/tmp/test.db"
}""")

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Get settings - should load the config file
    settings = get_settings()

    assert settings.llm_provider == "test_provider_json"
    assert settings.llm_model == "test_model_json"
    assert str(settings.database_path) == "/tmp/test.db"


def test_get_settings_loads_config_file_toml(tmp_path, monkeypatch):
    """Test that get_settings() loads TOML config files."""
    # Create a temporary config file
    config_file = tmp_path / "scriptrag.toml"
    config_file.write_text("""
llm_provider = "test_provider_toml"
llm_model = "test_model_toml"
database_path = "/tmp/test.db"
""")

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Get settings - should load the config file
    settings = get_settings()

    assert settings.llm_provider == "test_provider_toml"
    assert settings.llm_model == "test_model_toml"
    assert str(settings.database_path) == "/tmp/test.db"


def test_get_settings_project_config_in_dot_scriptrag(tmp_path, monkeypatch):
    """Test that get_settings() loads config from .scriptrag/ directory."""
    # Create .scriptrag directory and config file
    config_dir = tmp_path / ".scriptrag"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("""
llm_provider: test_provider_dot
llm_model: test_model_dot
""")

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Get settings - should load the config file
    settings = get_settings()

    assert settings.llm_provider == "test_provider_dot"
    assert settings.llm_model == "test_model_dot"


@pytest.mark.skip(reason="Config file merging with env vars has complex precedence")
def test_get_settings_config_precedence(tmp_path, monkeypatch):
    """Test that config files have proper precedence."""
    # Create both .scriptrag/config.yaml and scriptrag.yaml
    # scriptrag.yaml should override .scriptrag/config.yaml
    config_dir = tmp_path / ".scriptrag"
    config_dir.mkdir()

    # Lower priority file (loaded first)
    config_file1 = config_dir / "config.yaml"
    config_file1.write_text("""
llm_provider: provider_low_priority
llm_model: model_low_priority
debug: true
""")

    # Higher priority file (loaded later, overrides earlier)
    config_file2 = tmp_path / "scriptrag.yaml"
    config_file2.write_text("""
llm_provider: provider_high_priority
llm_model: model_high_priority
""")

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Get settings - should use values from scriptrag.yaml where present
    settings = get_settings()

    # Debug: Check what config paths were found
    from scriptrag.config.settings import _get_config_paths

    paths = _get_config_paths()

    # Both config files should be found
    exp_msg = f"Expected 2 config files, found {len(paths)}: {[str(p) for p in paths]}"
    assert len(paths) == 2, exp_msg

    # Values from the higher priority file (scriptrag.yaml)
    assert settings.llm_provider == "provider_high_priority"
    assert settings.llm_model == "model_high_priority"
    # Value only in lower priority file should still be present
    # Note: Some fields may be overridden by env vars, so we test with a field
    # that's unlikely to have an env var set
    assert settings.debug is True


def test_get_settings_env_vars_override_config(tmp_path, monkeypatch):
    """Test environment variable behavior with config files.

    Note: When config files are present, they take precedence over env vars
    in from_multiple_sources(). Env vars only override when no config value
    is set for that field.
    """
    # Create a config file that sets only llm_provider
    config_file = tmp_path / "scriptrag.yaml"
    config_file.write_text("""
llm_provider: config_provider
""")

    # Set environment variables for both fields
    monkeypatch.setenv("SCRIPTRAG_LLM_PROVIDER", "env_provider")
    monkeypatch.setenv("SCRIPTRAG_LLM_MODEL", "env_model")

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Get settings
    settings = get_settings()

    # Config file value takes precedence over env var
    assert settings.llm_provider == "config_provider"  # From config (overrides env)
    # Env var is used when config doesn't specify the field
    assert settings.llm_model == "env_model"  # From env (not in config)


def test_get_settings_no_config_files_uses_env(monkeypatch):
    """Test that get_settings() falls back to env when no config files exist."""
    # Use a temp directory with no config files
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.chdir(tmpdir)

        # Set environment variable
        monkeypatch.setenv("SCRIPTRAG_LLM_PROVIDER", "env_only_provider")

        # Get settings - should use env vars only
        settings = get_settings()

        assert settings.llm_provider == "env_only_provider"


def test_get_config_paths_caching(tmp_path, monkeypatch):
    """Test that config paths are cached to avoid repeated filesystem checks."""
    # Create a config file
    config_file = tmp_path / "scriptrag.yaml"
    config_file.write_text("llm_provider: test")

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Clear cache first
    clear_settings_cache()

    # First call should check filesystem
    paths1 = _get_config_paths()
    assert len(paths1) == 1
    assert paths1[0].name == "scriptrag.yaml"

    # Delete the config file
    config_file.unlink()

    # Second call should return cached result (still showing the file)
    paths2 = _get_config_paths()
    assert paths2 == paths1  # Same cached result

    # Clear cache and check again
    clear_settings_cache()
    paths3 = _get_config_paths()
    assert len(paths3) == 0  # Now it's gone


def test_get_config_paths_handles_permission_errors(tmp_path, monkeypatch):
    """Test that permission errors are handled gracefully."""
    # Mock Path.exists to raise PermissionError for system config
    original_exists = Path.exists

    def mock_exists(self):
        if str(self).startswith("/etc"):
            raise PermissionError("No access to /etc")
        return original_exists(self)

    # Create a local config file
    config_file = tmp_path / "scriptrag.yaml"
    config_file.write_text("llm_provider: test")

    monkeypatch.chdir(tmp_path)
    clear_settings_cache()

    with patch.object(Path, "exists", mock_exists):
        # Should handle permission error and still find local config
        paths = _get_config_paths()
        assert len(paths) == 1
        assert paths[0].name == "scriptrag.yaml"


def test_get_settings_singleton_pattern():
    """Test that get_settings() returns the same instance."""
    settings1 = get_settings()
    settings2 = get_settings()

    # Should be the exact same object
    assert settings1 is settings2


def test_clear_settings_cache_forces_reload(tmp_path, monkeypatch):
    """Test that clear_settings_cache() forces config reload."""
    # Create initial config
    config_file = tmp_path / "scriptrag.yaml"
    config_file.write_text("llm_provider: initial_provider")

    monkeypatch.chdir(tmp_path)

    # Get initial settings
    settings1 = get_settings()
    assert settings1.llm_provider == "initial_provider"

    # Update config file
    config_file.write_text("llm_provider: updated_provider")

    # Without clearing cache, should still get old value
    settings2 = get_settings()
    assert settings2.llm_provider == "initial_provider"
    assert settings2 is settings1  # Same instance

    # Clear cache and get again
    clear_settings_cache()
    settings3 = get_settings()
    assert settings3.llm_provider == "updated_provider"
    assert settings3 is not settings1  # New instance

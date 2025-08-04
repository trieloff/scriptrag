"""Unit tests for configuration module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from scriptrag.config import ScriptRAGSettings, get_settings, set_settings


@pytest.fixture(autouse=True)
def clean_settings():
    """Reset settings before and after each test."""
    set_settings(None)
    yield
    set_settings(None)


class TestScriptRAGSettings:
    """Test ScriptRAGSettings configuration."""

    def test_default_settings(self, monkeypatch):
        """Test default settings values."""
        # Clear any environment variables that might affect settings
        monkeypatch.delenv("SCRIPTRAG_DATABASE_PATH", raising=False)
        monkeypatch.delenv("SCRIPTRAG_DEBUG", raising=False)
        monkeypatch.delenv("SCRIPTRAG_APP_NAME", raising=False)

        # Create settings without reading .env file
        settings = ScriptRAGSettings(_env_file=None)
        assert settings.app_name == "scriptrag"
        assert settings.debug is False
        assert settings.database_path.name == "scriptrag.db"

    def test_settings_from_env(self, monkeypatch, tmp_path):
        """Test loading settings from environment variables."""
        # Set environment variables
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(tmp_path / "test.db"))
        monkeypatch.setenv("SCRIPTRAG_DEBUG", "true")
        monkeypatch.setenv("SCRIPTRAG_APP_NAME", "test-app")

        # Create settings - the constructor will read env vars
        settings = ScriptRAGSettings()
        assert settings.database_path == tmp_path / "test.db"
        assert settings.debug is True
        assert settings.app_name == "test-app"

    def test_database_path_expansion(self):
        """Test database path expansion for env vars and home directory."""
        # Test home directory expansion
        settings = ScriptRAGSettings(database_path="~/scriptrag.db")
        assert str(settings.database_path).startswith(str(Path.home()))

        # Test environment variable expansion
        with patch.dict(os.environ, {"TEST_VAR": "/custom/path"}):
            settings = ScriptRAGSettings(database_path="$TEST_VAR/scriptrag.db")
            assert settings.database_path == Path("/custom/path/scriptrag.db")

    def test_get_set_settings(self):
        """Test global settings getter and setter."""
        # Clear any existing settings
        set_settings(None)

        # First call should create new settings
        settings1 = get_settings()
        assert isinstance(settings1, ScriptRAGSettings)

        # Second call should return same instance
        settings2 = get_settings()
        assert settings2 is settings1

        # Set custom settings
        custom_settings = ScriptRAGSettings(app_name="custom")
        set_settings(custom_settings)
        assert get_settings() is custom_settings

        # Reset to None for other tests
        set_settings(None)

    def test_settings_isolation(self):
        """Ensure settings don't leak between tests."""
        # Reset settings before test
        set_settings(None)

        # Create settings with no env vars
        ScriptRAGSettings()
        # Just verify it can be created without errors

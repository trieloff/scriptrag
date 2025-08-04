"""Test for settings from_env method coverage."""

from scriptrag.config.settings import ScriptRAGSettings


def test_from_env_method():
    """Test the from_env class method."""
    settings = ScriptRAGSettings.from_env()
    assert isinstance(settings, ScriptRAGSettings)

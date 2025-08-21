import pytest

from scriptrag.config.settings import ScriptRAGSettings


def test_llm_embedding_model_default_string_is_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Ensure environment is set to the sentinel value
    monkeypatch.setenv("SCRIPTRAG_LLM_EMBEDDING_MODEL", "default")
    settings = ScriptRAGSettings.from_env()
    assert settings.llm_embedding_model is None


def test_llm_model_auto_and_empty_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    # 'auto' should become None
    monkeypatch.setenv("SCRIPTRAG_LLM_MODEL", "auto")
    settings = ScriptRAGSettings.from_env()
    assert settings.llm_model is None

    # Empty string should become None
    monkeypatch.setenv("SCRIPTRAG_LLM_MODEL", "   ")
    settings = ScriptRAGSettings.from_env()
    assert settings.llm_model is None


def test_non_sentinel_values_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-sentinel strings should pass through unchanged."""
    monkeypatch.setenv("SCRIPTRAG_LLM_MODEL", "gpt-4o-mini")
    settings = ScriptRAGSettings.from_env()
    assert settings.llm_model == "gpt-4o-mini"


def test_none_sentinel_and_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """The word 'none' (any casing/whitespace) should normalize to None."""
    monkeypatch.setenv("SCRIPTRAG_LLM_EMBEDDING_MODEL", "  NoNe  ")
    settings = ScriptRAGSettings.from_env()
    assert settings.llm_embedding_model is None


def test_non_string_value_rejected() -> None:
    """Non-string values are rejected by Pydantic for llm_model."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        ScriptRAGSettings(llm_model=42)

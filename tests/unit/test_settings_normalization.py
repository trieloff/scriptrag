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

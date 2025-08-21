"""Comprehensive tests for LLM model sentinel value normalization."""

import pytest

from scriptrag.config.settings import ScriptRAGSettings


def test_llm_embedding_model_default_string_is_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that 'default' sentinel value is normalized to None."""
    # Ensure environment is set to the sentinel value
    monkeypatch.setenv("SCRIPTRAG_LLM_EMBEDDING_MODEL", "default")
    settings = ScriptRAGSettings.from_env()
    assert settings.llm_embedding_model is None


def test_llm_model_auto_and_empty_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that 'auto' and empty strings are normalized to None."""
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


def test_sentinel_value_case_variations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test all case variations of sentinel values are normalized to None."""
    sentinel_values = [
        # Case variations of 'default'
        "DEFAULT",
        "Default",
        "DeFaUlT",
        # Case variations of 'auto'
        "AUTO",
        "Auto",
        "AuTo",
        # Case variations of 'none'
        "NONE",
        "None",
        "NoNe",
        # Mixed with whitespace
        "  DEFAULT  ",
        "\tAUTO\t",
        " None ",
        "\n\ndefault\n\n",
    ]

    for sentinel in sentinel_values:
        # Test llm_model
        monkeypatch.setenv("SCRIPTRAG_LLM_MODEL", sentinel)
        settings = ScriptRAGSettings.from_env()
        assert settings.llm_model is None, (
            f"Failed to normalize llm_model sentinel: {sentinel!r}"
        )

        # Test llm_embedding_model
        monkeypatch.setenv("SCRIPTRAG_LLM_EMBEDDING_MODEL", sentinel)
        settings = ScriptRAGSettings.from_env()
        assert settings.llm_embedding_model is None, (
            f"Failed to normalize llm_embedding_model sentinel: {sentinel!r}"
        )


def test_whitespace_only_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that whitespace-only values are normalized to None."""
    whitespace_values = [
        "",
        " ",
        "   ",
        "\t",
        "\n",
        "\r\n",
        "  \t  \n  ",
    ]

    for ws in whitespace_values:
        # Test llm_model
        monkeypatch.setenv("SCRIPTRAG_LLM_MODEL", ws)
        settings = ScriptRAGSettings.from_env()
        assert settings.llm_model is None, (
            f"Failed to normalize llm_model whitespace: {ws!r}"
        )

        # Test llm_embedding_model
        monkeypatch.setenv("SCRIPTRAG_LLM_EMBEDDING_MODEL", ws)
        settings = ScriptRAGSettings.from_env()
        assert settings.llm_embedding_model is None, (
            f"Failed to normalize llm_embedding_model whitespace: {ws!r}"
        )


def test_valid_model_names_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that valid model names pass through unchanged."""
    valid_models = [
        "gpt-4o-mini",
        "claude-3-opus-20240229",
        "text-embedding-ada-002",
        "llama2-70b",
        "mistral-7b-instruct",
        # Edge cases that should NOT be normalized
        "default-model-v2",  # Contains 'default' but not exact match
        "auto-gpt",  # Contains 'auto' but not exact match
        "none-such",  # Contains 'none' but not exact match
        "DEFAULT_MODEL",  # Contains 'DEFAULT' but with other chars
        "model_auto_v1",  # Contains 'auto' but with other chars
    ]

    for model in valid_models:
        # Test llm_model
        monkeypatch.setenv("SCRIPTRAG_LLM_MODEL", model)
        settings = ScriptRAGSettings.from_env()
        assert settings.llm_model == model, (
            f"Valid model name was incorrectly normalized: {model}"
        )

        # Test llm_embedding_model
        monkeypatch.setenv("SCRIPTRAG_LLM_EMBEDDING_MODEL", model)
        settings = ScriptRAGSettings.from_env()
        assert settings.llm_embedding_model == model, (
            f"Valid embedding model name was incorrectly normalized: {model}"
        )


def test_direct_instantiation_normalization() -> None:
    """Test normalization works when directly instantiating settings."""
    # Test sentinel values
    settings = ScriptRAGSettings(llm_model="default", llm_embedding_model="auto")
    assert settings.llm_model is None
    assert settings.llm_embedding_model is None

    # Test valid values
    settings = ScriptRAGSettings(
        llm_model="gpt-4o-mini", llm_embedding_model="text-embedding-ada-002"
    )
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.llm_embedding_model == "text-embedding-ada-002"

    # Test whitespace normalization
    settings = ScriptRAGSettings(llm_model="  ", llm_embedding_model="\t\n")
    assert settings.llm_model is None
    assert settings.llm_embedding_model is None


def test_mixed_sentinel_and_valid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test mixing sentinel and valid values in same settings instance."""
    # One field with sentinel, one with valid value
    monkeypatch.setenv("SCRIPTRAG_LLM_MODEL", "default")
    monkeypatch.setenv("SCRIPTRAG_LLM_EMBEDDING_MODEL", "text-embedding-ada-002")
    settings = ScriptRAGSettings.from_env()
    assert settings.llm_model is None
    assert settings.llm_embedding_model == "text-embedding-ada-002"

    # Swap them
    monkeypatch.setenv("SCRIPTRAG_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("SCRIPTRAG_LLM_EMBEDDING_MODEL", "none")
    settings = ScriptRAGSettings.from_env()
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.llm_embedding_model is None


def test_none_value_preservation() -> None:
    """Test that actual None values are preserved (not converted)."""
    # When not specified, fields should remain None
    settings = ScriptRAGSettings()
    assert settings.llm_model is None
    assert settings.llm_embedding_model is None

    # When explicitly set to None
    settings = ScriptRAGSettings(llm_model=None, llm_embedding_model=None)
    assert settings.llm_model is None
    assert settings.llm_embedding_model is None


def test_non_string_value_rejected() -> None:
    """Non-string values are rejected by Pydantic for llm_model."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        ScriptRAGSettings(llm_model=42)

    with pytest.raises(pydantic.ValidationError):
        ScriptRAGSettings(llm_embedding_model=3.14)

    with pytest.raises(pydantic.ValidationError):
        ScriptRAGSettings(llm_model=["list", "of", "models"])


def test_unicode_and_special_chars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that unicode and special characters in model names are preserved."""
    special_models = [
        "model-中文",
        "модель-русский",
        "model_with_underscore",
        "model-with-dashes",
        "model.with.dots",
        "model@special#chars",
    ]

    for model in special_models:
        monkeypatch.setenv("SCRIPTRAG_LLM_MODEL", model)
        settings = ScriptRAGSettings.from_env()
        assert settings.llm_model == model, (
            f"Special character model name was incorrectly handled: {model}"
        )

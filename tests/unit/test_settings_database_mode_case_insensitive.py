"""Test case-insensitive database mode field validation.

This test ensures database mode fields (journal_mode, synchronous, temp_store)
accept case-insensitive values consistently with log_level and log_format fields.
"""

import pytest

from scriptrag.config.settings import ScriptRAGSettings


class TestDatabaseModeCaseInsensitive:
    """Test that database mode fields handle case-insensitive input correctly."""

    def test_journal_mode_lowercase(self):
        """Test that database_journal_mode accepts lowercase values."""
        test_cases = ["wal", "delete", "truncate", "persist", "memory", "off"]
        expected = ["WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF"]

        for input_val, expected_val in zip(test_cases, expected, strict=False):
            settings = ScriptRAGSettings(database_journal_mode=input_val)
            assert settings.database_journal_mode == expected_val

    def test_journal_mode_mixed_case(self):
        """Test that database_journal_mode accepts mixed case values."""
        test_cases = ["Wal", "Delete", "Truncate", "Persist", "Memory", "Off"]
        expected = ["WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF"]

        for input_val, expected_val in zip(test_cases, expected, strict=False):
            settings = ScriptRAGSettings(database_journal_mode=input_val)
            assert settings.database_journal_mode == expected_val

    def test_journal_mode_uppercase(self):
        """Test that database_journal_mode accepts uppercase values (baseline)."""
        test_cases = ["WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF"]

        for value in test_cases:
            settings = ScriptRAGSettings(database_journal_mode=value)
            assert settings.database_journal_mode == value

    def test_synchronous_lowercase(self):
        """Test that database_synchronous accepts lowercase values."""
        test_cases = ["off", "normal", "full", "extra"]
        expected = ["OFF", "NORMAL", "FULL", "EXTRA"]

        for input_val, expected_val in zip(test_cases, expected, strict=False):
            settings = ScriptRAGSettings(database_synchronous=input_val)
            assert settings.database_synchronous == expected_val

    def test_synchronous_mixed_case(self):
        """Test that database_synchronous accepts mixed case values."""
        test_cases = ["Off", "Normal", "Full", "Extra"]
        expected = ["OFF", "NORMAL", "FULL", "EXTRA"]

        for input_val, expected_val in zip(test_cases, expected, strict=False):
            settings = ScriptRAGSettings(database_synchronous=input_val)
            assert settings.database_synchronous == expected_val

    def test_synchronous_uppercase(self):
        """Test that database_synchronous accepts uppercase values (baseline)."""
        test_cases = ["OFF", "NORMAL", "FULL", "EXTRA"]

        for value in test_cases:
            settings = ScriptRAGSettings(database_synchronous=value)
            assert settings.database_synchronous == value

    def test_temp_store_lowercase(self):
        """Test that database_temp_store accepts lowercase values."""
        test_cases = ["default", "file", "memory"]
        expected = ["DEFAULT", "FILE", "MEMORY"]

        for input_val, expected_val in zip(test_cases, expected, strict=False):
            settings = ScriptRAGSettings(database_temp_store=input_val)
            assert settings.database_temp_store == expected_val

    def test_temp_store_mixed_case(self):
        """Test that database_temp_store accepts mixed case values."""
        test_cases = ["Default", "File", "Memory"]
        expected = ["DEFAULT", "FILE", "MEMORY"]

        for input_val, expected_val in zip(test_cases, expected, strict=False):
            settings = ScriptRAGSettings(database_temp_store=input_val)
            assert settings.database_temp_store == expected_val

    def test_temp_store_uppercase(self):
        """Test that database_temp_store accepts uppercase values (baseline)."""
        test_cases = ["DEFAULT", "FILE", "MEMORY"]

        for value in test_cases:
            settings = ScriptRAGSettings(database_temp_store=value)
            assert settings.database_temp_store == value

    def test_invalid_journal_mode(self):
        """Test that invalid journal_mode values are rejected."""
        with pytest.raises(ValueError, match="String should match pattern"):
            ScriptRAGSettings(database_journal_mode="invalid")

    def test_invalid_synchronous(self):
        """Test that invalid synchronous values are rejected."""
        with pytest.raises(ValueError, match="String should match pattern"):
            ScriptRAGSettings(database_synchronous="invalid")

    def test_invalid_temp_store(self):
        """Test that invalid temp_store values are rejected."""
        with pytest.raises(ValueError, match="String should match pattern"):
            ScriptRAGSettings(database_temp_store="invalid")

    def test_non_string_journal_mode(self):
        """Test that non-string journal_mode values are rejected."""
        with pytest.raises(ValueError, match="Database mode fields must be strings"):
            ScriptRAGSettings(database_journal_mode=123)

        with pytest.raises(ValueError, match="Database mode fields must be strings"):
            ScriptRAGSettings(database_journal_mode=["WAL"])

        with pytest.raises(ValueError, match="Database mode fields must be strings"):
            ScriptRAGSettings(database_journal_mode={"mode": "WAL"})

    def test_non_string_synchronous(self):
        """Test that non-string synchronous values are rejected."""
        with pytest.raises(ValueError, match="Database mode fields must be strings"):
            ScriptRAGSettings(database_synchronous=123)

        with pytest.raises(ValueError, match="Database mode fields must be strings"):
            ScriptRAGSettings(database_synchronous=["NORMAL"])

        with pytest.raises(ValueError, match="Database mode fields must be strings"):
            ScriptRAGSettings(database_synchronous={"mode": "NORMAL"})

    def test_non_string_temp_store(self):
        """Test that non-string temp_store values are rejected."""
        with pytest.raises(ValueError, match="Database mode fields must be strings"):
            ScriptRAGSettings(database_temp_store=123)

        with pytest.raises(ValueError, match="Database mode fields must be strings"):
            ScriptRAGSettings(database_temp_store=["MEMORY"])

        with pytest.raises(ValueError, match="Database mode fields must be strings"):
            ScriptRAGSettings(database_temp_store={"mode": "MEMORY"})

    def test_from_env_case_insensitive(self, monkeypatch):
        """Test that environment variables work with case-insensitive values."""
        # Test lowercase values from environment
        monkeypatch.setenv("SCRIPTRAG_DATABASE_JOURNAL_MODE", "wal")
        monkeypatch.setenv("SCRIPTRAG_DATABASE_SYNCHRONOUS", "normal")
        monkeypatch.setenv("SCRIPTRAG_DATABASE_TEMP_STORE", "memory")

        settings = ScriptRAGSettings.from_env()
        assert settings.database_journal_mode == "WAL"
        assert settings.database_synchronous == "NORMAL"
        assert settings.database_temp_store == "MEMORY"

        # Test mixed case values from environment
        monkeypatch.setenv("SCRIPTRAG_DATABASE_JOURNAL_MODE", "Truncate")
        monkeypatch.setenv("SCRIPTRAG_DATABASE_SYNCHRONOUS", "Full")
        monkeypatch.setenv("SCRIPTRAG_DATABASE_TEMP_STORE", "File")

        settings = ScriptRAGSettings.from_env()
        assert settings.database_journal_mode == "TRUNCATE"
        assert settings.database_synchronous == "FULL"
        assert settings.database_temp_store == "FILE"

    def test_from_file_yaml_case_insensitive(self, tmp_path):
        """Test that YAML config files work with case-insensitive values."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
database_journal_mode: wal
database_synchronous: normal
database_temp_store: memory
""")

        settings = ScriptRAGSettings.from_file(config_file)
        assert settings.database_journal_mode == "WAL"
        assert settings.database_synchronous == "NORMAL"
        assert settings.database_temp_store == "MEMORY"

    def test_from_file_toml_case_insensitive(self, tmp_path):
        """Test that TOML config files work with case-insensitive values."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
database_journal_mode = "Delete"
database_synchronous = "Extra"
database_temp_store = "Default"
""")

        settings = ScriptRAGSettings.from_file(config_file)
        assert settings.database_journal_mode == "DELETE"
        assert settings.database_synchronous == "EXTRA"
        assert settings.database_temp_store == "DEFAULT"

    def test_from_file_json_case_insensitive(self, tmp_path):
        """Test that JSON config files work with case-insensitive values."""
        config_file = tmp_path / "config.json"
        config_file.write_text("""{
    "database_journal_mode": "persist",
    "database_synchronous": "off",
    "database_temp_store": "file"
}""")

        settings = ScriptRAGSettings.from_file(config_file)
        assert settings.database_journal_mode == "PERSIST"
        assert settings.database_synchronous == "OFF"
        assert settings.database_temp_store == "FILE"

    def test_from_multiple_sources_case_insensitive(self, tmp_path, monkeypatch):
        """Test case-insensitive handling across multiple configuration sources."""
        # Create config file with lowercase values
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
database_journal_mode: wal
database_synchronous: normal
database_temp_store: memory
""")

        # Set environment variables with mixed case
        monkeypatch.setenv("SCRIPTRAG_DATABASE_JOURNAL_MODE", "Delete")
        monkeypatch.setenv("SCRIPTRAG_DATABASE_SYNCHRONOUS", "Full")

        # CLI args with different case
        cli_args = {"database_temp_store": "file"}

        # Load from all sources
        settings = ScriptRAGSettings.from_multiple_sources(
            config_files=[config_file],
            cli_args=cli_args,
        )

        # CLI args should win for temp_store
        assert settings.database_temp_store == "FILE"
        # Config file should be used for others (env vars are lower precedence)
        assert settings.database_journal_mode == "WAL"
        assert settings.database_synchronous == "NORMAL"

    def test_consistency_with_log_fields(self):
        """Test database mode fields behave consistently with log_level/log_format."""
        # Both log fields and database mode fields should normalize case
        settings = ScriptRAGSettings(
            log_level="debug",  # Normalized to uppercase
            log_format="JSON",  # Normalized to lowercase
            database_journal_mode="wal",  # Should be normalized to uppercase
            database_synchronous="normal",  # Should be normalized to uppercase
            database_temp_store="memory",  # Should be normalized to uppercase
        )

        assert settings.log_level == "DEBUG"  # Uppercase
        assert settings.log_format == "json"  # Lowercase
        assert settings.database_journal_mode == "WAL"  # Uppercase
        assert settings.database_synchronous == "NORMAL"  # Uppercase
        assert settings.database_temp_store == "MEMORY"  # Uppercase

    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is handled correctly."""
        settings = ScriptRAGSettings(
            database_journal_mode=" wal ",
            database_synchronous="  normal\t",
            database_temp_store="\nmemory\r\n",
        )

        # Whitespace should be stripped during uppercase conversion
        assert settings.database_journal_mode == "WAL"
        assert settings.database_synchronous == "NORMAL"
        assert settings.database_temp_store == "MEMORY"

    def test_edge_cases(self):
        """Test edge cases for database mode normalization."""
        # Empty strings should fail validation (not a valid option)
        with pytest.raises(ValueError, match="String should match pattern"):
            ScriptRAGSettings(database_journal_mode="")

        # None values should use defaults (not passed to validator)
        settings = ScriptRAGSettings()
        # These fields have defaults
        assert settings.database_journal_mode == "WAL"  # Default
        assert settings.database_synchronous == "NORMAL"  # Default
        assert settings.database_temp_store == "MEMORY"  # Default

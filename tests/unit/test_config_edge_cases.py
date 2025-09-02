"""Tests for config loading edge cases not covered in existing tests.

These tests specifically target error handling paths that were missing coverage
in PR #449, including permission errors, malformed configs, race conditions,
and circular references.
"""

import json
import tomllib
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError

from scriptrag.config.settings import (
    ScriptRAGSettings,
    _get_config_paths,
    clear_settings_cache,
    get_settings_for_cli,
)
from scriptrag.exceptions import ConfigurationError


@pytest.fixture(autouse=True)
def clean_state() -> Iterator[None]:
    """Ensure clean state before and after each test."""
    clear_settings_cache()
    yield
    clear_settings_cache()


class TestPermissionDeniedScenarios:
    """Test permission denied scenarios when reading config files."""

    def test_from_file_permission_denied_on_read(self, tmp_path: Path) -> None:
        """Test handling of permission denied when reading config file.

        This covers the error handling path when open() fails with PermissionError.
        """
        config_file = tmp_path / "restricted.yaml"
        config_file.write_text("app_name: test-app")

        # Mock Path.open to raise PermissionError (not builtins.open)
        with patch.object(
            Path, "open", side_effect=PermissionError("Permission denied")
        ):
            with pytest.raises(PermissionError) as exc_info:
                ScriptRAGSettings.from_file(config_file)

            assert "Permission denied" in str(exc_info.value)

    def test_from_file_permission_denied_yaml_file(self, tmp_path: Path) -> None:
        """Test permission denied specifically for YAML files."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("app_name: test")

        # Mock pathlib.Path.open to raise PermissionError
        with patch.object(
            Path, "open", side_effect=PermissionError("Cannot read file")
        ):
            with pytest.raises(PermissionError) as exc_info:
                ScriptRAGSettings.from_file(config_file)

            assert "Cannot read" in str(exc_info.value)

    def test_from_file_permission_denied_json_file(self, tmp_path: Path) -> None:
        """Test permission denied for JSON files."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"app_name": "test"}')

        with patch.object(Path, "open", side_effect=PermissionError("Access denied")):
            with pytest.raises(PermissionError) as exc_info:
                ScriptRAGSettings.from_file(config_file)

            assert "Access denied" in str(exc_info.value)

    def test_from_file_permission_denied_toml_file(self, tmp_path: Path) -> None:
        """Test permission denied for TOML files."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('app_name = "test"')

        # Mock pathlib.Path.open to raise PermissionError for binary mode
        with patch.object(
            Path, "open", side_effect=PermissionError("Cannot read binary file")
        ):
            with pytest.raises(PermissionError) as exc_info:
                ScriptRAGSettings.from_file(config_file)

            assert "Cannot read binary file" in str(exc_info.value)

    def test_get_config_paths_permission_error_on_is_file_check(
        self, tmp_path: Path
    ) -> None:
        """Test permission error during is_file() check in _get_config_paths."""
        # Create a config file
        config_file = tmp_path / "scriptrag.yaml"
        config_file.write_text("app_name: test")

        original_is_file = Path.is_file

        def mock_is_file(self: Path) -> bool:
            # Raise PermissionError for specific paths
            if "scriptrag" in str(self):
                raise PermissionError(f"Cannot check if {self} is a file")
            return original_is_file(self)

        with patch.object(Path, "is_file", mock_is_file):
            # Should handle the error and continue
            paths = _get_config_paths()
            # The file should not be in the list due to permission error
            assert config_file not in paths

    def test_get_config_paths_oserror_during_exists_check(self) -> None:
        """Test OSError handling in _get_config_paths exists() check."""
        original_exists = Path.exists

        def mock_exists(self: Path) -> bool:
            # Raise OSError for system paths
            if "/etc" in str(self) or ".config" in str(self):
                raise OSError("System error")
            return original_exists(self)

        clear_settings_cache()

        with patch.object(Path, "exists", mock_exists):
            # Should handle OSError and continue
            paths = _get_config_paths()
            # Should still return a list (possibly empty)
            assert isinstance(paths, list)


class TestMalformedConfigFiles:
    """Test malformed config files that raise parsing exceptions."""

    def test_yaml_with_invalid_syntax(self, tmp_path: Path) -> None:
        """Test YAML file with invalid syntax."""
        config_file = tmp_path / "invalid.yaml"
        # Invalid YAML: unclosed quote
        config_file.write_text('app_name: "unclosed string')

        with pytest.raises(yaml.YAMLError) as exc_info:
            ScriptRAGSettings.from_file(config_file)

        # The error should be about YAML parsing
        assert exc_info.type == yaml.scanner.ScannerError

    def test_yaml_with_duplicate_keys(self, tmp_path: Path) -> None:
        """Test YAML file with duplicate keys."""
        config_file = tmp_path / "duplicates.yaml"
        # Some YAML parsers reject duplicate keys
        config_file.write_text("""
app_name: first
app_name: second
debug: true
debug: false
""")

        # This might not raise an error (YAML takes last value),
        # but we should handle it gracefully
        settings = ScriptRAGSettings.from_file(config_file)
        # Should take the last value for duplicates
        assert settings.app_name == "second"
        assert settings.debug is False

    def test_json_with_trailing_comma(self, tmp_path: Path) -> None:
        """Test JSON file with trailing comma (invalid JSON)."""
        config_file = tmp_path / "invalid.json"
        # JSON doesn't allow trailing commas
        config_file.write_text('{"app_name": "test", "debug": true,}')

        with pytest.raises(json.JSONDecodeError):
            ScriptRAGSettings.from_file(config_file)

        # Should be a JSON decode error

    def test_json_with_single_quotes(self, tmp_path: Path) -> None:
        """Test JSON file with single quotes (invalid JSON)."""
        config_file = tmp_path / "invalid.json"
        # JSON requires double quotes
        config_file.write_text("{'app_name': 'test'}")

        with pytest.raises(json.JSONDecodeError):
            ScriptRAGSettings.from_file(config_file)

        # Should be a JSON decode error

    def test_toml_with_invalid_syntax(self, tmp_path: Path) -> None:
        """Test TOML file with invalid syntax."""
        config_file = tmp_path / "invalid.toml"
        # Invalid TOML: missing quotes around value with space
        config_file.write_text("app_name = test app")

        with pytest.raises(tomllib.TOMLDecodeError) as exc_info:
            ScriptRAGSettings.from_file(config_file)

        # Should be a TOML decode error
        assert exc_info.type == tomllib.TOMLDecodeError

    def test_toml_with_invalid_table_syntax(self, tmp_path: Path) -> None:
        """Test TOML file with invalid table syntax."""
        config_file = tmp_path / "invalid.toml"
        # Invalid TOML: unclosed table
        config_file.write_text("[section")

        with pytest.raises(tomllib.TOMLDecodeError) as exc_info:
            ScriptRAGSettings.from_file(config_file)

        assert exc_info.type == tomllib.TOMLDecodeError

    def test_config_with_invalid_data_types(self, tmp_path: Path) -> None:
        """Test config file with invalid data types for fields."""
        config_file = tmp_path / "invalid_types.yaml"
        config_data = {
            "database_timeout": "not_a_number",  # Should be float
            "debug": "not_a_boolean",  # Should be bool
            "search_vector_threshold": "ten",  # Should be int
        }

        with config_file.open("w") as f:
            yaml.dump(config_data, f)

        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings.from_file(config_file)

        # Should have validation errors for invalid types
        errors = exc_info.value.errors()
        assert any("database_timeout" in str(e) for e in errors)


class TestRaceConditions:
    """Test race conditions where config files are deleted between check and read."""

    def test_file_deleted_between_exists_and_read_yaml(self, tmp_path: Path) -> None:
        """Test YAML file deleted after exists() check but before read."""
        config_file = tmp_path / "vanishing.yaml"
        config_file.write_text("app_name: test")

        # Mock sequence: exists() returns True, then open() fails
        with patch.object(Path, "exists", return_value=True):
            with patch.object(
                Path, "open", side_effect=FileNotFoundError("File was deleted")
            ):
                with pytest.raises(FileNotFoundError) as exc_info:
                    ScriptRAGSettings.from_file(config_file)

                assert "was deleted" in str(exc_info.value)

    def test_file_deleted_between_exists_and_read_json(self, tmp_path: Path) -> None:
        """Test JSON file deleted after exists() check but before read."""
        config_file = tmp_path / "vanishing.json"

        # Simulate file existing for exists() but not for open()
        with patch.object(Path, "exists", return_value=True):
            with patch.object(
                Path, "open", side_effect=FileNotFoundError("Race condition")
            ):
                with pytest.raises(FileNotFoundError) as exc_info:
                    ScriptRAGSettings.from_file(config_file)

                assert "Race condition" in str(exc_info.value)

    def test_file_deleted_between_exists_and_read_toml(self, tmp_path: Path) -> None:
        """Test TOML file deleted after exists() check but before read."""
        config_file = tmp_path / "vanishing.toml"

        with patch.object(Path, "exists", return_value=True):
            with patch.object(
                Path, "open", side_effect=FileNotFoundError("File vanished")
            ):
                with pytest.raises(FileNotFoundError) as exc_info:
                    ScriptRAGSettings.from_file(config_file)

                # Check that the error message contains the expected text
                error_msg = str(exc_info.value)
                assert "File vanished" in error_msg or "vanishing.toml" in error_msg

    def test_file_becomes_directory_between_checks(self, tmp_path: Path) -> None:
        """Test file becomes a directory between exists() and open()."""
        config_path = tmp_path / "morphing.yaml"

        # First make it look like a file exists
        with patch.object(Path, "exists", return_value=True):
            # But when we try to open it, it's actually a directory
            with patch.object(
                Path, "open", side_effect=IsADirectoryError("It's a directory now")
            ):
                with pytest.raises(IsADirectoryError) as exc_info:
                    ScriptRAGSettings.from_file(config_path)

                assert "directory" in str(exc_info.value)

    def test_file_permissions_change_between_checks(self, tmp_path: Path) -> None:
        """Test file permissions change between exists() and open()."""
        config_file = tmp_path / "changing.yaml"
        config_file.write_text("app_name: test")

        # First read should succeed
        settings = ScriptRAGSettings.from_file(config_file)
        assert settings.app_name == "test"

        # Now mock the open to fail with permission error
        with patch.object(
            Path, "open", side_effect=PermissionError("Permissions changed")
        ):
            # Second read should fail with permission error
            with pytest.raises(PermissionError) as exc_info:
                ScriptRAGSettings.from_file(config_file)

            assert "Permissions changed" in str(exc_info.value)


class TestCircularReferences:
    """Test circular references or includes in config files."""

    def test_config_with_self_reference(self, tmp_path: Path) -> None:
        """Test config that references itself (logical circular reference)."""
        config_file = tmp_path / "circular.yaml"

        # Create a config that has a field referencing another field
        # Note: Standard YAML/TOML doesn't support includes, so we test
        # with validation that could detect circular logic
        config_data = {
            "app_name": "test",
            "database_path": "${database_path}/subdir",  # Self-reference
        }

        with config_file.open("w") as f:
            yaml.dump(config_data, f)

        # This will be treated as a literal string, not expanded
        settings = ScriptRAGSettings.from_file(config_file)
        # The path will contain the literal ${database_path}
        assert "${database_path}" in str(settings.database_path)

    def test_config_with_environment_variable_loop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config with environment variables that create a loop."""
        # Set environment variables that reference each other
        monkeypatch.setenv("TEST_VAR_A", "$TEST_VAR_B")
        monkeypatch.setenv("TEST_VAR_B", "$TEST_VAR_A")

        config_file = tmp_path / "env_loop.yaml"
        config_data = {
            "database_path": "$TEST_VAR_A/database.db",
        }

        with config_file.open("w") as f:
            yaml.dump(config_data, f)

        # The environment variable expansion happens once, not recursively
        settings = ScriptRAGSettings.from_file(config_file)
        # Will contain the unexpanded reference
        assert "$TEST_VAR_" in str(settings.database_path)

    def test_config_with_deeply_nested_references(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config with deeply nested environment variable references."""
        # Create a chain of environment variables
        monkeypatch.setenv("LEVEL1", "value1")
        monkeypatch.setenv("LEVEL2", "$LEVEL1/level2")
        monkeypatch.setenv("LEVEL3", "$LEVEL2/level3")

        config_file = tmp_path / "nested.yaml"
        config_data = {
            "database_path": "$LEVEL3/database.db",
        }

        with config_file.open("w") as f:
            yaml.dump(config_data, f)

        settings = ScriptRAGSettings.from_file(config_file)
        # Only one level of expansion happens
        path_str = str(settings.database_path)
        # Should have expanded LEVEL3 but not the nested references
        assert "$LEVEL2" in path_str or "level2" in path_str


class TestEdgeCasesInMultipleSources:
    """Test edge cases in from_multiple_sources method."""

    def test_from_multiple_sources_with_import_error_fallback(
        self, tmp_path: Path
    ) -> None:
        """Test ImportError fallback in from_multiple_sources when logger is gone."""
        config_file = tmp_path / "missing.yaml"  # Doesn't exist

        # First mock the internal logger import attempt to fail
        import_error = ImportError("No logger module")

        # Patch at the module level where it's imported
        with patch("scriptrag.config.logging.get_logger", side_effect=import_error):
            with patch("warnings.warn") as mock_warn:
                # Should fall back to warnings.warn
                settings = ScriptRAGSettings.from_multiple_sources(
                    config_files=[config_file]
                )

                # Should have warned about missing file
                mock_warn.assert_called()
                warning_msg = str(mock_warn.call_args[0][0])
                assert "not found" in warning_msg.lower()
                assert "missing.yaml" in warning_msg

    def test_from_multiple_sources_corrupted_middle_file(self, tmp_path: Path) -> None:
        """Test multiple sources with corrupted file in the middle."""
        # Create three config files
        config1 = tmp_path / "config1.yaml"
        config1.write_text("app_name: first\ndebug: true")

        config2 = tmp_path / "config2.yaml"
        config2.write_text("invalid: yaml: [syntax")  # Corrupted

        config3 = tmp_path / "config3.yaml"
        config3.write_text("app_name: third")

        # Should fail when it hits the corrupted file
        with pytest.raises(yaml.YAMLError):
            ScriptRAGSettings.from_multiple_sources(
                config_files=[config1, config2, config3]
            )

    def test_get_settings_for_cli_with_nonexistent_explicit_config(
        self, tmp_path: Path
    ) -> None:
        """Test get_settings_for_cli with explicitly specified nonexistent config."""
        nonexistent = tmp_path / "does_not_exist.yaml"

        with pytest.raises(FileNotFoundError) as exc_info:
            get_settings_for_cli(config_file=nonexistent)

        assert "Config file not found" in str(exc_info.value)
        assert str(nonexistent) in str(exc_info.value)

    def test_get_settings_for_cli_with_empty_cli_overrides(self) -> None:
        """Test get_settings_for_cli with empty dict for CLI overrides."""
        # Should work fine with empty overrides
        settings = get_settings_for_cli(cli_overrides={})
        assert isinstance(settings, ScriptRAGSettings)

    def test_get_settings_for_cli_all_none_cli_overrides(self) -> None:
        """Test get_settings_for_cli with all-None CLI overrides."""
        cli_overrides = {
            "app_name": None,
            "debug": None,
            "database_path": None,
        }

        settings = get_settings_for_cli(cli_overrides=cli_overrides)
        # None values should be filtered out, using defaults
        assert settings.app_name == "scriptrag"  # Default


class TestFileHandlingCornerCases:
    """Test corner cases in file handling."""

    def test_binary_file_mistaken_for_config(self, tmp_path: Path) -> None:
        """Test binary file mistakenly used as config."""
        binary_file = tmp_path / "binary.yaml"
        # Write binary data
        binary_file.write_bytes(b"\x00\x01\x02\x03\x04")

        with pytest.raises(yaml.YAMLError):
            ScriptRAGSettings.from_file(binary_file)

    def test_extremely_large_config_file(self, tmp_path: Path) -> None:
        """Test handling of extremely large config file."""
        large_file = tmp_path / "large.yaml"

        # Create a config with many entries
        large_config = {"app_name": "test"}
        # Add many dummy entries
        for i in range(1000):
            large_config[f"dummy_field_{i}"] = f"value_{i}"

        with large_file.open("w") as f:
            yaml.dump(large_config, f)

        # Should handle it (though ignore unknown fields)
        settings = ScriptRAGSettings.from_file(large_file)
        assert settings.app_name == "test"

    def test_config_file_with_null_bytes(self, tmp_path: Path) -> None:
        """Test config file containing null bytes."""
        config_file = tmp_path / "nulls.json"
        # Null bytes in JSON strings are not valid - they cause parse errors
        config_file.write_text('{"app_name": "test\x00with\x00nulls"}')

        # JSON cannot parse null bytes - should raise JSONDecodeError
        with pytest.raises(json.JSONDecodeError):
            ScriptRAGSettings.from_file(config_file)

    def test_symlink_to_config_file(self, tmp_path: Path) -> None:
        """Test loading config through a symlink."""
        # Create actual config file
        actual_config = tmp_path / "actual.yaml"
        actual_config.write_text("app_name: actual-app")

        # Create symlink to it
        symlink = tmp_path / "link.yaml"
        symlink.symlink_to(actual_config)

        # Should follow symlink and load config
        settings = ScriptRAGSettings.from_file(symlink)
        assert settings.app_name == "actual-app"

    def test_broken_symlink_config_file(self, tmp_path: Path) -> None:
        """Test loading config through a broken symlink."""
        # Create symlink to non-existent file
        symlink = tmp_path / "broken_link.yaml"
        symlink.symlink_to(tmp_path / "does_not_exist.yaml")

        with pytest.raises(FileNotFoundError):
            ScriptRAGSettings.from_file(symlink)


class TestErrorMessageDetails:
    """Test that error messages contain helpful details."""

    def test_unsupported_format_error_details(self, tmp_path: Path) -> None:
        """Test that unsupported format error has all expected details."""
        config_file = tmp_path / "config.xyz"
        config_file.write_text("some content")

        with pytest.raises(ConfigurationError) as exc_info:
            ScriptRAGSettings.from_file(config_file)

        error = exc_info.value
        # Check all expected fields are present
        assert error.message
        assert "Unsupported" in error.message
        assert error.hint
        assert "supported formats" in error.hint
        assert error.details
        assert "file" in error.details
        assert "detected_format" in error.details
        assert error.details["detected_format"] == ".xyz"
        assert "supported_formats" in error.details
        assert ".yaml" in error.details["supported_formats"]

    def test_config_key_validation_error_details(self, tmp_path: Path) -> None:
        """Test that config key validation provides helpful hints."""
        config_file = tmp_path / "typos.yaml"

        # Common typos that should be caught
        typo_config = {
            "db_path": "/path/to/db",  # Should be database_path
            "api_key": "test-key",  # Should be llm_api_key  # pragma: allowlist secret
        }

        with config_file.open("w") as f:
            yaml.dump(typo_config, f)

        with pytest.raises(ConfigurationError) as exc_info:
            ScriptRAGSettings.from_file(config_file)

        error = exc_info.value
        # Should provide helpful hint about the typo
        assert error.hint
        assert (
            "instead of" in error.hint
            or "Did you mean" in error.hint
            or "database_path" in error.hint
        )

"""Test expand_path validator robustness against edge cases and platform issues."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from scriptrag.config.settings import ScriptRAGSettings


class TestExpandPathRobustness:
    """Test suite for expand_path validator edge cases and error handling."""

    def test_circular_symlinks_raise_validation_error(self, tmp_path: Path) -> None:
        """Test that circular symlinks are properly caught and raise ValidationError."""
        # Create circular symlinks
        link1 = tmp_path / "link1"
        link2 = tmp_path / "link2"
        link1.symlink_to(link2)
        link2.symlink_to(link1)

        # Should raise ValidationError, not RuntimeError
        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(database_path=str(link1))

        # Check the error message mentions circular symlinks
        error_msg = str(exc_info.value)
        assert "circular symlinks" in error_msg.lower()

    def test_broken_symlink_resolves_to_target(self, tmp_path: Path) -> None:
        """Test that broken symlinks resolve to their target path."""
        # Create a broken symlink
        broken_link = tmp_path / "broken_link"
        nonexistent_target = tmp_path / "nonexistent" / "target.db"
        broken_link.symlink_to(nonexistent_target)

        # Should resolve to the target path even if it doesn't exist
        settings = ScriptRAGSettings(database_path=str(broken_link))
        assert settings.database_path == nonexistent_target

    def test_windows_path_on_unix_raises_error(self) -> None:
        """Test that Windows-style paths are rejected on Unix systems."""
        if os.name == "nt":
            pytest.skip("This test only runs on Unix systems")

        # Windows-style path with drive letter
        windows_path = "C:\\Users\\test\\database.db"

        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(database_path=windows_path)

        error_msg = str(exc_info.value)
        assert "Windows-style path not supported on Unix" in error_msg

    def test_windows_path_variations_on_unix(self) -> None:
        """Test various Windows path formats are rejected on Unix."""
        if os.name == "nt":
            pytest.skip("This test only runs on Unix systems")

        windows_paths = [
            "D:\\Program Files\\app\\data.db",
            "E:\\test.db",
            "Z:\\network\\share\\file.db",
        ]

        for win_path in windows_paths:
            with pytest.raises(ValidationError) as exc_info:
                ScriptRAGSettings(database_path=win_path)
            assert "Windows-style path not supported" in str(exc_info.value)

    def test_unix_absolute_path_on_windows_raises_error(self) -> None:
        """Test that Unix absolute paths are rejected on Windows systems."""
        if os.name != "nt":
            pytest.skip("This test only runs on Windows systems")

        # Unix-style absolute path
        unix_path = "/home/user/database.db"

        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(database_path=unix_path)

        error_msg = str(exc_info.value)
        assert "Unix-style absolute path not supported on Windows" in error_msg

    def test_unc_paths_allowed_on_windows(self) -> None:
        """Test that UNC paths are allowed on Windows."""
        if os.name != "nt":
            pytest.skip("This test only runs on Windows systems")

        # UNC path (network share)
        unc_path = "//server/share/database.db"

        # Should not raise an error
        settings = ScriptRAGSettings(database_path=unc_path)
        assert settings.database_path is not None

    def test_relative_paths_resolve_correctly(self) -> None:
        """Test that relative paths are resolved to absolute paths."""
        relative_path = "../test/database.db"
        settings = ScriptRAGSettings(database_path=relative_path)

        # Should be resolved to an absolute path
        assert settings.database_path.is_absolute()
        assert not str(settings.database_path).startswith("..")

    def test_path_with_special_characters(self, tmp_path: Path) -> None:
        """Test paths with spaces and special characters."""
        special_path = tmp_path / "path with spaces" / "db & data.db"
        special_path.parent.mkdir(exist_ok=True)

        settings = ScriptRAGSettings(database_path=str(special_path))
        assert settings.database_path == special_path

    def test_environment_variable_expansion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that environment variables in paths are expanded."""
        test_dir = str(tmp_path / "test")
        monkeypatch.setenv("TEST_DB_DIR", test_dir)

        path_with_env = "$TEST_DB_DIR/database.db"
        settings = ScriptRAGSettings(database_path=path_with_env)

        expected = Path(test_dir) / "database.db"
        assert settings.database_path == expected.resolve()

    def test_home_directory_expansion(self) -> None:
        """Test that tilde (~) expands to home directory."""
        home_path = "~/test_database.db"
        settings = ScriptRAGSettings(database_path=home_path)

        # Should expand to user's home directory
        assert str(settings.database_path).startswith(str(Path.home()))
        assert not str(settings.database_path).startswith("~")

    def test_numeric_values_converted_to_string(self) -> None:
        """Test that numeric values are converted to strings."""
        numeric_path = 12345
        settings = ScriptRAGSettings(database_path=numeric_path)

        # Should convert to string and then to Path
        assert "12345" in str(settings.database_path)

    def test_collection_types_rejected(self) -> None:
        """Test that collection types are properly rejected."""
        invalid_values = [
            ["path", "to", "database"],
            {"path": "/test/db.db"},
            {"/test/db.db"},
            ("path", "to", "db"),
        ]

        for invalid in invalid_values:
            with pytest.raises(ValidationError) as exc_info:
                ScriptRAGSettings(database_path=invalid)

            error_msg = str(exc_info.value)
            assert "cannot accept" in error_msg
            assert type(invalid).__name__ in error_msg

    def test_none_value_returns_none(self) -> None:
        """Test that None values are passed through."""
        settings = ScriptRAGSettings(log_file=None)
        assert settings.log_file is None

    def test_pathlib_path_object_accepted(self, tmp_path: Path) -> None:
        """Test that pathlib.Path objects are accepted."""
        path_obj = tmp_path / "database.db"
        settings = ScriptRAGSettings(database_path=path_obj)

        assert settings.database_path == path_obj.resolve()

    def test_multiple_symlink_levels(self, tmp_path: Path) -> None:
        """Test resolution through multiple symlink levels."""
        # Create a chain of symlinks
        final_target = tmp_path / "final.db"
        link3 = tmp_path / "link3"
        link2 = tmp_path / "link2"
        link1 = tmp_path / "link1"

        link3.symlink_to(final_target)
        link2.symlink_to(link3)
        link1.symlink_to(link2)

        settings = ScriptRAGSettings(database_path=str(link1))
        assert settings.database_path == final_target.resolve()

    def test_oserror_wrapped_in_validation_error(self, tmp_path: Path) -> None:
        """Test that OSError during resolution is wrapped in ValidationError."""
        if os.name == "nt":
            pytest.skip("Test designed for Unix permission errors")

        # Create a directory with no read permissions
        no_access = tmp_path / "no_access"
        no_access.mkdir()
        no_access.chmod(0o000)

        try:
            # Try to access a file inside the restricted directory
            restricted_path = no_access / "subdir" / "database.db"

            # This might raise different errors on different systems
            # The key is that any OSError should be wrapped
            try:
                settings = ScriptRAGSettings(database_path=str(restricted_path))
                # If it succeeds (some systems), check the path
                assert settings.database_path is not None
            except ValidationError as e:
                # Should wrap the OSError
                assert "Path resolution failed" in str(e)
        finally:
            # Restore permissions for cleanup
            no_access.chmod(0o755)

    def test_empty_string_path(self) -> None:
        """Test that empty string paths are handled."""
        settings = ScriptRAGSettings(database_path="")

        # Empty string becomes current directory
        assert settings.database_path == Path.cwd()

    def test_single_dot_path(self) -> None:
        """Test that single dot path resolves to current directory."""
        settings = ScriptRAGSettings(database_path=".")
        assert settings.database_path == Path.cwd()

    def test_double_dot_path(self) -> None:
        """Test that double dot path resolves to parent directory."""
        settings = ScriptRAGSettings(database_path="..")
        assert settings.database_path == Path.cwd().parent.resolve()

    def test_log_file_validator_same_behavior(self, tmp_path: Path) -> None:
        """Test that log_file field has same validation behavior."""
        # Test with circular symlink
        link1 = tmp_path / "log_link1"
        link2 = tmp_path / "log_link2"
        link1.symlink_to(link2)
        link2.symlink_to(link1)

        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(log_file=str(link1))

        assert "circular symlinks" in str(exc_info.value).lower()

    def test_cross_platform_path_single_char(self) -> None:
        """Test single character paths don't trigger cross-platform check."""
        # Single character paths like "a" shouldn't be mistaken for drive letters
        settings = ScriptRAGSettings(database_path="a")
        # Should resolve to current directory / "a"
        assert settings.database_path == (Path.cwd() / "a").resolve()

    def test_network_share_paths_unix(self) -> None:
        """Test that network share paths starting with // are handled correctly."""
        if os.name == "nt":
            pytest.skip("This test is for Unix systems")

        network_path = "//server/share/database.db"
        # On Unix, this is just a path starting with two slashes
        settings = ScriptRAGSettings(database_path=network_path)
        assert settings.database_path is not None

    def test_validation_error_chain_preserved(self) -> None:
        """Test that the original exception is preserved in the chain."""
        if os.name == "nt":
            pytest.skip("This test only runs on Unix systems")

        windows_path = "C:\\test\\db.db"

        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(database_path=windows_path)

        # Check that we have a proper error chain
        validation_error = exc_info.value
        assert len(validation_error.errors()) > 0
        error_dict = validation_error.errors()[0]
        assert error_dict["loc"] == ("database_path",)
        assert "Windows-style path" in error_dict["msg"]

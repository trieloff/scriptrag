"""Extended tests for file validators to improve coverage."""

from pathlib import Path
from unittest.mock import patch

import pytest

from scriptrag.cli.validators.base import ValidationError
from scriptrag.cli.validators.file_validator import (
    ConfigFileValidator,
    DirectoryValidator,
    FileValidator,
)


class TestFileValidatorExtended:
    """Extended tests for FileValidator coverage."""

    def test_validate_with_path_object(self, tmp_path):
        """Test validation with Path object instead of string."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        validator = FileValidator(must_exist=True)
        result = validator.validate(test_file)  # Pass Path object directly
        assert result == test_file.expanduser().resolve()

    def test_file_not_required_to_exist(self, tmp_path):
        """Test when file is not required to exist."""
        validator = FileValidator(must_exist=False)

        nonexistent = tmp_path / "nonexistent.txt"
        result = validator.validate(str(nonexistent))
        assert result == nonexistent

    def test_file_not_required_to_be_file(self, tmp_path):
        """Test when path is not required to be a file."""
        validator = FileValidator(must_be_file=False)

        # Directory should be accepted
        result = validator.validate(str(tmp_path))
        assert result == tmp_path

    def test_case_insensitive_extension_check(self, tmp_path):
        """Test case-insensitive extension validation."""
        test_file = tmp_path / "test.TXT"  # Uppercase extension
        test_file.write_text("content")

        validator = FileValidator(extensions=[".txt"])
        result = validator.validate(str(test_file))
        assert result == test_file

    def test_expanduser_in_path(self):
        """Test that ~ is expanded in paths."""
        validator = FileValidator(must_exist=False)

        with patch("pathlib.Path.expanduser") as mock_expand:
            mock_expand.return_value = Path("/home/user/file.txt")
            mock_expand.return_value.resolve.return_value = Path("/home/user/file.txt")

            result = validator.validate("~/file.txt")
            mock_expand.assert_called_once()


class TestDirectoryValidatorExtended:
    """Extended tests for DirectoryValidator coverage."""

    def test_validate_with_path_object(self, tmp_path):
        """Test validation with Path object instead of string."""
        validator = DirectoryValidator(must_exist=True)
        result = validator.validate(tmp_path)  # Pass Path object directly
        assert result == tmp_path.expanduser().resolve()

    def test_directory_not_required_to_exist(self, tmp_path):
        """Test when directory is not required to exist."""
        validator = DirectoryValidator(must_exist=False, create_if_missing=False)

        nonexistent = tmp_path / "nonexistent"
        result = validator.validate(str(nonexistent))
        assert result == nonexistent

    def test_create_directory_permission_error(self, tmp_path):
        """Test handling permission error when creating directory."""
        new_dir = tmp_path / "new_dir"
        validator = DirectoryValidator(create_if_missing=True)

        with patch("pathlib.Path.mkdir") as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")

            with pytest.raises(ValidationError, match="Failed to create directory"):
                validator.validate(str(new_dir))

    def test_writable_directory_check(self, tmp_path):
        """Test checking if directory is writable."""
        validator = DirectoryValidator(must_be_writable=True)

        # Normal case - writable directory
        result = validator.validate(str(tmp_path))
        assert result == tmp_path

    def test_non_writable_directory(self, tmp_path):
        """Test non-writable directory detection."""
        validator = DirectoryValidator(must_be_writable=True)

        with patch("pathlib.Path.touch") as mock_touch:
            mock_touch.side_effect = PermissionError("Cannot write")

            with pytest.raises(ValidationError, match="not writable"):
                validator.validate(str(tmp_path))

    def test_writable_check_cleanup(self, tmp_path):
        """Test that writable check cleans up test file."""
        validator = DirectoryValidator(must_be_writable=True)

        # Mock the test file operations
        test_file = tmp_path / ".write_test"

        with patch.object(Path, "touch") as mock_touch:
            with patch.object(Path, "unlink") as mock_unlink:
                validator.validate(str(tmp_path))

                # Verify cleanup was attempted
                mock_touch.assert_called_once()
                mock_unlink.assert_called_once()

    def test_create_nested_directories(self, tmp_path):
        """Test creating nested directories with parents."""
        nested_dir = tmp_path / "level1" / "level2" / "level3"
        validator = DirectoryValidator(create_if_missing=True)

        result = validator.validate(str(nested_dir))
        assert result == nested_dir
        assert nested_dir.exists()
        assert nested_dir.is_dir()

    def test_expanduser_in_directory_path(self):
        """Test that ~ is expanded in directory paths."""
        validator = DirectoryValidator(must_exist=False)

        with patch("pathlib.Path.expanduser") as mock_expand:
            mock_expand.return_value = Path("/home/user/dir")
            mock_expand.return_value.resolve.return_value = Path("/home/user/dir")

            result = validator.validate("~/dir")
            mock_expand.assert_called_once()


class TestConfigFileValidatorExtended:
    """Extended tests for ConfigFileValidator."""

    def test_inheritance_from_file_validator(self):
        """Test that ConfigFileValidator inherits from FileValidator."""
        validator = ConfigFileValidator()

        assert isinstance(validator, FileValidator)
        assert validator.must_exist is True
        assert validator.must_be_file is True
        assert validator.extensions == [".yaml", ".yml", ".json", ".toml"]

    def test_config_file_not_exists(self):
        """Test config file that doesn't exist."""
        validator = ConfigFileValidator()

        with pytest.raises(ValidationError, match="does not exist"):
            validator.validate("/nonexistent/config.yaml")

    def test_config_file_wrong_extension(self, tmp_path):
        """Test config file with wrong extension."""
        wrong_file = tmp_path / "config.ini"
        wrong_file.write_text("[section]\nkey = value")

        validator = ConfigFileValidator()

        with pytest.raises(ValidationError, match="Invalid file extension"):
            validator.validate(str(wrong_file))

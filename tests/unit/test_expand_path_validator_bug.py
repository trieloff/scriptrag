"""Test for expand_path validator edge cases and bug fixes."""

import pytest
from pydantic import ValidationError

from scriptrag.config.settings import ScriptRAGSettings


class TestExpandPathValidatorBug:
    """Test cases for expand_path validator bug with invalid input types."""

    def test_expand_path_with_dict_raises_error(self):
        """Test that passing a dict to database_path raises a proper error.

        This tests the bug where expand_path validator's fallback
        `return Path(v)` could fail with an unclear error message
        when given invalid types like dict.
        """
        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(database_path={"path": "/some/path"})

        # The error should be clear about the invalid type
        error_str = str(exc_info.value)
        # Should contain information about the type error
        assert "dict" in error_str.lower() or "path fields" in error_str.lower()

    def test_expand_path_with_list_raises_error(self):
        """Test that passing a list to database_path raises a proper error.

        Tests the validator's handling of list input which should fail
        with a clear error message.
        """
        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(database_path=["/path1", "/path2"])

        error_str = str(exc_info.value)
        assert "list" in error_str.lower() or "path fields" in error_str.lower()

    def test_expand_path_with_int_converts_to_path(self):
        """Test that passing an int to database_path converts it to Path.

        This tests the fallback behavior where numeric values are
        converted to Path objects (e.g., Path(123) -> "123").
        """
        # Integers should be converted to string paths
        settings = ScriptRAGSettings(database_path=123)
        assert str(settings.database_path).endswith("123")

    def test_expand_path_with_float_converts_to_path(self):
        """Test that passing a float to database_path converts it to Path.

        Tests numeric type conversion in the validator.
        """
        settings = ScriptRAGSettings(database_path=456.789)
        assert "456.789" in str(settings.database_path)

    def test_log_file_with_dict_raises_error(self):
        """Test that passing a dict to log_file raises a proper error.

        Verifies the validator works for all path fields, not just database_path.
        """
        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(log_file={"file": "/logs/app.log"})

        error_str = str(exc_info.value)
        assert "dict" in error_str.lower() or "path fields" in error_str.lower()

    def test_expand_path_with_boolean_converts_to_path(self):
        """Test that passing a boolean to database_path converts it to Path.

        Edge case where boolean True/False becomes path "True"/"False".
        """
        settings = ScriptRAGSettings(database_path=True)
        assert str(settings.database_path).endswith("True")

        settings = ScriptRAGSettings(database_path=False)
        assert str(settings.database_path).endswith("False")

    def test_expand_path_with_bytes_converts_to_path(self):
        """Test that passing bytes to database_path converts to string then Path.

        Bytes can be converted to string and then to Path.
        """
        # bytes will be converted to their string representation
        settings = ScriptRAGSettings(database_path=b"/some/bytes/path")
        # The bytes object gets converted to string like "b'/some/bytes/path'"
        path_str = str(settings.database_path)
        assert "b'" in path_str or "/some/bytes/path" in path_str

    def test_expand_path_with_custom_object_with_str(self):
        """Test that passing a custom object with __str__ method works.

        Tests with a custom object that has a string representation.
        """

        class CustomObject:
            """Object that can be converted to a path via __str__."""

            def __str__(self):
                return "/custom/object/path"

        settings = ScriptRAGSettings(database_path=CustomObject())
        assert str(settings.database_path).endswith("custom/object/path")

    def test_expand_path_with_tuple_raises_error(self):
        """Test that passing a tuple to database_path raises a proper error.

        Tuples should be explicitly rejected as they are collection types.
        """
        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(database_path=("/path1", "/path2"))

        error_str = str(exc_info.value)
        assert "tuple" in error_str.lower() or "path fields" in error_str.lower()

    def test_expand_path_with_set_raises_error(self):
        """Test that passing a set to database_path raises a proper error.

        Sets should be explicitly rejected as they are collection types.
        """
        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(database_path={"/path1", "/path2"})

        error_str = str(exc_info.value)
        assert "set" in error_str.lower() or "path fields" in error_str.lower()

    def test_expand_path_preserves_none_for_optional_fields(self):
        """Test that None values are preserved for optional fields.

        The validator should handle None correctly for optional fields.
        """
        settings = ScriptRAGSettings(log_file=None)
        assert settings.log_file is None

        # database_path is not optional, so it should have a default
        settings = ScriptRAGSettings()
        assert settings.database_path is not None
        assert str(settings.database_path).endswith("scriptrag.db")

    def test_expand_path_with_object_str_raises_error(self):
        """Test that an object whose __str__ raises an error is properly handled.

        This tests the exception handler in the validator.
        """

        class BadObject:
            """Object that raises error when converting to string."""

            def __str__(self):
                raise TypeError("Cannot convert to string")

        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(database_path=BadObject())

        error_str = str(exc_info.value)
        # Should contain information about the error
        assert "BadObject" in error_str or "path" in error_str.lower()

    def test_expand_path_with_null_byte_in_string(self):
        """Test that strings with null bytes are properly rejected.

        Path objects cannot contain null bytes, so this should fail.
        """
        with pytest.raises(ValidationError) as exc_info:
            ScriptRAGSettings(database_path="/path/with\x00null/byte")

        error_str = str(exc_info.value)
        # Should contain information about the error
        assert "null" in error_str.lower() or "path" in error_str.lower()

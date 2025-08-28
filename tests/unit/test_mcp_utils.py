"""Comprehensive unit tests for MCP utils."""

from unittest.mock import MagicMock, patch

import pytest

from scriptrag.mcp.utils import format_error, format_success, get_api_settings


class TestGetApiSettings:
    """Test the get_api_settings function."""

    @patch("scriptrag.mcp.utils.get_settings")
    def test_get_api_settings_returns_settings(self, mock_get_settings):
        """Test that get_api_settings returns configuration settings."""
        # Arrange
        mock_settings = MagicMock()  # Remove spec to prevent mock file artifacts
        mock_settings.database_journal_mode = "WAL"
        mock_settings.database_synchronous = "NORMAL"
        mock_settings.database_foreign_keys = True
        mock_get_settings.return_value = mock_settings

        # Act
        result = get_api_settings()

        # Assert
        assert result == mock_settings
        mock_get_settings.assert_called_once()

    @patch("scriptrag.mcp.utils.get_settings")
    def test_get_api_settings_passes_through_exception(self, mock_get_settings):
        """Test that get_api_settings propagates exceptions from get_settings."""
        # Arrange
        mock_get_settings.side_effect = RuntimeError("Config error")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Config error"):
            get_api_settings()


class TestFormatError:
    """Test the format_error function."""

    def test_format_error_with_value_error(self):
        """Test format_error with ValueError exception."""
        # Arrange
        error = ValueError("Test error message")

        # Act
        result = format_error(error)

        # Assert
        expected = {
            "success": False,
            "error": "Test error message",
            "error_type": "ValueError",
        }
        assert result == expected

    def test_format_error_with_runtime_error(self):
        """Test format_error with RuntimeError exception."""
        # Arrange
        error = RuntimeError("Runtime failure")

        # Act
        result = format_error(error)

        # Assert
        expected = {
            "success": False,
            "error": "Runtime failure",
            "error_type": "RuntimeError",
        }
        assert result == expected

    def test_format_error_with_custom_exception(self):
        """Test format_error with custom exception class."""

        # Arrange
        class CustomError(Exception):
            pass

        error = CustomError("Custom error")

        # Act
        result = format_error(error)

        # Assert
        expected = {
            "success": False,
            "error": "Custom error",
            "error_type": "CustomError",
        }
        assert result == expected

    def test_format_error_with_empty_message(self):
        """Test format_error with exception with empty message."""
        # Arrange
        error = ValueError("")

        # Act
        result = format_error(error)

        # Assert
        assert result["success"] is False
        assert result["error"] == ""
        assert result["error_type"] == "ValueError"

    def test_format_error_with_none_message(self):
        """Test format_error with exception that has None as message."""
        # Arrange
        error = Exception()

        # Act
        result = format_error(error)

        # Assert
        assert result["success"] is False
        assert result["error"] == ""
        assert result["error_type"] == "Exception"

    def test_format_error_preserves_unicode(self):
        """Test format_error preserves unicode characters in error message."""
        # Arrange
        error = ValueError("Unicode test: π ∞ 中文")

        # Act
        result = format_error(error)

        # Assert
        assert result["error"] == "Unicode test: π ∞ 中文"
        assert result["success"] is False
        assert result["error_type"] == "ValueError"


class TestFormatSuccess:
    """Test the format_success function."""

    def test_format_success_with_simple_data(self):
        """Test format_success with simple data."""
        # Arrange
        data = {"result": "test value"}

        # Act
        result = format_success(data)

        # Assert
        expected = {
            "success": True,
            "data": {"result": "test value"},
        }
        assert result == expected

    def test_format_success_with_list_data(self):
        """Test format_success with list data."""
        # Arrange
        data = ["item1", "item2", "item3"]

        # Act
        result = format_success(data)

        # Assert
        expected = {
            "success": True,
            "data": ["item1", "item2", "item3"],
        }
        assert result == expected

    def test_format_success_with_none_data(self):
        """Test format_success with None as data."""
        # Arrange
        data = None

        # Act
        result = format_success(data)

        # Assert
        expected = {
            "success": True,
            "data": None,
        }
        assert result == expected

    def test_format_success_with_metadata(self):
        """Test format_success with additional metadata."""
        # Arrange
        data = {"query": "test"}

        # Act
        result = format_success(data, total_count=10, execution_time=123.45)

        # Assert
        expected = {
            "success": True,
            "data": {"query": "test"},
            "total_count": 10,
            "execution_time": 123.45,
        }
        assert result == expected

    def test_format_success_with_empty_metadata(self):
        """Test format_success with empty metadata kwargs."""
        # Arrange
        data = {"test": "data"}

        # Act
        result = format_success(data, **{})

        # Assert
        expected = {
            "success": True,
            "data": {"test": "data"},
        }
        assert result == expected

    def test_format_success_metadata_can_override_success(self):
        """Test that metadata can override the success field."""
        # Arrange
        data = {"test": "data"}

        # Act
        result = format_success(data, success=False)

        # Assert - success can be overridden by metadata
        assert result["success"] is False
        assert result["data"] == {"test": "data"}

    def test_format_success_cannot_override_data_parameter(self):
        """Test that metadata cannot override the data positional parameter."""
        # Arrange
        data = {"original": "data"}

        # Act & Assert - Should raise TypeError due to multiple values for 'data'
        with pytest.raises(TypeError, match="got multiple values for argument 'data'"):
            format_success(data, data={"overridden": "data"})

    def test_format_success_with_complex_nested_data(self):
        """Test format_success with complex nested data structures."""
        # Arrange
        data = {
            "results": [
                {"id": 1, "name": "Test 1", "metadata": {"score": 0.95}},
                {"id": 2, "name": "Test 2", "metadata": {"score": 0.87}},
            ],
            "pagination": {"page": 1, "limit": 10, "total": 2},
        }

        # Act
        result = format_success(data, query_time_ms=45.2, cache_hit=True)

        # Assert
        assert result["success"] is True
        assert result["data"] == data
        assert result["query_time_ms"] == 45.2
        assert result["cache_hit"] is True

    @pytest.mark.parametrize(
        "data,metadata,expected_keys",
        [
            # Simple cases
            ("string_data", {}, {"success", "data"}),
            (123, {"count": 5}, {"success", "data", "count"}),
            # Complex cases
            (
                [{"id": 1}],
                {"total": 1, "page": 1, "limit": 10},
                {"success", "data", "total", "page", "limit"},
            ),
            # Edge cases
            (None, {"message": "empty"}, {"success", "data", "message"}),
            ({}, {"timestamp": "2024-01-01"}, {"success", "data", "timestamp"}),
        ],
    )
    def test_format_success_parametrized(self, data, metadata, expected_keys):
        """Test format_success with various data and metadata combinations."""
        # Act
        result = format_success(data, **metadata)

        # Assert
        assert set(result.keys()) == expected_keys
        assert result["success"] is True
        assert result["data"] == data
        # Check that all metadata was included
        for key, value in metadata.items():
            if key != "data":  # data might be overridden
                assert result[key] == value

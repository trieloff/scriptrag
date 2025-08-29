"""
Demonstration of mock file detection capabilities.

This file shows examples of tests that create mock file artifacts
and how the detection system identifies them.
"""

import contextlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestMockFileDetectionDemo:
    """Demonstrate mock file detection."""

    def test_good_mock_usage(self, tmp_path):
        """Example of proper mock usage that doesn't create artifacts."""
        # Good: Use temporary directory for file operations
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        assert test_file.exists()
        # Clean up
        test_file.unlink()

    def test_bad_mock_as_path(self):
        """Example of bad usage: MagicMock used as file path.

        This test intentionally creates a mock file artifact to demonstrate
        the detection system. In real code, this should be fixed!
        """
        # Bad: MagicMock object used as path
        mock_path = MagicMock()
        mock_path.__str__.return_value = "<MagicMock name='bad_path' id='123'>"

        # This creates a file with the mock's string representation as the name
        with contextlib.suppress(BaseException):
            Path(str(mock_path)).write_text("bad content")

    def test_another_bad_example(self):
        """Another example that creates mock artifacts."""
        # Bad: Mock without proper spec
        mock_file = MagicMock()
        mock_file.name = "MockFile_name='test'"

        # This might create a file with mock patterns in the name
        with contextlib.suppress(BaseException):
            test_path = Path(f"test_{mock_file.name}.txt")
            test_path.write_text("test")

    @pytest.mark.allow_mock_files
    def test_allowed_mock_files(self):
        """Test that's allowed to create mock-like files.

        This demonstrates the @pytest.mark.allow_mock_files decorator
        which allows specific tests to create files with mock-like names.
        """
        # This test is marked as allowed to create mock files
        test_file = Path("allowed_Mock_name=test.txt")
        test_file.write_text("allowed content")
        # Clean up
        test_file.unlink()

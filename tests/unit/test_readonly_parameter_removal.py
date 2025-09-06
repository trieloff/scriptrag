"""Test for the readonly module parameter removal refactoring.

This test ensures that the _is_temp_directory function works correctly
after removing the unused path_parts parameter.
"""

import pytest

from scriptrag.database.readonly import _is_temp_directory


@pytest.mark.unit
def test_is_temp_directory_no_longer_accepts_path_parts():
    """Verify that _is_temp_directory only takes one parameter now."""
    import inspect

    sig = inspect.signature(_is_temp_directory)
    params = list(sig.parameters.keys())

    # Should only have one parameter: db_path_str
    assert len(params) == 1
    assert params[0] == "db_path_str"


@pytest.mark.unit
def test_is_temp_directory_correct_return_type():
    """Verify that _is_temp_directory returns a bool."""
    result = _is_temp_directory("/tmp/test.db")
    assert isinstance(result, bool)


@pytest.mark.unit
def test_is_temp_directory_handles_complex_paths():
    """Test that complex path scenarios work correctly."""
    # Test paths with multiple temp indicators
    assert _is_temp_directory("/var/tmp/pytest/test.db") is True
    assert _is_temp_directory("/home/user/.pytest_cache/temp/test.db") is True

    # Test CI paths with additional segments
    assert _is_temp_directory("/home/runner/work/repo/branch/test.db") is True
    assert _is_temp_directory("/github/workspace/build/output/test.db") is True

    # Test non-temp paths that might look similar
    assert _is_temp_directory("/home/runner-work/test.db") is False
    assert _is_temp_directory("/var/lib/runner/work/test.db") is False


@pytest.mark.unit
def test_is_temp_directory_case_sensitivity():
    """Test case-sensitive behavior of temp detection."""
    # Lowercase temp indicators should work
    assert _is_temp_directory("/path/temp/test.db") is True
    assert _is_temp_directory("/path/tmp/test.db") is True
    assert _is_temp_directory("/path/pytest/test.db") is True

    # Mixed case should work (path_lower is used)
    assert _is_temp_directory("/path/TEMP/test.db") is True
    assert _is_temp_directory("/path/TMP/test.db") is True
    assert _is_temp_directory("/path/PYTEST/test.db") is True


@pytest.mark.unit
def test_is_temp_directory_windows_temp_paths():
    """Test Windows-style temp paths (if applicable)."""
    # These tests assume the function handles Windows paths
    # The function uses path_lower for checking
    paths_to_test = [
        ("C:\\Temp\\test.db", True),
        ("C:\\Users\\user\\AppData\\Local\\Temp\\test.db", True),
        ("D:\\tmp\\project\\test.db", True),
        ("C:\\Program Files\\app\\test.db", False),
    ]

    for path, _expected in paths_to_test:
        # Convert backslashes for cross-platform testing
        unix_path = path.replace("\\", "/").lower()
        if "temp" in unix_path or "tmp" in unix_path:
            assert _is_temp_directory(path) is True
        else:
            assert _is_temp_directory(path) is False


@pytest.mark.unit
def test_is_temp_directory_edge_cases():
    """Test edge cases and boundary conditions."""
    # Empty-like paths (shouldn't happen but good to test)
    assert _is_temp_directory("") is False
    assert _is_temp_directory("/") is False

    # Paths with special characters
    assert _is_temp_directory("/tmp/test-file.db") is True
    assert _is_temp_directory("/tmp/test_file.db") is True
    assert _is_temp_directory("/tmp/test file.db") is True

    # Very long paths
    long_temp_path = "/tmp/" + "a" * 200 + "/test.db"
    assert _is_temp_directory(long_temp_path) is True

    long_non_temp_path = "/var/lib/" + "b" * 200 + "/test.db"
    assert _is_temp_directory(long_non_temp_path) is False


@pytest.mark.unit
def test_is_temp_directory_performance():
    """Ensure the function performs efficiently without the unused parameter."""
    import time

    # Test that function executes quickly
    paths = [
        "/tmp/test.db",
        "/var/lib/test.db",
        "/home/runner/work/test.db",
        "/private/var/folders/xy/test.db",
    ] * 100  # Test 400 paths

    start_time = time.time()
    for path in paths:
        _is_temp_directory(path)
    elapsed_time = time.time() - start_time

    # Should process 400 paths in less than 0.1 seconds
    assert elapsed_time < 0.1, f"Function too slow: {elapsed_time:.3f} seconds"

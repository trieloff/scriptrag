"""Tests for progress callback functionality in ScriptRAG API."""

from unittest.mock import MagicMock

import pytest

from scriptrag import ScriptRAG
from scriptrag.config import ScriptRAGSettings


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def scriptrag(temp_db_path):
    """Create a ScriptRAG instance with test settings."""
    settings = ScriptRAGSettings(
        database_path=temp_db_path,
        skip_boneyard_filter=True,  # Allow indexing test files without metadata
    )
    return ScriptRAG(settings=settings, auto_init_db=True)


@pytest.fixture
def sample_fountain(tmp_path):
    """Create a sample Fountain file for testing."""
    fountain_file = tmp_path / "test_script.fountain"
    fountain_file.write_text(
        """Title: Test Script
Author: Test Author

INT. COFFEE SHOP - DAY

SARAH enters the bustling coffee shop.

SARAH
(to barista)
One large coffee, please.

The BARISTA smiles and starts preparing the order.

BARISTA
Coming right up!
"""
    )
    return fountain_file


class TestProgressCallbacks:
    """Test progress callback functionality."""

    def test_index_script_with_progress_callback(self, scriptrag, sample_fountain):
        """Test that index_script calls progress callback correctly."""
        # Create a mock callback
        progress_callback = MagicMock()

        # Index with progress callback
        result = scriptrag.index_script(
            sample_fountain, progress_callback=progress_callback
        )

        # Verify indexing succeeded
        assert result["indexed"] is True
        assert result["scenes_indexed"] > 0

        # Verify callback was called
        assert progress_callback.call_count == 2  # Start and end

        # Check first call (starting)
        first_call = progress_callback.call_args_list[0]
        assert first_call[0][0] == 0  # current
        assert first_call[0][1] == 1  # total
        assert "Indexing" in first_call[0][2]  # message
        assert sample_fountain.name in first_call[0][2]

        # Check second call (completed)
        second_call = progress_callback.call_args_list[1]
        assert second_call[0][0] == 1  # current
        assert second_call[0][1] == 1  # total
        assert "Completed" in second_call[0][2]  # message
        assert "indexed" in second_call[0][2].lower()

    def test_index_script_dry_run_with_progress(self, scriptrag, sample_fountain):
        """Test progress callback during dry run."""
        progress_callback = MagicMock()

        # Dry run with progress callback
        result = scriptrag.index_script(
            sample_fountain, dry_run=True, progress_callback=progress_callback
        )

        # Verify dry run result
        assert result["indexed"] is False  # Dry run doesn't actually index
        assert result["scenes_indexed"] > 0  # But still counts scenes

        # Verify callback was called
        assert progress_callback.call_count == 2

    def test_index_directory_with_progress_callback(self, scriptrag, tmp_path):
        """Test that index_directory calls progress callback correctly."""
        # Create multiple Fountain files
        for i in range(3):
            fountain_file = tmp_path / f"script_{i}.fountain"
            fountain_file.write_text(
                f"""Title: Script {i}

INT. LOCATION {i} - DAY

Action happens here.
"""
            )

        # Create a mock callback
        progress_callback = MagicMock()

        # Index directory with progress callback
        result = scriptrag.index_directory(
            tmp_path, recursive=False, progress_callback=progress_callback
        )

        # Verify indexing succeeded
        assert result["total_scripts_indexed"] == 3

        # Verify callback was called
        # Should be called: 1 for discovery + 3 for each script
        assert progress_callback.call_count >= 4

        # Check discovery call
        discovery_call = progress_callback.call_args_list[0]
        assert "Discovering" in discovery_call[0][2]

        # Check that scripts were reported
        script_calls = [
            call
            for call in progress_callback.call_args_list
            if "Processed" in call[0][2]
        ]
        assert len(script_calls) == 3

        # Verify progress numbers
        for i, call in enumerate(script_calls, 1):
            assert call[0][0] == i  # current should increment
            assert call[0][1] == 3  # total should be 3

    def test_index_directory_recursive_with_progress(self, scriptrag, tmp_path):
        """Test progress callback with recursive directory indexing."""
        # Create nested structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Create files in both directories
        for dir_path in [tmp_path, subdir]:
            fountain_file = dir_path / "script.fountain"
            fountain_file.write_text(
                """Title: Test Script

INT. ROOM - DAY

Action.
"""
            )

        progress_callback = MagicMock()

        # Index recursively with progress callback
        result = scriptrag.index_directory(
            tmp_path, recursive=True, progress_callback=progress_callback
        )

        # Verify both scripts were indexed
        assert result["total_scripts_indexed"] == 2

        # Verify progress was reported for both
        script_calls = [
            call
            for call in progress_callback.call_args_list
            if "Processed" in call[0][2]
        ]
        assert len(script_calls) == 2

    def test_progress_callback_with_invalid_script(self, scriptrag, tmp_path):
        """Test progress callback when processing invalid Fountain content."""
        # Create an invalid Fountain file
        invalid_file = tmp_path / "invalid.fountain"
        invalid_file.write_text("This is not valid Fountain content")

        # Create a valid file
        valid_file = tmp_path / "valid.fountain"
        valid_file.write_text(
            """Title: Valid Script

INT. ROOM - DAY

Action.
"""
        )

        progress_callback = MagicMock()

        # Index directory with mixed results
        result = scriptrag.index_directory(
            tmp_path, progress_callback=progress_callback
        )

        # Check that both files were processed
        script_calls = [
            call
            for call in progress_callback.call_args_list
            if "Processed" in call[0][2]
        ]
        assert len(script_calls) == 2

        # Both should be indexed (invalid content creates empty script)
        statuses = [call[0][2] for call in script_calls]
        assert all("indexed" in s for s in statuses)

    def test_progress_callback_signature(self, scriptrag, sample_fountain):
        """Test that progress callback receives correct argument types."""
        received_args = []

        def capture_args(current, total, message):
            received_args.append((current, total, message))

        # Index with capturing callback
        scriptrag.index_script(sample_fountain, progress_callback=capture_args)

        # Verify argument types
        for current, total, message in received_args:
            assert isinstance(current, int)
            assert isinstance(total, int)
            assert isinstance(message, str)
            assert current >= 0
            assert total >= 0
            assert current <= total

    def test_no_callback_works_normally(self, scriptrag, sample_fountain):
        """Test that operations work normally without callbacks."""
        # Index without callback (default behavior)
        result = scriptrag.index_script(sample_fountain)
        assert result["indexed"] is True

        # Index directory without callback
        result = scriptrag.index_directory(sample_fountain.parent)
        assert result["total_scripts_indexed"] >= 1

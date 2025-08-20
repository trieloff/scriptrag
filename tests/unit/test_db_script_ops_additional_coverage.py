"""Additional tests for db_script_ops.py to improve coverage."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest

from scriptrag.api.db_script_ops import ScriptOperations, ScriptRecord
from scriptrag.exceptions import DatabaseError
from scriptrag.parser import Script


@pytest.fixture
def mock_connection() -> sqlite3.Connection:
    """Create a mock database connection."""
    return Mock(spec=sqlite3.Connection)


@pytest.fixture
def script_ops() -> ScriptOperations:
    """Create ScriptOperations instance."""
    return ScriptOperations()


@pytest.fixture
def sample_script() -> Mock:
    """Create a sample script for testing."""
    script = Mock()
    script.title = "Test Script"
    script.author = "Test Author"
    script.metadata = {
        "project_title": "Test Project",
        "series_title": "Test Series",
        "season": 1,
        "episode": 5,
        "custom_field": "custom_value",
    }
    return script


class TestScriptRecord:
    """Test ScriptRecord dataclass."""

    def test_script_record_creation(self) -> None:
        """Test creating a ScriptRecord."""
        record = ScriptRecord(
            id=1,
            title="Test Script",
            author="Test Author",
            file_path="/path/to/script.fountain",
            metadata={"test": "data"},
        )
        assert record.id == 1
        assert record.title == "Test Script"
        assert record.author == "Test Author"
        assert record.file_path == "/path/to/script.fountain"
        assert record.metadata == {"test": "data"}

    def test_script_record_defaults(self) -> None:
        """Test ScriptRecord with default values."""
        record = ScriptRecord()
        assert record.id is None
        assert record.title is None
        assert record.author is None
        assert record.file_path is None
        assert record.metadata is None


class TestScriptOperationsGetExistingScript:
    """Test get_existing_script method."""

    def test_get_existing_script_found(
        self, script_ops: ScriptOperations, mock_connection: sqlite3.Connection
    ) -> None:
        """Test getting existing script when found."""
        # Mock cursor and row data
        mock_cursor = Mock()
        mock_row = {
            "id": 1,
            "title": "Test Script",
            "author": "Test Author",
            "file_path": "/path/to/script.fountain",
            "metadata": '{"test": "data"}',
        }
        mock_cursor.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_cursor

        file_path = Path("/path/to/script.fountain")
        result = script_ops.get_existing_script(mock_connection, file_path)

        assert result is not None
        assert result.id == 1
        assert result.title == "Test Script"
        assert result.author == "Test Author"
        assert result.file_path == "/path/to/script.fountain"
        assert result.metadata == {"test": "data"}

    def test_get_existing_script_not_found(
        self, script_ops: ScriptOperations, mock_connection: sqlite3.Connection
    ) -> None:
        """Test getting existing script when not found."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_connection.execute.return_value = mock_cursor

        file_path = Path("/path/to/script.fountain")
        result = script_ops.get_existing_script(mock_connection, file_path)

        assert result is None

    def test_get_existing_script_null_metadata(
        self, script_ops: ScriptOperations, mock_connection: sqlite3.Connection
    ) -> None:
        """Test getting existing script with null metadata."""
        mock_cursor = Mock()
        mock_row = {
            "id": 1,
            "title": "Test Script",
            "author": "Test Author",
            "file_path": "/path/to/script.fountain",
            "metadata": None,
        }
        mock_cursor.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_cursor

        file_path = Path("/path/to/script.fountain")
        result = script_ops.get_existing_script(mock_connection, file_path)

        assert result is not None
        assert result.metadata is None


class TestScriptOperationsUpsertScript:
    """Test upsert_script method."""

    def test_upsert_script_new_script(
        self,
        script_ops: ScriptOperations,
        mock_connection: sqlite3.Connection,
        sample_script: Script,
    ) -> None:
        """Test upserting a new script."""
        # Mock no existing script
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None  # No existing script
        mock_cursor.lastrowid = 123
        mock_connection.execute.return_value = mock_cursor

        file_path = Path("/path/to/script.fountain")
        script_id = script_ops.upsert_script(mock_connection, sample_script, file_path)

        assert script_id == 123
        # Should have called execute twice: SELECT and INSERT
        assert mock_connection.execute.call_count == 2

    def test_upsert_script_update_existing(
        self,
        script_ops: ScriptOperations,
        mock_connection: sqlite3.Connection,
        sample_script: Script,
    ) -> None:
        """Test upserting an existing script."""
        # Mock existing script
        existing_id = 456
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            (existing_id,),  # First call for SELECT id
            (
                '{"existing": "meta", "bible": {"old": "data"}}',
            ),  # Second call for SELECT metadata
        ]
        mock_connection.execute.return_value = mock_cursor

        file_path = Path("/path/to/script.fountain")
        script_id = script_ops.upsert_script(mock_connection, sample_script, file_path)

        assert script_id == existing_id
        # Should have called execute three times: SELECT id, SELECT metadata, UPDATE
        assert mock_connection.execute.call_count == 3

    def test_upsert_script_merge_metadata(
        self,
        script_ops: ScriptOperations,
        mock_connection: sqlite3.Connection,
    ) -> None:
        """Test metadata merging during upsert."""
        # Create script with bible metadata
        script = Mock()
        script.title = "Test"
        script.author = "Test Author"
        script.metadata = {"bible": {"new": "data"}, "other": "value"}

        # Mock existing script with existing bible metadata
        existing_id = 456
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            (existing_id,),  # First call for SELECT id
            (
                '{"bible": {"old": "data"}, "preserved": "value"}',
            ),  # Second call for SELECT metadata
        ]
        mock_connection.execute.return_value = mock_cursor

        file_path = Path("/path/to/script.fountain")
        script_id = script_ops.upsert_script(mock_connection, script, file_path)

        assert script_id == existing_id

        # Check that UPDATE was called with merged metadata
        update_call_args = mock_connection.execute.call_args_list[2]
        metadata_json = update_call_args[0][1][6]  # 7th parameter (0-indexed)
        metadata = json.loads(metadata_json)

        # Should merge bible objects and preserve other fields
        assert metadata["bible"]["old"] == "data"  # From existing
        assert metadata["bible"]["new"] == "data"  # From new
        assert metadata["preserved"] == "value"  # From existing
        assert metadata["other"] == "value"  # From new

    def test_upsert_script_defaults_for_missing_fields(
        self,
        script_ops: ScriptOperations,
        mock_connection: sqlite3.Connection,
    ) -> None:
        """Test upsert with missing title/author fields."""
        # Create script with minimal data
        script = Mock()
        script.title = None
        script.author = None
        script.metadata = None

        # Mock no existing script
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.lastrowid = 123
        mock_connection.execute.return_value = mock_cursor

        file_path = Path("/path/to/script.fountain")
        script_id = script_ops.upsert_script(mock_connection, sample_script, file_path)

        assert script_id == 123

        # Check that INSERT was called with defaults
        insert_call_args = mock_connection.execute.call_args_list[1]
        title = insert_call_args[0][1][1]  # 2nd parameter (0-indexed)
        author = insert_call_args[0][1][2]  # 3rd parameter (0-indexed)

        assert title == "Test Script"  # From sample_script fixture
        assert author == "Test Author"  # From sample_script fixture

    def test_upsert_script_lastrowid_none_error(
        self,
        script_ops: ScriptOperations,
        mock_connection: sqlite3.Connection,
        sample_script: Script,
    ) -> None:
        """Test upsert raises error when lastrowid is None."""
        # Mock no existing script
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.lastrowid = None  # Simulate failed insert
        mock_connection.execute.return_value = mock_cursor

        file_path = Path("/path/to/script.fountain")

        with pytest.raises(DatabaseError) as exc_info:
            script_ops.upsert_script(mock_connection, sample_script, file_path)

        assert "Failed to get script ID after insert" in str(exc_info.value)
        assert exc_info.value.details["script_title"] == "Test Script"
        assert exc_info.value.details["script_path"] == str(file_path)

    def test_upsert_script_existing_metadata_parse_error(
        self,
        script_ops: ScriptOperations,
        mock_connection: sqlite3.Connection,
        sample_script: Script,
    ) -> None:
        """Test upsert handles existing metadata parse errors gracefully."""
        # Mock existing script with invalid JSON metadata
        existing_id = 456
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            (existing_id,),  # First call for SELECT id
            ("invalid json",),  # Second call for SELECT metadata - invalid JSON
        ]
        mock_connection.execute.return_value = mock_cursor

        file_path = Path("/path/to/script.fountain")

        # Should not raise error, should use empty dict for existing metadata
        script_id = script_ops.upsert_script(mock_connection, sample_script, file_path)
        assert script_id == existing_id

    def test_upsert_script_bible_metadata_types(
        self,
        script_ops: ScriptOperations,
        mock_connection: sqlite3.Connection,
    ) -> None:
        """Test bible metadata merging with different types."""
        # Test case where one bible is dict and other is not
        script = Mock()
        script.title = "Test"
        script.author = "Test Author"
        script.metadata = {"bible": {"new": "data"}}

        # Mock existing script where bible is not a dict
        existing_id = 456
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            (existing_id,),
            ('{"bible": "string_value"}',),  # Bible as string, not dict
        ]
        mock_connection.execute.return_value = mock_cursor

        file_path = Path("/path/to/script.fountain")
        script_id = script_ops.upsert_script(mock_connection, script, file_path)

        assert script_id == existing_id

        # Should still merge properly, treating non-dict as empty dict
        update_call_args = mock_connection.execute.call_args_list[2]
        metadata_json = update_call_args[0][1][6]
        metadata = json.loads(metadata_json)
        assert metadata["bible"]["new"] == "data"


class TestScriptOperationsClearScriptData:
    """Test clear_script_data method."""

    def test_clear_script_data(
        self, script_ops: ScriptOperations, mock_connection: sqlite3.Connection
    ) -> None:
        """Test clearing script data."""
        script_id = 123

        script_ops.clear_script_data(mock_connection, script_id)

        # Should have called execute twice: DELETE scenes, DELETE characters
        assert mock_connection.execute.call_count == 2

        # Check the DELETE calls
        calls = mock_connection.execute.call_args_list
        assert "DELETE FROM scenes" in calls[0][0][0]
        assert "DELETE FROM characters" in calls[1][0][0]

        # Both should use the script_id
        assert calls[0][0][1] == (script_id,)
        assert calls[1][0][1] == (script_id,)


class TestScriptOperationsGetScriptStats:
    """Test get_script_stats method."""

    def test_get_script_stats(
        self, script_ops: ScriptOperations, mock_connection: sqlite3.Connection
    ) -> None:
        """Test getting script statistics."""
        script_id = 123

        # Mock cursor responses for each count query
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            {"count": 10},  # scenes count
            {"count": 5},  # characters count
            {"count": 25},  # dialogues count
            {"count": 15},  # actions count
        ]
        mock_connection.execute.return_value = mock_cursor

        stats = script_ops.get_script_stats(mock_connection, script_id)

        assert stats["scenes"] == 10
        assert stats["characters"] == 5
        assert stats["dialogues"] == 25
        assert stats["actions"] == 15

        # Should have executed 4 queries
        assert mock_connection.execute.call_count == 4

        # All queries should use the script_id
        calls = mock_connection.execute.call_args_list
        for call in calls:
            assert (script_id,) in call[0][1:]  # script_id should be in the parameters

    def test_get_script_stats_empty_script(
        self, script_ops: ScriptOperations, mock_connection: sqlite3.Connection
    ) -> None:
        """Test getting stats for script with no data."""
        script_id = 456

        # Mock cursor responses for empty script
        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = [
            {"count": 0},  # scenes count
            {"count": 0},  # characters count
            {"count": 0},  # dialogues count
            {"count": 0},  # actions count
        ]
        mock_connection.execute.return_value = mock_cursor

        stats = script_ops.get_script_stats(mock_connection, script_id)

        assert stats["scenes"] == 0
        assert stats["characters"] == 0
        assert stats["dialogues"] == 0
        assert stats["actions"] == 0

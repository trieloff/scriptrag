"""Tests for SceneDatabaseOperations to improve coverage."""

import hashlib
import sqlite3
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.api.scene_database import SceneDatabaseOperations
from scriptrag.api.scene_models import SceneIdentifier
from scriptrag.parser import Scene


class TestSceneDatabaseOperations:
    """Test SceneDatabaseOperations class."""

    @pytest.fixture
    def db_ops(self):
        """Create SceneDatabaseOperations instance."""
        return SceneDatabaseOperations()

    @pytest.fixture
    def mock_conn(self):
        """Create mock database connection."""
        conn = MagicMock(spec=sqlite3.Connection)
        # Setup row factory to return dict-like objects
        conn.row_factory = sqlite3.Row
        return conn

    def test_get_scene_by_id_success(self, db_ops, mock_conn):
        """Test successful scene retrieval."""
        scene_id = SceneIdentifier("test_project", 1)

        # Mock database row
        mock_row = {
            "scene_number": 1,
            "heading": "INT. OFFICE - DAY",
            "content": "Test content",
            "location": "OFFICE",
            "time_of_day": "DAY",
            "script_title": "test_project",
        }

        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor

        scene = db_ops.get_scene_by_id(mock_conn, scene_id)

        assert scene is not None
        assert scene.number == 1
        assert scene.heading == "INT. OFFICE - DAY"
        assert scene.content == "Test content"
        assert scene.location == "OFFICE"
        assert scene.time_of_day == "DAY"
        assert scene.content_hash == hashlib.sha256(b"Test content").hexdigest()

    def test_get_scene_by_id_with_season_episode(self, db_ops, mock_conn):
        """Test scene retrieval with season and episode."""
        scene_id = SceneIdentifier("test_show", 5, season=2, episode=3)

        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor

        scene = db_ops.get_scene_by_id(mock_conn, scene_id)

        assert scene is None
        # Verify the query includes season/episode filters
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]
        assert "json_extract" in query
        assert 2 in params  # season
        assert 3 in params  # episode

    def test_get_scene_by_id_not_found(self, db_ops, mock_conn):
        """Test scene retrieval when not found."""
        scene_id = SceneIdentifier("test_project", 999)

        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor

        scene = db_ops.get_scene_by_id(mock_conn, scene_id)
        assert scene is None

    def test_get_scene_by_id_with_empty_content(self, db_ops, mock_conn):
        """Test scene retrieval with null/empty content."""
        scene_id = SceneIdentifier("test_project", 1)

        # Mock database row with None content
        mock_row = {
            "scene_number": 1,
            "heading": "INT. OFFICE - DAY",
            "content": None,
            "location": "OFFICE",
            "time_of_day": "DAY",
            "script_title": "test_project",
        }

        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor

        scene = db_ops.get_scene_by_id(mock_conn, scene_id)

        assert scene is not None
        assert scene.content == ""
        assert scene.original_text == ""
        assert scene.content_hash == hashlib.sha256(b"").hexdigest()

    def test_update_scene_content_with_parsed_scene(self, db_ops, mock_conn):
        """Test updating scene content with parsed scene."""
        scene_id = SceneIdentifier("test_project", 1)
        new_content = "INT. UPDATED - DAY\n\nNew content"

        parsed_scene = Scene(
            number=1,
            heading="INT. UPDATED - DAY",
            content=new_content,
            original_text=new_content,
            content_hash="hash",
            location="UPDATED",
            time_of_day="DAY",
        )

        result = db_ops.update_scene_content(
            mock_conn, scene_id, new_content, parsed_scene
        )

        assert result.number == 1
        assert result.heading == "INT. UPDATED - DAY"
        assert result.content == new_content
        assert result.location == "UPDATED"
        assert result.time_of_day == "DAY"
        assert mock_conn.execute.called

    def test_update_scene_content_without_parsed_scene(self, db_ops, mock_conn):
        """Test updating scene content without parsed scene."""
        scene_id = SceneIdentifier("test_project", 1)
        new_content = "EXT. STREET - NIGHT\n\nAction here"

        with patch("scriptrag.api.scene_database.ScreenplayUtils") as mock_utils:
            mock_utils.extract_location.return_value = "STREET"
            mock_utils.extract_time.return_value = "NIGHT"

            result = db_ops.update_scene_content(mock_conn, scene_id, new_content, None)

            assert result.heading == "EXT. STREET - NIGHT"
            assert result.location == "STREET"
            assert result.time_of_day == "NIGHT"
            assert mock_utils.extract_location.called
            assert mock_utils.extract_time.called

    def test_update_scene_content_with_season_episode(self, db_ops, mock_conn):
        """Test updating scene with season/episode."""
        scene_id = SceneIdentifier("test_show", 1, season=1, episode=2)
        new_content = "INT. SCENE - DAY"

        db_ops.update_scene_content(mock_conn, scene_id, new_content, None)

        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]
        assert "json_extract" in query
        assert 1 in params  # season
        assert 2 in params  # episode

    def test_create_scene_with_parsed_scene(self, db_ops, mock_conn):
        """Test creating scene with parsed scene."""
        scene_id = SceneIdentifier("test_project", 10)
        content = "INT. NEW SCENE - DAY\n\nContent"

        parsed_scene = Scene(
            number=10,
            heading="INT. NEW SCENE - DAY",
            content=content,
            original_text=content,
            content_hash="hash",
            location="NEW SCENE",
            time_of_day="DAY",
        )

        # Mock script ID query
        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = (1,)  # script_id
        mock_conn.execute.return_value = mock_cursor

        result = db_ops.create_scene(mock_conn, scene_id, content, parsed_scene)

        assert result.number == 10
        assert result.heading == "INT. NEW SCENE - DAY"
        assert result.location == "NEW SCENE"
        assert result.time_of_day == "DAY"
        assert mock_conn.execute.call_count == 2  # SELECT + INSERT

    def test_create_scene_script_not_found(self, db_ops, mock_conn):
        """Test creating scene when script not found."""
        scene_id = SceneIdentifier("nonexistent_project", 1)
        content = "INT. SCENE - DAY"

        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor

        with pytest.raises(ValueError, match="Script not found"):
            db_ops.create_scene(mock_conn, scene_id, content, None)

    def test_create_scene_without_parsed_scene(self, db_ops, mock_conn):
        """Test creating scene without parsed scene."""
        scene_id = SceneIdentifier("test_project", 10)
        content = "EXT. LOCATION - NIGHT\n\nAction"

        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = (1,)  # script_id
        mock_conn.execute.return_value = mock_cursor

        with patch("scriptrag.api.scene_database.ScreenplayUtils") as mock_utils:
            mock_utils.extract_location.return_value = "LOCATION"
            mock_utils.extract_time.return_value = "NIGHT"

            result = db_ops.create_scene(mock_conn, scene_id, content, None)

            assert result.heading == "EXT. LOCATION - NIGHT"
            assert result.location == "LOCATION"
            assert result.time_of_day == "NIGHT"

    def test_create_scene_with_empty_content(self, db_ops, mock_conn):
        """Test creating scene with empty content."""
        scene_id = SceneIdentifier("test_project", 10)
        content = ""

        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = (1,)  # script_id
        mock_conn.execute.return_value = mock_cursor

        result = db_ops.create_scene(mock_conn, scene_id, content, None)

        assert result.heading == ""
        assert result.location == ""
        assert result.time_of_day == ""

    def test_delete_scene(self, db_ops, mock_conn):
        """Test deleting scene."""
        scene_id = SceneIdentifier("test_project", 5)

        db_ops.delete_scene(mock_conn, scene_id)

        assert mock_conn.execute.called
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]
        assert "DELETE FROM scenes" in query
        assert 5 in params
        assert "test_project" in params

    def test_delete_scene_with_season_episode(self, db_ops, mock_conn):
        """Test deleting scene with season/episode."""
        scene_id = SceneIdentifier("test_show", 5, season=2, episode=3)

        db_ops.delete_scene(mock_conn, scene_id)

        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]
        assert "json_extract" in query
        assert 2 in params  # season
        assert 3 in params  # episode

    def test_shift_scenes_after(self, db_ops, mock_conn):
        """Test shifting scene numbers after a scene."""
        scene_id = SceneIdentifier("test_project", 5)

        # Mock the cursor for SELECT query
        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchall.return_value = [(10, 6), (11, 7)]  # (id, scene_number)
        mock_conn.execute.return_value = mock_cursor

        db_ops.shift_scenes_after(mock_conn, scene_id, 1)

        # Should make multiple calls: first SELECT, then individual UPDATEs
        assert mock_conn.execute.call_count >= 2

        # First call should be SELECT query
        first_call = mock_conn.execute.call_args_list[0]
        query = first_call[0][0]
        params = first_call[0][1]
        assert "SELECT id, scene_number FROM scenes" in query
        assert "scene_number > ?" in query
        assert 5 in params  # scene number

        # Should also have individual UPDATE calls
        update_calls = [
            call
            for call in mock_conn.execute.call_args_list
            if "UPDATE scenes SET scene_number = scene_number + ?" in str(call)
        ]
        assert len(update_calls) >= 1

    def test_shift_scenes_from(self, db_ops, mock_conn):
        """Test shifting scene numbers from a scene."""
        scene_id = SceneIdentifier("test_project", 5)

        # Test negative shift (uses direct UPDATE)
        db_ops.shift_scenes_from(mock_conn, scene_id, -1)

        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]
        assert "UPDATE scenes" in query
        assert "scene_number >= ?" in query
        assert -1 in params  # shift amount

    def test_shift_scenes_from_positive(self, db_ops, mock_conn):
        """Test shifting scene numbers from a scene with positive shift."""
        scene_id = SceneIdentifier("test_project", 5)

        # Mock the cursor for SELECT query (positive shift uses SELECT-first approach)
        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchall.return_value = [(10, 5), (11, 6)]  # (id, scene_number)
        mock_conn.execute.return_value = mock_cursor

        db_ops.shift_scenes_from(mock_conn, scene_id, 1)

        # Should make multiple calls: first SELECT, then individual UPDATEs
        assert mock_conn.execute.call_count >= 2

        # First call should be SELECT query
        first_call = mock_conn.execute.call_args_list[0]
        query = first_call[0][0]
        params = first_call[0][1]
        assert "SELECT id, scene_number FROM scenes" in query
        assert "scene_number >= ?" in query
        assert 5 in params  # scene number

        # Should also have individual UPDATE calls
        update_calls = [
            call
            for call in mock_conn.execute.call_args_list
            if "UPDATE scenes SET scene_number = scene_number + ?" in str(call)
        ]
        assert len(update_calls) >= 1

    def test_compact_scene_numbers(self, db_ops, mock_conn):
        """Test compacting scene numbers after deletion."""
        scene_id = SceneIdentifier("test_project", 5)

        # Mock scenes that need renumbering
        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchall.return_value = [(6,), (7,), (8,)]
        mock_conn.execute.return_value = mock_cursor

        with patch.object(db_ops, "shift_scenes_after") as mock_shift:
            result = db_ops.compact_scene_numbers(mock_conn, scene_id)

            assert result == [6, 7, 8]
            mock_shift.assert_called_once_with(mock_conn, scene_id, -1)

    def test_compact_scene_numbers_no_scenes(self, db_ops, mock_conn):
        """Test compacting when no scenes need renumbering."""
        scene_id = SceneIdentifier("test_project", 100)

        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        with patch.object(db_ops, "shift_scenes_after") as mock_shift:
            result = db_ops.compact_scene_numbers(mock_conn, scene_id)

            assert result == []
            mock_shift.assert_not_called()

    def test_get_renumbered_scenes(self, db_ops, mock_conn):
        """Test getting list of renumbered scenes."""
        scene_id = SceneIdentifier("test_project", 5)

        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchall.return_value = [(6,), (7,), (8,)]
        mock_conn.execute.return_value = mock_cursor

        result = db_ops.get_renumbered_scenes(mock_conn, scene_id)

        assert result == [6, 7, 8]
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        assert "ORDER BY scene_number" in query

    def test_update_last_read(self, db_ops, mock_conn):
        """Test updating last read timestamp."""
        scene_id = SceneIdentifier("test_project", 5)
        timestamp = datetime.utcnow()

        db_ops.update_last_read(mock_conn, scene_id, timestamp)

        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]
        assert "UPDATE scenes" in query
        assert "last_read_at = ?" in query
        assert timestamp.isoformat() in params

    def test_update_last_read_with_season_episode(self, db_ops, mock_conn):
        """Test updating last read with season/episode."""
        scene_id = SceneIdentifier("test_show", 5, season=1, episode=2)
        timestamp = datetime.utcnow()

        db_ops.update_last_read(mock_conn, scene_id, timestamp)

        call_args = mock_conn.execute.call_args[0]
        params = call_args[1]
        assert 1 in params  # season
        assert 2 in params  # episode

    def test_get_last_modified_success(self, db_ops, mock_conn):
        """Test getting last modified timestamp."""
        scene_id = SceneIdentifier("test_project", 5)

        mock_row = {"updated_at": "2024-01-01T12:00:00"}
        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor

        result = db_ops.get_last_modified(mock_conn, scene_id)

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1

    def test_get_last_modified_with_space_separator(self, db_ops, mock_conn):
        """Test getting last modified with space instead of T."""
        scene_id = SceneIdentifier("test_project", 5)

        # SQLite sometimes returns timestamps with space instead of T
        mock_row = {"updated_at": "2024-01-01 12:00:00"}
        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor

        result = db_ops.get_last_modified(mock_conn, scene_id)

        assert result is not None
        assert result.year == 2024

    def test_get_last_modified_not_found(self, db_ops, mock_conn):
        """Test getting last modified when scene not found."""
        scene_id = SceneIdentifier("test_project", 999)

        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor

        result = db_ops.get_last_modified(mock_conn, scene_id)
        assert result is None

    def test_get_last_modified_null_timestamp(self, db_ops, mock_conn):
        """Test getting last modified when timestamp is null."""
        scene_id = SceneIdentifier("test_project", 5)

        mock_row = {"updated_at": None}
        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor

        result = db_ops.get_last_modified(mock_conn, scene_id)
        assert result is None

    def test_get_last_modified_with_season_episode(self, db_ops, mock_conn):
        """Test getting last modified with season/episode."""
        scene_id = SceneIdentifier("test_show", 5, season=3, episode=4)

        mock_cursor = MagicMock(spec=["content", "model", "provider", "usage"])
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor

        db_ops.get_last_modified(mock_conn, scene_id)

        call_args = mock_conn.execute.call_args[0]
        params = call_args[1]
        assert 3 in params  # season
        assert 4 in params  # episode

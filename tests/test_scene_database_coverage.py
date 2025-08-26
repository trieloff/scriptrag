"""Additional tests for SceneDatabaseOperations to achieve 99% coverage."""

import sqlite3
from unittest.mock import MagicMock

import pytest

from scriptrag.api.scene_database import SceneDatabaseOperations
from scriptrag.api.scene_models import SceneIdentifier


class TestSceneDatabaseCoverage:
    """Additional coverage tests for SceneDatabaseOperations."""

    @pytest.fixture
    def db_ops(self):
        """Create SceneDatabaseOperations instance."""
        return SceneDatabaseOperations()

    @pytest.fixture
    def mock_conn(self):
        """Create mock database connection."""
        conn = MagicMock(spec=sqlite3.Connection)
        conn.row_factory = sqlite3.Row
        return conn

    def test_shift_scenes_after_positive_with_season_only(self, db_ops, mock_conn):
        """Test shift_scenes_after with positive shift and season only (no episode)."""
        scene_id = SceneIdentifier(
            project="tv_show",
            season=3,  # Season specified
            episode=None,  # No episode
            scene_number=5,
        )

        # Mock the cursor for SELECT query
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchall.return_value = [(101, 6), (102, 7), (103, 8)]
        mock_conn.execute.return_value = mock_cursor

        # Perform positive shift
        db_ops.shift_scenes_after(mock_conn, scene_id, 2)

        # Verify the SELECT query was called with season parameter
        calls = mock_conn.execute.call_args_list
        select_call = calls[0]
        query = select_call[0][0]
        params = select_call[0][1]

        # Check that season condition is in the query
        assert "json_extract(metadata, '$.season') = ?" in query
        assert 3 in params  # season value
        assert 5 in params  # scene_number
        assert "tv_show" in params  # project

        # Verify individual UPDATE calls were made
        assert len(calls) >= 4  # 1 SELECT + 3 UPDATEs

    def test_shift_scenes_after_positive_with_episode_only(self, db_ops, mock_conn):
        """Test shift_scenes_after with positive shift and episode only."""
        scene_id = SceneIdentifier(
            project="mini_series",
            season=0,  # Season 0 (counts as None-ish for some shows)
            episode=2,  # Episode specified
            scene_number=10,
        )

        # Mock the cursor for SELECT query
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchall.return_value = [(201, 11), (202, 12)]
        mock_conn.execute.return_value = mock_cursor

        # Perform positive shift
        db_ops.shift_scenes_after(mock_conn, scene_id, 1)

        # Verify the SELECT query includes episode parameter
        calls = mock_conn.execute.call_args_list
        select_call = calls[0]
        query = select_call[0][0]
        params = select_call[0][1]

        # Both season and episode should be in query when not None
        assert "json_extract(metadata, '$.season') = ?" in query
        assert "json_extract(metadata, '$.episode') = ?" in query
        assert 0 in params  # season
        assert 2 in params  # episode
        assert 10 in params  # scene_number

    def test_shift_scenes_after_positive_with_both_season_and_episode(
        self, db_ops, mock_conn
    ):
        """Test shift_scenes_after with positive shift, season AND episode."""
        scene_id = SceneIdentifier(
            project="full_series",
            season=2,
            episode=5,
            scene_number=15,
        )

        # Mock the cursor for SELECT query
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchall.return_value = [(301, 16), (302, 17), (303, 18), (304, 19)]
        mock_conn.execute.return_value = mock_cursor

        # Perform positive shift
        db_ops.shift_scenes_after(mock_conn, scene_id, 3)

        # Verify the SELECT query includes both season and episode
        calls = mock_conn.execute.call_args_list
        select_call = calls[0]
        query = select_call[0][0]
        params = select_call[0][1]

        assert "json_extract(metadata, '$.season') = ?" in query
        assert "json_extract(metadata, '$.episode') = ?" in query
        assert 15 in params  # scene_number
        assert "full_series" in params  # project
        assert 2 in params  # season
        assert 5 in params  # episode

        # Should have made individual updates for each scene
        assert len(calls) == 5  # 1 SELECT + 4 UPDATEs

    def test_shift_scenes_from_positive_with_season_only(self, db_ops, mock_conn):
        """Test shift_scenes_from with positive shift and season only."""
        scene_id = SceneIdentifier(
            project="anthology",
            season=1,
            episode=None,  # No episode
            scene_number=3,
        )

        # Mock the cursor for SELECT query
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchall.return_value = [(401, 3), (402, 4), (403, 5)]
        mock_conn.execute.return_value = mock_cursor

        # Perform positive shift
        db_ops.shift_scenes_from(mock_conn, scene_id, 2)

        # Verify the SELECT query includes season
        calls = mock_conn.execute.call_args_list
        select_call = calls[0]
        query = select_call[0][0]
        params = select_call[0][1]

        assert "SELECT id, scene_number FROM scenes" in query
        assert "scene_number >= ?" in query
        assert "json_extract(metadata, '$.season') = ?" in query
        # Episode condition should NOT be in query when episode is None
        assert "json_extract(metadata, '$.episode')" not in query
        assert 3 in params  # scene_number
        assert "anthology" in params  # project
        assert 1 in params  # season

    def test_shift_scenes_from_positive_with_episode_only(self, db_ops, mock_conn):
        """Test shift_scenes_from with positive shift and episode only."""
        scene_id = SceneIdentifier(
            project="web_series",
            season=None,  # No season
            episode=7,  # Episode only
            scene_number=20,
        )

        # Mock the cursor for SELECT query
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchall.return_value = [(501, 20), (502, 21)]
        mock_conn.execute.return_value = mock_cursor

        # Perform positive shift
        db_ops.shift_scenes_from(mock_conn, scene_id, 1)

        # Verify the SELECT query includes episode but not season
        calls = mock_conn.execute.call_args_list
        select_call = calls[0]
        query = select_call[0][0]
        params = select_call[0][1]

        assert "SELECT id, scene_number FROM scenes" in query
        # Season condition should NOT be in query when season is None
        assert "json_extract(metadata, '$.season')" not in query
        assert "json_extract(metadata, '$.episode') = ?" in query
        assert 20 in params  # scene_number
        assert "web_series" in params  # project
        assert 7 in params  # episode

    def test_shift_scenes_from_positive_with_both_season_and_episode(
        self, db_ops, mock_conn
    ):
        """Test shift_scenes_from with positive shift, both season and episode."""
        scene_id = SceneIdentifier(
            project="drama_series",
            season=4,
            episode=12,
            scene_number=8,
        )

        # Mock the cursor for SELECT query
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchall.return_value = [
            (601, 8),
            (602, 9),
            (603, 10),
            (604, 11),
            (605, 12),
        ]
        mock_conn.execute.return_value = mock_cursor

        # Perform positive shift
        db_ops.shift_scenes_from(mock_conn, scene_id, 5)

        # Verify the SELECT query includes both season and episode
        calls = mock_conn.execute.call_args_list
        select_call = calls[0]
        query = select_call[0][0]
        params = select_call[0][1]

        assert "SELECT id, scene_number FROM scenes" in query
        assert "scene_number >= ?" in query
        assert "json_extract(metadata, '$.season') = ?" in query
        assert "json_extract(metadata, '$.episode') = ?" in query
        assert 8 in params  # scene_number
        assert "drama_series" in params  # project
        assert 4 in params  # season
        assert 12 in params  # episode

        # Should have made individual updates
        assert len(calls) == 6  # 1 SELECT + 5 UPDATEs

    def test_shift_scenes_after_negative_with_season_episode(self, db_ops, mock_conn):
        """Test shift_scenes_after with negative shift and season/episode."""
        scene_id = SceneIdentifier(
            project="sitcom",
            season=2,
            episode=3,
            scene_number=25,
        )

        # Negative shift uses direct UPDATE
        db_ops.shift_scenes_after(mock_conn, scene_id, -2)

        # Check the UPDATE query includes season and episode
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "UPDATE scenes" in query
        assert "json_extract(metadata, '$.season') = ?" in query
        assert "json_extract(metadata, '$.episode') = ?" in query
        assert -2 in params  # shift amount
        assert 25 in params  # scene_number
        assert "sitcom" in params  # project
        assert 2 in params  # season
        assert 3 in params  # episode

    def test_shift_scenes_from_negative_with_season_episode(self, db_ops, mock_conn):
        """Test shift_scenes_from with negative shift and season/episode."""
        scene_id = SceneIdentifier(
            project="thriller",
            season=1,
            episode=6,
            scene_number=30,
        )

        # Negative shift uses direct UPDATE
        db_ops.shift_scenes_from(mock_conn, scene_id, -3)

        # Check the UPDATE query includes season and episode
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "UPDATE scenes" in query
        assert "scene_number >= ?" in query
        assert "json_extract(metadata, '$.season') = ?" in query
        assert "json_extract(metadata, '$.episode') = ?" in query
        assert -3 in params  # shift amount
        assert 30 in params  # scene_number
        assert "thriller" in params  # project
        assert 1 in params  # season
        assert 6 in params  # episode

    def test_shift_scenes_edge_cases(self, db_ops, mock_conn):
        """Test edge cases like empty result sets."""
        scene_id = SceneIdentifier(
            project="empty_show",
            season=99,
            episode=99,
            scene_number=1,
        )

        # Mock empty result for SELECT query
        mock_cursor = MagicMock(spec=object)
        mock_cursor.fetchall.return_value = []  # No scenes to shift
        mock_conn.execute.return_value = mock_cursor

        # This should not fail even with no scenes
        db_ops.shift_scenes_after(mock_conn, scene_id, 1)

        # Only the SELECT should have been called, no UPDATEs
        assert mock_conn.execute.call_count == 1

        # Reset and test shift_scenes_from
        mock_conn.reset_mock()
        mock_conn.execute.return_value = mock_cursor

        db_ops.shift_scenes_from(mock_conn, scene_id, 1)

        # Only the SELECT should have been called
        assert mock_conn.execute.call_count == 1

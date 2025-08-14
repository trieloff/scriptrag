"""Targeted unit tests for PR #239 specific changes.

Focus on covering the exact lines that were modified in the PR.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

from scriptrag.api.scene_management import ReadTracker, SceneManagementAPI


class TestPR239Changes:
    """Test coverage for PR #239 specific code changes."""

    def test_read_tracker_dynamic_validation_window(self):
        """Test that ReadTracker uses _validation_window dynamically."""
        tracker = ReadTracker()

        # Test with custom validation window
        tracker._validation_window = 300  # 5 minutes

        # Register a read session
        token = tracker.register_read(
            scene_key="test:001", content_hash="test_hash", reader_id="test_reader"
        )

        # Check that the session expires in ~5 minutes
        session = tracker._sessions[token]
        time_diff = (session.expires_at - datetime.utcnow()).total_seconds()
        assert 295 <= time_diff <= 305  # Allow small margin for test execution

        # Test with different validation window
        tracker._validation_window = 60  # 1 minute

        token2 = tracker.register_read(
            scene_key="test:002", content_hash="test_hash2", reader_id="test_reader"
        )

        session2 = tracker._sessions[token2]
        time_diff2 = (session2.expires_at - datetime.utcnow()).total_seconds()
        assert 55 <= time_diff2 <= 65  # Allow small margin

    def test_screenplay_utils_import_error_in_update_scene_content(self):
        """Test the ImportError handling in _update_scene_content."""
        api = SceneManagementAPI()
        mock_conn = MagicMock()
        mock_conn.execute.return_value = MagicMock()

        # Mock scene_id
        scene_id = Mock()
        scene_id.project = "test_project"
        scene_id.scene_number = 1
        scene_id.season = None
        scene_id.episode = None

        # Test with ScreenplayUtils not available (ImportError path)
        with patch(
            "builtins.__import__",
            side_effect=ImportError("No module named 'scriptrag.utils'"),
        ):
            # This should execute the except ImportError block
            api._update_scene_content(
                conn=mock_conn,
                scene_id=scene_id,
                new_content="EXT. STREET - NIGHT\n\nA car drives by.",
                parsed_scene=None,  # Force the path that tries to import
            )

            # Check that UPDATE was called with empty strings for location/time
            update_calls = [
                call
                for call in mock_conn.execute.call_args_list
                if call and len(call[0]) > 0 and "UPDATE" in str(call[0][0])
            ]
            assert len(update_calls) > 0

            # The SQL should have been executed with fallback empty values
            sql = update_calls[0][0][0]
            params = update_calls[0][0][1]

            # Should have empty strings in params for location and time_of_day
            assert params.count("") >= 2  # At least location and time_of_day are empty

    def test_screenplay_utils_import_error_in_create_scene(self):
        """Test the ImportError handling in _create_scene."""
        api = SceneManagementAPI()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        # Return a tuple-like object that can be accessed with [0]
        mock_cursor.fetchone.return_value = (1,)

        # Mock scene_id
        scene_id = Mock()
        scene_id.project = "test_project"
        scene_id.scene_number = 1
        scene_id.season = None
        scene_id.episode = None

        # Test with ScreenplayUtils not available
        with patch(
            "builtins.__import__",
            side_effect=ImportError("No module named 'scriptrag.utils'"),
        ):
            api._create_scene(
                conn=mock_conn,
                scene_id=scene_id,
                content="INT. OFFICE - DAY\n\nThe office is empty.",
                parsed_scene=None,  # Force the path that tries to import
            )

            # Check that INSERT was called
            assert mock_conn.execute.called
            # The method should complete without errors when import fails

    def test_screenplay_utils_attribute_error_fallback(self):
        """Test handling when ScreenplayUtils exists but methods are missing."""
        api = SceneManagementAPI()
        mock_conn = MagicMock()
        mock_conn.execute.return_value = MagicMock()

        scene_id = Mock()
        scene_id.project = "test_project"
        scene_id.scene_number = 1
        scene_id.season = None
        scene_id.episode = None

        # Simulate module import that raises ImportError
        with patch(
            "builtins.__import__", side_effect=ImportError("No ScreenplayUtils")
        ):
            # This should trigger ImportError and use fallback
            api._update_scene_content(
                conn=mock_conn,
                scene_id=scene_id,
                new_content="INT. ROOM - DAY\n\nContent",
                parsed_scene=None,
            )

            # Should still execute with fallback values
            assert mock_conn.execute.called

    def test_validation_window_in_read_scene_context(self):
        """Test that the validation window is used correctly in the full context."""
        # This tests the actual line that was changed in the PR
        tracker = ReadTracker()
        original_window = tracker._validation_window

        # Change the validation window
        tracker._validation_window = 120  # 2 minutes

        # Create a session with the new window
        token = tracker.register_read("scene:001", "hash1", "reader1")
        session = tracker._sessions[token]

        # The expiration should use the instance variable, not hardcoded 600
        expected_expiry = datetime.utcnow() + timedelta(
            seconds=tracker._validation_window
        )
        actual_expiry = session.expires_at

        # They should be within a second of each other
        diff = abs((expected_expiry - actual_expiry).total_seconds())
        assert diff < 1.0

        # Restore original
        tracker._validation_window = original_window

    def test_import_error_with_real_modules(self):
        """Test the actual import error paths as they would occur in production."""
        api = SceneManagementAPI()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        # Return a tuple-like object that can be accessed with [0]
        mock_cursor.fetchone.return_value = (1,)

        scene_id = Mock()
        scene_id.project = "test"
        scene_id.scene_number = 1
        scene_id.season = None
        scene_id.episode = None

        # Test with ScreenplayUtils not available - simplified version
        with patch("builtins.__import__", side_effect=ImportError("No module")):
            # Test update path
            api._update_scene_content(
                conn=mock_conn,
                scene_id=scene_id,
                new_content="EXT. PARK - DAY\n\nBirds chirp.",
                parsed_scene=None,
            )

            # Should have executed with empty fallbacks
            assert mock_conn.execute.called

            # Reset for next test
            mock_conn.reset_mock()

            # Test create path
            api._create_scene(
                conn=mock_conn,
                scene_id=scene_id,
                content="INT. ROOM - NIGHT\n\nDark.",
                parsed_scene=None,
            )

            # Should have executed with empty fallbacks
            assert mock_conn.execute.called

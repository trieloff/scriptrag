"""Unit tests to ensure proper mock path handling.

This test module ensures that mock objects correctly return string/Path values
instead of MagicMock objects, preventing creation of invalid file names.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from scriptrag.config import ScriptRAGSettings
from scriptrag.search.engine import SearchEngine


class TestMockPathHandling:
    """Test proper handling of mock paths in SearchEngine."""

    def test_search_engine_with_proper_path(self):
        """Test SearchEngine initialization with proper path object."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = Path("/test/db.sqlite")
        settings.search_vector_result_limit_factor = 0.5
        settings.search_vector_min_results = 5
        settings.search_vector_similarity_threshold = 0.5
        settings.search_vector_threshold = 10
        settings.llm_model_cache_ttl = 3600
        settings.llm_force_static_models = False

        engine = SearchEngine(settings)
        assert engine.settings == settings
        assert engine.db_path == Path("/test/db.sqlite")
        assert isinstance(engine.db_path, Path)

    def test_search_engine_with_string_path(self):
        """Test SearchEngine initialization with string path."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = "/test/db.sqlite"
        settings.search_vector_result_limit_factor = 0.5
        settings.search_vector_min_results = 5
        settings.search_vector_similarity_threshold = 0.5
        settings.search_vector_threshold = 10
        settings.llm_model_cache_ttl = 3600
        settings.llm_force_static_models = False

        engine = SearchEngine(settings)
        assert engine.settings == settings
        assert engine.db_path == "/test/db.sqlite"
        assert isinstance(engine.db_path, str)

    @patch("scriptrag.config.get_settings")
    def test_search_engine_without_settings_uses_proper_path(self, mock_get_settings):
        """Test SearchEngine initialization without settings uses proper path."""
        mock_settings = MagicMock(spec=ScriptRAGSettings)
        mock_settings.database_path = Path("/test/db.sqlite")
        mock_settings.search_vector_result_limit_factor = 0.5
        mock_settings.search_vector_min_results = 5
        mock_settings.search_vector_similarity_threshold = 0.5
        mock_settings.search_vector_threshold = 10
        mock_settings.llm_model_cache_ttl = 3600
        mock_settings.llm_force_static_models = False
        mock_get_settings.return_value = mock_settings

        engine = SearchEngine()
        assert engine.settings is not None
        assert mock_get_settings.called
        assert engine.db_path == Path("/test/db.sqlite")
        assert isinstance(engine.db_path, Path)

    def test_path_not_magicmock(self):
        """Ensure database_path is never a MagicMock instance."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = Path("/test/db.sqlite")

        # This should not be a MagicMock
        assert not isinstance(settings.database_path, MagicMock)
        assert isinstance(settings.database_path, Path)

        # String representation should be a valid path (cross-platform compatible)
        path_str = str(settings.database_path)
        expected_path = str(
            Path("/test/db.sqlite")
        )  # Let Path handle platform differences
        assert path_str == expected_path
        assert not path_str.startswith("<MagicMock")

    def test_mock_embedding_response_indexable(self):
        """Test that mock embedding response supports dictionary indexing."""
        # This simulates what the integration test needs
        mock_embedding = {"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}

        # Should support dict-style access
        assert mock_embedding["embedding"] == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert mock_embedding.get("embedding") == [0.1, 0.2, 0.3, 0.4, 0.5]

        # When used in a list (like response.data)
        response_data = [mock_embedding]
        assert response_data[0]["embedding"] == [0.1, 0.2, 0.3, 0.4, 0.5]

    def test_mock_object_not_created_as_file(self):
        """Ensure mock objects are not accidentally used as file paths."""
        # This tests the scenario that was causing the CI failure
        mock = MagicMock()

        # Bad: Using MagicMock as path creates invalid filename
        bad_path = str(mock.database_path)
        assert bad_path.startswith("<MagicMock")  # This would create invalid file

        # Good: Using proper path
        mock.database_path = Path("/test/db.sqlite")
        good_path = str(mock.database_path)
        expected_path = str(Path("/test/db.sqlite"))  # Cross-platform compatible
        assert good_path == expected_path  # Valid file path

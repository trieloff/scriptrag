"""Comprehensive unit tests for scene type filtering functionality."""

from unittest.mock import MagicMock, patch

from scriptrag.main import ScriptRAG
from scriptrag.search.builder import QueryBuilder
from scriptrag.search.models import SearchQuery
from scriptrag.search.utils import SearchFilterUtils


class TestSceneTypeFiltering:
    """Test scene type filtering across all layers of the application."""

    def test_search_query_model_has_scene_type_field(self):
        """Test that SearchQuery model includes scene_type field."""
        query = SearchQuery(raw_query="test", scene_type="INT", limit=10, offset=0)
        assert query.scene_type == "INT"
        assert hasattr(query, "scene_type")

    def test_search_query_scene_type_default_is_none(self):
        """Test that scene_type defaults to None when not provided."""
        query = SearchQuery(raw_query="test")
        assert query.scene_type is None

    def test_search_filter_utils_adds_scene_type_filter(self):
        """Test SearchFilterUtils.add_scene_type_filter method."""
        where_conditions = []
        params = []

        # Test with INT scene type
        SearchFilterUtils.add_scene_type_filter(where_conditions, params, "INT")
        assert len(where_conditions) == 1
        assert "sc.heading LIKE ?" in where_conditions[0]
        assert params == ["INT.%"]

        # Reset and test with EXT
        where_conditions = []
        params = []
        SearchFilterUtils.add_scene_type_filter(where_conditions, params, "EXT")
        assert params == ["EXT.%"]

        # Reset and test with INT/EXT
        where_conditions = []
        params = []
        SearchFilterUtils.add_scene_type_filter(where_conditions, params, "INT/EXT")
        assert params == ["INT/EXT.%"]

    def test_search_filter_utils_ignores_none_scene_type(self):
        """Test that None scene_type is properly ignored."""
        where_conditions = []
        params = []

        SearchFilterUtils.add_scene_type_filter(where_conditions, params, None)
        assert len(where_conditions) == 0
        assert len(params) == 0

    def test_query_builder_includes_scene_type_in_search_query(self):
        """Test that QueryBuilder properly includes scene_type filter."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test", text_query="test", scene_type="INT", limit=10, offset=0
        )

        sql, params = builder.build_search_query(query)

        # Check that scene type filter is included
        assert "sc.heading LIKE ?" in sql
        assert "INT.%" in params

    def test_query_builder_includes_scene_type_in_count_query(self):
        """Test that QueryBuilder includes scene_type in count query."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test", text_query="test", scene_type="EXT", limit=10, offset=0
        )

        sql, params = builder.build_count_query(query)

        # Check that scene type filter is included
        assert "sc.heading LIKE ?" in sql
        assert "EXT.%" in params

    def test_main_scriptrag_passes_scene_type_from_filters(self):
        """Test that ScriptRAG.search properly handles scene_type in filters."""
        with patch("scriptrag.main.SearchEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            # Create ScriptRAG instance
            scriptrag = ScriptRAG(auto_init_db=False)

            # Mock the database check
            scriptrag.db_ops.check_database_exists = MagicMock(return_value=True)

            # Mock the search method
            mock_response = MagicMock()
            mock_response.results = []
            mock_response.total_count = 0
            mock_engine.search.return_value = mock_response

            # Call search with scene_type filter
            scriptrag.search("test query", filters={"scene_type": "INT"})

            # Verify that search was called with SearchQuery containing scene_type
            mock_engine.search.assert_called_once()
            search_query_arg = mock_engine.search.call_args[0][0]
            assert isinstance(search_query_arg, SearchQuery)
            assert search_query_arg.scene_type == "INT"

    def test_main_scriptrag_handles_all_valid_scene_types(self):
        """Test that all valid scene types are properly handled."""
        with patch("scriptrag.main.SearchEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            scriptrag = ScriptRAG(auto_init_db=False)

            # Mock the database check
            scriptrag.db_ops.check_database_exists = MagicMock(return_value=True)

            mock_response = MagicMock()
            mock_response.results = []
            mock_response.total_count = 0
            mock_engine.search.return_value = mock_response

            # Test INT
            scriptrag.search("test", filters={"scene_type": "INT"})
            assert mock_engine.search.call_args[0][0].scene_type == "INT"

            # Test EXT
            scriptrag.search("test", filters={"scene_type": "EXT"})
            assert mock_engine.search.call_args[0][0].scene_type == "EXT"

            # Test INT/EXT
            scriptrag.search("test", filters={"scene_type": "INT/EXT"})
            assert mock_engine.search.call_args[0][0].scene_type == "INT/EXT"

    def test_main_scriptrag_ignores_invalid_scene_types(self):
        """Test that invalid scene types are properly ignored."""
        with patch("scriptrag.main.SearchEngine") as mock_engine_class:
            mock_engine = MagicMock()
            mock_engine_class.return_value = mock_engine

            scriptrag = ScriptRAG(auto_init_db=False)

            # Mock the database check
            scriptrag.db_ops.check_database_exists = MagicMock(return_value=True)

            mock_response = MagicMock()
            mock_response.results = []
            mock_response.total_count = 0
            mock_engine.search.return_value = mock_response

            # Test invalid scene type
            scriptrag.search("test", filters={"scene_type": "INVALID"})

            # Should not have scene_type set
            search_query_arg = mock_engine.search.call_args[0][0]
            assert search_query_arg.scene_type is None

    def test_search_with_scene_type_and_other_filters(self):
        """Test scene_type filtering combined with other filters."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="coffee",
            text_query="coffee",
            scene_type="INT",
            locations=["office"],
            limit=10,
            offset=0,
        )

        sql, params = builder.build_search_query(query)

        # Check both filters are included
        assert "sc.heading LIKE ?" in sql
        assert "sc.location LIKE ?" in sql
        assert "INT.%" in params
        assert "%office%" in params

    def test_scene_type_filter_preserves_existing_functionality(self):
        """Test that adding scene_type doesn't break existing search functionality."""
        builder = QueryBuilder()

        # Query without scene_type (existing functionality)
        query1 = SearchQuery(
            raw_query="test", dialogue="hello", characters=["John"], limit=5, offset=0
        )
        sql1, params1 = builder.build_search_query(query1)

        # Verify existing query still works
        assert "d.dialogue_text LIKE ?" in sql1
        assert "%hello%" in params1

        # Query with scene_type (new functionality)
        query2 = SearchQuery(
            raw_query="test",
            dialogue="hello",
            characters=["John"],
            scene_type="INT",
            limit=5,
            offset=0,
        )
        sql2, params2 = builder.build_search_query(query2)

        # Verify both old and new filters work together
        assert "d.dialogue_text LIKE ?" in sql2
        assert "sc.heading LIKE ?" in sql2
        assert "%hello%" in params2
        assert "INT.%" in params2

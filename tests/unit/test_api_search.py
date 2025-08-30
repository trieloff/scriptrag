"""Unit tests for search API module."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from scriptrag.api.search import SearchAPI
from scriptrag.config.settings import ScriptRAGSettings
from scriptrag.search.models import (
    SearchMode,
    SearchQuery,
    SearchResponse,
    SearchResult,
)


@pytest.fixture
def settings(tmp_path):
    """Create test settings."""
    return ScriptRAGSettings(
        database_path=tmp_path / "test.db",
        database_timeout=5.0,
        search_vector_threshold=3,
    )


@pytest.fixture
def mock_parser():
    """Create mock query parser."""
    mock = Mock(spec=object)
    mock.parse.return_value = SearchQuery(
        raw_query="test query",
        text_query="test query",
        mode=SearchMode.AUTO,
        limit=5,
        offset=0,
    )
    return mock


@pytest.fixture
def mock_engine():
    """Create mock search engine."""
    mock = Mock(spec=object)
    mock.search.return_value = SearchResponse(
        query=SearchQuery(raw_query="test query"),
        results=[
            SearchResult(
                script_id=1,
                script_title="Test Script",
                script_author="Test Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. TEST SCENE - DAY",
                scene_location="TEST SCENE",
                scene_time="DAY",
                scene_content="This is a test scene.",
                match_type="text",
                relevance_score=0.95,
            )
        ],
        total_count=1,
        has_more=False,
        execution_time_ms=25.5,
        search_methods=["text_search"],
    )
    return mock


@pytest.fixture
def sample_search_response():
    """Create sample search response."""
    return SearchResponse(
        query=SearchQuery(
            raw_query="ALICE dialogue",
            characters=["ALICE"],
            mode=SearchMode.AUTO,
        ),
        results=[
            SearchResult(
                script_id=1,
                script_title="Test Script",
                script_author="Test Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. COFFEE SHOP - DAY",
                scene_location="COFFEE SHOP",
                scene_time="DAY",
                scene_content="ALICE sits at the counter.",
                character_name="ALICE",
                match_type="character",
                relevance_score=1.0,
                matched_text="ALICE sits at the counter.",
            ),
            SearchResult(
                script_id=2,
                script_title="Another Script",
                script_author="Another Author",
                scene_id=2,
                scene_number=5,
                scene_heading="EXT. PARK - MORNING",
                scene_location="PARK",
                scene_time="MORNING",
                scene_content="ALICE jogs through the park.",
                character_name="ALICE",
                match_type="action",
                relevance_score=0.87,
                matched_text="ALICE jogs through the park.",
            ),
        ],
        total_count=2,
        has_more=False,
        execution_time_ms=42.3,
        search_methods=["character_search", "text_search"],
        metadata={"search_index_version": "1.0"},
    )


class TestSearchAPIInit:
    """Test SearchAPI initialization."""

    def test_init_with_settings(self, settings):
        """Test SearchAPI initialization with provided settings."""
        api = SearchAPI(settings=settings)

        assert api.settings == settings
        assert api.parser is not None
        assert api.engine is not None
        # Verify the engine was initialized with the same settings
        assert api.engine.settings == settings

    def test_init_without_settings(self):
        """Test SearchAPI initialization without settings (uses default)."""
        with patch("scriptrag.config.get_settings") as mock_get_settings:
            mock_settings = MagicMock(
                spec=ScriptRAGSettings
            )  # Use spec to prevent mock file artifacts
            # Add required settings
            mock_settings.database_path = Path("/tmp/test.db")
            mock_settings.search_vector_result_limit_factor = 0.5
            mock_settings.search_vector_min_results = 5
            mock_settings.search_vector_similarity_threshold = 0.5
            mock_settings.search_vector_threshold = 10
            mock_settings.llm_model_cache_ttl = 3600  # Must be int for comparisons
            mock_settings.llm_force_static_models = False
            mock_settings.database_journal_mode = "WAL"
            mock_settings.database_synchronous = "NORMAL"
            mock_settings.database_foreign_keys = True
            mock_get_settings.return_value = mock_settings

            api = SearchAPI(settings=None)

            assert api.settings == mock_settings
            assert mock_get_settings.called
            assert api.parser is not None
            assert api.engine is not None

    def test_init_with_none_settings(self):
        """Test SearchAPI initialization with explicit None settings."""
        with patch("scriptrag.config.get_settings") as mock_get_settings:
            mock_settings = MagicMock(
                spec=ScriptRAGSettings
            )  # Use spec to prevent mock file artifacts
            # Add required settings
            mock_settings.database_path = Path("/tmp/test.db")
            mock_settings.search_vector_result_limit_factor = 0.5
            mock_settings.search_vector_min_results = 5
            mock_settings.search_vector_similarity_threshold = 0.5
            mock_settings.search_vector_threshold = 10
            mock_settings.llm_model_cache_ttl = 3600  # Must be int for comparisons
            mock_settings.llm_force_static_models = False
            mock_settings.database_journal_mode = "WAL"
            mock_settings.database_synchronous = "NORMAL"
            mock_settings.database_foreign_keys = True
            mock_get_settings.return_value = mock_settings

            api = SearchAPI(None)

            assert api.settings == mock_settings
            assert mock_get_settings.called

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_init_component_creation(
        self, mock_engine_class, mock_parser_class, settings
    ):
        """Test that SearchAPI creates parser and engine components correctly."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        api = SearchAPI(settings)

        mock_parser_class.assert_called_once_with()
        mock_engine_class.assert_called_once_with(settings)
        assert api.parser == mock_parser
        assert api.engine == mock_engine


class TestSearchAPIFromConfig:
    """Test SearchAPI.from_config class method."""

    def test_from_config_without_path(self):
        """Test creating SearchAPI from config without config path."""
        with patch("scriptrag.config.get_settings") as mock_get_settings:
            mock_settings = MagicMock(
                spec=ScriptRAGSettings
            )  # Use spec to prevent mock file artifacts
            # Add required settings
            mock_settings.database_path = Path("/tmp/test.db")
            mock_settings.search_vector_result_limit_factor = 0.5
            mock_settings.search_vector_min_results = 5
            mock_settings.search_vector_similarity_threshold = 0.5
            mock_settings.search_vector_threshold = 10
            mock_settings.llm_model_cache_ttl = 3600  # Must be int for comparisons
            mock_settings.llm_force_static_models = False
            mock_settings.database_journal_mode = "WAL"
            mock_settings.database_synchronous = "NORMAL"
            mock_settings.database_foreign_keys = True
            mock_get_settings.return_value = mock_settings

            api = SearchAPI.from_config()

            assert isinstance(api, SearchAPI)
            assert api.settings == mock_settings
            assert mock_get_settings.called

    def test_from_config_with_path(self):
        """Test creating SearchAPI from config with config path."""
        with patch(
            "scriptrag.api.search.ScriptRAGSettings.from_file"
        ) as mock_from_file:
            mock_settings = MagicMock(
                spec=ScriptRAGSettings
            )  # Use spec to prevent mock file artifacts
            mock_settings.database_path = "/tmp/test.db"
            mock_from_file.return_value = mock_settings

            api = SearchAPI.from_config(config_path="/path/to/config.json")

            assert isinstance(api, SearchAPI)
            assert api.settings == mock_settings
            mock_from_file.assert_called_once_with("/path/to/config.json")

    def test_from_config_with_none_path(self):
        """Test creating SearchAPI from config with None path."""
        with patch("scriptrag.config.get_settings") as mock_get_settings:
            mock_settings = MagicMock(
                spec=ScriptRAGSettings
            )  # Use spec to prevent mock file artifacts
            # Add required settings
            mock_settings.database_path = Path("/tmp/test.db")
            mock_settings.search_vector_result_limit_factor = 0.5
            mock_settings.search_vector_min_results = 5
            mock_settings.search_vector_similarity_threshold = 0.5
            mock_settings.search_vector_threshold = 10
            mock_settings.llm_model_cache_ttl = 3600  # Must be int for comparisons
            mock_settings.llm_force_static_models = False
            mock_settings.database_journal_mode = "WAL"
            mock_settings.database_synchronous = "NORMAL"
            mock_settings.database_foreign_keys = True
            mock_get_settings.return_value = mock_settings

            api = SearchAPI.from_config(config_path=None)

            assert isinstance(api, SearchAPI)
            assert api.settings == mock_settings


class TestSearchAPISearch:
    """Test SearchAPI.search method."""

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    @patch("scriptrag.api.search.logger")
    def test_search_basic_query(
        self, mock_logger, mock_engine_class, mock_parser_class, settings
    ):
        """Test basic search with minimal parameters."""
        # Setup mocks
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(
            raw_query="test query",
            text_query="test query",
            mode=SearchMode.AUTO,
            limit=5,
            offset=0,
        )
        mock_parser.parse.return_value = mock_query

        mock_response = SearchResponse(
            query=mock_query,
            results=[],
            total_count=0,
            has_more=False,
        )
        mock_engine.search.return_value = mock_response

        api = SearchAPI(settings)
        result = api.search(query="test query")

        # Verify parser was called correctly
        mock_parser.parse.assert_called_once_with(
            query="test query",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            mode=SearchMode.AUTO,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

        # Verify engine was called
        mock_engine.search.assert_called_once_with(mock_query)

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Executing search: query='test query', "
            "mode=SearchMode.AUTO, limit=5, offset=0"
        )

        assert result == mock_response

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_search_with_all_parameters(
        self, mock_engine_class, mock_parser_class, settings
    ):
        """Test search with all possible parameters."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="complex query")
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        api = SearchAPI(settings)
        api.search(
            query="complex query",
            character="ALICE",
            dialogue="Hello world",
            parenthetical="sarcastically",
            project="My Project",
            range_str="s1e1-s1e5",
            fuzzy=False,
            strict=False,
            limit=20,
            offset=10,
        )

        mock_parser.parse.assert_called_once_with(
            query="complex query",
            character="ALICE",
            dialogue="Hello world",
            parenthetical="sarcastically",
            project="My Project",
            range_str="s1e1-s1e5",
            mode=SearchMode.AUTO,
            limit=20,
            offset=10,
            include_bible=True,
            only_bible=False,
        )

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_search_mode_determination_strict(
        self, mock_engine_class, mock_parser_class, settings
    ):
        """Test search mode determination - strict mode."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="test")
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        api = SearchAPI(settings)
        api.search(query="test", strict=True)

        mock_parser.parse.assert_called_once_with(
            query="test",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            mode=SearchMode.STRICT,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_search_mode_determination_fuzzy(
        self, mock_engine_class, mock_parser_class, settings
    ):
        """Test search mode determination - fuzzy mode."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="test")
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        api = SearchAPI(settings)
        api.search(query="test", fuzzy=True)

        mock_parser.parse.assert_called_once_with(
            query="test",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            mode=SearchMode.FUZZY,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_search_mode_determination_auto(
        self, mock_engine_class, mock_parser_class, settings
    ):
        """Test search mode determination - auto mode (default)."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="test")
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        api = SearchAPI(settings)
        api.search(query="test", fuzzy=False, strict=False)

        mock_parser.parse.assert_called_once_with(
            query="test",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            mode=SearchMode.AUTO,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_search_mode_priority_strict_over_fuzzy(
        self, mock_engine_class, mock_parser_class, settings
    ):
        """Test search mode priority - strict takes precedence over fuzzy."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="test")
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        api = SearchAPI(settings)
        # Both strict and fuzzy are True - strict should win
        api.search(query="test", fuzzy=True, strict=True)

        mock_parser.parse.assert_called_once_with(
            query="test",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            mode=SearchMode.STRICT,  # Should be strict, not fuzzy
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    @patch("scriptrag.api.search.logger")
    def test_search_logging_with_custom_params(
        self, mock_logger, mock_engine_class, mock_parser_class, settings
    ):
        """Test search logging with custom parameters."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="custom query")
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        api = SearchAPI(settings)
        api.search(
            query="custom query",
            fuzzy=True,
            limit=15,
            offset=25,
        )

        mock_logger.info.assert_called_once_with(
            "Executing search: query='custom query', "
            "mode=SearchMode.FUZZY, limit=15, offset=25"
        )

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_search_returns_engine_response(
        self,
        mock_engine_class,
        mock_parser_class,
        settings,
        sample_search_response,
    ):
        """Test that search returns the engine's response unchanged."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="test")
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = sample_search_response

        api = SearchAPI(settings)
        result = api.search(query="test")

        assert result == sample_search_response
        assert len(result.results) == 2
        assert result.total_count == 2
        assert result.execution_time_ms == 42.3


class TestSearchAPIIntegration:
    """Test SearchAPI integration scenarios."""

    def test_search_with_real_components(self, settings):
        """Test search with real QueryParser and SearchEngine (mocked deeper)."""
        with patch("scriptrag.search.engine.SearchEngine.search") as mock_engine_search:
            mock_response = SearchResponse(
                query=SearchQuery(raw_query="integration test"),
                results=[],
                total_count=0,
                has_more=False,
            )
            mock_engine_search.return_value = mock_response

            api = SearchAPI(settings)
            result = api.search(
                query='ALICE "Hello world" (cheerfully)',
                limit=10,
            )

            # Verify the query was parsed correctly by checking the engine call
            assert mock_engine_search.called
            called_query = mock_engine_search.call_args[0][0]
            assert called_query.raw_query == 'ALICE "Hello world" (cheerfully)'
            assert called_query.limit == 10
            assert called_query.offset == 0

            assert result == mock_response

    def test_search_error_propagation(self, settings):
        """Test that search errors are properly propagated."""
        with (
            patch("scriptrag.api.search.QueryParser") as mock_parser_class,
            patch("scriptrag.api.search.SearchEngine") as mock_engine_class,
        ):
            mock_parser = Mock(spec=["parse"])
            mock_engine = Mock(spec=["search", "init_from_db"])
            mock_parser_class.return_value = mock_parser
            mock_engine_class.return_value = mock_engine

            # Make parser raise an exception
            mock_parser.parse.side_effect = ValueError("Parse error")

            api = SearchAPI(settings)

            with pytest.raises(ValueError, match="Parse error"):
                api.search(query="invalid query")

    def test_search_engine_error_propagation(self, settings):
        """Test that search engine errors are properly propagated."""
        with (
            patch("scriptrag.api.search.QueryParser") as mock_parser_class,
            patch("scriptrag.api.search.SearchEngine") as mock_engine_class,
        ):
            mock_parser = Mock(spec=["parse"])
            mock_engine = Mock(spec=["search", "init_from_db"])
            mock_parser_class.return_value = mock_parser
            mock_engine_class.return_value = mock_engine

            mock_query = SearchQuery(raw_query="test")
            mock_parser.parse.return_value = mock_query

            # Make engine raise an exception
            mock_engine.search.side_effect = RuntimeError("Database connection failed")

            api = SearchAPI(settings)

            with pytest.raises(RuntimeError, match="Database connection failed"):
                api.search(query="test")


class TestSearchAPIEdgeCases:
    """Test SearchAPI edge cases and boundary conditions."""

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_search_empty_query(self, mock_engine_class, mock_parser_class, settings):
        """Test search with empty query string."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="")
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        api = SearchAPI(settings)
        result = api.search(query="")

        mock_parser.parse.assert_called_once_with(
            query="",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            mode=SearchMode.AUTO,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )
        assert result is not None

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_search_large_limit_offset(
        self, mock_engine_class, mock_parser_class, settings
    ):
        """Test search with large limit and offset values."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="test")
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        api = SearchAPI(settings)
        api.search(
            query="test",
            limit=10000,
            offset=50000,
        )

        mock_parser.parse.assert_called_once_with(
            query="test",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            mode=SearchMode.AUTO,
            limit=10000,
            offset=50000,
            include_bible=True,
            only_bible=False,
        )

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_search_zero_limit(self, mock_engine_class, mock_parser_class, settings):
        """Test search with zero limit."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="test")
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        api = SearchAPI(settings)
        api.search(query="test", limit=0)

        mock_parser.parse.assert_called_once_with(
            query="test",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            mode=SearchMode.AUTO,
            limit=0,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_search_negative_offset(
        self, mock_engine_class, mock_parser_class, settings
    ):
        """Test search with negative offset."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="test")
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        api = SearchAPI(settings)
        api.search(query="test", offset=-10)

        mock_parser.parse.assert_called_once_with(
            query="test",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            mode=SearchMode.AUTO,
            limit=5,
            offset=-10,
            include_bible=True,
            only_bible=False,
        )

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_search_unicode_query(self, mock_engine_class, mock_parser_class, settings):
        """Test search with Unicode characters in query."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        unicode_query = "café français 🎬 émoji"
        mock_query = SearchQuery(raw_query=unicode_query)
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        api = SearchAPI(settings)
        api.search(query=unicode_query)

        mock_parser.parse.assert_called_once_with(
            query=unicode_query,
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            mode=SearchMode.AUTO,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    def test_search_special_characters_in_params(
        self, mock_engine_class, mock_parser_class, settings
    ):
        """Test search with special characters in various parameters."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="test")
        mock_parser.parse.return_value = mock_query
        mock_engine.search.return_value = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        api = SearchAPI(settings)
        api.search(
            query="test",
            character="MÜNCHEN-23",
            dialogue='"Hello, it\'s a test!" & <special>',
            parenthetical="sarcastically; with a wink",
            project="Project™ v2.0",
            range_str="s1e1-s2e10",
        )

        mock_parser.parse.assert_called_once_with(
            query="test",
            character="MÜNCHEN-23",
            dialogue='"Hello, it\'s a test!" & <special>',
            parenthetical="sarcastically; with a wink",
            project="Project™ v2.0",
            range_str="s1e1-s2e10",
            mode=SearchMode.AUTO,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )


class TestSearchAPIAsync:
    """Test SearchAPI.search_async method."""

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    @patch("scriptrag.api.search.logger")
    @pytest.mark.asyncio
    async def test_search_async_basic_query(
        self, mock_logger, mock_engine_class, mock_parser_class, settings
    ):
        """Test basic async search with minimal parameters."""
        # Setup mocks
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(
            raw_query="async test query",
            text_query="async test query",
            mode=SearchMode.AUTO,
            limit=5,
            offset=0,
        )
        mock_parser.parse.return_value = mock_query

        mock_response = SearchResponse(
            query=mock_query,
            results=[],
            total_count=0,
            has_more=False,
        )

        # Mock the async method
        async def mock_search_async(query):
            return mock_response

        mock_engine.search_async = mock_search_async

        api = SearchAPI(settings)
        result = await api.search_async(query="async test query")

        # Verify parser was called correctly
        mock_parser.parse.assert_called_once_with(
            query="async test query",
            character=None,
            dialogue=None,
            parenthetical=None,
            project=None,
            range_str=None,
            mode=SearchMode.AUTO,
            limit=5,
            offset=0,
            include_bible=True,
            only_bible=False,
        )

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Executing async search: query='async test query', "
            "mode=SearchMode.AUTO, limit=5, offset=0"
        )

        assert result == mock_response

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    @pytest.mark.asyncio
    async def test_search_async_with_all_parameters(
        self, mock_engine_class, mock_parser_class, settings
    ):
        """Test async search with all possible parameters."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="complex async query")
        mock_parser.parse.return_value = mock_query

        mock_response = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        async def mock_search_async(query):
            return mock_response

        mock_engine.search_async = mock_search_async

        api = SearchAPI(settings)
        result = await api.search_async(
            query="complex async query",
            character="ALICE",
            dialogue="Hello async world",
            parenthetical="asynchronously",
            project="Async Project",
            range_str="s1e1-s1e5",
            fuzzy=True,
            strict=False,
            limit=20,
            offset=10,
            include_bible=False,
            only_bible=True,
        )

        mock_parser.parse.assert_called_once_with(
            query="complex async query",
            character="ALICE",
            dialogue="Hello async world",
            parenthetical="asynchronously",
            project="Async Project",
            range_str="s1e1-s1e5",
            mode=SearchMode.FUZZY,
            limit=20,
            offset=10,
            include_bible=False,
            only_bible=True,
        )

        assert result == mock_response

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    @patch("scriptrag.api.search.logger")
    @pytest.mark.asyncio
    async def test_search_async_logging_with_custom_params(
        self, mock_logger, mock_engine_class, mock_parser_class, settings
    ):
        """Test async search logging with custom parameters."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="custom async query")
        mock_parser.parse.return_value = mock_query

        mock_response = SearchResponse(
            query=mock_query, results=[], total_count=0, has_more=False
        )

        async def mock_search_async(query):
            return mock_response

        mock_engine.search_async = mock_search_async

        api = SearchAPI(settings)
        result = await api.search_async(
            query="custom async query",
            fuzzy=True,
            limit=15,
            offset=25,
        )

        mock_logger.info.assert_called_once_with(
            "Executing async search: query='custom async query', "
            "mode=SearchMode.FUZZY, limit=15, offset=25"
        )

        assert result == mock_response

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    @pytest.mark.asyncio
    async def test_search_async_error_propagation(
        self, mock_engine_class, mock_parser_class, settings
    ):
        """Test that async search errors are properly propagated."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        # Make parser raise an exception
        mock_parser.parse.side_effect = ValueError("Async parse error")

        api = SearchAPI(settings)

        with pytest.raises(ValueError, match="Async parse error"):
            await api.search_async(query="invalid query")

    @patch("scriptrag.api.search.QueryParser")
    @patch("scriptrag.api.search.SearchEngine")
    @pytest.mark.asyncio
    async def test_search_async_engine_error_propagation(
        self, mock_engine_class, mock_parser_class, settings
    ):
        """Test that async search engine errors are properly propagated."""
        mock_parser = Mock(spec=["parse"])
        mock_engine = Mock(spec=["search", "init_from_db"])
        mock_parser_class.return_value = mock_parser
        mock_engine_class.return_value = mock_engine

        mock_query = SearchQuery(raw_query="test")
        mock_parser.parse.return_value = mock_query

        # Make engine raise an exception
        async def mock_search_async_error(query):
            raise RuntimeError("Async database connection failed")

        mock_engine.search_async = mock_search_async_error

        api = SearchAPI(settings)

        with pytest.raises(RuntimeError, match="Async database connection failed"):
            await api.search_async(query="test")

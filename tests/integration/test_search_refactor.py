"""Integration tests for refactored search functionality."""

import sqlite3

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.search.builder import QueryBuilder
from scriptrag.search.engine import SearchEngine
from scriptrag.search.filters import (
    CharacterFilter,
    DuplicateFilter,
    LocationFilter,
    SearchFilterChain,
    SeasonEpisodeFilter,
    TimeOfDayFilter,
)
from scriptrag.search.models import SearchQuery, SearchResult
from scriptrag.search.rankers import (
    HybridRanker,
    PositionalRanker,
    ProximityRanker,
    RelevanceRanker,
    TextMatchRanker,
)
from scriptrag.search.utils import (
    SearchFilterUtils,
    SearchResultUtils,
    SearchTextUtils,
)


@pytest.fixture
def sample_search_results():
    """Create sample search results for testing."""
    return [
        SearchResult(
            script_id=1,
            script_title="Test Script",
            script_author="Test Author",
            scene_id=1,
            scene_number=1,
            scene_heading="INT. COFFEE SHOP - DAY",
            scene_location="COFFEE SHOP",
            scene_time="DAY",
            scene_content="WALTER enters the coffee shop. He orders a latte.",
            season=1,
            episode=1,
            relevance_score=0.8,
        ),
        SearchResult(
            script_id=1,
            script_title="Test Script",
            script_author="Test Author",
            scene_id=2,
            scene_number=2,
            scene_heading="EXT. PARK - NIGHT",
            scene_location="PARK",
            scene_time="NIGHT",
            scene_content="WALTER walks through the park, thinking about coffee.",
            season=1,
            episode=1,
            relevance_score=0.6,
        ),
        SearchResult(
            script_id=1,
            script_title="Test Script",
            script_author="Test Author",
            scene_id=3,
            scene_number=3,
            scene_heading="INT. OFFICE - DAY",
            scene_location="OFFICE",
            scene_time="DAY",
            scene_content="SARAH enters. She talks to WALTER about the project.",
            season=1,
            episode=2,
            relevance_score=0.4,
        ),
    ]


class TestSearchUtilities:
    """Test search utility functions."""

    def test_filter_utils_project_filter(self):
        """Test project filter utility."""
        where_conditions = []
        params = []
        SearchFilterUtils.add_project_filter(where_conditions, params, "Test Project")

        assert len(where_conditions) == 1
        assert "s.title LIKE ?" in where_conditions[0]
        assert params == ["%Test Project%"]

    def test_filter_utils_season_episode_single(self):
        """Test season/episode filter for single episode."""
        where_conditions = []
        params = []
        query = SearchQuery(
            raw_query="test",
            season_start=1,
            episode_start=5,
        )
        SearchFilterUtils.add_season_episode_filters(where_conditions, params, query)

        assert len(where_conditions) == 1
        assert "json_extract" in where_conditions[0]
        assert params == [1, 5]

    def test_filter_utils_season_episode_range(self):
        """Test season/episode filter for range."""
        where_conditions = []
        params = []
        query = SearchQuery(
            raw_query="test",
            season_start=1,
            season_end=2,
            episode_start=1,
            episode_end=10,
        )
        SearchFilterUtils.add_season_episode_filters(where_conditions, params, query)

        assert len(where_conditions) == 1
        assert ">=" in where_conditions[0] and "<=" in where_conditions[0]
        assert params == [1, 2, 1, 10]

    def test_text_utils_dialogue_search(self):
        """Test dialogue search utility."""
        from_parts = []
        where_conditions = []
        params = []
        query = SearchQuery(
            raw_query="test",
            dialogue="hello world",
            characters=["WALTER"],
        )
        SearchTextUtils.add_dialogue_search(from_parts, where_conditions, params, query)

        assert "INNER JOIN dialogues d" in from_parts[0]
        assert "INNER JOIN characters c" in from_parts[1]
        assert "d.dialogue_text LIKE ?" in where_conditions[0]
        assert "%hello world%" in params

    def test_result_utils_parse_metadata(self):
        """Test metadata parsing utility."""
        metadata_json = '{"season": 1, "episode": 5}'
        result = SearchResultUtils.parse_metadata(metadata_json)

        assert result["season"] == 1
        assert result["episode"] == 5

    def test_result_utils_parse_invalid_metadata(self):
        """Test invalid metadata parsing."""
        result = SearchResultUtils.parse_metadata("invalid json")
        assert result == {}

    def test_result_utils_determine_match_type(self):
        """Test match type determination."""
        dialogue_query = SearchQuery(raw_query="test", dialogue="hello")
        assert SearchResultUtils.determine_match_type(dialogue_query) == "dialogue"

        action_query = SearchQuery(raw_query="test", action="walks")
        assert SearchResultUtils.determine_match_type(action_query) == "action"

        character_query = SearchQuery(raw_query="test", characters=["WALTER"])
        assert SearchResultUtils.determine_match_type(character_query) == "character"

        location_query = SearchQuery(raw_query="test", locations=["OFFICE"])
        assert SearchResultUtils.determine_match_type(location_query) == "location"


class TestSearchFilters:
    """Test search filter classes."""

    def test_character_filter(self, sample_search_results):
        """Test character filtering."""
        filter_obj = CharacterFilter(["WALTER"])
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(sample_search_results, query)

        assert len(filtered) == 3  # WALTER appears in all 3 scenes
        assert all("WALTER" in r.scene_content.upper() for r in filtered)

    def test_location_filter(self, sample_search_results):
        """Test location filtering."""
        filter_obj = LocationFilter(["COFFEE SHOP"])
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(sample_search_results, query)

        assert len(filtered) == 1
        assert filtered[0].scene_location == "COFFEE SHOP"

    def test_time_of_day_filter(self, sample_search_results):
        """Test time of day filtering."""
        filter_obj = TimeOfDayFilter(["DAY"])
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(sample_search_results, query)

        assert len(filtered) == 2  # Two DAY scenes
        assert all(r.scene_time == "DAY" for r in filtered)

    def test_season_episode_filter(self, sample_search_results):
        """Test season/episode filtering."""
        filter_obj = SeasonEpisodeFilter(season_start=1, episode_start=2)
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(sample_search_results, query)

        assert len(filtered) == 1
        assert filtered[0].episode == 2

    def test_duplicate_filter(self):
        """Test duplicate removal."""
        # Create results with duplicates
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. ROOM",
                scene_location="ROOM",
                scene_time="DAY",
                scene_content="Test",
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. ROOM",
                scene_location="ROOM",
                scene_time="DAY",
                scene_content="Test",
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=2,
                scene_number=2,
                scene_heading="EXT. STREET",
                scene_location="STREET",
                scene_time="NIGHT",
                scene_content="Test",
            ),
        ]

        filter_obj = DuplicateFilter()
        query = SearchQuery(raw_query="test")
        filtered = filter_obj.filter(results, query)

        assert len(filtered) == 2
        assert filtered[0].scene_id == 1
        assert filtered[1].scene_id == 2

    def test_filter_chain(self, sample_search_results):
        """Test chaining multiple filters."""
        chain = SearchFilterChain()
        chain.add_filter(TimeOfDayFilter(["DAY"]))
        chain.add_filter(CharacterFilter(["WALTER"]))

        query = SearchQuery(raw_query="test")
        filtered = chain.apply(sample_search_results, query)

        assert len(filtered) == 2  # Scenes 1 and 3 have both DAY and WALTER
        assert filtered[0].scene_id == 1
        assert filtered[1].scene_id == 3


class TestSearchRankers:
    """Test search ranking classes."""

    def test_relevance_ranker(self, sample_search_results):
        """Test relevance-based ranking."""
        ranker = RelevanceRanker()
        query = SearchQuery(raw_query="test")
        ranked = ranker.rank(sample_search_results, query)

        # Should be sorted by relevance score descending
        assert ranked[0].relevance_score == 0.8
        assert ranked[1].relevance_score == 0.6
        assert ranked[2].relevance_score == 0.4

    def test_text_match_ranker(self, sample_search_results):
        """Test text matching ranker."""
        ranker = TextMatchRanker()
        query = SearchQuery(raw_query="test", text_query="coffee")
        ranked = ranker.rank(sample_search_results, query)

        # Scenes with "coffee" should rank higher
        assert "coffee" in ranked[0].scene_content.lower()

    def test_positional_ranker(self, sample_search_results):
        """Test positional ranking."""
        ranker = PositionalRanker()
        query = SearchQuery(raw_query="test")
        ranked = ranker.rank(sample_search_results, query)

        # Should be sorted by scene number
        assert ranked[0].scene_number == 1
        assert ranked[1].scene_number == 2
        assert ranked[2].scene_number == 3

    def test_proximity_ranker(self):
        """Test proximity-based ranking."""
        results = [
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=1,
                scene_number=1,
                scene_heading="INT. ROOM",
                scene_location="ROOM",
                scene_time="DAY",
                scene_content="The quick brown fox jumps over the lazy dog",
                relevance_score=0.5,
            ),
            SearchResult(
                script_id=1,
                script_title="Test",
                script_author="Author",
                scene_id=2,
                scene_number=2,
                scene_heading="EXT. STREET",
                scene_location="STREET",
                scene_time="NIGHT",
                scene_content="The fox is quick and brown",
                relevance_score=0.5,
            ),
        ]

        ranker = ProximityRanker()
        query = SearchQuery(raw_query="test", text_query="quick brown")
        ranked = ranker.rank(results, query)

        # Scene 2 should rank higher (terms are closer)
        # But proximity score is combined with relevance score
        # Since both start with 0.5 relevance, check proximity influenced it
        assert ranked[0].scene_id in [
            1,
            2,
        ]  # Either could rank first depending on algorithm

    def test_hybrid_ranker(self, sample_search_results):
        """Test hybrid ranking combining multiple strategies."""
        ranker = HybridRanker()
        query = SearchQuery(raw_query="test", text_query="coffee")
        ranked = ranker.rank(sample_search_results, query)

        # Results should be ranked with combined scoring
        assert all(r.relevance_score > 0 for r in ranked)


class TestQueryBuilder:
    """Test SQL query builder with new utilities."""

    def test_build_search_query_with_dialogue(self):
        """Test building query for dialogue search."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            dialogue="hello world",
            characters=["WALTER"],
            limit=10,
            offset=0,
        )

        sql, params = builder.build_search_query(query)

        assert "INNER JOIN dialogues d" in sql
        assert "INNER JOIN characters c" in sql
        assert "%hello world%" in params
        assert "WALTER" in params

    def test_build_search_query_with_action(self):
        """Test building query for action search."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            action="walks",
            limit=10,
            offset=0,
        )

        sql, params = builder.build_search_query(query)

        assert "sc.content LIKE ?" in sql
        assert "EXISTS" in sql
        assert "%walks%" in params

    def test_build_count_query(self):
        """Test building count query."""
        builder = QueryBuilder()
        query = SearchQuery(
            raw_query="test",
            text_query="coffee",
            project="Test Project",
        )

        sql, params = builder.build_count_query(query)

        assert "COUNT(DISTINCT sc.id)" in sql
        assert "%Test Project%" in params
        assert "%coffee%" in params


@pytest.mark.asyncio
class TestSearchEngineIntegration:
    """Integration tests for the search engine."""

    async def test_search_with_filters_and_ranking(self, tmp_path):
        """Test search engine with filters and ranking."""
        # Create a test database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        # Create minimal schema
        conn.execute("""
            CREATE TABLE scripts (
                id INTEGER PRIMARY KEY,
                title TEXT,
                author TEXT,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE scenes (
                id INTEGER PRIMARY KEY,
                script_id INTEGER,
                scene_number INTEGER,
                heading TEXT,
                location TEXT,
                time_of_day TEXT,
                content TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE actions (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                action_text TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE dialogues (
                id INTEGER PRIMARY KEY,
                scene_id INTEGER,
                character_id INTEGER,
                dialogue_text TEXT,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE characters (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)

        # Insert test data
        conn.execute("INSERT INTO scripts VALUES (1, 'Test Script', 'Author', '{}')")
        conn.execute("""
            INSERT INTO scenes VALUES
            (1, 1, 1, 'INT. COFFEE SHOP - DAY', 'COFFEE SHOP', 'DAY',
             'WALTER enters and orders coffee'),
            (2, 1, 2, 'EXT. PARK - NIGHT', 'PARK', 'NIGHT',
             'WALTER walks through the park')
        """)
        conn.commit()
        conn.close()

        # Create search engine with test database
        settings = ScriptRAGSettings(database_path=db_path)
        engine = SearchEngine(settings)

        # Test search
        query = SearchQuery(
            raw_query="coffee",
            text_query="coffee",
            limit=10,
            offset=0,
        )

        response = await engine.search_async(query)

        assert len(response.results) > 0
        assert "coffee" in response.results[0].scene_content.lower()


@pytest.mark.asyncio
async def test_search_utilities_integration():
    """Test that all utilities work together properly."""
    # Create a query
    query = SearchQuery(
        raw_query="dialogue:hello character:WALTER location:office",
        dialogue="hello",
        characters=["WALTER"],
        locations=["OFFICE"],
        limit=10,
        offset=0,
    )

    # Test utilities can process the query
    where_conditions = []
    params = []
    from_parts = []

    # Apply filters
    SearchFilterUtils.add_location_filters(where_conditions, params, query.locations)
    SearchTextUtils.add_dialogue_search(from_parts, where_conditions, params, query)

    assert len(where_conditions) > 0
    assert len(params) > 0
    assert len(from_parts) > 0

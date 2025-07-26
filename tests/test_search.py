"""Tests for search functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.database.connection import DatabaseConnection
from scriptrag.llm.client import LLMClient
from scriptrag.search import SearchInterface, SearchResult, SearchType
from scriptrag.search.ranking import SearchRanker
from scriptrag.search.text_search import TextSearchEngine


@pytest.fixture
def mock_connection():
    """Create mock database connection."""
    conn = MagicMock(spec=DatabaseConnection)
    conn.fetch_all = MagicMock(return_value=[])
    conn.fetch_one = MagicMock(return_value=None)
    return conn


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock(spec=LLMClient)
    client.generate_embedding = AsyncMock(return_value=[0.1] * 768)
    client.generate_embeddings = AsyncMock(return_value=[[0.1] * 768])
    client.default_embedding_model = "text-embedding-ada-002"
    return client


@pytest.fixture
def search_interface(mock_connection, mock_llm_client):
    """Create search interface with mocks."""
    return SearchInterface(mock_connection, mock_llm_client)


@pytest.fixture
def text_engine(mock_connection):
    """Create text search engine with mock connection."""
    return TextSearchEngine(mock_connection)


@pytest.fixture
def ranker():
    """Create search ranker."""
    return SearchRanker()


class TestSearchInterface:
    """Test SearchInterface class."""

    @pytest.mark.asyncio
    async def test_empty_query(self, search_interface):
        """Test empty query returns no results."""
        results = await search_interface.search("")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_all_types(self, search_interface, mock_connection):
        """Test search across all content types."""
        # Mock dialogue results
        mock_connection.fetch_all.return_value = [
            {
                "id": "d1",
                "content": "Test dialogue",
                "character_name": "John",
                "order_in_scene": 1,
                "scene_id": "s1",
                "scene_heading": "INT. ROOM - DAY",
                "script_order": 1,
            }
        ]

        results = await search_interface.search("test", limit=5)

        # Verify search was called
        assert mock_connection.fetch_all.called
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_dialogue(self, search_interface, mock_connection):
        """Test dialogue-specific search."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "d1",
                "content": "Hello world",
                "character_name": "Alice",
                "order_in_scene": 1,
                "scene_id": "s1",
                "scene_heading": "INT. HOUSE - DAY",
                "script_order": 1,
            }
        ]

        results = await search_interface.search_dialogue("hello", character="Alice")

        assert len(results) == 1
        assert results[0]["type"] == "dialogue"
        assert results[0]["content"] == "Hello world"
        assert results[0]["metadata"]["character"] == "Alice"

    @pytest.mark.asyncio
    async def test_search_similar_scenes(self, search_interface):
        """Test similar scene search."""
        with patch.object(
            search_interface.embedding_pipeline,
            "get_similar_scenes",
            return_value=[
                {
                    "entity_id": "s2",
                    "text": "Similar scene",
                    "similarity": 0.85,
                    "entity_details": {
                        "heading": "INT. SIMILAR ROOM - DAY",
                        "script_order": 2,
                    },
                }
            ],
        ):
            results = await search_interface.search_similar_scenes("s1")

            assert len(results) == 1
            assert results[0]["id"] == "s2"
            assert results[0]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_search_by_theme(self, search_interface):
        """Test thematic search."""
        with patch.object(
            search_interface.embedding_pipeline,
            "semantic_search",
            return_value=[
                {
                    "entity_id": "s1",
                    "entity_type": "scene",
                    "text": "Betrayal scene",
                    "similarity": 0.75,
                    "entity_details": {},
                }
            ],
        ):
            results = await search_interface.search_by_theme("betrayal")

            assert len(results) == 1
            assert results[0]["content"] == "Betrayal scene"

    @pytest.mark.asyncio
    async def test_search_temporal(self, search_interface, mock_connection):
        """Test temporal search."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "s1",
                "heading": "INT. ROOM - NIGHT",
                "script_order": 1,
                "description": "Night scene",
                "story_time": "2023-01-01",
                "time_of_day": "NIGHT",
            }
        ]

        results = await search_interface.search_temporal(day_night="NIGHT")

        assert len(results) == 1
        assert results[0]["metadata"]["time_of_day"] == "NIGHT"

    @pytest.mark.asyncio
    async def test_close(self, search_interface):
        """Test interface cleanup."""
        await search_interface.close()
        # Should not raise any errors


class TestTextSearchEngine:
    """Test TextSearchEngine class."""

    @pytest.mark.asyncio
    async def test_search_dialogue(self, text_engine, mock_connection):
        """Test dialogue search functionality."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "d1",
                "content": "This is a test dialogue line",
                "character_name": "Bob",
                "order_in_scene": 1,
                "scene_id": "s1",
                "scene_heading": "EXT. STREET - DAY",
                "script_order": 5,
            }
        ]

        results = await text_engine.search_dialogue("test")

        assert len(results) == 1
        assert results[0]["type"] == "dialogue"
        assert "test" in results[0]["content"]
        assert results[0]["metadata"]["character"] == "Bob"

    @pytest.mark.asyncio
    async def test_search_action(self, text_engine, mock_connection):
        """Test action search functionality."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "a1",
                "content": "The door slowly opens",
                "order_in_scene": 2,
                "scene_id": "s1",
                "scene_heading": "INT. HALLWAY - NIGHT",
                "script_order": 10,
            }
        ]

        results = await text_engine.search_action("door")

        assert len(results) == 1
        assert results[0]["type"] == "action"
        assert "door" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_search_entities(self, text_engine, mock_connection):
        """Test entity search functionality."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "c1",
                "name": "John Smith",
                "description": "Main character",
                "first_appearance_scene_id": "s1",
            }
        ]
        mock_connection.fetch_one.return_value = {"count": 15}

        results = await text_engine.search_entities("John", "character")

        assert len(results) == 1
        assert results[0]["type"] == "character"
        assert results[0]["content"] == "John Smith"
        assert results[0]["metadata"]["appearance_count"] == 15

    @pytest.mark.asyncio
    async def test_search_scenes(self, text_engine, mock_connection):
        """Test scene search functionality."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "s1",
                "heading": "INT. OFFICE - DAY",
                "script_order": 1,
                "description": "A busy office environment",
                "time_of_day": "DAY",
                "location_type": "INT",
                "story_time": None,
            }
        ]

        results = await text_engine.search_scenes("office")

        assert len(results) == 1
        assert results[0]["type"] == "scene"
        assert "office" in results[0]["content"].lower()

    def test_calculate_text_score(self, text_engine):
        """Test text scoring algorithm."""
        # Exact match
        score = text_engine._calculate_text_score("test", "test")
        assert score == 1.0

        # Whole word match
        score = text_engine._calculate_text_score("test", "This is a test case")
        assert 0.8 <= score <= 1.0

        # Substring match
        score = text_engine._calculate_text_score("test", "testing 123")
        assert 0.5 <= score <= 0.9

        # No match
        score = text_engine._calculate_text_score("test", "nothing here")
        assert score == 0.0

    def test_extract_highlights(self, text_engine):
        """Test highlight extraction."""
        content = (
            "This is a long text with the word test in the middle "
            "and another test at the end."
        )
        highlights = text_engine._extract_highlights("test", content)

        assert len(highlights) >= 1
        assert "test" in highlights[0]
        # Check if we have context markers when needed
        if len(highlights) > 1:
            assert "..." in highlights[1]  # Second match should have context


class TestSearchRanker:
    """Test SearchRanker class."""

    def test_rank_results(self, ranker):
        """Test result ranking."""
        results = [
            SearchResult(
                id="1",
                type="dialogue",
                content="Test dialogue",
                score=0.5,
                metadata={"script_order": 10},
                highlights=[],
            ),
            SearchResult(
                id="2",
                type="scene",
                content="Test scene",
                score=0.7,
                metadata={"script_order": 5},
                highlights=[],
            ),
        ]

        ranked = ranker.rank_results(results, "test")

        # Scene should rank higher (higher base score + type weight)
        assert ranked[0]["id"] == "2"
        assert ranked[0]["score"] > ranked[1]["score"]

    def test_filter_results(self, ranker):
        """Test result filtering."""
        results = [
            SearchResult(
                id="1",
                type="dialogue",
                content="Low score",
                score=0.1,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="2",
                type="scene",
                content="High score",
                score=0.8,
                metadata={},
                highlights=[],
            ),
        ]

        filtered = ranker.filter_results(results, min_score=0.5)

        assert len(filtered) == 1
        assert filtered[0]["id"] == "2"

    def test_group_results_by_type(self, ranker):
        """Test grouping results by type."""
        results = [
            SearchResult(
                id="1",
                type="dialogue",
                content="Dialogue 1",
                score=0.5,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="2",
                type="dialogue",
                content="Dialogue 2",
                score=0.6,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="3",
                type="scene",
                content="Scene 1",
                score=0.7,
                metadata={},
                highlights=[],
            ),
        ]

        grouped = ranker.group_results_by_type(results)

        assert len(grouped) == 2
        assert len(grouped["dialogue"]) == 2
        assert len(grouped["scene"]) == 1

    def test_merge_results(self, ranker):
        """Test merging result sets."""
        set1 = [
            SearchResult(
                id="1",
                type="dialogue",
                content="Result 1",
                score=0.8,
                metadata={},
                highlights=[],
            )
        ]
        set2 = [
            SearchResult(
                id="2",
                type="scene",
                content="Result 2",
                score=0.9,
                metadata={},
                highlights=[],
            )
        ]

        merged = ranker.merge_results(set1, set2)

        assert len(merged) == 2
        assert merged[0]["score"] > merged[1]["score"]  # Sorted by score

    def test_deduplicate_results(self, ranker):
        """Test result deduplication."""
        results = [
            SearchResult(
                id="1",
                type="dialogue",
                content="Content",
                score=0.8,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="1",
                type="dialogue",
                content="Same ID",
                score=0.7,
                metadata={},
                highlights=[],
            ),
        ]

        deduped = ranker._deduplicate_results(results)

        assert len(deduped) == 1
        assert deduped[0]["score"] == 0.8  # Keep the first occurrence


# Integration tests
@pytest.mark.integration
class TestSearchIntegration:
    """Integration tests for search functionality."""

    @pytest.mark.asyncio
    async def test_end_to_end_search(self, mock_connection, mock_llm_client):
        """Test complete search workflow."""
        # Setup mock data
        mock_connection.fetch_all.return_value = [
            {
                "id": "d1",
                "content": "To be or not to be",
                "character_name": "Hamlet",
                "order_in_scene": 1,
                "scene_id": "s1",
                "scene_heading": "INT. CASTLE - NIGHT",
                "script_order": 50,
            }
        ]

        # Create interface and search
        interface = SearchInterface(mock_connection, mock_llm_client)
        results = await interface.search(
            "be",
            search_types=[SearchType.DIALOGUE],
            limit=10,
        )

        # Verify results
        assert len(results) > 0
        assert results[0]["type"] == "dialogue"
        assert "be" in results[0]["content"]

        await interface.close()

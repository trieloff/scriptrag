"""Tests for search interface module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scriptrag.database.connection import DatabaseConnection
from scriptrag.llm.client import LLMClient
from scriptrag.search.interface import SearchInterface
from scriptrag.search.types import SearchResult, SearchType


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


class TestSearchInterfaceInit:
    """Test SearchInterface initialization."""

    def test_init_with_llm_client(self, mock_connection, mock_llm_client):
        """Test initialization with LLM client."""
        interface = SearchInterface(mock_connection, mock_llm_client)

        assert interface.connection == mock_connection
        assert interface.text_engine is not None
        assert interface.embedding_pipeline is not None
        assert interface.ranker is not None

    def test_init_without_llm_client(self, mock_connection):
        """Test initialization without LLM client."""
        interface = SearchInterface(mock_connection)

        assert interface.connection == mock_connection
        assert interface.text_engine is not None
        assert interface.embedding_pipeline is not None
        assert interface.ranker is not None


class TestSearchInterfaceSearch:
    """Test SearchInterface main search functionality."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_results(self, search_interface):
        """Test that empty query returns empty results."""
        results = await search_interface.search("")
        assert results == []

        results = await search_interface.search("   ")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_default_types(self, search_interface):
        """Test search with all default search types."""
        with (
            patch.object(search_interface, "_search_dialogue", return_value=[]),
            patch.object(search_interface, "_search_action", return_value=[]),
            patch.object(search_interface, "_search_full_text", return_value=[]),
            patch.object(search_interface, "_search_characters", return_value=[]),
            patch.object(search_interface, "_search_locations", return_value=[]),
            patch.object(search_interface, "_search_scenes", return_value=[]),
            patch.object(search_interface, "_search_semantic", return_value=[]),
            patch.object(search_interface, "_search_temporal", return_value=[]),
        ):
            results = await search_interface.search("test query")

            # All search methods should be called when no types specified
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_specific_types(self, search_interface):
        """Test search with specific search types."""
        mock_dialogue_results = [
            SearchResult(
                id="d1",
                type="dialogue",
                content="Test dialogue",
                score=0.8,
                metadata={"character": "John"},
                highlights=["Test dialogue"],
            )
        ]

        with patch.object(
            search_interface,
            "_search_dialogue",
            return_value=mock_dialogue_results,
        ):
            results = await search_interface.search(
                "test", search_types=[SearchType.DIALOGUE]
            )

            assert len(results) >= 1
            assert results[0]["type"] == "dialogue"

    @pytest.mark.asyncio
    async def test_search_with_filters(self, search_interface):
        """Test search with entity filters."""
        entity_filter = {"character_id": "c1", "scene_id": "s1"}

        with patch.object(
            search_interface, "_search_dialogue", return_value=[]
        ) as mock_dialogue:
            await search_interface.search(
                "test",
                search_types=[SearchType.DIALOGUE],
                entity_filter=entity_filter,
            )

            mock_dialogue.assert_called_once_with("test", entity_filter)

    @pytest.mark.asyncio
    async def test_search_with_pagination(self, search_interface):
        """Test search with limit and offset."""
        mock_results = [
            SearchResult(
                id=f"r{i}",
                type="dialogue",
                content=f"Result {i}",
                score=0.9 - i * 0.1,
                metadata={},
                highlights=[],
            )
            for i in range(20)
        ]

        with (
            patch.object(
                search_interface.ranker, "rank_results", return_value=mock_results
            ),
            patch.object(
                search_interface, "_search_dialogue", return_value=mock_results
            ),
        ):
            results = await search_interface.search(
                "test",
                search_types=[SearchType.DIALOGUE],
                limit=5,
                offset=2,
            )

            assert len(results) == 5
            assert results[0]["id"] == "r2"

    @pytest.mark.asyncio
    async def test_search_with_min_score_filter(self, search_interface):
        """Test search with minimum score threshold."""
        mock_results = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="High score",
                score=0.8,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="r2",
                type="dialogue",
                content="Low score",
                score=0.3,
                metadata={},
                highlights=[],
            ),
        ]

        with (
            patch.object(
                search_interface.ranker, "rank_results", return_value=mock_results
            ),
            patch.object(
                search_interface, "_search_dialogue", return_value=mock_results
            ),
        ):
            results = await search_interface.search(
                "test", search_types=[SearchType.DIALOGUE], min_score=0.5
            )

            assert len(results) == 1
            assert results[0]["score"] == 0.8

    @pytest.mark.asyncio
    async def test_search_handles_exceptions(self, search_interface):
        """Test search handles exceptions gracefully."""
        with patch.object(
            search_interface, "_search_dialogue", side_effect=Exception("Search failed")
        ):
            results = await search_interface.search(
                "test", search_types=[SearchType.DIALOGUE]
            )

            # Should return empty results and not crash
            assert results == []


class TestSearchInterfaceSpecializedMethods:
    """Test SearchInterface specialized search methods."""

    @pytest.mark.asyncio
    async def test_search_dialogue(self, search_interface, mock_connection):
        """Test dialogue-specific search method."""
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

        results = await search_interface.search_dialogue(
            "hello", character="Alice", scene_id="s1"
        )

        assert len(results) == 1
        assert results[0]["type"] == "dialogue"
        assert results[0]["content"] == "Hello world"
        assert results[0]["metadata"]["character"] == "Alice"

    @pytest.mark.asyncio
    async def test_search_similar_scenes(self, search_interface):
        """Test similar scene search."""
        mock_similar_scenes = [
            {
                "entity_id": "s2",
                "content": "Similar scene content",
                "similarity": 0.85,
                "entity_details": {
                    "heading": "INT. SIMILAR ROOM - DAY",
                    "script_order": 2,
                },
            }
        ]

        with patch.object(
            search_interface.embedding_pipeline,
            "get_similar_scenes",
            return_value=mock_similar_scenes,
        ):
            results = await search_interface.search_similar_scenes(
                "s1", limit=5, min_similarity=0.8
            )

            assert len(results) == 1
            assert results[0]["id"] == "s2"
            assert results[0]["score"] == 0.85
            assert results[0]["type"] == "scene"

    @pytest.mark.asyncio
    async def test_search_similar_scenes_handles_exception(self, search_interface):
        """Test similar scene search handles exceptions."""
        with patch.object(
            search_interface.embedding_pipeline,
            "get_similar_scenes",
            side_effect=Exception("Pipeline error"),
        ):
            results = await search_interface.search_similar_scenes("s1")

            assert results == []

    @pytest.mark.asyncio
    async def test_search_by_theme(self, search_interface):
        """Test thematic search."""
        mock_semantic_results = [
            {
                "entity_id": "s1",
                "entity_type": "scene",
                "content": "Betrayal scene content",
                "similarity": 0.75,
                "entity_details": {"mood": "dark"},
            }
        ]

        with patch.object(
            search_interface.embedding_pipeline,
            "semantic_search",
            return_value=mock_semantic_results,
        ):
            results = await search_interface.search_by_theme(
                "betrayal", entity_type="scene"
            )

            assert len(results) == 1
            assert results[0]["content"] == "Betrayal scene content"
            assert results[0]["score"] == 0.75

    @pytest.mark.asyncio
    async def test_search_temporal(self, search_interface, mock_connection):
        """Test temporal search."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "s1",
                "heading": "INT. ROOM - NIGHT",
                "script_order": 1,
                "description": "Night scene",
                "story_time": "2023-01-01T20:00:00",
                "time_of_day": "NIGHT",
            }
        ]

        results = await search_interface.search_temporal(
            time_range=("19:00:00", "23:00:00"), day_night="NIGHT"
        )

        assert len(results) == 1
        assert results[0]["metadata"]["time_of_day"] == "NIGHT"
        assert results[0]["type"] == "scene"


class TestSearchInterfacePrivateMethods:
    """Test SearchInterface private methods."""

    @pytest.mark.asyncio
    async def test_search_dialogue_private(self, search_interface):
        """Test private dialogue search method."""
        with patch.object(
            search_interface.text_engine, "search_dialogue"
        ) as mock_search:
            mock_search.return_value = []

            await search_interface._search_dialogue("test", {"character": "John"})

            mock_search.assert_called_once_with("test", {"character": "John"}, 10)

    @pytest.mark.asyncio
    async def test_search_semantic_private(self, search_interface):
        """Test private semantic search method."""
        mock_results = [
            {
                "entity_id": "e1",
                "entity_type": "dialogue",
                "content": "Test content",
                "similarity": 0.8,
                "entity_details": {},
            }
        ]

        with patch.object(
            search_interface.embedding_pipeline,
            "semantic_search",
            return_value=mock_results,
        ):
            results = await search_interface._search_semantic("test")

            assert len(results) == 1
            assert results[0]["id"] == "e1"
            assert results[0]["type"] == "dialogue"
            assert results[0]["score"] == 0.8

    @pytest.mark.asyncio
    async def test_search_temporal_private(self, search_interface, mock_connection):
        """Test private temporal search method."""
        mock_connection.fetch_all.return_value = [
            {
                "id": "s1",
                "heading": "INT. OFFICE - DAY",
                "script_order": 5,
                "description": "Office scene",
                "story_time": "2023-01-01T09:00:00",
                "time_of_day": "DAY",
            }
        ]

        results = await search_interface._search_temporal(
            "", {"time_range": ("08:00:00", "17:00:00")}
        )

        assert len(results) == 1
        assert results[0]["score"] == 1.0  # Temporal search uses fixed score


class TestSearchInterfaceResourceManagement:
    """Test SearchInterface resource management."""

    @pytest.mark.asyncio
    async def test_close_cleanup(self, search_interface):
        """Test interface cleanup and resource closing."""
        with patch.object(search_interface.embedding_pipeline, "close") as mock_close:
            await search_interface.close()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_none_pipeline(self, mock_connection):
        """Test close handles None embedding pipeline."""
        interface = SearchInterface(mock_connection)
        interface.embedding_pipeline = None

        # Should not raise exception
        await interface.close()


class TestSearchInterfaceEdgeCases:
    """Test SearchInterface edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_search_with_empty_search_types(self, search_interface):
        """Test search with empty search types list."""
        results = await search_interface.search("test", search_types=[])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_with_none_entity_filter(self, search_interface):
        """Test search with None entity filter."""
        with patch.object(search_interface, "_search_dialogue", return_value=[]):
            results = await search_interface.search(
                "test",
                search_types=[SearchType.DIALOGUE],
                entity_filter=None,
            )
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_invalid_limit(self, search_interface):
        """Test search with invalid limit values."""
        with patch.object(search_interface, "_search_dialogue", return_value=[]):
            # Negative limit should be handled gracefully
            results = await search_interface.search(
                "test", search_types=[SearchType.DIALOGUE], limit=-1
            )
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_concurrent_searches(self, search_interface):
        """Test concurrent search operations."""

        async def search_task(query_suffix):
            return await search_interface.search(f"test{query_suffix}")

        with patch.object(search_interface, "_search_dialogue", return_value=[]):
            # Run multiple searches concurrently
            tasks = [search_task(i) for i in range(5)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            assert all(isinstance(r, list) for r in results)


# Integration tests
@pytest.mark.integration
class TestSearchInterfaceIntegration:
    """Integration tests for search interface."""

    @pytest.mark.asyncio
    async def test_end_to_end_search_workflow(self, mock_connection, mock_llm_client):
        """Test complete search workflow from query to results."""
        # Setup mock data
        mock_connection.fetch_all.return_value = [
            {
                "id": "d1",
                "content": "To be or not to be, that is the question",
                "character_name": "Hamlet",
                "order_in_scene": 1,
                "scene_id": "s1",
                "scene_heading": "INT. CASTLE - NIGHT",
                "script_order": 50,
            }
        ]

        # Create interface and perform search
        interface = SearchInterface(mock_connection, mock_llm_client)

        results = await interface.search(
            "be",
            search_types=[SearchType.DIALOGUE],
            entity_filter={"character": "Hamlet"},
            limit=10,
            min_score=0.1,
        )

        # Verify results structure and content
        assert len(results) > 0
        result = results[0]
        assert result["type"] == "dialogue"
        assert "be" in result["content"]
        assert result["metadata"]["character"] == "Hamlet"
        assert "score" in result
        assert "highlights" in result

        await interface.close()

    @pytest.mark.asyncio
    async def test_search_performance_with_large_results(
        self, mock_connection, mock_llm_client
    ):
        """Test search performance with large result sets."""
        # Generate large mock dataset
        large_dataset = [
            {
                "id": f"d{i}",
                "content": f"This is dialogue number {i} with test content",
                "character_name": f"Character{i % 10}",
                "order_in_scene": i,
                "scene_id": f"s{i // 10}",
                "scene_heading": f"INT. LOCATION{i} - DAY",
                "script_order": i,
            }
            for i in range(1000)
        ]

        mock_connection.fetch_all.return_value = large_dataset

        interface = SearchInterface(mock_connection, mock_llm_client)

        # Search should complete in reasonable time
        import time

        start_time = time.time()

        results = await interface.search(
            "test", search_types=[SearchType.DIALOGUE], limit=50
        )

        end_time = time.time()

        # Verify results and performance
        assert len(results) <= 50  # Pagination working
        assert end_time - start_time < 5.0  # Reasonable performance

        await interface.close()

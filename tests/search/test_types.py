"""Tests for search types module."""

from scriptrag.search.types import SearchResult, SearchResults, SearchType


class TestSearchType:
    """Test SearchType enum."""

    def test_search_type_values(self):
        """Test SearchType enum has expected values."""
        assert SearchType.DIALOGUE == "dialogue"
        assert SearchType.ACTION == "action"
        assert SearchType.CHARACTER == "character"
        assert SearchType.LOCATION == "location"
        assert SearchType.OBJECT == "object"
        assert SearchType.SCENE == "scene"
        assert SearchType.SEMANTIC == "semantic"
        assert SearchType.SIMILARITY == "similarity"
        assert SearchType.TEMPORAL == "temporal"
        assert SearchType.FULL_TEXT == "full_text"

    def test_search_type_is_string_enum(self):
        """Test SearchType inherits from str."""
        assert isinstance(SearchType.DIALOGUE, str)
        assert SearchType.DIALOGUE == "dialogue"

    def test_search_type_iteration(self):
        """Test SearchType can be iterated."""
        all_types = list(SearchType)
        assert len(all_types) == 10
        assert SearchType.DIALOGUE in all_types
        assert SearchType.FULL_TEXT in all_types

    def test_search_type_comparison(self):
        """Test SearchType comparison operations."""
        assert SearchType.DIALOGUE == SearchType.DIALOGUE
        assert SearchType.DIALOGUE != SearchType.ACTION
        assert SearchType.DIALOGUE == "dialogue"
        assert SearchType.DIALOGUE != "action"

    def test_search_type_in_container(self):
        """Test SearchType can be used in containers."""
        search_types = {SearchType.DIALOGUE, SearchType.ACTION}
        assert SearchType.DIALOGUE in search_types
        assert SearchType.CHARACTER not in search_types

        search_list = [SearchType.SCENE, SearchType.LOCATION]
        assert SearchType.SCENE in search_list
        assert SearchType.DIALOGUE not in search_list

    def test_search_type_string_operations(self):
        """Test SearchType supports string operations."""
        assert SearchType.DIALOGUE.upper() == "DIALOGUE"
        assert SearchType.DIALOGUE.startswith("dia")
        assert SearchType.DIALOGUE.replace("dia", "mono") == "monologue"


class TestSearchResult:
    """Test SearchResult TypedDict."""

    def test_search_result_creation(self):
        """Test creating a valid SearchResult."""
        result = SearchResult(
            id="test_id",
            type="dialogue",
            content="Test content",
            score=0.85,
            metadata={"character": "John", "scene": "s1"},
            highlights=["Test content", "highlighted text"],
        )

        assert result["id"] == "test_id"
        assert result["type"] == "dialogue"
        assert result["content"] == "Test content"
        assert result["score"] == 0.85
        assert result["metadata"]["character"] == "John"
        assert len(result["highlights"]) == 2

    def test_search_result_required_fields(self):
        """Test SearchResult with all required fields."""
        result = SearchResult(
            id="r1",
            type="scene",
            content="INT. OFFICE - DAY",
            score=0.9,
            metadata={},
            highlights=[],
        )

        assert "id" in result
        assert "type" in result
        assert "content" in result
        assert "score" in result
        assert "metadata" in result
        assert "highlights" in result

    def test_search_result_metadata_types(self):
        """Test SearchResult metadata can contain various types."""
        metadata = {
            "string_field": "text",
            "int_field": 42,
            "float_field": 3.14,
            "bool_field": True,
            "list_field": [1, 2, 3],
            "dict_field": {"nested": "value"},
            "none_field": None,
        }

        result = SearchResult(
            id="r1",
            type="character",
            content="Character Name",
            score=0.7,
            metadata=metadata,
            highlights=[],
        )

        assert result["metadata"]["string_field"] == "text"
        assert result["metadata"]["int_field"] == 42
        assert result["metadata"]["float_field"] == 3.14
        assert result["metadata"]["bool_field"] is True
        assert result["metadata"]["list_field"] == [1, 2, 3]
        assert result["metadata"]["dict_field"]["nested"] == "value"
        assert result["metadata"]["none_field"] is None

    def test_search_result_empty_collections(self):
        """Test SearchResult with empty collections."""
        result = SearchResult(
            id="r1",
            type="action",
            content="Action description",
            score=0.6,
            metadata={},
            highlights=[],
        )

        assert isinstance(result["metadata"], dict)
        assert len(result["metadata"]) == 0
        assert isinstance(result["highlights"], list)
        assert len(result["highlights"]) == 0

    def test_search_result_highlights_list(self):
        """Test SearchResult highlights as list of strings."""
        highlights = [
            "First highlight snippet",
            "Second highlight with context",
            "...third partial highlight...",
        ]

        result = SearchResult(
            id="r1",
            type="dialogue",
            content="Full dialogue content",
            score=0.8,
            metadata={},
            highlights=highlights,
        )

        assert len(result["highlights"]) == 3
        assert all(isinstance(h, str) for h in result["highlights"])
        assert result["highlights"][0] == "First highlight snippet"

    def test_search_result_score_range(self):
        """Test SearchResult with various score values."""
        # Test different score values
        test_scores = [0.0, 0.1, 0.5, 0.999, 1.0]

        for score in test_scores:
            result = SearchResult(
                id=f"r_{score}",
                type="test",
                content="content",
                score=score,
                metadata={},
                highlights=[],
            )
            assert result["score"] == score

    def test_search_result_modification(self):
        """Test SearchResult can be modified after creation."""
        result = SearchResult(
            id="r1",
            type="dialogue",
            content="Original content",
            score=0.5,
            metadata={"original": True},
            highlights=["original"],
        )

        # Modify the result
        result["content"] = "Modified content"
        result["score"] = 0.9
        result["metadata"]["modified"] = True
        result["highlights"].append("new highlight")

        assert result["content"] == "Modified content"
        assert result["score"] == 0.9
        assert result["metadata"]["modified"] is True
        assert "new highlight" in result["highlights"]

    def test_search_result_dict_access(self):
        """Test SearchResult supports dict-like access."""
        result = SearchResult(
            id="r1",
            type="location",
            content="COFFEE SHOP",
            score=0.7,
            metadata={"interior": True},
            highlights=[],
        )

        # Test dict methods
        assert "id" in result
        assert result.get("type") == "location"
        assert result.get("nonexistent", "default") == "default"

        # Test keys, values, items
        assert "score" in result
        assert 0.7 in result.values()
        assert ("type", "location") in result.items()

    def test_search_result_copy(self):
        """Test SearchResult can be copied."""
        original = SearchResult(
            id="r1",
            type="scene",
            content="Scene content",
            score=0.8,
            metadata={"key": "value"},
            highlights=["highlight"],
        )

        # Test dict copy
        copied = dict(original)

        assert copied["id"] == original["id"]
        assert copied["metadata"]["key"] == "value"

        # Modify copy shouldn't affect original (need to copy metadata dict too)
        copied["id"] = "r2"
        copied["metadata"] = dict(copied["metadata"])  # Copy nested dict
        copied["metadata"]["new"] = "added"

        assert original["id"] == "r1"
        assert "new" not in original["metadata"]


class TestSearchResults:
    """Test SearchResults type alias."""

    def test_search_results_empty_list(self):
        """Test SearchResults as empty list."""
        results: SearchResults = []
        assert isinstance(results, list)
        assert len(results) == 0

    def test_search_results_with_results(self):
        """Test SearchResults with actual search results."""
        results: SearchResults = [
            SearchResult(
                id="r1",
                type="dialogue",
                content="First result",
                score=0.9,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="r2",
                type="scene",
                content="Second result",
                score=0.8,
                metadata={},
                highlights=[],
            ),
        ]

        assert len(results) == 2
        assert results[0]["id"] == "r1"
        assert results[1]["id"] == "r2"

    def test_search_results_list_operations(self):
        """Test SearchResults supports list operations."""
        results: SearchResults = []

        # Test append
        result1 = SearchResult(
            id="r1",
            type="action",
            content="Action content",
            score=0.7,
            metadata={},
            highlights=[],
        )
        results.append(result1)
        assert len(results) == 1

        # Test extend
        more_results = [
            SearchResult(
                id="r2",
                type="character",
                content="Character name",
                score=0.6,
                metadata={},
                highlights=[],
            )
        ]
        results.extend(more_results)
        assert len(results) == 2

        # Test sorting
        results.sort(key=lambda x: x["score"], reverse=True)
        assert results[0]["score"] >= results[1]["score"]

        # Test filtering
        high_scores = [r for r in results if r["score"] > 0.6]
        assert len(high_scores) == 1

    def test_search_results_iteration(self):
        """Test SearchResults can be iterated."""
        results: SearchResults = [
            SearchResult(
                id=f"r{i}",
                type="test",
                content=f"Content {i}",
                score=i * 0.1,
                metadata={},
                highlights=[],
            )
            for i in range(5)
        ]

        # Test iteration
        ids = [r["id"] for r in results]
        assert ids == ["r0", "r1", "r2", "r3", "r4"]

        # Test enumeration
        for i, result in enumerate(results):
            assert result["id"] == f"r{i}"

    def test_search_results_slicing(self):
        """Test SearchResults supports slicing."""
        results: SearchResults = [
            SearchResult(
                id=f"r{i}",
                type="test",
                content=f"Content {i}",
                score=i * 0.1,
                metadata={},
                highlights=[],
            )
            for i in range(10)
        ]

        # Test slicing
        first_three = results[:3]
        assert len(first_three) == 3
        assert first_three[0]["id"] == "r0"

        last_three = results[-3:]
        assert len(last_three) == 3
        assert last_three[0]["id"] == "r7"

        middle = results[2:5]
        assert len(middle) == 3
        assert middle[0]["id"] == "r2"

    def test_search_results_type_consistency(self):
        """Test SearchResults maintains type consistency."""
        results: SearchResults = []

        # All items should be SearchResult-compatible
        valid_result = SearchResult(
            id="r1",
            type="dialogue",
            content="Content",
            score=0.8,
            metadata={},
            highlights=[],
        )
        results.append(valid_result)

        # Verify type consistency
        for result in results:
            assert "id" in result
            assert "type" in result
            assert "content" in result
            assert "score" in result
            assert "metadata" in result
            assert "highlights" in result
            assert isinstance(result["metadata"], dict)
            assert isinstance(result["highlights"], list)


class TestSearchTypesIntegration:
    """Test integration between different search types."""

    def test_search_type_in_search_result(self):
        """Test using SearchType enum in SearchResult."""
        result = SearchResult(
            id="r1",
            type=SearchType.DIALOGUE,  # Using enum
            content="Dialogue content",
            score=0.8,
            metadata={},
            highlights=[],
        )

        assert result["type"] == "dialogue"
        assert result["type"] == SearchType.DIALOGUE

    def test_search_results_filtering_by_type(self):
        """Test filtering SearchResults by SearchType."""
        results: SearchResults = [
            SearchResult(
                id="d1",
                type=SearchType.DIALOGUE,
                content="Dialogue",
                score=0.8,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="s1",
                type=SearchType.SCENE,
                content="Scene",
                score=0.7,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="a1",
                type=SearchType.ACTION,
                content="Action",
                score=0.6,
                metadata={},
                highlights=[],
            ),
        ]

        # Filter by type
        dialogues = [r for r in results if r["type"] == SearchType.DIALOGUE]
        assert len(dialogues) == 1
        assert dialogues[0]["id"] == "d1"

        # Filter by multiple types
        narrative_types = {SearchType.SCENE, SearchType.ACTION}
        narrative_results = [r for r in results if r["type"] in narrative_types]
        assert len(narrative_results) == 2

    def test_search_results_grouping_by_type(self):
        """Test grouping SearchResults by type."""
        results: SearchResults = [
            SearchResult(
                id="d1",
                type=SearchType.DIALOGUE,
                content="First dialogue",
                score=0.9,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="d2",
                type=SearchType.DIALOGUE,
                content="Second dialogue",
                score=0.8,
                metadata={},
                highlights=[],
            ),
            SearchResult(
                id="s1",
                type=SearchType.SCENE,
                content="Scene content",
                score=0.7,
                metadata={},
                highlights=[],
            ),
        ]

        # Group by type
        grouped = {}
        for result in results:
            result_type = result["type"]
            if result_type not in grouped:
                grouped[result_type] = []
            grouped[result_type].append(result)

        assert len(grouped[SearchType.DIALOGUE]) == 2
        assert len(grouped[SearchType.SCENE]) == 1
        assert SearchType.ACTION not in grouped

    def test_comprehensive_search_result_creation(self):
        """Test creating comprehensive SearchResult with all features."""
        result = SearchResult(
            id="comprehensive_test",
            type=SearchType.SEMANTIC,
            content="This is a comprehensive test of the search result type",
            score=0.95,
            metadata={
                "character": "Test Character",
                "scene_id": "scene_123",
                "scene_heading": "INT. TEST ROOM - DAY",
                "script_order": 42,
                "element_order": 5,
                "appearance_count": 15,
                "similarity": 0.87,
                "embedding_model": "text-embedding-ada-002",
                "search_query": "comprehensive test",
                "timestamp": "2024-01-01T12:00:00Z",
                "custom_data": {
                    "nested_field": "nested_value",
                    "flags": ["important", "reviewed"],
                },
            },
            highlights=[
                "...comprehensive test of the search...",
                "semantic search type",
                "Test Character speaks about...",
            ],
        )

        # Verify all aspects work correctly
        assert result["type"] == SearchType.SEMANTIC
        assert result["score"] == 0.95
        assert len(result["metadata"]) > 5
        assert len(result["highlights"]) == 3
        assert result["metadata"]["custom_data"]["flags"][0] == "important"

    def test_edge_case_values(self):
        """Test SearchResult with edge case values."""
        result = SearchResult(
            id="",  # Empty string ID
            type=SearchType.OBJECT,
            content="",  # Empty content
            score=0.0,  # Minimum score
            metadata={"empty_string": "", "zero": 0, "false": False},
            highlights=[],  # Empty highlights
        )

        assert result["id"] == ""
        assert result["content"] == ""
        assert result["score"] == 0.0
        assert result["metadata"]["empty_string"] == ""
        assert result["metadata"]["zero"] == 0
        assert result["metadata"]["false"] is False
        assert len(result["highlights"]) == 0

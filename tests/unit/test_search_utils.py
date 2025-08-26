"""Unit tests for search utilities module achieving comprehensive coverage."""

from unittest.mock import MagicMock

from scriptrag.search.models import SearchQuery, SearchResult
from scriptrag.search.utils import (
    SearchFilterUtils,
    SearchResultUtils,
    SearchTextUtils,
)


class TestSearchFilterUtils:
    """Test SearchFilterUtils functionality."""

    def test_add_project_filter_none(self) -> None:
        """Test adding project filter when project is None."""
        where_conditions: list[str] = []
        params: list[str] = []

        SearchFilterUtils.add_project_filter(where_conditions, params, None)

        assert where_conditions == []
        assert params == []

    def test_add_project_filter_empty_string(self) -> None:
        """Test adding project filter when project is empty string."""
        where_conditions: list[str] = []
        params: list[str] = []

        SearchFilterUtils.add_project_filter(where_conditions, params, "")

        assert where_conditions == []
        assert params == []

    def test_add_project_filter_with_project(self) -> None:
        """Test adding project filter with valid project name."""
        where_conditions: list[str] = []
        params: list[str] = []

        SearchFilterUtils.add_project_filter(where_conditions, params, "Test Project")

        assert where_conditions == ["s.title LIKE ?"]
        assert params == ["%Test Project%"]

    def test_add_season_episode_filters_none(self) -> None:
        """Test adding season/episode filters when no season is specified."""
        where_conditions: list[str] = []
        params: list[int] = []
        search_query = SearchQuery(raw_query="test")

        SearchFilterUtils.add_season_episode_filters(
            where_conditions, params, search_query
        )

        assert where_conditions == []
        assert params == []

    def test_add_season_episode_filters_single_episode(self) -> None:
        """Test adding season/episode filters for single episode."""
        where_conditions: list[str] = []
        params: list[int] = []
        search_query = SearchQuery(raw_query="test", season_start=2, episode_start=5)

        SearchFilterUtils.add_season_episode_filters(
            where_conditions, params, search_query
        )

        assert len(where_conditions) == 1
        assert "json_extract(s.metadata, '$.season') = ?" in where_conditions[0]
        assert "json_extract(s.metadata, '$.episode') = ?" in where_conditions[0]
        assert params == [2, 5]

    def test_add_season_episode_filters_range(self) -> None:
        """Test adding season/episode filters for episode range."""
        where_conditions: list[str] = []
        params: list[int] = []
        search_query = SearchQuery(
            raw_query="test",
            season_start=1,
            season_end=3,
            episode_start=2,
            episode_end=8,
        )

        SearchFilterUtils.add_season_episode_filters(
            where_conditions, params, search_query
        )

        assert len(where_conditions) == 1
        assert "json_extract(s.metadata, '$.season') >= ?" in where_conditions[0]
        assert "json_extract(s.metadata, '$.season') <= ?" in where_conditions[0]
        assert "json_extract(s.metadata, '$.episode') >= ?" in where_conditions[0]
        assert "json_extract(s.metadata, '$.episode') <= ?" in where_conditions[0]
        assert params == [1, 3, 2, 8]

    def test_add_location_filters_none(self) -> None:
        """Test adding location filters when locations is None."""
        where_conditions: list[str] = []
        params: list[str] = []

        SearchFilterUtils.add_location_filters(where_conditions, params, None)

        assert where_conditions == []
        assert params == []

    def test_add_location_filters_empty_list(self) -> None:
        """Test adding location filters when locations is empty list."""
        where_conditions: list[str] = []
        params: list[str] = []

        SearchFilterUtils.add_location_filters(where_conditions, params, [])

        assert where_conditions == []
        assert params == []

    def test_add_location_filters_single_location(self) -> None:
        """Test adding location filters with single location."""
        where_conditions: list[str] = []
        params: list[str] = []

        SearchFilterUtils.add_location_filters(where_conditions, params, ["OFFICE"])

        assert where_conditions == ["(sc.location LIKE ?)"]
        assert params == ["%OFFICE%"]

    def test_add_location_filters_multiple_locations(self) -> None:
        """Test adding location filters with multiple locations."""
        where_conditions: list[str] = []
        params: list[str] = []

        SearchFilterUtils.add_location_filters(
            where_conditions, params, ["OFFICE", "KITCHEN", "BEDROOM"]
        )

        assert len(where_conditions) == 1
        assert "sc.location LIKE ?" in where_conditions[0]
        assert "OR" in where_conditions[0]
        assert params == ["%OFFICE%", "%KITCHEN%", "%BEDROOM%"]

    def test_add_character_filter_empty_list(self) -> None:
        """Test adding character filter with empty character list."""
        where_conditions: list[str] = []
        params: list[str] = []

        SearchFilterUtils.add_character_filter(where_conditions, params, [])

        assert where_conditions == []
        assert params == []

    def test_add_character_filter_single_character(self) -> None:
        """Test adding character filter with single character."""
        where_conditions: list[str] = []
        params: list[str] = []

        SearchFilterUtils.add_character_filter(where_conditions, params, ["JOHN"])

        assert len(where_conditions) == 1
        assert "EXISTS" in where_conditions[0]
        assert "dialogues d" in where_conditions[0]
        assert "characters c" in where_conditions[0]
        assert "c.name = ?" in where_conditions[0]
        assert params == ["JOHN"]

    def test_add_character_filter_multiple_characters(self) -> None:
        """Test adding character filter with multiple characters."""
        where_conditions: list[str] = []
        params: list[str] = []

        SearchFilterUtils.add_character_filter(
            where_conditions, params, ["JOHN", "SARAH", "MIKE"]
        )

        assert len(where_conditions) == 1
        assert "EXISTS" in where_conditions[0]
        assert "OR" in where_conditions[0]
        assert params == ["JOHN", "SARAH", "MIKE"]

    def test_add_character_filter_custom_scene_alias(self) -> None:
        """Test adding character filter with custom scene alias."""
        where_conditions: list[str] = []
        params: list[str] = []

        SearchFilterUtils.add_character_filter(
            where_conditions, params, ["DETECTIVE"], scene_alias="scenes"
        )

        assert len(where_conditions) == 1
        assert "scenes.id" in where_conditions[0]
        assert "d.scene_id = scenes.id" in where_conditions[0]
        assert params == ["DETECTIVE"]


class TestSearchTextUtils:
    """Test SearchTextUtils functionality."""

    def test_add_dialogue_search_no_dialogue(self) -> None:
        """Test adding dialogue search when no dialogue specified."""
        from_parts: list[str] = []
        where_conditions: list[str] = []
        params: list[str] = []
        search_query = SearchQuery(raw_query="test")

        SearchTextUtils.add_dialogue_search(
            from_parts, where_conditions, params, search_query
        )

        assert from_parts == []
        assert where_conditions == []
        assert params == []

    def test_add_dialogue_search_basic(self) -> None:
        """Test adding dialogue search with basic dialogue."""
        from_parts: list[str] = []
        where_conditions: list[str] = []
        params: list[str] = []
        search_query = SearchQuery(raw_query="test", dialogue="hello world")

        SearchTextUtils.add_dialogue_search(
            from_parts, where_conditions, params, search_query
        )

        assert "INNER JOIN dialogues d ON sc.id = d.scene_id" in from_parts
        assert "d.dialogue_text LIKE ?" in where_conditions
        assert "%hello world%" in params

    def test_add_dialogue_search_with_characters(self) -> None:
        """Test adding dialogue search with character filter."""
        from_parts: list[str] = []
        where_conditions: list[str] = []
        params: list[str] = []
        search_query = SearchQuery(
            raw_query="test", dialogue="hello", characters=["JOHN", "SARAH"]
        )

        SearchTextUtils.add_dialogue_search(
            from_parts, where_conditions, params, search_query
        )

        assert "INNER JOIN dialogues d ON sc.id = d.scene_id" in from_parts
        assert "INNER JOIN characters c ON d.character_id = c.id" in from_parts
        assert "d.dialogue_text LIKE ?" in where_conditions
        assert "c.name = ?" in where_conditions[1]
        assert "%hello%" in params
        assert "JOHN" in params
        assert "SARAH" in params

    def test_add_dialogue_search_with_parenthetical(self) -> None:
        """Test adding dialogue search with parenthetical filter."""
        from_parts: list[str] = []
        where_conditions: list[str] = []
        params: list[str] = []
        search_query = SearchQuery(
            raw_query="test", dialogue="hello", parenthetical="whisper"
        )

        SearchTextUtils.add_dialogue_search(
            from_parts, where_conditions, params, search_query
        )

        assert "INNER JOIN dialogues d ON sc.id = d.scene_id" in from_parts
        assert "d.dialogue_text LIKE ?" in where_conditions
        assert "json_extract(d.metadata, '$.parenthetical') LIKE ?" in where_conditions
        assert "%hello%" in params
        assert "%whisper%" in params

    def test_add_dialogue_search_empty_characters(self) -> None:
        """Test dialogue search with empty characters list."""
        from_parts: list[str] = []
        where_conditions: list[str] = []
        params: list[str] = []
        search_query = SearchQuery(raw_query="test", dialogue="hello", characters=[])

        SearchTextUtils.add_dialogue_search(
            from_parts, where_conditions, params, search_query
        )

        assert "INNER JOIN dialogues d ON sc.id = d.scene_id" in from_parts
        # Should not add character join for empty list
        assert not any("characters c" in part for part in from_parts)
        assert "d.dialogue_text LIKE ?" in where_conditions
        assert "%hello%" in params

    def test_add_action_search_no_query(self) -> None:
        """Test adding action search when no query specified."""
        where_conditions: list[str] = []
        params: list[str] = []
        search_query = SearchQuery(raw_query="test")

        SearchTextUtils.add_action_search(where_conditions, params, search_query)

        assert where_conditions == []
        assert params == []

    def test_add_action_search_text_query(self) -> None:
        """Test adding action search with text query."""
        where_conditions: list[str] = []
        params: list[str] = []
        search_query = SearchQuery(raw_query="test", text_query="explosion")

        SearchTextUtils.add_action_search(where_conditions, params, search_query)

        assert len(where_conditions) == 1
        assert "sc.content LIKE ?" in where_conditions[0]
        assert "EXISTS" in where_conditions[0]
        assert "actions a" in where_conditions[0]
        assert "a.action_text LIKE ?" in where_conditions[0]
        assert "%explosion%" in params
        assert params.count("%explosion%") == 2  # Used in both conditions

    def test_add_action_search_action_query(self) -> None:
        """Test adding action search with action query."""
        where_conditions: list[str] = []
        params: list[str] = []
        search_query = SearchQuery(raw_query="test", action="walks away")

        SearchTextUtils.add_action_search(where_conditions, params, search_query)

        assert len(where_conditions) == 1
        assert "sc.content LIKE ?" in where_conditions[0]
        assert "EXISTS" in where_conditions[0]
        assert "actions a" in where_conditions[0]
        assert "%walks away%" in params
        assert params.count("%walks away%") == 2

    def test_add_action_search_with_characters(self) -> None:
        """Test adding action search with character filter."""
        where_conditions: list[str] = []
        params: list[str] = []
        search_query = SearchQuery(raw_query="test", action="runs", characters=["HERO"])

        SearchTextUtils.add_action_search(where_conditions, params, search_query)

        assert len(where_conditions) == 2
        assert "sc.content LIKE ?" in where_conditions[0]
        assert "EXISTS" in where_conditions[1]  # Character filter
        assert "dialogues d" in where_conditions[1]
        assert "c.name = ?" in where_conditions[1]
        assert "%runs%" in params
        assert "HERO" in params


class TestSearchResultUtils:
    """Test SearchResultUtils functionality."""

    def test_parse_metadata_none(self) -> None:
        """Test parsing None metadata."""
        result = SearchResultUtils.parse_metadata(None)
        assert result == {}

    def test_parse_metadata_empty_string(self) -> None:
        """Test parsing empty string metadata."""
        result = SearchResultUtils.parse_metadata("")
        assert result == {}

    def test_parse_metadata_valid_json(self) -> None:
        """Test parsing valid JSON metadata."""
        metadata_json = '{"season": 2, "episode": 5, "writer": "Jane Doe"}'
        result = SearchResultUtils.parse_metadata(metadata_json)

        assert result == {"season": 2, "episode": 5, "writer": "Jane Doe"}

    def test_parse_metadata_invalid_json(self) -> None:
        """Test parsing invalid JSON metadata."""
        result = SearchResultUtils.parse_metadata("not valid json")
        assert result == {}

    def test_parse_metadata_invalid_json_with_context(self) -> None:
        """Test parsing invalid JSON with row context for logging."""
        row_context = {"script_id": 123, "row_index": 5}
        result = SearchResultUtils.parse_metadata("invalid json", row_context)
        assert result == {}

    def test_parse_metadata_type_error(self) -> None:
        """Test parsing metadata that causes TypeError."""
        # This could happen if metadata_json is not actually a string
        result = SearchResultUtils.parse_metadata('{"unclosed": string}')
        assert result == {}

    def test_determine_match_type_dialogue(self) -> None:
        """Test match type determination for dialogue query."""
        query = SearchQuery(raw_query="test", dialogue="hello")
        result = SearchResultUtils.determine_match_type(query)
        assert result == "dialogue"

    def test_determine_match_type_action(self) -> None:
        """Test match type determination for action query."""
        query = SearchQuery(raw_query="test", action="fight")
        result = SearchResultUtils.determine_match_type(query)
        assert result == "action"

    def test_determine_match_type_text(self) -> None:
        """Test match type determination for text query."""
        query = SearchQuery(raw_query="test", text_query="general")
        result = SearchResultUtils.determine_match_type(query)
        assert result == "text"

    def test_determine_match_type_character(self) -> None:
        """Test match type determination for character query."""
        query = SearchQuery(raw_query="test", characters=["JOHN"])
        result = SearchResultUtils.determine_match_type(query)
        assert result == "character"

    def test_determine_match_type_location(self) -> None:
        """Test match type determination for location query."""
        query = SearchQuery(raw_query="test", locations=["OFFICE"])
        result = SearchResultUtils.determine_match_type(query)
        assert result == "location"

    def test_determine_match_type_default(self) -> None:
        """Test match type determination for default case."""
        query = SearchQuery(raw_query="test")
        result = SearchResultUtils.determine_match_type(query)
        assert result == "text"

    def test_determine_match_type_priority_dialogue(self) -> None:
        """Test match type priority - dialogue has highest priority."""
        query = SearchQuery(
            raw_query="test",
            dialogue="hello",
            action="fight",
            text_query="general",
            characters=["JOHN"],
            locations=["OFFICE"],
        )
        result = SearchResultUtils.determine_match_type(query)
        assert result == "dialogue"

    def test_determine_match_type_priority_action(self) -> None:
        """Test match type priority - action over text/character/location."""
        query = SearchQuery(
            raw_query="test",
            action="fight",
            text_query="general",
            characters=["JOHN"],
            locations=["OFFICE"],
        )
        result = SearchResultUtils.determine_match_type(query)
        assert result == "action"

    def test_determine_match_type_priority_text(self) -> None:
        """Test match type priority - text over character/location."""
        query = SearchQuery(
            raw_query="test",
            text_query="general",
            characters=["JOHN"],
            locations=["OFFICE"],
        )
        result = SearchResultUtils.determine_match_type(query)
        assert result == "text"

    def test_determine_match_type_priority_character(self) -> None:
        """Test match type priority - character over location."""
        query = SearchQuery(raw_query="test", characters=["JOHN"], locations=["OFFICE"])
        result = SearchResultUtils.determine_match_type(query)
        assert result == "character"

    def test_merge_results_no_duplicates(self) -> None:
        """Test merging results with no duplicates."""
        primary = ["result1", "result2"]
        secondary = ["result3", "result4"]

        def key_fn(x):
            return x

        result = SearchResultUtils.merge_results(primary, secondary, key_fn)

        assert result == ["result1", "result2", "result3", "result4"]

    def test_merge_results_with_duplicates(self) -> None:
        """Test merging results with duplicates."""
        mock_result1 = MagicMock(spec=object)
        mock_result1.id = 1
        mock_result2 = MagicMock(spec=object)
        mock_result2.id = 2
        mock_result3 = MagicMock(spec=object)
        mock_result3.id = 1  # Duplicate
        mock_result4 = MagicMock(spec=object)
        mock_result4.id = 3

        primary = [mock_result1, mock_result2]
        secondary = [mock_result3, mock_result4]

        def key_fn(x):
            return x.id

        result = SearchResultUtils.merge_results(primary, secondary, key_fn)

        assert len(result) == 3  # Should exclude duplicate
        assert result[0].id == 1  # Original from primary
        assert result[1].id == 2
        assert result[2].id == 3

    def test_merge_results_empty_primary(self) -> None:
        """Test merging with empty primary results."""
        primary = []
        secondary = ["result1", "result2"]

        def key_fn(x):
            return x

        result = SearchResultUtils.merge_results(primary, secondary, key_fn)

        assert result == ["result1", "result2"]

    def test_merge_results_empty_secondary(self) -> None:
        """Test merging with empty secondary results."""
        primary = ["result1", "result2"]
        secondary = []

        def key_fn(x):
            return x

        result = SearchResultUtils.merge_results(primary, secondary, key_fn)

        assert result == ["result1", "result2"]

    def test_merge_results_both_empty(self) -> None:
        """Test merging with both result lists empty."""
        primary = []
        secondary = []

        def key_fn(x):
            return x

        result = SearchResultUtils.merge_results(primary, secondary, key_fn)

        assert result == []

    def test_merge_results_complex_key_function(self) -> None:
        """Test merging with complex key function."""
        result1 = SearchResult(
            script_id=1,
            script_title="Test1",
            script_author="Author1",
            scene_id=1,
            scene_number=1,
            scene_heading="Scene1",
            scene_location="LOC1",
            scene_time="DAY",
            scene_content="Content1",
        )
        result2 = SearchResult(
            script_id=1,
            script_title="Test1",
            script_author="Author1",
            scene_id=2,
            scene_number=2,
            scene_heading="Scene2",
            scene_location="LOC2",
            scene_time="NIGHT",
            scene_content="Content2",
        )
        result3 = SearchResult(
            script_id=1,
            script_title="Test1",
            script_author="Author1",
            scene_id=1,
            scene_number=1,
            scene_heading="Scene1",  # Duplicate scene_id
            scene_location="LOC1",
            scene_time="DAY",
            scene_content="Different content",
        )
        result4 = SearchResult(
            script_id=1,
            script_title="Test1",
            script_author="Author1",
            scene_id=3,
            scene_number=3,
            scene_heading="Scene3",
            scene_location="LOC3",
            scene_time="DAY",
            scene_content="Content3",
        )

        primary = [result1, result2]
        secondary = [result3, result4]  # result3 is duplicate of result1

        def key_fn(x):
            return x.scene_id

        result = SearchResultUtils.merge_results(primary, secondary, key_fn)

        assert len(result) == 3  # Should exclude duplicate scene_id
        scene_ids = [r.scene_id for r in result]
        assert scene_ids == [1, 2, 3]

"""Tests for bible extraction utilities."""

from unittest.mock import patch

from scriptrag.api.bible.utils import (
    CHARACTER_KEYWORDS,
    SCENE_KEYWORDS,
    VALID_SCENE_TYPES,
    LLMResponseParser,
)


class TestConstants:
    """Test module constants."""

    def test_character_keywords(self) -> None:
        """Test CHARACTER_KEYWORDS constant."""
        assert isinstance(CHARACTER_KEYWORDS, list)
        assert len(CHARACTER_KEYWORDS) == 8
        assert "character" in CHARACTER_KEYWORDS
        assert "protagonist" in CHARACTER_KEYWORDS
        assert "antagonist" in CHARACTER_KEYWORDS
        assert "cast" in CHARACTER_KEYWORDS
        assert "role" in CHARACTER_KEYWORDS
        assert "player" in CHARACTER_KEYWORDS
        assert "person" in CHARACTER_KEYWORDS
        assert "name" in CHARACTER_KEYWORDS

    def test_scene_keywords(self) -> None:
        """Test SCENE_KEYWORDS constant."""
        assert isinstance(SCENE_KEYWORDS, list)
        assert len(SCENE_KEYWORDS) == 8
        assert "scene" in SCENE_KEYWORDS
        assert "location" in SCENE_KEYWORDS
        assert "setting" in SCENE_KEYWORDS
        assert "place" in SCENE_KEYWORDS
        assert "environment" in SCENE_KEYWORDS
        assert "interior" in SCENE_KEYWORDS
        assert "exterior" in SCENE_KEYWORDS
        assert "stage" in SCENE_KEYWORDS

    def test_valid_scene_types(self) -> None:
        """Test VALID_SCENE_TYPES constant."""
        assert isinstance(VALID_SCENE_TYPES, list)
        assert len(VALID_SCENE_TYPES) == 4
        assert "INT" in VALID_SCENE_TYPES
        assert "EXT" in VALID_SCENE_TYPES
        assert "INT/EXT" in VALID_SCENE_TYPES
        assert "I/E" in VALID_SCENE_TYPES


class TestLLMResponseParser:
    """Test LLMResponseParser utility class."""

    def test_extract_json_array_valid_json(self) -> None:
        """Test extracting valid JSON array."""
        response = '[{"name": "John"}, {"name": "Jane"}]'
        result = LLMResponseParser.extract_json_array(response)
        assert result == [{"name": "John"}, {"name": "Jane"}]

    def test_extract_json_array_with_code_block(self) -> None:
        """Test extracting JSON from markdown code block."""
        response = '```json\n[{"canonical": "JANE", "aliases": ["J"]}]\n```'
        result = LLMResponseParser.extract_json_array(response)
        assert result == [{"canonical": "JANE", "aliases": ["J"]}]

    def test_extract_json_array_with_text_around(self) -> None:
        """Test extracting JSON with surrounding text."""
        response = (
            "Here is the extracted data:\n"
            '[{"location": "OFFICE", "type": "INT"}]\n'
            "That's all the scenes."
        )
        result = LLMResponseParser.extract_json_array(response)
        assert result == [{"location": "OFFICE", "type": "INT"}]

    def test_extract_json_array_multiline(self) -> None:
        """Test extracting multiline JSON array."""
        response = """
        The characters are:
        [
            {
                "canonical": "JOHN SMITH",
                "aliases": ["JOHN", "SMITH"]
            },
            {
                "canonical": "JANE DOE",
                "aliases": ["JANE"]
            }
        ]
        """
        result = LLMResponseParser.extract_json_array(response)
        assert len(result) == 2
        assert result[0]["canonical"] == "JOHN SMITH"
        assert result[1]["canonical"] == "JANE DOE"

    def test_extract_json_array_not_array(self) -> None:
        """Test with JSON that's not an array."""
        response = '{"name": "John"}'
        result = LLMResponseParser.extract_json_array(response)
        assert result == []

    def test_extract_json_array_invalid_json(self) -> None:
        """Test with invalid JSON."""
        response = "This is not JSON at all"
        result = LLMResponseParser.extract_json_array(response)
        assert result == []

    def test_extract_json_array_malformed_json(self) -> None:
        """Test with malformed JSON in code block."""
        response = '```json\n[{"name": "John", invalid}]\n```'
        result = LLMResponseParser.extract_json_array(response)
        assert result == []

    def test_extract_json_array_empty_array(self) -> None:
        """Test with empty JSON array."""
        response = "[]"
        result = LLMResponseParser.extract_json_array(response)
        assert result == []

    def test_extract_json_array_nested_arrays(self) -> None:
        """Test with nested arrays (should extract outer array)."""
        response = '[{"items": [1, 2, 3]}, {"items": [4, 5, 6]}]'
        result = LLMResponseParser.extract_json_array(response)
        assert len(result) == 2
        assert result[0]["items"] == [1, 2, 3]

    def test_extract_json_array_complex_response(self) -> None:
        """Test with complex LLM response containing multiple JSON-like structures."""
        response = """
        I found the following information:

        First, let me explain that {"this": "is not the array"}.

        Here's the actual data:
        ```json
        [
            {"canonical": "DETECTIVE JONES", "aliases": ["JONES", "DETECTIVE"]},
            {"canonical": "SARAH MILLER", "aliases": ["SARAH", "MS. MILLER"]}
        ]
        ```

        Note that [1, 2, 3] is just a list of numbers.
        """
        result = LLMResponseParser.extract_json_array(response)
        assert len(result) == 2
        assert result[0]["canonical"] == "DETECTIVE JONES"
        assert result[1]["aliases"] == ["SARAH", "MS. MILLER"]

    def test_extract_json_array_deeply_nested_objects(self) -> None:
        """Test extracting JSON arrays with deeply nested objects and arrays."""
        response = """
        Character data with complex relationships:
        [
            {
                "canonical": "JOHN DOE",
                "aliases": ["JOHN", "MR. DOE"],
                "relationships": {
                    "family": {
                        "spouse": "JANE DOE",
                        "children": ["JIMMY", "JENNY"],
                        "parents": {
                            "father": "JACK DOE",
                            "mother": "JILL DOE"
                        }
                    },
                    "work": {
                        "department": "Engineering",
                        "colleagues": [
                            {"name": "BOB", "role": "Manager", "years": 5},
                            {"name": "ALICE", "role": "Assistant", "years": 2}
                        ]
                    }
                },
                "metadata": {
                    "appearances": [1, 2, 3, 4, 5],
                    "characteristics": {
                        "physical": ["tall", "dark hair"],
                        "personality": ["kind", "determined"]
                    }
                }
            },
            {
                "canonical": "JANE DOE",
                "aliases": ["JANE", "MRS. DOE"],
                "relationships": {
                    "family": {
                        "spouse": "JOHN DOE",
                        "children": ["JIMMY", "JENNY"]
                    }
                },
                "metadata": {
                    "appearances": [1, 3, 5],
                    "traits": ["intelligent", "caring", "strong"]
                }
            }
        ]
        """
        result = LLMResponseParser.extract_json_array(response)

        # Verify we got both characters
        assert len(result) == 2

        # Verify first character's deeply nested data
        john = result[0]
        assert john["canonical"] == "JOHN DOE"
        assert john["aliases"] == ["JOHN", "MR. DOE"]
        assert john["relationships"]["family"]["spouse"] == "JANE DOE"
        assert john["relationships"]["family"]["children"] == ["JIMMY", "JENNY"]
        assert john["relationships"]["family"]["parents"]["father"] == "JACK DOE"
        assert john["relationships"]["work"]["colleagues"][0]["name"] == "BOB"
        assert john["relationships"]["work"]["colleagues"][0]["years"] == 5
        assert john["metadata"]["characteristics"]["physical"] == ["tall", "dark hair"]

        # Verify second character's data
        jane = result[1]
        assert jane["canonical"] == "JANE DOE"
        assert jane["metadata"]["traits"] == ["intelligent", "caring", "strong"]

    def test_extract_json_array_with_multiple_bracket_types(self) -> None:
        """Test JSON extraction when text contains various bracket patterns."""
        response = """
        Scene coordinates are [12.34, 56.78] (not important).

        The character list includes:
        [
            {"name": "HERO", "skills": ["fighting", "flying", "thinking"]},
            {"name": "VILLAIN", "weaknesses": ["pride", "anger"]}
        ]

        Also, time codes are [00:01:23, 00:05:45, 00:10:12].
        """
        result = LLMResponseParser.extract_json_array(response)

        # Should extract the character data, not coordinate or time arrays
        assert len(result) == 2
        assert result[0]["name"] == "HERO"
        assert result[0]["skills"] == ["fighting", "flying", "thinking"]
        assert result[1]["name"] == "VILLAIN"
        assert result[1]["weaknesses"] == ["pride", "anger"]

    def test_extract_json_array_with_escaped_quotes(self) -> None:
        """Test JSON extraction with escaped quotes in strings."""
        response = r"""
        Character data:
        [
            {
                "canonical": "JOHN \"THE BOSS\" SMITH",
                "dialogue": "He said, \"Let's do this!\""
            },
            {
                "canonical": "JANE O'CONNOR",
                "dialogue": "She replied, \"I'm ready.\""
            }
        ]
        """
        result = LLMResponseParser.extract_json_array(response)

        assert len(result) == 2
        assert result[0]["canonical"] == 'JOHN "THE BOSS" SMITH'
        assert result[0]["dialogue"] == 'He said, "Let\'s do this!"'
        assert result[1]["canonical"] == "JANE O'CONNOR"

    def test_extract_json_array_empty_nested_objects(self) -> None:
        """Test JSON extraction with empty nested objects and arrays."""
        response = """
        Data:
        [
            {"name": "CHAR1", "relationships": {}, "aliases": []},
            {"name": "CHAR2", "metadata": {"notes": "", "tags": []}}
        ]
        """
        result = LLMResponseParser.extract_json_array(response)

        assert len(result) == 2
        assert result[0]["name"] == "CHAR1"
        assert result[0]["relationships"] == {}
        assert result[0]["aliases"] == []
        assert result[1]["metadata"]["notes"] == ""
        assert result[1]["metadata"]["tags"] == []

    def test_extract_json_array_mixed_content_types(self) -> None:
        """Test JSON extraction with mixed content types in nested structures."""
        response = """
        Character analysis:
        [
            {
                "name": "PROTAGONIST",
                "stats": {
                    "appearances": 42,
                    "importance": 0.95,
                    "active": true,
                    "debut": null,
                    "traits": ["brave", "clever"],
                    "relationships": {
                        "allies": 3,
                        "enemies": 1,
                        "neutral": 5
                    }
                }
            }
        ]
        """
        result = LLMResponseParser.extract_json_array(response)

        assert len(result) == 1
        assert result[0]["name"] == "PROTAGONIST"
        assert result[0]["stats"]["appearances"] == 42
        assert result[0]["stats"]["importance"] == 0.95
        assert result[0]["stats"]["active"] is True
        assert result[0]["stats"]["debut"] is None
        assert result[0]["stats"]["traits"] == ["brave", "clever"]
        assert result[0]["stats"]["relationships"]["allies"] == 3

    @patch("scriptrag.api.bible.utils.logger")
    def test_extract_json_array_max_parse_attempts_exceeded(self, mock_logger) -> None:
        """Test warning when max parse attempts (20) is exceeded."""
        # Create pathological input with many unmatched opening brackets
        # This forces the parser to attempt parsing 21+ array candidates
        unmatched_brackets = "["  # Start with one opening bracket
        for i in range(25):  # Add 25 more opening brackets with minimal content
            unmatched_brackets += f"invalid{i}["

        # Add some valid-looking but unparseable content at the end
        response = f"{unmatched_brackets} not valid json"

        result = LLMResponseParser.extract_json_array(response)

        # Should return empty list and log warning
        assert result == []
        mock_logger.warning.assert_called()

        # Verify the specific warning message for max parse attempts
        warning_calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "max parse attempts" in str(call)
        ]
        assert len(warning_calls) > 0
        assert "20" in str(warning_calls[0])

    @patch("scriptrag.api.bible.utils.logger")
    def test_extract_json_array_max_nesting_depth_exceeded(self, mock_logger) -> None:
        """Test warning when max nesting depth (100) is exceeded."""
        # Create deeply nested ARRAY structure that exceeds 100 levels
        # The bracket_count tracks [ and ] brackets, not { and }
        deeply_nested = ""
        for _ in range(110):  # Create 110 levels of nested arrays
            deeply_nested += "["
        # Add some minimal content that contains objects (to pass the filter)
        deeply_nested += '{"test": "data"}'
        # Don't close all brackets - this will trigger the depth check

        response = f"Deep nesting test: {deeply_nested}"

        result = LLMResponseParser.extract_json_array(response)

        # Should return empty list and log warning about nesting depth
        assert result == []
        mock_logger.warning.assert_called()

        # Verify the specific warning message for max nesting depth
        warning_calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "Max nesting depth" in str(call)
        ]
        assert len(warning_calls) > 0
        assert "100" in str(warning_calls[0])

    @patch("scriptrag.api.bible.utils.logger")
    def test_extract_json_array_max_search_distance_exceeded(self, mock_logger) -> None:
        """Test warning when max search distance (50000) is exceeded."""
        # Create very long JSON-like content that exceeds 50,000 chars
        # Start with opening bracket
        long_content = "["
        # Add over 50,000 characters of content before any closing bracket
        padding = "x" * 51000  # 51,000 characters of padding
        long_content += padding
        # Add closing bracket at the end (but it won't be reached due to search limit)
        long_content += "]"

        response = f"Very long response: {long_content}"

        result = LLMResponseParser.extract_json_array(response)

        # Should return empty list and log warning about search distance
        assert result == []
        mock_logger.warning.assert_called()

        # Verify the specific warning message for max search distance
        warning_calls = [
            call
            for call in mock_logger.warning.call_args_list
            if "Max search distance" in str(call)
        ]
        assert len(warning_calls) > 0
        assert "50000" in str(warning_calls[0])

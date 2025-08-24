"""Tests for bible extraction utilities."""

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

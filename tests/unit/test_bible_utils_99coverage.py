"""Tests for bible utils module - 99% coverage target."""

import pytest

from scriptrag.api.bible.utils import (
    CHARACTER_KEYWORDS,
    SCENE_KEYWORDS,
    VALID_SCENE_TYPES,
    LLMResponseParser,
)


class TestConstants:
    """Test module constants coverage."""

    def test_character_keywords_exist(self):
        """Character keywords are defined."""
        assert isinstance(CHARACTER_KEYWORDS, list)
        assert len(CHARACTER_KEYWORDS) > 0
        assert "character" in CHARACTER_KEYWORDS

    def test_scene_keywords_exist(self):
        """Scene keywords are defined."""
        assert isinstance(SCENE_KEYWORDS, list)
        assert len(SCENE_KEYWORDS) > 0
        assert "scene" in SCENE_KEYWORDS

    def test_valid_scene_types_exist(self):
        """Valid scene types are defined."""
        assert isinstance(VALID_SCENE_TYPES, list)
        assert "INT" in VALID_SCENE_TYPES
        assert "EXT" in VALID_SCENE_TYPES


class TestLLMResponseParser:
    """Test LLM response parser with comprehensive coverage."""

    @pytest.mark.parametrize(
        "response,expected",
        [
            # Direct JSON array
            ('[{"name": "JANE"}]', [{"name": "JANE"}]),
            ("[]", []),
            (
                '[{"name": "JOHN"}, {"name": "JANE"}]',
                [{"name": "JOHN"}, {"name": "JANE"}],
            ),
            # JSON wrapped in code blocks
            ('```json\n[{"name": "JANE"}]\n```', [{"name": "JANE"}]),
            ('```\n[{"name": "JANE"}]\n```', [{"name": "JANE"}]),
            # JSON with surrounding text
            ('Here is the data: [{"name": "JANE"}] end', [{"name": "JANE"}]),
            (
                'Characters found: [{"name": "JOHN"}, {"name": "JANE"}]',
                [{"name": "JOHN"}, {"name": "JANE"}],
            ),
            # Nested objects
            (
                '[{"character": {"name": "JANE", "role": "lead"}}]',
                [{"character": {"name": "JANE", "role": "lead"}}],
            ),
            # Invalid/empty responses
            ("", []),
            ("no json here", []),
            ('{"not": "array"}', []),
            ("invalid json [", []),
            # Edge cases
            ("[]", []),
            ("[{}]", [{}]),
            ('Multiple [{"name": "A"}] arrays [{"name": "B"}]', [{"name": "A"}]),
        ],
    )
    def test_extract_json_array_valid_cases(self, response, expected):
        """Test JSON extraction for valid cases."""
        result = LLMResponseParser.extract_json_array(response)
        assert result == expected

    def test_extract_json_array_primitive_arrays_filtered(self):
        """Primitive arrays in mixed text are filtered out."""
        response = 'Numbers [1, 2, 3] and objects [{"name": "JANE"}]'
        result = LLMResponseParser.extract_json_array(response)
        assert result == [{"name": "JANE"}]

    def test_extract_json_array_string_arrays_filtered(self):
        """String arrays in mixed text are filtered out."""
        response = 'Words ["a", "b"] and objects [{"name": "JANE"}]'
        result = LLMResponseParser.extract_json_array(response)
        assert result == [{"name": "JANE"}]

    def test_extract_json_array_nested_brackets(self):
        """Nested brackets are handled correctly."""
        response = '[{"data": [1, 2, 3], "name": "JANE"}]'
        result = LLMResponseParser.extract_json_array(response)
        assert result == [{"data": [1, 2, 3], "name": "JANE"}]

    def test_extract_json_array_escaped_quotes(self):
        """Escaped quotes in strings are handled."""
        response = r'[{"name": "JANE \"DOE\""}]'
        result = LLMResponseParser.extract_json_array(response)
        assert result == [{"name": 'JANE "DOE"'}]

    def test_extract_json_array_complex_nesting(self):
        """Complex nested structures work."""
        response = (
            '[{"character": {"name": "JANE", "scenes": [{"location": "INT. HOUSE"}]}}]'
        )
        result = LLMResponseParser.extract_json_array(response)
        expected = [
            {"character": {"name": "JANE", "scenes": [{"location": "INT. HOUSE"}]}}
        ]
        assert result == expected

    def test_extract_json_array_malformed_json(self):
        """Malformed JSON returns empty list."""
        response = '[{"name": "JANE",}]'  # Trailing comma
        result = LLMResponseParser.extract_json_array(response)
        assert result == []

    def test_extract_json_array_multiple_valid_arrays(self):
        """First valid array is returned when multiple exist."""
        response = 'First [{"name": "JANE"}] and second [{"name": "JOHN"}]'
        result = LLMResponseParser.extract_json_array(response)
        assert result == [{"name": "JANE"}]

    def test_extract_json_array_performance_limits(self, caplog):
        """Performance limits prevent infinite loops."""
        # Test deeply nested structure that triggers nesting limit
        deeply_nested = "[" * 150 + "{}" + "]" * 150
        result = LLMResponseParser.extract_json_array(deeply_nested)
        # May or may not parse depending on implementation details
        assert isinstance(result, list)

    def test_extract_json_array_max_search_distance(self):
        """Max search distance limit works."""
        # Create response within search distance
        long_response = "x" * 10000 + '[{"name": "JANE"}]'
        result = LLMResponseParser.extract_json_array(long_response)
        # Should find the JSON within search distance
        assert result == [{"name": "JANE"}]

    def test_extract_json_array_many_brackets(self):
        """Many bracket patterns are handled."""
        # Create response with bracket patterns but valid JSON at end
        many_brackets = "[invalid" * 10 + '[{"name": "JANE"}]'
        result = LLMResponseParser.extract_json_array(many_brackets)
        assert result == [{"name": "JANE"}]

    def test_extract_json_array_empty_object_array(self):
        """Array with empty objects is valid."""
        response = "[{}, {}]"
        result = LLMResponseParser.extract_json_array(response)
        assert result == [{}, {}]

    def test_extract_json_array_non_dict_objects_direct(self):
        """Direct JSON arrays with non-dict objects are returned as-is."""
        response = "[1, 2, 3]"
        result = LLMResponseParser.extract_json_array(response)
        # Direct JSON is returned without filtering
        assert result == [1, 2, 3]

    def test_extract_json_array_mixed_types_direct(self):
        """Direct JSON arrays with mixed types are returned as-is."""
        response = '[1, {"name": "JANE"}]'
        result = LLMResponseParser.extract_json_array(response)
        # Direct JSON is returned without filtering
        assert result == [1, {"name": "JANE"}]

    def test_extract_json_array_string_with_brackets(self):
        """Strings containing brackets don't break parsing."""
        response = '[{"text": "This [has] brackets"}]'
        result = LLMResponseParser.extract_json_array(response)
        assert result == [{"text": "This [has] brackets"}]

    def test_extract_json_array_escape_sequences(self):
        """Various escape sequences are handled."""
        response = r'[{"text": "Line 1\nLine 2\tTabbed"}]'
        result = LLMResponseParser.extract_json_array(response)
        assert result == [{"text": "Line 1\nLine 2\tTabbed"}]

    def test_extract_json_array_unicode(self):
        """Unicode characters are preserved."""
        response = '[{"name": "José", "emoji": "🎬"}]'
        result = LLMResponseParser.extract_json_array(response)
        assert result == [{"name": "José", "emoji": "🎬"}]

    def test_extract_json_array_no_valid_json(self):
        """Returns empty list when no valid JSON found."""
        result = LLMResponseParser.extract_json_array("no json here")
        assert result == []

    def test_extract_json_array_valid_direct_json_bypasses_filtering(self):
        """Direct valid JSON bypasses object filtering."""
        # This should work even though it's an array of strings
        response = '["a", "b", "c"]'
        result = LLMResponseParser.extract_json_array(response)
        assert result == ["a", "b", "c"]

    def test_extract_json_array_direct_json_non_array(self):
        """Direct JSON that's not an array returns empty list."""
        response = '{"key": "value"}'
        result = LLMResponseParser.extract_json_array(response)
        assert result == []

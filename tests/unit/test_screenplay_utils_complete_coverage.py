"""Complete test coverage for ScreenplayUtils to achieve 99% coverage.

This module adds tests for all remaining uncovered lines in screenplay.py.
"""

import pytest

from scriptrag.utils import ScreenplayUtils


class TestExtractLocationEdgeCases:
    """Test edge cases for extract_location method."""

    def test_extract_location_with_none(self):
        """Test extract_location with None input (line 30)."""
        assert ScreenplayUtils.extract_location(None) is None

    def test_extract_location_with_int_ext_prefix(self):
        """Test extract_location with INT./EXT. prefix (line 37)."""
        result = ScreenplayUtils.extract_location("INT./EXT. WAREHOUSE - DAY")
        assert result == "WAREHOUSE"

    def test_extract_location_with_int_ext_prefix_no_location(self):
        """Test extract_location with INT./EXT. but no location after."""
        result = ScreenplayUtils.extract_location("INT./EXT. - DAY")
        assert result is None  # Only time, no location

    def test_extract_location_with_int_ext_prefix_empty(self):
        """Test extract_location with INT./EXT. and nothing after."""
        result = ScreenplayUtils.extract_location("INT./EXT.")
        assert result is None


class TestExtractTimeEdgeCases:
    """Test edge cases for extract_time method."""

    def test_extract_time_with_none(self):
        """Test extract_time with None input (line 74)."""
        assert ScreenplayUtils.extract_time(None) is None

    def test_extract_time_no_match(self):
        """Test extract_time when no time indicator is found (line 100)."""
        result = ScreenplayUtils.extract_time("INT. OFFICE")
        assert result is None

    def test_extract_time_with_empty_string(self):
        """Test extract_time with empty string."""
        result = ScreenplayUtils.extract_time("")
        assert result is None


class TestParseSceneHeading:
    """Test parse_scene_heading method (lines 112-133)."""

    def test_parse_scene_heading_with_none(self):
        """Test parse_scene_heading with None input (lines 112-113)."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(None)
        assert scene_type == ""
        assert location is None
        assert time is None

    def test_parse_scene_heading_with_empty_string(self):
        """Test parse_scene_heading with empty string."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading("")
        assert scene_type == ""
        assert location is None
        assert time is None

    def test_parse_scene_heading_int_ext_dot(self):
        """Test parse_scene_heading with INT./EXT. prefix (line 124)."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "INT./EXT. WAREHOUSE - DAY"
        )
        assert scene_type == "INT/EXT"
        assert location == "WAREHOUSE"
        assert time == "DAY"

    def test_parse_scene_heading_ie_dot(self):
        """Test parse_scene_heading with I/E. prefix."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "I/E. CAR - NIGHT"
        )
        assert scene_type == "INT/EXT"
        assert location == "CAR"
        assert time == "NIGHT"

    def test_parse_scene_heading_ie_space(self):
        """Test parse_scene_heading with I/E space prefix."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "I/E VEHICLE - MORNING"
        )
        assert scene_type == "INT/EXT"
        assert location == "VEHICLE"
        assert time == "MORNING"

    def test_parse_scene_heading_int_dot(self):
        """Test parse_scene_heading with INT. prefix (line 125-126)."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "INT. OFFICE - DAY"
        )
        assert scene_type == "INT"
        assert location == "OFFICE"
        assert time == "DAY"

    def test_parse_scene_heading_int_space(self):
        """Test parse_scene_heading with INT space prefix."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "INT CONFERENCE ROOM - AFTERNOON"
        )
        assert scene_type == "INT"
        assert location == "CONFERENCE ROOM"
        assert time == "AFTERNOON"

    def test_parse_scene_heading_ext_dot(self):
        """Test parse_scene_heading with EXT. prefix (line 127-128)."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "EXT. STREET - NIGHT"
        )
        assert scene_type == "EXT"
        assert location == "STREET"
        assert time == "NIGHT"

    def test_parse_scene_heading_ext_space(self):
        """Test parse_scene_heading with EXT space prefix."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "EXT PARK - EVENING"
        )
        assert scene_type == "EXT"
        assert location == "PARK"
        assert time == "EVENING"

    def test_parse_scene_heading_no_prefix(self):
        """Test parse_scene_heading with no standard prefix."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "SOMEWHERE - DAY"
        )
        assert scene_type == ""
        assert location == "SOMEWHERE"
        assert time == "DAY"

    def test_parse_scene_heading_only_location(self):
        """Test parse_scene_heading with only location, no time."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading("INT. OFFICE")
        assert scene_type == "INT"
        assert location == "OFFICE"
        assert time is None

    def test_parse_scene_heading_only_time(self):
        """Test parse_scene_heading with only time, no location."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading("INT. - DAY")
        assert scene_type == "INT"
        assert location is None
        assert time == "DAY"

    def test_parse_scene_heading_complex(self):
        """Test parse_scene_heading with complex location."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "INT./EXT. JENNY'S APARTMENT - LIVING ROOM - CONTINUOUS"
        )
        assert scene_type == "INT/EXT"
        assert location == "JENNY'S APARTMENT - LIVING ROOM"
        assert time == "CONTINUOUS"

    def test_parse_scene_heading_all_caps(self):
        """Test parse_scene_heading preserves original case for location."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "int. office - day"
        )
        assert scene_type == "INT"
        assert location == "office"
        assert time == "DAY"

    def test_parse_scene_heading_mixed_case(self):
        """Test parse_scene_heading with mixed case input."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "Int. Office Building - Night"
        )
        assert scene_type == "INT"
        assert location == "Office Building"
        assert time == "NIGHT"

    def test_parse_scene_heading_with_multiple_dashes(self):
        """Test parse_scene_heading with multiple dashes in location."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "EXT. NEW YORK - TIMES SQUARE - NIGHT"
        )
        assert scene_type == "EXT"
        assert location == "NEW YORK - TIMES SQUARE"
        assert time == "NIGHT"


class TestDialogueHandlingBranchCoverage:
    """Test dialogue handling branch coverage."""

    def test_format_scene_for_prompt_dialogue_none_entries_skipped(self):
        """Test that None entries in dialogue are properly skipped."""
        scene = {
            "dialogue": [
                None,  # This should be skipped
                {"character": "ALICE", "text": "Hello"},
                None,
                "BOB: Hi there",
            ]
        }
        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert "ALICE: Hello" in result
        assert "BOB: Hi there" in result
        assert result.count("\n") >= 2  # Should have proper formatting

    def test_format_scene_for_embedding_dialogue_none_entries_skipped(self):
        """Test that None entries in dialogue are skipped in embedding format."""
        scene = {
            "dialogue": [
                None,
                {"character": "ALICE", "text": "Hello"},
                123,  # Non-string, non-dict
                "BOB: Hi there",
            ]
        }
        result = ScreenplayUtils.format_scene_for_embedding(scene)
        assert "ALICE: Hello" in result
        assert "BOB: Hi there" in result
        assert "123" not in result


class TestFormatSceneEdgeCasesForBranches:
    """Test format_scene methods for edge case branches."""

    def test_format_scene_for_prompt_action_only_valid_strings(self):
        """Test action list with only valid string entries."""
        scene = {"action": ["First line", "Second line", "Third line", ""]}
        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert "First line" in result
        assert "Second line" in result
        assert "Third line" in result

    def test_format_scene_for_embedding_action_only_valid_strings(self):
        """Test action list with only valid string entries for embedding."""
        scene = {"action": ["First line", "Second line", "Third line", ""]}
        result = ScreenplayUtils.format_scene_for_embedding(scene)
        assert "Action: First line Second line Third line" in result


class TestParameterizedSceneHeadings:
    """Parametrized tests for comprehensive scene heading coverage."""

    @pytest.mark.parametrize(
        "heading,expected_type,expected_location,expected_time",
        [
            # INT./EXT. variations
            ("INT./EXT. WAREHOUSE", "INT/EXT", "WAREHOUSE", None),
            ("INT./EXT. WAREHOUSE - DAY", "INT/EXT", "WAREHOUSE", "DAY"),
            ("int./ext. warehouse - day", "INT/EXT", "warehouse", "DAY"),
            # I/E variations
            ("I/E. VEHICLE", "INT/EXT", "VEHICLE", None),
            ("I/E VEHICLE", "INT/EXT", "VEHICLE", None),
            ("I/E. VEHICLE - NIGHT", "INT/EXT", "VEHICLE", "NIGHT"),
            ("I/E VEHICLE - CONTINUOUS", "INT/EXT", "VEHICLE", "CONTINUOUS"),
            # INT variations
            ("INT. ROOM", "INT", "ROOM", None),
            ("INT ROOM", "INT", "ROOM", None),
            ("int. room - morning", "INT", "room", "MORNING"),
            # EXT variations
            ("EXT. STREET", "EXT", "STREET", None),
            ("EXT STREET", "EXT", "STREET", None),
            ("ext. street - dusk", "EXT", "street", "DUSK"),
            # No prefix
            ("WAREHOUSE - DAY", "", "WAREHOUSE", "DAY"),
            ("SOMEWHERE", "", "SOMEWHERE", None),
            # Edge cases
            ("", "", None, None),
            ("INT.", "INT", None, None),
            ("EXT.", "EXT", None, None),
            ("INT. - DAY", "INT", None, "DAY"),
            ("EXT. - NIGHT", "EXT", None, "NIGHT"),
        ],
    )
    def test_parse_scene_heading_variations(
        self, heading, expected_type, expected_location, expected_time
    ):
        """Test various scene heading formats."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(heading)
        assert scene_type == expected_type
        assert location == expected_location
        assert time == expected_time


class TestComplexSceneFormats:
    """Test complex scene formatting scenarios."""

    def test_format_scene_all_components(self):
        """Test scene with all components present."""
        scene = {
            "heading": "INT./EXT. COMPLEX LOCATION - NIGHT",
            "action": ["Action line 1", "", "Action line 2"],
            "dialogue": [
                {"character": "CHAR1", "text": "Dict dialogue"},
                "CHAR2: String dialogue",
                None,
                {"character": "", "text": "Invalid - no character"},
                {"character": "CHAR3", "text": ""},  # Invalid - no text
            ],
            "content": "Fallback content",
        }

        # Test prompt format
        prompt_result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert "SCENE HEADING: INT./EXT. COMPLEX LOCATION - NIGHT" in prompt_result
        assert "ACTION:" in prompt_result
        assert "Action line 1" in prompt_result
        assert "Action line 2" in prompt_result
        assert "DIALOGUE:" in prompt_result
        assert "CHAR1: Dict dialogue" in prompt_result
        assert "CHAR2: String dialogue" in prompt_result
        assert "Invalid - no character" not in prompt_result
        # Fallback content is not used when other data is present
        assert "Fallback content" not in prompt_result

        # Test embedding format
        embed_result = ScreenplayUtils.format_scene_for_embedding(scene)
        assert "Scene: INT./EXT. COMPLEX LOCATION - NIGHT" in embed_result
        assert "Action: Action line 1 Action line 2" in embed_result
        assert "CHAR1: Dict dialogue" in embed_result
        assert "CHAR2: String dialogue" in embed_result

"""Tests for screenplay utility functions."""

from scriptrag.utils.screenplay import ScreenplayUtils


class TestExtractLocation:
    """Tests for extract_location method."""

    def test_extract_int_location(self):
        """Test extracting location from INT scene."""
        heading = "INT. COFFEE SHOP - DAY"
        result = ScreenplayUtils.extract_location(heading)
        assert result == "COFFEE SHOP"

    def test_extract_ext_location(self):
        """Test extracting location from EXT scene."""
        heading = "EXT. CITY STREET - NIGHT"
        result = ScreenplayUtils.extract_location(heading)
        assert result == "CITY STREET"

    def test_extract_int_ext_location(self):
        """Test extracting location from INT./EXT. scene."""
        heading = "INT./EXT. CAR - CONTINUOUS"
        result = ScreenplayUtils.extract_location(heading)
        assert result == "CAR"

    def test_extract_i_e_location(self):
        """Test extracting location from I/E scene."""
        heading = "I/E. DOORWAY - MORNING"
        result = ScreenplayUtils.extract_location(heading)
        assert result == "DOORWAY"

    def test_extract_location_no_time(self):
        """Test extracting location when no time specified."""
        heading = "INT. OFFICE"
        result = ScreenplayUtils.extract_location(heading)
        assert result == "OFFICE"

    def test_extract_location_with_spaces(self):
        """Test extracting location with multiple spaces."""
        heading = "INT BEDROOM - NIGHT"
        result = ScreenplayUtils.extract_location(heading)
        assert result == "BEDROOM"

    def test_extract_location_multiple_dashes(self):
        """Test extracting location with multiple dashes."""
        heading = "INT. DINER - COUNTER - DAY"
        result = ScreenplayUtils.extract_location(heading)
        assert result == "DINER - COUNTER"

    def test_extract_location_empty_heading(self):
        """Test extracting location from empty heading."""
        assert ScreenplayUtils.extract_location("") is None
        assert ScreenplayUtils.extract_location(None) is None

    def test_extract_location_time_only(self):
        """Test extracting location when only time is present."""
        heading = "INT. - DAY"
        result = ScreenplayUtils.extract_location(heading)
        assert result is None

    def test_extract_location_dash_prefix(self):
        """Test extracting location with dash prefix (time only)."""
        heading = "- NIGHT"
        result = ScreenplayUtils.extract_location(heading)
        assert result is None

    def test_extract_location_complex(self):
        """Test extracting complex location."""
        heading = "INT. JANE'S APARTMENT - LIVING ROOM - NIGHT"
        result = ScreenplayUtils.extract_location(heading)
        assert result == "JANE'S APARTMENT - LIVING ROOM"

    def test_extract_location_ext_space(self):
        """Test extracting location with EXT followed by space."""
        heading = "EXT PARK - DAY"
        result = ScreenplayUtils.extract_location(heading)
        assert result == "PARK"

    def test_extract_location_whitespace_only(self):
        """Test location extraction when location is whitespace."""
        heading = "INT.    - DAY"
        result = ScreenplayUtils.extract_location(heading)
        assert result is None


class TestExtractTime:
    """Tests for extract_time method."""

    def test_extract_day(self):
        """Test extracting DAY time."""
        heading = "INT. OFFICE - DAY"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "DAY"

    def test_extract_night(self):
        """Test extracting NIGHT time."""
        heading = "EXT. STREET - NIGHT"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "NIGHT"

    def test_extract_morning(self):
        """Test extracting MORNING time."""
        heading = "INT. BEDROOM - MORNING"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "MORNING"

    def test_extract_continuous(self):
        """Test extracting CONTINUOUS time."""
        heading = "INT./EXT. CAR - CONTINUOUS"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "CONTINUOUS"

    def test_extract_later(self):
        """Test extracting LATER time."""
        heading = "INT. OFFICE - LATER"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "LATER"

    def test_extract_moments_later(self):
        """Test extracting MOMENTS LATER time."""
        heading = "INT. HALLWAY - MOMENTS LATER"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "MOMENTS LATER"

    def test_extract_dusk(self):
        """Test extracting DUSK time."""
        heading = "EXT. BEACH - DUSK"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "DUSK"

    def test_extract_dawn(self):
        """Test extracting DAWN time."""
        heading = "EXT. MOUNTAIN - DAWN"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "DAWN"

    def test_extract_sunset(self):
        """Test extracting SUNSET time."""
        heading = "EXT. ROOFTOP - SUNSET"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "SUNSET"

    def test_extract_time_no_separator(self):
        """Test extracting time without dash separator."""
        heading = "INT. OFFICE DAY"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "DAY"

    def test_extract_time_empty_heading(self):
        """Test extracting time from empty heading."""
        assert ScreenplayUtils.extract_time("") is None
        assert ScreenplayUtils.extract_time(None) is None

    def test_extract_time_no_time(self):
        """Test extracting time when no time present."""
        heading = "INT. OFFICE"
        result = ScreenplayUtils.extract_time(heading)
        assert result is None

    def test_extract_time_case_insensitive(self):
        """Test time extraction is case insensitive."""
        heading = "INT. ROOM - day"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "DAY"

    def test_extract_noon(self):
        """Test extracting NOON time."""
        heading = "INT. RESTAURANT - NOON"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "NOON"

    def test_extract_midnight(self):
        """Test extracting MIDNIGHT time."""
        heading = "EXT. STREET - MIDNIGHT"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "MIDNIGHT"

    def test_extract_time_with_multiple_dashes(self):
        """Test extracting time with multiple dashes in location."""
        heading = "INT. BUILDING - FLOOR 2 - NIGHT"
        result = ScreenplayUtils.extract_time(heading)
        assert result == "NIGHT"


class TestParseSceneHeading:
    """Tests for parse_scene_heading method."""

    def test_parse_int_scene(self):
        """Test parsing INT scene heading."""
        heading = "INT. OFFICE - DAY"
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(heading)
        assert scene_type == "INT"
        assert location == "OFFICE"
        assert time == "DAY"

    def test_parse_ext_scene(self):
        """Test parsing EXT scene heading."""
        heading = "EXT. PARK - MORNING"
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(heading)
        assert scene_type == "EXT"
        assert location == "PARK"
        assert time == "MORNING"

    def test_parse_int_ext_scene(self):
        """Test parsing INT./EXT. scene heading."""
        heading = "INT./EXT. VEHICLE - CONTINUOUS"
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(heading)
        assert scene_type == "INT/EXT"
        assert location == "VEHICLE"
        assert time == "CONTINUOUS"

    def test_parse_i_e_scene(self):
        """Test parsing I/E scene heading."""
        heading = "I/E. DOORWAY - NIGHT"
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(heading)
        assert scene_type == "INT/EXT"
        assert location == "DOORWAY"
        assert time == "NIGHT"

    def test_parse_empty_heading(self):
        """Test parsing empty heading."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading("")
        assert scene_type == ""
        assert location is None
        assert time is None

    def test_parse_none_heading(self):
        """Test parsing None heading."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(None)
        assert scene_type == ""
        assert location is None
        assert time is None

    def test_parse_no_scene_type(self):
        """Test parsing heading without scene type."""
        heading = "SOMEWHERE - DAY"
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(heading)
        assert scene_type == ""
        assert location == "SOMEWHERE"
        assert time == "DAY"

    def test_parse_int_with_space(self):
        """Test parsing INT with space instead of period."""
        heading = "INT KITCHEN - NIGHT"
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(heading)
        assert scene_type == "INT"
        assert location == "KITCHEN"
        assert time == "NIGHT"

    def test_parse_complex_location(self):
        """Test parsing complex multi-part location."""
        heading = "INT. HOSPITAL - EMERGENCY ROOM - NURSES' STATION - NIGHT"
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(heading)
        assert scene_type == "INT"
        assert location == "HOSPITAL - EMERGENCY ROOM - NURSES' STATION"
        assert time == "NIGHT"


class TestComputeSceneHash:
    """Tests for compute_scene_hash method."""

    def test_hash_basic_scene(self):
        """Test hashing a basic scene."""
        scene_text = "INT. OFFICE - DAY\n\nJohn enters the room."
        hash_result = ScreenplayUtils.compute_scene_hash(scene_text)
        assert len(hash_result) == 16  # Truncated by default
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_hash_with_boneyard(self):
        """Test hashing excludes boneyard metadata."""
        scene_without = "INT. OFFICE - DAY\n\nJohn enters."
        boneyard = "/* SCRIPTRAG-META-START\nSome metadata\nSCRIPTRAG-META-END */\n"
        scene_with = f"{boneyard}{scene_without}"

        hash_without = ScreenplayUtils.compute_scene_hash(scene_without)
        hash_with = ScreenplayUtils.compute_scene_hash(scene_with)

        assert hash_without == hash_with

    def test_hash_full_length(self):
        """Test getting full-length hash."""
        scene_text = "INT. OFFICE - DAY"
        hash_result = ScreenplayUtils.compute_scene_hash(scene_text, truncate=False)
        assert len(hash_result) == 64  # Full SHA256 length

    def test_hash_consistency(self):
        """Test hash is consistent for same content."""
        scene_text = "EXT. PARK - MORNING\n\nBirds chirping."
        hash1 = ScreenplayUtils.compute_scene_hash(scene_text)
        hash2 = ScreenplayUtils.compute_scene_hash(scene_text)
        assert hash1 == hash2

    def test_hash_different_scenes(self):
        """Test different scenes produce different hashes."""
        scene1 = "INT. OFFICE - DAY"
        scene2 = "EXT. PARK - NIGHT"
        hash1 = ScreenplayUtils.compute_scene_hash(scene1)
        hash2 = ScreenplayUtils.compute_scene_hash(scene2)
        assert hash1 != hash2

    def test_hash_whitespace_normalization(self):
        """Test hash after stripping whitespace."""
        scene1 = "INT. OFFICE - DAY\n\n"
        scene2 = "INT. OFFICE - DAY"
        hash1 = ScreenplayUtils.compute_scene_hash(scene1)
        hash2 = ScreenplayUtils.compute_scene_hash(scene2)
        assert hash1 == hash2


class TestStripBoneyard:
    """Tests for strip_boneyard method."""

    def test_strip_simple_boneyard(self):
        """Test stripping simple boneyard."""
        text_with = "/* SCRIPTRAG-META-START\nmetadata\nSCRIPTRAG-META-END */\nContent"
        result = ScreenplayUtils.strip_boneyard(text_with)
        assert result == "Content"

    def test_strip_multiline_boneyard(self):
        """Test stripping multiline boneyard."""
        text_with = """/* SCRIPTRAG-META-START
{
    "key": "value",
    "another": "data"
}
SCRIPTRAG-META-END */
Scene content here"""
        result = ScreenplayUtils.strip_boneyard(text_with)
        assert result == "Scene content here"

    def test_strip_no_boneyard(self):
        """Test stripping when no boneyard present."""
        text = "Just regular content"
        result = ScreenplayUtils.strip_boneyard(text)
        assert result == "Just regular content"

    def test_strip_multiple_boneyards(self):
        """Test stripping multiple boneyards."""
        text = """/* SCRIPTRAG-META-START
meta1
SCRIPTRAG-META-END */
Content
/* SCRIPTRAG-META-START
meta2
SCRIPTRAG-META-END */
More content"""
        result = ScreenplayUtils.strip_boneyard(text)
        assert result == "Content\n\nMore content"

    def test_strip_empty_text(self):
        """Test stripping from empty text."""
        result = ScreenplayUtils.strip_boneyard("")
        assert result == ""


class TestFormatSceneForPrompt:
    """Tests for format_scene_for_prompt method."""

    def test_format_with_heading(self):
        """Test formatting scene with heading."""
        scene = {"heading": "INT. OFFICE - DAY"}
        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert result == "SCENE HEADING: INT. OFFICE - DAY"

    def test_format_with_action(self):
        """Test formatting scene with action."""
        scene = {
            "heading": "INT. OFFICE - DAY",
            "action": ["John enters the room.", "", "He sits down."],
        }
        result = ScreenplayUtils.format_scene_for_prompt(scene)
        expected = """SCENE HEADING: INT. OFFICE - DAY
ACTION:
John enters the room.
He sits down."""
        assert result == expected

    def test_format_with_dialogue(self):
        """Test formatting scene with dialogue."""
        scene = {
            "heading": "INT. OFFICE - DAY",
            "dialogue": [
                {"character": "JOHN", "text": "Hello there."},
                {"character": "MARY", "text": "Hi John!"},
            ],
        }
        result = ScreenplayUtils.format_scene_for_prompt(scene)
        expected = """SCENE HEADING: INT. OFFICE - DAY
DIALOGUE:
JOHN: Hello there.
MARY: Hi John!"""
        assert result == expected

    def test_format_complete_scene(self):
        """Test formatting complete scene with all elements."""
        scene = {
            "heading": "INT. OFFICE - DAY",
            "action": ["John enters."],
            "dialogue": [{"character": "JOHN", "text": "Is anyone here?"}],
        }
        result = ScreenplayUtils.format_scene_for_prompt(scene)
        expected = """SCENE HEADING: INT. OFFICE - DAY
ACTION:
John enters.
DIALOGUE:
JOHN: Is anyone here?"""
        assert result == expected

    def test_format_fallback_to_content(self):
        """Test formatting falls back to content field."""
        scene = {"content": "Raw scene content"}
        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert result == "Raw scene content"

    def test_format_empty_scene(self):
        """Test formatting empty scene."""
        scene = {}
        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert result == ""

    def test_format_dialogue_missing_fields(self):
        """Test formatting dialogue with missing fields."""
        scene = {
            "dialogue": [
                {"character": "JOHN", "text": "Hello"},
                {"character": "", "text": "No name"},  # Missing character
                {"character": "MARY", "text": ""},  # Missing text
                {"text": "No character"},  # Missing character field
            ]
        }
        result = ScreenplayUtils.format_scene_for_prompt(scene)
        assert result == "DIALOGUE:\nJOHN: Hello"


class TestFormatSceneForEmbedding:
    """Tests for format_scene_for_embedding method."""

    def test_format_with_original_text(self):
        """Test format prefers original text."""
        scene = {
            "original_text": (
                "/* SCRIPTRAG-META-START\nmeta\nSCRIPTRAG-META-END */\n"
                "INT. OFFICE - DAY\n\nScene content"
            ),
            "heading": "INT. OFFICE - DAY",
            "action": ["Different content"],
        }
        result = ScreenplayUtils.format_scene_for_embedding(scene)
        assert result == "INT. OFFICE - DAY\n\nScene content"

    def test_format_structured_data(self):
        """Test formatting from structured data."""
        scene = {
            "heading": "INT. OFFICE - DAY",
            "action": ["John enters.", "He looks around."],
            "dialogue": [
                {"character": "JOHN", "text": "Hello?"},
                {"character": "MARY", "text": "Over here!"},
            ],
        }
        result = ScreenplayUtils.format_scene_for_embedding(scene)
        expected = """Scene: INT. OFFICE - DAY
Action: John enters. He looks around.
JOHN: Hello?
MARY: Over here!"""
        assert result == expected

    def test_format_action_compression(self):
        """Test action lines are compressed to single line."""
        scene = {
            "action": ["Line 1", "", "  Line 2  ", "Line 3"],
        }
        result = ScreenplayUtils.format_scene_for_embedding(scene)
        assert result == "Action: Line 1 Line 2 Line 3"

    def test_format_fallback_to_content(self):
        """Test fallback to content field."""
        scene = {"content": "Fallback content"}
        result = ScreenplayUtils.format_scene_for_embedding(scene)
        assert result == "Fallback content"

    def test_format_empty_scene(self):
        """Test formatting empty scene."""
        scene = {}
        result = ScreenplayUtils.format_scene_for_embedding(scene)
        assert result == ""

    def test_format_heading_only(self):
        """Test formatting with only heading."""
        scene = {"heading": "EXT. PARK - MORNING"}
        result = ScreenplayUtils.format_scene_for_embedding(scene)
        assert result == "Scene: EXT. PARK - MORNING"

    def test_format_dialogue_only(self):
        """Test formatting with only dialogue."""
        scene = {
            "dialogue": [
                {"character": "ALICE", "text": "Where are we?"},
                {"character": "BOB", "text": "I don't know."},
            ]
        }
        result = ScreenplayUtils.format_scene_for_embedding(scene)
        expected = """ALICE: Where are we?
BOB: I don't know."""
        assert result == expected

    def test_format_with_invalid_dialogue(self):
        """Test formatting skips invalid dialogue entries."""
        scene = {
            "dialogue": [
                {"character": "VALID", "text": "Good line"},
                {"character": "", "text": "No character"},
                {"character": "NOTEXT", "text": ""},
                {},
            ]
        }
        result = ScreenplayUtils.format_scene_for_embedding(scene)
        assert result == "VALID: Good line"

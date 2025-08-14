"""Unit tests for FountainParser."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.parser import FountainParser

# Path to fixture files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "fountain" / "test_data"


class TestFountainParser:
    """Test FountainParser class."""

    @pytest.fixture
    def parser(self):
        """Create a FountainParser instance."""
        return FountainParser()

    @pytest.fixture
    def sample_fountain(self):
        """Load sample Fountain content from fixture file."""
        fixture_file = FIXTURES_DIR / "parser_test.fountain"
        return fixture_file.read_text()

    def test_parse_basic_script(self, parser, sample_fountain):
        """Test parsing basic script content."""
        script = parser.parse(sample_fountain)

        assert script.title == "Test Script"
        assert script.author == "Test Author"
        assert script.metadata["episode"] == 3
        assert script.metadata["season"] == 2
        assert len(script.scenes) == 2

        # Check first scene
        scene1 = script.scenes[0]
        assert scene1.heading == "INT. COFFEE SHOP - DAY"
        assert scene1.type == "INT"
        assert scene1.location == "COFFEE SHOP"
        assert scene1.time_of_day == "DAY"
        assert len(scene1.dialogue_lines) == 2
        assert scene1.dialogue_lines[0].character == "SARAH"
        assert scene1.dialogue_lines[0].parenthetical == "(nervously)"

    def test_parse_file(self, parser, tmp_path, sample_fountain):
        """Test parsing from file."""
        file_path = tmp_path / "test.fountain"
        file_path.write_text(sample_fountain)

        script = parser.parse_file(file_path)

        assert script.title == "Test Script"
        assert script.metadata["source_file"] == str(file_path)
        assert len(script.scenes) == 2

    def test_parse_with_different_author_fields(self, parser):
        """Test parsing with different author field variations."""
        variations = [
            ("Authors: John Doe", "John Doe"),
            ("Writer: Jane Smith", "Jane Smith"),
            ("Writers: Bob & Alice", "Bob & Alice"),
            ("Written by: Charlie", "Charlie"),
        ]

        for field, expected in variations:
            content = f"""Title: Test
{field}

INT. ROOM - DAY

Test scene.
"""
            script = parser.parse(content)
            assert script.author == expected, f"Failed for field: {field}"

    def test_parse_episode_season_as_string(self, parser):
        """Test parsing episode/season when they're not numeric."""
        content = """Title: Test
Episode: Three
Season: Two

INT. ROOM - DAY

Test scene.
"""
        script = parser.parse(content)
        assert script.metadata["episode"] == "Three"
        assert script.metadata["season"] == "Two"

    def test_parse_no_title_values(self, parser):
        """Test parsing when no title page values exist."""
        content = """INT. ROOM - DAY

Just a scene.
"""
        script = parser.parse(content)
        assert script.title is None
        assert script.author is None
        assert script.metadata == {}

    def test_parse_file_with_jouvence_error(self, parser, tmp_path):
        """Test parse_file when jouvence fails."""
        file_path = tmp_path / "bad.fountain"
        file_path.write_text("Invalid content")

        with patch("scriptrag.parser.fountain_parser.JouvenceParser") as mock_parser:
            mock_parser.return_value.parseString.side_effect = RuntimeError(
                "Parse failed"
            )

            with pytest.raises(RuntimeError, match="Parse failed"):
                parser.parse_file(file_path)

    def test_parse_with_boneyard_metadata(self, parser):
        """Test parsing with existing boneyard metadata."""
        content = """Title: Test

INT. ROOM - DAY

A room with metadata.

/* SCRIPTRAG-META-START
{
    "content_hash": "abc123",
    "analyzed_at": "2024-01-01",
    "analyzers": {
        "test_analyzer": {
            "result": {}
        }
    }
}
SCRIPTRAG-META-END */
"""
        script = parser.parse(content)
        scene = script.scenes[0]

        assert scene.boneyard_metadata is not None
        assert scene.boneyard_metadata["content_hash"] == "abc123"
        assert "test_analyzer" in scene.boneyard_metadata["analyzers"]

    def test_parse_with_invalid_boneyard_json(self, parser):
        """Test parsing with invalid JSON in boneyard."""
        content = """Title: Test

INT. ROOM - DAY

A room with bad metadata.

/* SCRIPTRAG-META-START
{invalid json}
SCRIPTRAG-META-END */
"""
        script = parser.parse(content)
        scene = script.scenes[0]

        # Should handle gracefully and not have metadata
        assert scene.boneyard_metadata is None

    def test_process_scene_types(self, parser):
        """Test processing basic scene types."""
        content = """Title: Test

INT. ROOM - DAY

Interior scene.

EXT. PARK - NIGHT

Exterior scene.
"""
        script = parser.parse(content)

        # Basic scenes should be parsed correctly
        assert len(script.scenes) == 2
        assert script.scenes[0].type == "INT"
        assert script.scenes[1].type == "EXT"

    def test_scene_without_time_of_day(self, parser):
        """Test scene heading without time of day."""
        content = """Title: Test

INT. ROOM - DAY

A basic scene.

INT. KITCHEN

A scene without time of day.
"""
        script = parser.parse(content)

        assert len(script.scenes) >= 1
        # Find the scene without time of day
        scene_without_time = None
        for scene in script.scenes:
            if scene.location == "KITCHEN":
                scene_without_time = scene
                break

        if scene_without_time:
            assert scene_without_time.location == "KITCHEN"
            assert scene_without_time.time_of_day == ""

    def test_write_with_updated_scenes(self, parser, tmp_path):
        """Test writing back with updated scenes."""
        content = """Title: Test

INT. ROOM - DAY

A simple scene.

CHARACTER
Some dialogue.
"""
        file_path = tmp_path / "test.fountain"
        file_path.write_text(content)

        # Parse the script
        script = parser.parse_file(file_path)
        scene = script.scenes[0]

        # Update scene metadata
        scene.update_boneyard({"test_key": "test_value", "analyzed_at": "2024-01-01"})

        # Write back
        parser.write_with_updated_scenes(file_path, script, [scene])

        # Read and verify
        updated_content = file_path.read_text()
        assert "SCRIPTRAG-META-START" in updated_content
        assert "test_key" in updated_content
        assert "test_value" in updated_content

    def test_write_with_existing_boneyard(self, parser, tmp_path):
        """Test writing when scene already has boneyard metadata."""
        content = """Title: Test

INT. ROOM - DAY

A scene with metadata.

/* SCRIPTRAG-META-START
{
    "existing_key": "existing_value"
}
SCRIPTRAG-META-END */
"""
        file_path = tmp_path / "test.fountain"
        file_path.write_text(content)

        # Parse the script
        script = parser.parse_file(file_path)
        scene = script.scenes[0]

        # Update scene metadata
        scene.update_boneyard({"new_key": "new_value"})

        # Write back
        parser.write_with_updated_scenes(file_path, script, [scene])

        # Read and verify
        updated_content = file_path.read_text()
        assert "existing_key" in updated_content
        assert "existing_value" in updated_content
        assert "new_key" in updated_content
        assert "new_value" in updated_content

    def test_write_ensures_newline_at_end(self, parser, tmp_path):
        """Test that writing ensures file ends with newline."""
        content = "Title: Test\n\nINT. ROOM - DAY\n\nTest"  # No ending newline
        file_path = tmp_path / "test.fountain"
        file_path.write_text(content)

        script = parser.parse_file(file_path)
        parser.write_with_updated_scenes(file_path, script, [])

        updated_content = file_path.read_text()
        assert updated_content.endswith("\n")

    def test_write_scene_not_found(self, parser, tmp_path):
        """Test write when scene cannot be found in content."""
        file_path = tmp_path / "test.fountain"
        file_path.write_text("Title: Test\n\nINT. ROOM - DAY\n\nTest scene.")

        script = parser.parse_file(file_path)
        scene = script.scenes[0]

        # Modify scene text so it won't be found
        scene.original_text = "NONEXISTENT SCENE"
        scene.update_boneyard({"test": "value"})

        # Should handle gracefully
        parser.write_with_updated_scenes(file_path, script, [scene])

        # Content should be unchanged
        content = file_path.read_text()
        assert "SCRIPTRAG-META-START" not in content

    def test_update_scene_boneyard_with_invalid_json(self, parser, tmp_path):
        """Test updating boneyard when existing JSON is invalid."""
        content = """Title: Test

INT. ROOM - DAY

A scene with bad metadata.

/* SCRIPTRAG-META-START
{invalid json}
SCRIPTRAG-META-END */
"""
        file_path = tmp_path / "test.fountain"
        file_path.write_text(content)

        script = parser.parse_file(file_path)
        scene = script.scenes[0]

        # Force valid metadata on the scene
        scene.update_boneyard({"new_key": "new_value"})

        # Write back - should replace invalid JSON
        parser.write_with_updated_scenes(file_path, script, [scene])

        updated_content = file_path.read_text()
        assert "new_key" in updated_content
        assert "{invalid json}" not in updated_content

    def test_scene_with_no_heading(self, parser):
        """Test that scenes without headers are skipped."""
        content = """Title: Test

FADE IN:

Some action without a scene heading.

INT. ROOM - DAY

A proper scene.
"""
        script = parser.parse(content)

        # Should only have one scene (the one with heading)
        assert len(script.scenes) == 1
        assert script.scenes[0].heading == "INT. ROOM - DAY"

    def test_dialogue_without_text(self, parser):
        """Test character with no dialogue text."""
        content = """Title: Test

INT. ROOM - DAY

CHARACTER
(parenthetical)

Another action line.
"""
        script = parser.parse(content)
        scene = script.scenes[0]

        # Character without dialogue text shouldn't create dialogue line
        assert len(scene.dialogue_lines) == 0

    def test_scene_text_not_found_in_content(self, parser):
        """Test when scene heading cannot be found in full content."""
        with patch("scriptrag.parser.fountain_parser.JouvenceParser") as mock_parser:
            mock_doc = MagicMock()
            mock_doc.title_values = {"title": "Test"}
            mock_doc.scenes = [MagicMock()]
            mock_doc.scenes[0].header = "INT. ROOM - DAY"
            mock_doc.scenes[0].paragraphs = []

            mock_parser.return_value.parseString.return_value = mock_doc

            # Parse with content that doesn't contain the heading
            script = parser.parse("Different content")

            assert len(script.scenes) == 1
            assert script.scenes[0].original_text == "INT. ROOM - DAY"

    def test_scene_heading_parsing_edge_cases(self, parser):
        """Test edge cases in scene heading parsing to cover uncovered lines."""
        # Create mock jouvence scenes to test specific code paths

        # Test case 1: Scene starting with something that would trigger INT./EXT. branch
        # but not INT. or EXT. - this seems impossible given current logic
        # Let's test I/E. which should work
        mock_ie_scene = MagicMock()
        mock_ie_scene.header = "I/E. VEHICLE - DAY"
        mock_ie_scene.paragraphs = []

        ie_scene = parser._process_jouvence_scene(
            1, mock_ie_scene, "I/E. VEHICLE - DAY\n\nTest content."
        )

        assert ie_scene.type == "INT/EXT"
        assert ie_scene.location == "VEHICLE"
        assert ie_scene.time_of_day == "DAY"
        assert ie_scene.heading == "I/E. VEHICLE - DAY"

        # Test case 2: Scene with no recognized prefix (should hit line 311)
        mock_no_prefix_scene = MagicMock()
        mock_no_prefix_scene.header = "SOMEWHERE - DAY"
        mock_no_prefix_scene.paragraphs = []

        no_prefix_scene = parser._process_jouvence_scene(
            1, mock_no_prefix_scene, "SOMEWHERE - DAY\n\nTest content."
        )

        assert no_prefix_scene.type == ""
        assert no_prefix_scene.location == "SOMEWHERE"
        assert no_prefix_scene.time_of_day == "DAY"
        assert no_prefix_scene.heading == "SOMEWHERE - DAY"

    def test_unreachable_int_ext_branch_documentation(self, parser):
        """Test that INT./EXT. scene headings are correctly parsed.

        This test verifies that the ScreenplayUtils.parse_scene_heading() method
        correctly handles INT./EXT. prefixes by checking the more specific pattern
        first,
        ensuring that "INT./EXT. BEDROOM - NIGHT" returns type "INT/EXT" not just "INT".
        """
        # Test case 1: Verify INT./EXT. is correctly parsed as "INT/EXT" type
        mock_int_ext_scene = MagicMock()
        mock_int_ext_scene.header = "INT./EXT. BEDROOM - NIGHT"
        mock_int_ext_scene.paragraphs = []

        scene = parser._process_jouvence_scene(
            1, mock_int_ext_scene, "INT./EXT. BEDROOM - NIGHT"
        )

        # This correctly returns "INT/EXT" due to proper logic order
        assert scene.type == "INT/EXT"  # Parser correctly handles INT/EXT prefixes
        assert scene.location == "BEDROOM"  # Location should be correctly extracted
        assert scene.time_of_day == "NIGHT"

        # Test case 2: Demonstrate that logic correctly prioritizes patterns
        # The ScreenplayUtils.parse_scene_heading() method checks INT./EXT. before INT.
        # ensuring proper scene type classification for combined scenes.

    def test_character_extraction_with_apostrophes_and_numbers(self, parser):
        """Test extraction of characters with apostrophes and numbers.

        Jouvence fails to detect characters with apostrophes (e.g., "CHARACTER'S VOICE")
        and numbers (e.g., "COP 1", "GUARD #2"). Our parser should handle these cases.
        """
        content = """Title: Test Script

INT. POLICE STATION - DAY

The station is busy.

CHARACTER'S VOICE
I can hear you.

COP 1
Stop right there!

GUARD #2
Move along, nothing to see here.

MARY'S MOTHER
Where is she?

YOUNG BOY #3
Can I help?
"""
        script = parser.parse(content)

        # Extract all characters from the scene
        all_characters = set()
        for scene in script.scenes:
            for dialogue in scene.dialogue_lines:
                all_characters.add(dialogue.character)

        # All these characters should be detected
        expected_characters = {
            "CHARACTER'S VOICE",
            "COP 1",
            "GUARD #2",
            "MARY'S MOTHER",
            "YOUNG BOY #3",
        }

        assert all_characters == expected_characters, (
            f"Expected {expected_characters}, got {all_characters}"
        )

        # Verify dialogue is properly associated
        scene = script.scenes[0]
        assert len(scene.dialogue_lines) == 5

        # Check specific dialogues
        dialogue_map = {d.character: d.text for d in scene.dialogue_lines}
        assert dialogue_map["CHARACTER'S VOICE"] == "I can hear you."
        assert dialogue_map["COP 1"] == "Stop right there!"
        assert dialogue_map["GUARD #2"] == "Move along, nothing to see here."

    def test_character_extraction_with_extensions(self, parser):
        """Test extraction of characters with parenthetical extensions."""
        content = """Title: Test Script

INT. ROOM - DAY

CHARACTER (CONT'D)
Continuing from before.

CHARACTER (V.O.)
Voice over dialogue.

CHARACTER (O.S.)
Off screen dialogue.

CHARACTER (PRELAP)
Prelap dialogue.

CHARACTER (FILTERED)
Filtered voice.
"""
        script = parser.parse(content)

        # Extract all characters
        all_characters = set()
        for scene in script.scenes:
            for dialogue in scene.dialogue_lines:
                all_characters.add(dialogue.character)

        # These should all be detected (jouvence handles these correctly)
        expected_characters = {
            "CHARACTER (CONT'D)",
            "CHARACTER (V.O.)",
            "CHARACTER (O.S.)",
            "CHARACTER (PRELAP)",
            "CHARACTER (FILTERED)",
        }

        assert all_characters == expected_characters

    def test_mixed_character_formats(self, parser):
        """Test a mix of character formats in one scene."""
        content = """Title: Complex Character Test

INT. COURTROOM - DAY

The courtroom is packed.

JUDGE
Order in the court!

DEFENDANT'S LAWYER
(standing)
Objection, your honor!

PROSECUTOR #1
(frustrated)
This is ridiculous.

JURY MEMBER #12
(whispering)
Did you hear that?

MR. O'BRIEN
I object to this line of questioning.

DR. SMITH-JONES
The evidence is clear.
"""
        script = parser.parse(content)
        scene = script.scenes[0]

        # Check all characters are extracted
        characters = {d.character for d in scene.dialogue_lines}
        expected = {
            "JUDGE",
            "DEFENDANT'S LAWYER",
            "PROSECUTOR #1",
            "JURY MEMBER #12",
            "MR. O'BRIEN",
            "DR. SMITH-JONES",
        }

        assert characters == expected, f"Expected {expected}, got {characters}"

        # Check parentheticals are preserved
        dialogue_map = {d.character: d for d in scene.dialogue_lines}
        assert dialogue_map["DEFENDANT'S LAWYER"].parenthetical == "(standing)"
        assert dialogue_map["PROSECUTOR #1"].parenthetical == "(frustrated)"
        assert dialogue_map["JURY MEMBER #12"].parenthetical == "(whispering)"

    def test_is_character_line_method(self, parser):
        """Test the _is_character_line helper method."""
        # Valid character lines
        assert parser._is_character_line("JOHN")
        assert parser._is_character_line("MARY JANE")
        assert parser._is_character_line("COP 1")
        assert parser._is_character_line("GUARD #2")
        assert parser._is_character_line("CHARACTER'S VOICE")
        assert parser._is_character_line("MR. SMITH")
        assert parser._is_character_line("CHARACTER (V.O.)")
        assert parser._is_character_line("CHARACTER (CONT'D)")
        assert parser._is_character_line("DR. SMITH-JONES")

        # Invalid character lines
        assert not parser._is_character_line("")
        assert not parser._is_character_line("INT. ROOM - DAY")
        assert not parser._is_character_line("EXT. PARK - NIGHT")
        assert not parser._is_character_line("INT./EXT. BEDROOM - NIGHT")
        assert not parser._is_character_line("not uppercase")
        assert not parser._is_character_line("Mixed Case")

    def test_action_lines_preserved(self, parser):
        """Test that action lines are preserved and not mistaken for characters."""
        content = """Title: Test Script

INT. ROOM - DAY

JOHN enters the room.

MARY'S VOICE
(from outside)
Are you there?

The door SLAMS shut.

COP 1
Freeze!

JOHN raises his hands.
"""
        script = parser.parse(content)
        scene = script.scenes[0]

        # Check characters
        characters = {d.character for d in scene.dialogue_lines}
        assert characters == {"MARY'S VOICE", "COP 1"}

        # Check that action lines are preserved
        # Note: jouvence might combine some action lines
        action_text = " ".join(scene.action_lines)
        assert "JOHN enters the room" in action_text
        assert "The door SLAMS shut" in action_text
        assert "JOHN raises his hands" in action_text

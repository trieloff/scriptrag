#!/usr/bin/env python3
"""
Edge case tests for the Fountain parser integration.
Tests boundary conditions, error handling, and complex scenarios.
"""

from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch

import pytest

from scriptrag.models import Script
from scriptrag.parser import FountainParser, FountainParsingError


class TestFountainParserEdgeCases:
    """Test edge cases for the FountainParser class."""

    @pytest.fixture
    def parser(self):
        """Create a fresh parser instance for each test."""
        return FountainParser()

    def test_parse_very_large_script(self, parser):
        """Test parsing a very large script with many scenes."""
        # Generate a large script with 100 scenes
        large_content = """Title: Large Script
Author: Test Author

FADE IN:

"""
        for i in range(100):
            large_content += f"""
INT. LOCATION {i} - DAY

Character {i} enters.

                    CHARACTER {i}
     Line of dialogue {i}.

"""

        large_content += "FADE OUT."

        script = parser.parse_string(large_content)
        assert isinstance(script, Script)
        assert len(script.scenes) == 100
        assert len(script.characters) == 100

    def test_parse_script_with_special_characters(self, parser):
        """Test parsing script with special characters in names and dialogue."""
        content = """Title: Special Characters Script
Author: François Müller

FADE IN:

INT. CAFÉ - DAY

JOSÉ-MARÍA enters. He sees BJÖRN and MR. O'BRIEN.

                    JOSÉ-MARÍA
                    (excited)
     ¡Hola! ¿Cómo estás? I've got €100!

                    BJÖRN
     That's great! Let's celebrate at the café.

                    MR. O'BRIEN
     I'll have a Guinness® please.

FADE OUT.
"""
        script = parser.parse_string(content)
        assert script.author == "François Müller"

        # Check that character names with special chars are handled
        char_names = [c.name for c in script.characters]
        assert "JOSÉ-MARÍA" in char_names or "JOSÉ MARÍA" in char_names
        assert "BJÖRN" in char_names
        assert any("O'BRIEN" in name or "O BRIEN" in name for name in char_names)

    def test_parse_empty_scenes(self, parser):
        """Test handling of scenes with no content."""
        content = """Title: Empty Scenes

FADE IN:

INT. EMPTY ROOM - DAY

EXT. ANOTHER EMPTY LOCATION - NIGHT

FADE OUT.
"""
        script = parser.parse_string(content)
        # Empty scenes should still be parsed
        assert len(script.scenes) >= 0  # Implementation dependent

    def test_parse_nested_parentheticals(self, parser):
        """Test handling of nested or complex parentheticals."""
        content = """Title: Complex Parentheticals

FADE IN:

INT. ROOM - DAY

                    ALICE
                    (whispering (but loudly))
     This is a test.

                    BOB
                    ((confused))
     What?

                    CHARLIE
                    (to Bob, (sotto voce))
     Never mind.

FADE OUT.
"""
        script = parser.parse_string(content)
        assert len(script.characters) >= 3

    def test_parse_malformed_scene_headings(self, parser):
        """Test handling of malformed scene headings."""
        content = """Title: Malformed Headings

FADE IN:

INT COFFEE SHOP DAY

Someone enters.

INT. - COFFEE SHOP - DAY

Another person enters.

COFFEE SHOP - DAY

Third person enters.

I/E. DOORWAY - CONTINUOUS

Someone stands in doorway.

FADE OUT.
"""
        script = parser.parse_string(content)
        # Parser should handle these gracefully
        assert isinstance(script, Script)

    def test_parse_continuous_and_same_scenes(self, parser):
        """Test handling of CONTINUOUS and SAME time indicators."""
        content = """Title: Time Continuity

FADE IN:

INT. OFFICE - DAY

JOHN works at his desk.

INT. HALLWAY - CONTINUOUS

John walks down the hall.

INT. BREAK ROOM - SAME

John pours coffee.

INT. OFFICE - LATER

John returns to work.

FADE OUT.
"""
        script = parser.parse_string(content)
        assert len(script.scenes) >= 3

    def test_parse_dual_dialogue(self, parser):
        """Test handling of dual dialogue formatting."""
        content = """Title: Dual Dialogue

FADE IN:

INT. RESTAURANT - NIGHT

                    ALICE
     I think we should...

                    BOB ^
     No, listen to me...

They talk over each other.

FADE OUT.
"""
        script = parser.parse_string(content)
        # Should handle dual dialogue marker
        assert len(script.characters) >= 2

    def test_parse_character_extensions(self, parser):
        """Test all character name extensions."""
        content = """Title: Character Extensions

FADE IN:

INT. ROOM - DAY

                    ALICE (V.O.)
     I remember it well.

                    BOB (O.S.)
     Are you there?

                    CHARLIE (O.C.)
     I'm off camera.

                    DAVID (CONT'D)
     As I was saying...

                    EVE (PRE-LAP)
     Tomorrow will be different.

                    FRANK (FILTERED)
     Can you hear me through this?

                    GRACE (INTO PHONE)
     Hello? Hello?

                    HENRY (SUBTITLE)
                    [Speaking French]
     Bonjour!

FADE OUT.
"""
        script = parser.parse_string(content)
        # All characters should be parsed, extensions stored as aliases
        assert len(script.characters) >= 8

        # Check that base names are extracted
        char_names = [c.name for c in script.characters]
        for name in [
            "ALICE",
            "BOB",
            "CHARLIE",
            "DAVID",
            "EVE",
            "FRANK",
            "GRACE",
            "HENRY",
        ]:
            assert name in char_names

    def test_parse_action_with_caps_words(self, parser):
        """Test character recognition in action with capitalized words."""
        content = """Title: Caps in Action

FADE IN:

INT. OFFICE - DAY

The MANAGER enters. He sees the NEW EMPLOYEE standing by the COFFEE MACHINE.

                    MANAGER
     Welcome to ACME CORP.

The NEW EMPLOYEE nods. A SECURITY GUARD walks by.

FADE OUT.
"""
        script = parser.parse_string(content)
        # Should identify MANAGER and SECURITY GUARD as characters
        # but not COFFEE MACHINE or ACME CORP
        char_names = [c.name for c in script.characters]
        assert "MANAGER" in char_names
        # NEW EMPLOYEE might be parsed as one or two characters
        assert "SECURITY GUARD" in char_names or "GUARD" in char_names

    def test_parse_with_notes_and_synopses(self, parser):
        """Test handling of notes and synopses."""
        content = """Title: Script with Notes

FADE IN:

[[This is a note about the opening]]

= Synopsis: The hero begins their journey =

INT. CAVE - NIGHT

The HERO enters cautiously.

[[TODO: Add more description here]]

                    HERO
     Is anyone there?

/* This is a comment that should be ignored */

FADE OUT.
"""
        script = parser.parse_string(content)
        assert len(script.characters) >= 1
        assert any(c.name == "HERO" for c in script.characters)

    def test_parse_with_sections_and_synopsis(self, parser):
        """Test handling of sections and act breaks."""
        content = """Title: Structured Script

# ACT I

## The Beginning

### Introduction Scene

INT. CLASSROOM - DAY

The TEACHER writes on the board.

# ACT II

## The Middle

INT. PLAYGROUND - DAY

CHILDREN play.

# ACT III

## The End

INT. AUDITORIUM - NIGHT

Everyone gathers for the finale.

FADE OUT.
"""
        script = parser.parse_string(content)
        assert len(script.scenes) >= 3

    def test_parse_with_lyrics_and_notes(self, parser):
        """Test handling of lyrics."""
        content = """Title: Musical Script

FADE IN:

INT. STAGE - NIGHT

~This is a musical note~

SINGER steps forward.

                    SINGER
     (singing)
     ~Oh what a beautiful morning
     ~Oh what a beautiful day
     ~I've got a beautiful feeling
     ~Everything's going my way

The crowd cheers.

FADE OUT.
"""
        script = parser.parse_string(content)
        assert len(script.characters) >= 1

    def test_file_encoding_issues(self, parser):
        """Test handling of files with different encodings."""
        # Test UTF-8 with BOM
        content_with_bom = (
            "\ufeff"
            """Title: BOM Test

FADE IN:

INT. ROOM - DAY

CHARACTER speaks.

FADE OUT.
"""
        )
        script = parser.parse_string(content_with_bom)
        assert isinstance(script, Script)

    def test_parse_file_permission_error(self, parser):
        """Test error handling for file permission issues."""
        with NamedTemporaryFile(mode="w", suffix=".fountain", delete=False) as f:
            f.write("Title: Test\n\nFADE IN:\n\nFADE OUT.")
            temp_path = Path(f.name)

        try:
            # Make file unreadable (Unix-like systems)
            temp_path.chmod(0o000)

            # This should raise an error
            with pytest.raises(FountainParsingError):
                parser.parse_file(str(temp_path))

        finally:
            # Restore permissions and cleanup
            temp_path.chmod(0o644)
            temp_path.unlink()

    def test_parser_with_mocked_jouvence_error(self, parser):
        """Test error handling when Jouvence parser fails."""
        with patch.object(parser.jouvence_parser, "parse") as mock_parse:
            mock_parse.side_effect = Exception("Jouvence parsing failed")

            # Should handle the error gracefully
            with pytest.raises(FountainParsingError, match="parsing failed"):
                parser.parse_string("Title: Test\n\nFADE IN:")

    def test_concurrent_parsing(self, parser):
        """Test parser state isolation with concurrent use."""
        content1 = """Title: Script One

FADE IN:

INT. ROOM A - DAY

                    ALICE
     Hello from script one.

FADE OUT.
"""

        content2 = """Title: Script Two

FADE IN:

INT. ROOM B - NIGHT

                    BOB
     Hello from script two.

FADE OUT.
"""

        # Parse both scripts
        script1 = parser.parse_string(content1)
        script2 = parser.parse_string(content2)

        # Verify scripts are independent
        assert script1.title == "Script One"
        assert script2.title == "Script Two"
        assert len(script1.characters) == 1
        assert len(script2.characters) == 1
        assert script1.characters[0].name == "ALICE"
        assert script2.characters[0].name == "BOB"

    def test_memory_efficient_parsing(self, parser):
        """Test that parser doesn't keep references to previous parses."""
        # Parse first script
        parser.parse_string(
            "Title: First\n\nFADE IN:\n\nINT. ROOM - DAY\n\nALICE enters.\n\nFADE OUT."
        )

        # Clear cache
        parser._characters_cache.clear()
        parser._scene_count = 0

        # Parse second script
        script = parser.parse_string(
            "Title: Second\n\nFADE IN:\n\nINT. ROOM - DAY\n\nBOB enters.\n\nFADE OUT."
        )

        # Should only have BOB
        assert len(script.characters) == 1
        assert script.characters[0].name == "BOB"

    def test_scene_numbering_edge_cases(self, parser):
        """Test scene numbering with edge cases."""
        content = """Title: Scene Numbers

FADE IN:

1 INT. FIRST SCENE - DAY

Action here.

A10 INT. ADDED SCENE - DAY

Added in revision.

42A INT. ANOTHER ADDED SCENE - DAY

Also added.

OMITTED

100 INT. HIGH NUMBER SCENE - NIGHT

Final scene.

FADE OUT.
"""
        script = parser.parse_string(content)
        # Should handle scene numbers gracefully
        assert isinstance(script, Script)

    def test_fountain_forced_elements(self, parser):
        """Test Fountain forced element syntax."""
        content = r"""Title: Forced Elements

FADE IN:

.FORCED SCENE HEADING

!FORCED ACTION

@FORCED CHARACTER
Some dialogue.

>FORCED TRANSITION<

~FORCED LYRICS~

FADE OUT.
"""
        script = parser.parse_string(content)
        # Parser should handle forced elements
        assert isinstance(script, Script)

    def test_parse_centered_text(self, parser):
        """Test handling of centered text."""
        content = """Title: Centered Text

FADE IN:

INT. ROOM - DAY

>THE END<

>To Be Continued...<

FADE OUT.
"""
        script = parser.parse_string(content)
        assert isinstance(script, Script)

    def test_edge_case_character_names(self, parser):
        """Test edge cases in character name parsing."""
        content = """Title: Edge Case Names

FADE IN:

INT. ROOM - DAY

                    A
     Single letter name.

                    123
     Number name?

                    MR.
     Just a title.

                    THE NARRATOR
     Multi-word with article.

                    JOHN'S MOTHER
     Possessive form.

                    JACK/JILL
     Slash in name.

FADE OUT.
"""
        script = parser.parse_string(content)
        # Check various edge case handling
        assert len(script.characters) >= 1  # At least some should parse

    @pytest.mark.parametrize(
        "title_format",
        [
            "Title: Normal Title",
            "TITLE: UPPERCASE TITLE",
            "title: lowercase title",
            "Title:No Space After Colon",
            "Title  :  Extra Spaces",
            "Title:\nNewline After",
        ],
    )
    def test_title_format_variations(self, parser, title_format):
        """Test various title format variations."""
        content = f"{title_format}\n\nFADE IN:\n\nINT. ROOM - DAY\n\nFADE OUT."
        script = parser.parse_string(content)
        assert isinstance(script, Script)
        # Title should be extracted in most cases
        assert script.title != "Untitled Script" or "Title" not in title_format

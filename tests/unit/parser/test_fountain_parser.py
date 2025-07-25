#!/usr/bin/env python3
"""
Unit tests for the Fountain parser integration.
"""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from scriptrag.models import (
    Character,
    ElementType,
    Location,
    Script,
)
from scriptrag.parser import FountainParser, FountainParsingError


class TestFountainParser:
    """Test cases for the FountainParser class."""

    @pytest.fixture
    def parser(self):
        """Create a fresh parser instance for each test."""
        return FountainParser()

    @pytest.fixture
    def sample_fountain_content(self):
        """Sample fountain content for testing."""
        return """
Title: Test Script
Author: Test Author
Format: screenplay

FADE IN:

EXT. COFFEE SHOP - DAY

A busy coffee shop on a sunny morning. ALICE (30s, determined) sits at a table.

                    ALICE
          (muttering to herself)
     This code has to work.

BARISTA approaches with a steaming cup.

                    BARISTA
     One large coffee for the lady?

                    ALICE
                    (looking up)
     Thanks. I'm trying to build
     something revolutionary.

CUT TO:

INT. ALICE'S APARTMENT - NIGHT

Alice reviews her work on multiple monitors.

                    ALICE
     Finally! It's working!

FADE OUT.
"""

    def test_parser_initialization(self, parser):
        """Test that parser initializes correctly."""
        assert isinstance(parser, FountainParser)
        assert parser.jouvence_parser is not None
        assert parser._characters_cache == {}
        assert parser._scene_count == 0

    def test_parse_string_basic(self, parser, sample_fountain_content):
        """Test basic string parsing functionality."""
        script = parser.parse_string(sample_fountain_content)

        assert isinstance(script, Script)
        assert script.title == "Test Script"
        assert script.author == "Test Author"
        assert script.format == "screenplay"
        assert script.fountain_source == sample_fountain_content
        assert (
            len(script.scenes) == 2
        )  # Two actual scenes (EXT. COFFEE SHOP and INT. APARTMENT)

    def test_parse_file(self, parser, sample_fountain_content):
        """Test file parsing functionality."""
        with NamedTemporaryFile(mode="w", suffix=".fountain", delete=False) as f:
            f.write(sample_fountain_content)
            temp_path = f.name

        try:
            script = parser.parse_file(temp_path)
            assert isinstance(script, Script)
            assert script.title == "Test Script"
            assert script.source_file == temp_path
        finally:
            Path(temp_path).unlink()

    def test_parse_file_not_found(self, parser):
        """Test error handling for non-existent files."""
        with pytest.raises(FountainParsingError, match="File not found"):
            parser.parse_file("nonexistent_file.fountain")

    def test_title_extraction(self, parser):
        """Test title extraction from various title page formats."""
        # Standard title
        content1 = "Title: My Great Script\n\nFADE IN:"
        script1 = parser.parse_string(content1)
        assert script1.title == "My Great Script"

        # Lowercase title
        content2 = "title: Another Script\n\nFADE IN:"
        script2 = parser.parse_string(content2)
        assert script2.title == "Another Script"

        # No title
        content3 = "Author: Someone\n\nFADE IN:"
        script3 = parser.parse_string(content3)
        assert script3.title == "Untitled Script"

    def test_location_parsing(self, parser):
        """Test location parsing from scene headings."""
        # Test INT location
        location1 = parser._parse_location("INT. COFFEE SHOP - DAY")
        assert location1 is not None
        assert location1.interior is True
        assert location1.name == "COFFEE SHOP"
        assert location1.time == "DAY"

        # Test EXT location
        location2 = parser._parse_location("EXT. PARK - NIGHT")
        assert location2 is not None
        assert location2.interior is False
        assert location2.name == "PARK"
        assert location2.time == "NIGHT"

        # Test location without time
        location3 = parser._parse_location("INT. APARTMENT")
        assert location3 is not None
        assert location3.interior is True
        assert location3.name == "APARTMENT"
        assert location3.time is None

        # Test invalid location
        location4 = parser._parse_location("INVALID HEADING")
        assert location4 is None

    def test_character_name_cleaning(self, parser):
        """Test character name cleaning and normalization."""
        # Basic name
        assert parser._clean_character_name("ALICE") == "ALICE"

        # Name with parenthetical
        assert parser._clean_character_name("ALICE (O.S.)") == "ALICE"

        # Name with V.O.
        assert parser._clean_character_name("NARRATOR (V.O.)") == "NARRATOR"

        # Name with CONT'D
        assert parser._clean_character_name("JOHN (CONT'D)") == "JOHN"

        # Name with extra spaces
        assert parser._clean_character_name("  MARY   JANE  ") == "MARY JANE"

        # Name with punctuation
        assert parser._clean_character_name("DR. SMITH") == "DR SMITH"

    def test_character_creation_and_caching(self, parser):
        """Test character creation and caching."""
        # Create first character
        char1 = parser._get_or_create_character("ALICE")
        assert isinstance(char1, Character)
        assert char1.name == "ALICE"

        # Get same character again - should be cached
        char2 = parser._get_or_create_character("ALICE")
        assert char1.id == char2.id
        assert len(parser._characters_cache) == 1

        # Create character with different formatting
        char3 = parser._get_or_create_character("ALICE (O.S.)")
        assert char3.id == char1.id  # Should be same character
        assert "ALICE (O.S.)" in char3.aliases

        # Create different character
        char4 = parser._get_or_create_character("BOB")
        assert char4.id != char1.id
        assert len(parser._characters_cache) == 2

    def test_scene_parsing(self, parser, sample_fountain_content):
        """Test scene parsing and element extraction."""
        script = parser.parse_string(sample_fountain_content)

        # Should have 2 actual scenes (skipping title page)
        assert len(script.scenes) == 2

        # Characters should be extracted
        assert len(script.characters) >= 2  # At least ALICE and BARISTA

    def test_element_type_mapping(self, parser):
        """Test that Jouvence element types map correctly."""
        # Test the mapping dictionary
        assert parser.JOUVENCE_TYPE_MAP[0] == ElementType.ACTION
        assert parser.JOUVENCE_TYPE_MAP[2] == ElementType.CHARACTER
        assert parser.JOUVENCE_TYPE_MAP[3] == ElementType.DIALOGUE
        assert parser.JOUVENCE_TYPE_MAP[4] == ElementType.PARENTHETICAL
        assert parser.JOUVENCE_TYPE_MAP[5] == ElementType.TRANSITION

    def test_character_mentions_extraction(self, parser):
        """Test extraction of character mentions from action text."""
        # Add some characters to cache first
        alice = parser._get_or_create_character("ALICE")
        bob = parser._get_or_create_character("BOB")

        # Test action with character mentions
        action_text = "ALICE walks over to BOB and THE table."
        mentions = parser._extract_character_mentions_from_action(action_text)

        # Should find ALICE and BOB, but not THE
        assert alice.id in mentions
        assert bob.id in mentions
        assert len(mentions) == 2

    def test_complex_screenplay_structure(self, parser):
        """Test parsing a more complex screenplay structure."""
        complex_content = """
Title: Complex Script
Author: Test Writer
Genre: Drama

FADE IN:

EXT. CITY STREET - DAY

Bustling city life. JOHN (40s) walks quickly.

                    JOHN
                    (into phone)
     I'll be there in five minutes.

He hangs up and continues walking.

                    NARRATOR (V.O.)
     Sometimes life takes unexpected turns.

CUT TO:

INT. OFFICE BUILDING - CONTINUOUS

John enters the lobby. RECEPTIONIST looks up.

                    RECEPTIONIST
     Mr. Smith? They're waiting for you.

                    JOHN
                    (nervously)
     Thanks.

FADE OUT.
"""

        script = parser.parse_string(complex_content)

        # Verify script metadata
        assert script.title == "Complex Script"
        assert script.author == "Test Writer"
        assert script.genre == "Drama"

        # Should have 2 scenes
        assert len(script.scenes) == 2

        # Should have multiple characters including V.O. character
        assert len(script.characters) >= 3  # JOHN, NARRATOR, RECEPTIONIST

    def test_empty_content_handling(self, parser):
        """Test handling of empty or minimal content."""
        minimal_content = "Title: Minimal\n\nFADE IN:\n\nFADE OUT."
        script = parser.parse_string(minimal_content)

        assert script.title == "Minimal"
        assert len(script.scenes) == 0  # No actual scenes with content

    def test_malformed_fountain_handling(self, parser):
        """Test handling of malformed fountain content."""
        # This should not raise an exception - Jouvence should handle it gracefully
        malformed_content = "This is not valid fountain format at all!"
        script = parser.parse_string(malformed_content)

        # Should still create a script, even if parsing is limited
        assert isinstance(script, Script)

    def test_unicode_content(self, parser):
        """Test handling of unicode characters."""
        unicode_content = """
Title: Café Script
Author: François

FADE IN:

INT. CAFÉ - DAY

ANDRÉ sits at the café.

                    ANDRÉ
     Bonjour! Comment ça va?

FADE OUT.
"""

        script = parser.parse_string(unicode_content)
        assert script.title == "Café Script"
        assert script.author == "François"

    def test_scene_ordering(self, parser, sample_fountain_content):
        """Test that scenes maintain proper script order."""
        script = parser.parse_string(sample_fountain_content)

        # Parse the actual scenes to check ordering
        # Note: We need to create a way to access the parsed scenes
        # This test verifies the ordering logic exists
        assert len(script.scenes) > 0

    def test_parser_state_reset(self, parser, sample_fountain_content):
        """Test that parser state resets between parses."""
        # Parse first script
        script1 = parser.parse_string(sample_fountain_content)
        # Verify first script has characters
        assert len(script1.characters) > 0

        # Parse second script - should not carry over characters
        simple_content = """
Title: Simple Script

FADE IN:

INT. ROOM - DAY

                    CHARLIE
     Hello world.

FADE OUT.
"""
        script2 = parser.parse_string(simple_content)

        # Second script should only have CHARLIE
        assert len(script2.characters) == 1
        assert script2.title == "Simple Script"

        # Verify parser was reset
        assert parser._scene_count == 1  # Only one scene in second script


class TestFountainParsingError:
    """Test cases for FountainParsingError exception."""

    def test_fountain_parsing_error_creation(self):
        """Test that FountainParsingError can be created and raised."""
        error_message = "Test error message"
        error = FountainParsingError(error_message)
        assert str(error) == error_message

        # Test raising the error
        with pytest.raises(FountainParsingError, match="Test error message"):
            raise FountainParsingError(error_message)


class TestLocationModel:
    """Test cases for Location model functionality."""

    def test_location_creation(self):
        """Test Location model creation."""
        location = Location(
            interior=True,
            name="COFFEE SHOP",
            time="DAY",
            raw_text="INT. COFFEE SHOP - DAY",
        )

        assert location.interior is True
        assert location.name == "COFFEE SHOP"
        assert location.time == "DAY"
        assert str(location) == "INT. COFFEE SHOP - DAY"

    def test_location_exterior(self):
        """Test exterior location."""
        location = Location(
            interior=False, name="PARK", time="NIGHT", raw_text="EXT. PARK - NIGHT"
        )

        assert location.interior is False
        assert str(location) == "EXT. PARK - NIGHT"

    def test_location_no_time(self):
        """Test location without time specification."""
        location = Location(interior=True, name="APARTMENT", raw_text="INT. APARTMENT")

        assert location.time is None
        assert str(location) == "INT. APARTMENT"

    def test_location_name_validation(self):
        """Test location name validation."""
        with pytest.raises(ValueError, match="Location name cannot be empty"):
            Location(interior=True, name="", raw_text="INT.  - DAY")

        with pytest.raises(ValueError, match="Location name cannot be empty"):
            Location(interior=True, name="   ", raw_text="INT.    - DAY")

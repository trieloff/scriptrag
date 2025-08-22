"""Tests for screenplay utilities."""

from scriptrag.utils.screenplay import ScreenplayUtils


class TestScreenplayUtils:
    """Test ScreenplayUtils class."""

    def test_extract_location_empty(self):
        """Test extracting location from empty heading."""
        assert ScreenplayUtils.extract_location("") is None
        assert ScreenplayUtils.extract_location(None) is None

    def test_extract_location_int(self):
        """Test extracting location from INT scene."""
        assert (
            ScreenplayUtils.extract_location("INT. COFFEE SHOP - DAY") == "COFFEE SHOP"
        )
        assert (
            ScreenplayUtils.extract_location("INT COFFEE SHOP - DAY") == "COFFEE SHOP"
        )
        assert ScreenplayUtils.extract_location("INT. OFFICE") == "OFFICE"

    def test_extract_location_ext(self):
        """Test extracting location from EXT scene."""
        assert ScreenplayUtils.extract_location("EXT. PARK - NIGHT") == "PARK"
        assert ScreenplayUtils.extract_location("EXT STREET - DAWN") == "STREET"
        assert ScreenplayUtils.extract_location("EXT. BUILDING") == "BUILDING"

    def test_extract_location_int_ext(self):
        """Test extracting location from INT/EXT scene."""
        assert ScreenplayUtils.extract_location("INT./EXT. CAR - DAY") == "CAR"
        assert ScreenplayUtils.extract_location("I/E. HOUSE - NIGHT") == "HOUSE"
        assert ScreenplayUtils.extract_location("I/E GARAGE") == "GARAGE"

    def test_extract_location_no_prefix(self):
        """Test extracting location with no prefix."""
        assert ScreenplayUtils.extract_location("COFFEE SHOP - DAY") == "COFFEE SHOP"
        assert ScreenplayUtils.extract_location("STREET") == "STREET"

    def test_extract_location_multiple_dashes(self):
        """Test extracting location with multiple dashes."""
        assert (
            ScreenplayUtils.extract_location("INT. RESTAURANT - MAIN ROOM - NIGHT")
            == "RESTAURANT - MAIN ROOM"
        )

    def test_extract_location_whitespace_only(self):
        """Test extracting location from whitespace-only heading."""
        assert ScreenplayUtils.extract_location("   ") is None
        assert ScreenplayUtils.extract_location("INT.   ") is None
        # "INT. - DAY" actually extracts "" which becomes None
        result = ScreenplayUtils.extract_location("INT. - DAY")
        # Should extract empty string between "INT. " and " - DAY" (treated as None)
        assert result == "" or result is None

    def test_extract_time_empty(self):
        """Test extracting time from empty heading."""
        assert ScreenplayUtils.extract_time("") is None
        assert ScreenplayUtils.extract_time(None) is None

    def test_extract_time_common(self):
        """Test extracting common time indicators."""
        assert ScreenplayUtils.extract_time("INT. COFFEE SHOP - DAY") == "DAY"
        assert ScreenplayUtils.extract_time("EXT. PARK - NIGHT") == "NIGHT"
        assert ScreenplayUtils.extract_time("INT. OFFICE - MORNING") == "MORNING"
        assert ScreenplayUtils.extract_time("EXT. STREET - EVENING") == "EVENING"

    def test_extract_time_special(self):
        """Test extracting special time indicators."""
        assert ScreenplayUtils.extract_time("INT. ROOM - DAWN") == "DAWN"
        assert ScreenplayUtils.extract_time("EXT. HILL - DUSK") == "DUSK"
        assert ScreenplayUtils.extract_time("INT. OFFICE - CONTINUOUS") == "CONTINUOUS"
        assert ScreenplayUtils.extract_time("INT. HALLWAY - LATER") == "LATER"
        # "MOMENTS LATER" contains "LATER" which is found first
        assert ScreenplayUtils.extract_time("INT. ROOM - MOMENTS LATER") == "LATER"

    def test_extract_time_sun_indicators(self):
        """Test extracting sun-related time indicators."""
        assert ScreenplayUtils.extract_time("EXT. BEACH - SUNSET") == "SUNSET"
        assert ScreenplayUtils.extract_time("EXT. MOUNTAIN - SUNRISE") == "SUNRISE"

    def test_extract_time_specific_times(self):
        """Test extracting specific time indicators."""
        assert ScreenplayUtils.extract_time("INT. DINER - NOON") == "NOON"
        # "MIDNIGHT" contains "NIGHT" which is found first
        assert ScreenplayUtils.extract_time("EXT. ALLEY - MIDNIGHT") == "NIGHT"

    def test_extract_time_no_dash(self):
        """Test extracting time without dash separator."""
        assert ScreenplayUtils.extract_time("INT. COFFEE SHOP DAY") == "DAY"
        assert ScreenplayUtils.extract_time("EXT. PARK NIGHT") == "NIGHT"

    def test_extract_time_no_time(self):
        """Test extracting time when no time is present."""
        assert ScreenplayUtils.extract_time("INT. COFFEE SHOP") is None
        assert ScreenplayUtils.extract_time("EXT. PARK") is None

    def test_extract_time_case_insensitive(self):
        """Test that time extraction is case insensitive."""
        assert ScreenplayUtils.extract_time("INT. COFFEE SHOP - day") == "DAY"
        assert ScreenplayUtils.extract_time("EXT. PARK - Night") == "NIGHT"
        assert ScreenplayUtils.extract_time("INT. OFFICE - MoRnInG") == "MORNING"

    def test_extract_time_afternoon(self):
        """Test extracting AFTERNOON time indicator."""
        assert ScreenplayUtils.extract_time("INT. OFFICE - AFTERNOON") == "AFTERNOON"
        assert ScreenplayUtils.extract_time("EXT. GARDEN AFTERNOON") == "AFTERNOON"

    def test_extract_time_embedded_in_last_part(self):
        """Test extracting time when embedded in last part after dash."""
        assert ScreenplayUtils.extract_time("INT. OFFICE - THE NEXT DAY") == "DAY"
        assert ScreenplayUtils.extract_time("EXT. STREET - THAT NIGHT") == "NIGHT"

    def test_extract_time_ignores_location_words(self):
        """Time indicators embedded in locations should not be detected."""
        assert ScreenplayUtils.extract_time("INT. SCHOOL - DAYCARE") is None

    def test_parse_scene_heading_empty(self):
        """Test parsing empty scene heading."""
        assert ScreenplayUtils.parse_scene_heading("") == ("", None, None)
        assert ScreenplayUtils.parse_scene_heading(None) == ("", None, None)

    def test_parse_scene_heading_int(self):
        """Test parsing INT scene heading."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "INT. COFFEE SHOP - DAY"
        )
        assert scene_type == "INT"
        assert location == "COFFEE SHOP"
        assert time == "DAY"

        scene_type, location, time = ScreenplayUtils.parse_scene_heading("INT OFFICE")
        assert scene_type == "INT"
        assert location == "OFFICE"
        assert time is None

    def test_parse_scene_heading_ext(self):
        """Test parsing EXT scene heading."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "EXT. PARK - NIGHT"
        )
        assert scene_type == "EXT"
        assert location == "PARK"
        assert time == "NIGHT"

        scene_type, location, time = ScreenplayUtils.parse_scene_heading("EXT STREET")
        assert scene_type == "EXT"
        assert location == "STREET"
        assert time is None

    def test_parse_scene_heading_int_ext(self):
        """Test parsing INT/EXT scene heading."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "INT./EXT. CAR - DAY"
        )
        assert scene_type == "INT/EXT"
        assert location == "CAR"
        assert time == "DAY"

        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "I/E. HOUSE - NIGHT"
        )
        assert scene_type == "INT/EXT"
        assert location == "HOUSE"
        assert time == "NIGHT"

        scene_type, location, time = ScreenplayUtils.parse_scene_heading("I/E GARAGE")
        assert scene_type == "INT/EXT"
        assert location == "GARAGE"
        assert time is None

    def test_parse_scene_heading_no_prefix(self):
        """Test parsing scene heading with no prefix."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "COFFEE SHOP - DAY"
        )
        assert scene_type == ""
        assert location == "COFFEE SHOP"
        assert time == "DAY"

    def test_parse_scene_heading_case_insensitive(self):
        """Test that scene type detection is case insensitive."""
        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "int. coffee shop - day"
        )
        assert scene_type == "INT"
        assert location == "coffee shop"
        assert time == "DAY"

        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "Ext. PARK - Night"
        )
        assert scene_type == "EXT"
        assert location == "PARK"
        assert time == "NIGHT"

        scene_type, location, time = ScreenplayUtils.parse_scene_heading(
            "i/e. car - dawn"
        )
        assert scene_type == "INT/EXT"
        assert location == "car"
        assert time == "DAWN"

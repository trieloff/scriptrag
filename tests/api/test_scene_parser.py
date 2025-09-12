"""Unit tests for scene parser module."""

import pytest

from scriptrag.api.scene_parser import ParsedSceneData, SceneParser


class TestSceneParser:
    """Test scene parser functionality."""

    @pytest.fixture
    def parser(self) -> SceneParser:
        """Create parser instance."""
        return SceneParser()

    def test_parse_basic_scene(self, parser: SceneParser) -> None:
        """Test parsing a basic scene."""
        content = """INT. COFFEE SHOP - DAY

Sarah enters the bustling coffee shop."""

        result = parser.parse_scene_content(content)

        assert result.scene_type == "INT"
        assert result.location == "COFFEE SHOP"
        assert result.time_of_day == "DAY"
        assert result.heading == "INT. COFFEE SHOP - DAY"
        assert result.content == content

    def test_parse_exterior_scene(self, parser: SceneParser) -> None:
        """Test parsing exterior scene."""
        content = """EXT. PARKING LOT - NIGHT

The parking lot is empty."""

        result = parser.parse_scene_content(content)

        assert result.scene_type == "EXT"
        assert result.location == "PARKING LOT"
        assert result.time_of_day == "NIGHT"

    def test_parse_int_ext_scene(self, parser: SceneParser) -> None:
        """Test parsing INT/EXT scene."""
        content = """INT./EXT. CAR - CONTINUOUS

They drive through the city."""

        result = parser.parse_scene_content(content)

        assert result.scene_type == "INT/EXT"
        assert result.location == "CAR"
        assert result.time_of_day == "CONTINUOUS"

    def test_parse_scene_no_time(self, parser: SceneParser) -> None:
        """Test parsing scene without time of day."""
        content = """INT. OFFICE

The office is quiet."""

        result = parser.parse_scene_content(content)

        assert result.scene_type == "INT"
        assert result.location == "OFFICE"
        assert result.time_of_day is None

    def test_extract_scene_metadata(self, parser: SceneParser) -> None:
        """Test extracting scene metadata."""
        scene_data = {
            "dialogue": [
                {"character": "JOHN", "text": "Hello"},
                {"character": "JANE", "text": "Hi there"},
                {"character": "JOHN", "text": "How are you?"},
            ],
            "action": ["John enters.", "", "Jane waves."],
        }

        metadata = parser.extract_scene_metadata(scene_data)

        assert metadata["has_dialogue"] is True
        assert metadata["has_action"] is True
        assert metadata["character_count"] == 2
        assert metadata["dialogue_count"] == 3
        assert metadata["action_line_count"] == 2

    def test_prepare_scene_for_storage(self, parser: SceneParser) -> None:
        """Test preparing scene for database storage."""
        parsed_data = ParsedSceneData(
            scene_type="INT",
            location="OFFICE",
            time_of_day="DAY",
            heading="INT. OFFICE - DAY",
            content="INT. OFFICE - DAY\n\nWork continues.",
            parsed_scene=None,
        )

        storage_data = parser.prepare_scene_for_storage(parsed_data, 42)

        assert storage_data["scene_number"] == 42
        assert storage_data["heading"] == "INT. OFFICE - DAY"
        assert storage_data["location"] == "OFFICE"
        assert storage_data["time_of_day"] == "DAY"
        assert "content_hash" in storage_data

    def test_split_scene_content(self, parser: SceneParser) -> None:
        """Test splitting scene into components."""
        content = """INT. OFFICE - DAY

John enters the room.

JOHN
Hello everyone.

(smiling)

The meeting begins."""

        heading, action, dialogue = parser.split_scene_content(content)

        assert heading == "INT. OFFICE - DAY"
        assert action is not None
        assert dialogue is not None
        assert "John enters" in action
        assert "JOHN" in dialogue

    def test_is_valid_scene_heading(self, parser: SceneParser) -> None:
        """Test scene heading validation."""
        assert parser.is_valid_scene_heading("INT. OFFICE - DAY") is True
        assert parser.is_valid_scene_heading("EXT. STREET - NIGHT") is True
        assert parser.is_valid_scene_heading("I/E. CAR - CONTINUOUS") is True
        assert parser.is_valid_scene_heading("INT/EXT. BORDER") is True
        assert parser.is_valid_scene_heading("FADE IN:") is False
        assert parser.is_valid_scene_heading("JOHN enters") is False
        assert parser.is_valid_scene_heading("") is False

    def test_normalize_scene_heading(self, parser: SceneParser) -> None:
        """Test scene heading normalization."""
        assert (
            parser.normalize_scene_heading("int. office - day") == "INT. office - day"
        )
        assert (
            parser.normalize_scene_heading("EXT.   STREET   -   NIGHT")
            == "EXT. STREET - NIGHT"
        )
        assert parser.normalize_scene_heading("int/ext. border") == "INT/EXT. border"
        assert parser.normalize_scene_heading("") == ""

        # Test mixed case variations that could expose the slicing bug
        assert parser.normalize_scene_heading("Int. OFFICE") == "INT. OFFICE"
        assert parser.normalize_scene_heading("INT. OFFICE") == "INT. OFFICE"
        assert parser.normalize_scene_heading("InT. OFFICE") == "INT. OFFICE"
        assert parser.normalize_scene_heading("Ext. STREET") == "EXT. STREET"
        assert parser.normalize_scene_heading("EXT. STREET") == "EXT. STREET"
        assert parser.normalize_scene_heading("ExT. STREET") == "EXT. STREET"
        assert parser.normalize_scene_heading("I/E. BORDER") == "I/E. BORDER"
        assert parser.normalize_scene_heading("i/E. BORDER") == "I/E. BORDER"
        assert (
            parser.normalize_scene_heading("Int/Ext. COMPOUND") == "INT/EXT. COMPOUND"
        )
        assert (
            parser.normalize_scene_heading("INT/EXT. COMPOUND") == "INT/EXT. COMPOUND"
        )
        assert (
            parser.normalize_scene_heading("INT/ext. COMPOUND") == "INT/EXT. COMPOUND"
        )

        # Test with unusual spacing
        assert parser.normalize_scene_heading("int.OFFICE") == "INT.OFFICE"
        assert parser.normalize_scene_heading("int .  OFFICE") == "INT. OFFICE"

        # Test edge cases with prefix-like content
        assert (
            parser.normalize_scene_heading("int.ernational airport")
            == "INT.ernational airport"
        )
        assert (
            parser.normalize_scene_heading("ext.reme sports center")
            == "EXT.reme sports center"
        )

    def test_parse_scene_with_complex_location(self, parser: SceneParser) -> None:
        """Test parsing scene with complex location."""
        content = """INT. SARAH'S APARTMENT - LIVING ROOM - NIGHT

The room is dimly lit."""

        result = parser.parse_scene_content(content)

        assert result.scene_type == "INT"
        assert result.location == "SARAH'S APARTMENT - LIVING ROOM"
        assert result.time_of_day == "NIGHT"

    def test_parse_scene_empty_content(self, parser: SceneParser) -> None:
        """Test parsing empty content."""
        content = ""

        result = parser.parse_scene_content(content)

        assert result.scene_type == ""
        assert result.location is None
        assert result.time_of_day is None
        assert result.heading == ""

    def test_extract_metadata_empty_scene(self, parser: SceneParser) -> None:
        """Test extracting metadata from empty scene."""
        scene_data = {}

        metadata = parser.extract_scene_metadata(scene_data)

        assert metadata["has_dialogue"] is False
        assert metadata["has_action"] is False
        assert metadata["character_count"] == 0
        assert metadata["dialogue_count"] == 0
        assert metadata["action_line_count"] == 0

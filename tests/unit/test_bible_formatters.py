"""Tests for bible formatters module."""

from datetime import datetime

from scriptrag.api.bible.character_bible import BibleCharacter
from scriptrag.api.bible.formatters import BibleFormatter
from scriptrag.api.bible.scene_bible import BibleScene


class TestBibleFormatterCharacter:
    """Test character formatting methods."""

    def test_format_character_result_basic(self) -> None:
        """Test formatting basic character results."""
        characters = [
            BibleCharacter(
                canonical="JOHN SMITH",
                aliases=["JOHN", "SMITH"],
                tags=["protagonist"],
                notes="Main character",
            ),
            BibleCharacter(
                canonical="JANE DOE",
                aliases=["JANE"],
                tags=None,
                notes=None,
            ),
        ]

        result = BibleFormatter.format_character_result(characters)

        assert result["version"] == 1
        assert "extracted_at" in result
        assert len(result["characters"]) == 2

        char1 = result["characters"][0]
        assert char1["canonical"] == "JOHN SMITH"
        assert char1["aliases"] == ["JOHN", "SMITH"]
        assert char1["tags"] == ["protagonist"]
        assert char1["notes"] == "Main character"

        char2 = result["characters"][1]
        assert char2["canonical"] == "JANE DOE"
        assert char2["aliases"] == ["JANE"]
        assert char2["tags"] is None
        assert char2["notes"] is None

    def test_format_character_result_with_timestamp(self) -> None:
        """Test formatting with custom timestamp."""
        characters = [BibleCharacter(canonical="JOHN", aliases=[])]
        timestamp = datetime(2024, 1, 15, 10, 30, 0)

        result = BibleFormatter.format_character_result(characters, timestamp)

        assert result["extracted_at"] == "2024-01-15T10:30:00"

    def test_format_character_result_empty_list(self) -> None:
        """Test formatting empty character list."""
        result = BibleFormatter.format_character_result([])

        assert result["version"] == 1
        assert "extracted_at" in result
        assert result["characters"] == []

    def test_format_character_internal(self) -> None:
        """Test internal character formatting method."""
        character = BibleCharacter(
            canonical="TEST",
            aliases=["T"],
            tags=["test"],
            notes="Test note",
        )

        formatted = BibleFormatter._format_character(character)

        assert formatted["canonical"] == "TEST"
        assert formatted["aliases"] == ["T"]
        assert formatted["tags"] == ["test"]
        assert formatted["notes"] == "Test note"


class TestBibleFormatterScene:
    """Test scene formatting methods."""

    def test_format_scene_result_with_bible_scenes(self) -> None:
        """Test formatting BibleScene objects."""
        scenes = [
            BibleScene(
                location="OFFICE",
                type="INT",
                time="DAY",
                description="Modern office",
            ),
            BibleScene(
                location="STREET",
                type="EXT",
                time=None,
                description=None,
            ),
        ]

        result = BibleFormatter.format_scene_result(scenes)

        assert result["version"] == 1
        assert "extracted_at" in result
        assert len(result["scenes"]) == 2

        scene1 = result["scenes"][0]
        assert scene1["location"] == "OFFICE"
        assert scene1["type"] == "INT"
        assert scene1["time"] == "DAY"
        assert scene1["description"] == "Modern office"

        scene2 = result["scenes"][1]
        assert scene2["location"] == "STREET"
        assert scene2["type"] == "EXT"
        assert scene2["time"] is None
        assert scene2["description"] is None

    def test_format_scene_result_with_dicts(self) -> None:
        """Test formatting scene dictionaries."""
        scenes = [
            {"location": "OFFICE", "type": "INT"},
            {"location": "STREET", "type": "EXT", "time": "NIGHT"},
        ]

        result = BibleFormatter.format_scene_result(scenes)

        assert result["version"] == 1
        assert "extracted_at" in result
        assert result["scenes"] == scenes

    def test_format_scene_result_mixed_types(self) -> None:
        """Test formatting mixed BibleScene and dict types."""
        scenes = [
            BibleScene(location="OFFICE", type="INT"),
            {"location": "STREET", "type": "EXT"},
        ]

        result = BibleFormatter.format_scene_result(scenes)

        assert result["version"] == 1
        assert len(result["scenes"]) == 2
        assert result["scenes"][0]["location"] == "OFFICE"
        assert result["scenes"][1] == {"location": "STREET", "type": "EXT"}

    def test_format_scene_result_with_timestamp(self) -> None:
        """Test formatting with custom timestamp."""
        scenes = [BibleScene(location="OFFICE")]
        timestamp = datetime(2024, 2, 20, 15, 45, 30)

        result = BibleFormatter.format_scene_result(scenes, timestamp)

        assert result["extracted_at"] == "2024-02-20T15:45:30"

    def test_format_scene_result_empty_list(self) -> None:
        """Test formatting empty scene list."""
        result = BibleFormatter.format_scene_result([])

        assert result["version"] == 1
        assert "extracted_at" in result
        assert result["scenes"] == []

    def test_format_scene_internal(self) -> None:
        """Test internal scene formatting method."""
        scene = BibleScene(
            location="TEST",
            type="INT",
            time="DAY",
            description="Test desc",
        )

        formatted = BibleFormatter._format_scene(scene)

        assert formatted["location"] == "TEST"
        assert formatted["type"] == "INT"
        assert formatted["time"] == "DAY"
        assert formatted["description"] == "Test desc"


class TestBibleFormatterEmpty:
    """Test empty result formatting."""

    def test_create_empty_result_characters(self) -> None:
        """Test creating empty character result."""
        result = BibleFormatter.create_empty_result("characters")

        assert result["version"] == 1
        assert "extracted_at" in result
        assert result["characters"] == []

    def test_create_empty_result_scenes(self) -> None:
        """Test creating empty scene result."""
        result = BibleFormatter.create_empty_result("scenes")

        assert result["version"] == 1
        assert "extracted_at" in result
        assert result["scenes"] == []

    def test_create_empty_result_default(self) -> None:
        """Test creating empty result with default type."""
        result = BibleFormatter.create_empty_result()

        assert result["version"] == 1
        assert "extracted_at" in result
        assert result["characters"] == []

    def test_create_empty_result_with_timestamp(self) -> None:
        """Test creating empty result with custom timestamp."""
        timestamp = datetime(2024, 3, 10, 8, 15, 0)
        result = BibleFormatter.create_empty_result("characters", timestamp)

        assert result["extracted_at"] == "2024-03-10T08:15:00"


class TestBibleFormatterMerge:
    """Test result merging."""

    def test_merge_results_both(self) -> None:
        """Test merging both character and scene results."""
        char_result = {
            "version": 1,
            "extracted_at": "2024-01-01T00:00:00",
            "characters": [{"canonical": "JOHN", "aliases": []}],
        }
        scene_result = {
            "version": 1,
            "extracted_at": "2024-01-01T00:00:00",
            "scenes": [{"location": "OFFICE"}],
        }

        result = BibleFormatter.merge_results(char_result, scene_result)

        assert result["version"] == 1
        assert "extracted_at" in result
        assert result["characters"] == [{"canonical": "JOHN", "aliases": []}]
        assert result["scenes"] == [{"location": "OFFICE"}]

    def test_merge_results_characters_only(self) -> None:
        """Test merging with only character result."""
        char_result = {
            "version": 1,
            "extracted_at": "2024-01-01T00:00:00",
            "characters": [{"canonical": "JOHN", "aliases": []}],
        }

        result = BibleFormatter.merge_results(character_result=char_result)

        assert result["version"] == 1
        assert "extracted_at" in result
        assert result["characters"] == [{"canonical": "JOHN", "aliases": []}]
        assert "scenes" not in result

    def test_merge_results_scenes_only(self) -> None:
        """Test merging with only scene result."""
        scene_result = {
            "version": 1,
            "extracted_at": "2024-01-01T00:00:00",
            "scenes": [{"location": "OFFICE"}],
        }

        result = BibleFormatter.merge_results(scene_result=scene_result)

        assert result["version"] == 1
        assert "extracted_at" in result
        assert result["scenes"] == [{"location": "OFFICE"}]
        assert "characters" not in result

    def test_merge_results_neither(self) -> None:
        """Test merging with neither result."""
        result = BibleFormatter.merge_results()

        assert result["version"] == 1
        assert "extracted_at" in result
        assert "characters" not in result
        assert "scenes" not in result

    def test_merge_results_empty_data(self) -> None:
        """Test merging with empty data lists."""
        char_result = {"characters": []}
        scene_result = {"scenes": []}

        result = BibleFormatter.merge_results(char_result, scene_result)

        assert result["characters"] == []
        assert result["scenes"] == []

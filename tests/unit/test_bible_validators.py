"""Tests for bible validation module."""

from unittest.mock import patch

from scriptrag.api.bible.character_bible import BibleCharacter
from scriptrag.api.bible.scene_bible import BibleScene
from scriptrag.api.bible.validators import BibleValidator


class TestBibleValidatorCharacter:
    """Test character validation methods."""

    def test_validate_character_valid(self) -> None:
        """Test validating a valid character."""
        character = BibleCharacter(
            canonical="JOHN SMITH",
            aliases=["JOHN", "SMITH"],
            tags=["protagonist"],
            notes="Main character",
        )
        assert BibleValidator.validate_character(character) is True

    def test_validate_character_no_canonical(self) -> None:
        """Test character without canonical name is invalid."""
        character = BibleCharacter(canonical="", aliases=["JOHN"])
        assert BibleValidator.validate_character(character) is False

    def test_validate_character_whitespace_canonical(self) -> None:
        """Test character with only whitespace canonical is invalid."""
        character = BibleCharacter(canonical="   ", aliases=[])
        assert BibleValidator.validate_character(character) is False

    def test_validate_character_lowercase_canonical_warning(self) -> None:
        """Test lowercase canonical name triggers warning but is valid."""
        character = BibleCharacter(canonical="john smith", aliases=[])
        with patch("scriptrag.api.bible.validators.logger") as mock_logger:
            result = BibleValidator.validate_character(character)
            assert result is True
            mock_logger.warning.assert_called_once()

    def test_validate_character_invalid_aliases_type(self) -> None:
        """Test character with non-list aliases is invalid."""
        character = BibleCharacter(canonical="JOHN", aliases=[])
        character.aliases = "not a list"  # type: ignore
        assert BibleValidator.validate_character(character) is False

    def test_validate_character_invalid_tags_type(self) -> None:
        """Test character with non-list tags is invalid."""
        character = BibleCharacter(canonical="JOHN", aliases=[])
        character.tags = "not a list"  # type: ignore
        assert BibleValidator.validate_character(character) is False

    def test_validate_character_invalid_notes_type(self) -> None:
        """Test character with non-string notes is invalid."""
        character = BibleCharacter(canonical="JOHN", aliases=[])
        character.notes = 123  # type: ignore
        assert BibleValidator.validate_character(character) is False

    def test_validate_character_none_tags_valid(self) -> None:
        """Test character with None tags is valid."""
        character = BibleCharacter(canonical="JOHN", aliases=[], tags=None)
        assert BibleValidator.validate_character(character) is True

    def test_validate_character_none_notes_valid(self) -> None:
        """Test character with None notes is valid."""
        character = BibleCharacter(canonical="JOHN", aliases=[], notes=None)
        assert BibleValidator.validate_character(character) is True


class TestBibleValidatorScene:
    """Test scene validation methods."""

    def test_validate_bible_scene_valid(self) -> None:
        """Test validating a valid BibleScene."""
        scene = BibleScene(
            location="OFFICE",
            type="INT",
            time="DAY",
            description="Modern office",
        )
        assert BibleValidator.validate_bible_scene(scene) is True

    def test_validate_bible_scene_no_location(self) -> None:
        """Test scene without location is invalid."""
        scene = BibleScene(location="")
        assert BibleValidator.validate_bible_scene(scene) is False

    def test_validate_bible_scene_whitespace_location(self) -> None:
        """Test scene with only whitespace location is invalid."""
        scene = BibleScene(location="   ")
        assert BibleValidator.validate_bible_scene(scene) is False

    def test_validate_bible_scene_invalid_type_warning(self) -> None:
        """Test invalid scene type triggers warning but is valid."""
        scene = BibleScene(location="OFFICE", type="INVALID")
        with patch("scriptrag.api.bible.validators.logger") as mock_logger:
            result = BibleValidator.validate_bible_scene(scene)
            assert result is True
            mock_logger.warning.assert_called_with("Invalid scene type: INVALID")

    def test_validate_bible_scene_valid_types(self) -> None:
        """Test all valid scene types."""
        valid_types = ["INT", "EXT", "INT/EXT", "I/E"]
        for scene_type in valid_types:
            scene = BibleScene(location="OFFICE", type=scene_type)
            assert BibleValidator.validate_bible_scene(scene) is True

    def test_validate_scene_dict_valid(self) -> None:
        """Test validating a valid scene dictionary."""
        scene = {"location": "OFFICE", "type": "INT"}
        assert BibleValidator.validate_scene(scene) is True

    def test_validate_scene_dict_no_location(self) -> None:
        """Test scene dict without location is invalid."""
        scene = {"type": "INT"}
        assert BibleValidator.validate_scene(scene) is False

    def test_validate_scene_dict_empty_location(self) -> None:
        """Test scene dict with empty location is invalid."""
        scene = {"location": "", "type": "INT"}
        assert BibleValidator.validate_scene(scene) is False

    def test_validate_scene_dict_invalid_type_warning(self) -> None:
        """Test invalid type in scene dict triggers warning."""
        scene = {"location": "OFFICE", "type": "INVALID"}
        with patch("scriptrag.api.bible.validators.logger") as mock_logger:
            result = BibleValidator.validate_scene(scene)
            assert result is True
            mock_logger.warning.assert_called_with("Invalid scene type: INVALID")


class TestBibleValidatorNormalization:
    """Test normalization methods."""

    def test_normalize_scene_basic(self) -> None:
        """Test basic scene normalization."""
        scene = {
            "location": "office",
            "type": "int",
            "time": "day",
            "description": "An office",
        }
        result = BibleValidator.normalize_scene(scene)
        assert result["location"] == "OFFICE"
        assert result["type"] == "INT"
        assert result["time"] == "DAY"
        assert result["description"] == "An office"

    def test_normalize_scene_ie_to_int_ext(self) -> None:
        """Test I/E is standardized to INT/EXT."""
        scene = {"location": "OFFICE", "type": "I/E"}
        result = BibleValidator.normalize_scene(scene)
        assert result["type"] == "INT/EXT"

    def test_normalize_scene_missing_fields(self) -> None:
        """Test normalization with missing fields."""
        scene = {"location": "office"}
        result = BibleValidator.normalize_scene(scene)
        assert result == {"location": "OFFICE"}

    def test_normalize_scene_empty_type(self) -> None:
        """Test normalization skips empty type."""
        scene = {"location": "office", "type": ""}
        result = BibleValidator.normalize_scene(scene)
        assert "type" not in result

    def test_normalize_scene_empty_time(self) -> None:
        """Test normalization skips empty time."""
        scene = {"location": "office", "time": ""}
        result = BibleValidator.normalize_scene(scene)
        assert "time" not in result


class TestBibleValidatorExtractionResult:
    """Test extraction result validation."""

    def test_validate_extraction_result_valid_characters(self) -> None:
        """Test valid extraction result with characters."""
        result = {
            "version": 1,
            "extracted_at": "2024-01-01T00:00:00",
            "characters": [{"canonical": "JOHN", "aliases": []}],
        }
        assert BibleValidator.validate_extraction_result(result) is True

    def test_validate_extraction_result_valid_scenes(self) -> None:
        """Test valid extraction result with scenes."""
        result = {
            "version": 1,
            "extracted_at": "2024-01-01T00:00:00",
            "scenes": [{"location": "OFFICE"}],
        }
        assert BibleValidator.validate_extraction_result(result) is True

    def test_validate_extraction_result_both(self) -> None:
        """Test valid extraction result with both characters and scenes."""
        result = {
            "version": 1,
            "extracted_at": "2024-01-01T00:00:00",
            "characters": [],
            "scenes": [],
        }
        assert BibleValidator.validate_extraction_result(result) is True

    def test_validate_extraction_result_no_version(self) -> None:
        """Test extraction result without version is invalid."""
        result = {"extracted_at": "2024-01-01T00:00:00", "characters": []}
        assert BibleValidator.validate_extraction_result(result) is False

    def test_validate_extraction_result_no_timestamp(self) -> None:
        """Test extraction result without timestamp is invalid."""
        result = {"version": 1, "characters": []}
        assert BibleValidator.validate_extraction_result(result) is False

    def test_validate_extraction_result_no_data(self) -> None:
        """Test extraction result without characters or scenes is invalid."""
        result = {"version": 1, "extracted_at": "2024-01-01T00:00:00"}
        assert BibleValidator.validate_extraction_result(result) is False

    def test_validate_extraction_result_characters_not_list(self) -> None:
        """Test extraction result with non-list characters is invalid."""
        result = {
            "version": 1,
            "extracted_at": "2024-01-01T00:00:00",
            "characters": "not a list",
        }
        assert BibleValidator.validate_extraction_result(result) is False

    def test_validate_extraction_result_scenes_not_list(self) -> None:
        """Test extraction result with non-list scenes is invalid."""
        result = {
            "version": 1,
            "extracted_at": "2024-01-01T00:00:00",
            "scenes": "not a list",
        }
        assert BibleValidator.validate_extraction_result(result) is False

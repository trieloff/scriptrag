"""Unit tests for enhanced scene validator."""

import pytest

from scriptrag.validators.scene_validator import SceneValidator


class TestSceneValidator:
    """Test enhanced scene validator functionality."""

    @pytest.fixture
    def validator(self) -> SceneValidator:
        """Create validator instance."""
        return SceneValidator()

    def test_validate_valid_scene(self, validator: SceneValidator) -> None:
        """Test validating a properly formatted scene."""
        content = """INT. OFFICE - DAY

John enters the office carrying a briefcase.

JOHN
Good morning, everyone.

The team looks up from their work."""

        result = validator.validate_scene(content)

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_validate_empty_content(self, validator: SceneValidator) -> None:
        """Test validating empty content."""
        result = validator.validate_scene("")

        assert result.is_valid is False
        assert "Scene content cannot be empty" in result.errors

    def test_validate_missing_heading(self, validator: SceneValidator) -> None:
        """Test scene without proper heading."""
        content = """John enters the room.

JOHN
Hello."""

        result = validator.validate_scene(content)

        assert result.is_valid is False
        assert any("Invalid scene heading" in error for error in result.errors)

    def test_validate_heading_only(self, validator: SceneValidator) -> None:
        """Test scene with only heading."""
        content = """INT. OFFICE - DAY"""

        result = validator.validate_scene(content)

        assert result.is_valid is True
        assert "Scene has no content after heading" in result.warnings

    def test_validate_strict_mode(self, validator: SceneValidator) -> None:
        """Test strict validation mode."""
        content = """INT. OFFICE

Some action here."""

        result = validator.validate_scene(content, strict=True)

        # In strict mode, missing time of day causes an error, not just a warning
        assert result.is_valid is False
        assert any("time of day" in error for error in result.errors)

    def test_validate_unusual_time(self, validator: SceneValidator) -> None:
        """Test unusual time indicator."""
        content = """INT. OFFICE - TEATIME

Action here."""

        result = validator.validate_scene(content, strict=True)

        assert result.is_valid is True
        # In strict mode, missing time is an issue, but TEATIME is recognized as time
        # so we get a warning about the missing time indicator from standard list
        assert any("time" in warning.lower() for warning in result.warnings)

    def test_validate_long_heading(self, validator: SceneValidator) -> None:
        """Test excessively long heading."""
        long_location = "A" * 100
        content = f"""INT. {long_location} - DAY

Action."""

        result = validator.validate_scene(content, strict=True)

        assert result.is_valid is False
        assert any("too long" in error for error in result.errors)

    def test_validate_tabs_in_content(self, validator: SceneValidator) -> None:
        """Test content with tabs."""
        content = """INT. OFFICE - DAY

\tJohn enters the room.

JOHN
\tHello."""

        result = validator.validate_scene(content, strict=True)

        assert result.is_valid is True
        assert any("contains tabs" in warning for warning in result.warnings)

    def test_validate_excessive_blank_lines(self, validator: SceneValidator) -> None:
        """Test excessive blank lines."""
        content = """INT. OFFICE - DAY




Action here."""

        result = validator.validate_scene(content, strict=True)

        assert result.is_valid is True
        assert any("Excessive blank lines" in warning for warning in result.warnings)

    def test_validate_batch(self, validator: SceneValidator) -> None:
        """Test batch validation."""
        scenes = [
            "INT. OFFICE - DAY\n\nAction.",
            "EXT. STREET - NIGHT\n\nMore action.",
            "",  # Invalid
        ]

        results = validator.validate_batch(scenes)

        assert len(results) == 3
        assert results[0].is_valid is True
        assert results[1].is_valid is True
        assert results[2].is_valid is False

    def test_check_scene_conflicts_no_changes(self, validator: SceneValidator) -> None:
        """Test conflict checking with no changes."""
        content = """INT. OFFICE - DAY

Same content."""

        result = validator.check_scene_conflicts(content, content)

        assert result.is_valid is True
        assert result.metadata["has_changes"] is False
        assert "No changes detected" in result.warnings

    def test_check_scene_conflicts_with_changes(
        self, validator: SceneValidator
    ) -> None:
        """Test conflict checking with changes."""
        old_content = """INT. OFFICE - DAY

Old action."""

        new_content = """INT. OFFICE - NIGHT

New action here."""

        result = validator.check_scene_conflicts(new_content, old_content)

        assert result.is_valid is True
        assert result.metadata["has_changes"] is True
        assert result.metadata["heading_changed"] is True
        assert result.metadata["lines_added"] == 1

    def test_generate_suggestions_missing_time(self, validator: SceneValidator) -> None:
        """Test suggestion generation for missing time."""
        content = """INT. OFFICE

Action here."""

        result = validator.validate_scene(content)

        assert any("Consider adding time" in s for s in result.suggestions)

    def test_generate_suggestions_normalization(
        self, validator: SceneValidator
    ) -> None:
        """Test suggestion for heading normalization."""
        content = """int.   office   -   day

Action here."""

        result = validator.validate_scene(content)

        assert result.is_valid is False
        assert any("Consider reformatting" in s for s in result.suggestions)

    def test_all_valid_scene_types(self, validator: SceneValidator) -> None:
        """Test all valid scene type prefixes."""
        valid_types = [
            "INT. LOCATION - DAY",
            "EXT. LOCATION - NIGHT",
            "I/E. LOCATION - CONTINUOUS",
            "INT/EXT. LOCATION - MORNING",
            "INT LOCATION - DAY",
            "EXT LOCATION - NIGHT",
        ]

        for heading in valid_types:
            content = f"{heading}\n\nAction."
            result = validator.validate_scene(content)
            assert result.is_valid is True, f"Failed for: {heading}"

    def test_all_time_indicators(self, validator: SceneValidator) -> None:
        """Test all recognized time indicators."""
        for time in validator.TIME_INDICATORS:
            content = f"INT. OFFICE - {time}\n\nAction."
            result = validator.validate_scene(content)
            assert result.is_valid is True
            assert len(result.warnings) == 0

    def test_complex_location_validation(self, validator: SceneValidator) -> None:
        """Test complex location parsing."""
        content = """INT. SARAH'S APARTMENT - LIVING ROOM - NIGHT

Sarah sits on the couch."""

        result = validator.validate_scene(content)

        assert result.is_valid is True
        assert result.parsed_scene is not None

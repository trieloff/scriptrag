"""Enhanced scene validation with comprehensive Fountain format checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from scriptrag.api.scene_parser import SceneParser
from scriptrag.config import get_logger
from scriptrag.parser import Scene

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of scene validation with detailed feedback."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    parsed_scene: Scene | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SceneValidator:
    """Comprehensive scene validation for Fountain format."""

    # Scene heading patterns
    VALID_SCENE_TYPES: ClassVar[list[str]] = [
        "INT.",
        "EXT.",
        "I/E.",
        "INT/EXT.",
        "INT ",
        "EXT ",
    ]
    TIME_INDICATORS: ClassVar[list[str]] = [
        "DAY",
        "NIGHT",
        "MORNING",
        "AFTERNOON",
        "EVENING",
        "DAWN",
        "DUSK",
        "CONTINUOUS",
        "LATER",
        "MOMENTS LATER",
        "SUNSET",
        "SUNRISE",
        "NOON",
        "MIDNIGHT",
    ]

    def __init__(self) -> None:
        """Initialize the validator."""
        self.parser = SceneParser()

    def validate_scene(self, content: str, strict: bool = False) -> ValidationResult:
        """Validate scene content with comprehensive checks.

        Args:
            content: Scene content to validate
            strict: If True, apply stricter validation rules

        Returns:
            Detailed validation result
        """
        errors = []
        warnings = []
        suggestions = []
        metadata = {}

        # Check for empty content
        if not content or not content.strip():
            errors.append("Scene content cannot be empty")
            return ValidationResult(
                is_valid=False,
                errors=errors,
                parsed_scene=None,
            )

        # Parse the scene
        parsed_data = self.parser.parse_scene_content(content)
        metadata["parsed_data"] = parsed_data

        # Validate scene heading
        heading_errors = self._validate_heading(parsed_data.heading, strict=strict)
        errors.extend(heading_errors)

        # Check heading format
        if not self.parser.is_valid_scene_heading(parsed_data.heading):
            errors.append(
                "Invalid scene heading format. Must start with INT., EXT., "
                "I/E., or INT/EXT."
            )

        # Validate location
        location_warnings = self._validate_location(parsed_data.location, strict=strict)
        warnings.extend(location_warnings)

        # Validate time of day
        time_warnings = self._validate_time_of_day(
            parsed_data.time_of_day, strict=strict
        )
        warnings.extend(time_warnings)

        # Check content structure
        structure_warnings = self._validate_content_structure(content, strict=strict)
        warnings.extend(structure_warnings)

        # Generate suggestions
        suggestions = self._generate_suggestions(parsed_data, errors, warnings)

        # Determine overall validity
        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            parsed_scene=parsed_data.parsed_scene,
            metadata=metadata,
        )

    def validate_batch(
        self, scenes: list[str], strict: bool = False
    ) -> list[ValidationResult]:
        """Validate multiple scenes.

        Args:
            scenes: List of scene contents
            strict: If True, apply stricter validation

        Returns:
            List of validation results
        """
        return [self.validate_scene(scene, strict) for scene in scenes]

    def _validate_heading(self, heading: str, strict: bool = False) -> list[str]:
        """Validate scene heading format.

        Args:
            heading: Scene heading to validate
            strict: Apply strict validation

        Returns:
            List of errors found
        """
        errors = []

        if not heading:
            errors.append("Scene must have a heading")
            return errors

        heading_upper = heading.upper()

        # Check for valid scene type
        has_valid_type = any(
            heading_upper.startswith(prefix) for prefix in self.VALID_SCENE_TYPES
        )
        if not has_valid_type:
            errors.append("Scene heading must start with INT., EXT., I/E., or INT/EXT.")

        # In strict mode, check for proper formatting
        if strict:
            # Check for location after scene type
            if " - " not in heading and not self._has_time_indicator(heading):
                errors.append(
                    "Scene heading should include time of day (e.g., '- DAY')"
                )

            # Check for excessive length
            if len(heading) > 100:
                errors.append("Scene heading is too long (maximum 100 characters)")

        return errors

    def _validate_location(
        self, location: str | None, strict: bool = False
    ) -> list[str]:
        """Validate scene location.

        Args:
            location: Extracted location
            strict: Apply strict validation

        Returns:
            List of warnings
        """
        warnings = []

        if strict and not location:
            warnings.append("Scene heading missing location description")
        elif location and len(location) > 60:
            warnings.append("Location description is very long (over 60 characters)")

        return warnings

    def _validate_time_of_day(
        self, time_of_day: str | None, strict: bool = False
    ) -> list[str]:
        """Validate time of day indicator.

        Args:
            time_of_day: Extracted time of day
            strict: Apply strict validation

        Returns:
            List of warnings
        """
        warnings = []

        if strict and not time_of_day:
            warnings.append("Scene heading missing time of day indicator")
        elif time_of_day and time_of_day.upper() not in self.TIME_INDICATORS:
            warnings.append(
                f"Unusual time indicator '{time_of_day}'. "
                f"Common options: DAY, NIGHT, MORNING, etc."
            )

        return warnings

    def _validate_content_structure(
        self, content: str, strict: bool = False
    ) -> list[str]:
        """Validate overall content structure.

        Args:
            content: Full scene content
            strict: Apply strict validation

        Returns:
            List of warnings
        """
        warnings = []
        lines = content.strip().split("\n")

        # Check for minimal content
        non_empty_lines = [line for line in lines if line.strip()]
        if len(non_empty_lines) <= 1:
            warnings.append("Scene has no content after heading")

        # Check for common formatting issues
        if strict:
            # Check for tabs (Fountain prefers spaces)
            if "\t" in content:
                warnings.append("Scene contains tabs. Fountain format prefers spaces")

            # Check for excessive blank lines
            consecutive_blanks = 0
            max_consecutive = 0
            for line in lines:
                if not line.strip():
                    consecutive_blanks += 1
                    max_consecutive = max(max_consecutive, consecutive_blanks)
                else:
                    consecutive_blanks = 0

            if max_consecutive > 2:
                warnings.append(
                    "Excessive blank lines detected (more than 2 consecutive)"
                )

        return warnings

    def _has_time_indicator(self, heading: str) -> bool:
        """Check if heading contains a time indicator.

        Args:
            heading: Scene heading

        Returns:
            True if time indicator found
        """
        heading_upper = heading.upper()
        return any(indicator in heading_upper for indicator in self.TIME_INDICATORS)

    def _generate_suggestions(
        self,
        parsed_data: Any,
        errors: list[str],  # noqa: ARG002
        warnings: list[str],
    ) -> list[str]:
        """Generate helpful suggestions based on validation results.

        Args:
            parsed_data: Parsed scene data
            errors: List of errors found
            warnings: List of warnings found

        Returns:
            List of suggestions
        """
        suggestions = []

        # Suggest heading improvements
        if not parsed_data.location and not parsed_data.time_of_day:
            suggestions.append(
                "Consider adding location and time: e.g., 'INT. OFFICE - DAY'"
            )
        elif not parsed_data.time_of_day:
            suggestions.append(
                "Consider adding time of day: e.g., '- DAY' or '- NIGHT'"
            )

        # Suggest content additions
        if "no content after heading" in str(warnings):
            suggestions.append("Add action lines or dialogue after the scene heading")

        # Suggest formatting fixes
        if parsed_data.heading and not self.parser.is_valid_scene_heading(
            parsed_data.heading
        ):
            normalized = self.parser.normalize_scene_heading(parsed_data.heading)
            if normalized != parsed_data.heading:
                suggestions.append(f"Consider reformatting heading to: '{normalized}'")

        return suggestions

    def check_scene_conflicts(
        self,
        new_content: str,
        existing_content: str,
        last_modified: Any | None = None,  # noqa: ARG002
    ) -> ValidationResult:
        """Check for conflicts between new and existing scene content.

        Args:
            new_content: New scene content
            existing_content: Existing scene content
            last_modified: Last modification timestamp

        Returns:
            Validation result with conflict information
        """
        errors: list[str] = []
        warnings: list[str] = []
        metadata: dict[str, Any] = {}

        # Check if content has changed
        if new_content.strip() == existing_content.strip():
            warnings.append("No changes detected in scene content")
            metadata["has_changes"] = False
        else:
            metadata["has_changes"] = True

            # Analyze what changed
            new_lines = new_content.strip().split("\n")
            existing_lines = existing_content.strip().split("\n")

            if new_lines[0] != existing_lines[0]:
                metadata["heading_changed"] = True
                warnings.append("Scene heading has been modified")

            # Count line changes
            lines_added = len(new_lines) - len(existing_lines)
            metadata["lines_added"] = lines_added

        return ValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
            metadata=metadata,
        )

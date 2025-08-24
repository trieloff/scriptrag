"""Fountain format validation for scenes - compatibility wrapper."""

from scriptrag.api.scene_models import ValidationResult
from scriptrag.config import get_logger
from scriptrag.validators.scene_validator import SceneValidator

logger = get_logger(__name__)


class FountainValidator:
    """Validates Fountain format content - compatibility wrapper for SceneValidator."""

    def __init__(self) -> None:
        """Initialize the validator."""
        self.validator = SceneValidator()

    def validate_scene_content(self, content: str) -> ValidationResult:
        """Validate single scene Fountain content.

        This is a compatibility wrapper that uses the enhanced SceneValidator
        from the validators package.
        """
        try:
            # Use the enhanced validator
            result = self.validator.validate_scene(content, strict=False)

            # Convert to the expected ValidationResult format
            return ValidationResult(
                is_valid=result.is_valid,
                errors=result.errors,
                warnings=result.warnings,
                parsed_scene=result.parsed_scene,
            )
        except Exception as e:
            # If validation fails, return a basic validation result
            logger.error(f"Validation error: {e}")
            # Still try basic validation
            has_heading = self._has_scene_heading(content)
            if has_heading:
                # Has a valid heading, so it's technically valid
                return ValidationResult(
                    is_valid=True,
                    errors=[],
                    warnings=[f"Advanced validation failed: {e!s}"],
                    parsed_scene=None,
                )
            return ValidationResult(
                is_valid=False,
                errors=["Missing scene heading", f"Validation error: {e!s}"],
                warnings=[],
                parsed_scene=None,
            )

    def _has_scene_heading(self, content: str) -> bool:
        """Check if content has a valid scene heading."""
        first_line = content.strip().split("\n")[0] if content.strip() else ""
        return any(
            first_line.upper().startswith(prefix)
            for prefix in ["INT.", "EXT.", "I/E.", "INT/EXT."]
        )

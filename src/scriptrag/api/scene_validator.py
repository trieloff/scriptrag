"""Fountain format validation for scenes."""

from scriptrag.api.scene_models import ValidationResult
from scriptrag.config import get_logger
from scriptrag.parser import FountainParser

logger = get_logger(__name__)


class FountainValidator:
    """Validates Fountain format content."""

    def __init__(self) -> None:
        """Initialize the validator."""
        self.parser = FountainParser()

    def validate_scene_content(self, content: str) -> ValidationResult:
        """Validate single scene Fountain content."""
        try:
            errors = []
            warnings = []

            # Check for scene heading
            if not self._has_scene_heading(content):
                errors.append(
                    "Missing scene heading. Scene must start with INT. or EXT. "
                    "followed by location (e.g., 'INT. COFFEE SHOP - DAY')"
                )

            # Check for content after heading
            lines = content.strip().split("\n")
            non_empty_lines = [line for line in lines if line.strip()]
            if len(non_empty_lines) <= 1:
                warnings.append("Scene appears to have no content after heading")

            # Try to parse the content as a complete script
            # Wrap in minimal fountain structure if needed
            if not content.strip().startswith(("INT.", "EXT.", "I/E.", "INT/EXT.")):
                errors.append(
                    "Scene must start with a scene heading "
                    "(INT., EXT., I/E., or INT/EXT.)"
                )

            # Parse content to ensure valid Fountain
            try:
                # Create a temporary script with just this scene
                parsed = self.parser.parse(content)
                parsed_scene = parsed.scenes[0] if parsed.scenes else None
            except Exception as e:
                errors.append(f"Fountain parsing failed: {e!s}")
                parsed_scene = None

            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                parsed_scene=parsed_scene,
            )

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[f"Validation failed: {e!s}"],
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

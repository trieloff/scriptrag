"""Scene-related validators for CLI input."""

from scriptrag.api.scene_models import SceneIdentifier
from scriptrag.cli.validators.base import ValidationError, Validator


class SceneValidator(Validator[SceneIdentifier]):
    """Validator for scene identifiers."""

    def validate(self, value: dict) -> SceneIdentifier:
        """Validate scene identifier components.

        Args:
            value: Dictionary with scene identifier fields

        Returns:
            Valid SceneIdentifier

        Raises:
            ValidationError: If validation fails
        """
        project = self.validate_required(value.get("project"), "project")
        scene_number = value.get("scene_number")
        season = value.get("season")
        episode = value.get("episode")

        # Validate scene number is positive if provided
        if scene_number is not None:
            self.validate_type(scene_number, int, "scene_number")
            self.validate_range(scene_number, min_val=1, field_name="scene_number")

        # Validate season/episode for TV shows
        if season is not None:
            self.validate_type(season, int, "season")
            self.validate_range(season, min_val=1, field_name="season")

        if episode is not None:
            self.validate_type(episode, int, "episode")
            self.validate_range(episode, min_val=1, field_name="episode")
            # Episode requires season
            if season is None:
                raise ValidationError("Episode number requires season number")

        return SceneIdentifier(
            project=project,
            scene_number=scene_number or 1,  # Default to scene 1 if None
            season=season,
            episode=episode,
        )


class SceneContentValidator(Validator[str]):
    """Validator for scene content."""

    def __init__(self, require_heading: bool = True) -> None:
        """Initialize scene content validator.

        Args:
            require_heading: Whether content must start with scene heading
        """
        self.require_heading = require_heading

    def validate(self, value: str) -> str:
        """Validate scene content.

        Args:
            value: Scene content to validate

        Returns:
            Validated content

        Raises:
            ValidationError: If validation fails
        """
        content = self.validate_required(value, "scene content")

        if self.require_heading:
            # Check if content starts with a valid scene heading
            lines = content.strip().split("\n")
            if not lines:
                raise ValidationError("Scene content is empty")

            first_line = lines[0].strip()
            # Basic Fountain scene heading check
            if not (
                first_line.startswith("INT.")
                or first_line.startswith("EXT.")
                or first_line.startswith("INT/EXT.")
                or first_line.startswith("INT./EXT.")
                or first_line.startswith("I/E.")
            ):
                raise ValidationError(
                    "Scene content must start with a valid scene heading "
                    "(INT., EXT., INT/EXT., etc.)"
                )

        return content  # type: ignore[no-any-return]


class ScenePositionValidator(Validator[tuple[int, str]]):
    """Validator for scene position (before/after)."""

    def validate(self, value: dict) -> tuple[int, str]:
        """Validate scene position.

        Args:
            value: Dictionary with position fields

        Returns:
            Tuple of (reference_scene, position_type)

        Raises:
            ValidationError: If validation fails
        """
        after_scene = value.get("after_scene")
        before_scene = value.get("before_scene")

        # Exactly one must be specified
        if after_scene is None and before_scene is None:
            raise ValidationError("Must specify either --after-scene or --before-scene")

        if after_scene is not None and before_scene is not None:
            raise ValidationError(
                "Cannot specify both --after-scene and --before-scene"
            )

        if after_scene is not None:
            validated_after_scene = self.validate_type(after_scene, int, "after_scene")
            validated_after_scene = self.validate_range(
                validated_after_scene, min_val=1, field_name="after_scene"
            )
            return (int(validated_after_scene), "after")

        # before_scene must be not None at this point due to earlier validation
        validated_before_scene = self.validate_type(before_scene, int, "before_scene")
        validated_before_scene = self.validate_range(
            validated_before_scene, min_val=1, field_name="before_scene"
        )
        return (int(validated_before_scene), "before")

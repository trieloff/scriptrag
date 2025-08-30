"""Project validators for CLI input."""

from __future__ import annotations

import re

from scriptrag.cli.validators.base import ValidationError, Validator


class ProjectValidator(Validator[str]):
    """Validator for project names."""

    def __init__(self, allow_spaces: bool = True) -> None:
        """Initialize project validator.

        Args:
            allow_spaces: Whether to allow spaces in project names (defaults to True
                        since most real project names contain spaces)
        """
        self.allow_spaces = allow_spaces

    def validate(self, value: str) -> str:
        """Validate project name.

        Args:
            value: Project name to validate

        Returns:
            Validated project name

        Raises:
            ValidationError: If validation fails
        """
        project = self.validate_required(value, "project name")

        # Check length
        if len(project) < 1 or len(project) > 100:
            raise ValidationError("Project name must be between 1 and 100 characters")

        # Check for invalid characters
        pattern = (
            r"^[a-zA-Z0-9\s\-_]+$"  # Allow spaces
            if self.allow_spaces
            else r"^[a-zA-Z0-9\-_]+$"  # No spaces
        )

        if not re.match(pattern, project):
            if self.allow_spaces:
                raise ValidationError(
                    "Project name can only contain letters, numbers, "
                    "spaces, hyphens, and underscores"
                )
            raise ValidationError(
                "Project name can only contain letters, numbers, "
                "hyphens, and underscores (no spaces)"
            )

        return project  # type: ignore[no-any-return]


class EpisodeIdentifierValidator(Validator[dict]):
    """Validator for TV episode identifiers."""

    def validate(self, value: dict) -> dict:
        """Validate episode identifier.

        Args:
            value: Dictionary with season and episode numbers

        Returns:
            Validated dictionary

        Raises:
            ValidationError: If validation fails
        """
        season = value.get("season")
        episode = value.get("episode")

        if season is not None:
            self.validate_type(season, int, "season")
            self.validate_range(season, min_val=1, max_val=99, field_name="season")

        if episode is not None:
            self.validate_type(episode, int, "episode")
            self.validate_range(episode, min_val=1, max_val=999, field_name="episode")

            # Episode requires season
            if season is None:
                raise ValidationError("Episode number requires season number")

        return value

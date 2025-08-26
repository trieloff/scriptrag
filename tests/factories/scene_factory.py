"""Factory classes for Scene-related test data."""

import hashlib
from dataclasses import dataclass
from typing import Any

from scriptrag.parser.fountain_models import Dialogue, Scene


class SceneFactory:
    """Factory for creating Scene instances for testing."""

    @staticmethod
    def create(
        number: int = 1,
        heading: str = "INT. COFFEE SHOP - DAY",
        content: str | None = None,
        original_text: str | None = None,
        content_hash: str | None = None,
        scene_type: str = "INT",
        location: str = "COFFEE SHOP",
        time_of_day: str = "DAY",
        dialogue_lines: list[Dialogue] | None = None,
        action_lines: list[str] | None = None,
        boneyard_metadata: dict[str, Any] | None = None,
        has_new_metadata: bool = False,
    ) -> Scene:
        """Create a Scene instance with sensible defaults."""
        if content is None:
            content = f"{heading}\n\nThe scene begins."

        if original_text is None:
            original_text = content

        if content_hash is None:
            content_hash = hashlib.sha256(content.encode()).hexdigest()

        if dialogue_lines is None:
            dialogue_lines = []

        if action_lines is None:
            action_lines = []

        return Scene(
            number=number,
            heading=heading,
            content=content,
            original_text=original_text,
            content_hash=content_hash,
            type=scene_type,
            location=location,
            time_of_day=time_of_day,
            dialogue_lines=dialogue_lines,
            action_lines=action_lines,
            boneyard_metadata=boneyard_metadata,
            has_new_metadata=has_new_metadata,
        )

    @staticmethod
    def create_with_dialogue(
        number: int = 1,
        character: str = "JOHN",
        dialogue_text: str = "Hello, world!",
        parenthetical: str | None = None,
    ) -> Scene:
        """Create a Scene with dialogue."""
        heading = "INT. OFFICE - DAY"
        dialogue = Dialogue(
            character=character,
            text=dialogue_text,
            parenthetical=parenthetical,
        )

        content = f"{heading}\n\n{character}\n"
        if parenthetical:
            content += f"({parenthetical})\n"
        content += f"{dialogue_text}\n"

        return SceneFactory.create(
            number=number,
            heading=heading,
            content=content,
            dialogue_lines=[dialogue],
        )

    @staticmethod
    def create_exterior(
        number: int = 1,
        location: str = "PARKING LOT",
        time_of_day: str = "NIGHT",
    ) -> Scene:
        """Create an exterior scene."""
        heading = f"EXT. {location} - {time_of_day}"
        content = f"{heading}\n\nThe scene takes place outside."

        return SceneFactory.create(
            number=number,
            heading=heading,
            content=content,
            type="EXT",
            location=location,
            time_of_day=time_of_day,
        )


@dataclass
class SceneDataFactory:
    """Factory for creating Scene-like data dictionaries for API mocking."""

    @staticmethod
    def create_dict(
        number: int = 1,
        heading: str = "INT. COFFEE SHOP - DAY",
        content: str = "Scene content here",
        **kwargs,
    ) -> dict:
        """Create a dictionary representation of a scene."""
        return {
            "number": number,
            "heading": heading,
            "content": content,
            **kwargs,
        }

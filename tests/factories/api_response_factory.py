"""Factory classes for API response test data."""

from dataclasses import dataclass

from scriptrag.parser.fountain_models import Scene
from tests.factories.scene_factory import SceneFactory


@dataclass
class ReadSceneResultFactory:
    """Factory for creating ReadSceneResult-like responses."""

    @staticmethod
    def success(scene: Scene | None = None) -> dict:
        """Create a successful read result."""
        if scene is None:
            scene = SceneFactory.create()

        return {
            "success": True,
            "scene": scene,
            "error": None,
        }

    @staticmethod
    def failure(error: str = "Scene not found") -> dict:
        """Create a failed read result."""
        return {
            "success": False,
            "scene": None,
            "error": error,
        }


@dataclass
class UpdateSceneResultFactory:
    """Factory for creating UpdateSceneResult-like responses."""

    @staticmethod
    def success(message: str = "Scene updated successfully") -> dict:
        """Create a successful update result."""
        return {
            "success": True,
            "message": message,
            "error": None,
        }

    @staticmethod
    def failure(error: str = "Update failed") -> dict:
        """Create a failed update result."""
        return {
            "success": False,
            "message": None,
            "error": error,
        }


@dataclass
class BibleReadResultFactory:
    """Factory for creating BibleReadResult-like responses."""

    @staticmethod
    def success(content: dict[str, str] | None = None) -> dict:
        """Create a successful bible read result."""
        if content is None:
            content = {
                "world_bible.md": "# World Bible\n\nThe story world...",
                "character_bible.md": "# Character Bible\n\nMain characters...",
            }

        return {
            "success": True,
            "content": content,
            "error": None,
        }

    @staticmethod
    def failure(error: str = "Bible files not found") -> dict:
        """Create a failed bible read result."""
        return {
            "success": False,
            "content": None,
            "error": error,
        }

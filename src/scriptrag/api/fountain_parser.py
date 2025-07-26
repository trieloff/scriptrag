"""Simplified Fountain parser for API usage."""

from scriptrag.api.models import SceneModel, ScriptModel
from scriptrag.parser import FountainParser as BaseFountainParser


class FountainParser:
    """Simplified Fountain parser that returns API models."""

    def __init__(self) -> None:
        """Initialize parser."""
        self._base_parser = BaseFountainParser()

    def parse_string(
        self, content: str, title: str | None = None, author: str | None = None
    ) -> ScriptModel:
        """Parse Fountain content and return API script model.

        Args:
            content: Fountain format content
            title: Optional title override
            author: Optional author override

        Returns:
            ScriptModel for API usage
        """
        # Parse with base parser
        script = self._base_parser.parse_string(content)

        # Convert to API model
        scenes = []
        all_characters: set[str] = set()

        for i, _scene_id in enumerate(script.scenes):
            # For now, create simple scene models
            # In a real implementation, we'd load the actual scene data
            scene_model = SceneModel(
                scene_number=i + 1,
                heading=f"Scene {i + 1}",
                content="",  # Would be populated from actual scene data
                characters=[],
            )
            scenes.append(scene_model)

        return ScriptModel(
            title=title or script.title,
            author=author or script.author,
            scenes=scenes,
            characters=all_characters,
            metadata=script.metadata or {},
        )

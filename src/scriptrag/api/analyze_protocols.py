"""Protocol definitions for script analysis components."""

from typing import Any, Protocol


class SceneAnalyzer(Protocol):
    """Protocol defining the interface for scene analysis components.

    Defines the contract that all scene analyzers must implement to participate
    in the analysis pipeline. Analyzers receive scene data and return metadata
    that gets attached to scenes in the Fountain file's boneyard comments.

    The protocol enables pluggable analyzers for different types of scene
    analysis: character relationships, embeddings, themes, etc.

    Example:
        >>> class MyAnalyzer:
        ...     @property
        ...     def name(self) -> str:
        ...         return "my_analyzer"
        ...
        ...     async def analyze(self, scene: dict) -> dict:
        ...         return {"analysis": "completed"}
    """

    async def analyze(self, scene: dict[str, Any]) -> dict[str, Any]:
        """Analyze a scene and return analysis metadata.

        Args:
            scene: Dictionary containing scene data with keys like 'content',
                  'heading', 'dialogue', 'action', 'characters'

        Returns:
            Dictionary containing analysis results to be stored in scene metadata
        """
        ...

    @property
    def name(self) -> str:
        """Unique identifier for this analyzer.

        Returns:
            String name used for metadata storage and analyzer registration
        """
        ...

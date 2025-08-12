"""Base classes for scene analyzers."""

from abc import ABC, abstractmethod


class BaseSceneAnalyzer(ABC):
    """Base class for pluggable scene analyzers.

    Scene analyzers are used by the analyze command to extract
    additional metadata from scenes beyond the basic extraction.
    """

    def __init__(self, config: dict | None = None):
        """Initialize analyzer.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

    @abstractmethod
    async def analyze(self, scene: dict) -> dict:
        """Analyze a scene and return metadata.

        Args:
            scene: The scene dictionary containing:
                - content: Full scene text
                - heading: Scene heading (e.g., "INT. COFFEE SHOP - DAY")
                - dialogue: List of dialogue entries
                - action: List of action lines
                - characters: List of character names in scene

        Returns:
            Dictionary of analysis results to be merged into scene metadata
        """
        pass  # pragma: no cover

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this analyzer.

        This name is used in the metadata to identify results from this analyzer.
        """
        pass  # pragma: no cover

    @property
    def version(self) -> str:
        """Version of this analyzer.

        Override this to track analyzer versions in metadata.
        """
        return "1.0.0"

    @property
    def requires_llm(self) -> bool:
        """Whether this analyzer requires LLM access.

        Override to return True if your analyzer needs LLM.
        """
        return False

    async def initialize(self) -> None:  # noqa: B027
        """Initialize any resources needed by the analyzer.

        Called once before processing begins.
        Override if you need to set up connections, load models, etc.

        Base implementation does nothing - subclasses should override if needed.
        """
        # Intentionally empty - subclasses override as needed
        pass  # pragma: no cover

    async def cleanup(self) -> None:  # noqa: B027
        """Clean up any resources used by the analyzer.

        Called once after processing completes.
        Override if you need to close connections, free memory, etc.

        Base implementation does nothing - subclasses should override if needed.
        """
        # Intentionally empty - subclasses override as needed
        pass  # pragma: no cover

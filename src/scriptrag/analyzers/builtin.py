"""Built-in scene analyzers for ScriptRAG."""

from .base import BaseSceneAnalyzer
from .props_inventory import PropsInventoryAnalyzer


class NOPAnalyzer(BaseSceneAnalyzer):
    """No-operation analyzer that does nothing.

    This is a minimal analyzer implementation that returns empty results.
    It serves as a starting point for the analyze command without any
    actual analysis functionality.
    """

    name = "nop"

    async def analyze(self, scene: dict) -> dict:  # noqa: ARG002
        """Perform no analysis and return empty results.

        Args:
            scene: Scene data (ignored)

        Returns:
            Empty dictionary
        """
        return {}


# Registry of built-in analyzers
BUILTIN_ANALYZERS: dict[str, type[BaseSceneAnalyzer]] = {
    "nop": NOPAnalyzer,
    "props_inventory": PropsInventoryAnalyzer,
}

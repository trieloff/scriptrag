"""Built-in scene analyzers for ScriptRAG."""

from .base import BaseSceneAnalyzer


class NOPAnalyzer(BaseSceneAnalyzer):
    """No-operation analyzer that does nothing.
    
    This is a minimal analyzer implementation that returns empty results.
    It serves as a starting point for the analyze command without any
    actual analysis functionality.
    """

    name = "nop"
    
    async def analyze(self, scene: dict) -> dict:
        """Perform no analysis and return empty results.
        
        Args:
            scene: Scene data (ignored)
            
        Returns:
            Empty dictionary
        """
        return {}


# Registry of built-in analyzers - starting with just NOP
BUILTIN_ANALYZERS: dict[str, type[BaseSceneAnalyzer]] = {
    "nop": NOPAnalyzer,
}
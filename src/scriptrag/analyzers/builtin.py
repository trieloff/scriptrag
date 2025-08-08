"""Built-in scene analyzers for ScriptRAG."""

from .base import BaseSceneAnalyzer
from .embedding import SceneEmbeddingAnalyzer

# Registry of built-in analyzers
BUILTIN_ANALYZERS: dict[str, type[BaseSceneAnalyzer]] = {
    "scene_embeddings": SceneEmbeddingAnalyzer,
}

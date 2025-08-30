"""Built-in scene analyzers for ScriptRAG."""

from __future__ import annotations

from .base import BaseSceneAnalyzer
from .embedding import SceneEmbeddingAnalyzer
from .relationships import CharacterRelationshipsAnalyzer

# Registry of built-in analyzers
BUILTIN_ANALYZERS: dict[str, type[BaseSceneAnalyzer]] = {
    "scene_embeddings": SceneEmbeddingAnalyzer,
    "relationships": CharacterRelationshipsAnalyzer,
}

"""Embeddings module for ScriptRAG - handles vector generation and management."""

from .cache import EmbeddingCache
from .pipeline import EmbeddingPipeline
from .similarity import SimilarityCalculator
from .vector_store import VectorStore

__all__ = [
    "EmbeddingCache",
    "EmbeddingPipeline",
    "SimilarityCalculator",
    "VectorStore",
]

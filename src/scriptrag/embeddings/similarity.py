"""Similarity calculation utilities for embeddings."""

from enum import Enum
from typing import Any

import numpy as np

from scriptrag.config import get_logger

logger = get_logger(__name__)


class SimilarityMetric(Enum):
    """Supported similarity metrics."""

    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"
    MANHATTAN = "manhattan"


class SimilarityCalculator:
    """Calculator for various similarity metrics between embeddings."""

    def __init__(self, metric: SimilarityMetric = SimilarityMetric.COSINE):
        """Initialize similarity calculator.

        Args:
            metric: Default similarity metric to use
        """
        self.metric = metric

    def calculate(
        self,
        vec1: list[float] | np.ndarray,
        vec2: list[float] | np.ndarray,
        metric: SimilarityMetric | None = None,
    ) -> float:
        """Calculate similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector
            metric: Metric to use (defaults to instance metric)

        Returns:
            Similarity score

        Raises:
            ValueError: If vectors have different dimensions
        """
        metric = metric or self.metric

        # Convert to numpy arrays
        np_vec1 = np.array(vec1) if not isinstance(vec1, np.ndarray) else vec1
        np_vec2 = np.array(vec2) if not isinstance(vec2, np.ndarray) else vec2

        # Validate dimensions
        if np_vec1.shape != np_vec2.shape:
            raise ValueError(
                f"Vector dimension mismatch: {np_vec1.shape} vs {np_vec2.shape}"
            )

        if metric == SimilarityMetric.COSINE:
            return self.cosine_similarity(np_vec1, np_vec2)
        if metric == SimilarityMetric.EUCLIDEAN:
            return self.euclidean_distance(np_vec1, np_vec2)
        if metric == SimilarityMetric.DOT_PRODUCT:
            return self.dot_product(np_vec1, np_vec2)
        if metric == SimilarityMetric.MANHATTAN:
            return self.manhattan_distance(np_vec1, np_vec2)
        raise ValueError(f"Unsupported metric: {metric}")

    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score between -1 and 1
        """
        # Normalize vectors
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Calculate cosine similarity
        similarity = np.dot(vec1, vec2) / (norm1 * norm2)
        return float(similarity)

    @staticmethod
    def euclidean_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate Euclidean distance between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Euclidean distance (lower is more similar)
        """
        return float(np.linalg.norm(vec1 - vec2))

    @staticmethod
    def dot_product(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate dot product between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Dot product value
        """
        return float(np.dot(vec1, vec2))

    @staticmethod
    def manhattan_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate Manhattan (L1) distance between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Manhattan distance (lower is more similar)
        """
        return float(np.sum(np.abs(vec1 - vec2)))

    def find_most_similar(
        self,
        query_embedding: list[float] | np.ndarray,
        candidate_embeddings: list[tuple[int, list[float] | np.ndarray]],
        top_k: int = 10,
        threshold: float | None = None,
        metric: SimilarityMetric | None = None,
    ) -> list[tuple[int, float]]:
        """Find most similar embeddings to a query.

        Args:
            query_embedding: Query vector
            candidate_embeddings: List of (id, embedding) tuples
            top_k: Number of top results to return
            threshold: Optional similarity threshold
            metric: Metric to use (defaults to instance metric)

        Returns:
            List of (id, similarity_score) tuples, sorted by similarity
        """
        metric = metric or self.metric
        similarities = []

        # Convert query to numpy
        query_np = (
            np.array(query_embedding)
            if not isinstance(query_embedding, np.ndarray)
            else query_embedding
        )

        for entity_id, embedding in candidate_embeddings:
            try:
                score = self.calculate(query_np, embedding, metric)

                # For distance metrics, convert to similarity (higher is better)
                if metric in [
                    SimilarityMetric.EUCLIDEAN,
                    SimilarityMetric.MANHATTAN,
                ]:
                    # Convert distance to similarity score (0-1 range)
                    # Using exponential decay: e^(-distance)
                    score = float(np.exp(-score))

                # Apply threshold if specified
                if threshold is None or score >= threshold:
                    similarities.append((entity_id, score))

            except ValueError as e:
                logger.warning(f"Skipping entity {entity_id}: {e}")
                continue

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top k results
        return similarities[:top_k]

    def batch_similarity(
        self,
        embeddings: list[list[float] | np.ndarray],
        metric: SimilarityMetric | None = None,
    ) -> np.ndarray:
        """Calculate pairwise similarities for a batch of embeddings.

        Args:
            embeddings: List of embedding vectors
            metric: Metric to use (defaults to instance metric)

        Returns:
            Similarity matrix (n x n)
        """
        metric = metric or self.metric
        n = len(embeddings)

        # Convert to numpy matrix
        matrix = np.array(
            [
                np.array(emb) if not isinstance(emb, np.ndarray) else emb
                for emb in embeddings
            ]
        )

        # Initialize similarity matrix
        similarities = np.zeros((n, n))

        # Calculate pairwise similarities
        for i in range(n):
            for j in range(i, n):
                if i == j:
                    similarities[i, j] = 1.0  # Self-similarity
                else:
                    score = self.calculate(matrix[i], matrix[j], metric)
                    similarities[i, j] = score
                    similarities[j, i] = score  # Symmetric

        return similarities

    def rerank_results(
        self,
        query_embedding: list[float] | np.ndarray,
        results: list[tuple[int, Any, list[float] | np.ndarray]],
        metric: SimilarityMetric | None = None,
    ) -> list[tuple[int, float, Any]]:
        """Rerank search results using a different similarity metric.

        Args:
            query_embedding: Query vector
            results: List of (id, metadata, embedding) tuples
            metric: Metric to use for reranking

        Returns:
            List of (id, new_score, metadata) tuples, sorted by new scores
        """
        metric = metric or self.metric
        reranked = []

        for entity_id, metadata, embedding in results:
            score = self.calculate(query_embedding, embedding, metric)

            # Convert distance to similarity if needed
            if metric in [SimilarityMetric.EUCLIDEAN, SimilarityMetric.MANHATTAN]:
                score = float(np.exp(-score))

            reranked.append((entity_id, score, metadata))

        # Sort by new scores
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked

    def normalize_embeddings(
        self, embeddings: list[list[float] | np.ndarray]
    ) -> list[np.ndarray]:
        """Normalize embeddings to unit vectors.

        Args:
            embeddings: List of embedding vectors

        Returns:
            List of normalized embeddings
        """
        normalized = []
        for embedding in embeddings:
            np_emb = (
                np.array(embedding)
                if not isinstance(embedding, np.ndarray)
                else embedding
            )
            norm = np.linalg.norm(np_emb)
            if norm > 0:
                normalized.append(np_emb / norm)
            else:
                normalized.append(np_emb)
        return normalized

    def centroid(self, embeddings: list[list[float] | np.ndarray]) -> np.ndarray:
        """Calculate centroid of multiple embeddings.

        Args:
            embeddings: List of embedding vectors

        Returns:
            Centroid vector
        """
        if not embeddings:
            raise ValueError("Cannot calculate centroid of empty list")

        # Convert to numpy matrix
        matrix = np.array(
            [
                np.array(emb) if not isinstance(emb, np.ndarray) else emb
                for emb in embeddings
            ]
        )

        # Calculate mean across embeddings
        result: np.ndarray = np.mean(matrix, axis=0)
        return result

"""Comprehensive tests for similarity calculation utilities."""

import math

import numpy as np
import pytest

from scriptrag.embeddings.similarity import (
    SimilarityCalculator,
    SimilarityMetric,
)


class TestSimilarityMetric:
    """Test SimilarityMetric enum."""

    def test_enum_values(self):
        """Test that enum values are correct."""
        assert SimilarityMetric.COSINE.value == "cosine"
        assert SimilarityMetric.EUCLIDEAN.value == "euclidean"
        assert SimilarityMetric.DOT_PRODUCT.value == "dot_product"
        assert SimilarityMetric.MANHATTAN.value == "manhattan"

    def test_all_metrics_defined(self):
        """Test that all expected metrics are defined."""
        expected_metrics = {"cosine", "euclidean", "dot_product", "manhattan"}
        actual_metrics = {metric.value for metric in SimilarityMetric}
        assert actual_metrics == expected_metrics


class TestSimilarityCalculator:
    """Test SimilarityCalculator class."""

    @pytest.fixture
    def calculator(self):
        """Create similarity calculator."""
        return SimilarityCalculator()

    def test_init_default_metric(self):
        """Test calculator initialization with default metric."""
        calc = SimilarityCalculator()
        assert calc.metric == SimilarityMetric.COSINE

    def test_init_custom_metric(self):
        """Test calculator initialization with custom metric."""
        calc = SimilarityCalculator(SimilarityMetric.EUCLIDEAN)
        assert calc.metric == SimilarityMetric.EUCLIDEAN

    def test_calculate_cosine_similarity_identical(self, calculator):
        """Test cosine similarity with identical vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        result = calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)
        assert pytest.approx(result) == 1.0

    def test_calculate_cosine_similarity_orthogonal(self, calculator):
        """Test cosine similarity with orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        result = calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)
        assert pytest.approx(result) == 0.0

    def test_calculate_cosine_similarity_opposite(self, calculator):
        """Test cosine similarity with opposite vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]

        result = calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)
        assert pytest.approx(result) == -1.0

    def test_calculate_cosine_similarity_scaled(self, calculator):
        """Test cosine similarity with scaled vectors."""
        vec1 = [1.0, 1.0, 0.0]
        vec2 = [2.0, 2.0, 0.0]  # Same direction, different magnitude

        result = calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)
        assert pytest.approx(result) == 1.0

    def test_calculate_euclidean_distance_identical(self, calculator):
        """Test Euclidean distance with identical vectors."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0, 3.0]

        result = calculator.calculate(vec1, vec2, SimilarityMetric.EUCLIDEAN)
        assert pytest.approx(result) == 0.0

    def test_calculate_euclidean_distance_simple(self, calculator):
        """Test Euclidean distance with simple case."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [3.0, 4.0, 0.0]

        result = calculator.calculate(vec1, vec2, SimilarityMetric.EUCLIDEAN)
        assert pytest.approx(result) == 5.0  # 3-4-5 triangle

    def test_calculate_dot_product_orthogonal(self, calculator):
        """Test dot product with orthogonal vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        result = calculator.calculate(vec1, vec2, SimilarityMetric.DOT_PRODUCT)
        assert pytest.approx(result) == 0.0

    def test_calculate_dot_product_parallel(self, calculator):
        """Test dot product with parallel vectors."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [2.0, 4.0, 6.0]  # Same direction, double magnitude

        result = calculator.calculate(vec1, vec2, SimilarityMetric.DOT_PRODUCT)
        # 1*2 + 2*4 + 3*6 = 2 + 8 + 18 = 28
        assert pytest.approx(result) == 28.0

    def test_calculate_manhattan_distance_identical(self, calculator):
        """Test Manhattan distance with identical vectors."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.0, 2.0, 3.0]

        result = calculator.calculate(vec1, vec2, SimilarityMetric.MANHATTAN)
        assert pytest.approx(result) == 0.0

    def test_calculate_manhattan_distance_simple(self, calculator):
        """Test Manhattan distance with simple case."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]

        result = calculator.calculate(vec1, vec2, SimilarityMetric.MANHATTAN)
        # |1-0| + |2-0| + |3-0| = 1 + 2 + 3 = 6
        assert pytest.approx(result) == 6.0

    def test_calculate_with_numpy_arrays(self, calculator):
        """Test calculation with numpy arrays as input."""
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([0.0, 1.0, 0.0])

        result = calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)
        assert pytest.approx(result) == 0.0

    def test_calculate_mixed_input_types(self, calculator):
        """Test calculation with mixed list/numpy input types."""
        vec1 = [1.0, 0.0, 0.0]  # List
        vec2 = np.array([1.0, 0.0, 0.0])  # Numpy array

        result = calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)
        assert pytest.approx(result) == 1.0

    def test_calculate_dimension_mismatch(self, calculator):
        """Test calculation with mismatched vector dimensions."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0]  # Different dimension

        with pytest.raises(ValueError) as exc_info:
            calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)

        assert "dimension mismatch" in str(exc_info.value).lower()

    def test_calculate_unsupported_metric(self, calculator):
        """Test calculation with unsupported metric."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        # Create a mock metric that doesn't exist
        class MockMetric:
            pass

        mock_metric = MockMetric()

        with pytest.raises(ValueError) as exc_info:
            calculator.calculate(vec1, vec2, mock_metric)

        assert "Unsupported metric" in str(exc_info.value)

    def test_calculate_uses_default_metric(self, calculator):
        """Test that calculate uses default metric when none specified."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        # Should use default COSINE metric
        result = calculator.calculate(vec1, vec2)
        assert pytest.approx(result) == 1.0

    def test_calculate_overrides_default_metric(self, calculator):
        """Test that explicit metric overrides default."""
        # Calculator has COSINE default
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 1.0, 1.0]

        cosine_result = calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)
        euclidean_result = calculator.calculate(vec1, vec2, SimilarityMetric.EUCLIDEAN)

        # Results should be different
        assert cosine_result != euclidean_result

    def test_cosine_similarity_static_method(self):
        """Test cosine_similarity static method."""
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([0.0, 1.0, 0.0])

        result = SimilarityCalculator.cosine_similarity(vec1, vec2)
        assert pytest.approx(result) == 0.0

    def test_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector."""
        vec1 = np.array([0.0, 0.0, 0.0])
        vec2 = np.array([1.0, 1.0, 1.0])

        result = SimilarityCalculator.cosine_similarity(vec1, vec2)
        assert pytest.approx(result) == 0.0

    def test_cosine_similarity_both_zero_vectors(self):
        """Test cosine similarity with both zero vectors."""
        vec1 = np.array([0.0, 0.0, 0.0])
        vec2 = np.array([0.0, 0.0, 0.0])

        result = SimilarityCalculator.cosine_similarity(vec1, vec2)
        assert pytest.approx(result) == 0.0

    def test_cosine_similarity_normalized_vectors(self):
        """Test cosine similarity with pre-normalized vectors."""
        # Unit vectors
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([0.0, 1.0, 0.0])

        result = SimilarityCalculator.cosine_similarity(vec1, vec2)
        assert pytest.approx(result) == 0.0

    def test_euclidean_distance_static_method(self):
        """Test euclidean_distance static method."""
        vec1 = np.array([0.0, 0.0])
        vec2 = np.array([3.0, 4.0])

        result = SimilarityCalculator.euclidean_distance(vec1, vec2)
        assert pytest.approx(result) == 5.0

    def test_dot_product_static_method(self):
        """Test dot_product static method."""
        vec1 = np.array([1.0, 2.0, 3.0])
        vec2 = np.array([4.0, 5.0, 6.0])

        result = SimilarityCalculator.dot_product(vec1, vec2)
        # 1*4 + 2*5 + 3*6 = 4 + 10 + 18 = 32
        assert pytest.approx(result) == 32.0

    def test_manhattan_distance_static_method(self):
        """Test manhattan_distance static method."""
        vec1 = np.array([1.0, 2.0, 3.0])
        vec2 = np.array([4.0, 6.0, 8.0])

        result = SimilarityCalculator.manhattan_distance(vec1, vec2)
        # |1-4| + |2-6| + |3-8| = 3 + 4 + 5 = 12
        assert pytest.approx(result) == 12.0

    def test_manhattan_distance_negative_values(self):
        """Test Manhattan distance with negative values."""
        vec1 = np.array([-1.0, -2.0, -3.0])
        vec2 = np.array([1.0, 2.0, 3.0])

        result = SimilarityCalculator.manhattan_distance(vec1, vec2)
        # |-1-1| + |-2-2| + |-3-3| = 2 + 4 + 6 = 12
        assert pytest.approx(result) == 12.0

    def test_find_most_similar_basic(self, calculator):
        """Test finding most similar embeddings - basic case."""
        query = [1.0, 0.0, 0.0]
        candidates = [
            (1, [1.0, 0.0, 0.0]),  # Identical - should be first
            (2, [0.9, 0.1, 0.0]),  # Very similar - should be second
            (3, [0.0, 1.0, 0.0]),  # Orthogonal - should be last
            (4, [0.5, 0.5, 0.0]),  # Somewhat similar - should be third
        ]

        results = calculator.find_most_similar(query, candidates, top_k=3)

        assert len(results) == 3
        assert results[0][0] == 1  # ID 1 should be most similar
        assert results[0][1] == pytest.approx(1.0)  # Perfect similarity
        assert results[1][0] == 2  # ID 2 should be second
        assert results[2][0] == 4  # ID 4 should be third

    def test_find_most_similar_with_threshold(self, calculator):
        """Test finding most similar with similarity threshold."""
        query = [1.0, 0.0, 0.0]
        candidates = [
            (1, [1.0, 0.0, 0.0]),  # Similarity = 1.0
            (2, [0.8, 0.6, 0.0]),  # Similarity ≈ 0.8
            (3, [0.3, 0.4, 0.0]),  # Similarity = 0.6 (below threshold)
            (4, [0.0, 1.0, 0.0]),  # Similarity = 0.0 (below threshold)
        ]

        results = calculator.find_most_similar(
            query, candidates, top_k=5, threshold=0.7
        )

        # Only candidates 1 and 2 should meet the threshold
        assert len(results) == 2
        assert results[0][0] == 1
        assert results[1][0] == 2
        assert all(score >= 0.7 for _, score in results)

    def test_find_most_similar_euclidean_metric(self, calculator):
        """Test finding most similar with Euclidean distance metric."""
        query = [0.0, 0.0, 0.0]
        candidates = [
            (1, [1.0, 0.0, 0.0]),  # Distance = 1.0
            (2, [2.0, 0.0, 0.0]),  # Distance = 2.0
            (3, [3.0, 4.0, 0.0]),  # Distance = 5.0
        ]

        results = calculator.find_most_similar(
            query, candidates, metric=SimilarityMetric.EUCLIDEAN
        )

        # Should be ordered by distance (converted to similarity)
        # Closer distances should have higher similarity scores
        assert len(results) == 3
        assert results[0][0] == 1  # Closest distance
        assert results[1][0] == 2  # Middle distance
        assert results[2][0] == 3  # Farthest distance

        # Scores should be in descending order (higher = more similar)
        assert results[0][1] > results[1][1] > results[2][1]

    def test_find_most_similar_manhattan_metric(self, calculator):
        """Test finding most similar with Manhattan distance metric."""
        query = [0.0, 0.0]
        candidates = [
            (1, [1.0, 1.0]),  # Manhattan distance = 2.0
            (2, [2.0, 0.0]),  # Manhattan distance = 2.0
            (3, [3.0, 3.0]),  # Manhattan distance = 6.0
        ]

        results = calculator.find_most_similar(
            query, candidates, metric=SimilarityMetric.MANHATTAN
        )

        assert len(results) == 3
        # Candidates 1 and 2 have same distance, so either could be first
        assert results[0][0] in [1, 2]
        assert results[1][0] in [1, 2]
        assert results[2][0] == 3  # Farthest

    def test_find_most_similar_empty_candidates(self, calculator):
        """Test finding most similar with empty candidates list."""
        query = [1.0, 0.0, 0.0]
        candidates = []

        results = calculator.find_most_similar(query, candidates)
        assert results == []

    def test_find_most_similar_with_numpy_query(self, calculator):
        """Test finding most similar with numpy array query."""
        query = np.array([1.0, 0.0, 0.0])
        candidates = [
            (1, [1.0, 0.0, 0.0]),
            (2, [0.0, 1.0, 0.0]),
        ]

        results = calculator.find_most_similar(query, candidates)

        assert len(results) == 2
        assert results[0][0] == 1  # More similar
        assert results[1][0] == 2  # Less similar

    def test_find_most_similar_dimension_mismatch(self, calculator):
        """Test finding most similar with dimension mismatch."""
        query = [1.0, 0.0, 0.0]
        candidates = [
            (1, [1.0, 0.0, 0.0]),  # Correct dimensions
            (2, [1.0, 0.0]),  # Wrong dimensions - should be skipped
            (3, [0.0, 1.0, 0.0]),  # Correct dimensions
        ]

        results = calculator.find_most_similar(query, candidates)

        # Should skip candidate 2 due to dimension mismatch
        assert len(results) == 2
        assert results[0][0] == 1
        assert results[1][0] == 3

    def test_find_most_similar_top_k_limit(self, calculator):
        """Test that top_k properly limits results."""
        query = [1.0, 0.0]
        candidates = [(i, [1.0, 0.0]) for i in range(10)]  # 10 identical candidates

        results = calculator.find_most_similar(query, candidates, top_k=3)

        assert len(results) == 3  # Should limit to top_k
        # All should have same similarity score
        for _, score in results:
            assert pytest.approx(score) == 1.0

    def test_find_most_similar_uses_default_metric(self, calculator):
        """Test that find_most_similar uses calculator's default metric."""
        # Set calculator to use Euclidean by default
        calculator.metric = SimilarityMetric.EUCLIDEAN

        query = [0.0, 0.0]
        candidates = [
            (1, [1.0, 0.0]),  # Distance = 1.0
            (2, [2.0, 0.0]),  # Distance = 2.0
        ]

        results = calculator.find_most_similar(query, candidates)

        # Should use Euclidean distance (converted to similarity)
        assert results[0][0] == 1  # Closer should be more similar
        assert results[1][0] == 2
        assert results[0][1] > results[1][1]  # Higher similarity for closer

    def test_batch_similarity_basic(self, calculator):
        """Test batch similarity calculation."""
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [1.0, 0.0, 0.0],  # Same as first
        ]

        matrix = calculator.batch_similarity(embeddings)

        # Should be 3x3 matrix
        assert matrix.shape == (3, 3)

        # Diagonal should be all 1.0 (self-similarity)
        assert pytest.approx(matrix[0, 0]) == 1.0
        assert pytest.approx(matrix[1, 1]) == 1.0
        assert pytest.approx(matrix[2, 2]) == 1.0

        # First and third embeddings are identical
        assert pytest.approx(matrix[0, 2]) == 1.0
        assert pytest.approx(matrix[2, 0]) == 1.0

        # First and second are orthogonal (cosine = 0)
        assert pytest.approx(matrix[0, 1]) == 0.0
        assert pytest.approx(matrix[1, 0]) == 0.0

        # Matrix should be symmetric
        np.testing.assert_array_almost_equal(matrix, matrix.T)

    def test_batch_similarity_single_embedding(self, calculator):
        """Test batch similarity with single embedding."""
        embeddings = [[1.0, 0.0, 0.0]]

        matrix = calculator.batch_similarity(embeddings)

        assert matrix.shape == (1, 1)
        assert pytest.approx(matrix[0, 0]) == 1.0

    def test_batch_similarity_empty(self, calculator):
        """Test batch similarity with empty embeddings."""
        embeddings = []

        matrix = calculator.batch_similarity(embeddings)

        assert matrix.shape == (0, 0)

    def test_batch_similarity_euclidean_metric(self, calculator):
        """Test batch similarity with Euclidean metric."""
        embeddings = [
            [0.0, 0.0],
            [3.0, 4.0],  # Distance = 5.0 from first
        ]

        matrix = calculator.batch_similarity(
            embeddings, metric=SimilarityMetric.EUCLIDEAN
        )

        assert matrix.shape == (2, 2)
        # Diagonal should be 1.0 (self-similarity)
        assert pytest.approx(matrix[0, 0]) == 1.0
        assert pytest.approx(matrix[1, 1]) == 1.0
        # Off-diagonal should be distance value (not converted to similarity here)
        assert pytest.approx(matrix[0, 1]) == 5.0
        assert pytest.approx(matrix[1, 0]) == 5.0

    def test_batch_similarity_with_numpy_arrays(self, calculator):
        """Test batch similarity with numpy arrays as input."""
        embeddings = [
            np.array([1.0, 0.0]),
            np.array([0.0, 1.0]),
        ]

        matrix = calculator.batch_similarity(embeddings)

        assert matrix.shape == (2, 2)
        assert pytest.approx(matrix[0, 0]) == 1.0
        assert pytest.approx(matrix[1, 1]) == 1.0
        assert pytest.approx(matrix[0, 1]) == 0.0  # Orthogonal

    def test_rerank_results_basic(self, calculator):
        """Test reranking results with different metric."""
        query = [1.0, 0.0]
        results = [
            (1, {"title": "First"}, [1.0, 0.0]),  # Identical to query
            (2, {"title": "Second"}, [0.0, 1.0]),  # Orthogonal to query
            (3, {"title": "Third"}, [0.5, 0.5]),  # Somewhat similar
        ]

        reranked = calculator.rerank_results(query, results)

        assert len(reranked) == 3
        # Should be ordered by similarity (highest first)
        assert reranked[0][0] == 1  # Most similar
        assert reranked[0][2] == {"title": "First"}  # Metadata preserved
        assert reranked[1][0] == 3  # Second most similar
        assert reranked[2][0] == 2  # Least similar

        # Scores should be in descending order
        assert reranked[0][1] > reranked[1][1] > reranked[2][1]

    def test_rerank_results_euclidean_metric(self, calculator):
        """Test reranking with Euclidean distance metric."""
        query = [0.0, 0.0]
        results = [
            (1, {"meta": "data1"}, [1.0, 0.0]),  # Distance = 1.0
            (2, {"meta": "data2"}, [3.0, 4.0]),  # Distance = 5.0
        ]

        reranked = calculator.rerank_results(
            query, results, metric=SimilarityMetric.EUCLIDEAN
        )

        assert len(reranked) == 2
        # Closer distance should be ranked higher
        assert reranked[0][0] == 1  # Distance 1.0, higher similarity score
        assert reranked[1][0] == 2  # Distance 5.0, lower similarity score
        assert reranked[0][1] > reranked[1][1]  # Higher similarity for closer

    def test_rerank_results_empty(self, calculator):
        """Test reranking with empty results."""
        query = [1.0, 0.0]
        results = []

        reranked = calculator.rerank_results(query, results)
        assert reranked == []

    def test_rerank_results_uses_default_metric(self, calculator):
        """Test that reranking uses calculator's default metric."""
        query = [1.0, 0.0]
        results = [(1, {}, [1.0, 0.0])]

        # Should use default COSINE metric
        reranked = calculator.rerank_results(query, results)

        assert len(reranked) == 1
        assert pytest.approx(reranked[0][1]) == 1.0  # Perfect cosine similarity

    def test_normalize_embeddings_basic(self, calculator):
        """Test embedding normalization to unit vectors."""
        embeddings = [
            [3.0, 4.0],  # Length = 5.0
            [1.0, 0.0],  # Already unit vector
            [0.0, 0.0],  # Zero vector
        ]

        normalized = calculator.normalize_embeddings(embeddings)

        assert len(normalized) == 3

        # First embedding should be normalized to unit length
        np.testing.assert_array_almost_equal(normalized[0], [3.0 / 5.0, 4.0 / 5.0])

        # Second embedding should remain unchanged (already unit)
        np.testing.assert_array_almost_equal(normalized[1], [1.0, 0.0])

        # Zero vector should remain zero
        np.testing.assert_array_almost_equal(normalized[2], [0.0, 0.0])

    def test_normalize_embeddings_unit_lengths(self, calculator):
        """Test that normalized embeddings have unit length."""
        embeddings = [
            [3.0, 4.0, 0.0],
            [1.0, 2.0, 3.0],
            [10.0, 0.0, 0.0],
        ]

        normalized = calculator.normalize_embeddings(embeddings)

        # Check that all non-zero vectors have unit length
        for emb in normalized:
            length = np.linalg.norm(emb)
            if length > 0:  # Skip zero vectors
                assert pytest.approx(length) == 1.0

    def test_normalize_embeddings_with_numpy_arrays(self, calculator):
        """Test normalization with numpy arrays as input."""
        embeddings = [
            np.array([3.0, 4.0]),
            np.array([0.0, 5.0]),
        ]

        normalized = calculator.normalize_embeddings(embeddings)

        assert len(normalized) == 2
        # Results should be numpy arrays
        for norm_emb in normalized:
            assert isinstance(norm_emb, np.ndarray)

        # Check normalization
        np.testing.assert_array_almost_equal(normalized[0], [3.0 / 5.0, 4.0 / 5.0])
        np.testing.assert_array_almost_equal(normalized[1], [0.0, 1.0])

    def test_normalize_embeddings_empty(self, calculator):
        """Test normalization with empty embeddings list."""
        normalized = calculator.normalize_embeddings([])
        assert normalized == []

    def test_centroid_basic(self, calculator):
        """Test centroid calculation."""
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]

        centroid = calculator.centroid(embeddings)

        # Centroid should be average of all embeddings
        expected = [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]
        np.testing.assert_array_almost_equal(centroid, expected)

    def test_centroid_identical_embeddings(self, calculator):
        """Test centroid with identical embeddings."""
        embeddings = [
            [2.0, 3.0, 4.0],
            [2.0, 3.0, 4.0],
            [2.0, 3.0, 4.0],
        ]

        centroid = calculator.centroid(embeddings)

        # Centroid should be the same as input embeddings
        np.testing.assert_array_almost_equal(centroid, [2.0, 3.0, 4.0])

    def test_centroid_single_embedding(self, calculator):
        """Test centroid with single embedding."""
        embeddings = [[5.0, 10.0, 15.0]]

        centroid = calculator.centroid(embeddings)

        # Centroid of single embedding is itself
        np.testing.assert_array_almost_equal(centroid, [5.0, 10.0, 15.0])

    def test_centroid_with_numpy_arrays(self, calculator):
        """Test centroid calculation with numpy arrays."""
        embeddings = [
            np.array([1.0, 2.0]),
            np.array([3.0, 4.0]),
        ]

        centroid = calculator.centroid(embeddings)

        # Centroid should be average
        expected = [2.0, 3.0]  # (1+3)/2, (2+4)/2
        np.testing.assert_array_almost_equal(centroid, expected)
        assert isinstance(centroid, np.ndarray)

    def test_centroid_empty_list(self, calculator):
        """Test centroid with empty embeddings list."""
        with pytest.raises(ValueError) as exc_info:
            calculator.centroid([])

        assert "Cannot calculate centroid of empty list" in str(exc_info.value)

    def test_centroid_mixed_types(self, calculator):
        """Test centroid with mixed list/numpy types."""
        embeddings = [
            [1.0, 2.0],  # List
            np.array([3.0, 4.0]),  # Numpy array
        ]

        centroid = calculator.centroid(embeddings)

        expected = [2.0, 3.0]
        np.testing.assert_array_almost_equal(centroid, expected)

    def test_distance_to_similarity_conversion(self, calculator):
        """Test that distance metrics are properly converted to similarity scores."""
        query = [0.0, 0.0]
        candidates = [
            (1, [1.0, 0.0]),  # Distance = 1.0
            (2, [2.0, 0.0]),  # Distance = 2.0
        ]

        # Test Euclidean distance conversion
        euclidean_results = calculator.find_most_similar(
            query, candidates, metric=SimilarityMetric.EUCLIDEAN
        )

        # Manhattan distance conversion
        manhattan_results = calculator.find_most_similar(
            query, candidates, metric=SimilarityMetric.MANHATTAN
        )

        # Both should have closer distance ranked higher (higher similarity)
        assert euclidean_results[0][0] == 1  # Closer
        assert euclidean_results[1][0] == 2  # Farther
        assert euclidean_results[0][1] > euclidean_results[1][1]

        assert manhattan_results[0][0] == 1  # Closer
        assert manhattan_results[1][0] == 2  # Farther
        assert manhattan_results[0][1] > manhattan_results[1][1]

        # Similarity scores should be between 0 and 1 due to exp(-distance)
        for _, score in euclidean_results + manhattan_results:
            assert 0 <= score <= 1

    @pytest.mark.parametrize(
        "metric",
        [
            SimilarityMetric.COSINE,
            SimilarityMetric.EUCLIDEAN,
            SimilarityMetric.DOT_PRODUCT,
            SimilarityMetric.MANHATTAN,
        ],
    )
    def test_all_metrics_work(self, calculator, metric):
        """Test that all similarity metrics work without errors."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [4.0, 5.0, 6.0]

        # Should not raise any exceptions
        result = calculator.calculate(vec1, vec2, metric)
        assert isinstance(result, float)
        assert not math.isnan(result)
        assert not math.isinf(result)

    def test_large_dimension_vectors(self, calculator):
        """Test similarity calculation with high-dimensional vectors."""
        # Test with 1000-dimensional vectors
        vec1 = [1.0] * 1000
        vec2 = [2.0] * 1000

        result = calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)
        assert pytest.approx(result) == 1.0  # Same direction

        result = calculator.calculate(vec1, vec2, SimilarityMetric.EUCLIDEAN)
        assert pytest.approx(result) == math.sqrt(1000)  # sqrt(sum of 1.0^2)

    def test_precision_with_small_values(self, calculator):
        """Test precision with very small floating point values."""
        vec1 = [1e-10, 2e-10, 3e-10]
        vec2 = [4e-10, 5e-10, 6e-10]

        # Should handle small values without underflow
        result = calculator.calculate(vec1, vec2, SimilarityMetric.COSINE)
        assert isinstance(result, float)
        assert not math.isnan(result)
        assert not math.isinf(result)

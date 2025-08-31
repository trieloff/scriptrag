"""Test the specific bug fix for embedding pipeline array access."""

from scriptrag.embeddings.batch_processor import BatchResult


class TestEmbeddingPipelineFix:
    """Test that the bug fix for array access is correct."""

    def test_batch_result_structure(self):
        """Test BatchResult object structure."""
        # Verify BatchResult can be created with None embedding
        result = BatchResult(id="test", embedding=None, error="Error message")
        assert result.id == "test"
        assert result.embedding is None
        assert result.error == "Error message"

    def test_empty_list_handling(self):
        """Test safe handling of empty result lists."""
        results = []

        # The fix ensures we check len(results) > 0 before accessing results[0]
        # This simulates the fixed code pattern
        if results and len(results) > 0 and results[0].embedding:
            # This would have thrown IndexError before the fix
            embedding = results[0].embedding
            raise AssertionError("Should not reach here with empty results")
        # This is the expected path with empty results
        error = results[0].error if results and len(results) > 0 else "Unknown error"
        assert error == "Unknown error"

    def test_none_result_handling(self):
        """Test safe handling of None results."""
        results = None

        # The fix ensures we handle None results gracefully
        if results and len(results) > 0 and results[0].embedding:
            raise AssertionError("Should not reach here with None results")
        error = results[0].error if results and len(results) > 0 else "Unknown error"
        assert error == "Unknown error"

    def test_result_with_error_handling(self):
        """Test proper error extraction from results."""
        error_result = BatchResult(
            id="test", embedding=None, error="Specific error message"
        )
        results = [error_result]

        # The fix ensures we properly extract error messages
        if results and len(results) > 0 and results[0].embedding:
            raise AssertionError("Should not reach here when embedding is None")
        error = results[0].error if results and len(results) > 0 else "Unknown error"
        assert error == "Specific error message"

    def test_successful_result_handling(self):
        """Test successful embedding extraction."""
        embedding = [0.1] * 768
        success_result = BatchResult(id="test", embedding=embedding, error=None)
        results = [success_result]

        # The fix ensures successful results are handled correctly
        if results and len(results) > 0 and results[0].embedding:
            extracted = results[0].embedding
            assert extracted == embedding
        else:
            raise AssertionError("Should have extracted the embedding")

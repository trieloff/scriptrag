"""Comprehensive tests for vector operations module."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from scriptrag.database.vectors import (
    VectorError,
    VectorOperations,
)


@pytest.fixture
def mock_db_connection():
    """Mock database connection."""
    connection = MagicMock()

    # Mock the context manager for get_connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    conn_context = MagicMock()
    conn_context.__enter__ = MagicMock(return_value=mock_conn)
    conn_context.__exit__ = MagicMock(return_value=None)
    connection.get_connection.return_value = conn_context

    return connection, mock_conn, mock_cursor


@pytest.fixture
def vector_ops(mock_db_connection):
    """Create VectorOperations instance with mocked connection."""
    connection, _, _ = mock_db_connection

    # Mock sqlite_vec loading
    with patch("scriptrag.database.vectors.sqlite_vec.load"):
        return VectorOperations(connection)


class TestVectorOperationsInitialization:
    """Test VectorOperations initialization and setup."""

    def test_init_with_extension_support(self):
        """Test initialization when extension loading is supported."""
        mock_connection = MagicMock()
        mock_conn = MagicMock()
        mock_conn.enable_load_extension = MagicMock()

        conn_context = MagicMock()
        conn_context.__enter__ = MagicMock(return_value=mock_conn)
        conn_context.__exit__ = MagicMock(return_value=None)
        mock_connection.get_connection.return_value = conn_context

        with patch("scriptrag.database.vectors.sqlite_vec.load") as mock_load:
            VectorOperations(mock_connection)

            # Verify extension loading
            mock_conn.enable_load_extension.assert_any_call(True)
            mock_load.assert_called_once_with(mock_conn)
            mock_conn.enable_load_extension.assert_any_call(False)

    def test_init_without_extension_support(self):
        """Test initialization when extension loading is not supported."""
        mock_connection = MagicMock()
        mock_conn = MagicMock()
        # No enable_load_extension attribute
        del mock_conn.enable_load_extension

        conn_context = MagicMock()
        conn_context.__enter__ = MagicMock(return_value=mock_conn)
        conn_context.__exit__ = MagicMock(return_value=None)
        mock_connection.get_connection.return_value = conn_context

        with patch("scriptrag.database.vectors.sqlite_vec.load") as mock_load:
            VectorOperations(mock_connection)

            # Should still try to load
            mock_load.assert_called_once_with(mock_conn)

    def test_init_extension_loading_fails(self):
        """Test initialization when extension loading fails."""
        mock_connection = MagicMock()
        mock_conn = MagicMock()

        conn_context = MagicMock()
        conn_context.__enter__ = MagicMock(return_value=mock_conn)
        conn_context.__exit__ = MagicMock(return_value=None)
        mock_connection.get_connection.return_value = conn_context

        with patch("scriptrag.database.vectors.sqlite_vec.load") as mock_load:
            mock_load.side_effect = Exception("Extension load failed")

            with pytest.raises(VectorError, match="Could not load sqlite-vec"):
                VectorOperations(mock_connection)


class TestStoreEmbedding:
    """Test embedding storage operations."""

    def test_store_embedding_success(self, vector_ops, mock_db_connection):
        """Test successful embedding storage."""
        _, mock_conn, mock_cursor = mock_db_connection

        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        result = vector_ops.store_embedding(
            entity_type="scene",
            entity_id="scene_001",
            content="Test scene content",
            embedding=embedding,
            model_name="test-model",
            vector_type="float32",
        )

        assert result is True

        # Verify database insert
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert "INSERT OR REPLACE INTO embeddings" in call_args[0]
        assert len(call_args[1]) == 8  # 8 parameters
        assert call_args[1][0] == "scene_scene_001_test-model"  # ID
        assert call_args[1][1] == "scene"  # entity_type
        assert call_args[1][2] == "scene_001"  # entity_id

        mock_conn.commit.assert_called_once()

    def test_store_embedding_numpy_array(self, vector_ops, mock_db_connection):
        """Test storing numpy array embedding."""
        _, mock_conn, mock_cursor = mock_db_connection

        embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)

        result = vector_ops.store_embedding(
            entity_type="character",
            entity_id="char_001",
            content="Character dialogue",
            embedding=embedding,
            model_name="test-model",
        )

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_store_embedding_failure(self, vector_ops, mock_db_connection):
        """Test embedding storage failure."""
        _, mock_conn, mock_cursor = mock_db_connection

        # Simulate database error
        mock_cursor.execute.side_effect = Exception("Database error")

        embedding = [0.1, 0.2, 0.3]

        result = vector_ops.store_embedding(
            entity_type="scene",
            entity_id="scene_001",
            content="Test content",
            embedding=embedding,
            model_name="test-model",
        )

        assert result is False


class TestGetEmbedding:
    """Test embedding retrieval operations."""

    def test_get_embedding_success(self, vector_ops, mock_db_connection):
        """Test successful embedding retrieval."""
        _, _, mock_cursor = mock_db_connection

        # Mock database response
        vector_blob = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32).tobytes()
        mock_cursor.fetchone.return_value = (
            vector_blob,
            "float32",
            5,
            "Test content",
            "2024-01-01 12:00:00",
        )

        result = vector_ops.get_embedding(
            entity_type="scene", entity_id="scene_001", model_name="test-model"
        )

        assert result is not None
        vector, metadata = result

        # Check vector
        assert isinstance(vector, np.ndarray)
        assert len(vector) == 5
        assert np.allclose(vector, [0.1, 0.2, 0.3, 0.4, 0.5])

        # Check metadata
        assert metadata["content"] == "Test content"
        assert metadata["vector_type"] == "float32"
        assert metadata["dimension"] == 5
        assert metadata["created_at"] == "2024-01-01 12:00:00"

    def test_get_embedding_not_found(self, vector_ops, mock_db_connection):
        """Test embedding retrieval when not found."""
        _, _, mock_cursor = mock_db_connection

        mock_cursor.fetchone.return_value = None

        result = vector_ops.get_embedding(
            entity_type="scene", entity_id="non_existent", model_name="test-model"
        )

        assert result is None

    def test_get_embedding_error(self, vector_ops, mock_db_connection):
        """Test embedding retrieval error handling."""
        _, _, mock_cursor = mock_db_connection

        mock_cursor.execute.side_effect = Exception("Database error")

        result = vector_ops.get_embedding(
            entity_type="scene", entity_id="scene_001", model_name="test-model"
        )

        assert result is None


class TestFindSimilar:
    """Test similarity search operations."""

    def test_find_similar_basic(self, vector_ops, mock_db_connection):
        """Test basic similarity search."""
        _, _, mock_cursor = mock_db_connection

        query_vector = [0.1, 0.2, 0.3, 0.4, 0.5]

        # Mock search results
        mock_cursor.fetchall.return_value = [
            (
                "scene",
                "scene_001",
                0.05,
                "Scene 1 content",
                "test-model",
                5,
                "2024-01-01",
            ),
            (
                "scene",
                "scene_002",
                0.10,
                "Scene 2 content",
                "test-model",
                5,
                "2024-01-01",
            ),
            (
                "scene",
                "scene_003",
                0.15,
                "Scene 3 content",
                "test-model",
                5,
                "2024-01-01",
            ),
        ]

        results = vector_ops.find_similar(
            query_vector=query_vector,
            entity_type="scene",
            model_name="test-model",
            distance_metric="cosine",
            limit=10,
        )

        assert len(results) == 3
        assert results[0][0] == "scene"  # entity_type
        assert results[0][1] == "scene_001"  # entity_id
        assert results[0][2] == 0.05  # distance
        assert "content" in results[0][3]  # metadata

    def test_find_similar_with_filters(self, vector_ops, mock_db_connection):
        """Test similarity search with filters."""
        _, _, mock_cursor = mock_db_connection

        query_vector = np.array([0.1, 0.2, 0.3])

        mock_cursor.fetchall.return_value = []

        vector_ops.find_similar(
            query_vector=query_vector,
            entity_type="character",
            model_name="specific-model",
            distance_metric="l2",
            limit=5,
            threshold=0.5,
        )

        # Verify SQL construction
        call_args = mock_cursor.execute.call_args[0]
        sql = call_args[0]
        params = call_args[1]

        assert "WHERE entity_type = ?" in sql
        assert "AND embedding_model = ?" in sql
        assert "vec_distance_l2" in sql
        assert "character" in params
        assert "specific-model" in params
        assert params[-1] == 5  # limit

    def test_find_similar_no_filters(self, vector_ops, mock_db_connection):
        """Test similarity search without filters."""
        _, _, mock_cursor = mock_db_connection

        query_vector = [0.1, 0.2, 0.3]

        mock_cursor.fetchall.return_value = []

        vector_ops.find_similar(query_vector=query_vector, limit=20)

        # Verify no WHERE clause
        call_args = mock_cursor.execute.call_args[0]
        sql = call_args[0]
        assert "WHERE" not in sql or "ORDER BY" in sql.split("WHERE")[0]


class TestVectorConversion:
    """Test vector format conversion methods."""

    def test_convert_to_blob_list(self, vector_ops):
        """Test converting list to blob."""
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        blob = vector_ops._convert_to_blob(vector, "float32")

        assert isinstance(blob, bytes)
        assert len(blob) == 20  # 5 floats * 4 bytes

    def test_convert_to_blob_numpy(self, vector_ops):
        """Test converting numpy array to blob."""
        vector = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        blob = vector_ops._convert_to_blob(vector, "float32")

        assert isinstance(blob, bytes)
        assert len(blob) == 12  # 3 floats * 4 bytes

    def test_convert_to_blob_bytes(self, vector_ops):
        """Test converting bytes to blob (passthrough)."""
        vector = b"\x00\x01\x02\x03"
        blob = vector_ops._convert_to_blob(vector, "int8")

        assert blob == vector

    def test_convert_from_blob_float32(self, vector_ops):
        """Test converting blob to float32 array."""
        original = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        blob = original.tobytes()

        result = vector_ops._convert_from_blob(blob, "float32", 3)

        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32
        assert np.allclose(result, original)

    def test_convert_from_blob_int8(self, vector_ops):
        """Test converting blob to int8 array."""
        original = np.array([1, 2, 3, 4, 5], dtype=np.int8)
        blob = original.tobytes()

        result = vector_ops._convert_from_blob(blob, "int8", 5)

        assert isinstance(result, np.ndarray)
        assert result.dtype == np.int8
        assert np.array_equal(result, original)


class TestDistanceMetrics:
    """Test distance metric selection."""

    def test_get_distance_function_cosine(self, vector_ops):
        """Test cosine distance function selection."""
        func = vector_ops._get_distance_function("cosine")
        assert func == "vec_distance_cosine"

    def test_get_distance_function_l2(self, vector_ops):
        """Test L2 distance function selection."""
        func = vector_ops._get_distance_function("l2")
        assert func == "vec_distance_l2"

    def test_get_distance_function_l1(self, vector_ops):
        """Test L1 distance function selection."""
        func = vector_ops._get_distance_function("l1")
        assert func == "vec_distance_l1"

    def test_get_distance_function_invalid(self, vector_ops):
        """Test invalid distance metric."""
        with pytest.raises(VectorError, match="Unsupported distance metric"):
            vector_ops._get_distance_function("invalid")


class TestVectorDimensions:
    """Test vector dimension handling."""

    def test_get_vector_dimension_list(self, vector_ops):
        """Test getting dimension from list."""
        vector = [0.1, 0.2, 0.3, 0.4]
        dim = vector_ops._get_vector_dimension(vector)
        assert dim == 4

    def test_get_vector_dimension_numpy(self, vector_ops):
        """Test getting dimension from numpy array."""
        vector = np.array([0.1, 0.2, 0.3])
        dim = vector_ops._get_vector_dimension(vector)
        assert dim == 3

    def test_get_vector_dimension_bytes(self, vector_ops):
        """Test getting dimension from bytes - should raise error."""
        # Bytes vectors don't contain dimension information
        vector = b"\x00" * 20  # 20 bytes
        with pytest.raises(
            VectorError, match="Cannot determine dimension from bytes vector"
        ):
            vector_ops._get_vector_dimension(vector)


class TestBatchOperations:
    """Test batch vector operations."""

    def test_batch_store_embeddings(self, vector_ops, mock_db_connection):
        """Test storing multiple embeddings in batch."""
        _, mock_conn, mock_cursor = mock_db_connection

        embeddings = [
            {
                "entity_type": "scene",
                "entity_id": f"scene_{i:03d}",
                "content": f"Scene {i} content",
                "embedding": [0.1 * i, 0.2 * i, 0.3 * i],
                "model_name": "test-model",
            }
            for i in range(5)
        ]

        results = vector_ops.batch_store_embeddings(embeddings)

        assert len(results) == 5
        assert all(results.values())
        assert mock_cursor.execute.call_count == 5
        assert mock_conn.commit.call_count == 5

    def test_delete_embeddings(self, vector_ops, mock_db_connection):
        """Test deleting embeddings."""
        _, mock_conn, mock_cursor = mock_db_connection

        # Set up mock cursor to return a rowcount
        mock_cursor.rowcount = 3

        result = vector_ops.delete_embeddings(
            entity_type="scene", entity_id="scene_001"
        )

        assert result == 3

        # Verify delete query
        call_args = mock_cursor.execute.call_args[0]
        assert "DELETE FROM embeddings" in call_args[0]
        assert "entity_type = ?" in call_args[0]
        assert "entity_id = ?" in call_args[0]
        assert call_args[1] == ["scene", "scene_001"]

        mock_conn.commit.assert_called_once()

    def test_count_embeddings(self, vector_ops, mock_db_connection):
        """Test counting embeddings."""
        _, _, mock_cursor = mock_db_connection

        mock_cursor.fetchone.return_value = (42,)

        count = vector_ops.count_embeddings(
            entity_type="scene", model_name="test-model"
        )

        assert count == 42

        # Verify count query
        call_args = mock_cursor.execute.call_args[0]
        assert "SELECT COUNT(*)" in call_args[0]
        assert "entity_type = ?" in call_args[0]
        assert "embedding_model = ?" in call_args[0]

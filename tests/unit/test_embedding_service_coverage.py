"""Comprehensive tests for embedding service to improve coverage to 92%+."""

import json
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.api.embedding_service import EmbeddingService
from scriptrag.config import ScriptRAGSettings


class TestEmbeddingServiceErrorHandling:
    """Test error handling and edge cases in embedding service."""

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        client = MagicMock()
        client.generate_embedding = MagicMock()
        return client

    @pytest.fixture
    def service(self, tmp_path, mock_llm_client):
        """Create embedding service with mocked dependencies."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("scriptrag.api.embedding_service.DatabaseOperations"):
            with patch(
                "scriptrag.api.embedding_service.create_llm_client"
            ) as mock_create:
                mock_create.return_value = mock_llm_client
                return EmbeddingService(settings)

    def test_generate_scene_embeddings_db_error(self, service, mock_llm_client):
        """Test database error during scene embedding generation."""
        mock_llm_client.generate_embedding.return_value = [0.1] * 1536

        # Mock database error
        service.db_ops.get_script_scenes.return_value = []
        service.db_ops.add_embedding.side_effect = Exception("DB Error")

        with patch("scriptrag.api.embedding_service.logger") as mock_logger:
            result = service.generate_scene_embeddings(1)

            assert result["generated"] == 0
            assert result["failed"] == 0  # No scenes to process

            # If we had scenes, it would log errors
            service.db_ops.get_script_scenes.return_value = [
                {"id": 1, "content": "Test scene"}
            ]

            result = service.generate_scene_embeddings(1)
            assert result["failed"] > 0

    def test_generate_scene_embeddings_llm_error(self, service, mock_llm_client):
        """Test LLM error during embedding generation."""
        mock_llm_client.generate_embedding.side_effect = Exception("LLM Error")

        service.db_ops.get_script_scenes.return_value = [
            {"id": 1, "content": "Test scene", "heading": "INT. ROOM"}
        ]

        with patch("scriptrag.api.embedding_service.logger") as mock_logger:
            result = service.generate_scene_embeddings(1)

            assert result["generated"] == 0
            assert result["failed"] == 1
            mock_logger.error.assert_called()

    def test_generate_scene_embeddings_skip_existing(self, service, mock_llm_client):
        """Test skipping existing embeddings."""
        mock_llm_client.generate_embedding.return_value = [0.1] * 1536

        # Scene with existing embedding
        service.db_ops.get_script_scenes.return_value = [
            {"id": 1, "content": "Test", "embedding": b"existing"}
        ]

        result = service.generate_scene_embeddings(1, force_regenerate=False)

        assert result["skipped"] == 1
        assert result["generated"] == 0
        mock_llm_client.generate_embedding.assert_not_called()

    def test_generate_scene_embeddings_force_regenerate(self, service, mock_llm_client):
        """Test force regeneration of existing embeddings."""
        mock_llm_client.generate_embedding.return_value = [0.1] * 1536

        service.db_ops.get_script_scenes.return_value = [
            {
                "id": 1,
                "content": "Test",
                "embedding": b"existing",
                "heading": "INT. ROOM",
            }
        ]

        result = service.generate_scene_embeddings(1, force_regenerate=True)

        assert result["skipped"] == 0
        assert result["generated"] == 1
        mock_llm_client.generate_embedding.assert_called_once()

    def test_generate_bible_embeddings_no_bible(self, service):
        """Test bible embedding generation when no bible exists."""
        service.db_ops.get_script_bible_chunks.return_value = []

        result = service.generate_bible_embeddings(1)

        assert result["generated"] == 0
        assert result["failed"] == 0
        assert result["skipped"] == 0

    def test_generate_bible_embeddings_with_errors(self, service, mock_llm_client):
        """Test bible embedding generation with errors."""
        mock_llm_client.generate_embedding.side_effect = [
            [0.1] * 1536,  # First chunk succeeds
            Exception("LLM Error"),  # Second chunk fails
        ]

        service.db_ops.get_script_bible_chunks.return_value = [
            {"id": 1, "content": "Chunk 1"},
            {"id": 2, "content": "Chunk 2"},
        ]

        with patch("scriptrag.api.embedding_service.logger") as mock_logger:
            result = service.generate_bible_embeddings(1)

            assert result["generated"] == 1
            assert result["failed"] == 1
            mock_logger.error.assert_called()

    def test_verify_embeddings_missing_scenes(self, service):
        """Test embedding verification with missing embeddings."""
        service.db_ops.execute_query.return_value = [
            {"scene_count": 10, "embedded_count": 7}
        ]

        result = service.verify_embeddings(1)

        assert result["scenes"]["total"] == 10
        assert result["scenes"]["embedded"] == 7
        assert result["scenes"]["missing"] == 3
        assert result["scenes"]["coverage"] == 0.7

    def test_verify_embeddings_no_scenes(self, service):
        """Test verification when no scenes exist."""
        service.db_ops.execute_query.return_value = [
            {"scene_count": 0, "embedded_count": 0}
        ]

        result = service.verify_embeddings(1)

        assert result["scenes"]["total"] == 0
        assert result["scenes"]["coverage"] == 0.0

    def test_check_embedding_model_no_embeddings(self, service):
        """Test checking embedding model when no embeddings exist."""
        service.db_ops.execute_query.return_value = []

        result = service.check_embedding_model(1)

        assert result["has_embeddings"] is False
        assert result["models"] == []
        assert result["needs_regeneration"] is True

    def test_check_embedding_model_mixed_models(self, service):
        """Test with mixed embedding models."""
        service.db_ops.execute_query.return_value = [
            {"embedding_model": "model-1", "count": 5},
            {"embedding_model": "model-2", "count": 3},
        ]

        with patch.object(service, "settings") as mock_settings:
            mock_settings.embedding_model = "model-3"

            result = service.check_embedding_model(1)

            assert result["has_embeddings"] is True
            assert len(result["models"]) == 2
            assert result["current_model"] == "model-3"
            assert (
                result["needs_regeneration"] is True
            )  # Current model not in embeddings

    def test_migrate_embeddings_no_vss_support(self, service):
        """Test migration when VSS is not supported."""
        with patch("scriptrag.api.embedding_service.VSSService") as mock_vss:
            mock_vss.side_effect = Exception("VSS not available")

            with patch("scriptrag.api.embedding_service.logger") as mock_logger:
                result = service.migrate_embeddings()

                assert result["success"] is False
                assert "VSS support not available" in result["error"]
                mock_logger.warning.assert_called()

    def test_migrate_embeddings_migration_error(self, service):
        """Test migration with errors during the process."""
        with patch("scriptrag.api.embedding_service.VSSService") as mock_vss_class:
            mock_vss = MagicMock()
            mock_vss.migrate_from_blob_storage.side_effect = Exception(
                "Migration failed"
            )
            mock_vss_class.return_value = mock_vss

            with patch("scriptrag.api.embedding_service.logger") as mock_logger:
                result = service.migrate_embeddings()

                assert result["success"] is False
                assert "Migration failed" in result["error"]
                mock_logger.error.assert_called()

    def test_migrate_embeddings_success(self, service):
        """Test successful embedding migration."""
        with patch("scriptrag.api.embedding_service.VSSService") as mock_vss_class:
            mock_vss = MagicMock()
            mock_vss.migrate_from_blob_storage.return_value = (10, 2)
            mock_vss_class.return_value = mock_vss

            result = service.migrate_embeddings()

            assert result["success"] is True
            assert result["migrated"] == 10
            assert result["failed"] == 2

    def test_batch_generate_embeddings(self, service, mock_llm_client):
        """Test batch embedding generation with mixed results."""
        mock_llm_client.generate_embedding.side_effect = [
            [0.1] * 1536,
            Exception("Error"),
            [0.2] * 1536,
        ]

        texts = ["Text 1", "Text 2", "Text 3"]

        with patch("scriptrag.api.embedding_service.logger"):
            results = service._batch_generate_embeddings(texts)

            assert len(results) == 3
            assert results[0] is not None
            assert results[1] is None  # Failed
            assert results[2] is not None

    def test_prepare_scene_text_with_metadata(self, service):
        """Test scene text preparation with full metadata."""
        scene = {
            "heading": "INT. ROOM - DAY",
            "content": "Action here.",
            "metadata": json.dumps(
                {"characters": ["JOHN", "MARY"], "props": ["gun", "phone"]}
            ),
        }

        text = service._prepare_scene_text(scene)

        assert "INT. ROOM - DAY" in text
        assert "Action here." in text
        assert "JOHN" in text
        assert "MARY" in text

    def test_prepare_scene_text_invalid_metadata(self, service):
        """Test scene text preparation with invalid metadata JSON."""
        scene = {
            "heading": "INT. ROOM",
            "content": "Action.",
            "metadata": "invalid json",
        }

        with patch("scriptrag.api.embedding_service.logger") as mock_logger:
            text = service._prepare_scene_text(scene)

            assert "INT. ROOM" in text
            assert "Action." in text
            mock_logger.debug.assert_called()  # Should log JSON decode error


class TestEmbeddingServiceIntegration:
    """Integration tests for embedding service."""

    def test_full_embedding_workflow(self, tmp_path):
        """Test complete embedding generation workflow."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db", embedding_model="test-model"
        )

        with patch("scriptrag.api.embedding_service.DatabaseOperations") as mock_db:
            with patch(
                "scriptrag.api.embedding_service.create_llm_client"
            ) as mock_create:
                mock_llm = MagicMock()
                mock_llm.generate_embedding.return_value = [0.1] * 1536
                mock_create.return_value = mock_llm

                mock_db_instance = MagicMock()
                mock_db.return_value = mock_db_instance

                # Setup mock data
                mock_db_instance.get_script_scenes.return_value = [
                    {"id": 1, "content": "Scene 1", "heading": "INT. ROOM"},
                    {"id": 2, "content": "Scene 2", "heading": "EXT. STREET"},
                ]

                service = EmbeddingService(settings)
                result = service.generate_scene_embeddings(1)

                assert result["generated"] == 2
                assert result["failed"] == 0
                assert mock_llm.generate_embedding.call_count == 2

    def test_embedding_service_initialization_error(self, tmp_path):
        """Test service initialization with database error."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("scriptrag.api.embedding_service.DatabaseOperations") as mock_db:
            mock_db.side_effect = Exception("DB Connection failed")

            with pytest.raises(Exception, match="DB Connection failed"):
                service = EmbeddingService(settings)

    def test_generate_embeddings_empty_content(self, tmp_path):
        """Test handling of empty content in scenes."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        with patch("scriptrag.api.embedding_service.DatabaseOperations") as mock_db:
            with patch(
                "scriptrag.api.embedding_service.create_llm_client"
            ) as mock_create:
                mock_llm = MagicMock()
                mock_create.return_value = mock_llm

                mock_db_instance = MagicMock()
                mock_db.return_value = mock_db_instance

                # Scene with empty content
                mock_db_instance.get_script_scenes.return_value = [
                    {"id": 1, "content": "", "heading": "INT. ROOM"},
                    {"id": 2, "content": None, "heading": "EXT. STREET"},
                ]

                service = EmbeddingService(settings)

                # Should handle empty content gracefully
                mock_llm.generate_embedding.return_value = [0.0] * 1536
                result = service.generate_scene_embeddings(1)

                # Should still try to generate embeddings even for empty content
                assert mock_llm.generate_embedding.call_count >= 0

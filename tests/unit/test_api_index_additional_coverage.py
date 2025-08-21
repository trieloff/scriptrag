"""Additional tests for index.py to improve coverage."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

from scriptrag.api.index import IndexCommand
from scriptrag.api.index_bible_aliases import IndexBibleAliasApplicator
from scriptrag.api.index_embeddings import IndexEmbeddingProcessor
from scriptrag.config import ScriptRAGSettings
from scriptrag.parser import Scene


class TestIndexCommandAdditionalCoverage:
    """Additional tests to cover missing lines in index.py."""

    @pytest.mark.asyncio
    async def test_filter_scripts_for_indexing_existing_script(self, tmp_path):
        """Test filtering when script already exists in database."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        # Mock database operations
        mock_db_ops = MagicMock()
        mock_existing_script = MagicMock()
        mock_existing_script.metadata = {"last_indexed": "2024-01-01T00:00:00"}
        mock_db_ops.get_existing_script.return_value = mock_existing_script

        # Mock connection
        mock_conn = MagicMock()
        mock_db_ops.transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        # Create test script metadata
        from scriptrag.api.list import FountainMetadata

        scripts = [FountainMetadata(file_path=Path("test.fountain"), title="Test")]

        result = await cmd._filter_scripts_for_indexing(scripts)

        # Should skip already indexed script
        assert len(result) == 0
        mock_db_ops.get_existing_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_scripts_for_indexing_no_last_indexed(self, tmp_path):
        """Test filtering when existing script has no last_indexed metadata."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        mock_db_ops = MagicMock()
        mock_existing_script = MagicMock()
        mock_existing_script.metadata = {}  # No last_indexed
        mock_db_ops.get_existing_script.return_value = mock_existing_script

        mock_conn = MagicMock()
        mock_db_ops.transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        from scriptrag.api.list import FountainMetadata

        scripts = [FountainMetadata(file_path=Path("test.fountain"), title="Test")]

        result = await cmd._filter_scripts_for_indexing(scripts)

        # Should include script for indexing since no last_indexed
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_apply_bible_aliases_success(self, tmp_path):
        """Test successful application of Bible aliases to characters."""
        # Mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock script metadata with Bible characters
        bible_metadata = {
            "bible.characters": {
                "characters": [
                    {"canonical": "JANE SMITH", "aliases": ["JANE", "MS. SMITH"]}
                ]
            }
        }
        mock_cursor.fetchone.return_value = (json.dumps(bible_metadata),)

        # Mock character map
        character_map = {"JANE SMITH": 1, "BOB": 2}

        await IndexBibleAliasApplicator.apply_bible_aliases(
            mock_conn, script_id=1, character_map=character_map
        )

        # Should update character with aliases
        mock_cursor.execute.assert_any_call(
            "SELECT metadata FROM scripts WHERE id = ?", (1,)
        )
        mock_cursor.execute.assert_any_call(
            "UPDATE characters SET aliases = ? WHERE id = ?",
            ('["JANE", "MS. SMITH"]', 1),
        )

    @pytest.mark.asyncio
    async def test_apply_bible_aliases_no_metadata(self, tmp_path):
        """Test Bible alias application when no script metadata exists."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # No metadata row

        await IndexBibleAliasApplicator.apply_bible_aliases(
            mock_conn, script_id=1, character_map={}
        )

        # Should handle gracefully and not attempt updates
        mock_cursor.execute.assert_called_once_with(
            "SELECT metadata FROM scripts WHERE id = ?", (1,)
        )

    @pytest.mark.asyncio
    async def test_apply_bible_aliases_invalid_data(self, tmp_path):
        """Test Bible alias application with invalid character data."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock metadata with invalid bible characters
        bible_metadata = {
            "bible.characters": {
                "characters": [
                    {"canonical": "", "aliases": []},  # Empty canonical
                    {"canonical": "JANE", "aliases": []},  # No aliases
                    {"no_canonical": "field"},  # Missing canonical field
                ]
            }
        }
        mock_cursor.fetchone.return_value = (json.dumps(bible_metadata),)

        character_map = {"JANE": 1}

        await IndexBibleAliasApplicator.apply_bible_aliases(
            mock_conn, script_id=1, character_map=character_map
        )

        # Should handle invalid data gracefully - no UPDATE calls made
        update_calls = [
            call
            for call in mock_cursor.execute.call_args_list
            if "UPDATE characters" in str(call)
        ]
        assert len(update_calls) == 0

    @pytest.mark.asyncio
    async def test_apply_bible_aliases_exception(self, tmp_path):
        """Test Bible alias application with database exception."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.side_effect = Exception("DB Error")

        # Should handle exception gracefully
        await IndexBibleAliasApplicator.apply_bible_aliases(
            mock_conn, script_id=1, character_map={}
        )

        # Exception should be caught and logged, not re-raised

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_from_lfs_file(self, tmp_path):
        """Test processing scene embeddings from existing LFS file."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")

        # Mock database operations
        mock_db_ops = MagicMock()

        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops, embedding_service=None, generate_embeddings=False
        )

        # Create mock embedding file
        embedding_file = tmp_path / "embeddings" / "scene_1.npy"
        embedding_file.parent.mkdir(exist_ok=True)
        test_embedding = np.array([0.1, 0.2, 0.3])
        np.save(embedding_file, test_embedding)

        # Mock scene with embedding metadata
        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="hash123",
            boneyard_metadata={
                "analyzers": {
                    "scene_embeddings": {
                        "result": {
                            "embedding_path": str(embedding_file.relative_to(tmp_path)),
                            "model": "test-model",
                        }
                    }
                }
            },
        )

        # Mock connection and git repo
        mock_conn = MagicMock()

        with patch("git.Repo") as mock_repo_class:
            mock_repo = mock_repo_class.return_value
            mock_repo.working_dir = str(tmp_path)

            await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

            # Should call upsert_embedding with loaded embedding data
            mock_db_ops.upsert_embedding.assert_called_once()
            call_args = mock_db_ops.upsert_embedding.call_args
            assert call_args[1]["entity_type"] == "scene"
            assert call_args[1]["entity_id"] == 1
            assert call_args[1]["embedding_model"] == "test-model"

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_lfs_file_missing(self, tmp_path):
        """Test processing scene embeddings when LFS file doesn't exist locally."""
        # Mock database operations
        mock_db_ops = MagicMock()

        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops, embedding_service=None, generate_embeddings=False
        )

        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="hash123",
            boneyard_metadata={
                "analyzers": {
                    "scene_embeddings": {
                        "result": {
                            "embedding_path": "missing_file.npy",
                            "model": "test-model",
                        }
                    }
                }
            },
        )

        mock_conn = MagicMock()

        with patch("git.Repo") as mock_repo_class:
            mock_repo = mock_repo_class.return_value
            mock_repo.working_dir = str(tmp_path)

            await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

            # Should store reference path without embedding data
            mock_db_ops.upsert_embedding.assert_called_once()
            call_args = mock_db_ops.upsert_embedding.call_args
            assert call_args[1]["embedding_path"] == "missing_file.npy"
            assert (
                "embedding_data" not in call_args[1]
                or call_args[1]["embedding_data"] is None
            )

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_error_in_result(self, tmp_path):
        """Test processing scene embeddings when result contains error."""
        # Mock database operations
        mock_db_ops = MagicMock()

        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops, embedding_service=None, generate_embeddings=False
        )

        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="hash123",
            boneyard_metadata={
                "analyzers": {
                    "scene_embeddings": {
                        "result": {
                            "error": "Embedding failed",
                            "embedding_path": "test.npy",
                        }
                    }
                }
            },
        )

        mock_conn = MagicMock()

        await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

        # Should not process embeddings when error is present
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_git_exception(self, tmp_path):
        """Test handling of git/embedding processing exceptions."""
        # Mock database operations
        mock_db_ops = MagicMock()

        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops, embedding_service=None, generate_embeddings=False
        )

        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="hash123",
            boneyard_metadata={
                "analyzers": {
                    "scene_embeddings": {
                        "result": {"embedding_path": "test.npy", "model": "test-model"}
                    }
                }
            },
        )

        mock_conn = MagicMock()

        with patch("git.Repo", side_effect=Exception("Git error")):
            # Should handle exception gracefully
            await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

            # No exception should be raised

    @pytest.mark.asyncio
    async def test_generate_new_embedding_success(self, tmp_path):
        """Test successful generation of new embeddings."""
        # Mock database operations
        mock_db_ops = MagicMock()

        # Mock embedding service
        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_scene_embedding.return_value = np.array(
            [0.1, 0.2, 0.3]
        )
        mock_embedding_service.save_embedding_to_lfs.return_value = Path(
            "embedding.npy"
        )
        mock_embedding_service.encode_embedding_for_db.return_value = b"encoded"
        mock_embedding_service.default_model = "test-model"

        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops,
            embedding_service=mock_embedding_service,
            generate_embeddings=True,
        )

        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="hash123",
        )

        mock_conn = MagicMock()

        await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

        # Should generate and store new embedding
        mock_embedding_service.generate_scene_embedding.assert_called_once_with(
            "Test content", "INT. TEST - DAY"
        )
        mock_db_ops.upsert_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_new_embedding_failure(self, tmp_path):
        """Test handling of embedding generation failures."""
        # Mock database operations
        mock_db_ops = MagicMock()

        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_scene_embedding.side_effect = Exception(
            "Generation failed"
        )

        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops,
            embedding_service=mock_embedding_service,
            generate_embeddings=True,
        )

        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="hash123",
        )

        mock_conn = MagicMock()

        # Should handle exception gracefully
        await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No exception should be raised

    @pytest.mark.asyncio
    async def test_discover_scripts_with_boneyard_filter(self, tmp_path):
        """Test script discovery with boneyard filter enabled."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            skip_boneyard_filter=False,  # Enable filtering
        )
        cmd = IndexCommand(settings=settings)

        # Mock script lister
        from scriptrag.api.list import FountainMetadata

        all_scripts = [
            FountainMetadata(
                file_path=Path("with_boneyard.fountain"), has_boneyard=True
            ),
            FountainMetadata(
                file_path=Path("without_boneyard.fountain"), has_boneyard=False
            ),
        ]

        cmd.lister.list_scripts = MagicMock(return_value=all_scripts)

        result = await cmd._discover_scripts(None, True)

        # Should only return scripts with boneyard metadata
        assert len(result) == 1
        assert result[0].file_path == Path("with_boneyard.fountain")

    @pytest.mark.asyncio
    async def test_discover_scripts_skip_boneyard_filter(self, tmp_path):
        """Test script discovery with boneyard filter disabled."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            skip_boneyard_filter=True,  # Skip filtering
        )
        cmd = IndexCommand(settings=settings)

        from scriptrag.api.list import FountainMetadata

        all_scripts = [
            FountainMetadata(
                file_path=Path("with_boneyard.fountain"), has_boneyard=True
            ),
            FountainMetadata(
                file_path=Path("without_boneyard.fountain"), has_boneyard=False
            ),
        ]

        cmd.lister.list_scripts = MagicMock(return_value=all_scripts)

        result = await cmd._discover_scripts(None, True)

        # Should return all scripts regardless of boneyard metadata
        assert len(result) == 2

"""Additional tests for API index module to improve coverage."""

from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

from scriptrag.api.duplicate_handler import DuplicateStrategy
from scriptrag.api.index import IndexCommand
from scriptrag.api.list import FountainMetadata
from scriptrag.config import ScriptRAGSettings
from scriptrag.parser import Scene


class TestIndexCommandCoverage:
    """Tests for IndexCommand to improve coverage."""

    @pytest.mark.asyncio
    async def test_discover_scripts_permission_error(self, tmp_path):
        """Test _discover_scripts handles permission errors."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create a test script file
        script_path = tmp_path / "script.fountain"
        script_path.write_text("/* SCRIPTRAG-META-START\n{}\nSCRIPTRAG-META-END */")

        mock_scripts = [FountainMetadata(file_path=script_path, title="Test Script")]

        with (
            patch.object(indexer.lister, "list_scripts", return_value=mock_scripts),
            # Mock file operations to raise PermissionError
            patch("pathlib.Path.stat", side_effect=PermissionError("Access denied")),
        ):
            result = await indexer._discover_scripts(tmp_path, recursive=True)

            # Should handle permission error gracefully and skip file
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_discover_scripts_unicode_decode_error(self, tmp_path):
        """Test _discover_scripts handles UnicodeDecodeError."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create a test script file
        script_path = tmp_path / "script.fountain"
        script_path.write_bytes(b"\x80\x81\x82")  # Invalid UTF-8

        mock_scripts = [FountainMetadata(file_path=script_path, title="Test Script")]

        with patch.object(indexer.lister, "list_scripts", return_value=mock_scripts):
            result = await indexer._discover_scripts(tmp_path, recursive=True)

            # Should handle decode error gracefully and skip file
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_discover_scripts_os_error(self, tmp_path):
        """Test _discover_scripts handles OSError."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create a test script file
        script_path = tmp_path / "script.fountain"
        script_path.write_text("/* SCRIPTRAG-META-START\n{}\nSCRIPTRAG-META-END */")

        mock_scripts = [FountainMetadata(file_path=script_path, title="Test Script")]

        with (
            patch.object(indexer.lister, "list_scripts", return_value=mock_scripts),
            # Mock file operations to raise OSError
            patch("pathlib.Path.stat", side_effect=OSError("Disk error")),
        ):
            result = await indexer._discover_scripts(tmp_path, recursive=True)

            # Should handle OS error gracefully and skip file
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_discover_scripts_unexpected_error(self, tmp_path):
        """Test _discover_scripts handles unexpected errors."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create a test script file
        script_path = tmp_path / "script.fountain"
        script_path.write_text("/* SCRIPTRAG-META-START\n{}\nSCRIPTRAG-META-END */")

        mock_scripts = [FountainMetadata(file_path=script_path, title="Test Script")]

        with (
            patch.object(indexer.lister, "list_scripts", return_value=mock_scripts),
            # Mock file operations to raise unexpected error
            patch("pathlib.Path.stat", side_effect=ValueError("Unexpected")),
        ):
            result = await indexer._discover_scripts(tmp_path, recursive=True)

            # Should handle unexpected error gracefully and skip file
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_no_metadata(self):
        """Test _process_scene_embeddings with no boneyard metadata."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create scene without boneyard metadata
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="Scene content",
            original_text="Original text",
            content_hash="hash123",
            dialogue_lines=[],
            action_lines=[],
            boneyard_metadata=None,
        )

        mock_conn = Mock()

        # Should return early without processing
        await indexer._process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No database operations should be called
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_no_analyzers(self):
        """Test _process_scene_embeddings with no analyzers in metadata."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create scene with empty boneyard metadata
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="Scene content",
            original_text="Original text",
            content_hash="hash123",
            dialogue_lines=[],
            action_lines=[],
            boneyard_metadata={},
        )

        mock_conn = Mock()

        # Should return early without processing
        await indexer._process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No database operations should be called
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_no_embedding_data(self):
        """Test _process_scene_embeddings with no embedding data."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create scene with analyzers but no scene_embeddings
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="Scene content",
            original_text="Original text",
            content_hash="hash123",
            dialogue_lines=[],
            action_lines=[],
            boneyard_metadata={"analyzers": {"other_analyzer": {}}},
        )

        mock_conn = Mock()

        # Should return early without processing
        await indexer._process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No database operations should be called
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_no_result(self):
        """Test _process_scene_embeddings with no result data."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create scene with embedding data but no result
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="Scene content",
            original_text="Original text",
            content_hash="hash123",
            dialogue_lines=[],
            action_lines=[],
            boneyard_metadata={"analyzers": {"scene_embeddings": {}}},
        )

        mock_conn = Mock()

        # Should return early without processing
        await indexer._process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No database operations should be called
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_with_error(self):
        """Test _process_scene_embeddings with error in result."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create scene with embedding error
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="Scene content",
            original_text="Original text",
            content_hash="hash123",
            dialogue_lines=[],
            action_lines=[],
            boneyard_metadata={
                "analyzers": {
                    "scene_embeddings": {
                        "result": {"error": "Failed to generate embedding"}
                    }
                }
            },
        )

        mock_conn = Mock()

        # Should return early due to error
        await indexer._process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No database operations should be called
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_no_embedding_path(self):
        """Test _process_scene_embeddings with no embedding path."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create scene with embedding result but no path
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="Scene content",
            original_text="Original text",
            content_hash="hash123",
            dialogue_lines=[],
            action_lines=[],
            boneyard_metadata={
                "analyzers": {"scene_embeddings": {"result": {"model": "test-model"}}}
            },
        )

        mock_conn = Mock()

        # Should return early without embedding path
        await indexer._process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No database operations should be called
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_file_exists(self, tmp_path):
        """Test _process_scene_embeddings with existing embedding file."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create embedding file
        embedding_path = "embeddings/test_hash.npy"
        full_path = tmp_path / embedding_path
        full_path.parent.mkdir(parents=True)
        test_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        np.save(full_path, test_embedding)

        # Create scene with embedding result
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="Scene content",
            original_text="Original text",
            content_hash="hash123",
            dialogue_lines=[],
            action_lines=[],
            boneyard_metadata={
                "analyzers": {
                    "scene_embeddings": {
                        "result": {
                            "embedding_path": embedding_path,
                            "model": "test-model",
                        }
                    }
                }
            },
        )

        mock_conn = Mock()

        with patch("git.Repo") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.working_dir = str(tmp_path)
            mock_repo_class.return_value = mock_repo

            await indexer._process_scene_embeddings(mock_conn, scene, scene_id=1)

            # Should store embedding in database
            mock_db_ops.upsert_embedding.assert_called_once()
            call_args = mock_db_ops.upsert_embedding.call_args

            # Check positional args
            assert call_args[0][0] == mock_conn

            # Check keyword arguments
            kwargs = call_args[1]
            assert kwargs["entity_type"] == "scene"
            assert kwargs["entity_id"] == 1
            assert kwargs["embedding_model"] == "test-model"
            assert kwargs["embedding_path"] == embedding_path

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_file_not_exists(self, tmp_path):
        """Test _process_scene_embeddings with non-existing embedding file."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create scene with embedding result but file doesn't exist
        embedding_path = "embeddings/nonexistent.npy"
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="Scene content",
            original_text="Original text",
            content_hash="hash123",
            dialogue_lines=[],
            action_lines=[],
            boneyard_metadata={
                "analyzers": {
                    "scene_embeddings": {
                        "result": {
                            "embedding_path": embedding_path,
                            "model": "test-model",
                        }
                    }
                }
            },
        )

        mock_conn = Mock()

        with patch("git.Repo") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.working_dir = str(tmp_path)
            mock_repo_class.return_value = mock_repo

            await indexer._process_scene_embeddings(mock_conn, scene, scene_id=1)

            # Should store reference without data
            mock_db_ops.upsert_embedding.assert_called_once()
            call_args = mock_db_ops.upsert_embedding.call_args

            # Check positional args - first should be conn
            assert call_args[0][0] == mock_conn

            # Check keyword arguments
            kwargs = call_args[1]
            assert kwargs["entity_type"] == "scene"
            assert kwargs["entity_id"] == 1
            assert kwargs["embedding_model"] == "test-model"
            assert kwargs["embedding_path"] == embedding_path
            assert kwargs.get("embedding_data") is None

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_processing_error(self):
        """Test _process_scene_embeddings with processing error."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create scene with embedding result
        embedding_path = "embeddings/test.npy"
        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="Scene content",
            original_text="Original text",
            content_hash="hash123",
            dialogue_lines=[],
            action_lines=[],
            boneyard_metadata={
                "analyzers": {
                    "scene_embeddings": {
                        "result": {
                            "embedding_path": embedding_path,
                            "model": "test-model",
                        }
                    }
                }
            },
        )

        mock_conn = Mock()

        with patch("git.Repo", side_effect=Exception("Git error")):
            # Should handle error gracefully
            await indexer._process_scene_embeddings(mock_conn, scene, scene_id=1)

            # No database operations should be called due to error
            mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_scene_without_file_path(self, tmp_path):
        """Test _process_scene_embeddings with scene that has no file_path attribute."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create scene without file_path attribute
        scene = Mock()
        scene.boneyard_metadata = {
            "analyzers": {
                "scene_embeddings": {
                    "result": {
                        "embedding_path": "embeddings/test.npy",
                        "model": "test-model",
                    }
                }
            }
        }
        # Remove file_path attribute so hasattr returns False
        del scene.file_path

        mock_conn = Mock()

        with patch("git.Repo") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.working_dir = str(tmp_path)
            mock_repo_class.return_value = mock_repo

            await indexer._process_scene_embeddings(mock_conn, scene, scene_id=1)

            # Should use current directory "." for repo search
            mock_repo_class.assert_called_once_with(".", search_parent_directories=True)

    @pytest.mark.asyncio
    async def test_index_single_script_existing_content(self, tmp_path):
        """Test _index_single_script when re-indexing existing content."""
        settings = ScriptRAGSettings(database_path=tmp_path / "test.db")
        mock_db_ops = Mock()

        # Setup transaction context manager
        mock_conn = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_db_ops.transaction.return_value = mock_context

        indexer = IndexCommand(settings, mock_db_ops)

        # Create test script
        from scriptrag.parser import Dialogue, Scene, Script

        scene = Scene(
            number=1,
            heading="INT. ROOM - DAY",
            content="Scene content",
            original_text="Original text",
            content_hash="hash123",
            dialogue_lines=[Dialogue(character="ALICE", text="Hello")],
            action_lines=["Action line"],
        )

        script = Script(
            title="Test Script",
            author="Test Author",
            scenes=[scene],
        )

        # Mock existing script and scene with content change
        existing_script = Mock()
        existing_script.id = 1
        mock_db_ops.get_existing_script.return_value = existing_script
        mock_db_ops.upsert_script.return_value = 1
        mock_db_ops.upsert_scene.return_value = (1, True)  # content_changed=True
        mock_db_ops.upsert_characters.return_value = {"ALICE": 1}
        mock_db_ops.insert_dialogues.return_value = 1
        mock_db_ops.insert_actions.return_value = 1
        mock_db_ops.get_script_stats.return_value = {
            "scenes": 1,
            "characters": 1,
            "dialogues": 1,
            "actions": 1,
        }

        with patch.object(indexer.parser, "parse_file", return_value=script):
            result = await indexer._index_single_script(
                Path("test.fountain"),
                dry_run=False,
                duplicate_strategy=DuplicateStrategy.ERROR,
            )

        # Should always clear existing data when updating
        mock_db_ops.clear_script_data.assert_called_once()
        # Should clear scene content when updating
        mock_db_ops.clear_scene_content.assert_called_once()
        assert result.indexed
        assert result.updated

    @pytest.mark.asyncio
    async def test_filter_scripts_with_existing_no_last_indexed(self):
        """Test _filter_scripts_for_indexing with existing script, no last_indexed."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()

        # Setup transaction context manager
        mock_conn = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_db_ops.transaction.return_value = mock_context

        indexer = IndexCommand(settings, mock_db_ops)

        scripts = [
            FountainMetadata(file_path=Path("script1.fountain"), title="Script 1")
        ]

        # Mock existing script with metadata but no last_indexed
        existing_script = Mock()
        existing_script.metadata = {"other_data": "value"}  # No last_indexed key
        mock_db_ops.get_existing_script.return_value = existing_script

        result = await indexer._filter_scripts_for_indexing(scripts)

        # Script should be included since it has no last_indexed
        assert len(result) == 1

"""Additional tests for API index module to improve coverage."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

from scriptrag.api.index import IndexCommand
from scriptrag.api.index_embeddings import IndexEmbeddingProcessor
from scriptrag.api.list import FountainMetadata
from scriptrag.config import ScriptRAGSettings
from scriptrag.parser import Scene


class TestIndexCommandCoverage:
    """Tests for IndexCommand to improve coverage."""

    @pytest.mark.asyncio
    async def test_discover_scripts_permission_error(self, tmp_path):
        """Test _discover_scripts handles permission errors."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            skip_boneyard_filter=True,  # Enable for unit tests
        )
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

            # With skip_boneyard_filter=True, all scripts returned (no file access)
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_discover_scripts_unicode_decode_error(self, tmp_path):
        """Test _discover_scripts handles UnicodeDecodeError."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            skip_boneyard_filter=True,  # Enable for unit tests
        )
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create a test script file
        script_path = tmp_path / "script.fountain"
        script_path.write_bytes(b"\x80\x81\x82")  # Invalid UTF-8

        mock_scripts = [FountainMetadata(file_path=script_path, title="Test Script")]

        with patch.object(indexer.lister, "list_scripts", return_value=mock_scripts):
            result = await indexer._discover_scripts(tmp_path, recursive=True)

            # With skip_boneyard_filter=True, all scripts returned (no file reading)
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_discover_scripts_os_error(self, tmp_path):
        """Test _discover_scripts handles OSError."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            skip_boneyard_filter=True,  # Enable for unit tests
        )
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

            # With skip_boneyard_filter=True, all scripts returned (no file reading)
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_discover_scripts_unexpected_error(self, tmp_path):
        """Test _discover_scripts handles unexpected errors."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            skip_boneyard_filter=True,  # Enable for unit tests
        )
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

            # With skip_boneyard_filter=True, all scripts returned (no file access)
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_no_metadata(self):
        """Test process_scene_embeddings with no boneyard metadata."""
        mock_db_ops = Mock()
        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops,
            embedding_service=None,
            generate_embeddings=False,
        )

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
        await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No database operations should be called
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_no_analyzers(self):
        """Test process_scene_embeddings with no analyzers in metadata."""
        mock_db_ops = Mock()
        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops,
            embedding_service=None,
            generate_embeddings=False,
        )

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
        await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No database operations should be called
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_no_embedding_data(self):
        """Test process_scene_embeddings with no embedding data."""
        mock_db_ops = Mock()
        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops,
            embedding_service=None,
            generate_embeddings=False,
        )

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
        await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No database operations should be called
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_no_result(self):
        """Test process_scene_embeddings with no result data."""
        mock_db_ops = Mock()
        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops,
            embedding_service=None,
            generate_embeddings=False,
        )

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
        await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No database operations should be called
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_with_error(self):
        """Test process_scene_embeddings with error in result."""
        mock_db_ops = Mock()
        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops,
            embedding_service=None,
            generate_embeddings=False,
        )

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
        await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No database operations should be called
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_no_embedding_path(self):
        """Test process_scene_embeddings with no embedding path."""
        mock_db_ops = Mock()
        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops,
            embedding_service=None,
            generate_embeddings=False,
        )

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
        await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

        # No database operations should be called
        mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_file_exists(self, tmp_path):
        """Test process_scene_embeddings with existing embedding file."""
        mock_db_ops = Mock()
        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops,
            embedding_service=None,
            generate_embeddings=False,
        )

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

            await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

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
        """Test process_scene_embeddings with non-existing embedding file."""
        mock_db_ops = Mock()
        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops,
            embedding_service=None,
            generate_embeddings=False,
        )

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

            await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

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
        mock_db_ops = Mock()
        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops,
            embedding_service=None,
            generate_embeddings=False,
        )

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
            await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

            # No database operations should be called due to error
            mock_db_ops.upsert_embedding.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_scene_embeddings_scene_without_file_path(self, tmp_path):
        """Test process_scene_embeddings with scene that has no file_path attribute."""
        mock_db_ops = Mock()
        processor = IndexEmbeddingProcessor(
            db_ops=mock_db_ops,
            embedding_service=None,
            generate_embeddings=False,
        )

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

            await processor.process_scene_embeddings(mock_conn, scene, scene_id=1)

            # Should use current directory "." for repo search
            mock_repo_class.assert_called_once_with(".", search_parent_directories=True)

    @pytest.mark.asyncio
    async def test_index_single_script_existing_content(self, tmp_path):
        """Test _index_single_script when re-indexing existing content."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            skip_boneyard_filter=True,  # Enable for unit tests
        )
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
                Path("test.fountain"), dry_run=False
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
        settings = ScriptRAGSettings(
            database_path=Path("test.db"),
            skip_boneyard_filter=True,  # Enable for unit tests
        )
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

    @pytest.mark.asyncio
    async def test_index_script_result_semantics_new_script(self, tmp_path):
        """Test IndexResult semantics for new scripts."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            skip_boneyard_filter=True,  # Enable for unit tests
        )
        mock_db_ops = Mock()

        # Setup transaction context
        mock_conn = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_db_ops.transaction.return_value = mock_context

        # Mock no existing script (new script)
        mock_db_ops.get_existing_script.return_value = None
        mock_db_ops.upsert_script.return_value = 1
        mock_db_ops.upsert_scene.return_value = (1, True)
        mock_db_ops.upsert_characters.return_value = {"ALICE": 1}
        mock_db_ops.insert_dialogues.return_value = 1
        mock_db_ops.insert_actions.return_value = 1
        mock_db_ops.get_script_stats.return_value = {
            "scenes": 1,
            "characters": 1,
            "dialogues": 1,
            "actions": 1,
        }

        indexer = IndexCommand(settings, mock_db_ops)

        # Create test script
        script_path = tmp_path / "new_script.fountain"
        script_path.write_text("""Title: New Script
Author: New Author

INT. NEW ROOM - DAY

This is a new script.

CHARACTER
Hello world!
""")

        result = await indexer._index_single_script(script_path, dry_run=False)

        # For new scripts: indexed=True, updated=False
        assert result.indexed is True  # Successfully processed
        assert result.updated is False  # Not an update (new script)
        assert result.script_id is not None

    @pytest.mark.asyncio
    async def test_index_script_result_semantics_existing_script(self, tmp_path):
        """Test IndexResult semantics for existing scripts."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            skip_boneyard_filter=True,  # Enable for unit tests
        )
        mock_db_ops = Mock()

        # Setup transaction context
        mock_conn = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_db_ops.transaction.return_value = mock_context

        indexer = IndexCommand(settings, mock_db_ops)

        # Create test script
        script_path = tmp_path / "existing_script.fountain"
        script_path.write_text("""Title: Existing Script
Author: Existing Author

INT. EXISTING ROOM - DAY

This is an existing script.

CHARACTER
Hello again!
""")

        # First index - new script
        mock_db_ops.get_existing_script.return_value = None  # No existing script
        mock_db_ops.upsert_script.return_value = 1
        mock_db_ops.upsert_scene.return_value = (1, True)
        mock_db_ops.upsert_characters.return_value = {"CHARACTER": 1}
        mock_db_ops.insert_dialogues.return_value = 1
        mock_db_ops.insert_actions.return_value = 1
        mock_db_ops.get_script_stats.return_value = {
            "scenes": 1,
            "characters": 1,
            "dialogues": 1,
            "actions": 1,
        }

        result1 = await indexer._index_single_script(script_path, dry_run=False)
        assert result1.indexed is True
        assert result1.updated is False  # First time = new

        # Second index - existing script
        existing_script = Mock()
        existing_script.id = 1
        mock_db_ops.get_existing_script.return_value = (
            existing_script  # Existing script
        )
        mock_db_ops.upsert_script.return_value = 1  # Same ID

        result2 = await indexer._index_single_script(script_path, dry_run=False)
        assert result2.indexed is True  # Successfully processed
        assert result2.updated is True  # This time it's an update
        assert result2.script_id == result1.script_id  # Same script

    @pytest.mark.asyncio
    async def test_dry_run_index_semantics(self, tmp_path):
        """Test dry run semantics for IndexResult flags."""
        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            skip_boneyard_filter=True,  # Enable for unit tests
        )
        mock_db_ops = Mock()

        # Setup transaction context manager (needed even for dry run)
        mock_conn = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_db_ops.transaction.return_value = mock_context

        # Also setup get_connection for dry run analysis
        mock_db_ops.get_connection.return_value = mock_context

        # Mock get_existing_script to return None (new script)
        mock_db_ops.get_existing_script.return_value = None

        indexer = IndexCommand(settings, mock_db_ops)

        # Create test script
        script_path = tmp_path / "dry_run_script.fountain"
        script_path.write_text("""Title: Dry Run Script
Author: Test Author

INT. ROOM - DAY

This is a dry run test.

CHARACTER
Testing!
""")

        # Test dry run
        result = await indexer._index_single_script(script_path, dry_run=True)

        # Dry run always reports: indexed=False, updated=False
        # Because nothing is actually indexed in dry run mode
        assert result.indexed is False  # Nothing actually indexed in dry run
        assert result.updated is False  # Nothing actually updated in dry run
        assert result.script_id is None  # No actual database operation

    @pytest.mark.asyncio
    async def test_index_script_comments_behavior(self, tmp_path):
        """Test IndexResult behavior consistency with comments in code."""
        # Based on the comments in the modified code:
        # indexed=True means "Successfully processed regardless of new/update"
        # updated=True means "Only updated if it existed"

        settings = ScriptRAGSettings(
            database_path=tmp_path / "test.db",
            skip_boneyard_filter=True,  # Enable for unit tests
        )
        mock_db_ops = Mock()

        # Setup transaction context
        mock_conn = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=None)
        mock_db_ops.transaction.return_value = mock_context

        indexer = IndexCommand(settings, mock_db_ops)

        script_path = tmp_path / "comment_test.fountain"
        script_path.write_text("""Title: Comment Test Script

INT. ROOM - DAY

Testing comment semantics.

CHARACTER
This validates the comment behavior.
""")

        # Test new script scenario
        mock_db_ops.get_existing_script.return_value = None  # New script
        mock_db_ops.upsert_script.return_value = 1
        mock_db_ops.upsert_scene.return_value = (1, True)
        mock_db_ops.upsert_characters.return_value = {"CHARACTER": 1}
        mock_db_ops.insert_dialogues.return_value = 1
        mock_db_ops.insert_actions.return_value = 1
        mock_db_ops.get_script_stats.return_value = {
            "scenes": 1,
            "characters": 1,
            "dialogues": 1,
            "actions": 1,
        }

        result_new = await indexer._index_single_script(script_path, dry_run=False)

        # For new scripts: Successfully processed (indexed=True),
        # not an update (updated=False)
        assert (
            result_new.indexed is True
        )  # Successfully processed regardless of new/update
        assert result_new.updated is False  # Only updated if it existed (it didn't)

        # Test existing script scenario
        existing_script = Mock()
        existing_script.id = 1
        mock_db_ops.get_existing_script.return_value = (
            existing_script  # Existing script
        )

        result_existing = await indexer._index_single_script(script_path, dry_run=False)

        # For existing scripts: Successfully processed (indexed=True),
        # is an update (updated=True)
        assert (
            result_existing.indexed is True
        )  # Successfully processed regardless of new/update
        assert result_existing.updated is True  # Only updated if it existed (it did)

    @pytest.mark.asyncio
    async def test_index_edge_case_empty_scripts_to_index(self):
        """Test the case where discovered scripts becomes empty after filtering."""
        settings = ScriptRAGSettings(
            database_path=Path("test.db"),
            skip_boneyard_filter=False,  # Enable boneyard filtering
        )
        mock_db_ops = Mock()
        mock_db_ops.check_database_exists.return_value = True

        indexer = IndexCommand(settings, mock_db_ops)

        # Create scripts without boneyard metadata
        from scriptrag.api.list import FountainMetadata

        scripts_without_boneyard = [
            FountainMetadata(
                file_path=Path("no_boneyard.fountain"),
                title="No Boneyard",
                has_boneyard=False,
            )
        ]

        # Mock lister to return scripts but _discover_scripts filters them out
        with patch.object(
            indexer.lister, "list_scripts", return_value=scripts_without_boneyard
        ):
            result = await indexer.index()

        assert result.total_scripts_indexed == 0
        assert len(result.errors) == 0
        # This should trigger the "No scripts need indexing" path (lines 154-155)

    @pytest.mark.asyncio
    async def test_apply_bible_aliases_no_bible_characters_key(self):
        """Test _apply_bible_aliases when metadata has no bible.characters key."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        cmd = IndexCommand(settings=settings)

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock metadata with no bible.characters at all
        metadata_no_bible = {"other_metadata": "value"}
        mock_cursor.fetchone.return_value = (json.dumps(metadata_no_bible),)

        # This should trigger the early return on line 552
        await cmd._apply_bible_aliases(
            mock_conn, script_id=1, character_map={"TEST": 1}
        )

        # Should only call SELECT, no UPDATE operations
        mock_cursor.execute.assert_called_once_with(
            "SELECT metadata FROM scripts WHERE id = ?", (1,)
        )

    @pytest.mark.asyncio
    async def test_apply_bible_aliases_character_not_in_map(self):
        """Test _apply_bible_aliases when character not found in character_map."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        cmd = IndexCommand(settings=settings)

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock metadata with Bible characters
        bible_metadata = {
            "bible.characters": {
                "characters": [
                    {"canonical": "NONEXISTENT", "aliases": ["MISSING", "NOT_FOUND"]}
                ]
            }
        }
        mock_cursor.fetchone.return_value = (json.dumps(bible_metadata),)

        # Character map that doesn't include "NONEXISTENT"
        character_map = {"ALICE": 1, "BOB": 2}  # No "NONEXISTENT"

        await cmd._apply_bible_aliases(
            mock_conn, script_id=1, character_map=character_map
        )

        # Should call SELECT but no UPDATE since character not found
        # This tests the branch where char_id is None (line 564->555)
        mock_cursor.execute.assert_called_once_with(
            "SELECT metadata FROM scripts WHERE id = ?", (1,)
        )

        # Verify no UPDATE was called
        update_calls = [
            call
            for call in mock_cursor.execute.call_args_list
            if "UPDATE characters" in str(call)
        ]
        assert len(update_calls) == 0

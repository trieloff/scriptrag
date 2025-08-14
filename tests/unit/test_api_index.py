"""Unit tests for index API module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from scriptrag.api.duplicate_handler import DuplicateStrategy
from scriptrag.api.index import IndexCommand, IndexOperationResult, IndexResult
from scriptrag.api.list import FountainMetadata
from scriptrag.config import ScriptRAGSettings
from scriptrag.parser import Dialogue, Scene, Script


@pytest.fixture
def settings(tmp_path):
    """Create test settings."""
    return ScriptRAGSettings(
        database_path=tmp_path / "test.db",
        database_timeout=5.0,
    )


@pytest.fixture
def mock_db_ops():
    """Create mock database operations."""
    mock = MagicMock()
    mock.check_database_exists.return_value = True
    mock.get_existing_script.return_value = None
    mock.upsert_script.return_value = 1
    mock.upsert_scene.return_value = (1, True)
    mock.upsert_characters.return_value = {"ALICE": 1, "BOB": 2}
    mock.insert_dialogues.return_value = 2
    mock.insert_actions.return_value = 2
    mock.get_script_stats.return_value = {
        "scenes": 1,
        "characters": 2,
        "dialogues": 2,
        "actions": 2,
    }
    mock.transaction.return_value.__enter__ = Mock(return_value=MagicMock())
    mock.transaction.return_value.__exit__ = Mock(return_value=None)
    return mock


@pytest.fixture
def sample_script():
    """Create a sample script for testing."""
    scene = Scene(
        number=1,
        heading="INT. COFFEE SHOP - DAY",
        content="The scene content",
        original_text="Original text",
        content_hash="hash123",
        dialogue_lines=[
            Dialogue(character="ALICE", text="Hello!"),
            Dialogue(character="BOB", text="Hi!"),
        ],
        action_lines=["Alice enters.", "Bob waves."],
        boneyard_metadata={"analyzed": True},
    )

    return Script(
        title="Test Script",
        author="Test Author",
        scenes=[scene],
        metadata={"genre": "drama"},
    )


@pytest.fixture
def sample_script_metadata():
    """Create sample script metadata."""
    from scriptrag.api.list import FountainMetadata

    return [
        FountainMetadata(
            file_path=Path("/test/script1.fountain"),
            title="Script 1",
            author="Author 1",
            scenes=10,
            has_boneyard=True,
        ),
        FountainMetadata(
            file_path=Path("/test/script2.fountain"),
            title="Script 2",
            author="Author 2",
            scenes=5,
            has_boneyard=True,
        ),
    ]


class TestIndexCommand:
    """Test IndexCommand class."""

    def test_init(self, settings, mock_db_ops):
        """Test IndexCommand initialization."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)
        assert cmd.settings == settings
        assert cmd.db_ops == mock_db_ops
        assert cmd.parser is not None
        assert cmd.lister is not None

    def test_from_config(self):
        """Test creating IndexCommand from config."""
        with patch("scriptrag.api.index.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            cmd = IndexCommand.from_config()
            assert cmd.settings == mock_settings
            mock_get_settings.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_no_database(self, settings, mock_db_ops):
        """Test index when database doesn't exist."""
        mock_db_ops.check_database_exists.return_value = False

        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)
        result = await cmd.index()

        assert not result.total_scripts_indexed
        assert len(result.errors) == 1
        assert "Database not initialized" in result.errors[0]

    @pytest.mark.asyncio
    async def test_index_no_scripts(self, settings, mock_db_ops):
        """Test index when no scripts are found."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        with patch.object(cmd, "_discover_scripts", return_value=[]):
            result = await cmd.index()

        assert result.total_scripts_indexed == 0
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_index_with_scripts(
        self, settings, mock_db_ops, sample_script, sample_script_metadata
    ):
        """Test successful indexing of scripts."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        # Mock methods
        with (
            patch.object(cmd, "_discover_scripts", return_value=sample_script_metadata),
            # _filter_scripts_for_indexing is no longer used (all scripts indexed)
            patch.object(cmd.parser, "parse_file", return_value=sample_script),
        ):
            result = await cmd.index()

        # Now all discovered scripts are indexed (2 scripts)
        assert result.total_scripts_indexed == 2
        assert result.total_scenes_indexed == 2  # 1 scene per script
        assert result.total_characters_indexed == 4  # 2 characters per script
        assert result.total_dialogues_indexed == 4  # 2 dialogues per script
        assert result.total_actions_indexed == 4  # 2 actions per script

    @pytest.mark.asyncio
    async def test_index_all_scripts(
        self, settings, mock_db_ops, sample_script, sample_script_metadata
    ):
        """Test that all discovered scripts are indexed."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        # Mock methods
        with (
            patch.object(cmd, "_discover_scripts", return_value=sample_script_metadata),
            patch.object(cmd.parser, "parse_file", return_value=sample_script),
        ):
            result = await cmd.index()  # Always indexes all scripts

        assert result.total_scripts_indexed == 2  # Both scripts indexed
        assert result.total_scenes_indexed == 2
        assert result.total_characters_indexed == 4

    @pytest.mark.asyncio
    async def test_index_with_progress_callback(
        self, settings, mock_db_ops, sample_script, sample_script_metadata
    ):
        """Test index with progress callback."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)
        progress_calls = []

        def progress_callback(pct, msg):
            progress_calls.append((pct, msg))

        with (
            patch.object(cmd, "_discover_scripts", return_value=sample_script_metadata),
            patch.object(
                cmd, "_filter_scripts_for_indexing", return_value=sample_script_metadata
            ),
            patch.object(cmd.parser, "parse_file", return_value=sample_script),
        ):
            await cmd.index(progress_callback=progress_callback)

        # Should have discovery, processing, and completion progress
        assert len(progress_calls) >= 3
        assert progress_calls[0][0] == 0.1
        assert "Discovering" in progress_calls[0][1]
        # Check batch processing progress
        assert any("batch" in msg.lower() for pct, msg in progress_calls)
        # Check completion
        assert progress_calls[-1][0] == 1.0
        assert "complete" in progress_calls[-1][1].lower()

    @pytest.mark.asyncio
    async def test_index_dry_run(self, settings, mock_db_ops, sample_script):
        """Test dry run mode."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        with patch.object(cmd.parser, "parse_file", return_value=sample_script):
            result = await cmd._index_single_script(
                Path("/test/script.fountain"),
                dry_run=True,
                duplicate_strategy=DuplicateStrategy.ERROR,
            )

        assert result.indexed
        assert result.scenes_indexed == 1
        assert result.characters_indexed == 2
        assert result.dialogues_indexed == 2
        assert result.actions_indexed == 2

        # Database operations should not be called in dry run
        mock_db_ops.upsert_script.assert_not_called()

    @pytest.mark.asyncio
    async def test_index_existing_script(self, settings, mock_db_ops, sample_script):
        """Test re-indexing an existing script."""
        # Setup existing script
        mock_db_ops.get_existing_script.return_value = MagicMock(id=1)

        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        with patch.object(cmd.parser, "parse_file", return_value=sample_script):
            result = await cmd._index_single_script(
                Path("/test/script.fountain"),
                dry_run=False,
                duplicate_strategy=DuplicateStrategy.ERROR,
            )

        assert result.indexed
        assert result.updated  # Should be marked as update
        mock_db_ops.clear_script_data.assert_called_once_with(
            mock_db_ops.transaction().__enter__(), 1
        )

    @pytest.mark.asyncio
    async def test_discover_scripts(self, settings, mock_db_ops, tmp_path):
        """Test discovering scripts with boneyard metadata."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        # Create test files
        script1 = tmp_path / "script1.fountain"
        script1.write_text(
            "/* SCRIPTRAG-META-START\n{}\nSCRIPTRAG-META-END */\nContent"
        )

        script2 = tmp_path / "script2.fountain"
        script2.write_text("No metadata here")

        # Mock lister to return both files
        from scriptrag.api.list import FountainMetadata

        mock_scripts = [
            FountainMetadata(file_path=script1, title="Script 1"),
            FountainMetadata(file_path=script2, title="Script 2"),
        ]

        with patch.object(cmd.lister, "list_scripts", return_value=mock_scripts):
            result = await cmd._discover_scripts(tmp_path, recursive=True)

        # Only script1 should be discovered (has metadata)
        assert len(result) == 1
        assert result[0].file_path == script1

    @pytest.mark.asyncio
    async def test_filter_scripts_for_indexing(
        self, settings, mock_db_ops, sample_script_metadata
    ):
        """Test filtering scripts that need indexing."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        # First script is new, second already exists
        def get_existing_side_effect(_conn, path):
            if "script1" in str(path):
                return None  # New script
            return MagicMock(metadata={"last_indexed": "2024-01-01"})  # Existing

        mock_db_ops.get_existing_script.side_effect = get_existing_side_effect

        result = await cmd._filter_scripts_for_indexing(sample_script_metadata)

        # Only script1 should need indexing
        assert len(result) == 1
        assert "script1" in str(result[0].file_path)

    @pytest.mark.asyncio
    async def test_process_scripts_batch(
        self, settings, mock_db_ops, sample_script, sample_script_metadata
    ):
        """Test processing a batch of scripts."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        with patch.object(cmd.parser, "parse_file", return_value=sample_script):
            results = await cmd._process_scripts_batch(
                sample_script_metadata,
                dry_run=False,
                duplicate_strategy=DuplicateStrategy.ERROR,
            )

        assert len(results) == 2
        assert all(r.indexed for r in results)
        assert all(r.error is None for r in results)

    @pytest.mark.asyncio
    async def test_process_scripts_batch_with_error(
        self, settings, mock_db_ops, sample_script_metadata
    ):
        """Test batch processing with errors."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        # Make parser fail
        with patch.object(
            cmd.parser, "parse_file", side_effect=Exception("Parse error")
        ):
            results = await cmd._process_scripts_batch(
                sample_script_metadata[:1],
                dry_run=False,
                duplicate_strategy=DuplicateStrategy.ERROR,
            )

        assert len(results) == 1
        assert not results[0].indexed
        assert "Parse error" in results[0].error

    @pytest.mark.asyncio
    async def test_index_single_script_success(
        self, settings, mock_db_ops, sample_script
    ):
        """Test successful indexing of a single script."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)
        file_path = Path("/test/script.fountain")

        with patch.object(cmd.parser, "parse_file", return_value=sample_script):
            result = await cmd._index_single_script(
                file_path, dry_run=False, duplicate_strategy=DuplicateStrategy.ERROR
            )

        assert result.indexed
        assert result.path == file_path
        assert result.script_id == 1
        assert result.scenes_indexed == 1
        assert result.characters_indexed == 2
        assert result.error is None

        # Verify database operations were called
        mock_db_ops.upsert_script.assert_called_once()
        mock_db_ops.upsert_scene.assert_called_once()
        mock_db_ops.upsert_characters.assert_called_once()
        mock_db_ops.insert_dialogues.assert_called_once()
        mock_db_ops.insert_actions.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_single_script_error(self, settings, mock_db_ops):
        """Test error handling in single script indexing."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)
        file_path = Path("/test/script.fountain")

        with (
            patch.object(
                cmd.parser, "parse_file", side_effect=Exception("Parse failed")
            ),
            pytest.raises(Exception, match="Parse failed"),
        ):
            await cmd._index_single_script(
                file_path, dry_run=False, duplicate_strategy=DuplicateStrategy.ERROR
            )

    @pytest.mark.asyncio
    async def test_dry_run_analysis(self, settings, mock_db_ops, sample_script):
        """Test dry run analysis of a script."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)
        file_path = Path("/test/script.fountain")

        # Test new script
        mock_db_ops.get_existing_script.return_value = None
        result = await cmd._dry_run_analysis(sample_script, file_path)

        assert result.indexed
        assert not result.updated
        assert result.scenes_indexed == 1
        assert result.characters_indexed == 2

        # Test existing script
        mock_db_ops.get_existing_script.return_value = MagicMock(id=1)
        result = await cmd._dry_run_analysis(sample_script, file_path)

        assert result.indexed
        assert result.updated

    @pytest.mark.asyncio
    async def test_index_exception_handling(self, settings, mock_db_ops):
        """Test exception handling in index method."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        # Simulate an exception during discovery
        with patch.object(
            cmd, "_discover_scripts", side_effect=Exception("Discovery failed")
        ):
            result = await cmd.index()

        assert len(result.errors) == 1
        assert "Index operation failed: Discovery failed" in result.errors[0]
        assert result.total_scripts_indexed == 0


class TestIndexResult:
    """Test IndexResult dataclass."""

    def test_default_values(self):
        """Test IndexResult default values."""
        result = IndexResult(path=Path("/test/script.fountain"))

        assert result.path == Path("/test/script.fountain")
        assert result.script_id is None
        assert not result.indexed
        assert not result.updated
        assert result.scenes_indexed == 0
        assert result.characters_indexed == 0
        assert result.dialogues_indexed == 0
        assert result.actions_indexed == 0
        assert result.error is None

    def test_with_values(self):
        """Test IndexResult with values."""
        result = IndexResult(
            path=Path("/test/script.fountain"),
            script_id=1,
            indexed=True,
            updated=True,
            scenes_indexed=5,
            characters_indexed=10,
            dialogues_indexed=50,
            actions_indexed=30,
            error="Some error",
        )

        assert result.script_id == 1
        assert result.indexed
        assert result.updated
        assert result.scenes_indexed == 5
        assert result.characters_indexed == 10
        assert result.dialogues_indexed == 50
        assert result.actions_indexed == 30
        assert result.error == "Some error"

    @pytest.mark.asyncio
    async def test_discover_scripts_with_errors(self, settings, mock_db_ops, tmp_path):
        """Test discovering scripts handles various errors."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        # Create test files with different error conditions
        script1 = tmp_path / "script1.fountain"
        script1.write_text(
            "/* SCRIPTRAG-META-START\n{}\nSCRIPTRAG-META-END */\nContent"
        )

        # Create a file that will cause permission error
        script2 = tmp_path / "script2.fountain"
        script2.write_text("/* SCRIPTRAG-META-START\n{}\nSCRIPTRAG-META-END */")

        # Mock lister to return both files
        from scriptrag.api.list import FountainMetadata

        mock_scripts = [
            FountainMetadata(file_path=script1, title="Script 1"),
            FountainMetadata(file_path=script2, title="Script 2"),
        ]

        # Test with file size optimization (non-zero scan size)
        settings.metadata_scan_size = 1024
        with patch.object(cmd.lister, "list_scripts", return_value=mock_scripts):
            result = await cmd._discover_scripts(tmp_path, recursive=True)

        # Both scripts should be discovered
        assert len(result) == 2

        # Test with full file scan (scan_size = 0)
        settings.metadata_scan_size = 0
        with patch.object(cmd.lister, "list_scripts", return_value=mock_scripts):
            result = await cmd._discover_scripts(tmp_path, recursive=True)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filter_scripts_no_metadata(
        self, settings, mock_db_ops, sample_script_metadata
    ):
        """Test filtering scripts with no last_indexed metadata."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        # Script exists but has no last_indexed metadata
        def get_existing_side_effect(_conn, path):
            if "script1" in str(path):
                return MagicMock(metadata={})  # No last_indexed key
            return None

        mock_db_ops.get_existing_script.side_effect = get_existing_side_effect

        result = await cmd._filter_scripts_for_indexing(sample_script_metadata[:1])

        # Script should need indexing since no last_indexed
        assert len(result) == 1
        assert "script1" in str(result[0].file_path)

    @pytest.mark.asyncio
    async def test_index_single_script_with_no_characters(self, settings, mock_db_ops):
        """Test indexing a script with no characters (only actions)."""
        from scriptrag.parser import Scene, Script

        # Create a script with only action lines, no dialogue
        scene = Scene(
            number=1,
            heading="INT. EMPTY ROOM - DAY",
            content="The scene content",
            original_text="Original text",
            content_hash="hash123",
            dialogue_lines=[],  # No dialogues
            action_lines=["The room is empty.", "A door creaks."],
            boneyard_metadata={"analyzed": True},
        )

        action_only_script = Script(
            title="Action Script",
            author="Test Author",
            scenes=[scene],
            metadata={"genre": "thriller"},
        )

        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)
        file_path = Path("/test/action_script.fountain")

        # Mock to return empty character map when no characters
        mock_db_ops.upsert_characters.return_value = {}
        # Update get_script_stats to reflect no characters
        mock_db_ops.get_script_stats.return_value = {
            "scenes": 1,
            "characters": 0,  # No characters
            "dialogues": 0,
            "actions": 2,
        }

        with patch.object(cmd.parser, "parse_file", return_value=action_only_script):
            result = await cmd._index_single_script(
                file_path, dry_run=False, duplicate_strategy=DuplicateStrategy.ERROR
            )

        assert result.indexed
        assert result.scenes_indexed == 1
        assert result.characters_indexed == 0  # No characters
        assert result.actions_indexed == 2

    @pytest.mark.asyncio
    async def test_index_single_script_update_no_content_change(
        self, settings, mock_db_ops, sample_script
    ):
        """Test updating a script when content hasn't changed."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)
        file_path = Path("/test/script.fountain")

        # Setup existing script
        mock_db_ops.get_existing_script.return_value = MagicMock(id=1)
        # Scene exists with same content hash (no change)
        mock_db_ops.upsert_scene.return_value = (1, False)  # content_changed=False

        with patch.object(cmd.parser, "parse_file", return_value=sample_script):
            result = await cmd._index_single_script(
                file_path, dry_run=False, duplicate_strategy=DuplicateStrategy.ERROR
            )

        assert result.indexed
        assert result.updated  # Script was updated
        # clear_scene_content should NOT be called when content unchanged and not forced
        mock_db_ops.clear_scene_content.assert_not_called()


class TestIndexOperationResult:
    """Test IndexOperationResult dataclass."""

    def test_empty_result(self):
        """Test empty operation result."""
        result = IndexOperationResult()

        assert result.scripts == []
        assert result.errors == []
        assert result.total_scripts_indexed == 0
        assert result.total_scripts_updated == 0
        assert result.total_scenes_indexed == 0
        assert result.total_characters_indexed == 0
        assert result.total_dialogues_indexed == 0
        assert result.total_actions_indexed == 0

    def test_with_scripts(self):
        """Test operation result with scripts."""
        script_results = [
            IndexResult(
                path=Path("/test/script1.fountain"),
                indexed=True,
                updated=False,
                scenes_indexed=5,
                characters_indexed=10,
                dialogues_indexed=20,
                actions_indexed=15,
            ),
            IndexResult(
                path=Path("/test/script2.fountain"),
                indexed=True,
                updated=True,
                scenes_indexed=3,
                characters_indexed=5,
                dialogues_indexed=10,
                actions_indexed=8,
            ),
            IndexResult(
                path=Path("/test/script3.fountain"),
                indexed=False,
                error="Failed to parse",
            ),
        ]

        result = IndexOperationResult(
            scripts=script_results, errors=["Error 1", "Error 2"]
        )

        assert len(result.scripts) == 3
        assert len(result.errors) == 2
        assert result.total_scripts_indexed == 2
        assert result.total_scripts_updated == 1
        assert result.total_scenes_indexed == 8
        assert result.total_characters_indexed == 15
        assert result.total_dialogues_indexed == 30
        assert result.total_actions_indexed == 23


class TestIndexCommandMissingCoverage:
    """Test missing coverage lines in IndexCommand."""

    @pytest.mark.asyncio
    async def test_index_with_batch_error_collection(self):
        """Test that errors from batch processing are collected properly."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create mock scripts with errors
        scripts = [
            FountainMetadata(
                file_path=Path("script1.fountain"),
                title="Script 1",
            ),
            FountainMetadata(
                file_path=Path("script2.fountain"),
                title="Script 2",
            ),
        ]

        # Mock the discover and filter methods
        indexer._discover_scripts = AsyncMock(return_value=scripts)
        indexer._filter_scripts_for_indexing = AsyncMock(return_value=scripts)

        # Mock process_scripts_batch to return results with errors
        batch_result_1 = IndexResult(
            path=Path("script1.fountain"),
            error="Failed to parse script 1",
        )
        batch_result_2 = IndexResult(
            path=Path("script2.fountain"),
            error="Failed to parse script 2",
        )

        indexer._process_scripts_batch = AsyncMock(
            return_value=[batch_result_1, batch_result_2]
        )

        # Run index
        result = await indexer.index(Path(), batch_size=2)

        # Verify errors were collected
        assert len(result.errors) == 2
        assert "script1.fountain: Failed to parse script 1" in result.errors
        assert "script2.fountain: Failed to parse script 2" in result.errors

    @pytest.mark.asyncio
    async def test_discover_scripts_default_path(self):
        """Test _discover_scripts with default path."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Mock the lister instance on the indexer
        with patch.object(indexer.lister, "list_scripts", return_value=[]) as mock_list:
            # Test with None path (should use current directory)
            await indexer._discover_scripts(None, recursive=True)
            mock_list.assert_called_once_with(None, True)

    @pytest.mark.asyncio
    async def test_filter_scripts_skip_metadata_condition(self):
        """Test _filter_scripts_for_indexing with skip_metadata condition."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        # Add context manager support for transaction
        mock_conn = Mock()
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock(return_value=mock_conn)
        mock_context_manager.__exit__ = Mock(return_value=None)
        mock_db_ops.transaction.return_value = mock_context_manager
        indexer = IndexCommand(settings, mock_db_ops)

        # Create test scripts
        scripts = [
            FountainMetadata(
                file_path=Path("script1.fountain"),
                title="Script 1",
            ),
        ]

        # Mock database to return existing script with last_indexed metadata
        existing_script = Mock()
        existing_script.content_hash = "hash1"
        existing_script.metadata = {"last_indexed": "2024-01-01T00:00:00Z"}
        mock_db_ops.get_existing_script.return_value = existing_script

        # Test _filter_scripts_for_indexing (method only takes scripts parameter)
        filtered = await indexer._filter_scripts_for_indexing(scripts)
        # Since script exists in database, it should be filtered out
        assert len(filtered) == 0

    @pytest.mark.asyncio
    async def test_process_scripts_batch_exception_handling(self):
        """Test _process_scripts_batch exception handling."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        # Create test scripts
        scripts = [
            FountainMetadata(
                file_path=Path("script1.fountain"),
                title="Script 1",
            ),
        ]

        # Mock _index_single_script to raise exception
        indexer._index_single_script = AsyncMock(side_effect=Exception("Test error"))

        # Process batch - should catch exception and add to errors
        results = await indexer._process_scripts_batch(
            scripts, dry_run=False, duplicate_strategy=DuplicateStrategy.ERROR
        )
        assert len(results) == 1
        assert results[0].error == "Test error"

    @pytest.mark.asyncio
    async def test_index_single_script_parser_error(self):
        """Test _index_single_script with parser error."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        indexer = IndexCommand(settings, mock_db_ops)

        script_metadata = FountainMetadata(
            file_path=Path("test.fountain"),
            title="Test Script",
        )

        # Mock parser to raise exception
        mock_parser = Mock()
        mock_parser.parse_file.side_effect = Exception("Parse error")
        indexer.parser = mock_parser

        # Test indexing - should raise exception
        with pytest.raises(Exception, match="Parse error"):
            await indexer._index_single_script(
                script_metadata.file_path,
                dry_run=False,
                duplicate_strategy=DuplicateStrategy.ERROR,
            )

    @pytest.mark.asyncio
    async def test_index_single_script_database_error(self):
        """Test _index_single_script with database error."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        # Mock transaction to raise database error
        mock_db_ops.transaction.side_effect = Exception("Database error")
        indexer = IndexCommand(settings, mock_db_ops)

        script_metadata = FountainMetadata(
            file_path=Path("test.fountain"),
            title="Test Script",
        )

        # Mock parsing
        mock_parser = Mock()
        mock_script = Mock()
        mock_script.title = "Test Script"
        mock_script.author = "Test Author"
        mock_script.scenes = []
        mock_parser.parse_file.return_value = mock_script
        indexer.parser = mock_parser

        # Test indexing - should raise database error
        with pytest.raises(Exception, match="Database error"):
            await indexer._index_single_script(
                script_metadata.file_path,
                dry_run=False,
                duplicate_strategy=DuplicateStrategy.ERROR,
            )

    @pytest.mark.asyncio
    async def test_index_single_script_update_case(self):
        """Test _index_single_script update case."""
        settings = ScriptRAGSettings(database_path=Path("test.db"))
        mock_db_ops = Mock()
        # Add context manager support for transaction
        mock_conn = Mock()
        mock_context_manager = Mock()
        mock_context_manager.__enter__ = Mock(return_value=mock_conn)
        mock_context_manager.__exit__ = Mock(return_value=None)
        mock_db_ops.transaction.return_value = mock_context_manager
        indexer = IndexCommand(settings, mock_db_ops)

        script_metadata = FountainMetadata(
            file_path=Path("test.fountain"),
            title="Test Script",
        )

        # Mock parsing
        mock_parser = Mock()
        mock_script = Mock()
        mock_script.title = "Test Script"
        mock_script.author = "Test Author"
        mock_script.scenes = []
        mock_parser.parse_file.return_value = mock_script
        indexer.parser = mock_parser

        # Mock database operations - existing script
        mock_db_ops.check_database.return_value = True
        mock_connection = Mock()
        mock_db_ops.get_connection.return_value = mock_connection
        existing_script = Mock()
        existing_script.id = 1
        existing_script.metadata = {}
        mock_db_ops.get_existing_script.return_value = existing_script
        mock_db_ops.upsert_script.return_value = 1
        mock_db_ops.get_script_stats.return_value = {
            "scenes": 3,
            "characters": 2,
            "dialogues": 5,
            "actions": 4,
        }

        # Test updating
        result = await indexer._index_single_script(
            script_metadata.file_path,
            dry_run=False,
            duplicate_strategy=DuplicateStrategy.ERROR,
        )
        assert result.indexed is True
        assert result.updated is True

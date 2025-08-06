"""Unit tests for index API module."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from scriptrag.api.index import IndexCommand, IndexOperationResult, IndexResult
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
            patch.object(
                cmd,
                "_filter_scripts_for_indexing",
                return_value=sample_script_metadata[:1],
            ),
            patch.object(cmd.parser, "parse_file", return_value=sample_script),
        ):
            result = await cmd.index()

        assert result.total_scripts_indexed == 1
        assert result.total_scenes_indexed == 1
        assert result.total_characters_indexed == 2
        assert result.total_dialogues_indexed == 2
        assert result.total_actions_indexed == 2

    @pytest.mark.asyncio
    async def test_index_with_progress_callback(
        self, settings, mock_db_ops, sample_script_metadata
    ):
        """Test index with progress callback."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)
        progress_calls = []

        def progress_callback(pct, msg):
            progress_calls.append((pct, msg))

        with (
            patch.object(cmd, "_discover_scripts", return_value=sample_script_metadata),
            patch.object(
                cmd, "_filter_scripts_for_indexing", return_value=[]
            ),  # No scripts to process
        ):
            await cmd.index(progress_callback=progress_callback)

        # Should have at least discovery progress
        assert len(progress_calls) > 0
        assert progress_calls[0][0] == 0.1
        assert "Discovering" in progress_calls[0][1]

    @pytest.mark.asyncio
    async def test_index_dry_run(self, settings, mock_db_ops, sample_script):
        """Test dry run mode."""
        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        with patch.object(cmd.parser, "parse_file", return_value=sample_script):
            result = await cmd._index_single_script(
                Path("/test/script.fountain"), force=False, dry_run=True
            )

        assert result.indexed
        assert result.scenes_indexed == 1
        assert result.characters_indexed == 2
        assert result.dialogues_indexed == 2
        assert result.actions_indexed == 2

        # Database operations should not be called in dry run
        mock_db_ops.upsert_script.assert_not_called()

    @pytest.mark.asyncio
    async def test_index_force_mode(self, settings, mock_db_ops, sample_script):
        """Test force re-indexing mode."""
        # Setup existing script
        mock_db_ops.get_existing_script.return_value = MagicMock(id=1)

        cmd = IndexCommand(settings=settings, db_ops=mock_db_ops)

        with patch.object(cmd.parser, "parse_file", return_value=sample_script):
            result = await cmd._index_single_script(
                Path("/test/script.fountain"), force=True, dry_run=False
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
                sample_script_metadata, force=False, dry_run=False
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
                sample_script_metadata[:1], force=False, dry_run=False
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
                file_path, force=False, dry_run=False
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
            await cmd._index_single_script(file_path, force=False, dry_run=False)

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

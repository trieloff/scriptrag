"""Additional tests for analyze.py to improve coverage."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from scriptrag.api.analyze import AnalyzeCommand
from scriptrag.api.analyze_helpers import (
    file_needs_update,
    load_bible_metadata,
    scene_needs_update,
)
from scriptrag.api.analyze_protocols import SceneAnalyzer
from scriptrag.api.analyze_results import AnalyzeResult, FileResult
from scriptrag.api.list import FountainMetadata
from scriptrag.exceptions import AnalyzerError
from scriptrag.parser import Scene, Script


@pytest.fixture
def mock_scene_analyzer() -> Mock:
    """Create a mock scene analyzer."""
    analyzer = Mock(spec=SceneAnalyzer)
    analyzer.name = "test-analyzer"
    analyzer.analyze = AsyncMock(return_value={"test": "result"})
    analyzer.version = "1.0"
    return analyzer


@pytest.fixture
def sample_script() -> Script:
    """Create a sample script for testing."""
    # Create a scene with all required arguments
    scene = Scene(
        number=1,
        heading="INT. OFFICE - DAY",
        content="Test scene content",
        original_text="INT. OFFICE - DAY\n\nTest scene content",
        content_hash="test_hash",
    )
    scene.boneyard_metadata = None

    # Create script with all required arguments
    return Script(title="Test Script", author="Test Author", scenes=[scene])


class TestFileResult:
    """Test FileResult dataclass."""

    def test_file_result_creation(self) -> None:
        """Test creating a FileResult."""
        result = FileResult(
            path=Path("/test/script.fountain"),
            updated=True,
            scenes_updated=5,
            error=None,
        )
        assert result.path == Path("/test/script.fountain")
        assert result.updated is True
        assert result.scenes_updated == 5
        assert result.error is None

    def test_file_result_with_error(self) -> None:
        """Test FileResult with error."""
        result = FileResult(
            path=Path("/test/script.fountain"),
            updated=False,
            error="Parse error",
        )
        assert result.updated is False
        assert result.scenes_updated == 0  # Default value
        assert result.error == "Parse error"


class TestAnalyzeResult:
    """Test AnalyzeResult dataclass."""

    def test_analyze_result_properties(self) -> None:
        """Test AnalyzeResult computed properties."""
        result = AnalyzeResult(
            files=[
                FileResult(Path("/test1.fountain"), updated=True, scenes_updated=3),
                FileResult(Path("/test2.fountain"), updated=False, scenes_updated=0),
                FileResult(Path("/test3.fountain"), updated=True, scenes_updated=5),
            ],
            errors=["Error 1", "Error 2"],
        )

        assert result.total_files_updated == 2  # Two files were updated
        assert result.total_scenes_updated == 8  # 3 + 0 + 5
        assert len(result.errors) == 2

    def test_analyze_result_empty(self) -> None:
        """Test empty AnalyzeResult."""
        result = AnalyzeResult()

        assert result.total_files_updated == 0
        assert result.total_scenes_updated == 0
        assert len(result.files) == 0
        assert len(result.errors) == 0


class TestAnalyzeCommand:
    """Test AnalyzeCommand class."""

    def test_init_with_analyzers(self, mock_scene_analyzer: Mock) -> None:
        """Test initialization with analyzers."""
        command = AnalyzeCommand(analyzers=[mock_scene_analyzer])
        assert len(command.analyzers) == 1
        assert command.analyzers[0] is mock_scene_analyzer

    def test_init_without_analyzers(self) -> None:
        """Test initialization without analyzers."""
        command = AnalyzeCommand()
        assert len(command.analyzers) == 0

    def test_from_config(self) -> None:
        """Test creating AnalyzeCommand from config."""
        command = AnalyzeCommand.from_config()
        assert isinstance(command, AnalyzeCommand)
        assert len(command.analyzers) == 0

    def test_register_analyzer(self) -> None:
        """Test registering an analyzer class."""
        command = AnalyzeCommand()

        # Mock analyzer class
        mock_class = Mock(spec=object)
        command.register_analyzer("test", mock_class)

        assert "test" in command._analyzer_registry
        assert command._analyzer_registry["test"] is mock_class

    def test_load_analyzer_already_loaded(self, mock_scene_analyzer: Mock) -> None:
        """Test loading analyzer that is already loaded."""
        command = AnalyzeCommand(analyzers=[mock_scene_analyzer])

        # Try to load the same analyzer again
        command.load_analyzer("test-analyzer")

        # Should still only have one analyzer
        assert len(command.analyzers) == 1

    def test_load_analyzer_from_registry(self) -> None:
        """Test loading analyzer from registry."""
        command = AnalyzeCommand()

        # Mock analyzer class
        mock_class = Mock(spec=object)
        mock_instance = Mock(spec=object)
        mock_instance.name = "test"
        mock_class.return_value = mock_instance

        command.register_analyzer("test", mock_class)
        command.load_analyzer("test")

        assert len(command.analyzers) == 1
        assert command.analyzers[0] is mock_instance

    def test_load_analyzer_from_builtin(self) -> None:
        """Test loading analyzer from builtin analyzers."""
        command = AnalyzeCommand()

        mock_analyzer_instance = Mock(spec=object)
        mock_analyzer_instance.name = "builtin_test"
        mock_analyzer_class = Mock(return_value=mock_analyzer_instance)

        with patch(
            "scriptrag.analyzers.builtin.BUILTIN_ANALYZERS",
            {"builtin_test": mock_analyzer_class},
        ):
            command.load_analyzer("builtin_test", {"config": "value"})

            assert len(command.analyzers) == 1
            assert command.analyzers[0] is mock_analyzer_instance
            mock_analyzer_class.assert_called_once_with({"config": "value"})

    def test_load_analyzer_from_agent_loader(self) -> None:
        """Test loading analyzer from markdown agent loader."""
        command = AnalyzeCommand()

        mock_agent = Mock(spec=object)
        mock_agent.name = "agent_test"
        mock_loader = Mock(spec=["load_agent"])
        mock_loader.load_agent.return_value = mock_agent

        with (
            patch("scriptrag.analyzers.builtin.BUILTIN_ANALYZERS", {}),
            patch("scriptrag.agents.AgentLoader", return_value=mock_loader),
        ):
            command.load_analyzer("agent_test")

            assert len(command.analyzers) == 1
            assert command.analyzers[0] is mock_agent
            mock_loader.load_agent.assert_called_once_with("agent_test")

    def test_load_analyzer_unknown(self) -> None:
        """Test loading unknown analyzer raises error."""
        command = AnalyzeCommand()

        with (
            patch("scriptrag.analyzers.builtin.BUILTIN_ANALYZERS", {}),
            patch("scriptrag.agents.AgentLoader") as mock_loader_class,
        ):
            mock_loader = Mock(spec=["load_agent"])
            mock_loader.load_agent.side_effect = ValueError("Unknown agent")
            mock_loader_class.return_value = mock_loader

            with pytest.raises(ValueError, match="Unknown analyzer: unknown"):
                command.load_analyzer("unknown")

    @pytest.mark.asyncio
    async def test_analyze_no_scripts_found(self) -> None:
        """Test analyze when no scripts are found."""
        command = AnalyzeCommand()

        with patch("scriptrag.api.analyze.ScriptLister") as mock_lister_class:
            mock_lister = Mock(spec=["list_scripts"])
            mock_lister.list_scripts.return_value = []
            mock_lister_class.return_value = mock_lister

            result = await command.analyze(Path("/empty"))

            assert len(result.files) == 0
            assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_analyze_with_progress_callback(
        self, mock_scene_analyzer: Mock
    ) -> None:
        """Test analyze with progress callback."""
        command = AnalyzeCommand(analyzers=[mock_scene_analyzer])

        # Mock script lister
        script_meta = FountainMetadata(file_path=Path("/test.fountain"), title="Test")

        # Mock progress callback
        progress_calls = []

        def progress_callback(progress: float, message: str) -> None:
            progress_calls.append((progress, message))

        with (
            patch("scriptrag.api.analyze.ScriptLister") as mock_lister_class,
            patch.object(
                command, "_process_file", new_callable=AsyncMock
            ) as mock_process,
        ):
            mock_lister = Mock(spec=["list_scripts"])
            mock_lister.list_scripts.return_value = [script_meta]
            mock_lister_class.return_value = mock_lister

            mock_process.return_value = FileResult(Path("/test.fountain"), updated=True)

            result = await command.analyze(
                Path("/test"), progress_callback=progress_callback
            )

            assert len(result.files) == 1
            assert len(progress_calls) == 1
            assert progress_calls[0][0] == 1.0  # 100% progress
            assert "test.fountain" in progress_calls[0][1]

    @pytest.mark.asyncio
    async def test_analyze_brittle_mode_file_error(
        self, mock_scene_analyzer: Mock
    ) -> None:
        """Test analyze in brittle mode with file processing error."""
        command = AnalyzeCommand(analyzers=[mock_scene_analyzer])

        script_meta = FountainMetadata(file_path=Path("/test.fountain"), title="Test")

        with (
            patch("scriptrag.api.analyze.ScriptLister") as mock_lister_class,
            patch.object(
                command, "_process_file", new_callable=AsyncMock
            ) as mock_process,
        ):
            mock_lister = Mock(spec=["list_scripts"])
            mock_lister.list_scripts.return_value = [script_meta]
            mock_lister_class.return_value = mock_lister

            mock_process.side_effect = AnalyzerError("File processing error")

            with pytest.raises(AnalyzerError, match="File processing error"):
                await command.analyze(Path("/test"), brittle=True)

    @pytest.mark.asyncio
    async def test_analyze_non_brittle_mode_file_error(
        self, mock_scene_analyzer: Mock
    ) -> None:
        """Test analyze in non-brittle mode with file processing error."""
        command = AnalyzeCommand(analyzers=[mock_scene_analyzer])

        script_meta = FountainMetadata(file_path=Path("/test.fountain"), title="Test")

        with (
            patch("scriptrag.api.analyze.ScriptLister") as mock_lister_class,
            patch.object(
                command, "_process_file", new_callable=AsyncMock
            ) as mock_process,
        ):
            mock_lister = Mock(spec=["list_scripts"])
            mock_lister.list_scripts.return_value = [script_meta]
            mock_lister_class.return_value = mock_lister

            mock_process.side_effect = AnalyzerError("File processing error")

            result = await command.analyze(Path("/test"), brittle=False)

            assert len(result.files) == 1
            assert result.files[0].updated is False
            assert result.files[0].error == "File processing error"
            assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_analyze_general_error_brittle(self) -> None:
        """Test analyze with general error in brittle mode."""
        command = AnalyzeCommand()

        with patch("scriptrag.api.analyze.ScriptLister") as mock_lister_class:
            mock_lister_class.side_effect = AnalyzerError("General error")

            with pytest.raises(AnalyzerError, match="General error"):
                await command.analyze(Path("/test"), brittle=True)

    @pytest.mark.asyncio
    async def test_analyze_general_error_non_brittle(self) -> None:
        """Test analyze with general error in non-brittle mode."""
        command = AnalyzeCommand()

        with patch("scriptrag.api.analyze.ScriptLister") as mock_lister_class:
            mock_lister_class.side_effect = AnalyzerError("General error")

            result = await command.analyze(Path("/test"), brittle=False)

            assert len(result.files) == 0
            assert len(result.errors) == 1
            assert "General error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_process_file_force_false_no_update_needed(
        self, sample_script: Script
    ) -> None:
        """Test processing file when no update is needed."""
        command = AnalyzeCommand()

        with (
            patch("scriptrag.api.analyze.FountainParser") as mock_parser_class,
            patch("scriptrag.api.analyze.file_needs_update", return_value=False),
        ):
            mock_parser = Mock(spec=object)
            mock_parser.parse_file.return_value = sample_script
            mock_parser_class.return_value = mock_parser

            result = await command._process_file(
                Path("/test.fountain"), force=False, dry_run=False
            )

            assert result.updated is False
            assert result.scenes_updated == 0

    @pytest.mark.asyncio
    async def test_process_file_dry_run_mode(
        self, sample_script: Script, mock_scene_analyzer: Mock
    ) -> None:
        """Test processing file in dry run mode."""
        command = AnalyzeCommand(analyzers=[mock_scene_analyzer])

        # Make analyzer support cleanup
        mock_scene_analyzer.cleanup = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )

        with (
            patch("scriptrag.api.analyze.FountainParser") as mock_parser_class,
            patch("scriptrag.api.analyze.file_needs_update", return_value=True),
            patch("scriptrag.api.analyze.scene_needs_update", return_value=True),
        ):
            mock_parser = Mock(spec=object)
            mock_parser.parse_file.return_value = sample_script
            mock_parser_class.return_value = mock_parser

            result = await command._process_file(
                Path("/test.fountain"), force=False, dry_run=True
            )

            assert result.updated is True
            assert result.scenes_updated == 1
            mock_scene_analyzer.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_file_with_script_context(
        self, sample_script: Script, mock_scene_analyzer: Mock
    ) -> None:
        """Test processing file that sets script context on analyzers."""
        # Add script attribute to analyzer
        mock_scene_analyzer.script = None

        command = AnalyzeCommand(analyzers=[mock_scene_analyzer])

        with (
            patch("scriptrag.api.analyze.FountainParser") as mock_parser_class,
            patch("scriptrag.api.analyze.file_needs_update", return_value=True),
            patch("scriptrag.api.analyze.scene_needs_update", return_value=False),
        ):
            mock_parser = Mock(spec=object)
            mock_parser.parse_file.return_value = sample_script
            mock_parser_class.return_value = mock_parser

            result = await command._process_file(
                Path("/test.fountain"), force=False, dry_run=False
            )

            # Should have set script context
            assert mock_scene_analyzer.script is sample_script

    @pytest.mark.asyncio
    async def test_process_file_relationships_analyzer_with_bible(
        self, sample_script: Script
    ) -> None:
        """Test processing file with relationships analyzer and bible metadata."""
        # Create relationships analyzer mock
        relationships_analyzer = Mock(spec=object)
        relationships_analyzer.name = "relationships"
        relationships_analyzer.bible_characters = None
        relationships_analyzer._build_alias_index = Mock(spec=object)
        relationships_analyzer.analyze = AsyncMock(return_value={})
        # Remove initialize and cleanup attributes to prevent hasattr checks
        del relationships_analyzer.initialize
        del relationships_analyzer.cleanup

        command = AnalyzeCommand(analyzers=[relationships_analyzer])

        bible_metadata = {"version": 1, "characters": []}

        with (
            patch("scriptrag.api.analyze.FountainParser") as mock_parser_class,
            patch("scriptrag.api.analyze.file_needs_update", return_value=True),
            patch("scriptrag.api.analyze.scene_needs_update", return_value=False),
            patch(
                "scriptrag.api.analyze.load_bible_metadata",
                new_callable=AsyncMock,
                return_value=bible_metadata,
            ),
        ):
            mock_parser = Mock(spec=object)
            mock_parser.parse_file.return_value = sample_script
            mock_parser_class.return_value = mock_parser

            result = await command._process_file(
                Path("/test.fountain"), force=False, dry_run=False
            )

            # Should have set bible metadata and called build index
            assert relationships_analyzer.bible_characters is bible_metadata
            relationships_analyzer._build_alias_index.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_file_analyzer_with_initialize(
        self, sample_script: Script
    ) -> None:
        """Test processing file with analyzer that has initialize method."""
        analyzer_with_init = Mock(spec=object)
        analyzer_with_init.name = "test"
        analyzer_with_init.initialize = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        analyzer_with_init.analyze = AsyncMock(return_value={})
        # Remove cleanup attribute to prevent hasattr check from passing
        del analyzer_with_init.cleanup

        command = AnalyzeCommand(analyzers=[analyzer_with_init])

        with (
            patch("scriptrag.api.analyze.FountainParser") as mock_parser_class,
            patch("scriptrag.api.analyze.file_needs_update", return_value=True),
            patch("scriptrag.api.analyze.scene_needs_update", return_value=False),
        ):
            mock_parser = Mock(spec=object)
            mock_parser.parse_file.return_value = sample_script
            mock_parser_class.return_value = mock_parser

            await command._process_file(
                Path("/test.fountain"), force=False, dry_run=False
            )

            analyzer_with_init.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_file_scenes_with_new_metadata(
        self, sample_script: Script, mock_scene_analyzer: Mock
    ) -> None:
        """Test processing file where scenes get new metadata."""
        command = AnalyzeCommand(analyzers=[mock_scene_analyzer])

        # Mark the scene as having new metadata
        sample_script.scenes[0].has_new_metadata = True

        with (
            patch("scriptrag.api.analyze.FountainParser") as mock_parser_class,
            patch("scriptrag.api.analyze.file_needs_update", return_value=True),
            patch("scriptrag.api.analyze.scene_needs_update", return_value=True),
        ):
            mock_parser = Mock(spec=object)
            mock_parser.parse_file.return_value = sample_script
            mock_parser.write_with_updated_scenes = Mock(spec=object)
            mock_parser_class.return_value = mock_parser

            result = await command._process_file(
                Path("/test.fountain"), force=False, dry_run=False
            )

            # Should have written updated scenes
            mock_parser.write_with_updated_scenes.assert_called_once()
            assert result.scenes_updated == 1

    def test_file_needs_update_not_script(self) -> None:
        """Test file_needs_update with non-Script object."""
        # Pass non-Script object
        result = file_needs_update("not a script", [], Path("/test"))
        assert result is False

    def test_file_needs_update_script_needs_update(self, sample_script: Script) -> None:
        """Test file_needs_update when script has scenes needing update."""
        with patch(
            "scriptrag.api.analyze_helpers.scene_needs_update", return_value=True
        ):
            result = file_needs_update(sample_script, [], Path("/test"))
            assert result is True

    def test_file_needs_update_script_no_update_needed(
        self, sample_script: Script
    ) -> None:
        """Test file_needs_update when script doesn't need update."""
        with patch(
            "scriptrag.api.analyze_helpers.scene_needs_update", return_value=False
        ):
            result = file_needs_update(sample_script, [], Path("/test"))
            assert result is False

    def test_scene_needs_update_not_scene(self) -> None:
        """Test scene_needs_update with non-Scene object."""
        result = scene_needs_update("not a scene", [])
        assert result is False

    def test_scene_needs_update_no_metadata(self) -> None:
        """Test scene_needs_update with scene having no metadata."""
        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="INT. TEST - DAY\n\nTest content",
            content_hash="test_hash",
        )
        scene.boneyard_metadata = None

        result = scene_needs_update(scene, [])
        assert result is True

    def test_scene_needs_update_no_analyzed_at(self) -> None:
        """Test scene_needs_update with metadata missing analyzed_at."""
        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="INT. TEST - DAY\n\nTest content",
            content_hash="test_hash",
        )
        scene.boneyard_metadata = {"some": "data"}

        result = scene_needs_update(scene, [])
        assert result is True

    def test_scene_needs_update_missing_analyzers(
        self, mock_scene_analyzer: Mock
    ) -> None:
        """Test scene_needs_update when current analyzers missing from metadata."""
        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="INT. TEST - DAY\n\nTest content",
            content_hash="test_hash",
        )
        scene.boneyard_metadata = {
            "analyzed_at": "2023-01-01T00:00:00",
            "analyzers": {"other-analyzer": {}},
        }

        result = scene_needs_update(scene, [mock_scene_analyzer])
        assert result is True  # test-analyzer is missing

    def test_scene_needs_update_all_analyzers_present(
        self, mock_scene_analyzer: Mock
    ) -> None:
        """Test scene_needs_update when all analyzers are present."""
        scene = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="INT. TEST - DAY\n\nTest content",
            content_hash="test_hash",
        )
        scene.boneyard_metadata = {
            "analyzed_at": "2023-01-01T00:00:00",
            "analyzers": {"test-analyzer": {}},
        }

        result = scene_needs_update(scene, [mock_scene_analyzer])
        assert result is False

    @pytest.mark.asyncio
    async def test_load_bible_metadata_no_database(self) -> None:
        """Test loading bible metadata when database doesn't exist."""
        with patch(
            "scriptrag.api.database_operations.DatabaseOperations"
        ) as mock_db_class:
            mock_db = Mock(spec=object)
            mock_db.check_database_exists.return_value = False
            mock_db_class.return_value = mock_db

            result = await load_bible_metadata(Path("/test.fountain"))
            assert result is None

    @pytest.mark.asyncio
    async def test_load_bible_metadata_no_script_record(self) -> None:
        """Test loading bible metadata when script record not found."""
        with patch(
            "scriptrag.api.database_operations.DatabaseOperations"
        ) as mock_db_class:
            mock_db = Mock(spec=object)
            mock_db.check_database_exists.return_value = True

            mock_conn = Mock(spec=object)
            mock_cursor = Mock(spec=object)
            mock_cursor.fetchone.return_value = None  # No record found
            mock_conn.cursor.return_value = mock_cursor
            mock_db.transaction.return_value.__enter__ = Mock(return_value=mock_conn)
            mock_db.transaction.return_value.__exit__ = Mock(return_value=None)
            mock_db_class.return_value = mock_db

            result = await load_bible_metadata(Path("/test.fountain"))
            assert result is None

    @pytest.mark.asyncio
    async def test_load_bible_metadata_success(self) -> None:
        """Test successfully loading bible metadata."""
        bible_data = {"version": 1, "characters": []}
        metadata = {"bible.characters": bible_data}

        with patch(
            "scriptrag.api.database_operations.DatabaseOperations"
        ) as mock_db_class:
            mock_db = Mock(spec=object)
            mock_db.check_database_exists.return_value = True

            mock_conn = Mock(spec=object)
            mock_cursor = Mock(spec=object)
            mock_cursor.fetchone.return_value = (json.dumps(metadata),)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.transaction.return_value.__enter__ = Mock(return_value=mock_conn)
            mock_db.transaction.return_value.__exit__ = Mock(return_value=None)
            mock_db_class.return_value = mock_db

            result = await load_bible_metadata(Path("/test.fountain"))
            assert result == bible_data

    @pytest.mark.asyncio
    async def test_load_bible_metadata_exception(self) -> None:
        """Test loading bible metadata with exception."""
        with patch(
            "scriptrag.api.database_operations.DatabaseOperations"
        ) as mock_db_class:
            mock_db_class.side_effect = Exception("Database error")

            result = await load_bible_metadata(Path("/test.fountain"))
            assert result is None

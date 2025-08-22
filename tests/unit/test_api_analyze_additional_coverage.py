"""Additional tests for analyze.py to improve coverage."""

import json
from typing import ClassVar
from unittest.mock import MagicMock, Mock, patch

import pytest

from scriptrag.analyzers.base import BaseSceneAnalyzer
from scriptrag.api.analyze import AnalyzeCommand
from scriptrag.api.analyze_helpers import load_bible_metadata, scene_needs_update
from scriptrag.parser import Scene, Script


@pytest.fixture
def temp_fountain_file(tmp_path):
    """Create a temporary fountain file."""
    file_path = tmp_path / "test_script.fountain"
    content = """Title: Test Script
Author: Test Author

FADE IN:

INT. OFFICE - DAY

ALICE enters the room.

ALICE
Hello world!

BOB
Hi there!

FADE OUT."""
    file_path.write_text(content)
    return file_path


class TestAnalyzeCommandAdditionalCoverage:
    """Additional tests to cover missing lines in analyze.py."""

    @pytest.mark.asyncio
    async def test_load_bible_metadata_success(self, tmp_path):
        """Test successful loading of Bible metadata from database."""
        cmd = AnalyzeCommand()
        script_path = tmp_path / "test.fountain"

        # Mock Bible metadata
        bible_metadata = {
            "version": 1,
            "characters": [
                {"canonical": "JANE SMITH", "aliases": ["JANE", "MS. SMITH"]}
            ],
        }

        # Mock database operations
        with patch(
            "scriptrag.api.database_operations.DatabaseOperations"
        ) as mock_db_ops_class:
            with patch("scriptrag.config.get_settings") as mock_settings:
                mock_db_ops = mock_db_ops_class.return_value
                mock_db_ops.check_database_exists.return_value = True

                # Mock transaction context manager
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                mock_cursor.fetchone.return_value = (
                    json.dumps({"bible.characters": bible_metadata}),
                )

                mock_db_ops.transaction.return_value.__enter__ = Mock(
                    return_value=mock_conn
                )
                mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

                result = await load_bible_metadata(script_path)

                assert result == bible_metadata
                mock_cursor.execute.assert_called_once_with(
                    "SELECT metadata FROM scripts WHERE file_path = ?",
                    (str(script_path),),
                )

    @pytest.mark.asyncio
    async def test_load_bible_metadata_no_database(self, tmp_path):
        """Test Bible metadata loading when database doesn't exist."""
        cmd = AnalyzeCommand()
        script_path = tmp_path / "test.fountain"

        with patch(
            "scriptrag.api.database_operations.DatabaseOperations"
        ) as mock_db_ops_class:
            with patch("scriptrag.config.get_settings"):
                mock_db_ops = mock_db_ops_class.return_value
                mock_db_ops.check_database_exists.return_value = False

                result = await load_bible_metadata(script_path)

                assert result is None

    @pytest.mark.asyncio
    async def test_load_bible_metadata_no_row(self, tmp_path):
        """Test Bible metadata loading when no script row found."""
        cmd = AnalyzeCommand()
        script_path = tmp_path / "test.fountain"

        with patch(
            "scriptrag.api.database_operations.DatabaseOperations"
        ) as mock_db_ops_class:
            with patch("scriptrag.config.get_settings"):
                mock_db_ops = mock_db_ops_class.return_value
                mock_db_ops.check_database_exists.return_value = True

                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                mock_cursor.fetchone.return_value = None

                mock_db_ops.transaction.return_value.__enter__ = Mock(
                    return_value=mock_conn
                )
                mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

                result = await load_bible_metadata(script_path)

                assert result is None

    @pytest.mark.asyncio
    async def test_load_bible_metadata_invalid_characters(self, tmp_path):
        """Test Bible metadata loading with invalid characters data."""
        cmd = AnalyzeCommand()
        script_path = tmp_path / "test.fountain"

        with patch(
            "scriptrag.api.database_operations.DatabaseOperations"
        ) as mock_db_ops_class:
            with patch("scriptrag.config.get_settings"):
                mock_db_ops = mock_db_ops_class.return_value
                mock_db_ops.check_database_exists.return_value = True

                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                # Return metadata with invalid bible.characters (string instead of dict)
                mock_cursor.fetchone.return_value = (
                    json.dumps({"bible.characters": "invalid"}),
                )

                mock_db_ops.transaction.return_value.__enter__ = Mock(
                    return_value=mock_conn
                )
                mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

                result = await load_bible_metadata(script_path)

                assert result is None

    @pytest.mark.asyncio
    async def test_load_bible_metadata_exception(self, tmp_path):
        """Test Bible metadata loading with database exception."""
        cmd = AnalyzeCommand()
        script_path = tmp_path / "test.fountain"

        with patch(
            "scriptrag.api.database_operations.DatabaseOperations"
        ) as mock_db_ops_class:
            with patch("scriptrag.config.get_settings"):
                mock_db_ops = mock_db_ops_class.return_value
                mock_db_ops.check_database_exists.side_effect = Exception("DB Error")

                result = await load_bible_metadata(script_path)

                assert result is None

    @pytest.mark.asyncio
    async def test_analyzer_with_bible_metadata_application(self, temp_fountain_file):
        """Test analyzer receives Bible metadata when available."""

        class RelationshipsAnalyzer(BaseSceneAnalyzer):
            name = "relationships"
            bible_characters = None

            def _build_alias_index(self):
                self.alias_built = True

            async def analyze(self, scene):
                return {"relationships": "analyzed"}

        analyzer = RelationshipsAnalyzer()
        cmd = AnalyzeCommand(analyzers=[analyzer])

        bible_metadata = {
            "version": 1,
            "characters": [{"canonical": "JANE", "aliases": ["MS. JANE"]}],
        }

        with patch(
            "scriptrag.api.analyze.load_bible_metadata", return_value=bible_metadata
        ):
            result = await cmd.analyze(path=temp_fountain_file.parent, force=True)

            # Analyzer should have received bible metadata
            assert analyzer.bible_characters == bible_metadata
            assert hasattr(analyzer, "alias_built")
            assert result.files[0].updated

    @pytest.mark.asyncio
    async def test_analyzer_with_script_context_in_normal_mode(
        self, temp_fountain_file
    ):
        """Test analyzer receives script context in normal processing mode."""

        class ScriptContextAnalyzer(BaseSceneAnalyzer):
            name = "script_context"
            script = None

            async def analyze(self, scene):
                return {"has_script": self.script is not None}

        analyzer = ScriptContextAnalyzer()
        cmd = AnalyzeCommand(analyzers=[analyzer])

        result = await cmd.analyze(path=temp_fountain_file.parent, force=True)

        # Analyzer should have received script context
        assert analyzer.script is not None
        assert result.files[0].updated

    @pytest.mark.asyncio
    async def test_scene_with_new_metadata_flag(self, temp_fountain_file):
        """Test handling of scenes with has_new_metadata flag."""

        class MetadataAnalyzer(BaseSceneAnalyzer):
            name = "metadata_test"

            async def analyze(self, scene):
                return {"test": "metadata"}

        cmd = AnalyzeCommand(analyzers=[MetadataAnalyzer()])

        # Mock parser to ensure we can control the scenes
        with patch("scriptrag.api.analyze.FountainParser") as mock_parser:
            mock_scene = Scene(
                number=1,
                heading="INT. TEST - DAY",
                content="Test content",
                original_text="Test",
                content_hash="hash123",
            )
            # Add the has_new_metadata attribute
            mock_scene.has_new_metadata = True

            mock_script = Script(title="Test", author="Author", scenes=[mock_scene])

            mock_parser_instance = mock_parser.return_value
            mock_parser_instance.parse_file.return_value = mock_script

            # Mock the write method to be callable
            mock_parser_instance.write_with_updated_scenes = MagicMock()

            result = await cmd.analyze(path=temp_fountain_file.parent, force=True)

            # Should call write_with_updated_scenes since scene has new metadata
            mock_parser_instance.write_with_updated_scenes.assert_called_once()
            assert result.files[0].updated

    def test_create_empty_result(self):
        """Test creation of empty analyze result structure."""
        from scriptrag.api.analyze import AnalyzeResult

        result = AnalyzeResult()

        # Test all properties with empty data
        assert result.files == []
        assert result.errors == []
        assert result.total_files_updated == 0
        assert result.total_scenes_updated == 0

    @pytest.mark.asyncio
    async def test_bible_metadata_without_build_alias_index(self, temp_fountain_file):
        """Test Bible metadata loading when analyzer has no _build_alias_index."""

        class RelationshipsAnalyzerNoBuildIndex(BaseSceneAnalyzer):
            name = "relationships"
            bible_characters = None
            # Note: no _build_alias_index method

            async def analyze(self, scene):
                return {"relationships": "analyzed"}

        analyzer = RelationshipsAnalyzerNoBuildIndex()
        cmd = AnalyzeCommand(analyzers=[analyzer])

        bible_metadata = {
            "version": 1,
            "characters": [{"canonical": "JANE", "aliases": ["MS. JANE"]}],
        }

        with patch(
            "scriptrag.api.analyze.load_bible_metadata", return_value=bible_metadata
        ):
            result = await cmd.analyze(path=temp_fountain_file.parent, force=True)

            # Bible metadata should be loaded but NOT assigned to analyzer
            # since the _build_alias_index method doesn't exist (branch 254->241)
            assert analyzer.bible_characters is None  # Not set due to missing method
            assert not hasattr(analyzer, "_build_alias_index")
            assert result.files[0].updated

    @pytest.mark.asyncio
    async def test_dry_run_scenes_not_needing_update(self, temp_fountain_file):
        """Test dry run mode when scenes don't need update (line 269->268)."""
        cmd = AnalyzeCommand()

        # Mock parser to return a script with scenes that don't need update
        with patch("scriptrag.api.analyze.FountainParser") as mock_parser:
            mock_scene = Scene(
                number=1,
                heading="INT. TEST - DAY",
                content="Test content",
                original_text="Test",
                content_hash="hash123",
                boneyard_metadata={
                    "analyzed_at": "2024-01-01T00:00:00",
                    "analyzers": {},  # No analyzers, so no update needed
                },
            )

            mock_script = Script(title="Test", author="Author", scenes=[mock_scene])

            mock_parser_instance = mock_parser.return_value
            mock_parser_instance.parse_file.return_value = mock_script

            # Process in dry run mode with force=False
            result = await cmd.analyze(
                path=temp_fountain_file.parent, force=False, dry_run=True
            )

            # No scenes should be updated since they don't need it
            assert len(result.files) == 1
            assert not result.files[0].updated
            assert result.files[0].scenes_updated == 0

    @pytest.mark.asyncio
    async def test_normal_processing_scenes_not_needing_update(
        self, temp_fountain_file
    ):
        """Test normal processing when scenes don't need update (line 284->283)."""
        cmd = AnalyzeCommand()

        # Mock parser to return a script with scenes that don't need update
        with patch("scriptrag.api.analyze.FountainParser") as mock_parser:
            mock_scene = Scene(
                number=1,
                heading="INT. TEST - DAY",
                content="Test content",
                original_text="Test",
                content_hash="hash123",
                boneyard_metadata={
                    "analyzed_at": "2024-01-01T00:00:00",
                    "analyzers": {},  # No analyzers, so no update needed
                },
            )

            mock_script = Script(title="Test", author="Author", scenes=[mock_scene])

            mock_parser_instance = mock_parser.return_value
            mock_parser_instance.parse_file.return_value = mock_script

            # Process in normal mode with force=False
            result = await cmd.analyze(
                path=temp_fountain_file.parent, force=False, dry_run=False
            )

            # No scenes should be processed since they don't need it
            assert len(result.files) == 1
            assert not result.files[0].updated
            assert result.files[0].scenes_updated == 0

    @pytest.mark.asyncio
    async def test_load_analyzer_with_config_parameter(self):
        """Test load_analyzer method with config parameter for complete coverage."""
        cmd = AnalyzeCommand()

        class ConfigurableAnalyzer(BaseSceneAnalyzer):
            name = "configurable"

            def __init__(self, config=None):
                super().__init__(config)
                self.config = config or {}

            async def analyze(self, scene):
                return {"config_used": bool(self.config)}

        # Register and load with config
        cmd.register_analyzer("configurable", ConfigurableAnalyzer)
        config = {"setting": "value"}
        cmd.load_analyzer("configurable", config)

        assert len(cmd.analyzers) == 1
        # Note: Current implementation doesn't pass config to registered analyzers
        # This test documents the current behavior
        assert cmd.analyzers[0].config == {}  # Default empty config

    @pytest.mark.asyncio
    async def test_edge_case_relationships_analyzer_with_existing_bible_chars(
        self, temp_fountain_file
    ):
        """Test that analyzer with existing bible_characters doesn't get reloaded."""

        class RelationshipsAnalyzerWithData(BaseSceneAnalyzer):
            name = "relationships"
            bible_characters: ClassVar = {"existing": "data"}  # Already has data

            def _build_alias_index(self):
                self.alias_built = True

            async def analyze(self, scene):
                return {"relationships": "analyzed"}

        analyzer = RelationshipsAnalyzerWithData()
        cmd = AnalyzeCommand(analyzers=[analyzer])

        with patch("scriptrag.api.analyze.load_bible_metadata") as mock_load:
            result = await cmd.analyze(path=temp_fountain_file.parent, force=True)

            # _load_bible_metadata not called since bible_characters already exists
            mock_load.assert_not_called()
            assert analyzer.bible_characters == {"existing": "data"}
            assert result.files[0].updated

    def test_scene_needs_update_edge_cases(self):
        """Test scene_needs_update function edge cases for complete coverage."""
        cmd = AnalyzeCommand()

        # Test with None scene
        assert scene_needs_update(None, cmd.analyzers) is False

        # Test with empty metadata dict but no analyzed_at
        scene_no_analyzed_at = Scene(
            number=1,
            heading="INT. TEST - DAY",
            content="Test content",
            original_text="Test",
            content_hash="hash123",
            boneyard_metadata={},  # Empty dict, no analyzed_at
        )
        assert scene_needs_update(scene_no_analyzed_at, cmd.analyzers) is True

    @pytest.mark.asyncio
    async def test_load_bible_metadata_with_dict_metadata(self, tmp_path):
        """Test Bible metadata loading when metadata is already a dict (not string)."""
        cmd = AnalyzeCommand()
        script_path = tmp_path / "test.fountain"

        bible_metadata = {
            "version": 1,
            "characters": [{"canonical": "JANE", "aliases": ["MS. JANE"]}],
        }

        with patch(
            "scriptrag.api.database_operations.DatabaseOperations"
        ) as mock_db_ops_class:
            with patch("scriptrag.config.get_settings"):
                mock_db_ops = mock_db_ops_class.return_value
                mock_db_ops.check_database_exists.return_value = True

                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                # Return metadata as dict directly (not JSON string)
                mock_cursor.fetchone.return_value = (
                    {
                        "bible.characters": bible_metadata
                    },  # Direct dict, not JSON string
                )

                mock_db_ops.transaction.return_value.__enter__ = Mock(
                    return_value=mock_conn
                )
                mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

                result = await load_bible_metadata(script_path)

                assert result == bible_metadata

    @pytest.mark.asyncio
    async def test_file_result_error_handling(self):
        """Test FileResult class with error scenarios."""
        from pathlib import Path

        from scriptrag.api.analyze import FileResult

        # Test FileResult with error
        result = FileResult(
            path=Path("test.fountain"), updated=False, error="Parse failed"
        )

        assert result.path == Path("test.fountain")
        assert not result.updated
        assert result.scenes_updated == 0  # Default value
        assert result.error == "Parse failed"

        # Test FileResult with custom scenes_updated
        result2 = FileResult(
            path=Path("test2.fountain"), updated=True, scenes_updated=5
        )

        assert result2.scenes_updated == 5
        assert result2.error is None  # Default value

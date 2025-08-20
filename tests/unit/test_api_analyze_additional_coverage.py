"""Additional tests for analyze.py to improve coverage."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from scriptrag.analyzers.base import BaseSceneAnalyzer
from scriptrag.api.analyze import AnalyzeCommand
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

                result = await cmd._load_bible_metadata(script_path)

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

                result = await cmd._load_bible_metadata(script_path)

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

                result = await cmd._load_bible_metadata(script_path)

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

                result = await cmd._load_bible_metadata(script_path)

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

                result = await cmd._load_bible_metadata(script_path)

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

        with patch.object(cmd, "_load_bible_metadata", return_value=bible_metadata):
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

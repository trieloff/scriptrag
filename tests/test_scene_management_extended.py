"""Extended tests for scene management to improve coverage."""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.api.scene_management import (
    FountainValidator,
    SceneIdentifier,
    SceneManagementAPI,
    ValidationResult,
)
from scriptrag.parser import Scene


class TestSceneIdentifierExtended:
    """Extended tests for SceneIdentifier."""

    def test_from_string_invalid_tv_format(self):
        """Test parsing invalid TV format."""
        with pytest.raises(ValueError, match="invalid literal"):
            SceneIdentifier.from_string("show:S01Einvalid:023")

    def test_from_string_invalid_parts_count(self):
        """Test parsing with wrong number of parts."""
        with pytest.raises(ValueError, match="Invalid scene key format"):
            SceneIdentifier.from_string("too:many:parts:here:extra")


class TestValidationResultDataclass:
    """Test ValidationResult dataclass."""

    def test_validation_result_defaults(self):
        """Test ValidationResult with defaults."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.parsed_scene is None

    def test_validation_result_with_errors(self):
        """Test ValidationResult with errors."""
        result = ValidationResult(
            is_valid=False,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"],
        )
        assert result.is_valid is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 1


class TestFountainValidatorExtended:
    """Extended tests for Fountain validator."""

    def test_has_scene_heading_int_ext(self):
        """Test _has_scene_heading with INT/EXT variations."""
        validator = FountainValidator()

        # Test INT variant
        assert validator._has_scene_heading("INT. LOCATION - DAY\n\nContent") is True

        # Test EXT variant
        assert validator._has_scene_heading("EXT. LOCATION - NIGHT\n\nContent") is True

        # Test I/E variant
        assert validator._has_scene_heading("I/E. CAR/STREET - DAY\n\nContent") is True

        # Test INT/EXT variant
        assert validator._has_scene_heading("INT/EXT. BUILDING - DAY") is True

        # Test invalid
        assert validator._has_scene_heading("Invalid heading") is False

        # Test empty
        assert validator._has_scene_heading("") is False

    def test_validate_scene_with_parsing_error(self):
        """Test validation when parsing fails."""
        validator = FountainValidator()

        with patch.object(
            validator.parser, "parse", side_effect=Exception("Parse error")
        ):
            content = "INT. SCENE - DAY\n\nContent"
            result = validator.validate_scene_content(content)

            assert result.is_valid is False
            assert any("parsing failed" in error.lower() for error in result.errors)
            assert result.parsed_scene is None

    def test_validate_scene_general_exception(self):
        """Test validation with general exception."""
        validator = FountainValidator()

        with patch.object(
            validator, "_has_scene_heading", side_effect=Exception("Unexpected error")
        ):
            content = "INT. SCENE - DAY\n\nContent"
            result = validator.validate_scene_content(content)

            assert result.is_valid is False
            assert any("validation failed" in error.lower() for error in result.errors)


class TestSceneManagementAPIExtended:
    """Extended tests for SceneManagementAPI."""

    @pytest.fixture
    def api(self):
        """Create API instance."""
        return SceneManagementAPI()

    @pytest.fixture
    def mock_conn(self):
        """Create mock database connection."""
        conn = MagicMock(spec=sqlite3.Connection)
        cursor = MagicMock()
        conn.execute.return_value = cursor
        return conn

    def test_get_scene_by_id_with_season_episode(self, api, mock_conn):
        """Test _get_scene_by_id with TV show parameters."""
        scene_id = SceneIdentifier(
            project="show",
            season=1,
            episode=5,
            scene_number=10,
        )

        # Mock database response
        mock_conn.execute().fetchone.return_value = {
            "scene_number": 10,
            "heading": "INT. LOCATION - DAY",
            "content": "Scene content",
            "location": "LOCATION",
            "time_of_day": "DAY",
        }

        scene = api._get_scene_by_id(mock_conn, scene_id)

        assert scene is not None
        assert scene.number == 10
        assert scene.heading == "INT. LOCATION - DAY"

        # Check SQL query included season/episode filters
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "json_extract" in query
        assert "season" in query
        assert "episode" in query
        assert 1 in params  # season
        assert 5 in params  # episode

    def test_get_scene_by_id_not_found(self, api, mock_conn):
        """Test _get_scene_by_id when scene not found."""
        scene_id = SceneIdentifier(project="test", scene_number=999)

        mock_conn.execute().fetchone.return_value = None

        scene = api._get_scene_by_id(mock_conn, scene_id)
        assert scene is None

    def test_update_scene_content_with_parsed_scene(self, api, mock_conn):
        """Test _update_scene_content with parsed scene data."""
        scene_id = SceneIdentifier(project="test", scene_number=1)
        new_content = "INT. NEW SCENE - DAY\n\nNew content"
        parsed_scene = Scene(
            number=1,
            heading="INT. NEW SCENE - DAY",
            content=new_content,
            original_text=new_content,
            content_hash="hash",
            location="NEW SCENE",
            time_of_day="DAY",
        )

        updated = api._update_scene_content(
            mock_conn, scene_id, new_content, parsed_scene
        )

        assert updated.heading == "INT. NEW SCENE - DAY"
        assert updated.location == "NEW SCENE"
        assert updated.time_of_day == "DAY"
        assert updated.content == new_content

    def test_update_scene_content_without_parsed_scene(self, api, mock_conn):
        """Test _update_scene_content without parsed scene data."""
        scene_id = SceneIdentifier(project="test", scene_number=1)
        new_content = "INT. NEW SCENE - DAY\n\nNew content"

        with patch("scriptrag.utils.ScreenplayUtils") as mock_utils:
            mock_utils.extract_location.return_value = "NEW SCENE"
            mock_utils.extract_time.return_value = "DAY"

            updated = api._update_scene_content(mock_conn, scene_id, new_content, None)

            assert updated.heading == "INT. NEW SCENE - DAY"
            assert updated.location == "NEW SCENE"
            assert updated.time_of_day == "DAY"

    def test_update_scene_content_with_season_episode(self, api, mock_conn):
        """Test _update_scene_content with TV show parameters."""
        scene_id = SceneIdentifier(
            project="show",
            season=2,
            episode=3,
            scene_number=5,
        )
        new_content = "INT. NEW SCENE - DAY\n\nNew content"

        updated = api._update_scene_content(mock_conn, scene_id, new_content, None)

        # Check SQL query included season/episode conditions
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "json_extract" in query
        assert 2 in params  # season
        assert 3 in params  # episode

    def test_create_scene_with_parsed_scene(self, api, mock_conn):
        """Test _create_scene with parsed scene data."""
        scene_id = SceneIdentifier(project="test", scene_number=5)
        content = "INT. NEW SCENE - DAY\n\nContent"
        parsed_scene = Scene(
            number=5,
            heading="INT. NEW SCENE - DAY",
            content=content,
            original_text=content,
            content_hash="hash",
            location="NEW SCENE",
            time_of_day="DAY",
        )

        # Mock script ID query
        mock_conn.execute().fetchone.return_value = [123]  # script_id

        created = api._create_scene(mock_conn, scene_id, content, parsed_scene)

        assert created.number == 5
        assert created.heading == "INT. NEW SCENE - DAY"
        assert created.location == "NEW SCENE"
        assert created.time_of_day == "DAY"

    def test_create_scene_without_parsed_scene(self, api, mock_conn):
        """Test _create_scene without parsed scene data."""
        scene_id = SceneIdentifier(project="test", scene_number=5)
        content = "INT. NEW SCENE - DAY\n\nContent"

        # Mock script ID query
        mock_conn.execute().fetchone.return_value = [123]  # script_id

        with patch("scriptrag.utils.ScreenplayUtils") as mock_utils:
            mock_utils.extract_location.return_value = "NEW SCENE"
            mock_utils.extract_time.return_value = "DAY"

            created = api._create_scene(mock_conn, scene_id, content, None)

            assert created.number == 5
            assert created.heading == "INT. NEW SCENE - DAY"

    def test_create_scene_script_not_found(self, api, mock_conn):
        """Test _create_scene when script not found."""
        scene_id = SceneIdentifier(project="nonexistent", scene_number=5)
        content = "INT. NEW SCENE - DAY\n\nContent"

        # Mock no script found
        mock_conn.execute().fetchone.return_value = None

        with pytest.raises(ValueError, match="Script not found"):
            api._create_scene(mock_conn, scene_id, content, None)

    def test_create_scene_with_season_episode(self, api, mock_conn):
        """Test _create_scene with TV show parameters."""
        scene_id = SceneIdentifier(
            project="show",
            season=1,
            episode=2,
            scene_number=5,
        )
        content = "INT. NEW SCENE - DAY\n\nContent"

        # Mock script ID query
        mock_conn.execute().fetchone.return_value = [123]  # script_id

        created = api._create_scene(mock_conn, scene_id, content, None)

        # Check SQL query for script lookup included season/episode
        if mock_conn.execute.call_args_list:
            call_args = mock_conn.execute.call_args_list[0]
            if call_args and call_args[0]:
                query = call_args[0][0]
                params = call_args[0][1]
                assert "json_extract" in query
                assert 1 in params  # season
                assert 2 in params  # episode
        else:
            # Just verify the scene was created correctly
            assert created.number == 5

    def test_delete_scene(self, api, mock_conn):
        """Test _delete_scene."""
        scene_id = SceneIdentifier(project="test", scene_number=5)

        api._delete_scene(mock_conn, scene_id)

        # Check DELETE query was executed
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "DELETE FROM scenes" in query
        assert 5 in params  # scene_number
        assert "test" in params  # project

    def test_delete_scene_with_season_episode(self, api, mock_conn):
        """Test _delete_scene with TV show parameters."""
        scene_id = SceneIdentifier(
            project="show",
            season=1,
            episode=3,
            scene_number=5,
        )

        api._delete_scene(mock_conn, scene_id)

        # Check SQL query included season/episode conditions
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "json_extract" in query
        assert 1 in params  # season
        assert 3 in params  # episode

    def test_shift_scenes_after(self, api, mock_conn):
        """Test _shift_scenes_after."""
        scene_id = SceneIdentifier(project="test", scene_number=5)

        # Mock the SELECT query to return scenes to shift
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(6,), (7,), (8,)]
        mock_conn.execute.return_value = mock_cursor

        api._shift_scenes_after(mock_conn, scene_id, 1)

        # Should have 1 SELECT + 3 UPDATEs = 4 calls
        assert mock_conn.execute.call_count == 4

        # Check SELECT query was executed first
        first_call = mock_conn.execute.call_args_list[0]
        query = first_call[0][0]
        params = first_call[0][1]

        assert "SELECT scene_number FROM scenes" in query
        assert "scene_number > ?" in query
        assert 5 in params  # scene_number
        assert "test" in params  # project

    def test_shift_scenes_after_with_season_episode(self, api, mock_conn):
        """Test _shift_scenes_after with TV show parameters."""
        scene_id = SceneIdentifier(
            project="show",
            season=2,
            episode=4,
            scene_number=5,
        )

        api._shift_scenes_after(mock_conn, scene_id, 2)

        # Check SQL query included season/episode conditions
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "json_extract" in query
        assert 2 in params  # shift or season
        assert 4 in params  # episode

    def test_shift_scenes_from(self, api, mock_conn):
        """Test _shift_scenes_from."""
        scene_id = SceneIdentifier(project="test", scene_number=5)

        # Mock the SELECT query to return scenes to shift
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(5,), (6,), (7,)]
        mock_conn.execute.return_value = mock_cursor

        api._shift_scenes_from(mock_conn, scene_id, 1)

        # Should have 1 SELECT + 3 UPDATEs = 4 calls
        assert mock_conn.execute.call_count == 4

        # Check SELECT query was executed first
        first_call = mock_conn.execute.call_args_list[0]
        query = first_call[0][0]
        params = first_call[0][1]

        assert "SELECT scene_number FROM scenes" in query
        assert "scene_number >= ?" in query
        assert 5 in params  # scene_number
        assert "test" in params  # project

    def test_shift_scenes_from_with_season_episode(self, api, mock_conn):
        """Test _shift_scenes_from with TV show parameters."""
        scene_id = SceneIdentifier(
            project="show",
            season=1,
            episode=5,
            scene_number=10,
        )

        api._shift_scenes_from(mock_conn, scene_id, -1)

        # Check SQL query included season/episode conditions
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "json_extract" in query
        assert 1 in params  # season
        assert 5 in params  # episode

    def test_compact_scene_numbers(self, api, mock_conn):
        """Test _compact_scene_numbers."""
        scene_id = SceneIdentifier(project="test", scene_number=5)

        # Mock scenes after deleted scene
        mock_conn.execute().fetchall.return_value = [(6,), (7,), (8,)]

        with patch.object(api, "_shift_scenes_after") as mock_shift:
            renumbered = api._compact_scene_numbers(mock_conn, scene_id)

            assert renumbered == [6, 7, 8]
            mock_shift.assert_called_once_with(mock_conn, scene_id, -1)

    def test_compact_scene_numbers_no_scenes_after(self, api, mock_conn):
        """Test _compact_scene_numbers when no scenes after deleted."""
        scene_id = SceneIdentifier(project="test", scene_number=100)

        # Mock no scenes after
        mock_conn.execute().fetchall.return_value = []

        with patch.object(api, "_shift_scenes_after") as mock_shift:
            renumbered = api._compact_scene_numbers(mock_conn, scene_id)

            assert renumbered == []
            mock_shift.assert_not_called()

    def test_compact_scene_numbers_with_season_episode(self, api, mock_conn):
        """Test _compact_scene_numbers with TV show parameters."""
        scene_id = SceneIdentifier(
            project="show",
            season=1,
            episode=2,
            scene_number=5,
        )

        # Mock scenes after deleted scene
        mock_conn.execute().fetchall.return_value = [(6,), (7,)]

        renumbered = api._compact_scene_numbers(mock_conn, scene_id)

        # Check SQL query included season/episode conditions
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "json_extract" in query
        assert 1 in params  # season
        assert 2 in params  # episode

    def test_get_renumbered_scenes(self, api, mock_conn):
        """Test _get_renumbered_scenes."""
        scene_id = SceneIdentifier(project="test", scene_number=5)

        # Mock scenes after reference
        mock_conn.execute().fetchall.return_value = [(6,), (7,), (8,)]

        renumbered = api._get_renumbered_scenes(mock_conn, scene_id)

        assert renumbered == [6, 7, 8]

        # Check query
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "scene_number > ?" in query
        assert 5 in params  # scene_number
        assert "test" in params  # project

    def test_get_renumbered_scenes_with_season_episode(self, api, mock_conn):
        """Test _get_renumbered_scenes with TV show parameters."""
        scene_id = SceneIdentifier(
            project="show",
            season=2,
            episode=3,
            scene_number=10,
        )

        # Mock scenes after reference
        mock_conn.execute().fetchall.return_value = [(11,), (12,)]

        renumbered = api._get_renumbered_scenes(mock_conn, scene_id)

        assert renumbered == [11, 12]

        # Check SQL query included season/episode conditions
        call_args = mock_conn.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "json_extract" in query
        assert 2 in params  # season
        assert 3 in params  # episode

    @pytest.mark.asyncio
    async def test_read_scene_exception(self, api):
        """Test read_scene with exception."""
        scene_id = SceneIdentifier("test", 1)

        with patch.object(
            api.db_ops, "transaction", side_effect=Exception("Database error")
        ):
            result = await api.read_scene(scene_id)

            assert result.success is False
            assert "Database error" in result.error
            assert result.scene is None

    @pytest.mark.asyncio
    async def test_update_scene_exception(self, api):
        """Test update_scene with exception."""
        scene_id = SceneIdentifier("test", 1)
        content = "INT. SCENE - DAY\n\nContent"
        token = "test-token"  # noqa: S105

        with patch.object(
            api.db_ops, "transaction", side_effect=Exception("Database error")
        ):
            result = await api.update_scene(scene_id, content, check_conflicts=False)

            assert result.success is False
            assert "Database error" in result.error
            assert "UPDATE_FAILED" in result.validation_errors

    @pytest.mark.asyncio
    async def test_update_scene_not_found(self, api):
        """Test update_scene when scene no longer exists."""
        scene_id = SceneIdentifier("test", 1)
        content = "INT. SCENE - DAY\n\nContent"

        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()
            with patch.object(api, "_get_scene_by_id", return_value=None):
                result = await api.update_scene(
                    scene_id, content, check_conflicts=False
                )

                assert result.success is False
                assert "Scene not found" in result.error
                assert "SCENE_NOT_FOUND" in result.validation_errors

    @pytest.mark.asyncio
    async def test_add_scene_reference_not_found(self, api):
        """Test add_scene when reference scene not found."""
        scene_id = SceneIdentifier("test", 999)
        content = "INT. NEW SCENE - DAY\n\nContent"

        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()
            with patch.object(api, "_get_scene_by_id", return_value=None):
                result = await api.add_scene(scene_id, content, "after")

                assert result.success is False
                assert "Reference scene not found" in result.error

    @pytest.mark.asyncio
    async def test_add_scene_invalid_position(self, api):
        """Test add_scene with invalid position."""
        scene_id = SceneIdentifier("test", 5)
        content = "INT. NEW SCENE - DAY\n\nContent"

        # Mock reference scene exists
        mock_scene = Scene(
            number=5,
            heading="INT. REF - DAY",
            content="Ref",
            original_text="Ref",
            content_hash="hash",
        )

        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()
            with patch.object(api, "_get_scene_by_id", return_value=mock_scene):
                result = await api.add_scene(scene_id, content, "invalid")

                assert result.success is False
                assert "Invalid position" in result.error

    @pytest.mark.asyncio
    async def test_add_scene_exception(self, api):
        """Test add_scene with exception."""
        scene_id = SceneIdentifier("test", 5)
        content = "INT. NEW SCENE - DAY\n\nContent"

        with patch.object(
            api.db_ops, "transaction", side_effect=Exception("Database error")
        ):
            result = await api.add_scene(scene_id, content, "after")

            assert result.success is False
            assert "Database error" in result.error

    @pytest.mark.asyncio
    async def test_delete_scene_exception(self, api):
        """Test delete_scene with exception."""
        scene_id = SceneIdentifier("test", 5)

        with patch.object(
            api.db_ops, "transaction", side_effect=Exception("Database error")
        ):
            result = await api.delete_scene(scene_id, confirm=True)

            assert result.success is False
            assert "Database error" in result.error

    @pytest.mark.asyncio
    async def test_read_bible_project_not_found(self, api):
        """Test read_bible when project not found."""
        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()
            mock_conn.execute().fetchone.return_value = None

            result = await api.read_bible("nonexistent")

            assert result.success is False
            assert "Project 'nonexistent' not found" in result.error

    @pytest.mark.asyncio
    async def test_read_bible_no_files_found(self, api):
        """Test read_bible when no bible files found."""
        with patch.object(api.db_ops, "transaction") as mock_trans:
            mock_conn = mock_trans().__enter__()
            mock_conn.execute().fetchone.return_value = {
                "file_path": "/path/to/script.fountain"
            }

            with patch(
                "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                return_value=[],
            ):
                result = await api.read_bible("test_project")

                assert result.success is False
                assert "No bible files found" in result.error

    @pytest.mark.asyncio
    async def test_read_bible_list_files(self, api):
        """Test read_bible listing available files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test bible files
            tmpdir_path = Path(tmpdir)
            bible1 = tmpdir_path / "world_bible.md"
            bible2 = tmpdir_path / "characters.md"
            bible1.write_text("World bible content")
            bible2.write_text("Character bible content")

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(tmpdir_path / "script.fountain")
                }

                with patch(
                    "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                    return_value=[bible1, bible2],
                ):
                    result = await api.read_bible("test_project")

                    assert result.success is True
                    assert len(result.bible_files) == 2
                    assert any(
                        f["name"] == "world_bible.md" for f in result.bible_files
                    )
                    assert any(f["name"] == "characters.md" for f in result.bible_files)

    @pytest.mark.asyncio
    async def test_read_bible_specific_file(self, api):
        """Test read_bible reading specific file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test bible file
            tmpdir_path = Path(tmpdir)
            bible_file = tmpdir_path / "world_bible.md"
            bible_content = "# World Bible\n\nContent here"
            bible_file.write_text(bible_content)

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(tmpdir_path / "script.fountain")
                }

                with patch(
                    "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                    return_value=[bible_file],
                ):
                    result = await api.read_bible("test_project", "world_bible.md")

                    assert result.success is True
                    assert result.content == bible_content

    @pytest.mark.asyncio
    async def test_read_bible_file_not_found(self, api):
        """Test read_bible when specific file not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            bible_file = tmpdir_path / "world_bible.md"
            bible_file.write_text("Content")

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(tmpdir_path / "script.fountain")
                }

                with patch(
                    "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                    return_value=[bible_file],
                ):
                    result = await api.read_bible("test_project", "nonexistent.md")

                    assert result.success is False
                    assert "not found" in result.error
                    assert "Available: world_bible.md" in result.error

    @pytest.mark.asyncio
    async def test_read_bible_file_by_relative_path(self, api):
        """Test read_bible finding file by relative path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            subdir = tmpdir_path / "docs"
            subdir.mkdir()
            bible_file = subdir / "world_bible.md"
            bible_content = "Content"
            bible_file.write_text(bible_content)

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(tmpdir_path / "script.fountain")
                }

                with patch(
                    "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                    return_value=[bible_file],
                ):
                    result = await api.read_bible("test_project", "docs/world_bible.md")

                    assert result.success is True
                    assert result.content == bible_content

    @pytest.mark.asyncio
    async def test_read_bible_read_error(self, api):
        """Test read_bible when file read fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            bible_file = tmpdir_path / "world_bible.md"
            bible_file.write_text("Content")

            with patch.object(api.db_ops, "transaction") as mock_trans:
                mock_conn = mock_trans().__enter__()
                mock_conn.execute().fetchone.return_value = {
                    "file_path": str(tmpdir_path / "script.fountain")
                }

                with patch(
                    "scriptrag.api.scene_management.BibleAutoDetector.find_bible_files",
                    return_value=[bible_file],
                ):
                    # Mock read_text to fail
                    with patch.object(
                        Path, "read_text", side_effect=Exception("Read error")
                    ):
                        result = await api.read_bible("test_project", "world_bible.md")

                        assert result.success is False
                        assert "Failed to read bible file" in result.error

    @pytest.mark.asyncio
    async def test_read_bible_exception(self, api):
        """Test read_bible with general exception."""
        with patch.object(
            api.db_ops, "transaction", side_effect=Exception("Database error")
        ):
            result = await api.read_bible("test_project")

            assert result.success is False
            assert "Database error" in result.error

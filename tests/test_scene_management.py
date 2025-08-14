"""Tests for AI-friendly scene management functionality."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from scriptrag.api.scene_management import (
    FountainValidator,
    SceneIdentifier,
    SceneManagementAPI,
)
from scriptrag.parser import Scene


class TestSceneIdentifier:
    """Test scene identifier functionality."""

    def test_tv_show_identifier(self):
        """Test identifier for TV show scenes."""
        scene_id = SceneIdentifier(
            project="breaking_bad",
            season=1,
            episode=5,
            scene_number=42,
        )
        assert scene_id.key == "breaking_bad:S01E05:042"

    def test_feature_film_identifier(self):
        """Test identifier for feature film scenes."""
        scene_id = SceneIdentifier(
            project="inception",
            scene_number=23,
        )
        assert scene_id.key == "inception:023"

    def test_from_string_tv_format(self):
        """Test parsing TV show scene key."""
        scene_id = SceneIdentifier.from_string("breaking_bad:S02E07:015")
        assert scene_id.project == "breaking_bad"
        assert scene_id.season == 2
        assert scene_id.episode == 7
        assert scene_id.scene_number == 15

    def test_from_string_feature_format(self):
        """Test parsing feature film scene key."""
        scene_id = SceneIdentifier.from_string("inception:042")
        assert scene_id.project == "inception"
        assert scene_id.season is None
        assert scene_id.episode is None
        assert scene_id.scene_number == 42

    def test_from_string_invalid_format(self):
        """Test parsing invalid scene key."""
        with pytest.raises(ValueError, match="Invalid scene key format"):
            SceneIdentifier.from_string("invalid:key:format:extra")


class TestFountainValidator:
    """Test Fountain format validation."""

    def test_valid_scene_with_heading(self):
        """Test validating scene with proper heading."""
        validator = FountainValidator()
        content = """INT. COFFEE SHOP - DAY

Walter enters, looking tired.

WALTER
I need coffee."""

        result = validator.validate_scene_content(content)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_missing_scene_heading(self):
        """Test validating scene without heading."""
        validator = FountainValidator()
        content = """Walter enters, looking tired.

WALTER
I need coffee."""

        result = validator.validate_scene_content(content)
        assert result.is_valid is False
        assert any("heading" in error.lower() for error in result.errors)

    def test_external_scene_heading(self):
        """Test validating external scene heading."""
        validator = FountainValidator()
        content = """EXT. CITY STREET - NIGHT

Rain falls on empty streets."""

        result = validator.validate_scene_content(content)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_intercut_scene_heading(self):
        """Test validating I/E scene heading."""
        validator = FountainValidator()
        content = """I/E. CAR/STREET - DAY

Through the windshield we see the city."""

        result = validator.validate_scene_content(content)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_scene_with_only_heading(self):
        """Test scene with only heading generates warning."""
        validator = FountainValidator()
        content = """INT. EMPTY ROOM - DAY"""

        result = validator.validate_scene_content(content)
        assert result.is_valid is True  # Valid but with warning
        assert len(result.warnings) > 0
        assert any("no content" in warning.lower() for warning in result.warnings)

    def test_invalid_fountain_format(self):
        """Test invalid Fountain format."""
        validator = FountainValidator()
        content = """Not a valid scene heading

Some content here."""

        result = validator.validate_scene_content(content)
        assert result.is_valid is False
        assert len(result.errors) > 0


class TestSceneManagementAPI:
    """Test scene management API."""

    @pytest.fixture
    def mock_db_ops(self):
        """Create mock database operations."""
        with patch("scriptrag.api.scene_management.DatabaseOperations") as mock:
            yield mock

    @pytest.fixture
    def api(self, mock_db_ops):
        """Create API instance with mocked dependencies."""
        return SceneManagementAPI()

    @pytest.mark.asyncio
    async def test_read_scene_success(self, api):
        """Test successful scene read."""
        scene_id = SceneIdentifier("test_project", 1)

        # Mock the database response
        mock_scene = Scene(
            number=1,
            heading="INT. TEST SCENE - DAY",
            content="Test content",
            original_text="Test content",
            content_hash="hash123",
        )

        with patch.object(api, "_get_scene_by_id", return_value=mock_scene):
            result = await api.read_scene(scene_id, "test_reader")

        assert result.success is True
        assert result.error is None
        assert result.scene == mock_scene
        assert result.last_read is not None

    @pytest.mark.asyncio
    async def test_read_scene_not_found(self, api):
        """Test reading non-existent scene."""
        scene_id = SceneIdentifier("test_project", 999)

        with patch.object(api, "_get_scene_by_id", return_value=None):
            result = await api.read_scene(scene_id, "test_reader")

        assert result.success is False
        assert "not found" in result.error.lower()
        assert result.scene is None
        assert result.last_read is None

    @pytest.mark.asyncio
    async def test_update_scene_success(self, api):
        """Test successful scene update without conflict checking."""
        scene_id = SceneIdentifier("test_project", 1)
        new_content = """INT. UPDATED SCENE - DAY

Updated content here."""

        # Mock current scene
        mock_scene = Scene(
            number=1,
            heading="INT. TEST SCENE - DAY",
            content="Original content",
            original_text="Original content",
            content_hash="original_hash",
        )

        # Mock updated scene
        updated_scene = Scene(
            number=1,
            heading="INT. UPDATED SCENE - DAY",
            content=new_content,
            original_text=new_content,
            content_hash="new_hash",
        )

        with patch.object(api, "_get_scene_by_id", return_value=mock_scene):
            with patch.object(api, "_update_scene_content", return_value=updated_scene):
                # Update without conflict checking (simple mode)
                result = await api.update_scene(
                    scene_id, new_content, check_conflicts=False
                )

        assert result.success is True
        assert result.error is None
        assert result.updated_scene == updated_scene
        assert len(result.validation_errors) == 0

    @pytest.mark.asyncio
    async def test_update_scene_invalid_fountain(self, api):
        """Test updating scene with invalid Fountain format."""
        scene_id = SceneIdentifier("test_project", 1)
        invalid_content = "Not a valid scene"

        result = await api.update_scene(
            scene_id, invalid_content, check_conflicts=False
        )

        assert result.success is False
        assert "Invalid Fountain format" in result.error
        assert len(result.validation_errors) > 0

    @pytest.mark.asyncio
    async def test_update_scene_with_safe_mode_missing_timestamp(self, api):
        """Test updating scene with safe mode but missing timestamp."""
        scene_id = SceneIdentifier("test_project", 1)
        new_content = """INT. UPDATED SCENE - DAY

Updated content."""

        # Mock that scene exists
        mock_scene = Scene(
            number=1,
            heading="INT. TEST SCENE - DAY",
            content="Original content",
            original_text="Original content",
            content_hash="original_hash",
        )

        with patch.object(api, "_get_scene_by_id", return_value=mock_scene):
            # Try to update with conflict checking but no last_read timestamp
            result = await api.update_scene(
                scene_id, new_content, check_conflicts=True, last_read=None
            )

        assert result.success is False
        assert "last_read timestamp required" in result.error
        assert "MISSING_TIMESTAMP" in result.validation_errors

    @pytest.mark.asyncio
    async def test_update_scene_concurrent_modification(self, api):
        """Test concurrent modification detection with safe mode."""
        scene_id = SceneIdentifier("test_project", 1)
        new_content = """INT. UPDATED SCENE - DAY

Updated content."""

        # Timestamp when scene was last read
        last_read = datetime.utcnow() - timedelta(minutes=5)

        # Mock scene that was modified after the read
        mock_scene = Scene(
            number=1,
            heading="INT. TEST SCENE - DAY",
            content="Modified by another process",
            original_text="Modified by another process",
            content_hash="different_hash",
        )

        # Mock that scene was modified after our last read
        last_modified = datetime.utcnow()  # Modified just now

        with patch.object(api, "_get_scene_by_id", return_value=mock_scene):
            with patch.object(api, "_get_last_modified", return_value=last_modified):
                result = await api.update_scene(
                    scene_id, new_content, check_conflicts=True, last_read=last_read
                )

        assert result.success is False
        assert "modified since last read" in result.error.lower()
        assert "CONCURRENT_MODIFICATION" in result.validation_errors

    @pytest.mark.asyncio
    async def test_add_scene_after(self, api):
        """Test adding scene after reference scene."""
        reference_id = SceneIdentifier("test_project", 5)
        content = """INT. NEW SCENE - DAY

New scene content."""

        # Mock reference scene exists
        mock_reference = Scene(
            number=5,
            heading="INT. REFERENCE - DAY",
            content="Reference",
            original_text="Reference",
            content_hash="ref_hash",
        )

        # Mock created scene
        created_scene = Scene(
            number=6,
            heading="INT. NEW SCENE - DAY",
            content=content,
            original_text=content,
            content_hash="new_hash",
        )

        with patch.object(api, "_get_scene_by_id", return_value=mock_reference):
            with patch.object(api, "_shift_scenes_after") as mock_shift:
                with patch.object(api, "_create_scene", return_value=created_scene):
                    with patch.object(
                        api, "_get_renumbered_scenes", return_value=[7, 8, 9]
                    ):
                        result = await api.add_scene(reference_id, content, "after")

        assert result.success is True
        assert result.error is None
        assert result.created_scene == created_scene
        assert result.renumbered_scenes == [7, 8, 9]
        mock_shift.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_scene_before(self, api):
        """Test adding scene before reference scene."""
        reference_id = SceneIdentifier("test_project", 5)
        content = """INT. NEW SCENE - DAY

New scene content."""

        # Mock reference scene exists
        mock_reference = Scene(
            number=5,
            heading="INT. REFERENCE - DAY",
            content="Reference",
            original_text="Reference",
            content_hash="ref_hash",
        )

        # Mock created scene
        created_scene = Scene(
            number=5,
            heading="INT. NEW SCENE - DAY",
            content=content,
            original_text=content,
            content_hash="new_hash",
        )

        with patch.object(api, "_get_scene_by_id", return_value=mock_reference):
            with patch.object(api, "_shift_scenes_from") as mock_shift:
                with patch.object(api, "_create_scene", return_value=created_scene):
                    with patch.object(
                        api, "_get_renumbered_scenes", return_value=[6, 7, 8]
                    ):
                        result = await api.add_scene(reference_id, content, "before")

        assert result.success is True
        assert result.error is None
        assert result.created_scene == created_scene
        assert result.renumbered_scenes == [6, 7, 8]
        mock_shift.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_scene_invalid_fountain(self, api):
        """Test adding scene with invalid Fountain."""
        reference_id = SceneIdentifier("test_project", 5)
        invalid_content = "Not a valid scene"

        result = await api.add_scene(reference_id, invalid_content, "after")

        assert result.success is False
        assert "Invalid Fountain format" in result.error

    @pytest.mark.asyncio
    async def test_delete_scene_without_confirm(self, api):
        """Test delete requires confirmation."""
        scene_id = SceneIdentifier("test_project", 5)

        result = await api.delete_scene(scene_id, confirm=False)

        assert result.success is False
        assert "confirm=True" in result.error

    @pytest.mark.asyncio
    async def test_delete_scene_success(self, api):
        """Test successful scene deletion."""
        scene_id = SceneIdentifier("test_project", 5)

        # Mock scene exists
        mock_scene = Scene(
            number=5,
            heading="INT. TO DELETE - DAY",
            content="Delete me",
            original_text="Delete me",
            content_hash="del_hash",
        )

        with patch.object(api, "_get_scene_by_id", return_value=mock_scene):
            with patch.object(api, "_delete_scene") as mock_delete:
                with patch.object(
                    api, "_compact_scene_numbers", return_value=[6, 7, 8]
                ):
                    result = await api.delete_scene(scene_id, confirm=True)

        assert result.success is True
        assert result.error is None
        assert result.renumbered_scenes == [6, 7, 8]
        mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_scene_not_found(self, api):
        """Test deleting non-existent scene."""
        scene_id = SceneIdentifier("test_project", 999)

        with patch.object(api, "_get_scene_by_id", return_value=None):
            result = await api.delete_scene(scene_id, confirm=True)

        assert result.success is False
        assert "not found" in result.error.lower()

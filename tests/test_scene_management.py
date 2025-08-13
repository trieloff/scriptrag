"""Tests for AI-friendly scene management functionality."""

from unittest.mock import patch

import pytest

from scriptrag.api.scene_management import (
    FountainValidator,
    ReadTracker,
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


class TestReadTracker:
    """Test read session tracking."""

    def test_register_read(self):
        """Test registering a read session."""
        tracker = ReadTracker(validation_window=600)
        token = tracker.register_read(
            scene_key="test:001",
            content_hash="abc123",
            reader_id="test_reader",
        )

        assert token is not None
        assert len(token) > 0

    def test_validate_valid_session(self):
        """Test validating a valid session."""
        tracker = ReadTracker(validation_window=600)
        token = tracker.register_read(
            scene_key="test:001",
            content_hash="abc123",
            reader_id="test_reader",
        )

        result = tracker.validate_session(token, "test:001")
        assert result.is_valid is True
        assert result.error is None
        assert result.original_hash == "abc123"

    def test_validate_expired_session(self):
        """Test validating an expired session."""
        tracker = ReadTracker(validation_window=1)  # 1 second window
        token = tracker.register_read(
            scene_key="test:001",
            content_hash="abc123",
            reader_id="test_reader",
        )

        # Wait for expiration
        import time

        time.sleep(2)

        result = tracker.validate_session(token, "test:001")
        assert result.is_valid is False
        assert "expired" in result.error.lower()

    def test_validate_wrong_scene(self):
        """Test validating session for wrong scene."""
        tracker = ReadTracker(validation_window=600)
        token = tracker.register_read(
            scene_key="test:001",
            content_hash="abc123",
            reader_id="test_reader",
        )

        result = tracker.validate_session(token, "test:002")
        assert result.is_valid is False
        assert "test:001" in result.error
        assert "test:002" in result.error

    def test_validate_invalid_token(self):
        """Test validating invalid token."""
        tracker = ReadTracker(validation_window=600)
        result = tracker.validate_session("invalid_token", "test:001")
        assert result.is_valid is False
        assert "not found" in result.error.lower()

    def test_invalidate_session(self):
        """Test invalidating a session."""
        tracker = ReadTracker(validation_window=600)
        token = tracker.register_read(
            scene_key="test:001",
            content_hash="abc123",
            reader_id="test_reader",
        )

        # Session should be valid
        result = tracker.validate_session(token, "test:001")
        assert result.is_valid is True

        # Invalidate the session
        tracker.invalidate_session(token)

        # Session should now be invalid
        result = tracker.validate_session(token, "test:001")
        assert result.is_valid is False


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
        assert result.session_token is not None
        assert result.expires_at is not None

    @pytest.mark.asyncio
    async def test_read_scene_not_found(self, api):
        """Test reading non-existent scene."""
        scene_id = SceneIdentifier("test_project", 999)

        with patch.object(api, "_get_scene_by_id", return_value=None):
            result = await api.read_scene(scene_id, "test_reader")

        assert result.success is False
        assert "not found" in result.error.lower()
        assert result.scene is None
        assert result.session_token is None

    @pytest.mark.asyncio
    async def test_update_scene_success(self, api):
        """Test successful scene update."""
        scene_id = SceneIdentifier("test_project", 1)
        new_content = """INT. UPDATED SCENE - DAY

Updated content here."""

        # Setup read session with correct hash
        import hashlib

        original_content = "Original content"
        api.read_tracker.register_read(
            scene_key=scene_id.key,
            content_hash=hashlib.sha256(original_content.encode()).hexdigest(),
            reader_id="test_reader",
        )
        token = next(iter(api.read_tracker._sessions.keys()))

        # Mock current scene (with matching hash)
        mock_scene = Scene(
            number=1,
            heading="INT. TEST SCENE - DAY",
            content=original_content,
            original_text=original_content,
            content_hash=hashlib.sha256(original_content.encode()).hexdigest(),
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
                result = await api.update_scene(
                    scene_id, new_content, token, "test_reader"
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

        # Setup read session
        token = api.read_tracker.register_read(
            scene_key=scene_id.key,
            content_hash="original_hash",
            reader_id="test_reader",
        )

        result = await api.update_scene(scene_id, invalid_content, token, "test_reader")

        assert result.success is False
        assert "Invalid Fountain format" in result.error
        assert len(result.validation_errors) > 0

    @pytest.mark.asyncio
    async def test_update_scene_expired_session(self, api):
        """Test updating scene with expired session."""
        scene_id = SceneIdentifier("test_project", 1)
        new_content = """INT. UPDATED SCENE - DAY

Updated content."""

        result = await api.update_scene(
            scene_id, new_content, "expired_token", "test_reader"
        )

        assert result.success is False
        assert result.error is not None
        assert "SESSION_INVALID" in result.validation_errors

    @pytest.mark.asyncio
    async def test_update_scene_concurrent_modification(self, api):
        """Test concurrent modification detection."""
        scene_id = SceneIdentifier("test_project", 1)
        new_content = """INT. UPDATED SCENE - DAY

Updated content."""

        # Setup read session with original hash
        api.read_tracker.register_read(
            scene_key=scene_id.key,
            content_hash="original_hash",
            reader_id="test_reader",
        )
        token = next(iter(api.read_tracker._sessions.keys()))

        # Mock scene with different hash (modified by another process)
        mock_scene = Scene(
            number=1,
            heading="INT. TEST SCENE - DAY",
            content="Modified by another process",
            original_text="Modified by another process",
            content_hash="different_hash",  # Different from original
        )

        with patch.object(api, "_get_scene_by_id", return_value=mock_scene):
            result = await api.update_scene(scene_id, new_content, token, "test_reader")

        assert result.success is False
        assert "modified by another process" in result.error.lower()
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

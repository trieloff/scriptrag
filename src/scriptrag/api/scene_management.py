"""AI-friendly scene management API for ScriptRAG."""

import hashlib
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.parser import FountainParser, Scene

logger = get_logger(__name__)


@dataclass
class SceneIdentifier:
    """Unique identifier for scenes in hierarchical projects."""

    project: str
    scene_number: int
    season: int | None = None
    episode: int | None = None

    @property
    def key(self) -> str:
        """Generate unique key for scene identification."""
        if self.season is not None and self.episode is not None:
            return (
                f"{self.project}:S{self.season:02d}E{self.episode:02d}:"
                f"{self.scene_number:03d}"
            )
        return f"{self.project}:{self.scene_number:03d}"

    @classmethod
    def from_string(cls, key: str) -> "SceneIdentifier":
        """Parse scene identifier from string key."""
        parts = key.split(":")
        if len(parts) == 2:
            # Feature film format: "project:scene"
            return cls(
                project=parts[0],
                scene_number=int(parts[1]),
            )
        if len(parts) == 3:
            # TV format: "project:S##E##:scene"
            season_episode = parts[1]
            if season_episode.startswith("S") and "E" in season_episode:
                season_str, episode_str = season_episode[1:].split("E")
                return cls(
                    project=parts[0],
                    season=int(season_str),
                    episode=int(episode_str),
                    scene_number=int(parts[2]),
                )
        raise ValueError(f"Invalid scene key format: {key}")


@dataclass
class ReadSession:
    """Tracks a scene read session for validation window."""

    scene_key: str
    content_hash: str
    read_at: datetime
    expires_at: datetime
    reader_id: str
    token: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class ValidationResult:
    """Result of scene content validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    parsed_scene: Scene | None = None


@dataclass
class SessionValidationResult:
    """Result of session validation."""

    is_valid: bool
    error: str | None = None
    original_hash: str | None = None


@dataclass
class ReadSceneResult:
    """Result of reading a scene."""

    success: bool
    error: str | None
    scene: Scene | None
    session_token: str | None
    expires_at: datetime | None = None


@dataclass
class UpdateSceneResult:
    """Result of updating a scene."""

    success: bool
    error: str | None
    updated_scene: Scene | None = None
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class AddSceneResult:
    """Result of adding a scene."""

    success: bool
    error: str | None
    created_scene: Scene | None = None
    renumbered_scenes: list[int] = field(default_factory=list)


@dataclass
class DeleteSceneResult:
    """Result of deleting a scene."""

    success: bool
    error: str | None
    renumbered_scenes: list[int] = field(default_factory=list)


class ReadTracker:
    """Manages read sessions with 10-minute validation windows."""

    def __init__(self, validation_window: int = 600):
        """Initialize the read tracker.

        Args:
            validation_window: Validation window in seconds (default: 10 minutes)
        """
        self._sessions: dict[str, ReadSession] = {}
        self._validation_window = validation_window

    def register_read(self, scene_key: str, content_hash: str, reader_id: str) -> str:
        """Register scene read, return session token."""
        # Clean up expired sessions
        self._cleanup_expired()

        session = ReadSession(
            scene_key=scene_key,
            content_hash=content_hash,
            read_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=self._validation_window),
            reader_id=reader_id,
        )

        self._sessions[session.token] = session
        logger.debug(
            f"Registered read session for {scene_key}",
            token=session.token,
            expires_at=session.expires_at.isoformat(),
        )
        return session.token

    def validate_session(self, token: str, scene_key: str) -> SessionValidationResult:
        """Validate session for updates."""
        # Clean up expired sessions
        self._cleanup_expired()

        if token not in self._sessions:
            return SessionValidationResult(
                is_valid=False,
                error="Session token not found or expired",
            )

        session = self._sessions[token]

        # Check if session is expired
        if datetime.utcnow() > session.expires_at:
            del self._sessions[token]
            return SessionValidationResult(
                is_valid=False,
                error="Session has expired. Please read the scene again.",
            )

        # Check if scene key matches
        if session.scene_key != scene_key:
            return SessionValidationResult(
                is_valid=False,
                error=(
                    f"Session token is for scene {session.scene_key}, not {scene_key}"
                ),
            )

        return SessionValidationResult(
            is_valid=True,
            error=None,
            original_hash=session.content_hash,
        )

    def invalidate_session(self, token: str) -> None:
        """Invalidate a session after successful update."""
        if token in self._sessions:
            del self._sessions[token]
            logger.debug(f"Invalidated session {token}")

    def _cleanup_expired(self) -> None:
        """Remove expired sessions from memory."""
        now = datetime.utcnow()
        expired_tokens = [
            token
            for token, session in self._sessions.items()
            if session.expires_at < now
        ]
        for token in expired_tokens:
            del self._sessions[token]
        if expired_tokens:
            logger.debug(f"Cleaned up {len(expired_tokens)} expired sessions")


class FountainValidator:
    """Validates Fountain format content."""

    def __init__(self) -> None:
        """Initialize the validator."""
        self.parser = FountainParser()

    def validate_scene_content(self, content: str) -> ValidationResult:
        """Validate single scene Fountain content."""
        try:
            errors = []
            warnings = []

            # Check for scene heading
            if not self._has_scene_heading(content):
                errors.append(
                    "Missing scene heading. Scene must start with INT. or EXT. "
                    "followed by location (e.g., 'INT. COFFEE SHOP - DAY')"
                )

            # Check for content after heading
            lines = content.strip().split("\n")
            non_empty_lines = [line for line in lines if line.strip()]
            if len(non_empty_lines) <= 1:
                warnings.append("Scene appears to have no content after heading")

            # Try to parse the content as a complete script
            # Wrap in minimal fountain structure if needed
            if not content.strip().startswith(("INT.", "EXT.", "I/E.", "INT/EXT.")):
                errors.append(
                    "Scene must start with a scene heading "
                    "(INT., EXT., I/E., or INT/EXT.)"
                )

            # Parse content to ensure valid Fountain
            try:
                # Create a temporary script with just this scene
                parsed = self.parser.parse(content)
                parsed_scene = parsed.scenes[0] if parsed.scenes else None
            except Exception as e:
                errors.append(f"Fountain parsing failed: {e!s}")
                parsed_scene = None

            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                parsed_scene=parsed_scene,
            )

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[f"Validation failed: {e!s}"],
                warnings=[],
                parsed_scene=None,
            )

    def _has_scene_heading(self, content: str) -> bool:
        """Check if content has a valid scene heading."""
        first_line = content.strip().split("\n")[0] if content.strip() else ""
        return any(
            first_line.upper().startswith(prefix)
            for prefix in ["INT.", "EXT.", "I/E.", "INT/EXT."]
        )


class SceneManagementAPI:
    """AI-friendly scene management interface."""

    def __init__(self, settings: ScriptRAGSettings | None = None):
        """Initialize the API.

        Args:
            settings: Configuration settings
        """
        from scriptrag.config import get_settings

        self.settings = settings or get_settings()
        self.db_ops = DatabaseOperations(self.settings)
        self.read_tracker = ReadTracker()
        self.validator = FountainValidator()
        self.parser = FountainParser()

    async def read_scene(
        self, scene_id: SceneIdentifier, reader_id: str = "ai_agent"
    ) -> ReadSceneResult:
        """Read a scene and establish tracking session."""
        try:
            with self.db_ops.transaction() as conn:
                # Get scene from database
                scene = self._get_scene_by_id(conn, scene_id)
                if not scene:
                    return ReadSceneResult(
                        success=False,
                        error=f"Scene not found: {scene_id.key}",
                        scene=None,
                        session_token=None,
                    )

                # Calculate content hash
                content_hash = hashlib.sha256(scene.content.encode()).hexdigest()

                # Register read session
                session_token = self.read_tracker.register_read(
                    scene_key=scene_id.key,
                    content_hash=content_hash,
                    reader_id=reader_id,
                )

                expires_at = datetime.utcnow() + timedelta(seconds=600)

                logger.info(
                    f"Scene read: {scene_id.key}",
                    reader_id=reader_id,
                    session_token=session_token,
                )

                return ReadSceneResult(
                    success=True,
                    error=None,
                    scene=scene,
                    session_token=session_token,
                    expires_at=expires_at,
                )

        except Exception as e:
            logger.error(f"Failed to read scene {scene_id.key}: {e}")
            return ReadSceneResult(
                success=False,
                error=str(e),
                scene=None,
                session_token=None,
            )

    async def update_scene(
        self,
        scene_id: SceneIdentifier,
        new_content: str,
        session_token: str,
        reader_id: str = "ai_agent",
    ) -> UpdateSceneResult:
        """Update scene with validation window enforcement."""
        # Validate Fountain content first
        validation = self.validator.validate_scene_content(new_content)
        if not validation.is_valid:
            return UpdateSceneResult(
                success=False,
                error=f"Invalid Fountain format: {'; '.join(validation.errors)}",
                validation_errors=validation.errors,
            )

        # Check read session
        session_validation = self.read_tracker.validate_session(
            session_token, scene_id.key
        )

        if not session_validation.is_valid:
            return UpdateSceneResult(
                success=False,
                error=session_validation.error,
                validation_errors=["SESSION_INVALID"],
            )

        try:
            with self.db_ops.transaction() as conn:
                # Get current scene for conflict detection
                current_scene = self._get_scene_by_id(conn, scene_id)
                if not current_scene:
                    return UpdateSceneResult(
                        success=False,
                        error="Scene no longer exists",
                        validation_errors=["SCENE_NOT_FOUND"],
                    )

                # Check if scene changed since read (optimistic locking)
                current_content_hash = hashlib.sha256(
                    current_scene.content.encode()
                ).hexdigest()
                if current_content_hash != session_validation.original_hash:
                    return UpdateSceneResult(
                        success=False,
                        error=(
                            "Scene was modified by another process. "
                            "Please re-read and try again."
                        ),
                        validation_errors=["CONCURRENT_MODIFICATION"],
                    )

                # Update scene content
                updated_scene = self._update_scene_content(
                    conn, scene_id, new_content, validation.parsed_scene
                )

                # Invalidate read session
                self.read_tracker.invalidate_session(session_token)

                logger.info(
                    f"Scene updated: {scene_id.key}",
                    reader_id=reader_id,
                )

                return UpdateSceneResult(
                    success=True,
                    error=None,
                    updated_scene=updated_scene,
                    validation_errors=[],
                )

        except Exception as e:
            logger.error(f"Failed to update scene {scene_id.key}: {e}")
            return UpdateSceneResult(
                success=False,
                error=str(e),
                validation_errors=["UPDATE_FAILED"],
            )

    async def add_scene(
        self,
        scene_id: SceneIdentifier,
        content: str,
        position: str = "after",
    ) -> AddSceneResult:
        """Add new scene with automatic renumbering."""
        # Validate Fountain content
        validation = self.validator.validate_scene_content(content)
        if not validation.is_valid:
            return AddSceneResult(
                success=False,
                error=f"Invalid Fountain format: {'; '.join(validation.errors)}",
            )

        try:
            with self.db_ops.transaction() as conn:
                # Check if reference scene exists
                reference_scene = self._get_scene_by_id(conn, scene_id)
                if not reference_scene:
                    return AddSceneResult(
                        success=False,
                        error=f"Reference scene not found: {scene_id.key}",
                    )

                # Determine new scene number
                if position == "after":
                    new_number = scene_id.scene_number + 1
                    # Shift all subsequent scenes +1
                    self._shift_scenes_after(conn, scene_id, 1)
                elif position == "before":
                    new_number = scene_id.scene_number
                    # Shift current scene and all after +1
                    self._shift_scenes_from(conn, scene_id, 1)
                else:
                    return AddSceneResult(
                        success=False,
                        error=f"Invalid position: {position}. Use 'before' or 'after'",
                    )

                # Create new scene
                new_scene_id = SceneIdentifier(
                    project=scene_id.project,
                    season=scene_id.season,
                    episode=scene_id.episode,
                    scene_number=new_number,
                )

                created_scene = self._create_scene(
                    conn, new_scene_id, content, validation.parsed_scene
                )

                # Get list of renumbered scenes
                renumbered = self._get_renumbered_scenes(conn, scene_id)

                logger.info(
                    f"Scene added: {new_scene_id.key}",
                    position=position,
                    reference=scene_id.key,
                )

                return AddSceneResult(
                    success=True,
                    error=None,
                    created_scene=created_scene,
                    renumbered_scenes=renumbered,
                )

        except Exception as e:
            logger.error(f"Failed to add scene: {e}")
            return AddSceneResult(
                success=False,
                error=str(e),
            )

    async def delete_scene(
        self, scene_id: SceneIdentifier, confirm: bool = False
    ) -> DeleteSceneResult:
        """Delete scene with automatic renumbering."""
        if not confirm:
            return DeleteSceneResult(
                success=False,
                error="Deletion requires confirm=True to prevent accidental deletions",
            )

        try:
            with self.db_ops.transaction() as conn:
                # Check if scene exists
                scene = self._get_scene_by_id(conn, scene_id)
                if not scene:
                    return DeleteSceneResult(
                        success=False,
                        error=f"Scene not found: {scene_id.key}",
                    )

                # Delete scene
                self._delete_scene(conn, scene_id)

                # Compact scene numbers (close gaps)
                renumbered = self._compact_scene_numbers(conn, scene_id)

                logger.info(
                    f"Scene deleted: {scene_id.key}",
                    renumbered_count=len(renumbered),
                )

                return DeleteSceneResult(
                    success=True,
                    error=None,
                    renumbered_scenes=renumbered,
                )

        except Exception as e:
            logger.error(f"Failed to delete scene: {e}")
            return DeleteSceneResult(
                success=False,
                error=str(e),
            )

    def _get_scene_by_id(
        self, conn: sqlite3.Connection, scene_id: SceneIdentifier
    ) -> Scene | None:
        """Get scene from database by identifier."""
        # Build query based on available identifiers
        query = """
            SELECT s.*, sc.title as script_title
            FROM scenes s
            JOIN scripts sc ON s.script_id = sc.id
            WHERE s.scene_number = ?
        """
        params: list[Any] = [scene_id.scene_number]

        # Add project filter
        query += " AND sc.title = ?"
        params.append(scene_id.project)

        # Add season/episode filters if present
        if scene_id.season is not None:
            query += " AND json_extract(sc.metadata, '$.season') = ?"
            params.append(scene_id.season)

        if scene_id.episode is not None:
            query += " AND json_extract(sc.metadata, '$.episode') = ?"
            params.append(scene_id.episode)

        cursor = conn.execute(query, params)
        row = cursor.fetchone()

        if not row:
            return None

        # Convert row to Scene object
        return Scene(
            number=row["scene_number"],
            heading=row["heading"],
            content=row["content"] or "",
            original_text=row["content"] or "",
            content_hash=hashlib.sha256((row["content"] or "").encode()).hexdigest(),
            location=row["location"],
            time_of_day=row["time_of_day"],
        )

    def _update_scene_content(
        self,
        conn: sqlite3.Connection,
        scene_id: SceneIdentifier,
        new_content: str,
        parsed_scene: Scene | None,
    ) -> Scene:
        """Update scene content in database."""
        # Parse the new content to extract scene details
        if parsed_scene:
            heading = parsed_scene.heading
            location = parsed_scene.location
            time_of_day = parsed_scene.time_of_day
        else:
            # Extract basic info from content
            lines = new_content.strip().split("\n")
            heading = lines[0] if lines else ""
            from scriptrag.utils import ScreenplayUtils

            location = ScreenplayUtils.extract_location(heading) or ""
            time_of_day = ScreenplayUtils.extract_time(heading) or ""

        # Update scene in database
        query = """
            UPDATE scenes
            SET content = ?,
                heading = ?,
                location = ?,
                time_of_day = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE scene_number = ?
                AND script_id = (
                    SELECT id FROM scripts
                    WHERE title = ?
        """
        params: list[Any] = [
            new_content,
            heading,
            location,
            time_of_day,
            scene_id.scene_number,
            scene_id.project,
        ]

        # Add season/episode conditions
        if scene_id.season is not None:
            query += " AND json_extract(metadata, '$.season') = ?"
            params.append(scene_id.season)

        if scene_id.episode is not None:
            query += " AND json_extract(metadata, '$.episode') = ?"
            params.append(scene_id.episode)

        query += ")"

        conn.execute(query, params)

        # Return updated scene
        return Scene(
            number=scene_id.scene_number,
            heading=heading,
            content=new_content,
            original_text=new_content,
            content_hash=hashlib.sha256(new_content.encode()).hexdigest(),
            location=location,
            time_of_day=time_of_day,
        )

    def _create_scene(
        self,
        conn: sqlite3.Connection,
        scene_id: SceneIdentifier,
        content: str,
        parsed_scene: Scene | None,
    ) -> Scene:
        """Create new scene in database."""
        # Get script ID
        query = "SELECT id FROM scripts WHERE title = ?"
        params: list[Any] = [scene_id.project]

        if scene_id.season is not None:
            query += " AND json_extract(metadata, '$.season') = ?"
            params.append(scene_id.season)

        if scene_id.episode is not None:
            query += " AND json_extract(metadata, '$.episode') = ?"
            params.append(scene_id.episode)

        cursor = conn.execute(query, params)
        row = cursor.fetchone()

        if not row:
            raise ValueError(f"Script not found for {scene_id.key}")

        script_id = row[0]

        # Parse scene details
        if parsed_scene:
            heading = parsed_scene.heading
            location = parsed_scene.location
            time_of_day = parsed_scene.time_of_day
        else:
            lines = content.strip().split("\n")
            heading = lines[0] if lines else ""
            from scriptrag.utils import ScreenplayUtils

            location = ScreenplayUtils.extract_location(heading) or ""
            time_of_day = ScreenplayUtils.extract_time(heading) or ""

        # Insert new scene
        conn.execute(
            """
            INSERT INTO scenes (script_id, scene_number, heading, location,
                              time_of_day, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                script_id,
                scene_id.scene_number,
                heading,
                location,
                time_of_day,
                content,
                "{}",
            ),
        )

        return Scene(
            number=scene_id.scene_number,
            heading=heading,
            content=content,
            original_text=content,
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            location=location,
            time_of_day=time_of_day,
        )

    def _delete_scene(
        self, conn: sqlite3.Connection, scene_id: SceneIdentifier
    ) -> None:
        """Delete scene from database."""
        query = """
            DELETE FROM scenes
            WHERE scene_number = ?
                AND script_id = (
                    SELECT id FROM scripts
                    WHERE title = ?
        """
        params: list[Any] = [scene_id.scene_number, scene_id.project]

        if scene_id.season is not None:
            query += " AND json_extract(metadata, '$.season') = ?"
            params.append(scene_id.season)

        if scene_id.episode is not None:
            query += " AND json_extract(metadata, '$.episode') = ?"
            params.append(scene_id.episode)

        query += ")"

        conn.execute(query, params)

    def _shift_scenes_after(
        self, conn: sqlite3.Connection, scene_id: SceneIdentifier, shift: int
    ) -> None:
        """Shift scene numbers after a given scene."""
        query = """
            UPDATE scenes
            SET scene_number = scene_number + ?
            WHERE scene_number > ?
                AND script_id = (
                    SELECT id FROM scripts
                    WHERE title = ?
        """
        params: list[Any] = [shift, scene_id.scene_number, scene_id.project]

        if scene_id.season is not None:
            query += " AND json_extract(metadata, '$.season') = ?"
            params.append(scene_id.season)

        if scene_id.episode is not None:
            query += " AND json_extract(metadata, '$.episode') = ?"
            params.append(scene_id.episode)

        query += ")"

        conn.execute(query, params)

    def _shift_scenes_from(
        self, conn: sqlite3.Connection, scene_id: SceneIdentifier, shift: int
    ) -> None:
        """Shift scene numbers from a given scene."""
        query = """
            UPDATE scenes
            SET scene_number = scene_number + ?
            WHERE scene_number >= ?
                AND script_id = (
                    SELECT id FROM scripts
                    WHERE title = ?
        """
        params: list[Any] = [shift, scene_id.scene_number, scene_id.project]

        if scene_id.season is not None:
            query += " AND json_extract(metadata, '$.season') = ?"
            params.append(scene_id.season)

        if scene_id.episode is not None:
            query += " AND json_extract(metadata, '$.episode') = ?"
            params.append(scene_id.episode)

        query += ")"

        conn.execute(query, params)

    def _compact_scene_numbers(
        self, conn: sqlite3.Connection, scene_id: SceneIdentifier
    ) -> list[int]:
        """Compact scene numbers after deletion."""
        # Get all scenes after the deleted one
        query = """
            SELECT scene_number FROM scenes
            WHERE scene_number > ?
                AND script_id = (
                    SELECT id FROM scripts
                    WHERE title = ?
        """
        params: list[Any] = [scene_id.scene_number, scene_id.project]

        if scene_id.season is not None:
            query += " AND json_extract(metadata, '$.season') = ?"
            params.append(scene_id.season)

        if scene_id.episode is not None:
            query += " AND json_extract(metadata, '$.episode') = ?"
            params.append(scene_id.episode)

        query += ") ORDER BY scene_number"

        cursor = conn.execute(query, params)
        scenes_to_renumber = [row[0] for row in cursor.fetchall()]

        # Shift them all down by 1
        if scenes_to_renumber:
            self._shift_scenes_after(conn, scene_id, -1)

        return scenes_to_renumber

    def _get_renumbered_scenes(
        self, conn: sqlite3.Connection, scene_id: SceneIdentifier
    ) -> list[int]:
        """Get list of scene numbers that were renumbered."""
        query = """
            SELECT scene_number FROM scenes
            WHERE scene_number > ?
                AND script_id = (
                    SELECT id FROM scripts
                    WHERE title = ?
        """
        params: list[Any] = [scene_id.scene_number, scene_id.project]

        if scene_id.season is not None:
            query += " AND json_extract(metadata, '$.season') = ?"
            params.append(scene_id.season)

        if scene_id.episode is not None:
            query += " AND json_extract(metadata, '$.episode') = ?"
            params.append(scene_id.episode)

        query += ") ORDER BY scene_number"

        cursor = conn.execute(query, params)
        return [row[0] for row in cursor.fetchall()]

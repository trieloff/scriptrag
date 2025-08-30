"""AI-friendly scene management API for ScriptRAG."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from scriptrag.api.bible_detector import BibleAutoDetector
from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.scene_database import SceneDatabaseOperations
from scriptrag.api.scene_models import (
    AddSceneResult,
    BibleReadResult,
    DeleteSceneResult,
    ReadSceneResult,
    SceneIdentifier,
    UpdateSceneResult,
)
from scriptrag.api.scene_parser import SceneParser
from scriptrag.api.scene_validator import FountainValidator
from scriptrag.config import ScriptRAGSettings, get_logger

logger = get_logger(__name__)


class SceneManagementAPI:
    """AI-friendly scene management interface."""

    def __init__(self, settings: ScriptRAGSettings | None = None) -> None:
        """Initialize the API.

        Args:
            settings: Configuration settings
        """
        from scriptrag.config import get_settings

        self.settings = settings or get_settings()
        self.db_ops = DatabaseOperations(self.settings)
        self.scene_db = SceneDatabaseOperations()
        self.validator = FountainValidator()
        self.parser = SceneParser()

    async def read_scene(
        self, scene_id: SceneIdentifier, reader_id: str = "ai_agent"
    ) -> ReadSceneResult:
        """Read a scene and update last_read timestamp."""
        try:
            with self.db_ops.transaction() as conn:
                # Get scene from database
                scene = self.scene_db.get_scene_by_id(conn, scene_id)
                if not scene:
                    return ReadSceneResult(
                        success=False,
                        error=f"Scene not found: {scene_id.key}",
                        scene=None,
                        last_read=None,
                    )

                # Update last_read_at timestamp
                last_read = datetime.now(UTC)
                self.scene_db.update_last_read(conn, scene_id, last_read)

                logger.info(
                    f"Scene read: {scene_id.key}",
                    reader_id=reader_id,
                    last_read=last_read.isoformat(),
                )

                return ReadSceneResult(
                    success=True,
                    error=None,
                    scene=scene,
                    last_read=last_read,
                )

        except Exception as e:
            logger.error(f"Failed to read scene {scene_id.key}: {e}")
            return ReadSceneResult(
                success=False,
                error=str(e),
                scene=None,
                last_read=None,
            )

    async def update_scene(
        self,
        scene_id: SceneIdentifier,
        new_content: str,
        check_conflicts: bool = False,
        last_read: datetime | None = None,
        reader_id: str = "ai_agent",
    ) -> UpdateSceneResult:
        """Update scene with optional conflict checking.

        Args:
            scene_id: Scene identifier
            new_content: New scene content
            check_conflicts: If True, verify scene hasn't changed since last_read
            last_read: Timestamp of when scene was last read (required if
                check_conflicts=True)
            reader_id: ID of the reader/agent
        """
        # Validate Fountain content first
        validation = self.validator.validate_scene_content(new_content)
        if not validation.is_valid:
            return UpdateSceneResult(
                success=False,
                error=f"Invalid Fountain format: {'; '.join(validation.errors)}",
                validation_errors=validation.errors,
            )

        try:
            with self.db_ops.transaction() as conn:
                # Get current scene
                current_scene = self.scene_db.get_scene_by_id(conn, scene_id)
                if not current_scene:
                    return UpdateSceneResult(
                        success=False,
                        error="Scene not found",
                        validation_errors=["SCENE_NOT_FOUND"],
                    )

                # Check for conflicts if requested
                if check_conflicts:
                    if last_read is None:
                        return UpdateSceneResult(
                            success=False,
                            error=(
                                "last_read timestamp required when check_conflicts=True"
                            ),
                            validation_errors=["MISSING_TIMESTAMP"],
                        )

                    # Get last modified time
                    last_modified = self.scene_db.get_last_modified(conn, scene_id)
                    if last_modified and last_modified > last_read:
                        return UpdateSceneResult(
                            success=False,
                            error=(
                                "Scene was modified since last read. "
                                "Please re-read and try again."
                            ),
                            validation_errors=["CONCURRENT_MODIFICATION"],
                        )

                # Update scene content
                updated_scene = self.scene_db.update_scene_content(
                    conn, scene_id, new_content, validation.parsed_scene
                )

                logger.info(
                    f"Scene updated: {scene_id.key}",
                    reader_id=reader_id,
                    check_conflicts=check_conflicts,
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
                reference_scene = self.scene_db.get_scene_by_id(conn, scene_id)
                if not reference_scene:
                    return AddSceneResult(
                        success=False,
                        error=f"Reference scene not found: {scene_id.key}",
                    )

                # Determine new scene number
                if position == "after":
                    new_number = scene_id.scene_number + 1
                    # Shift all subsequent scenes +1
                    self.scene_db.shift_scenes_after(conn, scene_id, 1)
                elif position == "before":
                    new_number = scene_id.scene_number
                    # Shift current scene and all after +1
                    self.scene_db.shift_scenes_from(conn, scene_id, 1)
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

                created_scene = self.scene_db.create_scene(
                    conn, new_scene_id, content, validation.parsed_scene
                )

                # Get list of renumbered scenes
                renumbered = self.scene_db.get_renumbered_scenes(conn, scene_id)

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
                scene = self.scene_db.get_scene_by_id(conn, scene_id)
                if not scene:
                    return DeleteSceneResult(
                        success=False,
                        error=f"Scene not found: {scene_id.key}",
                    )

                # Delete scene
                self.scene_db.delete_scene(conn, scene_id)

                # Compact scene numbers (close gaps)
                renumbered = self.scene_db.compact_scene_numbers(conn, scene_id)

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

    async def read_bible(
        self, project: str, bible_name: str | None = None
    ) -> BibleReadResult:
        """Read script bible content.

        Args:
            project: Project/script name
            bible_name: Optional specific bible file name (without path)

        Returns:
            BibleReadResult with bible content or list of available bible files
        """
        try:
            # Get the script record to find project path
            with self.db_ops.transaction() as conn:
                cursor = conn.execute(
                    "SELECT file_path FROM scripts WHERE title = ?", (project,)
                )
                row = cursor.fetchone()
                if not row:
                    return BibleReadResult(
                        success=False, error=f"Project '{project}' not found"
                    )

                script_path = Path(row["file_path"])
                project_path = script_path.parent

            # Find bible files in the project
            bible_files = BibleAutoDetector.find_bible_files(project_path, script_path)

            if not bible_files:
                return BibleReadResult(
                    success=False,
                    error=f"No bible files found for project '{project}'",
                )

            # If no specific bible requested, return list of available files
            if bible_name is None:
                bible_list = []
                for bible_path in bible_files:
                    relative_path = (
                        bible_path.relative_to(project_path)
                        if (
                            project_path in bible_path.parents
                            or bible_path.parent == project_path
                        )
                        else bible_path
                    )
                    # Convert to forward slashes for cross-platform consistency
                    path_str = str(relative_path).replace("\\", "/")
                    bible_list.append(
                        {
                            "name": bible_path.name,
                            "path": path_str,
                            "size": bible_path.stat().st_size,
                        }
                    )
                return BibleReadResult(success=True, error=None, bible_files=bible_list)

            # Find the specific bible file
            target_bible = None
            for bible_path in bible_files:
                if bible_path.name == bible_name:
                    target_bible = bible_path
                    break
                # Also check relative path
                relative_path = (
                    bible_path.relative_to(project_path)
                    if (
                        project_path in bible_path.parents
                        or bible_path.parent == project_path
                    )
                    else bible_path
                )
                # Convert to forward slashes for cross-platform comparison
                relative_path_str = str(relative_path).replace("\\", "/")
                if relative_path_str == bible_name:
                    target_bible = bible_path
                    break

            if not target_bible:
                # Provide helpful error with available files
                available = [bp.name for bp in bible_files]
                available_str = ", ".join(available)
                return BibleReadResult(
                    success=False,
                    error=(
                        f"Bible file '{bible_name}' not found. "
                        f"Available: {available_str}"
                    ),
                )

            # Read the bible content
            try:
                content = target_bible.read_text(encoding="utf-8")
                return BibleReadResult(success=True, error=None, content=content)
            except Exception as e:
                logger.error(f"Failed to read bible file {target_bible}: {e}")
                return BibleReadResult(
                    success=False, error=f"Failed to read bible file: {e}"
                )

        except Exception as e:
            logger.error(f"Failed to read bible for project '{project}': {e}")
            return BibleReadResult(success=False, error=str(e))

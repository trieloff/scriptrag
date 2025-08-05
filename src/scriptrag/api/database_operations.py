"""Database operations for indexing scripts into ScriptRAG database."""

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.parser import Dialogue, Scene, Script

logger = get_logger(__name__)


@dataclass
class ScriptRecord:
    """Database record for a script."""

    id: int | None = None
    title: str | None = None
    author: str | None = None
    file_path: str | None = None
    metadata: dict | None = None


class DatabaseOperations:
    """Handles all database operations for indexing."""

    def __init__(self, settings: ScriptRAGSettings):
        """Initialize database operations with settings.

        Args:
            settings: Configuration settings for database connection
        """
        self.settings = settings
        self.db_path = settings.database_path

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper configuration.

        Returns:
            Configured SQLite connection
        """
        conn = sqlite3.connect(
            str(self.db_path), timeout=self.settings.database_timeout
        )

        # Configure connection
        conn.execute(f"PRAGMA journal_mode = {self.settings.database_journal_mode}")
        conn.execute(f"PRAGMA synchronous = {self.settings.database_synchronous}")
        conn.execute(f"PRAGMA cache_size = {self.settings.database_cache_size}")
        conn.execute(f"PRAGMA temp_store = {self.settings.database_temp_store}")

        if self.settings.database_foreign_keys:
            conn.execute("PRAGMA foreign_keys = ON")

        # Enable JSON support
        conn.row_factory = sqlite3.Row

        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a transactional database context.

        Yields:
            Database connection within a transaction context
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def check_database_exists(self) -> bool:
        """Check if the database exists and is initialized.

        Returns:
            True if database exists and has schema, False otherwise
        """
        if not self.db_path.exists():
            return False

        try:
            with self.transaction() as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='scripts'"
                )
                return cursor.fetchone() is not None
        except sqlite3.Error:
            return False

    def get_existing_script(
        self, conn: sqlite3.Connection, file_path: Path
    ) -> ScriptRecord | None:
        """Get existing script record by file path.

        Args:
            conn: Database connection
            file_path: Path to the script file

        Returns:
            ScriptRecord if found, None otherwise
        """
        cursor = conn.execute(
            "SELECT id, title, author, file_path, metadata "
            "FROM scripts WHERE file_path = ?",
            (str(file_path),),
        )
        row = cursor.fetchone()

        if row:
            return ScriptRecord(
                id=row["id"],
                title=row["title"],
                author=row["author"],
                file_path=row["file_path"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
        return None

    def upsert_script(
        self, conn: sqlite3.Connection, script: Script, file_path: Path
    ) -> int:
        """Insert or update script record.

        Args:
            conn: Database connection
            script: Script object to store
            file_path: Path to the script file

        Returns:
            ID of the inserted or updated script
        """
        metadata = script.metadata.copy() if script.metadata else {}
        metadata["last_indexed"] = datetime.now().isoformat()

        # Check if script exists
        existing = self.get_existing_script(conn, file_path)

        if existing and existing.id is not None:
            # Update existing script
            conn.execute(
                """
                UPDATE scripts
                SET title = ?, author = ?, metadata = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (script.title, script.author, json.dumps(metadata), existing.id),
            )
            logger.debug(f"Updated script {existing.id}: {script.title}")
            return existing.id

        # Insert new script
        cursor = conn.execute(
            """
            INSERT INTO scripts (title, author, file_path, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (script.title, script.author, str(file_path), json.dumps(metadata)),
        )
        script_id = cursor.lastrowid
        if script_id is None:
            raise RuntimeError("Failed to get script ID after insert")
        logger.debug(f"Inserted script {script_id}: {script.title}")
        return script_id

    def clear_script_data(self, conn: sqlite3.Connection, script_id: int) -> None:
        """Clear all existing data for a script before re-indexing.

        Args:
            conn: Database connection
            script_id: ID of the script to clear
        """
        # Delete all related data (cascades will handle most)
        conn.execute("DELETE FROM scenes WHERE script_id = ?", (script_id,))
        conn.execute("DELETE FROM characters WHERE script_id = ?", (script_id,))
        logger.debug(f"Cleared existing data for script {script_id}")

    def upsert_scene(
        self, conn: sqlite3.Connection, scene: Scene, script_id: int
    ) -> int:
        """Insert or update scene record.

        Args:
            conn: Database connection
            scene: Scene object to store
            script_id: ID of the parent script

        Returns:
            ID of the inserted or updated scene
        """
        # Extract location and time from heading
        location = (
            scene.location if scene.location else self._extract_location(scene.heading)
        )
        time_of_day = (
            scene.time_of_day
            if scene.time_of_day
            else self._extract_time(scene.heading)
        )

        # Prepare metadata
        metadata: dict[str, Any] = {}
        if scene.boneyard_metadata:
            metadata["boneyard"] = scene.boneyard_metadata
        metadata["content_hash"] = scene.content_hash

        # Check if scene exists
        cursor = conn.execute(
            "SELECT id FROM scenes WHERE script_id = ? AND scene_number = ?",
            (script_id, scene.number),
        )
        existing = cursor.fetchone()

        scene_id: int
        if existing:
            # Update existing scene
            conn.execute(
                """
                UPDATE scenes
                SET heading = ?, location = ?, time_of_day = ?, content = ?,
                    metadata = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    scene.heading,
                    location,
                    time_of_day,
                    scene.content,
                    json.dumps(metadata),
                    existing["id"],
                ),
            )
            scene_id = int(existing["id"])
            logger.debug(f"Updated scene {scene_id}: {scene.heading}")
        else:
            # Insert new scene
            cursor = conn.execute(
                """
                INSERT INTO scenes (script_id, scene_number, heading, location,
                                  time_of_day, content, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    script_id,
                    scene.number,
                    scene.heading,
                    location,
                    time_of_day,
                    scene.content,
                    json.dumps(metadata),
                ),
            )
            lastrowid = cursor.lastrowid
            if lastrowid is None:
                raise RuntimeError("Failed to get scene ID after insert")
            scene_id = lastrowid
            logger.debug(f"Inserted scene {scene_id}: {scene.heading}")

        return scene_id

    def upsert_characters(
        self, conn: sqlite3.Connection, script_id: int, characters: set[str]
    ) -> dict[str, int]:
        """Insert or update character records.

        Args:
            conn: Database connection
            script_id: ID of the parent script
            characters: Set of character names

        Returns:
            Mapping of character names to their IDs
        """
        character_map = {}

        for name in characters:
            # Check if character exists
            cursor = conn.execute(
                "SELECT id FROM characters WHERE script_id = ? AND name = ?",
                (script_id, name),
            )
            existing = cursor.fetchone()

            if existing:
                character_map[name] = existing["id"]
            else:
                # Insert new character
                cursor = conn.execute(
                    """
                    INSERT INTO characters (script_id, name)
                    VALUES (?, ?)
                    """,
                    (script_id, name),
                )
                character_map[name] = cursor.lastrowid
                logger.debug(f"Inserted character {character_map[name]}: {name}")

        return character_map

    def clear_scene_content(self, conn: sqlite3.Connection, scene_id: int) -> None:
        """Clear dialogues and actions for a scene before re-inserting.

        Args:
            conn: Database connection
            scene_id: ID of the scene to clear
        """
        conn.execute("DELETE FROM dialogues WHERE scene_id = ?", (scene_id,))
        conn.execute("DELETE FROM actions WHERE scene_id = ?", (scene_id,))

    def insert_dialogues(
        self,
        conn: sqlite3.Connection,
        scene_id: int,
        dialogues: list[Dialogue],
        character_map: dict[str, int],
    ) -> int:
        """Insert dialogue records.

        Args:
            conn: Database connection
            scene_id: ID of the parent scene
            dialogues: List of dialogue objects
            character_map: Mapping of character names to IDs

        Returns:
            Number of dialogues inserted
        """
        count = 0
        for order, dialogue in enumerate(dialogues):
            if dialogue.character not in character_map:
                # Skip dialogues for unknown characters
                logger.warning(f"Unknown character in dialogue: {dialogue.character}")
                continue

            metadata = {}
            if dialogue.parenthetical:
                metadata["parenthetical"] = dialogue.parenthetical

            conn.execute(
                """
                INSERT INTO dialogues (scene_id, character_id, dialogue_text,
                                     order_in_scene, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    scene_id,
                    character_map[dialogue.character],
                    dialogue.text,
                    order,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            count += 1

        logger.debug(f"Inserted {count} dialogues for scene {scene_id}")
        return count

    def insert_actions(
        self, conn: sqlite3.Connection, scene_id: int, actions: list[str]
    ) -> int:
        """Insert action records.

        Args:
            conn: Database connection
            scene_id: ID of the parent scene
            actions: List of action text lines

        Returns:
            Number of actions inserted
        """
        count = 0
        for order, action_text in enumerate(actions):
            if not action_text.strip():
                continue

            conn.execute(
                """
                INSERT INTO actions (scene_id, action_text, order_in_scene)
                VALUES (?, ?, ?)
                """,
                (scene_id, action_text, order),
            )
            count += 1

        logger.debug(f"Inserted {count} actions for scene {scene_id}")
        return count

    def _extract_location(self, heading: str) -> str | None:
        """Extract location from scene heading.

        Args:
            heading: Scene heading text

        Returns:
            Extracted location or None
        """
        # Basic extraction - can be enhanced
        parts = heading.split(" - ")
        if len(parts) > 0:
            # Remove INT./EXT. prefix
            location = parts[0]
            for prefix in ["INT.", "EXT.", "INT", "EXT", "I/E"]:
                if location.startswith(prefix):
                    location = location[len(prefix) :].strip()
                    break
            return location if location else None
        return None

    def _extract_time(self, heading: str) -> str | None:
        """Extract time of day from scene heading.

        Args:
            heading: Scene heading text

        Returns:
            Extracted time or None
        """
        # Look for common time indicators at the end
        heading_upper = heading.upper()
        time_indicators = [
            "DAY",
            "NIGHT",
            "MORNING",
            "AFTERNOON",
            "EVENING",
            "DAWN",
            "DUSK",
            "CONTINUOUS",
            "LATER",
            "MOMENTS LATER",
        ]

        for indicator in time_indicators:
            if heading_upper.endswith(indicator):
                return indicator
            if f"- {indicator}" in heading_upper:
                return indicator

        return None

    def get_script_stats(
        self, conn: sqlite3.Connection, script_id: int
    ) -> dict[str, int]:
        """Get statistics for an indexed script.

        Args:
            conn: Database connection
            script_id: ID of the script

        Returns:
            Dictionary with counts of scenes, characters, dialogues, and actions
        """
        stats = {}

        # Count scenes
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM scenes WHERE script_id = ?", (script_id,)
        )
        stats["scenes"] = cursor.fetchone()["count"]

        # Count characters
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM characters WHERE script_id = ?", (script_id,)
        )
        stats["characters"] = cursor.fetchone()["count"]

        # Count dialogues
        cursor = conn.execute(
            """
            SELECT COUNT(*) as count FROM dialogues d
            JOIN scenes s ON d.scene_id = s.id
            WHERE s.script_id = ?
            """,
            (script_id,),
        )
        stats["dialogues"] = cursor.fetchone()["count"]

        # Count actions
        cursor = conn.execute(
            """
            SELECT COUNT(*) as count FROM actions a
            JOIN scenes s ON a.scene_id = s.id
            WHERE s.script_id = ?
            """,
            (script_id,),
        )
        stats["actions"] = cursor.fetchone()["count"]

        return stats

"""Script-related database operations for ScriptRAG."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scriptrag.config import get_logger
from scriptrag.exceptions import DatabaseError
from scriptrag.parser import Script

logger = get_logger(__name__)


@dataclass
class ScriptRecord:
    """Database record for a script."""

    id: int | None = None
    title: str | None = None
    author: str | None = None
    file_path: str | None = None
    metadata: dict[str, Any] | None = None


class ScriptOperations:
    """Handles script-related database operations."""

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
        """Insert or update script record using file_path as unique key.

        Args:
            conn: Database connection
            script: Script object to store
            file_path: Path to the script file

        Returns:
            ID of the inserted or updated script
        """
        metadata = script.metadata.copy() if script.metadata else {}
        metadata["last_indexed"] = datetime.now().isoformat()

        # Extract series/episode info from metadata if available
        # Ensure we have safe defaults for all fields
        title = script.title or "Untitled"
        author = script.author or "Unknown"
        project_title = metadata.get("project_title") or title
        series_title = metadata.get("series_title")
        season = metadata.get("season")
        episode = metadata.get("episode")

        # Use separate SELECT/UPDATE/INSERT for compatibility
        # This works with older SQLite versions that don't support ON CONFLICT RETURNING
        cursor = conn.execute(
            "SELECT id FROM scripts WHERE file_path = ?", (str(file_path),)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing script
            conn.execute(
                """
                UPDATE scripts SET
                    title = ?, author = ?, project_title = ?,
                    series_title = ?, season = ?, episode = ?,
                    metadata = ?, updated_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
                """,
                (
                    title,
                    author,
                    project_title,
                    series_title,
                    season,
                    episode,
                    json.dumps(metadata),
                    str(file_path),
                ),
            )
            script_id = existing[0]
            logger.debug(f"Updated script {script_id}: {title} at {file_path}")
        else:
            # Insert new script
            cursor = conn.execute(
                """
                INSERT INTO scripts (
                    file_path, title, author, project_title,
                    series_title, season, episode, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(file_path),
                    title,
                    author,
                    project_title,
                    series_title,
                    season,
                    episode,
                    json.dumps(metadata),
                ),
            )
            script_id = cursor.lastrowid
            if script_id is None:
                raise DatabaseError(
                    message="Failed to get script ID after insert",
                    hint="Database constraint violation or transaction issue",
                    details={
                        "script_title": title,
                        "script_path": str(file_path),
                        "operation": "INSERT INTO scripts",
                    },
                )
            logger.debug(f"Inserted script {script_id}: {title} at {file_path}")

        return int(script_id)

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

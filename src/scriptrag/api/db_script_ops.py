"""Database operations for script records and metadata management.

This module provides operations for managing screenplay records in the ScriptRAG
database, including inserting, updating, and querying script information. It handles
the complex metadata merging required to preserve important data like Bible character
information while updating indexing timestamps and script details.

The module is designed to work with the broader ScriptRAG indexing pipeline,
ensuring that script records are properly maintained as files are processed
and re-processed over time.
"""

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
    """Represents a script record from the database.

    Contains all the basic information about a screenplay stored in the
    scripts table, including metadata that may contain Bible character
    data, series information, and other script-specific details.

    Attributes:
        id: Database primary key for the script record
        title: Script title, defaults to "Untitled" if not provided
        author: Script author, defaults to "Unknown" if not provided
        file_path: Absolute path to the Fountain file on disk
        metadata: Dictionary containing additional script data including
                 series/episode info, Bible character data, indexing
                 timestamps, and other custom metadata

    Example:
        >>> record = ScriptRecord(
        ...     id=42,
        ...     title="My Great Script",
        ...     author="Jane Writer",
        ...     file_path="/path/to/script.fountain",
        ...     metadata={"last_indexed": "2024-01-15T10:30:00"}
        ... )
    """

    id: int | None = None
    title: str | None = None
    author: str | None = None
    file_path: str | None = None
    metadata: dict[str, Any] | None = None


class ScriptOperations:
    """Provides database operations for script records and metadata.

    Handles all script-related database interactions including inserting,
    updating, and querying script records. Manages metadata merging to
    preserve important data like Bible character information while
    updating indexing timestamps and series information.

    This class encapsulates the logic for:
    - Script record CRUD operations
    - Metadata merging with special handling for Bible data
    - Statistics collection for indexed scripts
    - Data cleanup for re-indexing operations

    Example:
        >>> ops = ScriptOperations()
        >>> with database_connection() as conn:
        ...     script_id = ops.upsert_script(conn, script_obj, file_path)
        ...     stats = ops.get_script_stats(conn, script_id)
    """

    def get_existing_script(
        self, conn: sqlite3.Connection, file_path: Path
    ) -> ScriptRecord | None:
        """Retrieve an existing script record from the database by file path.

        Looks up a script record using the file path as the unique identifier.
        This is used to determine whether a script needs to be inserted as
        new or updated as existing during indexing operations.

        Args:
            conn: Active database connection
            file_path: Path to the Fountain file to look up. Will be converted
                      to string for database comparison.

        Returns:
            ScriptRecord containing all database fields if a matching script
            is found, None if no script exists with the given file path.
            Metadata is automatically parsed from JSON if present.

        Example:
            >>> existing = ops.get_existing_script(conn, Path("script.fountain"))
            >>> if existing:
            ...     print(f"Found script ID {existing.id}: {existing.title}")
            ... else:
            ...     print("Script not in database yet")
        """
        cursor = conn.execute(
            "SELECT id, title, author, file_path, metadata "
            "FROM scripts WHERE file_path = ?",
            (str(file_path),),
        )
        row = cursor.fetchone()

        if row:
            # Type-safe row access
            row_dict = dict(row)  # Convert Row to dict for type safety
            return ScriptRecord(
                id=row_dict["id"],
                title=row_dict["title"],
                author=row_dict["author"],
                file_path=row_dict["file_path"],
                metadata=json.loads(row_dict["metadata"])
                if row_dict["metadata"]
                else None,
            )
        return None

    def upsert_script(
        self, conn: sqlite3.Connection, script: Script, file_path: Path
    ) -> int:
        """Insert new script or update existing script record in database.

        Performs an "upsert" operation using file_path as the unique key.
        For existing scripts, carefully merges metadata to preserve important
        data like Bible character information while updating indexing metadata.

        The metadata merging process:
        1. Starts with script-provided metadata
        2. Adds last_indexed timestamp
        3. For existing scripts, merges with database metadata
        4. Special handling for 'bible' metadata to preserve character data

        Args:
            conn: Active database connection within a transaction
            script: Parsed Script object containing title, author, and metadata
            file_path: Path to the Fountain file, used as unique identifier

        Returns:
            Database ID of the script record (existing or newly inserted)

        Raises:
            DatabaseError: If insertion fails or script ID cannot be retrieved

        Example:
            >>> script_id = ops.upsert_script(conn, parsed_script,
            ...                               Path("script.fountain"))
            >>> print(f"Script stored with ID: {script_id}")

        Note:
            The method handles both new inserts and updates of existing records.
            Metadata is carefully merged to avoid losing important data like
            Bible character aliases that may have been extracted previously.
        """
        # Start from the script-provided metadata
        new_metadata = script.metadata.copy() if script.metadata else {}
        new_metadata["last_indexed"] = datetime.now().isoformat()

        # Extract series/episode info from metadata if available
        # Ensure we have safe defaults for all fields
        title = script.title or "Untitled"
        author = script.author or "Unknown"
        project_title = new_metadata.get("project_title") or title
        series_title = new_metadata.get("series_title")
        season = new_metadata.get("season")
        episode = new_metadata.get("episode")

        # Use separate SELECT/UPDATE/INSERT for compatibility
        # This works with older SQLite versions that don't support ON CONFLICT RETURNING
        cursor = conn.execute(
            "SELECT id FROM scripts WHERE file_path = ?", (str(file_path),)
        )
        existing = cursor.fetchone()

        if existing:
            # Merge with existing metadata to preserve authored info (e.g., bible)
            try:
                row = conn.execute(
                    "SELECT metadata FROM scripts WHERE file_path = ?",
                    (str(file_path),),
                ).fetchone()
                existing_meta = json.loads(row[0]) if row and row[0] else {}
            except Exception:  # pragma: no cover
                existing_meta = {}

            # Shallow merge, with special handling for nested 'bible'
            merged_meta = {**existing_meta, **new_metadata}
            if isinstance(existing_meta.get("bible"), dict) or isinstance(
                new_metadata.get("bible"), dict
            ):
                # Handle cases where existing or new bible metadata might not be dicts
                existing_bible = existing_meta.get("bible") or {}
                new_bible = new_metadata.get("bible") or {}

                # Only merge if both are dicts, otherwise use the dict one or new one
                if isinstance(existing_bible, dict) and isinstance(new_bible, dict):
                    merged_meta["bible"] = {**existing_bible, **new_bible}
                elif isinstance(new_bible, dict):
                    merged_meta["bible"] = new_bible
                elif isinstance(existing_bible, dict):
                    merged_meta["bible"] = existing_bible
                else:
                    # Both are non-dicts, prefer new
                    merged_meta["bible"] = new_bible

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
                    json.dumps(merged_meta),
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
                    json.dumps(new_metadata),
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
        """Remove all indexed content for a script to prepare for re-indexing.

        Deletes all scenes, characters, dialogues, actions, and related data
        for a script while preserving the script record itself and its metadata.
        This is used when re-indexing a script to ensure clean data without
        duplicates or stale references.

        The deletion cascade removes:
        - All scenes belonging to the script
        - All characters extracted from the script
        - All dialogues and actions (via scene cascades)
        - Any embeddings or analysis data (via cascades)

        Args:
            conn: Active database connection within a transaction
            script_id: Database ID of the script whose data should be cleared

        Note:
            This method relies on database foreign key constraints and cascade
            deletes to clean up related data. The script record and its metadata
            (including Bible character data) are preserved.
        """
        # Delete all related data (cascades will handle most)
        conn.execute("DELETE FROM scenes WHERE script_id = ?", (script_id,))
        conn.execute("DELETE FROM characters WHERE script_id = ?", (script_id,))
        logger.debug(f"Cleared existing data for script {script_id}")

    def get_script_stats(
        self, conn: sqlite3.Connection, script_id: int
    ) -> dict[str, int]:
        """Generate statistics about an indexed script's content.

        Counts the various elements that have been extracted and indexed from
        a screenplay, providing insight into the script's structure and the
        completeness of the indexing process.

        The statistics include:
        - scenes: Number of scenes identified in the script
        - characters: Number of unique character records
        - dialogues: Total dialogue lines across all scenes
        - actions: Total action lines across all scenes

        Args:
            conn: Active database connection
            script_id: Database ID of the script to analyze

        Returns:
            Dictionary mapping statistic names to counts:
            {
                "scenes": 45,
                "characters": 12,
                "dialogues": 320,
                "actions": 180
            }

        Example:
            >>> stats = ops.get_script_stats(conn, script_id)
            >>> print(f"Script has {stats['scenes']} scenes and "
            ...       f"{stats['characters']} characters")

        Note:
            Counts are based on indexed data in the database, not the original
            Fountain file. If indexing is incomplete, counts may be lower than
            the actual content in the screenplay.
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

"""Duplicate script handling for ScriptRAG."""

import sqlite3
from enum import Enum
from pathlib import Path
from typing import Any

from scriptrag.config import get_logger

logger = get_logger(__name__)


class DuplicateStrategy(str, Enum):
    """Strategies for handling duplicate scripts."""

    REPLACE = "replace"  # Replace existing script
    SKIP = "skip"  # Skip duplicate script
    VERSION = "version"  # Create new version, mark old as not current
    ERROR = "error"  # Raise error on duplicate (default)


class DuplicateHandler:
    """Handles duplicate scripts during indexing."""

    def check_for_duplicate(
        self,
        conn: sqlite3.Connection,
        title: str | None,
        author: str | None,
        file_path: Path,
    ) -> dict[str, Any] | None:
        """Check if a duplicate script exists.

        Args:
            conn: Database connection
            title: Script title
            author: Script author
            file_path: Path to the script file

        Returns:
            Dictionary with duplicate info if found, None otherwise
        """
        # First check if this exact file path already exists
        # Use as_posix() to ensure consistent path format across platforms
        posix_path = file_path.as_posix()
        cursor = conn.execute(
            "SELECT id, title, author, file_path FROM scripts WHERE file_path = ?",
            (posix_path,),
        )
        existing_by_path = cursor.fetchone()
        if existing_by_path:
            # Same file path - this is an update, not a duplicate
            return None

        # Check for scripts with same title and author (but different file path)
        if not title:
            return None

        # Optimized query that handles both NULL and non-NULL authors
        cursor = conn.execute(
            """
            SELECT id, title, author, file_path, version, is_current
            FROM scripts
            WHERE title = ?
                AND (author = ? OR (author IS NULL AND ? IS NULL))
                AND file_path != ?
            ORDER BY version DESC
            """,
            (title, author, author, posix_path),
        )

        duplicates = cursor.fetchall()
        if duplicates:
            # Found duplicate(s) with same title/author but different path
            latest = duplicates[0]
            return {
                "id": latest[0],
                "title": latest[1],
                "author": latest[2],
                "file_path": latest[3],
                "version": latest[4] if len(latest) > 4 else 1,
                "is_current": latest[5] if len(latest) > 5 else True,
                "count": len(duplicates),
            }

        return None

    def handle_duplicate(
        self,
        conn: sqlite3.Connection,
        duplicate_info: dict[str, Any],
        strategy: DuplicateStrategy,
        new_file_path: Path,
    ) -> tuple[DuplicateStrategy, int | None]:
        """Handle a duplicate script based on the specified strategy.

        Args:
            conn: Database connection
            duplicate_info: Information about the duplicate
            strategy: How to handle the duplicate
            new_file_path: Path to the new script file

        Returns:
            Tuple of (applied_strategy, existing_script_id_to_update)
        """
        if strategy == DuplicateStrategy.SKIP:
            logger.info(
                f"Skipping duplicate script: {duplicate_info['title']} "
                f"(new: {new_file_path}, existing: {duplicate_info['file_path']})"
            )
            return (DuplicateStrategy.SKIP, None)

        if strategy == DuplicateStrategy.REPLACE:
            # Mark the old script as replaced and we'll insert a new one
            logger.info(
                f"Replacing existing script: {duplicate_info['title']} "
                f"(old: {duplicate_info['file_path']}, new: {new_file_path})"
            )
            # We'll delete the old one and insert new
            conn.execute("DELETE FROM scripts WHERE id = ?", (duplicate_info["id"],))
            return (DuplicateStrategy.REPLACE, None)

        if strategy == DuplicateStrategy.VERSION:
            # Create a new version, mark old ones as not current
            new_version = duplicate_info.get("version", 1) + 1
            logger.info(
                f"Creating version {new_version} of script: {duplicate_info['title']} "
                f"(new file: {new_file_path})"
            )

            # Mark all existing versions as not current (optimized query)
            author = duplicate_info.get("author")
            conn.execute(
                """
                UPDATE scripts
                SET is_current = 0
                WHERE title = ?
                    AND (author = ? OR (author IS NULL AND ? IS NULL))
                """,
                (duplicate_info["title"], author, author),
            )

            return (DuplicateStrategy.VERSION, new_version)

        # DuplicateStrategy.ERROR
        raise ValueError(
            f"Duplicate script found: '{duplicate_info['title']}' by "
            f"'{duplicate_info['author'] or 'Unknown'}' already exists at "
            f"{duplicate_info['file_path']}. Use --replace, --skip, or "
            f"--version to handle duplicates."
        )

    def get_episode_info(self, metadata: dict[str, Any]) -> dict[str, Any] | None:
        """Extract episode/season information from metadata.

        Args:
            metadata: Script metadata

        Returns:
            Dictionary with episode info if found, None otherwise
        """
        episode_info = {}

        # Check for TV series metadata
        if "series" in metadata:
            episode_info["series"] = metadata["series"]
        if "season" in metadata:
            episode_info["season"] = metadata["season"]
        if "episode" in metadata:
            episode_info["episode"] = metadata["episode"]
        if "episode_title" in metadata:
            episode_info["episode_title"] = metadata["episode_title"]

        return episode_info if episode_info else None

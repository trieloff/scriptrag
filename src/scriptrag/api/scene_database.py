"""Database operations for scene management."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from typing import Any

from scriptrag.api.scene_models import SceneIdentifier
from scriptrag.config import get_logger
from scriptrag.parser import Scene
from scriptrag.utils import ScreenplayUtils

logger = get_logger(__name__)


class SceneDatabaseOperations:
    """Handles database operations for scenes."""

    def get_scene_by_id(
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

    def update_scene_content(
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

    def create_scene(
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

    def delete_scene(self, conn: sqlite3.Connection, scene_id: SceneIdentifier) -> None:
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

    def shift_scenes_after(
        self, conn: sqlite3.Connection, scene_id: SceneIdentifier, shift: int
    ) -> None:
        """Shift scene numbers after a given scene."""
        # When shifting up (positive), we need to update in descending order
        # When shifting down (negative), we need to update in ascending order
        # Use a two-step process to avoid UNIQUE constraint violations

        if shift > 0:
            # First, get all scenes that need to be shifted
            select_query = """
                SELECT id, scene_number FROM scenes
                WHERE scene_number > ?
                    AND script_id = (
                        SELECT id FROM scripts
                        WHERE title = ?
            """
            params: list[Any] = [scene_id.scene_number, scene_id.project]

            if scene_id.season is not None:
                select_query += " AND json_extract(metadata, '$.season') = ?"
                params.append(scene_id.season)

            if scene_id.episode is not None:
                select_query += " AND json_extract(metadata, '$.episode') = ?"
                params.append(scene_id.episode)

            select_query += ") ORDER BY scene_number DESC"

            # Get scenes in descending order
            cursor = conn.execute(select_query, params)
            scenes = cursor.fetchall()

            # Update each scene individually in order
            for scene_internal_id, _ in scenes:
                conn.execute(
                    "UPDATE scenes SET scene_number = scene_number + ? WHERE id = ?",
                    (shift, scene_internal_id),
                )
        else:
            # For negative shifts, update in ascending order
            query = """
                UPDATE scenes
                SET scene_number = scene_number + ?
                WHERE scene_number > ?
                    AND script_id = (
                        SELECT id FROM scripts
                        WHERE title = ?
            """
            params = [shift, scene_id.scene_number, scene_id.project]

            if scene_id.season is not None:
                query += " AND json_extract(metadata, '$.season') = ?"
                params.append(scene_id.season)

            if scene_id.episode is not None:
                query += " AND json_extract(metadata, '$.episode') = ?"
                params.append(scene_id.episode)

            query += ")"
            conn.execute(query, params)

    def shift_scenes_from(
        self, conn: sqlite3.Connection, scene_id: SceneIdentifier, shift: int
    ) -> None:
        """Shift scene numbers from a given scene."""
        # When shifting up (positive), we need to update in descending order
        # When shifting down (negative), we need to update in ascending order
        # Use a two-step process to avoid UNIQUE constraint violations

        if shift > 0:
            # First, get all scenes that need to be shifted
            select_query = """
                SELECT id, scene_number FROM scenes
                WHERE scene_number >= ?
                    AND script_id = (
                        SELECT id FROM scripts
                        WHERE title = ?
            """
            params: list[Any] = [scene_id.scene_number, scene_id.project]

            if scene_id.season is not None:
                select_query += " AND json_extract(metadata, '$.season') = ?"
                params.append(scene_id.season)

            if scene_id.episode is not None:
                select_query += " AND json_extract(metadata, '$.episode') = ?"
                params.append(scene_id.episode)

            select_query += ") ORDER BY scene_number DESC"

            # Get scenes in descending order
            cursor = conn.execute(select_query, params)
            scenes = cursor.fetchall()

            # Update each scene individually in order
            for scene_internal_id, _ in scenes:
                conn.execute(
                    "UPDATE scenes SET scene_number = scene_number + ? WHERE id = ?",
                    (shift, scene_internal_id),
                )
        else:
            # For negative shifts, update in ascending order
            query = """
                UPDATE scenes
                SET scene_number = scene_number + ?
                WHERE scene_number >= ?
                    AND script_id = (
                        SELECT id FROM scripts
                        WHERE title = ?
            """
            params = [shift, scene_id.scene_number, scene_id.project]

            if scene_id.season is not None:
                query += " AND json_extract(metadata, '$.season') = ?"
                params.append(scene_id.season)

            if scene_id.episode is not None:
                query += " AND json_extract(metadata, '$.episode') = ?"
                params.append(scene_id.episode)

            query += ")"
            conn.execute(query, params)

    def compact_scene_numbers(
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
            self.shift_scenes_after(conn, scene_id, -1)

        return scenes_to_renumber

    def get_renumbered_scenes(
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

    def update_last_read(
        self, conn: sqlite3.Connection, scene_id: SceneIdentifier, timestamp: datetime
    ) -> None:
        """Update the last_read_at timestamp for a scene."""
        query = """
            UPDATE scenes
            SET last_read_at = ?
            WHERE scene_number = ?
                AND script_id = (
                    SELECT id FROM scripts
                    WHERE title = ?
        """
        # Convert datetime to string for SQLite
        timestamp_str = timestamp.isoformat()
        params: list[Any] = [timestamp_str, scene_id.scene_number, scene_id.project]

        # Add season/episode conditions
        if scene_id.season is not None:
            query += " AND json_extract(metadata, '$.season') = ?"
            params.append(scene_id.season)

        if scene_id.episode is not None:
            query += " AND json_extract(metadata, '$.episode') = ?"
            params.append(scene_id.episode)

        query += ")"
        conn.execute(query, params)

    def get_last_modified(
        self, conn: sqlite3.Connection, scene_id: SceneIdentifier
    ) -> datetime | None:
        """Get the last modification time for a scene."""
        query = """
            SELECT updated_at
            FROM scenes
            WHERE scene_number = ?
                AND script_id = (
                    SELECT id FROM scripts
                    WHERE title = ?
        """
        params: list[Any] = [scene_id.scene_number, scene_id.project]

        # Add season/episode conditions
        if scene_id.season is not None:
            query += " AND json_extract(metadata, '$.season') = ?"
            params.append(scene_id.season)

        if scene_id.episode is not None:
            query += " AND json_extract(metadata, '$.episode') = ?"
            params.append(scene_id.episode)

        query += ")"

        cursor = conn.execute(query, params)
        row = cursor.fetchone()

        if row and row["updated_at"]:
            # Parse timestamp string to datetime
            return datetime.fromisoformat(row["updated_at"].replace(" ", "T"))
        return None

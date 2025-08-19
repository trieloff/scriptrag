"""Scene and content-related database operations for ScriptRAG."""

import json
import sqlite3
from typing import Any

from scriptrag.config import get_logger
from scriptrag.exceptions import DatabaseError
from scriptrag.parser import Dialogue, Scene
from scriptrag.utils import ScreenplayUtils

logger = get_logger(__name__)


class SceneOperations:
    """Handles scene and content-related database operations."""

    def upsert_scene(
        self, conn: sqlite3.Connection, scene: Scene, script_id: int
    ) -> tuple[int, bool]:
        """Insert or update scene record.

        Args:
            conn: Database connection
            scene: Scene object to store
            script_id: ID of the parent script

        Returns:
            Tuple of (scene_id, content_changed) where content_changed is True
            if the scene content has changed
        """
        # Extract location and time from heading
        location = (
            scene.location
            if scene.location
            else ScreenplayUtils.extract_location(scene.heading)
        )
        time_of_day = (
            scene.time_of_day
            if scene.time_of_day
            else ScreenplayUtils.extract_time(scene.heading)
        )

        # Prepare metadata
        metadata: dict[str, Any] = {}
        if scene.boneyard_metadata:
            metadata["boneyard"] = scene.boneyard_metadata
        metadata["content_hash"] = scene.content_hash

        # Check if scene exists
        cursor = conn.execute(
            "SELECT id, metadata FROM scenes WHERE script_id = ? AND scene_number = ?",
            (script_id, scene.number),
        )
        existing = cursor.fetchone()

        scene_id: int
        content_changed = False

        if existing:
            # Check if content has actually changed by comparing hashes
            existing_metadata = (
                json.loads(existing["metadata"]) if existing["metadata"] else {}
            )
            existing_hash = existing_metadata.get("content_hash")
            content_changed = existing_hash != scene.content_hash

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
            logger.debug(
                f"Updated scene {scene_id}: {scene.heading}, "
                f"content_changed={content_changed}"
            )
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
                raise DatabaseError(
                    message="Failed to get scene ID after database insert",
                    hint="Database constraint violation or transaction issue",
                    details={
                        "scene_number": getattr(scene, "scene_number", "unknown"),
                        "script_id": script_id,
                        "operation": "INSERT INTO scenes",
                    },
                )
            scene_id = lastrowid
            content_changed = True  # New scene, so content has "changed"
            logger.debug(f"Inserted scene {scene_id}: {scene.heading}")

        return scene_id, content_changed

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
                # Skip dialogues for unknown characters - this can happen when a
                # dialogue is attributed to a character that wasn't properly
                # extracted during character discovery phase, possibly due to
                # formatting issues in the screenplay
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

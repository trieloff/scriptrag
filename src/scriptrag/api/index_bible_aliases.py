"""Bible alias application for script indexing."""

from __future__ import annotations

import json
import sqlite3

from scriptrag.config import get_logger

logger = get_logger(__name__)


class IndexBibleAliasApplicator:
    """Applies Bible-extracted aliases to characters during indexing."""

    @staticmethod
    async def apply_bible_aliases(
        conn: sqlite3.Connection, script_id: int, character_map: dict[str, int]
    ) -> None:
        """Apply Bible-extracted aliases to characters.

        Args:
            conn: Database connection
            script_id: ID of the script
            character_map: Map of character names to IDs
        """
        try:
            cursor = conn.cursor()

            # Get Bible metadata from script
            cursor.execute("SELECT metadata FROM scripts WHERE id = ?", (script_id,))
            row = cursor.fetchone()

            if not row or not row[0]:
                return

            metadata = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            bible_characters = metadata.get("bible.characters")

            if not bible_characters or not bible_characters.get("characters"):
                return

            # Apply aliases to matching characters
            for char_data in bible_characters["characters"]:
                canonical = char_data.get("canonical", "").upper()
                aliases = char_data.get("aliases", [])

                if not canonical or not aliases:
                    continue

                # Find matching character ID
                char_id = character_map.get(canonical)
                if char_id:
                    # Update character with aliases
                    aliases_json = json.dumps([alias.upper() for alias in aliases])
                    cursor.execute(
                        "UPDATE characters SET aliases = ? WHERE id = ?",
                        (aliases_json, char_id),
                    )
                    logger.debug(
                        f"Applied {len(aliases)} aliases to character {canonical}"
                    )

        except Exception as e:
            logger.warning(f"Failed to apply Bible aliases: {e}")

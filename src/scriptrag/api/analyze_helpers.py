"""Helper functions for script analysis operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scriptrag.config import get_logger
from scriptrag.parser import Scene, Script

logger = get_logger(__name__)


def file_needs_update(
    script: Script, analyzers: list[Any], _file_path: Path | None = None
) -> bool:
    """Determine if a screenplay file needs analysis processing.

    Checks whether any scenes in the script need analysis by examining
    existing metadata and comparing with currently loaded analyzers.
    Used to skip files that are already up-to-date unless force mode.

    Args:
        script: Parsed Script object containing scenes with potential metadata
        analyzers: List of loaded analyzers to check against
        _file_path: Path to the file (parameter preserved for compatibility
                   but not currently used in the logic)

    Returns:
        True if the file contains scenes that need processing by current
        analyzers, False if all scenes are up-to-date

    Note:
        Currently checks all scenes in the script. A file needs updating
        if any scene needs updating according to scene_needs_update().
    """
    # Check if any scene needs updating
    if isinstance(script, Script):
        for scene in script.scenes:
            if scene_needs_update(scene, analyzers):
                return True

    return False


def scene_needs_update(scene: Scene, analyzers: list[Any]) -> bool:
    """Determine if a scene needs analysis processing.

    Checks scene metadata to decide whether analysis should be performed:
    1. Scenes without any metadata need processing
    2. Scenes missing 'analyzed_at' timestamp need processing
    3. Scenes missing results from currently loaded analyzers need processing

    This enables incremental analysis where only new or changed scenes
    are processed, and new analyzers are run on existing scenes.

    Args:
        scene: Scene object that may contain existing analysis metadata
              in its boneyard_metadata attribute
        analyzers: List of loaded analyzers to check against

    Returns:
        True if the scene should be processed by the analysis pipeline,
        False if it's already up-to-date with current analyzer set

    Example:
        A scene with relationship analysis but no embedding analysis
        would return True if an embedding analyzer is loaded, enabling
        incremental processing of just the missing analysis type.
    """
    if not isinstance(scene, Scene):
        return False

    # No metadata yet
    if scene.boneyard_metadata is None:
        return True

    # Check if metadata is outdated (e.g., missing analyzer results)
    metadata = scene.boneyard_metadata

    # Check if analyzed_at exists and is recent
    if "analyzed_at" not in metadata:
        return True

    # Check if all registered analyzers have been run
    if "analyzers" in metadata:
        existing_analyzers = set(metadata["analyzers"].keys())
        current_analyzers = {a.name for a in analyzers}
        if current_analyzers - existing_analyzers:
            # New analyzers to run
            return True

    # For now, consider up to date
    return False


async def load_bible_metadata(script_path: Path) -> dict[str, Any] | None:
    """Load Bible character metadata from database for analyzer context.

    Retrieves character alias data that may have been extracted from
    script Bible files and stored in the database. This metadata is used
    by analyzers like the relationships analyzer to identify characters
    mentioned in scenes.

    The method looks for character data stored under 'bible.characters'
    in the script's metadata column, which contains the output from
    Bible character extraction operations.

    Args:
        script_path: Path to the script file to look up in database

    Returns:
        Dictionary containing Bible character metadata if found and valid,
        None if script not in database, no metadata exists, or database
        errors occur. The format matches BibleCharacterExtractor output.

    Example:
        >>> metadata = await load_bible_metadata(Path("script.fountain"))
        >>> if metadata:
        ...     char_count = len(metadata.get("characters", []))
        ...     print(f"Found {char_count} Bible characters")

    Note:
        All database errors are caught and logged as debug messages.
        Returns None gracefully to allow analysis to continue without
        Bible character data if database issues occur.
    """
    try:
        # Try to load from database
        from scriptrag.api.database_operations import DatabaseOperations
        from scriptrag.config import get_settings

        settings = get_settings()
        db_ops = DatabaseOperations(settings)

        if not db_ops.check_database_exists():
            return None

        with db_ops.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT metadata FROM scripts WHERE file_path = ?",
                (str(script_path),),
            )
            row = cursor.fetchone()

            if row and row[0]:
                metadata = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                bible_chars = metadata.get("bible.characters")
                return bible_chars if isinstance(bible_chars, dict) else None

    except Exception as e:
        logger.debug(f"Could not load Bible metadata: {e}")

    return None

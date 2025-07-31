"""ScriptRAG CLI package.

This package organizes CLI commands into logical modules to keep file sizes
manageable and improve code organization.
"""

# Import supporting modules for backwards compatibility during CLI refactoring
from scriptrag.config import get_logger, get_settings
from scriptrag.database.bible import ScriptBibleOperations
from scriptrag.database.connection import DatabaseConnection

from .main import app


def get_latest_script_id(connection: "DatabaseConnection") -> tuple[str, str] | None:
    """Get the latest script ID and title from the database.

    Args:
        connection: Database connection instance

    Returns:
        Tuple of (script_id, script_title) or None if no scripts found
    """
    with connection.transaction() as conn:
        result = conn.execute(
            """
            SELECT id, json_extract(properties_json, '$.title') as title
            FROM nodes
            WHERE node_type = 'script'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()

        if result:
            return (result[0], result[1])
        return None


__all__ = [
    "DatabaseConnection",
    "ScriptBibleOperations",
    "app",
    "get_latest_script_id",
    "get_logger",
    "get_settings",
]

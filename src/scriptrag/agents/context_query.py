"""Context query execution for markdown-based agents."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scriptrag.config import ScriptRAGSettings, get_logger, get_settings
from scriptrag.query import ParamSpec, QueryEngine, QuerySpec
from scriptrag.utils import ScreenplayUtils

if TYPE_CHECKING:
    from scriptrag.parser import Script

logger = get_logger(__name__)

# Constants
HASH_ID_LENGTH = 12  # Length for truncated hash IDs used throughout the system


@dataclass
class ContextParameters:
    """Parameters extracted from scene context for query execution."""

    # Scene-specific parameters
    content_hash: str | None = None
    scene_number: int | None = None
    scene_id: str | None = None
    scene_heading: str | None = None

    # Script-specific parameters
    script_id: str | None = None
    file_path: str | None = None
    project_name: str | None = None

    # Series metadata
    episode: int | str | None = None
    season: int | str | None = None
    series: str | None = None

    # Additional context
    previous_scene_hash: str | None = None
    next_scene_hash: str | None = None

    @classmethod
    def from_scene(
        cls,
        scene: dict[str, Any],
        script: Script | None = None,
        settings: ScriptRAGSettings | None = None,
    ) -> ContextParameters:
        """Extract parameters from scene data.

        Args:
            scene: Scene data dictionary
            script: Optional Script object for additional context
            settings: Optional settings for project info

        Returns:
            ContextParameters instance
        """
        params = cls()

        # Extract scene-specific parameters
        # Handle both dict scene data and Scene objects
        if hasattr(scene, "content_hash"):
            # It's a Scene object
            params.content_hash = scene.content_hash
            params.scene_number = getattr(scene, "number", None)
            params.scene_heading = getattr(scene, "heading", None)
        else:
            # It's a dict
            content = scene.get("content_hash") or scene.get("original_text")
            params.content_hash = content
            params.scene_number = scene.get("scene_number") or scene.get("number")
            params.scene_heading = scene.get("heading")

        # Generate scene_id if we have enough info
        if params.content_hash:
            # Compute hash if it's raw text
            if len(params.content_hash) > 64:  # Likely raw text, not a hash
                params.content_hash = ScreenplayUtils.compute_scene_hash(
                    params.content_hash, truncate=True
                )
            params.scene_id = params.content_hash[:HASH_ID_LENGTH]  # Short hash for ID

        # Extract script metadata if available
        if script:
            # Generate script_id from file path or metadata
            if hasattr(script, "file_path"):
                file_str = str(script.file_path)
            else:
                # Fallback to source file stored in script metadata
                file_str = None
                try:
                    meta = getattr(script, "metadata", {}) or {}
                    src = meta.get("source_file")
                    if src:
                        file_str = str(src)
                except Exception:  # pragma: no cover - defensive fallback
                    file_str = None

            if file_str:
                params.script_id = hashlib.sha256(file_str.encode()).hexdigest()[
                    :HASH_ID_LENGTH
                ]
                params.file_path = file_str

            # Extract series metadata from script
            metadata = getattr(script, "metadata", {})
            params.episode = metadata.get("episode")
            params.season = metadata.get("season") or metadata.get("series")
            params.series = metadata.get("series_title") or metadata.get("title")

            # Find scene number and previous/next scenes if available
            if hasattr(script, "scenes"):
                scenes = script.scenes
                for i, s in enumerate(scenes):
                    # Match by content hash
                    if (
                        hasattr(s, "content_hash")
                        and params.content_hash
                        and s.content_hash == params.content_hash
                    ):
                        # Set scene number if not already set
                        if params.scene_number is None:
                            params.scene_number = i + 1  # 1-indexed

                        # Get previous/next scene hashes
                        if i > 0:
                            prev_scene = scenes[i - 1]
                            if hasattr(prev_scene, "content_hash"):
                                params.previous_scene_hash = prev_scene.content_hash
                        if i < len(scenes) - 1:
                            next_scene = scenes[i + 1]
                            if hasattr(next_scene, "content_hash"):
                                params.next_scene_hash = next_scene.content_hash
                        break

        # Extract project name from settings or file path
        if settings:
            params.project_name = getattr(settings, "project_name", None)

        if not params.project_name and params.file_path:
            # Use parent directory name as project name
            path = Path(params.file_path)
            if path.parent.name:
                params.project_name = path.parent.name

        return params

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for query execution.

        Returns:
            Dictionary of non-None parameters
        """
        return {key: value for key, value in self.__dict__.items() if value is not None}


class ContextQueryExecutor:
    """Executes context queries for agents."""

    def __init__(self, settings: ScriptRAGSettings | None = None) -> None:
        """Initialize the executor.

        Args:
            settings: Configuration settings
        """
        if settings is None:
            settings = get_settings()

        self.settings = settings
        self.engine = QueryEngine(settings)

    async def execute(
        self,
        query_sql: str,
        parameters: ContextParameters,
    ) -> list[dict[str, Any]]:
        """Execute a context query with parameters.

        Args:
            query_sql: SQL query string
            parameters: Context parameters

        Returns:
            List of result rows as dictionaries
        """
        if not query_sql:
            return []

        try:
            # Convert SQL to QuerySpec for validation
            spec = self._sql_to_spec(query_sql, parameters)

            # Execute using QueryEngine
            params_dict = parameters.to_dict()
            rows, execution_time = self.engine.execute(spec, params_dict)

            logger.info(
                "Context query executed successfully",
                row_count=len(rows),
                execution_time_ms=execution_time,
                params=list(params_dict.keys()),
            )

            return rows

        except FileNotFoundError as e:
            # Database file not found
            logger.error(
                "Database not found for context query",
                error=str(e),
                query_preview=query_sql[:200] if query_sql else None,
            )
            return []

        except ValueError as e:
            # SQL syntax errors, parameter errors, or database errors
            logger.error(
                "Context query validation or execution error",
                error=str(e),
                query_preview=query_sql[:200] if query_sql else None,
            )
            return []

        except RuntimeError as e:
            # Database permission or configuration errors
            logger.error(
                "Context query runtime error",
                error=str(e),
                query_preview=query_sql[:200] if query_sql else None,
            )
            return []

        except Exception as e:
            # Unexpected errors - log with full details for debugging
            logger.error(
                "Unexpected error in context query execution",
                error=str(e),
                error_type=type(e).__name__,
                query_preview=query_sql[:200] if query_sql else None,
            )
            # Still return empty results for graceful degradation
            return []

    def _get_standard_param_specs(self) -> list[ParamSpec]:
        """Get predefined parameter specifications for context queries.

        Returns:
            List of standard parameter specifications
        """
        # Define all known context parameters with their types
        # These match the fields in ContextParameters dataclass
        return [
            # Scene-specific parameters
            ParamSpec(
                name="content_hash",
                type="str",
                required=False,
                help="Hash of the scene content",
            ),
            ParamSpec(
                name="scene_number",
                type="int",
                required=False,
                help="Scene number in the script",
            ),
            ParamSpec(
                name="scene_id",
                type="str",
                required=False,
                help="Unique scene identifier",
            ),
            ParamSpec(
                name="scene_heading",
                type="str",
                required=False,
                help="Scene heading text",
            ),
            # Script-specific parameters
            ParamSpec(
                name="script_id",
                type="str",
                required=False,
                help="Unique script identifier",
            ),
            ParamSpec(
                name="file_path",
                type="str",
                required=False,
                help="Path to the script file",
            ),
            ParamSpec(
                name="project_name",
                type="str",
                required=False,
                help="Name of the project",
            ),
            # Series metadata
            ParamSpec(
                name="episode",
                type="str",
                required=False,
                help="Episode number or identifier",
            ),
            ParamSpec(
                name="season",
                type="str",
                required=False,
                help="Season number or identifier",
            ),
            ParamSpec(name="series", type="str", required=False, help="Series name"),
            # Additional context
            ParamSpec(
                name="previous_scene_hash",
                type="str",
                required=False,
                help="Hash of the previous scene",
            ),
            ParamSpec(
                name="next_scene_hash",
                type="str",
                required=False,
                help="Hash of the next scene",
            ),
        ]

    def _sql_to_spec(self, sql: str, _parameters: ContextParameters) -> QuerySpec:
        """Convert raw SQL to QuerySpec with predefined parameters.

        Args:
            sql: SQL query string
            _parameters: Context parameters (unused, kept for compatibility)

        Returns:
            QuerySpec instance with standard parameter specifications
        """
        return QuerySpec(
            name="context_query",
            description="Agent context query",
            sql=sql,
            params=self._get_standard_param_specs(),
        )


class ContextResultFormatter:
    """Formats context query results for LLM prompts."""

    @staticmethod
    def format_as_table(
        rows: list[dict[str, Any]],
        max_rows: int = 50,
    ) -> str:
        """Format results as a simple markdown table.

        Args:
            rows: Query result rows
            max_rows: Maximum rows to include (default 50)

        Returns:
            Formatted markdown table string
        """
        if not rows:
            return "No results found"

        # Limit rows if needed
        display_rows = rows[:max_rows] if len(rows) > max_rows else rows
        truncated = len(rows) > max_rows

        # Handle edge case where max_rows is 0 or display_rows is empty
        if not display_rows:
            return "No results to display (max_rows limit reached)"

        # Get column names from first row
        columns = list(display_rows[0].keys())

        # Build markdown table
        lines = []

        # Header
        lines.append(" | ".join(columns))
        lines.append(" | ".join("-" * len(col) for col in columns))

        # Data rows
        for row in display_rows:
            values = []
            for col in columns:
                value = row.get(col, "")
                # Handle None and convert to string
                str_value = "" if value is None else str(value)
                # Truncate very long values to keep table readable
                if len(str_value) > 100:
                    str_value = str_value[:97] + "..."
                values.append(str_value)
            lines.append(" | ".join(values))

        if truncated:
            lines.append(f"\n... and {len(rows) - max_rows} more rows")

        return "\n".join(lines)

    @staticmethod
    def format_for_agent(
        rows: list[dict[str, Any]],
        _agent_name: str,
    ) -> str:
        """Format results as a table for all agents.

        Args:
            rows: Query results
            _agent_name: Name of the agent (kept for compatibility, unused)

        Returns:
            Formatted results as a table
        """
        # Use uniform table formatting for all query results
        return ContextResultFormatter.format_as_table(rows)


# Export main classes
__all__ = [
    "ContextParameters",
    "ContextQueryExecutor",
    "ContextResultFormatter",
]

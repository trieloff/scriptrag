"""Context query execution for markdown-based agents."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from scriptrag.config import ScriptRAGSettings, get_logger, get_settings
from scriptrag.query import ParamSpec, QueryEngine, QuerySpec
from scriptrag.utils.screenplay import ScreenplayUtils

if TYPE_CHECKING:
    from scriptrag.parser import Script

logger = get_logger(__name__)


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
            params.scene_id = params.content_hash[:12]  # Short hash for ID

        # Extract script metadata if available
        if script:
            # Generate script_id from file path or metadata
            if hasattr(script, "file_path"):
                file_str = str(script.file_path)
                params.script_id = hashlib.sha256(file_str.encode()).hexdigest()[:12]
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
                    # Match by content hash or by object identity
                    if (
                        hasattr(s, "content_hash")
                        and params.content_hash
                        and s.content_hash == params.content_hash
                    ) or s == scene:
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

    def __init__(self, settings: ScriptRAGSettings | None = None):
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

        except Exception as e:
            logger.error(
                "Context query execution failed",
                error=str(e),
                query_preview=query_sql[:200] if query_sql else None,
            )
            # Return empty results on failure (graceful degradation)
            return []

    def _sql_to_spec(self, sql: str, parameters: ContextParameters) -> QuerySpec:
        """Convert raw SQL to QuerySpec.

        Args:
            sql: SQL query string
            parameters: Context parameters for validation

        Returns:
            QuerySpec instance
        """
        # Extract parameter names from SQL
        param_pattern = re.compile(r":(\w+)")
        param_names = param_pattern.findall(sql)

        # Build parameter specifications based on available context
        param_specs = []
        params_dict = parameters.to_dict()

        for param_name in param_names:
            if param_name in params_dict:
                value = params_dict[param_name]
                # Infer type from value
                param_type: Literal["str", "int", "float", "bool"]
                if isinstance(value, int):
                    param_type = "int"
                elif isinstance(value, float):
                    param_type = "float"
                elif isinstance(value, bool):
                    param_type = "bool"
                else:
                    param_type = "str"

                param_specs.append(
                    ParamSpec(
                        name=param_name,
                        type=param_type,
                        required=True,
                        help=f"Context parameter: {param_name}",
                    )
                )

        return QuerySpec(
            name="context_query",
            description="Agent context query",
            sql=sql,
            params=param_specs,
        )


class ContextResultFormatter:
    """Formats context query results for LLM prompts."""

    @staticmethod
    def format_as_table(
        rows: list[dict[str, Any]],
        max_rows: int = 10,
    ) -> str:
        """Format results as a simple table.

        Args:
            rows: Query result rows
            max_rows: Maximum rows to include

        Returns:
            Formatted table string
        """
        if not rows:
            return "No results found"

        # Limit rows
        display_rows = rows[:max_rows]
        truncated = len(rows) > max_rows

        # Get column names
        columns = list(display_rows[0].keys())

        # Build table
        lines = []

        # Header
        lines.append(" | ".join(columns))
        lines.append("-" * (sum(len(col) + 3 for col in columns) - 3))

        # Rows
        for row in display_rows:
            values = [str(row.get(col, "")) for col in columns]
            lines.append(" | ".join(values))

        if truncated:
            lines.append(f"... and {len(rows) - max_rows} more rows")

        return "\n".join(lines)

    @staticmethod
    def format_props_history(rows: list[dict[str, Any]]) -> str:
        """Format props history for inventory tracking.

        Args:
            rows: Query results with prop information

        Returns:
            Formatted props history
        """
        if not rows:
            return "No previous props found in earlier scenes."

        # Parse JSON props data from query results
        props_by_scene = {}

        for row in rows:
            scene_num = row.get("scene_number", "Unknown")
            scene_heading = row.get("heading", "")
            props_json = row.get("props_json")

            if props_json:
                try:
                    # Parse the JSON data
                    if isinstance(props_json, str):
                        props_data = json.loads(props_json)
                    else:
                        props_data = props_json

                    if props_data and isinstance(props_data, list):
                        if scene_num not in props_by_scene:
                            props_by_scene[scene_num] = {
                                "heading": scene_heading,
                                "props": [],
                            }
                        props_by_scene[scene_num]["props"].extend(props_data)

                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Failed to parse props JSON for scene {scene_num}")

        if not props_by_scene:
            return "No previous props with valid data found."

        # Format output
        lines = ["## Props from Previous Scenes\n"]
        lines.append(
            "The following props have been established in earlier scenes. "
            "Maintain consistency with their names and descriptions:\n"
        )

        for scene_num in sorted(props_by_scene.keys(), reverse=True):
            scene_data = props_by_scene[scene_num]
            props = scene_data["props"]
            heading = scene_data["heading"]

            lines.append(f"### Scene {scene_num}: {heading}")

            # Group by category
            by_category: dict[str, list[str]] = {}
            for prop in props:
                cat = prop.get("category", "miscellaneous")
                if cat not in by_category:
                    by_category[cat] = []

                # Format prop with significance if it's important
                name = prop.get("name", "Unknown")
                sig = prop.get("significance", "practical")
                if sig in ["hero", "plot_device", "character_defining"]:
                    name = f"**{name}** ({sig})"

                by_category[cat].append(name)

            # Output by category
            for category, items in sorted(by_category.items()):
                lines.append(f"- **{category}**: {', '.join(items)}")

            lines.append("")

        # Add summary of recurring/hero props
        hero_props = []
        recurring_props: dict[str, int] = {}

        for scene_data in props_by_scene.values():
            for prop in scene_data["props"]:
                name = prop.get("name", "")
                sig = prop.get("significance", "")

                if sig in ["hero", "plot_device"] and name not in hero_props:
                    hero_props.append(name)

                if name:
                    recurring_props[name] = recurring_props.get(name, 0) + 1

        if hero_props:
            lines.append("### Important Props to Track:")
            lines.append(", ".join(f"**{p}**" for p in hero_props))
            lines.append("")

        recurring = [name for name, count in recurring_props.items() if count > 1]
        if recurring:
            lines.append("### Recurring Props (appearing in multiple scenes):")
            lines.append(", ".join(recurring[:10]))  # Limit to top 10
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_for_agent(
        rows: list[dict[str, Any]],
        agent_name: str,
    ) -> str:
        """Format results based on agent type.

        Args:
            rows: Query results
            agent_name: Name of the agent

        Returns:
            Formatted results appropriate for the agent
        """
        # Special formatting for specific agents
        if "inventory" in agent_name or "props" in agent_name:
            return ContextResultFormatter.format_props_history(rows)

        # Default table format
        return ContextResultFormatter.format_as_table(rows)


# Export main classes
__all__ = [
    "ContextParameters",
    "ContextQueryExecutor",
    "ContextResultFormatter",
]

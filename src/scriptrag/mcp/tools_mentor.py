"""Mentor-related MCP tools."""

import json
from typing import TYPE_CHECKING, Any

from scriptrag.config import get_logger

if TYPE_CHECKING:
    from scriptrag.mcp.server import ScriptRAGMCPServer
from scriptrag.database.connection import DatabaseConnection
from scriptrag.mentors.database import MentorDatabaseOperations
from scriptrag.mentors.registry import MentorRegistry


class MentorTools:
    """Tools for mentor analysis."""

    def __init__(self, server: "ScriptRAGMCPServer"):
        """Initialize mentor tools.

        Args:
            server: Parent MCP server instance
        """
        self.server = server
        self.logger = get_logger(__name__)
        self.scriptrag = server.scriptrag
        self.config = server.config

    async def list_mentors(self, _args: dict[str, Any]) -> dict[str, Any]:
        """List available mentors."""
        registry = MentorRegistry()
        available_mentors = registry.list_mentors()

        # available_mentors is already a list of mentor metadata
        mentors = available_mentors

        return {"mentors": mentors, "count": len(mentors)}

    async def analyze_script_with_mentor(self, args: dict[str, Any]) -> dict[str, Any]:
        """Analyze script with specified mentor."""
        script_id = args.get("script_id")
        mentor_type = args.get("mentor_type")
        options = args.get("options", {})

        if not script_id or not mentor_type:
            raise ValueError("script_id and mentor_type are required")

        # Validate script exists
        script = self.server._validate_script_id(script_id)

        # Run mentor analysis
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            _ = MentorDatabaseOperations(connection)  # TODO: Use when methods available
            registry = MentorRegistry()

            # Get mentor
            mentor_class = registry.get_mentor(mentor_type)
            if not mentor_class:
                raise ValueError(f"Unknown mentor type: {mentor_type}")

            if not callable(mentor_class):
                raise ValueError(f"Invalid mentor class for type: {mentor_type}")

            mentor = mentor_class()

            # Run analysis
            self.logger.info(
                "Starting mentor analysis",
                script_id=script_id,
                mentor_type=mentor_type,
            )

            try:
                analysis_result = mentor.analyze_script(script, **options)

                # Store result (placeholder implementation)
                # TODO: Implement proper mentor result storage
                analysis_id = f"{mentor_type}_{script_id}_{hash(str(analysis_result))}"

                return {
                    "script_id": script_id,
                    "analysis_id": analysis_id,
                    "mentor_type": mentor_type,
                    "status": "completed",
                    "summary": analysis_result.get("summary", {}),
                }

            except Exception as e:
                self.logger.error(
                    "Mentor analysis failed",
                    script_id=script_id,
                    mentor_type=mentor_type,
                    error=str(e),
                )
                raise

    async def get_mentor_results(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get mentor analysis results."""
        script_id = args.get("script_id")
        analysis_id = args.get("analysis_id")
        _ = args.get("mentor_type")  # TODO: Use for filtering

        if not script_id:
            raise ValueError("script_id is required")

        # Validate script exists
        _ = self.server._validate_script_id(script_id)

        # Get results from database
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            _ = MentorDatabaseOperations(connection)  # TODO: Use when methods available

            if analysis_id:
                # Get specific analysis (placeholder implementation)
                # TODO: Implement proper mentor result retrieval
                analysis = {"analysis_id": analysis_id, "placeholder": True}
                if not analysis:
                    raise ValueError(f"Analysis not found: {analysis_id}")

                return {
                    "script_id": script_id,
                    "analysis": analysis,
                }
            # Get all analyses for script (placeholder implementation)
            # TODO: Implement proper mentor result retrieval
            analyses: list[dict[str, Any]] = []

            return {
                "script_id": script_id,
                "analyses": analyses,
                "count": len(analyses),
            }

    async def search_mentor_analyses(self, args: dict[str, Any]) -> dict[str, Any]:
        """Search mentor analyses."""
        query = args.get("query")
        mentor_type = args.get("mentor_type")
        script_id = args.get("script_id")
        limit = args.get("limit", 10)

        if not query:
            raise ValueError("query is required")

        # Search analyses
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            # Build search query
            search_query = """
                SELECT
                    ma.id,
                    ma.script_id,
                    ma.mentor_type,
                    ma.analysis_timestamp,
                    ma.result_json,
                    ma.metadata_json,
                    s.title as script_title
                FROM mentor_analyses ma
                LEFT JOIN scripts s ON s.id = ma.script_id
                WHERE ma.result_json LIKE ?
            """
            params = [f"%{query}%"]

            if mentor_type:
                search_query += " AND ma.mentor_type = ?"
                params.append(mentor_type)

            if script_id:
                # Validate script exists
                script = self.server._validate_script_id(script_id)
                search_query += " AND ma.script_id = ?"
                params.append(str(script.id))

            search_query += " ORDER BY ma.analysis_timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = connection.execute(search_query, tuple(params))

            results = []
            for row in cursor.fetchall():
                try:
                    result = json.loads(row["result_json"])
                    metadata = (
                        json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                    )

                    # Extract relevant portions based on query
                    relevant_sections = self._extract_relevant_sections(result, query)

                    results.append(
                        {
                            "analysis_id": row["id"],
                            "script_id": row["script_id"],
                            "script_title": row["script_title"],
                            "mentor_type": row["mentor_type"],
                            "timestamp": row["analysis_timestamp"],
                            "relevant_sections": relevant_sections,
                            "metadata": metadata,
                        }
                    )
                except json.JSONDecodeError:
                    continue

            return {
                "query": query,
                "results": results,
                "count": len(results),
                "filters": {
                    "mentor_type": mentor_type,
                    "script_id": script_id,
                },
            }

    async def get_mentor_statistics(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get mentor analysis statistics."""
        script_id = args.get("script_id")

        # Get statistics from database
        with DatabaseConnection(str(self.config.get_database_path())) as connection:
            if script_id:
                # Validate script exists
                script = self.server._validate_script_id(script_id)

                # Get stats for specific script
                stats_query = """
                    SELECT
                        mentor_type,
                        COUNT(*) as analysis_count,
                        MAX(analysis_timestamp) as last_analysis
                    FROM mentor_analyses
                    WHERE script_id = ?
                    GROUP BY mentor_type
                """
                cursor = connection.execute(stats_query, (str(script.id),))
            else:
                # Get overall stats
                stats_query = """
                    SELECT
                        mentor_type,
                        COUNT(*) as analysis_count,
                        COUNT(DISTINCT script_id) as scripts_analyzed,
                        MAX(analysis_timestamp) as last_analysis
                    FROM mentor_analyses
                    GROUP BY mentor_type
                """
                cursor = connection.execute(stats_query)

            stats = []
            for row in cursor.fetchall():
                stat_data = {
                    "mentor_type": row["mentor_type"],
                    "analysis_count": row["analysis_count"],
                    "last_analysis": row["last_analysis"],
                }
                if not script_id:
                    stat_data["scripts_analyzed"] = row["scripts_analyzed"]
                stats.append(stat_data)

            # Get total counts
            if script_id:
                total_query = """
                    SELECT COUNT(*) as total
                    FROM mentor_analyses
                    WHERE script_id = ?
                """
                total = connection.execute(total_query, (str(script.id),)).fetchone()[
                    "total"
                ]
            else:
                total_query = """
                    SELECT
                        COUNT(*) as total_analyses,
                        COUNT(DISTINCT script_id) as total_scripts
                    FROM mentor_analyses
                """
                total_row = connection.execute(total_query).fetchone()
                total = total_row["total_analyses"]

            result = {
                "statistics": stats,
                "total_analyses": total,
            }

            if script_id:
                result["script_id"] = script_id
            else:
                result["total_scripts"] = total_row["total_scripts"]

            return result

    def _extract_relevant_sections(
        self, result: dict[str, Any], query: str
    ) -> list[dict[str, Any]]:
        """Extract sections of the result that match the query."""
        sections = []
        query_lower = query.lower()

        def search_dict(obj: dict, path: str = "") -> None:
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key

                if isinstance(value, str):
                    if query_lower in value.lower():
                        sections.append(
                            {
                                "path": current_path,
                                "content": value[:200] + "..."
                                if len(value) > 200
                                else value,
                            }
                        )
                elif isinstance(value, dict):
                    search_dict(value, current_path)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            search_dict(item, f"{current_path}[{i}]")
                        elif isinstance(item, str) and query_lower in item.lower():
                            sections.append(
                                {
                                    "path": f"{current_path}[{i}]",
                                    "content": item[:200] + "..."
                                    if len(item) > 200
                                    else item,
                                }
                            )

        search_dict(result)
        return sections[:5]  # Limit to 5 most relevant sections

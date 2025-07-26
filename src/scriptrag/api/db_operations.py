"""Database operations wrapper for API endpoints."""

import json
from typing import Any
from uuid import uuid4

from scriptrag.api.models import ScriptModel
from scriptrag.config import get_logger
from scriptrag.database import (
    DatabaseConnection,
    EmbeddingPipeline,
    GraphOperations,
    initialize_database,
)

logger = get_logger(__name__)


class DatabaseOperations:
    """High-level database operations for API endpoints."""

    def __init__(self, database_url: str) -> None:
        """Initialize database operations.

        Args:
            database_url: SQLAlchemy database URL
        """
        self.database_url = database_url
        self._connection: DatabaseConnection | None = None
        self._graph_ops: GraphOperations | None = None
        self._embedding_pipeline: EmbeddingPipeline | None = None

    async def initialize(self) -> None:
        """Initialize database connection and schema."""
        # Extract database path from URL
        db_path = self.database_url.replace("sqlite+aiosqlite:///", "")

        # Initialize database schema
        initialize_database(db_path)

        # Create connection
        self._connection = DatabaseConnection(db_path)
        self._graph_ops = GraphOperations(self._connection)
        self._embedding_pipeline = EmbeddingPipeline(self._connection)

        logger.info("Database operations initialized", db_url=self.database_url)

    async def close(self) -> None:
        """Close database connections."""
        if self._connection:
            # Connection doesn't have async close yet
            pass

    async def store_script(self, script: ScriptModel) -> int:
        """Store a script in the database.

        Args:
            script: Script model to store

        Returns:
            Script ID
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        # Store script using connection
        with self._connection.transaction() as conn:
            # Insert script using raw SQL
            script_uuid = str(uuid4())
            cursor = conn.execute(
                """
                INSERT INTO scripts (id, title, author, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    script_uuid,
                    script.title,
                    script.author,
                    json.dumps(script.metadata or {}),
                ),
            )
            script_id = cursor.lastrowid

            # Insert scenes
            for scene in script.scenes:
                conn.execute(
                    """
                    INSERT INTO scenes (
                        id, script_id, script_order, heading, description
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        script_uuid,
                        scene.scene_number,
                        scene.heading,
                        scene.content,
                    ),
                )

        logger.info("Stored script", script_id=script_id, title=script.title)
        return script_id or 0

    async def get_script(self, script_id: int) -> ScriptModel | None:
        """Get a script by ID.

        Args:
            script_id: Script ID

        Returns:
            Script model or None if not found
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.get_connection() as conn:
            # Get script using raw SQL
            script_result = conn.execute(
                "SELECT * FROM scripts WHERE id = ?", (script_id,)
            ).fetchone()

            if not script_result:
                return None

            # Get scenes
            scenes_result = conn.execute(
                "SELECT * FROM scenes WHERE script_id = ? ORDER BY script_order",
                (script_result["id"],),
            ).fetchall()

            # Parse metadata if it's JSON string
            metadata = script_result["metadata_json"]
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}

            # Build model
            from scriptrag.api.models import SceneModel

            scenes = [
                SceneModel(
                    id=scene["id"],
                    script_id=scene["script_id"],
                    scene_number=scene["script_order"],
                    heading=scene["heading"] or "",
                    content=scene["description"] or "",
                    characters=self._extract_characters(scene["description"] or ""),
                )
                for scene in scenes_result
            ]

            return ScriptModel(
                id=int(script_result["id"]) if script_result["id"].isdigit() else 0,
                title=script_result["title"],
                author=script_result["author"],
                metadata=metadata,
                scenes=scenes,
                characters=set(),  # Will be populated from scenes
            )

    async def list_scripts(self) -> list[dict[str, Any]]:
        """List all scripts with basic info.

        Returns:
            List of script summaries
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.get_connection() as conn:
            # Get scripts with scene count using raw SQL
            result = conn.execute(
                """
                SELECT s.*, COUNT(sc.id) as scene_count
                FROM scripts s
                LEFT JOIN scenes sc ON s.id = sc.script_id
                GROUP BY s.id
                ORDER BY s.created_at DESC
                """
            ).fetchall()

            return [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "author": row["author"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "scene_count": row["scene_count"],
                    "character_count": 0,  # TODO: implement character counting
                    "has_embeddings": False,  # TODO: check embeddings
                }
                for row in result
            ]

    async def delete_script(self, script_id: int) -> None:
        """Delete a script and all related data.

        Args:
            script_id: Script ID to delete
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.transaction() as conn:
            conn.execute("DELETE FROM scripts WHERE id = ?", (script_id,))

        logger.info("Deleted script", script_id=script_id)

    async def generate_embeddings(
        self, script_id: int, regenerate: bool = False
    ) -> dict[str, Any]:
        """Generate embeddings for a script.

        Args:
            script_id: Script ID
            regenerate: Force regeneration of existing embeddings

        Returns:
            Generation results
        """
        if not self._embedding_pipeline:
            raise RuntimeError("Database not initialized")

        # Get script
        script = await self.get_script(script_id)
        if not script:
            raise ValueError(f"Script {script_id} not found")

        # Generate embeddings
        # Note: The embedding pipeline is async, so we await it
        results = await self._embedding_pipeline.process_script(
            str(script_id), force_refresh=regenerate
        )

        return {
            "script_id": script_id,
            "scenes_processed": results.get("embeddings_generated", 0),
            "scenes_skipped": results.get("embeddings_skipped", 0),
            "processing_time": results.get("processing_time", 0.0),
        }

    async def search_scenes(
        self,
        query: str | None = None,
        script_id: int | None = None,
        character: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search scenes with filters.

        Args:
            query: Text search query
            script_id: Filter by script
            character: Filter by character
            limit: Result limit
            offset: Result offset

        Returns:
            Search results
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.get_connection() as conn:
            # Build SQL query with conditions
            conditions: list[str] = []
            params: list[Any] = []

            if script_id:
                conditions.append("sc.script_id = ?")
                params.append(script_id)
            if query:
                conditions.append("(sc.description LIKE ? OR sc.heading LIKE ?)")
                params.extend([f"%{query}%", f"%{query}%"])
            if character:
                conditions.append("sc.description LIKE ?")
                params.append(f"%{character.upper()}%")

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            # Count total
            count_sql = f"""
                SELECT COUNT(*)
                FROM scenes sc
                JOIN scripts s ON sc.script_id = s.id
                {where_clause}
            """
            total = conn.execute(count_sql, params).fetchone()[0]

            # Get results
            results_sql = f"""
                SELECT sc.*, s.title
                FROM scenes sc
                JOIN scripts s ON sc.script_id = s.id
                {where_clause}
                ORDER BY sc.script_order
                LIMIT ? OFFSET ?
            """
            results = conn.execute(results_sql, [*params, limit, offset]).fetchall()

            return {
                "results": [
                    {
                        "scene": {
                            "id": row["id"],
                            "script_id": row["script_id"],
                            "scene_number": row["script_order"],
                            "heading": row["heading"] or "",
                            "content": row["description"] or "",
                            "character_count": len(
                                self._extract_characters(row["description"] or "")
                            ),
                            "word_count": len((row["description"] or "").split()),
                            "page_start": None,
                            "page_end": None,
                            "has_embedding": False,  # TODO: check embeddings
                        },
                        "score": None,
                        "highlights": [],
                    }
                    for row in results
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    async def semantic_search(
        self,
        query: str,
        script_id: int | None = None,
        threshold: float = 0.7,  # noqa: ARG002
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search scenes by semantic similarity.

        Args:
            query: Search query
            script_id: Filter by script
            threshold: Similarity threshold
            limit: Result limit

        Returns:
            Search results with similarity scores
        """
        if not self._embedding_pipeline:
            raise RuntimeError("Database not initialized")

        # Simplified semantic search - in a real implementation this would
        # use embeddings
        # For now, fallback to text search
        text_results = await self.search_scenes(
            query=query, script_id=script_id, limit=limit
        )

        # Convert to semantic search format with dummy scores
        results = []
        for item in text_results["results"]:
            results.append(
                {
                    "scene": item["scene"],
                    "score": 0.8,  # Dummy score above threshold
                    "highlights": [],
                }
            )

        return {
            "results": results,
            "total": len(results),
            "limit": limit,
            "offset": 0,
        }

    def _extract_characters(self, content: str) -> list[str]:
        """Extract character names from scene content.

        Args:
            content: Scene content

        Returns:
            List of character names
        """
        characters = []
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            # Character names are typically in uppercase
            if (
                line
                and line.isupper()
                and not line.startswith("(")
                and not line.endswith(":")
                and not any(
                    keyword in line
                    for keyword in [
                        "INT.",
                        "EXT.",
                        "FADE",
                        "CUT",
                        "DISSOLVE",
                        "THE END",
                    ]
                )
            ):
                characters.append(line)

        return list(set(characters))

    async def get_scene(self, scene_id: int) -> dict[str, Any] | None:
        """Get a scene by ID."""
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.get_connection() as conn:
            result = conn.execute(
                "SELECT * FROM scenes WHERE id = ?", (scene_id,)
            ).fetchone()

            if not result:
                return None

            return {
                "id": result["id"],
                "script_id": result["script_id"],
                "scene_number": result["script_order"],
                "heading": result["heading"] or "",
                "content": result["description"] or "",
                "character_count": len(
                    self._extract_characters(result["description"] or "")
                ),
                "word_count": len((result["description"] or "").split()),
                "page_start": None,
                "page_end": None,
                "has_embedding": False,  # TODO: check embeddings
            }

    async def create_scene(
        self, script_id: int, scene_number: int, heading: str, content: str
    ) -> int:
        """Create a new scene."""
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scenes (id, script_id, script_order, heading, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid4()), str(script_id), scene_number, heading, content),
            )
            return cursor.lastrowid or 0

    async def update_scene(
        self,
        scene_id: int,
        scene_number: int | None = None,
        heading: str | None = None,
        content: str | None = None,
    ) -> None:
        """Update a scene."""
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.transaction() as conn:
            updates: list[str] = []
            params: list[Any] = []

            if scene_number is not None:
                updates.append("script_order = ?")
                params.append(scene_number)
            if heading is not None:
                updates.append("heading = ?")
                params.append(heading)
            if content is not None:
                updates.append("description = ?")
                params.append(content)

            if updates:
                params.append(scene_id)
                sql = f"UPDATE scenes SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)

    async def delete_scene(self, scene_id: int) -> None:
        """Delete a scene."""
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.transaction() as conn:
            conn.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))

    async def shift_scene_numbers(self, script_id: int, from_scene_number: int) -> None:
        """Shift scene numbers to make room for insertion."""
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.transaction() as conn:
            # Increment scene numbers >= from_scene_number
            conn.execute(
                """
                UPDATE scenes
                SET script_order = script_order + 1
                WHERE script_id = ? AND script_order >= ?
                """,
                (script_id, from_scene_number),
            )

    async def get_character_graph(
        self,
        character_name: str,
        script_id: int | None = None,  # noqa: ARG002
        depth: int = 2,  # noqa: ARG002
        min_interaction_count: int = 1,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Get character relationship graph data."""
        # Simplified implementation - TODO: use parameters
        return {
            "nodes": [
                {
                    "id": f"char_{character_name}",
                    "type": "character",
                    "label": character_name,
                    "properties": {"main": True},
                }
            ],
            "edges": [],
        }

    async def get_timeline_graph(
        self,
        script_id: int,
        group_by: str = "act",  # noqa: ARG002
        include_characters: bool = True,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Get timeline visualization graph data."""
        # Simplified implementation - TODO: use parameters
        return {
            "nodes": [
                {
                    "id": f"script_{script_id}",
                    "type": "scene",
                    "label": f"Script {script_id}",
                    "properties": {},
                }
            ],
            "edges": [],
        }

    async def get_location_graph(self, script_id: int) -> dict[str, Any]:
        """Get location-based graph data for a specific script."""
        if not self._connection:
            raise RuntimeError("Database not initialized")

        # Query locations from the specified script
        with self._connection.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT location_id, COUNT(*) as scene_count
                FROM scenes
                WHERE script_id = ? AND location_id IS NOT NULL
                GROUP BY location_id
                ORDER BY scene_count DESC
                """,
                (script_id,),
            ).fetchall()

        nodes = []
        for i, row in enumerate(rows):
            nodes.append(
                {
                    "id": f"loc_{i}",
                    "type": "location",
                    "label": f"Location {row['location_id']}",
                    "properties": {
                        "scene_count": row["scene_count"],
                        "script_id": script_id,
                    },
                }
            )

        # For now, return nodes without edges
        # (location connections could be added later)
        return {
            "nodes": nodes,
            "edges": [],
        }

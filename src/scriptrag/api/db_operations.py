"""Database operations wrapper for API endpoints."""

import contextlib
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
from scriptrag.models import SceneDependency

logger = get_logger(__name__)


class DatabaseOperations:
    """High-level database operations for API endpoints.

    WARNING: Current implementation uses synchronous SQLite operations
    in async functions, which blocks the event loop. This is acceptable
    for development/testing but should be fixed for production use.

    TODO: Implement proper async database operations using one of:
    1. aiosqlite for native async SQLite support
    2. asyncio.run_in_executor() to run sync operations in thread pool
    3. SQLAlchemy async with aiosqlite driver

    TODO: Add proper connection pooling:
    1. Current implementation uses thread-local connections
    2. Consider SQLAlchemy connection pooling
    3. Add connection health checks and retry logic
    """

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
        # Log warning about async/sync mismatch
        logger.warning(
            "DatabaseOperations uses synchronous SQLite operations in async functions. "
            "This blocks the event loop and should be fixed for production use."
        )

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

    async def store_script(self, script: ScriptModel) -> str:
        """Store a script in the database.

        Args:
            script: Script model to store

        Returns:
            Script ID
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        # Store script using connection
        script_uuid = str(uuid4())
        scene_uuids = []

        with self._connection.transaction() as conn:
            # Insert script using raw SQL
            conn.execute(
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
            script_id = script_uuid

            # Insert scenes
            for scene in script.scenes:
                scene_uuid = str(uuid4())
                scene_uuids.append((scene_uuid, scene))
                conn.execute(
                    """
                    INSERT INTO scenes (
                        id, script_id, script_order, heading, description
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        scene_uuid,
                        script_uuid,
                        scene.scene_number,
                        scene.heading,
                        scene.content,
                    ),
                )

        # Create graph nodes after the transaction is complete
        if self._graph_ops:
            from uuid import UUID

            from scriptrag.models import Scene as SceneModel
            from scriptrag.models import Script as ScriptModel

            # Create script node in graph
            script_model = ScriptModel(
                id=UUID(script_uuid),
                title=script.title,
                author=script.author,
            )
            # Note: create_script_graph returns the graph node ID, not the database UUID
            script_graph_node_id = self._graph_ops.create_script_graph(script_model)

            # Create scene nodes in graph
            for scene_uuid, scene in scene_uuids:
                scene_model = SceneModel(
                    id=UUID(scene_uuid),
                    script_id=UUID(script_uuid),
                    script_order=scene.scene_number,
                    heading=scene.heading,
                    description=scene.content,
                )
                self._graph_ops.create_scene_node(
                    scene=scene_model,
                    script_node_id=script_graph_node_id,  # Use the graph node ID here!
                )

        logger.info("Stored script", script_id=script_id, title=script.title)
        return script_uuid

    async def get_script(self, script_id: str) -> ScriptModel | None:
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
                    characters=list(
                        self._extract_characters(scene["description"] or "")
                    ),
                )
                for scene in scenes_result
            ]

            return ScriptModel(
                id=script_result["id"],
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
            # Get scripts with scene count, character count, and embeddings check
            result = conn.execute(
                """
                SELECT
                    s.*,
                    COUNT(DISTINCT sc.id) as scene_count,
                    COUNT(DISTINCT c.id) as character_count,
                    EXISTS(
                        SELECT 1
                        FROM embeddings e
                        INNER JOIN scenes sc2 ON e.entity_id = sc2.id
                        WHERE sc2.script_id = s.id
                        AND e.entity_type = 'scene'
                        LIMIT 1
                    ) as has_embeddings
                FROM scripts s
                LEFT JOIN scenes sc ON s.id = sc.script_id
                LEFT JOIN characters c ON s.id = c.script_id
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
                    "character_count": row["character_count"],
                    "has_embeddings": bool(row["has_embeddings"]),
                }
                for row in result
            ]

    async def delete_script(self, script_id: str) -> None:
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
        self, script_id: str, regenerate: bool = False
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
        script_id: str | None = None,
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

        # Enforce server-side pagination limits
        if limit > 100:
            limit = 100
        if limit < 1:
            limit = 1
        if offset < 0:
            offset = 0

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
                SELECT
                    sc.*,
                    s.title,
                    EXISTS(
                        SELECT 1
                        FROM embeddings e
                        WHERE e.entity_id = sc.id
                        AND e.entity_type = 'scene'
                        LIMIT 1
                    ) as has_embedding
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
                            "has_embedding": bool(row["has_embedding"]),
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
        query: str,  # noqa: ARG002
        script_id: str | None = None,  # noqa: ARG002
        threshold: float = 0.7,  # noqa: ARG002
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search scenes by semantic similarity.

        NOTE: This feature is not yet implemented. Semantic search requires
        embedding generation and vector similarity computation infrastructure.

        Args:
            query: Search query
            script_id: Filter by script
            threshold: Similarity threshold
            limit: Result limit

        Returns:
            Search results with similarity scores

        Raises:
            NotImplementedError: Semantic search not yet implemented
        """
        if not self._embedding_pipeline:
            raise RuntimeError("Database not initialized")

        # Enforce server-side pagination limits
        if limit > 100:
            limit = 100
        if limit < 1:
            limit = 1

        # Semantic search requires proper embedding infrastructure
        # For now, raise an error indicating the limitation
        raise NotImplementedError(
            "Semantic search requires embedding generation and vector similarity "
            "computation. Please generate embeddings first using POST "
            "/api/v1/embeddings/{script_id}, then use regular text search via "
            "GET /api/v1/search/scenes instead."
        )

    def _extract_characters(self, content: str) -> set[str]:
        """Extract character names from scene content.

        Args:
            content: Scene content

        Returns:
            Set of character names (deduplicated)
        """
        characters = set()
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            # Character names are typically in uppercase, may have parentheticals
            if (
                line
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
                # Clean character names by removing parentheticals like (CONT'D), etc.
                cleaned_name = line.split("(")[0].strip()
                # Check if the cleaned name is uppercase (character name)
                if cleaned_name and cleaned_name.isupper():
                    characters.add(cleaned_name)

        return characters

    async def get_embeddings_coverage(self, script_id: str) -> dict[str, Any]:
        """Get embeddings coverage statistics for a script.

        Args:
            script_id: Script ID

        Returns:
            Dictionary with coverage statistics
        """
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.get_connection() as conn:
            # Get total scenes and embedded scenes count
            result = conn.execute(
                """
                SELECT
                    COUNT(DISTINCT sc.id) as total_scenes,
                    COUNT(DISTINCT e.entity_id) as embedded_scenes
                FROM scenes sc
                LEFT JOIN embeddings e ON e.entity_id = sc.id
                    AND e.entity_type = 'scene'
                WHERE sc.script_id = ?
                """,
                (script_id,),
            ).fetchone()

            total_scenes = result["total_scenes"] or 0
            embedded_scenes = result["embedded_scenes"] or 0
            coverage_percentage = (
                (embedded_scenes / total_scenes * 100) if total_scenes > 0 else 0
            )

            return {
                "script_id": script_id,
                "total_scenes": total_scenes,
                "embedded_scenes": embedded_scenes,
                "coverage_percentage": round(coverage_percentage, 2),
                "has_full_coverage": (
                    embedded_scenes == total_scenes and total_scenes > 0
                ),
            }

    async def get_scene(self, scene_id: str) -> dict[str, Any] | None:
        """Get a scene by ID."""
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.get_connection() as conn:
            result = conn.execute(
                """
                SELECT
                    sc.*,
                    EXISTS(
                        SELECT 1
                        FROM embeddings e
                        WHERE e.entity_id = sc.id
                        AND e.entity_type = 'scene'
                        LIMIT 1
                    ) as has_embedding
                FROM scenes sc
                WHERE sc.id = ?
                """,
                (scene_id,),
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
                "has_embedding": bool(result["has_embedding"]),
            }

    async def create_scene(
        self, script_id: str, scene_number: int, heading: str, content: str
    ) -> str:
        """Create a new scene."""
        if not self._connection:
            raise RuntimeError("Database not initialized")

        scene_uuid = str(uuid4())

        with self._connection.transaction() as conn:
            conn.execute(
                """
                INSERT INTO scenes (id, script_id, script_order, heading, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (scene_uuid, script_id, scene_number, heading, content),
            )

        # NOTE: Graph operations are disabled for individual scene creation
        # The graph integration expects scenes to be created as part of
        # full script import where the script graph node already exists.
        # Individual scene CRUD operations currently only work with the
        # database, not the graph.

        return scene_uuid

    async def update_scene(
        self,
        scene_id: str,
        scene_number: int | None = None,
        heading: str | None = None,
        content: str | None = None,
    ) -> bool:
        """Update a scene."""
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.transaction() as conn:
            # First check if scene exists
            result = conn.execute(
                "SELECT id FROM scenes WHERE id = ?", (scene_id,)
            ).fetchone()

            if not result:
                return False

            # Use predefined queries to prevent SQL injection
            if scene_number is not None:
                conn.execute(
                    "UPDATE scenes SET script_order = ? WHERE id = ?",
                    (scene_number, scene_id),
                )
            if heading is not None:
                conn.execute(
                    "UPDATE scenes SET heading = ? WHERE id = ?", (heading, scene_id)
                )
            if content is not None:
                conn.execute(
                    "UPDATE scenes SET description = ? WHERE id = ?",
                    (content, scene_id),
                )

            return True

    async def delete_scene(self, scene_id: str) -> None:
        """Delete a scene."""
        if not self._connection:
            raise RuntimeError("Database not initialized")

        with self._connection.transaction() as conn:
            conn.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))

    async def shift_scene_numbers(self, script_id: str, from_scene_number: int) -> None:
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
        script_id: str | None = None,  # noqa: ARG002
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
        script_id: str,
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

    async def get_location_graph(self, script_id: str) -> dict[str, Any]:
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

    # Scene ordering operations
    async def reorder_scenes(
        self,
        script_id: str,
        scene_ids: list[str],
        order_type: str = "script",
    ) -> bool:
        """Reorder scenes according to provided order."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        # Convert order_type string to enum
        from scriptrag.models import SceneOrderType

        try:
            order_type_enum = SceneOrderType(order_type)
        except ValueError:
            logger.error(f"Invalid order type: {order_type}")
            return False

        return self._graph_ops.reorder_scenes(script_id, order_type_enum, scene_ids)

    async def infer_temporal_order(self, script_id: str) -> dict[str, int]:
        """Infer temporal (chronological) order of scenes."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        return self._graph_ops.infer_temporal_order(script_id)

    async def analyze_scene_dependencies(self, script_id: str) -> list[SceneDependency]:
        """Analyze and create logical dependencies between scenes."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        # The analyze_scene_dependencies method in GraphOperations calls
        # analyze_logical_dependencies which returns list[SceneDependency]
        dependencies = self._graph_ops.analyze_scene_dependencies(script_id)
        # Ensure we return the correct type
        return dependencies if isinstance(dependencies, list) else []

    async def get_scene_dependencies(
        self,
        scene_id: str,
        direction: str = "both",  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """Get dependencies for a specific scene."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        dependencies = self._graph_ops.get_scene_dependencies(scene_id)
        # Convert SceneDependency objects to dict format expected by API
        return [
            {
                "from_scene_id": str(dep.from_scene_id),
                "to_scene_id": str(dep.to_scene_id),
                "dependency_type": dep.dependency_type.value,
                "strength": dep.strength,
                "description": dep.description,
            }
            for dep in dependencies
        ]

    async def calculate_logical_order(self, script_id: str) -> list[str]:
        """Calculate logical order based on dependencies."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        return self._graph_ops.calculate_logical_order(script_id)

    async def validate_scene_ordering(self, script_id: str) -> dict[str, Any]:
        """Validate consistency across different ordering systems."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        return self._graph_ops.validate_scene_ordering(script_id)

    # Enhanced Scene Operations for Phase 5.2
    async def update_scene_with_graph_propagation(
        self,
        scene_id: str,
        scene_number: int | None = None,
        heading: str | None = None,
        content: str | None = None,
        location: str | None = None,
        time_of_day: str | None = None,
    ) -> bool:
        """Update scene with enhanced graph propagation."""
        # First update basic fields using existing method
        if scene_number is not None or heading is not None or content is not None:
            success = await self.update_scene(scene_id, scene_number, heading, content)
            if not success:
                return False

        # Graph operations are optional - if they fail, we still consider
        # the update successful since the database was updated
        if self._graph_ops:
            # Note: scene_id is the database UUID, not the graph node ID
            # The graph operations will fail if the scene doesn't have a graph node
            with contextlib.suppress(Exception):
                # Create metadata dict with accepted fields
                metadata = {}
                if heading is not None:
                    metadata["heading"] = heading
                if content is not None:
                    metadata["description"] = content
                if time_of_day is not None:
                    metadata["time_of_day"] = time_of_day
                if location is not None:
                    metadata["location"] = location

                self._graph_ops.update_scene_metadata(
                    scene_node_id=scene_id, metadata=metadata, merge=True
                )

        # Always return True if we got this far - the database update succeeded
        return True

    async def delete_scene_with_references(self, scene_id: str) -> bool:
        """Delete scene with reference maintenance."""
        # First delete from database
        await self.delete_scene(scene_id)

        # Then try to delete from graph if available
        if self._graph_ops:
            with contextlib.suppress(Exception):
                self._graph_ops.delete_scene_with_references(scene_id)

        return True

    async def inject_scene_at_position(
        self,
        script_id: str,
        scene_data: Any,  # SceneCreateRequest
        position: int,
    ) -> str | None:
        """Inject scene at specific position with full re-indexing."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        # Convert script_id to script_node_id
        # This assumes script_id is the same as script_node_id
        # In a real implementation, you might need to query for the script node
        from uuid import UUID, uuid4

        from scriptrag.models import Scene

        # Use the scene ID from scene_data if provided, otherwise generate new
        scene_id = getattr(scene_data, "id", None)
        if scene_id and isinstance(scene_id, str):
            # Convert string UUID to UUID object
            scene_uuid = UUID(scene_id)
        else:
            # Generate new UUID if not provided
            scene_uuid = uuid4()

        scene = Scene(
            id=scene_uuid,
            heading=scene_data.heading,
            description=scene_data.content,
            script_order=scene_data.scene_number,
            script_id=UUID(script_id),
        )

        return self._graph_ops.inject_scene_at_position(
            new_scene=scene,
            script_node_id=script_id,
            position=position,
        )

    async def update_scene_metadata(
        self,
        scene_id: str,
        heading: str | None = None,
        description: str | None = None,
        time_of_day: str | None = None,
        location: str | None = None,
        propagate_to_graph: bool = True,  # noqa: ARG002
    ) -> bool:
        """Update scene metadata with optional graph propagation."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        # Create metadata dict with only the fields accepted by update_scene_metadata
        metadata = {}
        if heading is not None:
            metadata["heading"] = heading
        if description is not None:
            metadata["description"] = description
        if time_of_day is not None:
            metadata["time_of_day"] = time_of_day
        if location is not None:
            metadata["location"] = location

        return self._graph_ops.update_scene_metadata(
            scene_node_id=scene_id, metadata=metadata, merge=True
        )

    async def validate_story_continuity(self, script_id: str) -> dict[str, Any]:
        """Validate story continuity across all scenes."""
        if not self._graph_ops:
            raise RuntimeError("Database not initialized")

        # Convert script_id to script_node_id if needed
        return self._graph_ops.validate_story_continuity(script_id)

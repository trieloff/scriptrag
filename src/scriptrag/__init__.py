"""ScriptRAG: A Graph-Based Screenwriting Assistant.

ScriptRAG combines fountain parsing, graph databases, and local LLMs to create
an intelligent screenplay assistant using the GraphRAG (Graph + Retrieval-Augmented
Generation) pattern.
"""

import json
from pathlib import Path
from typing import Any

# Configuration imports
from .config import (
    ScriptRAGSettings,
    get_logger,
    get_settings,
    load_settings,
    setup_logging_for_environment,
)

# LLM imports
from .llm import LLMClient as ActualLLMClient
from .llm import create_llm_client

# Model imports
from .models import Script

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"
__license__ = "MIT"

# Package metadata
__all__ = [
    "FountainParser",
    "GraphDatabase",
    "LLMClient",
    "Script",
    "ScriptRAG",
    "ScriptRAGSettings",
    "__version__",
    "create_llm_client",
    "get_settings",
    "load_settings",
    "setup_logging_for_environment",
]

# Imports will be added as modules are created


# For now, we'll define placeholder classes
class ScriptRAG:
    """Main ScriptRAG interface."""

    def __init__(
        self,
        config: ScriptRAGSettings | None = None,
        config_file: Path | None = None,
        llm_endpoint: str | None = None,
        db_path: str | None = None,
    ) -> None:
        """Initialize ScriptRAG with configuration.

        Args:
            config: ScriptRAG configuration object
            config_file: Path to configuration file
            llm_endpoint: Override LLM endpoint (for backward compatibility)
            db_path: Override database path (for backward compatibility)
        """
        # Load or use provided configuration
        if config:
            self.config = config
        elif config_file:
            self.config = load_settings(config_file)
        else:
            self.config = get_settings()

        # Apply backward compatibility overrides
        if llm_endpoint:
            self.config.llm.endpoint = llm_endpoint
        if db_path:
            self.config.database.path = Path(db_path)

        # Initialize logging
        setup_logging_for_environment(
            environment=self.config.environment,
            log_file=self.config.get_log_file_path(),
        )

        self.logger = get_logger(__name__)
        self.logger.info(
            "ScriptRAG initialized",
            environment=self.config.environment,
            llm_endpoint=self.config.llm.endpoint,
            database_path=str(self.config.get_database_path()),
        )

        # TODO: Initialize components
        self._fountain_parser: FountainParser | None = None
        self._graph_db: GraphDatabase | None = None
        self._llm_client: ActualLLMClient | None = None

    def parse_fountain(self, path: str) -> Script:
        """Parse a screenplay in Fountain format.

        Args:
            path: Path to the Fountain file

        Returns:
            Script object containing parsed screenplay data
        """
        self.logger.info("Parsing Fountain screenplay", path=path)

        # Import here to avoid circular dependencies
        from .database import create_database, get_connection, initialize_database
        from .database.operations import GraphOperations
        from .parser import FountainParser

        # Ensure database exists and is initialized
        db_path = self.config.get_database_path()
        if not db_path.exists():
            self.logger.info("Creating new database", path=str(db_path))
            db_path.parent.mkdir(parents=True, exist_ok=True)
            create_database(db_path)

        # Initialize database schema if needed
        initialize_database(db_path)

        # Parse the fountain file
        parser = FountainParser()
        script = parser.parse_file(path)

        # Save script data to database
        with get_connection() as conn:
            # Save script
            conn.execute(
                """
                INSERT INTO scripts (id, title, fountain_source, source_file,
                                   author, description, genre, logline, title_page_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(script.id),
                    script.title,
                    script.fountain_source,
                    script.source_file,
                    script.author,
                    script.description,
                    script.genre,
                    script.logline,
                    json.dumps(script.title_page) if script.title_page else None,
                ),
            )

            # Save characters
            for char in parser.get_characters():
                conn.execute(
                    """
                    INSERT INTO characters (id, script_id, name, aliases_json)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        str(char.id),
                        str(script.id),
                        char.name,
                        json.dumps(char.aliases) if char.aliases else None,
                    ),
                )

            # Save scenes and locations
            from uuid import uuid4

            location_map = {}  # Map location text to ID

            for scene in parser.get_scenes():
                location_id = None

                # Save location if present
                if scene.location:
                    # Create a unique key for the location
                    location_key = (
                        f"{scene.location.interior}:{scene.location.name}:"
                        f"{scene.location.time}"
                    )

                    if location_key not in location_map:
                        location_id = str(uuid4())
                        location_map[location_key] = location_id

                        conn.execute(
                            """
                            INSERT INTO locations (id, script_id, interior, name,
                                                 time_of_day, raw_text)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """,
                            (
                                location_id,
                                str(script.id),
                                scene.location.interior,
                                scene.location.name,
                                scene.location.time,
                                scene.location.raw_text,
                            ),
                        )
                    else:
                        location_id = location_map[location_key]

                # Save scene
                conn.execute(
                    """
                    INSERT INTO scenes (id, script_id, location_id, heading,
                                      script_order, time_of_day)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        str(scene.id),
                        str(script.id),
                        location_id,
                        scene.heading,
                        scene.script_order,
                        scene.location.time if scene.location else None,
                    ),
                )

            # Build graph structure
            ops = GraphOperations(conn)
            ops.create_script_graph(script)

            # Note: We're skipping async LLM enrichment for now
            self.logger.info("Graph building and LLM enrichment not yet implemented")

        self.logger.info(
            "Successfully parsed and stored screenplay",
            title=script.title,
            scenes=len(script.scenes),
            characters=len(script.characters),
        )

        return script

    def search_scenes(self, **kwargs: Any) -> list[Any]:
        """Search for scenes based on various criteria.

        Returns:
            List of matching scenes
        """
        self.logger.debug("Searching scenes", criteria=kwargs)
        raise NotImplementedError("Search not yet implemented")

    def update_scene(self, scene_id: int, **kwargs: Any) -> None:
        """Update a scene with new information."""
        self.logger.info("Updating scene", scene_id=scene_id, changes=kwargs)
        raise NotImplementedError("Scene update not yet implemented")

    @property
    def fountain_parser(self) -> "FountainParser":
        """Get the fountain parser instance."""
        if self._fountain_parser is None:
            self._fountain_parser = FountainParser(self.config)
        if self._fountain_parser is None:
            raise RuntimeError("Failed to initialize fountain parser")
        return self._fountain_parser

    @property
    def graph_db(self) -> "GraphDatabase":
        """Get the graph database instance."""
        if self._graph_db is None:
            self._graph_db = GraphDatabase(self.config)
        if self._graph_db is None:
            raise RuntimeError("Failed to initialize graph database")
        return self._graph_db

    @property
    def llm_client(self) -> ActualLLMClient:
        """Get the LLM client instance."""
        if self._llm_client is None:
            self._llm_client = create_llm_client()
        if self._llm_client is None:
            raise RuntimeError("Failed to initialize LLM client")
        return self._llm_client


class FountainParser:
    """Fountain format parser placeholder."""

    def __init__(self, config: ScriptRAGSettings) -> None:
        """Initialize parser with configuration."""
        self.config = config
        self.logger = get_logger(__name__)


class GraphDatabase:
    """Graph database interface placeholder."""

    def __init__(self, config: ScriptRAGSettings) -> None:
        """Initialize database with configuration."""
        self.config = config
        self.logger = get_logger(__name__)


# Alias for backward compatibility
LLMClient = ActualLLMClient

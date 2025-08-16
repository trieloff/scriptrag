"""ScriptRAG main entry point."""

import asyncio
from pathlib import Path
from typing import Any

from scriptrag.api.database import DatabaseInitializer
from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.api.index import IndexCommand
from scriptrag.config import ScriptRAGSettings, get_logger, get_settings
from scriptrag.exceptions import DatabaseError
from scriptrag.parser import FountainParser, Script
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import SearchMode, SearchResponse
from scriptrag.search.parser import QueryParser

logger = get_logger(__name__)


class ScriptRAG:
    """Main ScriptRAG class for screenplay analysis."""

    def __init__(
        self,
        settings: ScriptRAGSettings | None = None,
        auto_init_db: bool = True,
    ) -> None:
        """Initialize ScriptRAG instance.

        Args:
            settings: Configuration settings (optional, uses defaults if not provided)
            auto_init_db: Automatically initialize database if it doesn't exist
        """
        self.settings = settings or get_settings()
        self.parser = FountainParser()
        self.search_engine = SearchEngine(self.settings)
        self.query_parser = QueryParser()
        self.index_command = IndexCommand(settings=self.settings)
        self.db_ops = DatabaseOperations(self.settings)

        # Initialize database if requested and it doesn't exist
        if auto_init_db and not self.db_ops.check_database_exists():
            logger.info("Database not found, initializing...")
            initializer = DatabaseInitializer()
            initializer.initialize_database(settings=self.settings)
            logger.info("Database initialized successfully")

    def parse_fountain(self, path: str | Path) -> Script:
        """Parse a Fountain format screenplay.

        Args:
            path: Path to the Fountain file (string or Path object)

        Returns:
            Parsed Script object containing scenes, characters, and metadata

        Raises:
            FileNotFoundError: If the specified file doesn't exist
            ParseError: If the file cannot be parsed as valid Fountain format
        """
        file_path = Path(path) if isinstance(path, str) else path

        if not file_path.exists():
            raise FileNotFoundError(f"Fountain file not found: {file_path}")

        logger.debug(f"Parsing Fountain file: {file_path}")
        script = self.parser.parse_file(file_path)
        logger.info(
            f"Successfully parsed '{script.title or 'Untitled'}' "
            f"with {len(script.scenes)} scenes"
        )

        return script

    def index_script(self, path: str | Path, dry_run: bool = False) -> dict[str, Any]:
        """Index a parsed screenplay into the database.

        Args:
            path: Path to the Fountain file to index
            dry_run: If True, preview changes without applying them

        Returns:
            Dictionary with indexing results including:
                - script_id: Database ID of the indexed script
                - indexed: Whether indexing was successful
                - updated: Whether this was an update to existing script
                - scenes_indexed: Number of scenes indexed
                - characters_indexed: Number of characters indexed
                - dialogues_indexed: Number of dialogues indexed
                - actions_indexed: Number of actions indexed

        Raises:
            FileNotFoundError: If the specified file doesn't exist
            DatabaseError: If database operations fail
        """
        file_path = Path(path) if isinstance(path, str) else path

        if not file_path.exists():
            raise FileNotFoundError(f"Fountain file not found: {file_path}")

        # Use async index method with existing or new event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, we can't use run_until_complete
            # This would need to be handled differently in async context
            result = asyncio.run_coroutine_threadsafe(
                self.index_command._index_single_script(file_path, dry_run), loop
            ).result()
        except RuntimeError:
            # No running loop, create one
            result = asyncio.run(
                self.index_command._index_single_script(file_path, dry_run)
            )

        return {
            "script_id": result.script_id,
            "indexed": result.indexed,
            "updated": result.updated,
            "scenes_indexed": result.scenes_indexed,
            "characters_indexed": result.characters_indexed,
            "dialogues_indexed": result.dialogues_indexed,
            "actions_indexed": result.actions_indexed,
            "error": result.error,
        }

    def search(
        self,
        query: str,
        mode: SearchMode | str = SearchMode.AUTO,
        limit: int = 10,
        offset: int = 0,
        character: str | None = None,
        location: str | None = None,
        dialogue: str | None = None,
        project: str | None = None,
        include_bible: bool = True,
        only_bible: bool = False,
    ) -> SearchResponse:
        """Search for content in the screenplay database.

        Args:
            query: Search query string
            mode: Search mode - 'strict', 'fuzzy', or 'auto' (default)
            limit: Maximum number of results to return (default: 10)
            offset: Number of results to skip for pagination (default: 0)
            character: Filter results by character name
            location: Filter results by scene location
            dialogue: Search specifically for dialogue content
            project: Filter by project name
            include_bible: Include bible/reference content in search
            only_bible: Search only bible/reference content

        Returns:
            SearchResponse object containing:
                - results: List of SearchResult objects
                - bible_results: List of BibleSearchResult objects
                - total_count: Total number of matching results
                - query: The parsed query used for search

        Raises:
            DatabaseError: If database is not initialized or query fails
            ValueError: If invalid search parameters are provided
        """
        # Ensure database exists
        if not self.db_ops.check_database_exists():
            raise DatabaseError(
                message="Database not initialized",
                hint="Run 'scriptrag init' or initialize with auto_init_db=True",
            )

        # Convert string mode to enum if needed
        if isinstance(mode, str):
            mode = SearchMode(mode.lower())

        # Parse the query
        parsed_query = self.query_parser.parse(
            query=query,
            character=character,
            dialogue=dialogue,
            project=project,
            mode=mode,
            limit=limit,
            offset=offset,
            include_bible=include_bible,
            only_bible=only_bible,
        )

        # Add location to parsed query if provided
        if location:
            parsed_query.locations = [location]

        logger.debug(f"Executing search: {parsed_query.raw_query}")

        # Execute search
        response = self.search_engine.search(parsed_query)

        logger.info(
            f"Search returned {len(response.results)} results "
            f"(total: {response.total_count})"
        )

        return response

    def index_directory(
        self,
        path: str | Path | None = None,
        recursive: bool = True,
        dry_run: bool = False,
        batch_size: int = 10,
    ) -> dict[str, Any]:
        """Index all Fountain files in a directory.

        Args:
            path: Directory path to search for Fountain files (default: current dir)
            recursive: Search subdirectories recursively (default: True)
            dry_run: Preview changes without applying them (default: False)
            batch_size: Number of scripts to process in each batch (default: 10)

        Returns:
            Dictionary with indexing statistics including:
                - total_scripts_indexed: Number of scripts successfully indexed
                - total_scripts_updated: Number of existing scripts updated
                - total_scenes_indexed: Total scenes across all scripts
                - total_characters_indexed: Total unique characters
                - total_dialogues_indexed: Total dialogue entries
                - total_actions_indexed: Total action entries
                - errors: List of any errors encountered

        Raises:
            DatabaseError: If database operations fail
        """
        dir_path = Path(path) if path else Path.cwd()

        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {dir_path}")

        # Use async index method with existing or new event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, we can't use run_until_complete
            # This would need to be handled differently in async context
            result = asyncio.run_coroutine_threadsafe(
                self.index_command.index(
                    path=dir_path,
                    recursive=recursive,
                    dry_run=dry_run,
                    batch_size=batch_size,
                ),
                loop,
            ).result()
        except RuntimeError:
            # No running loop, create one
            result = asyncio.run(
                self.index_command.index(
                    path=dir_path,
                    recursive=recursive,
                    dry_run=dry_run,
                    batch_size=batch_size,
                )
            )

        return {
            "total_scripts_indexed": result.total_scripts_indexed,
            "total_scripts_updated": result.total_scripts_updated,
            "total_scenes_indexed": result.total_scenes_indexed,
            "total_characters_indexed": result.total_characters_indexed,
            "total_dialogues_indexed": result.total_dialogues_indexed,
            "total_actions_indexed": result.total_actions_indexed,
            "errors": result.errors,
        }

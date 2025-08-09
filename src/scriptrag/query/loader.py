"""Query loader for discovering and parsing SQL files."""

import os
from pathlib import Path

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.query.spec import HeaderParser, QuerySpec

logger = get_logger(__name__)


class QueryLoader:
    """Load and manage SQL query specifications."""

    def __init__(self, settings: ScriptRAGSettings | None = None):
        """Initialize query loader.

        Args:
            settings: Configuration settings
        """
        if settings is None:
            from scriptrag.config import get_settings

            settings = get_settings()

        self.settings = settings
        self._cache: dict[str, QuerySpec] = {}
        self._query_dir = self._get_query_directory()

    def _get_query_directory(self) -> Path:
        """Get the query directory path.

        Returns:
            Path to query directory
        """
        # Check environment variable first
        env_dir = os.environ.get("SCRIPTRAG_QUERY_DIR")
        if env_dir:
            path = Path(env_dir)
            if path.exists() and path.is_dir():
                logger.info(f"Using query directory from env: {path}")
                return path
            logger.warning(f"SCRIPTRAG_QUERY_DIR set but path doesn't exist: {env_dir}")

        # Default to storage/database/queries
        default_path = Path(__file__).parent.parent / "storage" / "database" / "queries"
        if not default_path.exists():
            logger.warning(f"Default query directory doesn't exist: {default_path}")
            default_path.mkdir(parents=True, exist_ok=True)

        return default_path

    def discover_queries(self, force_reload: bool = False) -> dict[str, QuerySpec]:
        """Discover and load all SQL queries.

        Args:
            force_reload: Force reload from disk

        Returns:
            Dictionary of query name to QuerySpec
        """
        if self._cache and not force_reload:
            return self._cache

        queries: dict[str, QuerySpec] = {}

        if not self._query_dir.exists():
            logger.warning(f"Query directory doesn't exist: {self._query_dir}")
            return queries

        # Find all .sql files
        sql_files = list(self._query_dir.glob("*.sql"))
        logger.info(f"Found {len(sql_files)} SQL files in {self._query_dir}")

        for sql_file in sql_files:
            try:
                spec = self.load_query(sql_file)
                if spec.name in queries:
                    logger.warning(
                        f"Duplicate query name '{spec.name}' from {sql_file}. "
                        f"Skipping (loaded from {queries[spec.name].source_path})"
                    )
                else:
                    queries[spec.name] = spec
                    logger.debug(f"Loaded query '{spec.name}' from {sql_file}")
            except Exception as e:
                logger.error(f"Failed to load query from {sql_file}: {e}")

        # Update cache
        self._cache = queries
        logger.info(f"Loaded {len(queries)} queries")

        return queries

    def load_query(self, path: Path) -> QuerySpec:
        """Load a single query from file.

        Args:
            path: Path to SQL file

        Returns:
            Parsed query specification

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file cannot be parsed
        """
        if not path.exists():
            raise FileNotFoundError(f"Query file not found: {path}")

        if not path.suffix == ".sql":
            raise ValueError(f"Not an SQL file: {path}")

        try:
            content = path.read_text(encoding="utf-8")
            spec = HeaderParser.parse(content, source_path=path)

            # Warn if using filename as fallback name
            if spec.name == path.stem and not content.startswith("-- name:"):
                logger.warning(
                    f"Query '{spec.name}' has no '-- name:' header, "
                    "using filename as name"
                )

            return spec
        except Exception as e:
            raise ValueError(f"Failed to parse query file {path}: {e}") from e

    def get_query(self, name: str) -> QuerySpec | None:
        """Get a query by name.

        Args:
            name: Query name

        Returns:
            Query spec or None if not found
        """
        # Ensure queries are loaded
        if not self._cache:
            self.discover_queries()

        return self._cache.get(name)

    def list_queries(self) -> list[QuerySpec]:
        """List all available queries.

        Returns:
            List of query specifications
        """
        # Ensure queries are loaded
        if not self._cache:
            self.discover_queries()

        return list(self._cache.values())

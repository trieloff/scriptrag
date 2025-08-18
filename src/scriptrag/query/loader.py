"""Query loader for discovering and parsing SQL files."""

from pathlib import Path

from scriptrag.common import FileSourceResolver
from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.exceptions import QueryError, ValidationError
from scriptrag.query.spec import HeaderParser, QuerySpec

logger = get_logger(__name__)


class QueryLoader:
    """Load and manage SQL query specifications."""

    def __init__(self, settings: ScriptRAGSettings | None = None) -> None:
        """Initialize query loader.

        Args:
            settings: Configuration settings
        """
        if settings is None:
            from scriptrag.config import get_settings

            settings = get_settings()

        self.settings = settings
        self._cache: dict[str, QuerySpec] = {}

        # Initialize file source resolver for queries
        self._resolver = FileSourceResolver(
            file_type="queries",
            env_var="SCRIPTRAG_QUERY_DIR",
            default_subdir="storage/database/queries",
            file_extension="sql",
        )

        # For backward compatibility
        self._query_dir = self._get_query_directory()

    def _get_query_directory(self) -> Path:
        """Get the query directory path.

        Returns:
            Path to query directory
        """
        import os

        # Check if environment variable is set - use only that directory if it exists
        env_dir = os.environ.get("SCRIPTRAG_QUERY_DIR")
        if env_dir:
            env_path = Path(env_dir)
            if env_path.exists() and env_path.is_dir():
                logger.info(f"Using query directory from env: {env_path}")
                return env_path
            logger.warning(f"SCRIPTRAG_QUERY_DIR set but path doesn't exist: {env_dir}")
            # Fall back to resolver/default behavior

        # Use first directory from resolver
        dirs = self._resolver.get_search_directories()
        if dirs:
            return dirs[0]

        # Fallback to creating default directory
        default_path = Path(__file__).parent.parent / "storage" / "database" / "queries"
        if not default_path.exists():
            logger.warning(f"Default query directory doesn't exist: {default_path}")
            default_path.mkdir(parents=True, exist_ok=True)
        return default_path

    def _is_query_dir_explicitly_set(self) -> bool:
        """Check if _query_dir was explicitly overridden (e.g., by tests).

        Returns:
            True if _query_dir was set to something other than the default resolver path
        """
        if not hasattr(self, "_query_dir"):
            return False

        # Get what the resolver would return as the default
        default_dirs = self._resolver.get_search_directories()
        default_dir = default_dirs[0] if default_dirs else None

        # If _query_dir is different from the resolver default, it was explicitly set
        return default_dir is None or self._query_dir != default_dir

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

        # Check if environment variable is set - if so, only use that directory
        import os

        env_dir = os.environ.get("SCRIPTRAG_QUERY_DIR")
        if env_dir:
            query_dir = Path(env_dir)
            if query_dir.exists() and query_dir.is_dir():
                # Only use the environment-specified directory
                sql_files = list(query_dir.glob("*.sql"))
                logger.info(f"Found {len(sql_files)} SQL files in {query_dir}")
            else:
                logger.warning(
                    f"SCRIPTRAG_QUERY_DIR set but path doesn't exist: {env_dir}"
                )
                sql_files = []
        elif self._is_query_dir_explicitly_set():
            # Query directory was explicitly set (likely by tests)
            # Use only that directory
            if self._query_dir.exists() and self._query_dir.is_dir():
                sql_files = list(self._query_dir.glob("*.sql"))
                logger.info(f"Found {len(sql_files)} SQL files in {self._query_dir}")
            else:
                # Query directory doesn't exist, return empty list
                logger.warning(f"Query directory doesn't exist: {self._query_dir}")
                sql_files = []
        else:
            # Discover all SQL files using the resolver from multiple sources
            sql_files = self._resolver.discover_files(pattern="*.sql")
            logger.info(f"Found {len(sql_files)} SQL files across search directories")

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
            raise ValidationError(
                message=f"Not an SQL file: {path}",
                hint="Query files must have a .sql extension",
                details={
                    "file": str(path),
                    "extension": path.suffix,
                    "expected": ".sql",
                },
            )

        try:
            content = path.read_text(encoding="utf-8")
            spec = HeaderParser.parse(content, source_path=path)

            # Warn if using filename as fallback name
            if spec.name == path.stem and not content.startswith("-- name:"):
                logger.warning(
                    f"Query '{spec.name}' has no '-- name:' header, "
                    "using filename as name"
                )

            # Validate SQL syntax (basic check)
            self._validate_sql_syntax(spec.sql)

            return spec
        except ValidationError:
            raise
        except Exception as e:
            raise QueryError(
                message=f"Failed to parse query file: {path.name}",
                hint="Check the SQL syntax and header format in the file",
                details={
                    "file": str(path),
                    "error": str(e),
                    "format": "Valid SQL with header comments required",
                },
            ) from e

    def _validate_sql_syntax(self, sql: str) -> None:
        """Validate SQL syntax without execution.

        Args:
            sql: SQL query string

        Raises:
            ValueError: If SQL syntax is invalid
        """
        import sqlite3

        # Strip trailing whitespace and comments for validation
        sql_stripped = sql.strip()
        if not sql_stripped:
            raise ValidationError(
                message="Empty SQL statement",
                hint="The query file contains no executable SQL",
                details={
                    "sql_length": len(sql),
                    "stripped_length": len(sql_stripped),
                },
            )

        # Use sqlite3.complete_statement for basic validation
        # Add semicolon if not present (sqlite3.complete_statement needs it)
        if not sql_stripped.endswith(";"):
            sql_test = sql_stripped + ";"
        else:
            sql_test = sql_stripped

        if not sqlite3.complete_statement(sql_test):
            raise ValueError("Incomplete SQL statement")

        # Additional validation for obvious syntax errors
        # Check for statements that end with FROM, WHERE, etc. without table/condition
        sql_upper = sql_stripped.upper().rstrip(";")
        if any(
            sql_upper.endswith(keyword)
            for keyword in [" FROM", " WHERE", " JOIN", " ON", " SET"]
        ):
            raise ValueError("Incomplete SQL statement")

        # Additional validation: check for SELECT (read-only queries)
        if not any(
            sql_upper.startswith(keyword)
            for keyword in ["SELECT", "WITH", "PRAGMA", "EXPLAIN"]
        ):
            raise ValueError(
                "Only read-only queries (SELECT, WITH, PRAGMA, EXPLAIN) are allowed"
            )

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

    def reload_queries(self) -> dict[str, QuerySpec]:
        """Reload all queries from disk, clearing cache.

        Returns:
            Dictionary of query name to QuerySpec
        """
        return self.discover_queries(force_reload=True)

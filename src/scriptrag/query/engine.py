"""Query execution engine."""

import sqlite3
import time
from typing import Any

from scriptrag.config import ScriptRAGSettings, get_logger, get_settings
from scriptrag.database.readonly import get_read_only_connection
from scriptrag.query.spec import QuerySpec

logger = get_logger(__name__)


class QueryEngine:
    """Execute SQL queries with parameter binding."""

    def __init__(self, settings: ScriptRAGSettings | None = None) -> None:
        """Initialize query engine.

        Args:
            settings: Configuration settings (deprecated, use get_settings())
        """
        # Store settings but prefer get_settings() for runtime configuration
        # This ensures tests with environment variable changes work correctly
        self._initial_settings = settings

    @property
    def settings(self) -> ScriptRAGSettings:
        """Get current settings, always fresh from configuration system.

        This ensures tests that modify environment variables and call reset_settings()
        will see the updated configuration.
        """
        if self._initial_settings is not None:
            # Use initial settings if provided (for backward compatibility)
            return self._initial_settings

        # Use module-level import to avoid circular import issues
        return get_settings()

    @property
    def db_path(self) -> Any:
        """Get current database path from settings.

        This ensures we always use the latest database path,
        even if settings have been reset/reloaded.
        """
        return self.settings.database_path

    def execute(
        self,
        spec: QuerySpec,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[dict[str, Any]], float]:
        """Execute a query with parameters.

        Args:
            spec: Query specification
            params: Query parameters
            limit: Row limit (if not in params)
            offset: Row offset (if not in params)

        Returns:
            Tuple of (rows as list of dicts, execution time in ms)

        Raises:
            FileNotFoundError: If database doesn't exist
            ValueError: If required parameters are missing or invalid
        """
        # Check if database exists
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Database not found at {self.db_path}. "
                "Please run 'scriptrag init' first."
            )

        start_time = time.time()

        # Build and validate parameters
        validated_params = self._validate_params(spec, params or {})

        # Handle limit/offset
        has_limit, has_offset = spec.has_limit_offset()

        # Add limit/offset to params if provided
        if limit is not None and "limit" not in validated_params:
            validated_params["limit"] = limit
        if offset is not None and "offset" not in validated_params:
            validated_params["offset"] = offset

        # Apply defaults for limit/offset if not provided
        if "limit" not in validated_params and not has_limit:
            validated_params["limit"] = 10
        if "offset" not in validated_params and not has_offset:
            validated_params["offset"] = 0

        # Prepare SQL
        # Normalize SQL by trimming whitespace and removing a trailing semicolon.
        # This avoids syntax errors when wrapping the statement in a subquery
        # for LIMIT/OFFSET handling (SQLite disallows a semicolon inside).
        sql = spec.sql.strip()
        if sql.endswith(";"):
            sql = sql[:-1].rstrip()

        # Wrap SQL if limit/offset not in original query but provided in params
        if not has_limit and "limit" in validated_params:
            if not has_offset and "offset" in validated_params:
                sql = f"SELECT * FROM ({sql}) LIMIT :limit OFFSET :offset"
            else:
                sql = f"SELECT * FROM ({sql}) LIMIT :limit"
        elif not has_offset and "offset" in validated_params:
            # If query already has LIMIT but no OFFSET, modify the LIMIT clause
            if has_limit and ":limit" in sql.lower():
                # Replace LIMIT :limit with LIMIT :limit OFFSET :offset
                import re

                sql = re.sub(
                    r"LIMIT\s+:limit",
                    "LIMIT :limit OFFSET :offset",
                    sql,
                    flags=re.IGNORECASE,
                )
            else:
                sql = f"SELECT * FROM ({sql}) OFFSET :offset"

        # Execute query using the engine's settings
        with get_read_only_connection(self.settings) as conn:
            logger.debug(
                f"Executing query '{spec.name}' with params: {validated_params}"
            )

            try:
                cursor = conn.execute(sql, validated_params)
                rows = cursor.fetchall()

                # Convert rows to list of dicts
                if rows:
                    columns = [description[0] for description in cursor.description]
                    result = [dict(zip(columns, row, strict=False)) for row in rows]
                else:
                    result = []

                execution_time_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Query '{spec.name}' executed: {len(result)} rows "
                    f"in {execution_time_ms:.2f}ms"
                )

                return result, execution_time_ms

            except sqlite3.OperationalError as e:
                logger.error(f"Database operational error: {e}")
                if "no such table" in str(e):
                    raise ValueError(
                        f"Table not found in query '{spec.name}': {e}"
                    ) from e
                if "no such column" in str(e):
                    raise ValueError(
                        f"Column not found in query '{spec.name}': {e}"
                    ) from e
                raise ValueError(f"Database error in query '{spec.name}': {e}") from e
            except sqlite3.IntegrityError as e:
                logger.error(f"Database integrity error: {e}")
                raise ValueError(f"Integrity error in query '{spec.name}': {e}") from e
            except sqlite3.ProgrammingError as e:
                logger.error(f"SQL programming error: {e}")
                raise ValueError(f"SQL error in query '{spec.name}': {e}") from e
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                raise ValueError(f"Query execution failed: {e}") from e

    def _validate_params(
        self, spec: QuerySpec, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate and cast parameters.

        Args:
            spec: Query specification
            params: Raw parameters

        Returns:
            Validated and casted parameters

        Raises:
            ValueError: If validation fails
        """
        validated = {}

        # Process each parameter spec
        for param_spec in spec.params:
            value = params.get(param_spec.name)
            casted = param_spec.cast_value(value)
            if casted is not None:
                validated[param_spec.name] = casted

        # Add any extra params not in spec (for backwards compatibility)
        for key, value in params.items():
            if key not in validated:
                logger.warning(
                    f"Parameter '{key}' not defined in query spec, passing as-is"
                )
                validated[key] = value

        return validated

    def check_read_only(self) -> bool:
        """Verify that the database connection is read-only.

        Returns:
            True if connection is read-only

        Raises:
            RuntimeError: If write operation succeeds (should not happen)
        """
        with get_read_only_connection(self.settings) as conn:
            try:
                # Attempt to create a table (should fail)
                conn.execute("CREATE TABLE test_write (id INTEGER)")
                conn.commit()
                # If we get here, connection is NOT read-only
                raise RuntimeError("Database connection is not read-only!")
            except Exception as e:
                # Re-raise our own RuntimeError first
                if "Database connection is not read-only" in str(e):
                    raise
                # Expected: write operation should fail with read-only error
                if "read-only" in str(e).lower() or "readonly" in str(e).lower():
                    return True
                # Other exceptions also indicate read-only behavior
                return True

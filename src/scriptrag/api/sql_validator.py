"""SQL content validator for secure database initialization."""

import re
from pathlib import Path

from scriptrag.config import get_logger

logger = get_logger(__name__)

# Maximum file size for SQL schema files (5MB)
MAX_SQL_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes

# Allowed DDL statement patterns
ALLOWED_DDL_PATTERNS = [
    r"^\s*CREATE\s+(TABLE|INDEX|TRIGGER|VIEW)\s+",
    r"^\s*DROP\s+(TABLE|INDEX|TRIGGER|VIEW)\s+",
    r"^\s*ALTER\s+TABLE\s+",
    r"^\s*PRAGMA\s+",  # SQLite specific settings
    r"^\s*--",  # Comments
    r"^\s*$",  # Empty lines
]

# Disallowed patterns for security
DISALLOWED_PATTERNS = [
    r"^\s*DELETE\s+FROM\b",  # Must be at start of statement
    r"^\s*UPDATE\s+\w+\s+SET\b",  # Must be at start of statement
    r"\bDROP\s+DATABASE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bATTACH\s+DATABASE\b",
    r"\bLOAD\s+EXTENSION\b",
]

# Special case for INSERT - only allow schema_version table
INSERT_SCHEMA_VERSION_PATTERN = r"^\s*INSERT\s+INTO\s+schema_version\s*\("


class SQLValidationError(Exception):
    """Raised when SQL content validation fails."""

    pass


class SQLValidator:
    """Validates SQL content for security and safety."""

    def __init__(self) -> None:
        """Initialize SQL validator."""
        self.allowed_patterns = [
            re.compile(p, re.IGNORECASE) for p in ALLOWED_DDL_PATTERNS
        ]
        self.disallowed_patterns = [
            re.compile(p, re.IGNORECASE) for p in DISALLOWED_PATTERNS
        ]
        self.insert_pattern = re.compile(INSERT_SCHEMA_VERSION_PATTERN, re.IGNORECASE)

    def validate_file_size(self, file_path: Path) -> None:
        """Validate SQL file size is within limits.

        Args:
            file_path: Path to SQL file.

        Raises:
            SQLValidationError: If file size exceeds limit.
        """
        file_size = file_path.stat().st_size
        if file_size > MAX_SQL_FILE_SIZE:
            raise SQLValidationError(
                f"SQL file size ({file_size} bytes) exceeds maximum allowed size "
                f"({MAX_SQL_FILE_SIZE} bytes)"
            )
        logger.debug("SQL file size validated", path=str(file_path), size=file_size)

    def validate_sql_content(self, sql_content: str, filename: str = "unknown") -> None:
        """Validate SQL content contains only safe DDL statements.

        Args:
            sql_content: SQL content to validate.
            filename: Name of the SQL file for error reporting.

        Raises:
            SQLValidationError: If SQL content contains unsafe statements.
        """
        # Split by semicolons but preserve them for statement parsing
        statements = self._split_sql_statements(sql_content)

        for i, statement in enumerate(statements, 1):
            statement = statement.strip()
            if not statement:
                continue

            # Check if statement matches allowed patterns first
            is_allowed = False
            for pattern in self.allowed_patterns:
                if pattern.match(statement):
                    is_allowed = True
                    break

            # Special case for INSERT INTO schema_version
            if not is_allowed and self.insert_pattern.match(statement):
                is_allowed = True

            # If allowed, skip further checks
            if is_allowed:
                continue

            # Check for disallowed patterns only if not already allowed
            for pattern in self.disallowed_patterns:
                if pattern.search(statement):
                    raise SQLValidationError(
                        f"Disallowed SQL pattern found in {filename} at statement {i}: "
                        f"'{statement[:50]}...'"
                    )

            # If we reach here, statement is not allowed
            # Extract first 50 chars of statement for error message
            stmt_preview = statement[:50].replace("\n", " ")
            if len(statement) > 50:
                stmt_preview += "..."

            raise SQLValidationError(
                f"Statement {i} in {filename} is not a recognized DDL statement: "
                f"'{stmt_preview}'. Only CREATE TABLE/INDEX/TRIGGER/VIEW, "
                f"ALTER TABLE, DROP TABLE/INDEX/TRIGGER/VIEW, PRAGMA, "
                f"and INSERT INTO schema_version are allowed."
            )

        logger.debug(
            "SQL content validated",
            filename=filename,
            statements=len(statements),
        )

    def _split_sql_statements(self, sql_content: str) -> list[str]:
        """Split SQL content into individual statements.

        Handles multi-line statements and preserves statement structure.
        Special handling for CREATE TRIGGER which contains BEGIN/END blocks.

        Args:
            sql_content: SQL content to split.

        Returns:
            List of SQL statements.
        """
        # Simple split by semicolon, but handle multi-line statements
        statements = []
        current_statement = []
        in_string = False
        string_char = None
        in_trigger = False
        trigger_depth = 0

        for line in sql_content.splitlines():
            # Check if we're starting a CREATE TRIGGER statement
            if re.match(r"^\s*CREATE\s+TRIGGER\b", line, re.IGNORECASE):
                in_trigger = True
                trigger_depth = 0

            # Track BEGIN/END blocks in triggers
            if in_trigger:
                if re.match(r"^\s*BEGIN\b", line, re.IGNORECASE):
                    trigger_depth += 1
                elif re.match(r"^\s*END\s*;", line, re.IGNORECASE):
                    trigger_depth -= 1
                    if trigger_depth == 0:
                        in_trigger = False

            # Track if we're inside a string literal
            i = 0
            while i < len(line):
                char = line[i]
                if not in_string and char in ("'", '"'):
                    in_string = True
                    string_char = char
                elif in_string and char == string_char:
                    # Check if it's escaped
                    if i + 1 < len(line) and line[i + 1] == string_char:
                        i += 1  # Skip escaped quote
                    else:
                        in_string = False
                        string_char = None
                i += 1

            current_statement.append(line)

            # If line ends with semicolon and we're not in a string or trigger,
            # it's end of statement
            if line.rstrip().endswith(";") and not in_string and not in_trigger:
                statement = "\n".join(current_statement).strip()
                if statement and statement != ";":  # Skip empty statements
                    statements.append("\n".join(current_statement))
                current_statement = []

        # Add any remaining statement
        if current_statement:
            statement = "\n".join(current_statement).strip()
            if statement and statement != ";":  # Skip empty statements
                statements.append("\n".join(current_statement))

        return statements

    def validate_database_path(self, db_path: Path) -> None:
        """Validate database path for security issues.

        Args:
            db_path: Database file path to validate.

        Raises:
            SQLValidationError: If path contains security issues.
        """
        # Resolve to absolute path to check for path traversal
        try:
            resolved_path = db_path.resolve()
        except Exception as e:
            raise SQLValidationError(f"Invalid database path: {e}") from e

        # Check for path traversal attempts
        if ".." in str(db_path):
            raise SQLValidationError(
                "Database path contains path traversal attempt (..)"
            )

        # Ensure file extension is .db or .sqlite
        valid_extensions = {".db", ".sqlite", ".sqlite3"}
        if resolved_path.suffix.lower() not in valid_extensions:
            raise SQLValidationError(
                f"Database file must have one of these extensions: {valid_extensions}"
            )

        logger.debug("Database path validated", path=str(resolved_path))

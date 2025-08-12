"""Common test utilities for ScriptRAG tests."""

import contextlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from scriptrag.cli.main import app


def strip_ansi_codes(text: str) -> str:
    """Strip ANSI escape sequences and spinner characters from text.

    This is useful for testing CLI output that contains color codes,
    formatting sequences, and spinner characters that can vary between
    environments and cause Windows compatibility issues.

    Args:
        text: Text potentially containing ANSI escape codes and spinners

    Returns:
        Text with all ANSI escape sequences and spinner characters removed
    """
    # Remove ANSI escape sequences
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    text = ansi_escape.sub("", text)

    # Remove Unicode spinner characters (Braille patterns)
    spinner_chars = re.compile(r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]")
    return spinner_chars.sub("", text)


class CLITestHelper:
    """Helper class for testing CLI commands."""

    def __init__(self, tmp_path: Path):
        """Initialize the CLI test helper.

        Args:
            tmp_path: Temporary directory path from pytest fixture
        """
        self.tmp_path = tmp_path
        self.runner = CliRunner()
        self.db_path = tmp_path / "test.db"

    def init_database(self) -> tuple[int, str]:
        """Initialize a test database.

        Returns:
            Tuple of (exit_code, cleaned_output)
        """
        result = self.runner.invoke(app, ["init", "--db-path", str(self.db_path)])
        return result.exit_code, strip_ansi_codes(result.stdout)

    def analyze_scripts(
        self, script_dir: Path, analyzer: str | None = None, force: bool = False
    ) -> tuple[int, str]:
        """Run the analyze command on a directory.

        Args:
            script_dir: Directory containing fountain scripts
            analyzer: Optional specific analyzer to run
            force: Whether to force re-analysis

        Returns:
            Tuple of (exit_code, cleaned_output)
        """
        args = ["analyze", str(script_dir)]
        if analyzer:
            args.extend(["--analyzer", analyzer])
        if force:
            args.append("--force")

        result = self.runner.invoke(app, args)
        return result.exit_code, strip_ansi_codes(result.stdout)

    def index_scripts(self, script_dir: Path) -> tuple[int, str]:
        """Run the index command on a directory.

        Args:
            script_dir: Directory containing fountain scripts

        Returns:
            Tuple of (exit_code, cleaned_output)
        """
        result = self.runner.invoke(app, ["index", str(script_dir)])
        return result.exit_code, strip_ansi_codes(result.stdout)

    def search(self, query: str, **kwargs) -> tuple[int, str, dict[str, Any] | None]:
        """Run a search query.

        Args:
            query: Search query string
            **kwargs: Additional search options (limit, offset, etc.)

        Returns:
            Tuple of (exit_code, cleaned_output, parsed_json_if_available)
        """
        args = ["search", query]
        if kwargs.get("json"):
            args.append("--json")
        if "limit" in kwargs:
            args.extend(["--limit", str(kwargs["limit"])])
        if "offset" in kwargs:
            args.extend(["--offset", str(kwargs["offset"])])

        result = self.runner.invoke(app, args)
        output = strip_ansi_codes(result.stdout)

        json_data = None
        if kwargs.get("json") and result.exit_code == 0:
            with contextlib.suppress(json.JSONDecodeError):
                json_data = json.loads(output)

        return result.exit_code, output, json_data

    def query_database(self, conn: sqlite3.Connection, query: str) -> list[dict]:
        """Execute a database query and return results as dicts.

        Args:
            conn: SQLite database connection
            query: SQL query to execute

        Returns:
            List of row dictionaries
        """
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]


def create_test_screenplay(
    tmp_path: Path, filename: str = "test.fountain", content: str | None = None
) -> Path:
    """Create a test screenplay file.

    Args:
        tmp_path: Temporary directory path
        filename: Name of the fountain file
        content: Optional content (uses default if not provided)

    Returns:
        Path to the created screenplay file
    """
    if content is None:
        content = """Title: Test Script
Author: Test Suite
Draft date: 2024-01-01

INT. TEST LOCATION - DAY

This is a test scene with some action.

CHARACTER
Test dialogue here.

FADE OUT."""

    script_path = tmp_path / filename
    script_path.write_text(content)
    return script_path


def verify_database_structure(db_path: Path) -> dict[str, list[str]]:
    """Verify the database has the expected structure.

    Args:
        db_path: Path to the SQLite database

    Returns:
        Dictionary mapping table names to column names
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Get all tables
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    tables = [row[0] for row in cursor.fetchall()]

    structure = {}
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        structure[table] = columns

    conn.close()
    return structure


def assert_scene_in_database(
    db_path: Path, scene_heading: str, script_title: str | None = None
) -> dict:
    """Assert that a scene exists in the database.

    Args:
        db_path: Path to the SQLite database
        scene_heading: The scene heading to look for
        script_title: Optional script title to filter by

    Returns:
        The scene record as a dictionary

    Raises:
        AssertionError: If the scene is not found
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT s.* FROM scenes s"
    params = []

    if script_title:
        query += (
            " JOIN scripts sc ON s.script_id = sc.id "
            "WHERE sc.title = ? AND s.heading = ?"
        )
        params = [script_title, scene_heading]
    else:
        query += " WHERE s.heading = ?"
        params = [scene_heading]

    cursor.execute(query, params)
    scene = cursor.fetchone()
    conn.close()

    assert scene is not None, f"Scene '{scene_heading}' not found in database"
    return dict(scene)


def count_database_records(db_path: Path, table: str) -> int:
    """Count the number of records in a database table.

    Args:
        db_path: Path to the SQLite database
        table: Name of the table

    Returns:
        Number of records in the table
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    conn.close()
    return count

"""Schema initialization helpers for SQLite VSS tables."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def initialize_vss_tables(conn: sqlite3.Connection) -> None:
    """Initialize VSS-related virtual tables if migration SQL exists.

    Executes statements found in ``database/sql/vss_migration.sql`` adjacent to
    this module, skipping comments and any ``.load`` directives.
    """
    migration_path = Path(__file__).parent / "database" / "sql" / "vss_migration.sql"
    if not migration_path.exists():
        return

    migration_sql = migration_path.read_text()
    for statement in migration_sql.split(";"):
        stmt = statement.strip()
        if not stmt or stmt.startswith("--") or ".load" in stmt:
            continue
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                continue
            raise
    conn.commit()

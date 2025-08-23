"""Schema initialization helpers for SQLite VSS tables."""

from __future__ import annotations

import sqlite3


def initialize_vss_tables(conn: sqlite3.Connection) -> None:
    """Initialize VSS-related virtual tables.

    This is now a no-op as VSS tables are created directly in the main
    database initialization via vss_schema.sql. This function is kept
    for backward compatibility.
    """
    # Tables are now created directly in database initialization
    # via src/scriptrag/storage/database/sql/vss_schema.sql
    pass

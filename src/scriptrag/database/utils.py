"""Database management utilities for ScriptRAG.

This module provides utility functions for database maintenance, backup,
statistics, and other administrative operations.
"""

import json
import sqlite3
import tempfile
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scriptrag.config import get_logger, get_settings

from .connection import DatabaseConnection

logger = get_logger(__name__)


def get_connection(db_path: Path | None = None) -> DatabaseConnection:
    """Get a database connection.

    Args:
        db_path: Optional database path (uses settings if not provided)

    Returns:
        Database connection instance
    """
    if db_path is None:
        settings = get_settings()
        db_path = settings.get_database_path()

    return DatabaseConnection(db_path)


class DatabaseStats:
    """Database statistics and information."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize database stats.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)

    def get_table_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all tables.

        Returns:
            Dictionary mapping table names to their statistics
        """
        stats = {}

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get all table names
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            tables = [row["name"] for row in cursor.fetchall()]

            for table in tables:
                table_stats = self._get_single_table_stats(conn, table)
                stats[table] = table_stats

        return stats

    def _get_single_table_stats(
        self, conn: sqlite3.Connection, table: str
    ) -> dict[str, Any]:
        """Get statistics for a single table.

        Args:
            conn: Database connection
            table: Table name

        Returns:
            Dictionary of table statistics
        """
        stats = {}

        # Row count
        cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
        stats["row_count"] = cursor.fetchone()["count"]

        # Table size (approximate)
        try:
            cursor = conn.execute(
                f"SELECT SUM(pgsize) as size FROM dbstat WHERE name='{table}'"
            )
            result = cursor.fetchone()
            stats["size_bytes"] = result["size"] if result["size"] else 0
        except sqlite3.OperationalError as e:
            # dbstat virtual table not available (common on macOS/Homebrew SQLite)
            if "no such table: dbstat" in str(e):
                logger.debug(f"dbstat virtual table not available: {e}")
                stats["size_bytes"] = None  # Unable to determine size
            else:
                raise

        # Column information
        cursor = conn.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        stats["column_count"] = len(columns)
        stats["columns"] = [
            {
                "name": col["name"],
                "type": col["type"],
                "nullable": not col["notnull"],
                "primary_key": bool(col["pk"]),
            }
            for col in columns
        ]

        # Index information
        cursor = conn.execute(f"PRAGMA index_list({table})")
        indexes = cursor.fetchall()
        stats["index_count"] = len(indexes)
        stats["indexes"] = [
            {"name": idx["name"], "unique": bool(idx["unique"])} for idx in indexes
        ]

        return stats

    def get_database_size(self) -> dict[str, Any]:
        """Get overall database size information.

        Returns:
            Dictionary with size information
        """
        size_info = {}

        if self.db_path.exists():
            # File size
            size_info["file_size_bytes"] = self.db_path.stat().st_size

            with sqlite3.connect(self.db_path) as conn:
                # Page count and size
                cursor = conn.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor = conn.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]

                size_info["page_count"] = page_count
                size_info["page_size"] = page_size
                size_info["total_pages_bytes"] = page_count * page_size

                # Free pages
                cursor = conn.execute("PRAGMA freelist_count")
                free_pages = cursor.fetchone()[0]
                size_info["free_pages"] = free_pages
                size_info["free_bytes"] = free_pages * page_size

                # Used space
                size_info["used_bytes"] = (
                    size_info["total_pages_bytes"] - size_info["free_bytes"]
                )
                size_info["utilization_percent"] = int(
                    (size_info["used_bytes"] / size_info["total_pages_bytes"]) * 100
                    if size_info["total_pages_bytes"] > 0
                    else 0
                )

        else:
            size_info = {
                "file_size_bytes": 0,
                "page_count": 0,
                "page_size": 0,
                "total_pages_bytes": 0,
                "free_pages": 0,
                "free_bytes": 0,
                "used_bytes": 0,
                "utilization_percent": 0,
            }

        return size_info

    def get_query_performance_stats(self) -> dict[str, Any]:
        """Get query performance statistics.

        Returns:
            Dictionary with performance metrics
        """
        stats: dict[str, Any] = {}

        with sqlite3.connect(self.db_path) as conn:
            # SQLite compile options
            cursor = conn.execute("PRAGMA compile_options")
            compile_options = [row[0] for row in cursor.fetchall()]
            stats["compile_options"] = compile_options

            # Cache statistics
            cursor = conn.execute("PRAGMA cache_size")
            stats["cache_size_pages"] = cursor.fetchone()[0]

            cursor = conn.execute("PRAGMA cache_spill")
            cache_spill_result = cursor.fetchone()[0]
            stats["cache_spill"] = bool(cache_spill_result)

            # Journal mode
            cursor = conn.execute("PRAGMA journal_mode")
            stats["journal_mode"] = cursor.fetchone()[0]

            # Synchronous mode
            cursor = conn.execute("PRAGMA synchronous")
            stats["synchronous"] = cursor.fetchone()[0]

            # Auto vacuum
            cursor = conn.execute("PRAGMA auto_vacuum")
            stats["auto_vacuum"] = cursor.fetchone()[0]

        return stats


class DatabaseBackup:
    """Database backup and restore utilities."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize database backup utility.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)

    def create_backup(self, backup_path: str | Path, compress: bool = True) -> bool:
        """Create a backup of the database.

        Args:
            backup_path: Path for backup file
            compress: Whether to compress the backup

        Returns:
            True if successful
        """
        backup_path = Path(backup_path)

        try:
            if not self.db_path.exists():
                logger.error(f"Source database {self.db_path} does not exist")
                return False

            # Ensure backup directory exists
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            if compress:
                return self._create_compressed_backup(backup_path)
            return self._create_simple_backup(backup_path)

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False

    def _create_simple_backup(self, backup_path: Path) -> bool:
        """Create a simple file copy backup.

        Args:
            backup_path: Path for backup file

        Returns:
            True if successful
        """
        # Use SQLite's backup API for consistency
        source = None
        backup = None
        try:
            source = sqlite3.connect(self.db_path)
            backup = sqlite3.connect(backup_path)
            source.backup(backup)
        finally:
            # Explicitly close connections to release file handles on Windows
            if backup:
                backup.close()
            if source:
                source.close()

        logger.info(f"Created backup at {backup_path}")
        return True

    def _create_compressed_backup(self, backup_path: Path) -> bool:
        """Create a compressed backup.

        Args:
            backup_path: Path for backup file (will add .zip extension)

        Returns:
            True if successful
        """
        # Ensure .zip extension
        if backup_path.suffix != ".zip":
            backup_path = backup_path.with_suffix(backup_path.suffix + ".zip")

        # Use a temporary directory approach that works on Windows
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / f"{self.db_path.stem}_backup.db"

            # Create temporary backup
            if not self._create_simple_backup(temp_path):
                return False

            # Compress the backup
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(temp_path, f"{self.db_path.stem}.db")

                # Add metadata
                metadata = {
                    "source_path": str(self.db_path),
                    "backup_time": datetime.now(UTC).isoformat(),
                    "source_size_bytes": self.db_path.stat().st_size,
                }
                zip_file.writestr(
                    "backup_metadata.json", json.dumps(metadata, indent=2)
                )

        logger.info(f"Created compressed backup at {backup_path}")
        return True

    def restore_backup(self, backup_path: str | Path, force: bool = False) -> bool:
        """Restore database from backup.

        Args:
            backup_path: Path to backup file
            force: Whether to overwrite existing database

        Returns:
            True if successful
        """
        backup_path = Path(backup_path)

        try:
            if not backup_path.exists():
                logger.error(f"Backup file {backup_path} does not exist")
                return False

            if self.db_path.exists() and not force:
                logger.error(
                    f"Database {self.db_path} exists. Use force=True to overwrite"
                )
                return False

            if backup_path.suffix == ".zip":
                return self._restore_compressed_backup(backup_path)
            return self._restore_simple_backup(backup_path)

        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False

    def _restore_simple_backup(self, backup_path: Path) -> bool:
        """Restore from simple backup.

        Args:
            backup_path: Path to backup file

        Returns:
            True if successful
        """
        # Ensure target directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Use SQLite's backup API
        source = None
        target = None
        try:
            source = sqlite3.connect(backup_path)
            target = sqlite3.connect(self.db_path)
            source.backup(target)
        finally:
            # Explicitly close connections to release file handles on Windows
            if target:
                target.close()
            if source:
                source.close()

        logger.info(f"Restored database from {backup_path}")
        return True

    def _restore_compressed_backup(self, backup_path: Path) -> bool:
        """Restore from compressed backup.

        Args:
            backup_path: Path to compressed backup file

        Returns:
            True if successful
        """
        with zipfile.ZipFile(backup_path, "r") as zip_file:
            # Extract database file to temporary location
            db_files = [f for f in zip_file.namelist() if f.endswith(".db")]
            if not db_files:
                logger.error("No database file found in backup")
                return False

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / db_files[0]
                zip_file.extract(db_files[0], temp_dir)

                return self._restore_simple_backup(temp_path)

    def list_backups(self, backup_dir: str | Path) -> list[dict[str, Any]]:
        """List available backups in a directory.

        Args:
            backup_dir: Directory containing backups

        Returns:
            List of backup information
        """
        backup_dir = Path(backup_dir)
        backups: list[dict[str, Any]] = []

        if not backup_dir.exists():
            return backups

        # Find backup files
        backup_files = list(backup_dir.glob("*.db")) + list(backup_dir.glob("*.zip"))

        for backup_file in backup_files:
            backup_info = {
                "path": str(backup_file),
                "name": backup_file.name,
                "size_bytes": backup_file.stat().st_size,
                "created_at": datetime.fromtimestamp(
                    backup_file.stat().st_mtime
                ).isoformat(),
                "compressed": backup_file.suffix == ".zip",
            }

            # Try to get metadata from compressed backups
            if backup_file.suffix == ".zip":
                try:
                    with zipfile.ZipFile(backup_file, "r") as zip_file:
                        if "backup_metadata.json" in zip_file.namelist():
                            metadata_content = zip_file.read("backup_metadata.json")
                            metadata = json.loads(metadata_content.decode())
                            backup_info["metadata"] = metadata
                except Exception:
                    logger.debug("Failed to parse backup metadata")

            backups.append(backup_info)

        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups


class DatabaseMaintenance:
    """Database maintenance operations."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize database maintenance utility.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)

    def vacuum(self) -> bool:
        """Run VACUUM to reclaim space and defragment.

        Returns:
            True if successful
        """
        try:
            logger.info("Running VACUUM operation")
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("VACUUM")
            logger.info("VACUUM completed successfully")
            return True
        except Exception as e:
            logger.error(f"VACUUM failed: {e}")
            return False

    def analyze(self) -> bool:
        """Run ANALYZE to update query planner statistics.

        Returns:
            True if successful
        """
        try:
            logger.info("Running ANALYZE operation")
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("ANALYZE")
            logger.info("ANALYZE completed successfully")
            return True
        except Exception as e:
            logger.error(f"ANALYZE failed: {e}")
            return False

    def reindex(self, table: str | None = None) -> bool:
        """Rebuild indexes.

        Args:
            table: Specific table to reindex (all if None)

        Returns:
            True if successful
        """
        try:
            if table:
                logger.info(f"Reindexing table {table}")
                sql = f"REINDEX {table}"
            else:
                logger.info("Reindexing all tables")
                sql = "REINDEX"

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(sql)

            logger.info("Reindex completed successfully")
            return True
        except Exception as e:
            logger.error(f"Reindex failed: {e}")
            return False

    def check_integrity(self) -> tuple[bool, list[str]]:
        """Check database integrity.

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check integrity
                cursor = conn.execute("PRAGMA integrity_check")
                results = cursor.fetchall()

                for result in results:
                    if result[0] != "ok":
                        issues.append(result[0])

                # Check foreign key constraints
                cursor = conn.execute("PRAGMA foreign_key_check")
                fk_violations = cursor.fetchall()

                for violation in fk_violations:
                    issues.append(
                        f"Foreign key violation in table {violation[0]}: {violation}"
                    )

        except Exception as e:
            issues.append(f"Integrity check failed: {e}")

        is_valid = len(issues) == 0
        if is_valid:
            logger.info("Database integrity check passed")
        else:
            logger.warning(f"Database integrity check found {len(issues)} issues")

        return is_valid, issues

    def optimize(self) -> bool:
        """Run full optimization (analyze, vacuum, reindex).

        Returns:
            True if all operations successful
        """
        logger.info("Starting database optimization")

        operations: list[tuple[str, Callable[[], bool]]] = [
            ("analyze", self.analyze),
            ("vacuum", self.vacuum),
            ("reindex", self.reindex),
        ]

        success = True
        for name, operation in operations:
            if not operation():
                logger.error(f"Optimization failed at {name}")
                success = False
                break

        if success:
            logger.info("Database optimization completed successfully")
        else:
            logger.error("Database optimization failed")

        return success

    def get_fragmentation_info(self) -> dict[str, Any]:
        """Get database fragmentation information.

        Returns:
            Dictionary with fragmentation metrics
        """
        info = {}

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get page statistics
                cursor = conn.execute("PRAGMA page_count")
                total_pages = cursor.fetchone()[0]

                cursor = conn.execute("PRAGMA freelist_count")
                free_pages = cursor.fetchone()[0]

                cursor = conn.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]

                # Calculate fragmentation
                used_pages = total_pages - free_pages
                fragmentation_percent = (
                    (free_pages / total_pages) * 100 if total_pages > 0 else 0
                )

                info = {
                    "total_pages": total_pages,
                    "used_pages": used_pages,
                    "free_pages": free_pages,
                    "page_size": page_size,
                    "fragmentation_percent": fragmentation_percent,
                    "wasted_bytes": free_pages * page_size,
                    "total_bytes": total_pages * page_size,
                }

        except Exception as e:
            logger.error(f"Failed to get fragmentation info: {e}")

        return info


def export_data_to_json(
    db_path: str | Path, output_path: str | Path, tables: list[str] | None = None
) -> bool:
    """Export database data to JSON format.

    Args:
        db_path: Path to SQLite database
        output_path: Path for JSON output file
        tables: Specific tables to export (all if None)

    Returns:
        True if successful
    """
    db_path = Path(db_path)
    output_path = Path(output_path)

    try:
        data = {}

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get table list
            if tables is None:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
                tables = [row["name"] for row in cursor.fetchall()]

            # Export each table
            for table in tables:
                cursor = conn.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                data[table] = [dict(row) for row in rows]

        # Write JSON
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Exported {len(tables)} tables to {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to export data: {e}")
        return False


def get_database_health_report(db_path: str | Path) -> dict[str, Any]:
    """Generate comprehensive database health report.

    Args:
        db_path: Path to SQLite database

    Returns:
        Dictionary with health report
    """
    db_path = Path(db_path)

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "database_path": str(db_path),
        "exists": db_path.exists(),
    }

    if not db_path.exists():
        report["status"] = "NOT_FOUND"
        return report

    try:
        # Basic statistics
        stats = DatabaseStats(db_path)
        report["size_info"] = stats.get_database_size()

        # Table stats may fail if dbstat is not available
        try:
            report["table_stats"] = stats.get_table_stats()
        except sqlite3.OperationalError as e:
            if "no such table: dbstat" in str(e):
                logger.debug("dbstat not available, skipping detailed table stats")
                report["table_stats"] = {}  # Empty dict to indicate no stats available
            else:
                raise

        report["performance_stats"] = stats.get_query_performance_stats()

        # Maintenance checks
        maintenance = DatabaseMaintenance(db_path)
        integrity_ok, integrity_issues = maintenance.check_integrity()
        report["integrity"] = {
            "valid": integrity_ok,
            "issues": integrity_issues,
        }

        report["fragmentation"] = maintenance.get_fragmentation_info()

        # Overall health assessment
        issues = []
        if not integrity_ok:
            issues.append("Integrity check failed")

        fragmentation_data = report.get("fragmentation", {})
        if (
            isinstance(fragmentation_data, dict)
            and fragmentation_data.get("fragmentation_percent", 0) > 20
        ):
            issues.append("High fragmentation detected")

        size_info_data = report.get("size_info", {})
        if (
            isinstance(size_info_data, dict)
            and size_info_data.get("utilization_percent", 100) < 50
        ):
            issues.append("Low space utilization")

        report["status"] = "HEALTHY" if not issues else "NEEDS_ATTENTION"
        report["issues"] = issues
        report["recommendations"] = _get_health_recommendations(report)

    except Exception as e:
        report["status"] = "ERROR"
        report["error"] = str(e)
        logger.error(f"Failed to generate health report: {e}")

    return report


def _get_health_recommendations(report: dict[str, Any]) -> list[str]:
    """Generate health recommendations based on report.

    Args:
        report: Health report data

    Returns:
        List of recommendations
    """
    recommendations = []

    # Fragmentation recommendations
    fragmentation = report.get("fragmentation", {}).get("fragmentation_percent", 0)
    if fragmentation > 30:
        recommendations.append("Run VACUUM to reduce fragmentation")
    elif fragmentation > 15:
        recommendations.append("Consider running VACUUM during maintenance window")

    # Utilization recommendations
    utilization = report.get("size_info", {}).get("utilization_percent", 100)
    if utilization < 50:
        recommendations.append("Database has significant unused space, consider VACUUM")

    # Performance recommendations
    cache_size = report.get("performance_stats", {}).get("cache_size_pages", 0)
    if cache_size < 2000:
        recommendations.append("Consider increasing cache_size for better performance")

    journal_mode = report.get("performance_stats", {}).get("journal_mode", "")
    if journal_mode != "wal":
        recommendations.append("Consider using WAL mode for better concurrency")

    # General maintenance
    recommendations.append("Run ANALYZE periodically to update query statistics")

    return recommendations

"""Database operations for the Mentors system.

This module provides database operations for storing and retrieving mentor
analysis results. It extends the existing ScriptRAG database schema with
tables for mentor analyses and results.
"""

import json
import sqlite3
from datetime import datetime
from uuid import UUID

from scriptrag.config import get_logger
from scriptrag.database.connection import DatabaseConnection
from scriptrag.mentors.base import AnalysisSeverity, MentorAnalysis, MentorResult

logger = get_logger(__name__)


# Extended schema for mentor system
MENTOR_SCHEMA_SQL = """
-- Mentor analysis results table
CREATE TABLE IF NOT EXISTS mentor_results (
    id TEXT PRIMARY KEY,
    mentor_name TEXT NOT NULL,
    mentor_version TEXT NOT NULL,
    script_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    score REAL,
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms INTEGER,
    config_json TEXT, -- JSON string of configuration used
    metadata_json TEXT, -- JSON string for additional metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
);

-- Individual mentor analyses table
CREATE TABLE IF NOT EXISTS mentor_analyses (
    id TEXT PRIMARY KEY,
    result_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL, -- 'info', 'suggestion', 'warning', 'error'
    scene_id TEXT,
    character_id TEXT,
    element_id TEXT,
    category TEXT NOT NULL,
    mentor_name TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    recommendations_json TEXT, -- JSON array of recommendations
    examples_json TEXT, -- JSON array of examples
    metadata_json TEXT, -- JSON object for mentor-specific data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (result_id) REFERENCES mentor_results(id) ON DELETE CASCADE,
    FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (element_id) REFERENCES scene_elements(id) ON DELETE CASCADE
);

-- Indexes for mentor tables
CREATE INDEX IF NOT EXISTS idx_mentor_results_script_id ON mentor_results(script_id);
CREATE INDEX IF NOT EXISTS idx_mentor_results_mentor_name
    ON mentor_results(mentor_name);
CREATE INDEX IF NOT EXISTS idx_mentor_results_analysis_date
    ON mentor_results(analysis_date);

CREATE INDEX IF NOT EXISTS idx_mentor_analyses_result_id ON mentor_analyses(result_id);
CREATE INDEX IF NOT EXISTS idx_mentor_analyses_scene_id ON mentor_analyses(scene_id);
CREATE INDEX IF NOT EXISTS idx_mentor_analyses_character_id
    ON mentor_analyses(character_id);
CREATE INDEX IF NOT EXISTS idx_mentor_analyses_element_id
    ON mentor_analyses(element_id);
CREATE INDEX IF NOT EXISTS idx_mentor_analyses_category ON mentor_analyses(category);
CREATE INDEX IF NOT EXISTS idx_mentor_analyses_severity ON mentor_analyses(severity);
CREATE INDEX IF NOT EXISTS idx_mentor_analyses_mentor_name
    ON mentor_analyses(mentor_name);

-- Triggers for maintaining updated_at timestamps
CREATE TRIGGER IF NOT EXISTS update_mentor_results_timestamp
    AFTER UPDATE ON mentor_results
    BEGIN
        UPDATE mentor_results SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_mentor_analyses_timestamp
    AFTER UPDATE ON mentor_analyses
    BEGIN
        UPDATE mentor_analyses SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- Full-text search for mentor analyses
CREATE VIRTUAL TABLE IF NOT EXISTS mentor_analyses_fts USING fts5(
    analysis_id,
    title,
    description,
    mentor_name,
    category,
    content='mentor_analyses',
    content_rowid='rowid'
);

-- FTS triggers for mentor analyses
CREATE TRIGGER IF NOT EXISTS mentor_analyses_fts_insert
    AFTER INSERT ON mentor_analyses
    BEGIN
        INSERT INTO mentor_analyses_fts(
            analysis_id, title, description, mentor_name, category
        )
        VALUES (NEW.id, NEW.title, NEW.description, NEW.mentor_name, NEW.category);
    END;

CREATE TRIGGER IF NOT EXISTS mentor_analyses_fts_update
    AFTER UPDATE ON mentor_analyses
    BEGIN
        UPDATE mentor_analyses_fts
        SET title = NEW.title, description = NEW.description,
            mentor_name = NEW.mentor_name, category = NEW.category
        WHERE analysis_id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS mentor_analyses_fts_delete
    AFTER DELETE ON mentor_analyses
    BEGIN
        DELETE FROM mentor_analyses_fts WHERE analysis_id = OLD.id;
    END;
"""


class MentorDatabaseOperations:
    """Database operations for mentor system.

    This class provides methods for storing and retrieving mentor analysis
    results from the database.
    """

    def __init__(self, connection: DatabaseConnection) -> None:
        """Initialize database operations.

        Args:
            connection: Database connection instance
        """
        self.connection = connection
        self._ensure_mentor_schema()

    def _ensure_mentor_schema(self) -> None:
        """Ensure mentor-specific tables exist in the database."""
        with self.connection.transaction() as conn:
            conn.executescript(MENTOR_SCHEMA_SQL)
            logger.debug("Mentor database schema ensured")

    def store_mentor_result(self, result: MentorResult) -> bool:
        """Store a complete mentor analysis result.

        Args:
            result: The mentor result to store

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            with self.connection.transaction() as conn:
                # Store the main result
                conn.execute(
                    """
                    INSERT OR REPLACE INTO mentor_results (
                        id, mentor_name, mentor_version, script_id, summary, score,
                        analysis_date, execution_time_ms, config_json, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(result.id),
                        result.mentor_name,
                        result.mentor_version,
                        str(result.script_id),
                        result.summary,
                        result.score,
                        result.analysis_date.isoformat(),
                        result.execution_time_ms,
                        json.dumps(result.config),
                        json.dumps({}),  # Reserved for future metadata
                    ),
                )

                # Store individual analyses
                for analysis in result.analyses:
                    self._store_mentor_analysis(conn, analysis, str(result.id))

            logger.info(
                f"Stored mentor result {result.id} with {len(result.analyses)} analyses"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store mentor result {result.id}: {e}")
            return False

    def _store_mentor_analysis(
        self, conn: sqlite3.Connection, analysis: MentorAnalysis, result_id: str
    ) -> None:
        """Store an individual mentor analysis.

        Args:
            conn: Database connection
            analysis: The analysis to store
            result_id: ID of the parent result
        """
        conn.execute(
            """
            INSERT OR REPLACE INTO mentor_analyses (
                id, result_id, title, description, severity, scene_id, character_id,
                element_id, category, mentor_name, confidence, recommendations_json,
                examples_json, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(analysis.id),
                result_id,
                analysis.title,
                analysis.description,
                analysis.severity.value,
                str(analysis.scene_id) if analysis.scene_id else None,
                str(analysis.character_id) if analysis.character_id else None,
                str(analysis.element_id) if analysis.element_id else None,
                analysis.category,
                analysis.mentor_name,
                analysis.confidence,
                json.dumps(analysis.recommendations),
                json.dumps(analysis.examples),
                json.dumps(analysis.metadata),
            ),
        )

    def get_mentor_result(self, result_id: UUID) -> MentorResult | None:
        """Retrieve a mentor result by ID.

        Args:
            result_id: ID of the result to retrieve

        Returns:
            MentorResult if found, None otherwise
        """
        try:
            with self.connection.transaction() as conn:
                # Get the main result
                result_row = conn.execute(
                    """
                    SELECT id, mentor_name, mentor_version, script_id, summary, score,
                           analysis_date, execution_time_ms, config_json
                    FROM mentor_results
                    WHERE id = ?
                    """,
                    (str(result_id),),
                ).fetchone()

                if not result_row:
                    return None

                # Get the analyses
                analysis_rows = conn.execute(
                    """
                    SELECT id, title, description, severity, scene_id, character_id,
                           element_id, category, mentor_name, confidence,
                           recommendations_json, examples_json, metadata_json
                    FROM mentor_analyses
                    WHERE result_id = ?
                    ORDER BY created_at
                    """,
                    (str(result_id),),
                ).fetchall()

                # Build analyses list
                analyses = []
                for row in analysis_rows:
                    analyses.append(
                        MentorAnalysis(
                            id=UUID(row[0]),
                            title=row[1],
                            description=row[2],
                            severity=AnalysisSeverity(row[3]),
                            scene_id=UUID(row[4]) if row[4] else None,
                            character_id=UUID(row[5]) if row[5] else None,
                            element_id=UUID(row[6]) if row[6] else None,
                            category=row[7],
                            mentor_name=row[8],
                            confidence=row[9],
                            recommendations=json.loads(row[10]) if row[10] else [],
                            examples=json.loads(row[11]) if row[11] else [],
                            metadata=json.loads(row[12]) if row[12] else {},
                        )
                    )

                # Build result
                return MentorResult(
                    id=UUID(result_row[0]),
                    mentor_name=result_row[1],
                    mentor_version=result_row[2],
                    script_id=UUID(result_row[3]),
                    summary=result_row[4],
                    score=result_row[5],
                    analysis_date=datetime.fromisoformat(result_row[6]),
                    execution_time_ms=result_row[7],
                    config=json.loads(result_row[8]) if result_row[8] else {},
                    analyses=analyses,
                )

        except Exception as e:
            logger.error(f"Failed to get mentor result {result_id}: {e}")
            return None

    def get_script_mentor_results(
        self, script_id: UUID, mentor_name: str | None = None
    ) -> list[MentorResult]:
        """Get all mentor results for a script.

        Args:
            script_id: ID of the script
            mentor_name: Optional filter by mentor name

        Returns:
            List of mentor results
        """
        try:
            with self.connection.transaction() as conn:
                query = """
                    SELECT id FROM mentor_results
                    WHERE script_id = ?
                """
                params = [str(script_id)]

                if mentor_name:
                    query += " AND mentor_name = ?"
                    params.append(mentor_name)

                query += " ORDER BY analysis_date DESC"

                result_ids = conn.execute(query, params).fetchall()

                results = []
                for (result_id,) in result_ids:
                    result = self.get_mentor_result(UUID(result_id))
                    if result:
                        results.append(result)

                return results

        except Exception as e:
            logger.error(f"Failed to get mentor results for script {script_id}: {e}")
            return []

    def get_scene_analyses(
        self, scene_id: UUID, mentor_name: str | None = None
    ) -> list[MentorAnalysis]:
        """Get all analyses for a specific scene.

        Args:
            scene_id: ID of the scene
            mentor_name: Optional filter by mentor name

        Returns:
            List of mentor analyses for the scene
        """
        try:
            with self.connection.transaction() as conn:
                query = """
                    SELECT id, title, description, severity, scene_id, character_id,
                           element_id, category, mentor_name, confidence,
                           recommendations_json, examples_json, metadata_json
                    FROM mentor_analyses
                    WHERE scene_id = ?
                """
                params = [str(scene_id)]

                if mentor_name:
                    query += " AND mentor_name = ?"
                    params.append(mentor_name)

                query += " ORDER BY created_at"

                rows = conn.execute(query, params).fetchall()

                analyses = []
                for row in rows:
                    analyses.append(
                        MentorAnalysis(
                            id=UUID(row[0]),
                            title=row[1],
                            description=row[2],
                            severity=AnalysisSeverity(row[3]),
                            scene_id=UUID(row[4]) if row[4] else None,
                            character_id=UUID(row[5]) if row[5] else None,
                            element_id=UUID(row[6]) if row[6] else None,
                            category=row[7],
                            mentor_name=row[8],
                            confidence=row[9],
                            recommendations=json.loads(row[10]) if row[10] else [],
                            examples=json.loads(row[11]) if row[11] else [],
                            metadata=json.loads(row[12]) if row[12] else {},
                        )
                    )

                return analyses

        except Exception as e:
            logger.error(f"Failed to get scene analyses for scene {scene_id}: {e}")
            return []

    def delete_mentor_result(self, result_id: UUID) -> bool:
        """Delete a mentor result and all its analyses.

        Args:
            result_id: ID of the result to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            with self.connection.transaction() as conn:
                # Delete the result (analyses will be deleted via CASCADE)
                cursor = conn.execute(
                    "DELETE FROM mentor_results WHERE id = ?", (str(result_id),)
                )

                if cursor.rowcount > 0:
                    logger.info(f"Deleted mentor result {result_id}")
                    return True
                logger.warning(f"Mentor result {result_id} not found for deletion")
                return False

        except Exception as e:
            logger.error(f"Failed to delete mentor result {result_id}: {e}")
            return False

    def search_analyses(
        self,
        query: str,
        mentor_name: str | None = None,
        category: str | None = None,
        severity: AnalysisSeverity | None = None,
        limit: int = 50,
    ) -> list[MentorAnalysis]:
        """Search mentor analyses using full-text search.

        Args:
            query: Search query
            mentor_name: Optional filter by mentor name
            category: Optional filter by category
            severity: Optional filter by severity
            limit: Maximum number of results

        Returns:
            List of matching mentor analyses
        """
        try:
            with self.connection.transaction() as conn:
                # Build the query
                sql_query = """
                    SELECT ma.id, ma.title, ma.description, ma.severity, ma.scene_id,
                           ma.character_id, ma.element_id, ma.category, ma.mentor_name,
                           ma.confidence, ma.recommendations_json, ma.examples_json,
                           ma.metadata_json
                    FROM mentor_analyses_fts fts
                    JOIN mentor_analyses ma ON fts.analysis_id = ma.id
                    WHERE mentor_analyses_fts MATCH ?
                """
                params = [query]

                if mentor_name:
                    sql_query += " AND ma.mentor_name = ?"
                    params.append(mentor_name)

                if category:
                    sql_query += " AND ma.category = ?"
                    params.append(category)

                if severity:
                    sql_query += " AND ma.severity = ?"
                    params.append(severity.value)

                sql_query += " ORDER BY fts.rank LIMIT ?"
                params.append(str(limit))

                rows = conn.execute(sql_query, params).fetchall()

                analyses = []
                for row in rows:
                    analyses.append(
                        MentorAnalysis(
                            id=UUID(row[0]),
                            title=row[1],
                            description=row[2],
                            severity=AnalysisSeverity(row[3]),
                            scene_id=UUID(row[4]) if row[4] else None,
                            character_id=UUID(row[5]) if row[5] else None,
                            element_id=UUID(row[6]) if row[6] else None,
                            category=row[7],
                            mentor_name=row[8],
                            confidence=row[9],
                            recommendations=json.loads(row[10]) if row[10] else [],
                            examples=json.loads(row[11]) if row[11] else [],
                            metadata=json.loads(row[12]) if row[12] else {},
                        )
                    )

                return analyses

        except Exception as e:
            logger.error(f"Failed to search mentor analyses: {e}")
            return []

    def get_mentor_statistics(self, script_id: UUID) -> dict[str, int | float]:
        """Get statistics about mentor analyses for a script.

        Args:
            script_id: ID of the script

        Returns:
            Dictionary with statistics
        """
        try:
            with self.connection.transaction() as conn:
                # Get basic counts
                stats = {}

                # Total analyses
                total = conn.execute(
                    """
                    SELECT COUNT(*) FROM mentor_analyses ma
                    JOIN mentor_results mr ON ma.result_id = mr.id
                    WHERE mr.script_id = ?
                    """,
                    (str(script_id),),
                ).fetchone()[0]
                stats["total_analyses"] = total

                # Severity breakdown
                for severity in AnalysisSeverity:
                    count = conn.execute(
                        """
                        SELECT COUNT(*) FROM mentor_analyses ma
                        JOIN mentor_results mr ON ma.result_id = mr.id
                        WHERE mr.script_id = ? AND ma.severity = ?
                        """,
                        (str(script_id), severity.value),
                    ).fetchone()[0]
                    stats[f"{severity.value}_count"] = count

                # Average confidence
                avg_confidence = conn.execute(
                    """
                    SELECT AVG(ma.confidence) FROM mentor_analyses ma
                    JOIN mentor_results mr ON ma.result_id = mr.id
                    WHERE mr.script_id = ?
                    """,
                    (str(script_id),),
                ).fetchone()[0]
                stats["average_confidence"] = avg_confidence or 0.0

                # Number of unique mentors
                unique_mentors = conn.execute(
                    """
                    SELECT COUNT(DISTINCT ma.mentor_name) FROM mentor_analyses ma
                    JOIN mentor_results mr ON ma.result_id = mr.id
                    WHERE mr.script_id = ?
                    """,
                    (str(script_id),),
                ).fetchone()[0]
                stats["unique_mentors"] = unique_mentors

                return stats

        except Exception as e:
            logger.error(f"Failed to get mentor statistics for script {script_id}: {e}")
            return {}

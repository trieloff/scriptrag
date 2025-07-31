"""Migration 5: Add Script Bible and continuity tracking tables."""

import sqlite3

from scriptrag.config import get_logger

from .base import Migration

logger = get_logger(__name__)


class ScriptBibleMigration(Migration):
    """Migration 5: Add Script Bible and continuity tracking tables."""

    version = 5
    description = "Add Script Bible and continuity tracking tables"

    def up(self, connection: sqlite3.Connection) -> None:
        """Apply Script Bible migration."""
        logger.info("Applying Script Bible migration")

        # Series information and bible metadata
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS series_bibles (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                version INTEGER DEFAULT 1,
                created_by TEXT,
                status TEXT DEFAULT 'active',
                bible_type TEXT DEFAULT 'series',
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
            )
            """
        )

        # Character development profiles and arcs
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS character_profiles (
                id TEXT PRIMARY KEY,
                character_id TEXT NOT NULL,
                script_id TEXT NOT NULL,
                series_bible_id TEXT,
                full_name TEXT,
                age INTEGER,
                occupation TEXT,
                background TEXT,
                personality_traits TEXT,
                motivations TEXT,
                fears TEXT,
                goals TEXT,
                physical_description TEXT,
                distinguishing_features TEXT,
                family_background TEXT,
                relationship_status TEXT,
                initial_state TEXT,
                character_arc TEXT,
                growth_trajectory TEXT,
                first_appearance_episode_id TEXT,
                last_appearance_episode_id TEXT,
                total_appearances INTEGER DEFAULT 0,
                notes TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                FOREIGN KEY (series_bible_id)
                    REFERENCES series_bibles(id) ON DELETE CASCADE,
                FOREIGN KEY (first_appearance_episode_id)
                    REFERENCES episodes(id) ON DELETE SET NULL,
                FOREIGN KEY (last_appearance_episode_id)
                    REFERENCES episodes(id) ON DELETE SET NULL,
                UNIQUE(character_id, script_id)
            )
            """
        )

        # World building and setting elements
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS world_elements (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                series_bible_id TEXT,
                element_type TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                description TEXT,
                rules_and_constraints TEXT,
                visual_description TEXT,
                first_introduced_episode_id TEXT,
                first_introduced_scene_id TEXT,
                usage_frequency INTEGER DEFAULT 0,
                importance_level INTEGER DEFAULT 1,
                related_locations_json TEXT,
                related_characters_json TEXT,
                continuity_notes TEXT,
                established_rules_json TEXT,
                notes TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                FOREIGN KEY (series_bible_id)
                    REFERENCES series_bibles(id) ON DELETE CASCADE,
                FOREIGN KEY (first_introduced_episode_id)
                    REFERENCES episodes(id) ON DELETE SET NULL,
                FOREIGN KEY (first_introduced_scene_id)
                    REFERENCES scenes(id) ON DELETE SET NULL
            )
            """
        )

        # Timeline and chronology tracking
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS story_timelines (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                series_bible_id TEXT,
                name TEXT NOT NULL,
                timeline_type TEXT DEFAULT 'main',
                description TEXT,
                start_date TEXT,
                end_date TEXT,
                duration_description TEXT,
                reference_episodes_json TEXT,
                reference_scenes_json TEXT,
                notes TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                FOREIGN KEY (series_bible_id)
                    REFERENCES series_bibles(id) ON DELETE CASCADE
            )
            """
        )

        # Timeline events for detailed chronology
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS timeline_events (
                id TEXT PRIMARY KEY,
                timeline_id TEXT NOT NULL,
                script_id TEXT NOT NULL,
                event_name TEXT NOT NULL,
                event_type TEXT DEFAULT 'plot',
                story_date TEXT,
                relative_order INTEGER,
                duration_minutes INTEGER,
                description TEXT,
                episode_id TEXT,
                scene_id TEXT,
                related_characters_json TEXT,
                establishes_json TEXT,
                requires_json TEXT,
                affects_json TEXT,
                notes TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (timeline_id)
                    REFERENCES story_timelines(id) ON DELETE CASCADE,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
                FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE SET NULL
            )
            """
        )

        # Production notes and tracking
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS production_notes (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                series_bible_id TEXT,
                note_type TEXT NOT NULL,
                category TEXT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                priority INTEGER DEFAULT 3,
                status TEXT DEFAULT 'open',
                episode_id TEXT,
                scene_id TEXT,
                character_id TEXT,
                assigned_to TEXT,
                due_date TEXT,
                resolved_date TEXT,
                resolution_notes TEXT,
                tags_json TEXT,
                attachments_json TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                FOREIGN KEY (series_bible_id)
                    REFERENCES series_bibles(id) ON DELETE CASCADE,
                FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
                FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE SET NULL,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE SET NULL
            )
            """
        )

        # Continuity issues tracking
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS continuity_issues (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                issue_type TEXT NOT NULL,
                severity TEXT DEFAULT 'warning',
                status TEXT DEFAULT 'open',
                description TEXT NOT NULL,
                first_occurrence_episode_id TEXT,
                first_occurrence_scene_id TEXT,
                conflicting_episodes_json TEXT,
                conflicting_scenes_json TEXT,
                affected_characters_json TEXT,
                affected_elements_json TEXT,
                suggested_resolution TEXT,
                resolution_notes TEXT,
                resolved_by TEXT,
                resolved_date TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                FOREIGN KEY (first_occurrence_episode_id)
                    REFERENCES episodes(id) ON DELETE SET NULL,
                FOREIGN KEY (first_occurrence_scene_id)
                    REFERENCES scenes(id) ON DELETE SET NULL
            )
            """
        )

        # Continuity validations log
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS continuity_validations (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                validation_type TEXT NOT NULL,
                validation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                episodes_validated INTEGER DEFAULT 0,
                scenes_validated INTEGER DEFAULT 0,
                issues_found INTEGER DEFAULT 0,
                issues_resolved INTEGER DEFAULT 0,
                validation_rules_json TEXT,
                results_summary_json TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
            )
            """
        )

        # Continuity notes table
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS continuity_notes (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                series_bible_id TEXT,
                note_type TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'open',
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                suggested_resolution TEXT,
                episode_id TEXT,
                scene_id TEXT,
                character_id TEXT,
                world_element_id TEXT,
                timeline_event_id TEXT,
                related_episodes_json TEXT,
                related_scenes_json TEXT,
                related_characters_json TEXT,
                reported_by TEXT,
                assigned_to TEXT,
                resolution_notes TEXT,
                resolved_at TIMESTAMP,
                tags_json TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                FOREIGN KEY (series_bible_id)
                    REFERENCES series_bibles(id) ON DELETE CASCADE,
                FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
                FOREIGN KEY (scene_id) REFERENCES scenes(id) ON DELETE SET NULL,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE SET NULL,
                FOREIGN KEY (world_element_id)
                    REFERENCES world_elements(id) ON DELETE SET NULL,
                FOREIGN KEY (timeline_event_id)
                    REFERENCES timeline_events(id) ON DELETE SET NULL
            )
            """
        )

        # Character knowledge tracking
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS character_knowledge (
                id TEXT PRIMARY KEY,
                character_id TEXT NOT NULL,
                script_id TEXT NOT NULL,
                knowledge_type TEXT NOT NULL,
                knowledge_subject TEXT NOT NULL,
                knowledge_description TEXT,
                acquired_episode_id TEXT,
                acquired_scene_id TEXT,
                acquisition_method TEXT,
                first_used_episode_id TEXT,
                first_used_scene_id TEXT,
                usage_count INTEGER DEFAULT 0,
                should_know_before TEXT,
                verification_status TEXT DEFAULT 'unverified',
                confidence_level REAL DEFAULT 1.0,
                notes TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                FOREIGN KEY (acquired_episode_id)
                    REFERENCES episodes(id) ON DELETE SET NULL,
                FOREIGN KEY (acquired_scene_id)
                    REFERENCES scenes(id) ON DELETE SET NULL,
                FOREIGN KEY (first_used_episode_id)
                    REFERENCES episodes(id) ON DELETE SET NULL,
                FOREIGN KEY (first_used_scene_id)
                    REFERENCES scenes(id) ON DELETE SET NULL
            )
            """
        )

        # Plot threads tracking
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS plot_threads (
                id TEXT PRIMARY KEY,
                script_id TEXT NOT NULL,
                series_bible_id TEXT,
                name TEXT NOT NULL,
                thread_type TEXT DEFAULT 'main',
                priority INTEGER DEFAULT 1,
                description TEXT,
                initial_setup TEXT,
                central_conflict TEXT,
                resolution TEXT,
                status TEXT DEFAULT 'active',
                introduced_episode_id TEXT,
                resolved_episode_id TEXT,
                total_episodes_involved INTEGER DEFAULT 0,
                primary_characters_json TEXT,
                supporting_characters_json TEXT,
                key_scenes_json TEXT,
                resolution_scenes_json TEXT,
                notes TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE,
                FOREIGN KEY (series_bible_id)
                    REFERENCES series_bibles(id) ON DELETE CASCADE,
                FOREIGN KEY (introduced_episode_id)
                    REFERENCES episodes(id) ON DELETE SET NULL,
                FOREIGN KEY (resolved_episode_id)
                    REFERENCES episodes(id) ON DELETE SET NULL
            )
            """
        )

        # Create indexes for Script Bible tables
        self._create_indexes(connection)

        logger.info("Script Bible migration applied successfully")

    def down(self, connection: sqlite3.Connection) -> None:
        """Rollback Script Bible migration."""
        logger.warning("Rolling back Script Bible migration")

        # Drop indexes
        indexes = [
            "idx_series_bibles_script_id",
            "idx_series_bibles_status",
            "idx_series_bibles_type",
            "idx_character_profiles_character_id",
            "idx_character_profiles_script_id",
            "idx_character_profiles_series_bible_id",
            "idx_world_elements_script_id",
            "idx_world_elements_series_bible_id",
            "idx_world_elements_type",
            "idx_world_elements_name",
            "idx_story_timelines_script_id",
            "idx_story_timelines_series_bible_id",
            "idx_story_timelines_type",
            "idx_timeline_events_timeline_id",
            "idx_timeline_events_script_id",
            "idx_timeline_events_episode_id",
            "idx_timeline_events_scene_id",
            "idx_timeline_events_type",
            "idx_production_notes_script_id",
            "idx_production_notes_series_bible_id",
            "idx_production_notes_type",
            "idx_production_notes_status",
            "idx_production_notes_priority",
            "idx_continuity_issues_script_id",
            "idx_continuity_issues_type",
            "idx_continuity_issues_severity",
            "idx_continuity_issues_status",
            "idx_continuity_validations_script_id",
            "idx_continuity_validations_type",
            "idx_continuity_validations_date",
            "idx_continuity_notes_script_id",
            "idx_continuity_notes_bible_id",
            "idx_continuity_notes_type",
            "idx_continuity_notes_status",
            "idx_continuity_notes_severity",
            "idx_character_knowledge_character_id",
            "idx_character_knowledge_script_id",
            "idx_character_knowledge_type",
            "idx_plot_threads_script_id",
            "idx_plot_threads_bible_id",
            "idx_plot_threads_type",
            "idx_plot_threads_status",
        ]

        for idx in indexes:
            connection.execute(f"DROP INDEX IF EXISTS {idx}")

        # Drop tables in reverse order of creation
        tables = [
            "plot_threads",
            "character_knowledge",
            "continuity_notes",
            "continuity_validations",
            "continuity_issues",
            "production_notes",
            "timeline_events",
            "story_timelines",
            "world_elements",
            "character_profiles",
            "series_bibles",
        ]

        for table in tables:
            connection.execute(f"DROP TABLE IF EXISTS {table}")

        logger.info("Script Bible migration rolled back successfully")

    def _create_indexes(self, connection: sqlite3.Connection) -> None:
        """Create indexes for Script Bible tables."""
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_series_bibles_script_id
                ON series_bibles(script_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_series_bibles_status
                ON series_bibles(status)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_series_bibles_type
                ON series_bibles(bible_type)"""
        )

        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_character_profiles_character_id
                ON character_profiles(character_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_character_profiles_script_id
                ON character_profiles(script_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_character_profiles_series_bible_id
                ON character_profiles(series_bible_id)"""
        )

        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_world_elements_script_id
                ON world_elements(script_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_world_elements_series_bible_id
                ON world_elements(series_bible_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_world_elements_type
                ON world_elements(element_type)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_world_elements_name
                ON world_elements(name)"""
        )

        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_story_timelines_script_id
                ON story_timelines(script_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_story_timelines_series_bible_id
                ON story_timelines(series_bible_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_story_timelines_type
                ON story_timelines(timeline_type)"""
        )

        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_timeline_events_timeline_id
                ON timeline_events(timeline_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_timeline_events_script_id
                ON timeline_events(script_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_timeline_events_episode_id
                ON timeline_events(episode_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_timeline_events_scene_id
                ON timeline_events(scene_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_timeline_events_type
                ON timeline_events(event_type)"""
        )

        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_production_notes_script_id
                ON production_notes(script_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_production_notes_series_bible_id
                ON production_notes(series_bible_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_production_notes_type
                ON production_notes(note_type)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_production_notes_status
                ON production_notes(status)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_production_notes_priority
                ON production_notes(priority)"""
        )

        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_continuity_issues_script_id
                ON continuity_issues(script_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_continuity_issues_type
                ON continuity_issues(issue_type)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_continuity_issues_severity
                ON continuity_issues(severity)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_continuity_issues_status
                ON continuity_issues(status)"""
        )

        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_continuity_validations_script_id
                ON continuity_validations(script_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_continuity_validations_type
                ON continuity_validations(validation_type)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_continuity_validations_date
                ON continuity_validations(validation_date)"""
        )

        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_continuity_notes_script_id
                ON continuity_notes(script_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_continuity_notes_bible_id
                ON continuity_notes(series_bible_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_continuity_notes_type
                ON continuity_notes(note_type)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_continuity_notes_status
                ON continuity_notes(status)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_continuity_notes_severity
                ON continuity_notes(severity)"""
        )

        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_character_knowledge_character_id
                ON character_knowledge(character_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_character_knowledge_script_id
                ON character_knowledge(script_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_character_knowledge_type
                ON character_knowledge(knowledge_type)"""
        )

        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_plot_threads_script_id
                ON plot_threads(script_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_plot_threads_bible_id
                ON plot_threads(series_bible_id)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_plot_threads_type
                ON plot_threads(thread_type)"""
        )
        connection.execute(
            """CREATE INDEX IF NOT EXISTS idx_plot_threads_status
                ON plot_threads(status)"""
        )

"""Script Bible and Continuity Management database operations.

This module provides database operations for managing Script Bibles,
character development tracking, continuity validation, and storyline management.
"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from scriptrag.config import get_logger
from scriptrag.models import (
    CharacterKnowledge,
    CharacterProfile,
    ContinuityNote,
    PlotThread,
    SeriesBible,
    TimelineEvent,
    WorldElement,
)

from .connection import DatabaseConnection

logger = get_logger(__name__)


class ScriptBibleOperations:
    """Database operations for Script Bible and continuity management."""

    def __init__(self, connection: DatabaseConnection) -> None:
        """Initialize Script Bible operations.

        Args:
            connection: Database connection instance
        """
        self.connection = connection

    # Series Bible operations
    def create_series_bible(
        self,
        script_id: str,
        title: str,
        description: str | None = None,
        created_by: str | None = None,
        bible_type: str = "series",
    ) -> str:
        """Create a new series bible.

        Args:
            script_id: ID of the associated script
            title: Bible title
            description: Bible description
            created_by: Creator name
            bible_type: Type of bible (series, movie, anthology)

        Returns:
            Bible ID
        """
        bible_id = str(uuid4())

        with self.connection.transaction() as conn:
            conn.execute(
                """
                INSERT INTO series_bibles
                (id, script_id, title, description, created_by, bible_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (bible_id, script_id, title, description, created_by, bible_type),
            )

        logger.info(f"Created series bible {bible_id} for script {script_id}")
        return bible_id

    def get_series_bible(self, bible_id: str) -> SeriesBible | None:
        """Get a series bible by ID.

        Args:
            bible_id: Bible identifier

        Returns:
            SeriesBible instance or None if not found
        """
        row = self.connection.fetch_one(
            "SELECT * FROM series_bibles WHERE id = ?", (bible_id,)
        )
        if not row:
            return None

        return SeriesBible(
            id=UUID(row["id"]),
            script_id=UUID(row["script_id"]),
            title=row["title"],
            description=row["description"],
            version=row["version"],
            created_by=row["created_by"],
            status=row["status"],
            bible_type=row["bible_type"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_series_bibles_for_script(self, script_id: str) -> list[SeriesBible]:
        """Get all series bibles for a script.

        Args:
            script_id: Script identifier

        Returns:
            List of SeriesBible instances
        """
        rows = self.connection.fetch_all(
            "SELECT * FROM series_bibles WHERE script_id = ? ORDER BY created_at",
            (script_id,),
        )

        bibles = []
        for row in rows:
            bible = SeriesBible(
                id=UUID(row["id"]),
                script_id=UUID(row["script_id"]),
                title=row["title"],
                description=row["description"],
                version=row["version"],
                created_by=row["created_by"],
                status=row["status"],
                bible_type=row["bible_type"],
                metadata=(
                    json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                ),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            bibles.append(bible)

        return bibles

    def update_series_bible(
        self,
        bible_id: str,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        version: int | None = None,
    ) -> bool:
        """Update a series bible.

        Args:
            bible_id: Bible identifier
            title: New title
            description: New description
            status: New status
            version: New version

        Returns:
            True if bible was updated
        """
        updates: list[str] = []
        params: list[Any] = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)

        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if version is not None:
            updates.append("version = ?")
            params.append(version)

        if not updates:
            return False

        params.append(bible_id)
        sql = f"UPDATE series_bibles SET {', '.join(updates)} WHERE id = ?"

        with self.connection.transaction() as conn:
            cursor = conn.execute(sql, params)
            updated = cursor.rowcount > 0

        if updated:
            logger.info(f"Updated series bible {bible_id}")

        return updated

    # Character Profile operations
    def create_character_profile(
        self,
        character_id: str,
        script_id: str,
        series_bible_id: str | None = None,
        _conn: Any = None,
        **profile_data: Any,
    ) -> str:
        """Create a character profile.

        Args:
            character_id: Character identifier
            script_id: Script identifier
            series_bible_id: Optional bible identifier
            _conn: Optional connection to reuse (for internal use)
            **profile_data: Profile data fields

        Returns:
            Profile ID
        """
        profile_id = str(uuid4())

        # Build the insert query dynamically based on provided fields
        base_fields = ["id", "character_id", "script_id"]
        base_values = [profile_id, character_id, script_id]

        if series_bible_id:
            base_fields.append("series_bible_id")
            base_values.append(series_bible_id)

        # Map profile_data keys to database columns
        field_mapping = {
            "full_name": "full_name",
            "age": "age",
            "occupation": "occupation",
            "background": "background",
            "personality_traits": "personality_traits",
            "motivations": "motivations",
            "fears": "fears",
            "goals": "goals",
            "physical_description": "physical_description",
            "distinguishing_features": "distinguishing_features",
            "family_background": "family_background",
            "relationship_status": "relationship_status",
            "initial_state": "initial_state",
            "character_arc": "character_arc",
            "growth_trajectory": "growth_trajectory",
            "notes": "notes",
            "first_appearance_episode_id": "first_appearance_episode_id",
            "last_appearance_episode_id": "last_appearance_episode_id",
            "total_appearances": "total_appearances",
        }

        for key, db_field in field_mapping.items():
            if key in profile_data:
                base_fields.append(db_field)
                base_values.append(profile_data[key])

        placeholders = ", ".join(["?"] * len(base_fields))
        sql = (
            f"INSERT INTO character_profiles ({', '.join(base_fields)}) "
            f"VALUES ({placeholders})"
        )

        if _conn:
            # Use existing connection (no new transaction)
            _conn.execute(sql, base_values)
        else:
            # Create new transaction
            with self.connection.transaction() as conn:
                conn.execute(sql, base_values)

        logger.info(
            f"Created character profile {profile_id} for character {character_id}"
        )
        return profile_id

    def get_character_profile(
        self, character_id: str, script_id: str
    ) -> CharacterProfile | None:
        """Get character profile by character and script ID.

        Args:
            character_id: Character identifier
            script_id: Script identifier

        Returns:
            CharacterProfile instance or None if not found
        """
        row = self.connection.fetch_one(
            "SELECT * FROM character_profiles WHERE character_id = ? AND script_id = ?",
            (character_id, script_id),
        )
        if not row:
            return None

        return self._character_profile_from_row(row)

    def update_character_appearances(
        self, character_id: str, script_id: str, episode_id: str
    ) -> None:
        """Update character appearance tracking.

        Args:
            character_id: Character identifier
            script_id: Script identifier
            episode_id: Episode identifier
        """
        with self.connection.transaction() as conn:
            # Check if profile exists
            existing = conn.execute(
                "SELECT id, first_appearance_episode_id, total_appearances "
                "FROM character_profiles WHERE character_id = ? AND script_id = ?",
                (character_id, script_id),
            ).fetchone()

            if existing:
                # Update existing profile
                updates = [
                    "last_appearance_episode_id = ?",
                    "total_appearances = total_appearances + 1",
                ]
                params = [episode_id]

                # Set first appearance if not set
                if not existing["first_appearance_episode_id"]:
                    updates.append("first_appearance_episode_id = ?")
                    params.append(episode_id)

                params.append(existing["id"])
                sql = f"UPDATE character_profiles SET {', '.join(updates)} WHERE id = ?"
                conn.execute(sql, params)
            else:
                # Create minimal profile if none exists
                self.create_character_profile(
                    character_id=character_id,
                    script_id=script_id,
                    _conn=conn,
                    first_appearance_episode_id=episode_id,
                    last_appearance_episode_id=episode_id,
                    total_appearances=1,
                )

    # World Element operations
    def create_world_element(
        self,
        script_id: str,
        element_type: str,
        name: str,
        **element_data: Any,
    ) -> str:
        """Create a world element.

        Args:
            script_id: Script identifier
            element_type: Type of element
            name: Element name
            **element_data: Additional element data

        Returns:
            Element ID
        """
        element_id = str(uuid4())

        # Convert list fields to JSON
        related_locations = json.dumps(element_data.get("related_locations", []))
        related_characters = json.dumps(element_data.get("related_characters", []))
        established_rules = json.dumps(element_data.get("established_rules", {}))

        with self.connection.transaction() as conn:
            conn.execute(
                """
                INSERT INTO world_elements
                (id, script_id, series_bible_id, element_type, name, category,
                 description, rules_and_constraints, visual_description,
                 first_introduced_episode_id, first_introduced_scene_id,
                 importance_level, related_locations_json, related_characters_json,
                 continuity_notes, established_rules_json, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    element_id,
                    script_id,
                    element_data.get("series_bible_id"),
                    element_type,
                    name,
                    element_data.get("category"),
                    element_data.get("description"),
                    element_data.get("rules_and_constraints"),
                    element_data.get("visual_description"),
                    element_data.get("first_introduced_episode_id"),
                    element_data.get("first_introduced_scene_id"),
                    element_data.get("importance_level", 1),
                    related_locations,
                    related_characters,
                    element_data.get("continuity_notes"),
                    established_rules,
                    element_data.get("notes"),
                ),
            )

        logger.info(f"Created world element {element_id}: {name}")
        return element_id

    def get_world_elements_by_type(
        self, script_id: str, element_type: str | None = None
    ) -> list[WorldElement]:
        """Get world elements by type.

        Args:
            script_id: Script identifier
            element_type: Optional element type filter

        Returns:
            List of WorldElement instances
        """
        if element_type:
            rows = self.connection.fetch_all(
                "SELECT * FROM world_elements WHERE script_id = ? AND element_type = ? "
                "ORDER BY importance_level DESC, name",
                (script_id, element_type),
            )
        else:
            rows = self.connection.fetch_all(
                "SELECT * FROM world_elements WHERE script_id = ? "
                "ORDER BY element_type, importance_level DESC, name",
                (script_id,),
            )

        return [self._world_element_from_row(row) for row in rows]

    # Story Timeline operations
    def create_story_timeline(
        self,
        script_id: str,
        name: str,
        timeline_type: str = "main",
        **timeline_data: Any,
    ) -> str:
        """Create a story timeline.

        Args:
            script_id: Script identifier
            name: Timeline name
            timeline_type: Type of timeline
            **timeline_data: Additional timeline data

        Returns:
            Timeline ID
        """
        timeline_id = str(uuid4())

        # Convert list fields to JSON
        reference_episodes = json.dumps(timeline_data.get("reference_episodes", []))
        reference_scenes = json.dumps(timeline_data.get("reference_scenes", []))

        with self.connection.transaction() as conn:
            conn.execute(
                """
                INSERT INTO story_timelines
                (id, script_id, series_bible_id, name, timeline_type, description,
                 start_date, end_date, duration_description,
                 reference_episodes_json, reference_scenes_json, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timeline_id,
                    script_id,
                    timeline_data.get("series_bible_id"),
                    name,
                    timeline_type,
                    timeline_data.get("description"),
                    timeline_data.get("start_date"),
                    timeline_data.get("end_date"),
                    timeline_data.get("duration_description"),
                    reference_episodes,
                    reference_scenes,
                    timeline_data.get("notes"),
                ),
            )

        logger.info(f"Created story timeline {timeline_id}: {name}")
        return timeline_id

    def add_timeline_event(
        self,
        timeline_id: str,
        script_id: str,
        event_name: str,
        **event_data: Any,
    ) -> str:
        """Add an event to a timeline.

        Args:
            timeline_id: Timeline identifier
            script_id: Script identifier
            event_name: Event name
            **event_data: Additional event data

        Returns:
            Event ID
        """
        event_id = str(uuid4())

        # Convert list fields to JSON
        related_characters = json.dumps(event_data.get("related_characters", []))
        establishes = json.dumps(event_data.get("establishes", []))
        requires = json.dumps(event_data.get("requires", []))
        affects = json.dumps(event_data.get("affects", []))

        with self.connection.transaction() as conn:
            conn.execute(
                """
                INSERT INTO timeline_events
                (id, timeline_id, script_id, event_name, event_type, description,
                 story_date, relative_order, duration_minutes, scene_id, episode_id,
                 related_characters_json, establishes_json, requires_json,
                 affects_json, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    timeline_id,
                    script_id,
                    event_name,
                    event_data.get("event_type", "plot"),
                    event_data.get("description"),
                    event_data.get("story_date"),
                    event_data.get("relative_order"),
                    event_data.get("duration_minutes"),
                    event_data.get("scene_id"),
                    event_data.get("episode_id"),
                    related_characters,
                    establishes,
                    requires,
                    affects,
                    event_data.get("notes"),
                ),
            )

        logger.info(f"Added timeline event {event_id}: {event_name}")
        return event_id

    def get_timeline_events(self, timeline_id: str) -> list[TimelineEvent]:
        """Get events for a timeline.

        Args:
            timeline_id: Timeline identifier

        Returns:
            List of TimelineEvent instances ordered by relative_order
        """
        rows = self.connection.fetch_all(
            "SELECT * FROM timeline_events WHERE timeline_id = ? "
            "ORDER BY relative_order, created_at",
            (timeline_id,),
        )

        return [self._timeline_event_from_row(row) for row in rows]

    # Continuity Note operations
    def create_continuity_note(
        self,
        script_id: str,
        note_type: str,
        title: str,
        description: str,
        **note_data: Any,
    ) -> str:
        """Create a continuity note.

        Args:
            script_id: Script identifier
            note_type: Type of note
            title: Note title
            description: Note description
            **note_data: Additional note data

        Returns:
            Note ID
        """
        note_id = str(uuid4())

        # Convert list fields to JSON
        related_episodes = json.dumps(note_data.get("related_episodes", []))
        related_scenes = json.dumps(note_data.get("related_scenes", []))
        related_characters = json.dumps(note_data.get("related_characters", []))
        tags = json.dumps(note_data.get("tags", []))

        with self.connection.transaction() as conn:
            conn.execute(
                """
                INSERT INTO continuity_notes
                (id, script_id, series_bible_id, note_type, severity, status, title,
                 description, suggested_resolution, episode_id, scene_id,
                 character_id, world_element_id,
                 timeline_event_id, related_episodes_json, related_scenes_json,
                 related_characters_json, reported_by, assigned_to, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note_id,
                    script_id,
                    note_data.get("series_bible_id"),
                    note_type,
                    note_data.get("severity", "medium"),
                    note_data.get("status", "open"),
                    title,
                    description,
                    note_data.get("suggested_resolution"),
                    note_data.get("episode_id"),
                    note_data.get("scene_id"),
                    note_data.get("character_id"),
                    note_data.get("world_element_id"),
                    note_data.get("timeline_event_id"),
                    related_episodes,
                    related_scenes,
                    related_characters,
                    note_data.get("reported_by"),
                    note_data.get("assigned_to"),
                    tags,
                ),
            )

        logger.info(f"Created continuity note {note_id}: {title}")
        return note_id

    def get_continuity_notes(
        self,
        script_id: str,
        status: str | None = None,
        note_type: str | None = None,
        severity: str | None = None,
    ) -> list[ContinuityNote]:
        """Get continuity notes with optional filters.

        Args:
            script_id: Script identifier
            status: Optional status filter
            note_type: Optional type filter
            severity: Optional severity filter

        Returns:
            List of ContinuityNote instances
        """
        conditions = ["script_id = ?"]
        params = [script_id]

        if status:
            conditions.append("status = ?")
            params.append(status)

        if note_type:
            conditions.append("note_type = ?")
            params.append(note_type)

        if severity:
            conditions.append("severity = ?")
            params.append(severity)

        where_clause = " AND ".join(conditions)
        sql = (
            f"SELECT * FROM continuity_notes WHERE {where_clause} "
            f"ORDER BY severity DESC, created_at DESC"
        )

        rows = self.connection.fetch_all(sql, tuple(params))
        return [self._continuity_note_from_row(row) for row in rows]

    def resolve_continuity_note(
        self, note_id: str, resolution_notes: str, resolved_by: str | None = None
    ) -> bool:
        """Resolve a continuity note.

        Args:
            note_id: Note identifier
            resolution_notes: Resolution description
            resolved_by: Person who resolved the note

        Returns:
            True if note was resolved
        """
        with self.connection.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE continuity_notes
                SET status = 'resolved', resolution_notes = ?, resolved_at = ?,
                    assigned_to = COALESCE(?, assigned_to)
                WHERE id = ?
                """,
                (resolution_notes, datetime.now(UTC).isoformat(), resolved_by, note_id),
            )
            updated = cursor.rowcount > 0

        if updated:
            logger.info(f"Resolved continuity note {note_id}")

        return updated

    # Character Knowledge operations
    def add_character_knowledge(
        self,
        character_id: str,
        script_id: str,
        knowledge_type: str,
        knowledge_subject: str,
        **knowledge_data: Any,
    ) -> str:
        """Add character knowledge entry.

        Args:
            character_id: Character identifier
            script_id: Script identifier
            knowledge_type: Type of knowledge
            knowledge_subject: What the knowledge is about
            **knowledge_data: Additional knowledge data

        Returns:
            Knowledge ID
        """
        knowledge_id = str(uuid4())

        with self.connection.transaction() as conn:
            conn.execute(
                """
                INSERT INTO character_knowledge
                (id, character_id, script_id, knowledge_type, knowledge_subject,
                 knowledge_description, acquired_episode_id, acquired_scene_id,
                 acquisition_method, confidence_level, notes, first_used_episode_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    knowledge_id,
                    character_id,
                    script_id,
                    knowledge_type,
                    knowledge_subject,
                    knowledge_data.get("knowledge_description"),
                    knowledge_data.get("acquired_episode_id"),
                    knowledge_data.get("acquired_scene_id"),
                    knowledge_data.get("acquisition_method"),
                    knowledge_data.get("confidence_level", 1.0),
                    knowledge_data.get("notes"),
                    knowledge_data.get("first_used_episode_id"),
                ),
            )

        logger.info(f"Added knowledge {knowledge_id} for character {character_id}")
        return knowledge_id

    def get_character_knowledge(
        self, character_id: str, script_id: str
    ) -> list[CharacterKnowledge]:
        """Get all knowledge for a character.

        Args:
            character_id: Character identifier
            script_id: Script identifier

        Returns:
            List of CharacterKnowledge instances
        """
        rows = self.connection.fetch_all(
            "SELECT * FROM character_knowledge "
            "WHERE character_id = ? AND script_id = ? "
            "ORDER BY acquired_episode_id, created_at",
            (character_id, script_id),
        )

        return [self._character_knowledge_from_row(row) for row in rows]

    # Plot Thread operations
    def create_plot_thread(
        self,
        script_id: str,
        name: str,
        thread_type: str = "main",
        **thread_data: Any,
    ) -> str:
        """Create a plot thread.

        Args:
            script_id: Script identifier
            name: Thread name
            thread_type: Type of thread
            **thread_data: Additional thread data

        Returns:
            Thread ID
        """
        thread_id = str(uuid4())

        # Convert list fields to JSON
        primary_characters = json.dumps(thread_data.get("primary_characters", []))
        supporting_characters = json.dumps(thread_data.get("supporting_characters", []))
        key_scenes = json.dumps(thread_data.get("key_scenes", []))
        resolution_scenes = json.dumps(thread_data.get("resolution_scenes", []))

        with self.connection.transaction() as conn:
            conn.execute(
                """
                INSERT INTO plot_threads
                (id, script_id, series_bible_id, name, thread_type, priority,
                 description, initial_setup, central_conflict, resolution, status,
                 introduced_episode_id, resolved_episode_id,
                 primary_characters_json, supporting_characters_json,
                 key_scenes_json, resolution_scenes_json, notes,
                total_episodes_involved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread_id,
                    script_id,
                    thread_data.get("series_bible_id"),
                    name,
                    thread_type,
                    thread_data.get("priority", 1),
                    thread_data.get("description"),
                    thread_data.get("initial_setup"),
                    thread_data.get("central_conflict"),
                    thread_data.get("resolution"),
                    thread_data.get("status", "active"),
                    thread_data.get("introduced_episode_id"),
                    thread_data.get("resolved_episode_id"),
                    primary_characters,
                    supporting_characters,
                    key_scenes,
                    resolution_scenes,
                    thread_data.get("notes"),
                    thread_data.get("total_episodes_involved", 0),
                ),
            )

        logger.info(f"Created plot thread {thread_id}: {name}")
        return thread_id

    def get_plot_threads(
        self, script_id: str, status: str | None = None
    ) -> list[PlotThread]:
        """Get plot threads for a script.

        Args:
            script_id: Script identifier
            status: Optional status filter

        Returns:
            List of PlotThread instances
        """
        if status:
            rows = self.connection.fetch_all(
                "SELECT * FROM plot_threads WHERE script_id = ? AND status = ? "
                "ORDER BY priority DESC, created_at",
                (script_id, status),
            )
        else:
            rows = self.connection.fetch_all(
                "SELECT * FROM plot_threads WHERE script_id = ? "
                "ORDER BY priority DESC, created_at",
                (script_id,),
            )

        return [self._plot_thread_from_row(row) for row in rows]

    # Helper methods for converting database rows to model instances
    def _character_profile_from_row(self, row: Any) -> CharacterProfile:
        """Convert database row to CharacterProfile instance."""
        return CharacterProfile(
            id=UUID(row["id"]),
            character_id=UUID(row["character_id"]),
            script_id=UUID(row["script_id"]),
            series_bible_id=(
                UUID(row["series_bible_id"]) if row["series_bible_id"] else None
            ),
            full_name=row["full_name"],
            age=row["age"],
            occupation=row["occupation"],
            background=row["background"],
            personality_traits=row["personality_traits"],
            motivations=row["motivations"],
            fears=row["fears"],
            goals=row["goals"],
            physical_description=row["physical_description"],
            distinguishing_features=row["distinguishing_features"],
            family_background=row["family_background"],
            relationship_status=row["relationship_status"],
            initial_state=row["initial_state"],
            character_arc=row["character_arc"],
            growth_trajectory=row["growth_trajectory"],
            first_appearance_episode_id=(
                UUID(row["first_appearance_episode_id"])
                if row["first_appearance_episode_id"]
                else None
            ),
            last_appearance_episode_id=(
                UUID(row["last_appearance_episode_id"])
                if row["last_appearance_episode_id"]
                else None
            ),
            total_appearances=row["total_appearances"],
            notes=row["notes"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _world_element_from_row(self, row: Any) -> WorldElement:
        """Convert database row to WorldElement instance."""
        return WorldElement(
            id=UUID(row["id"]),
            script_id=UUID(row["script_id"]),
            series_bible_id=(
                UUID(row["series_bible_id"]) if row["series_bible_id"] else None
            ),
            element_type=row["element_type"],
            name=row["name"],
            category=row["category"],
            description=row["description"],
            rules_and_constraints=row["rules_and_constraints"],
            visual_description=row["visual_description"],
            first_introduced_episode_id=(
                UUID(row["first_introduced_episode_id"])
                if row["first_introduced_episode_id"]
                else None
            ),
            first_introduced_scene_id=(
                UUID(row["first_introduced_scene_id"])
                if row["first_introduced_scene_id"]
                else None
            ),
            usage_frequency=row["usage_frequency"],
            importance_level=row["importance_level"],
            related_locations=(
                [UUID(item_id) for item_id in json.loads(row["related_locations_json"])]
                if row["related_locations_json"]
                else []
            ),
            related_characters=(
                [
                    UUID(item_id)
                    for item_id in json.loads(row["related_characters_json"])
                ]
                if row["related_characters_json"]
                else []
            ),
            continuity_notes=row["continuity_notes"],
            established_rules=(
                json.loads(row["established_rules_json"])
                if row["established_rules_json"]
                else {}
            ),
            notes=row["notes"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _timeline_event_from_row(self, row: Any) -> TimelineEvent:
        """Convert database row to TimelineEvent instance."""
        return TimelineEvent(
            id=UUID(row["id"]),
            timeline_id=UUID(row["timeline_id"]),
            script_id=UUID(row["script_id"]),
            event_name=row["event_name"],
            event_type=row["event_type"],
            description=row["description"],
            story_date=row["story_date"],
            relative_order=row["relative_order"],
            duration_minutes=row["duration_minutes"],
            scene_id=UUID(row["scene_id"]) if row["scene_id"] else None,
            episode_id=UUID(row["episode_id"]) if row["episode_id"] else None,
            related_characters=(
                [
                    UUID(item_id)
                    for item_id in json.loads(row["related_characters_json"])
                ]
                if row["related_characters_json"]
                else []
            ),
            establishes=(
                json.loads(row["establishes_json"]) if row["establishes_json"] else []
            ),
            requires=json.loads(row["requires_json"]) if row["requires_json"] else [],
            affects=json.loads(row["affects_json"]) if row["affects_json"] else [],
            notes=row["notes"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _continuity_note_from_row(self, row: Any) -> ContinuityNote:
        """Convert database row to ContinuityNote instance."""
        return ContinuityNote(
            id=UUID(row["id"]),
            script_id=UUID(row["script_id"]),
            series_bible_id=(
                UUID(row["series_bible_id"]) if row["series_bible_id"] else None
            ),
            note_type=row["note_type"],
            severity=row["severity"],
            status=row["status"],
            title=row["title"],
            description=row["description"],
            suggested_resolution=row["suggested_resolution"],
            episode_id=UUID(row["episode_id"]) if row["episode_id"] else None,
            scene_id=UUID(row["scene_id"]) if row["scene_id"] else None,
            character_id=UUID(row["character_id"]) if row["character_id"] else None,
            world_element_id=(
                UUID(row["world_element_id"]) if row["world_element_id"] else None
            ),
            timeline_event_id=(
                UUID(row["timeline_event_id"]) if row["timeline_event_id"] else None
            ),
            related_episodes=(
                [UUID(item_id) for item_id in json.loads(row["related_episodes_json"])]
                if row["related_episodes_json"]
                else []
            ),
            related_scenes=(
                [UUID(item_id) for item_id in json.loads(row["related_scenes_json"])]
                if row["related_scenes_json"]
                else []
            ),
            related_characters=(
                [
                    UUID(item_id)
                    for item_id in json.loads(row["related_characters_json"])
                ]
                if row["related_characters_json"]
                else []
            ),
            reported_by=row["reported_by"],
            assigned_to=row["assigned_to"],
            resolution_notes=row["resolution_notes"],
            resolved_at=(
                datetime.fromisoformat(row["resolved_at"])
                if row["resolved_at"]
                else None
            ),
            tags=json.loads(row["tags_json"]) if row["tags_json"] else [],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _character_knowledge_from_row(self, row: Any) -> CharacterKnowledge:
        """Convert database row to CharacterKnowledge instance."""
        return CharacterKnowledge(
            id=UUID(row["id"]),
            character_id=UUID(row["character_id"]),
            script_id=UUID(row["script_id"]),
            knowledge_type=row["knowledge_type"],
            knowledge_subject=row["knowledge_subject"],
            knowledge_description=row["knowledge_description"],
            acquired_episode_id=(
                UUID(row["acquired_episode_id"]) if row["acquired_episode_id"] else None
            ),
            acquired_scene_id=(
                UUID(row["acquired_scene_id"]) if row["acquired_scene_id"] else None
            ),
            acquisition_method=row["acquisition_method"],
            first_used_episode_id=(
                UUID(row["first_used_episode_id"])
                if row["first_used_episode_id"]
                else None
            ),
            first_used_scene_id=(
                UUID(row["first_used_scene_id"]) if row["first_used_scene_id"] else None
            ),
            usage_count=row["usage_count"],
            should_know_before=row["should_know_before"],
            verification_status=row["verification_status"],
            confidence_level=row["confidence_level"],
            notes=row["notes"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _plot_thread_from_row(self, row: Any) -> PlotThread:
        """Convert database row to PlotThread instance."""
        return PlotThread(
            id=UUID(row["id"]),
            script_id=UUID(row["script_id"]),
            series_bible_id=(
                UUID(row["series_bible_id"]) if row["series_bible_id"] else None
            ),
            name=row["name"],
            thread_type=row["thread_type"],
            priority=row["priority"],
            description=row["description"],
            initial_setup=row["initial_setup"],
            central_conflict=row["central_conflict"],
            resolution=row["resolution"],
            status=row["status"],
            introduced_episode_id=(
                UUID(row["introduced_episode_id"])
                if row["introduced_episode_id"]
                else None
            ),
            resolved_episode_id=(
                UUID(row["resolved_episode_id"]) if row["resolved_episode_id"] else None
            ),
            total_episodes_involved=row["total_episodes_involved"],
            primary_characters=(
                [
                    UUID(item_id)
                    for item_id in json.loads(row["primary_characters_json"])
                ]
                if row["primary_characters_json"]
                else []
            ),
            supporting_characters=(
                [
                    UUID(item_id)
                    for item_id in json.loads(row["supporting_characters_json"])
                ]
                if row["supporting_characters_json"]
                else []
            ),
            key_scenes=(
                [UUID(item_id) for item_id in json.loads(row["key_scenes_json"])]
                if row["key_scenes_json"]
                else []
            ),
            resolution_scenes=(
                [UUID(item_id) for item_id in json.loads(row["resolution_scenes_json"])]
                if row["resolution_scenes_json"]
                else []
            ),
            notes=row["notes"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

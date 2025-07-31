"""Continuity validation and analysis for Script Bible management.

This module provides automated continuity checking for character knowledge,
timeline consistency, plot thread resolution, and cross-episode validation.
"""

from datetime import UTC, datetime
from typing import Any

from scriptrag.config import get_logger
from scriptrag.models import (
    ContinuityNote,
    NoteStatus,
    VerificationStatus,
)

from .bible import ScriptBibleOperations
from .connection import DatabaseConnection

logger = get_logger(__name__)


class ContinuityIssue:
    """Represents a continuity issue found during validation."""

    def __init__(
        self,
        issue_type: str,
        severity: str,
        title: str,
        description: str,
        episode_id: str | None = None,
        scene_id: str | None = None,
        character_id: str | None = None,
        **metadata: Any,
    ) -> None:
        """Initialize a continuity issue."""
        self.issue_type = issue_type
        self.severity = severity
        self.title = title
        self.description = description
        self.episode_id = episode_id
        self.scene_id = scene_id
        self.character_id = character_id
        self.metadata = metadata


class ContinuityValidator:
    """Automated continuity validation for screenplays and series."""

    def __init__(self, connection: DatabaseConnection) -> None:
        """Initialize continuity validator.

        Args:
            connection: Database connection instance
        """
        self.connection = connection
        self.bible_ops = ScriptBibleOperations(connection)

    def validate_script_continuity(self, script_id: str) -> list[ContinuityIssue]:
        """Perform comprehensive continuity validation for a script.

        Args:
            script_id: Script identifier

        Returns:
            List of continuity issues found
        """
        issues: list[ContinuityIssue] = []

        logger.info(f"Starting continuity validation for script {script_id}")

        # Character knowledge validation
        issues.extend(self._validate_character_knowledge(script_id))

        # Timeline consistency validation
        issues.extend(self._validate_timeline_consistency(script_id))

        # Plot thread validation
        issues.extend(self._validate_plot_threads(script_id))

        # Character arc validation
        issues.extend(self._validate_character_arcs(script_id))

        # World element consistency validation
        issues.extend(self._validate_world_elements(script_id))

        # Cross-episode validation (for series)
        if self._is_series(script_id):
            issues.extend(self._validate_cross_episode_consistency(script_id))

        logger.info(f"Found {len(issues)} continuity issues for script {script_id}")
        return issues

    def _validate_character_knowledge(self, script_id: str) -> list[ContinuityIssue]:
        """Validate character knowledge consistency.

        Args:
            script_id: Script identifier

        Returns:
            List of knowledge-related continuity issues
        """
        issues: list[ContinuityIssue] = []

        # Get all character knowledge entries
        knowledge_rows = self.connection.fetch_all(
            """
            SELECT ck.*, c.name as character_name,
                   e1.number as acquired_episode, e2.number as used_episode
            FROM character_knowledge ck
            JOIN characters c ON ck.character_id = c.id
            LEFT JOIN episodes e1 ON ck.acquired_episode_id = e1.id
            LEFT JOIN episodes e2 ON ck.first_used_episode_id = e2.id
            WHERE ck.script_id = ?
            ORDER BY c.name, ck.acquired_episode_id
            """,
            (script_id,),
        )

        # Group knowledge by character
        character_knowledge: dict[str, list[Any]] = {}
        for row in knowledge_rows:
            char_id = row["character_id"]
            if char_id not in character_knowledge:
                character_knowledge[char_id] = []
            character_knowledge[char_id].append(row)

        # Validate each character's knowledge
        for char_id, knowledge_list in character_knowledge.items():
            char_name = (
                knowledge_list[0]["character_name"] if knowledge_list else "Unknown"
            )

            # Check for knowledge used before acquisition
            for knowledge in knowledge_list:
                if (
                    knowledge["acquired_episode"]
                    and knowledge["used_episode"]
                    and knowledge["used_episode"] < knowledge["acquired_episode"]
                ):
                    issues.append(
                        ContinuityIssue(
                            issue_type="knowledge_temporal_violation",
                            severity="high",
                            title=f"{char_name} uses knowledge before acquiring it",
                            description=(
                                f"Character uses '{knowledge['knowledge_subject']}' "
                                f"in episode {knowledge['used_episode']} but doesn't "
                                f"acquire it until episode "
                                f"{knowledge['acquired_episode']}"
                            ),
                            character_id=char_id,
                            episode_id=knowledge["first_used_episode_id"],
                            knowledge_id=knowledge["id"],
                        )
                    )

            # Check for contradictory knowledge
            subjects: dict[str, Any] = {}
            for knowledge in knowledge_list:
                subject = knowledge["knowledge_subject"]
                if subject in subjects:
                    # Check if descriptions conflict
                    existing = subjects[subject]
                    if (
                        existing["knowledge_description"]
                        and knowledge["knowledge_description"]
                        and existing["knowledge_description"]
                        != knowledge["knowledge_description"]
                    ):
                        issues.append(
                            ContinuityIssue(
                                issue_type="knowledge_contradiction",
                                severity="medium",
                                title=(
                                    f"{char_name} has contradictory knowledge "
                                    f"about {subject}"
                                ),
                                description=f"Character has conflicting information: "
                                f"'{existing['knowledge_description']}' vs "
                                f"'{knowledge['knowledge_description']}'",
                                character_id=char_id,
                            )
                        )
                else:
                    subjects[subject] = knowledge

        return issues

    def _validate_timeline_consistency(self, script_id: str) -> list[ContinuityIssue]:
        """Validate timeline and chronological consistency.

        Args:
            script_id: Script identifier

        Returns:
            List of timeline-related continuity issues
        """
        issues: list[ContinuityIssue] = []

        # Get all timeline events with episode information
        events_rows = self.connection.fetch_all(
            """
            SELECT te.*, st.name as timeline_name, e.number as episode_number
            FROM timeline_events te
            JOIN story_timelines st ON te.timeline_id = st.id
            LEFT JOIN episodes e ON te.episode_id = e.id
            WHERE te.script_id = ?
            ORDER BY st.id, te.relative_order
            """,
            (script_id,),
        )

        # Group events by timeline
        timeline_events: dict[str, list[Any]] = {}
        for row in events_rows:
            timeline_id = row["timeline_id"]
            if timeline_id not in timeline_events:
                timeline_events[timeline_id] = []
            timeline_events[timeline_id].append(row)

        # Validate each timeline
        for timeline_id, events in timeline_events.items():
            if not events:
                continue

            timeline_name = events[0]["timeline_name"]

            # Check for temporal ordering issues
            prev_event = None
            for event in events:
                if prev_event:
                    # Check if episode numbers are consistent with timeline order
                    if (
                        event["episode_number"]
                        and prev_event["episode_number"]
                        and event["episode_number"] < prev_event["episode_number"]
                    ):
                        issues.append(
                            ContinuityIssue(
                                issue_type="timeline_episode_order",
                                severity="medium",
                                title=(
                                    f"Episode order inconsistent with timeline "
                                    f"in {timeline_name}"
                                ),
                                description=(
                                    f"Event '{event['event_name']}' occurs in episode "
                                    f"{event['episode_number']} but follows "
                                    f"'{prev_event['event_name']}' from episode "
                                    f"{prev_event['episode_number']}"
                                ),
                                timeline_id=timeline_id,
                                episode_id=event["episode_id"],
                            )
                        )

                    # Check story date consistency if available
                    # Basic date comparison
                    # (needs sophisticated parsing for complex dates)
                    if (
                        event["story_date"]
                        and prev_event["story_date"]
                        and event["story_date"] < prev_event["story_date"]
                    ):
                        issues.append(
                            ContinuityIssue(
                                issue_type="timeline_date_order",
                                severity="medium",
                                title=(
                                    f"Story date inconsistent with timeline order "
                                    f"in {timeline_name}"
                                ),
                                description=(
                                    f"Event '{event['event_name']}' has story date "
                                    f"'{event['story_date']}' but follows "
                                    f"'{prev_event['event_name']}' "
                                    f"with date '{prev_event['story_date']}'"
                                ),
                                timeline_id=timeline_id,
                                episode_id=event["episode_id"],
                            )
                        )

                prev_event = event

        return issues

    def _validate_plot_threads(self, script_id: str) -> list[ContinuityIssue]:
        """Validate plot thread consistency and resolution.

        Args:
            script_id: Script identifier

        Returns:
            List of plot thread-related continuity issues
        """
        issues: list[ContinuityIssue] = []

        # Get all plot threads
        threads = self.bible_ops.get_plot_threads(script_id)

        for thread in threads:
            # Check for unresolved high-priority threads
            # Check if thread has been running for many episodes without progress
            if (
                thread.status == "active"
                and thread.priority >= 4
                and thread.introduced_episode_id
                and thread.total_episodes_involved > 10
                and not thread.resolved_episode_id
            ):
                issues.append(
                    ContinuityIssue(
                        issue_type="plot_thread_stagnant",
                        severity="medium",
                        title=(
                            f"High-priority plot thread '{thread.name}' "
                            f"lacks resolution"
                        ),
                        description=(
                            f"Thread has been active for "
                            f"{thread.total_episodes_involved} "
                            f"episodes without resolution"
                        ),
                        plot_thread_id=str(thread.id),
                    )
                )

            # Check for threads marked as resolved but missing resolution description
            if thread.status == "resolved" and not thread.resolution:
                issues.append(
                    ContinuityIssue(
                        issue_type="plot_thread_incomplete_resolution",
                        severity="low",
                        title=(
                            f"Plot thread '{thread.name}' marked resolved "
                            f"but missing resolution details"
                        ),
                        description=(
                            "Thread status is resolved but no resolution "
                            "description provided"
                        ),
                        plot_thread_id=str(thread.id),
                    )
                )

            # Check for abandoned threads without explanation
            if thread.status == "abandoned" and thread.priority >= 3:
                issues.append(
                    ContinuityIssue(
                        issue_type="plot_thread_abandoned",
                        severity="medium",
                        title=(f"Important plot thread '{thread.name}' was abandoned"),
                        description=(
                            f"Priority {thread.priority} thread was abandoned "
                            f"without resolution"
                        ),
                        plot_thread_id=str(thread.id),
                    )
                )

        return issues

    def _validate_character_arcs(self, script_id: str) -> list[ContinuityIssue]:
        """Validate character development and arc consistency.

        Args:
            script_id: Script identifier

        Returns:
            List of character arc-related continuity issues
        """
        issues: list[ContinuityIssue] = []

        # Get character profiles with arc information
        profiles_rows = self.connection.fetch_all(
            """
            SELECT cp.*, c.name as character_name
            FROM character_profiles cp
            JOIN characters c ON cp.character_id = c.id
            WHERE cp.script_id = ?
            AND cp.total_appearances > 5
            """,
            (script_id,),
        )

        for row in profiles_rows:
            char_name = row["character_name"]
            char_id = row["character_id"]

            # Check for characters with many appearances but no defined arc
            if row["total_appearances"] > 10 and not row["character_arc"]:
                issues.append(
                    ContinuityIssue(
                        issue_type="character_arc_missing",
                        severity="low",
                        title=(
                            f"Major character '{char_name}' lacks defined character arc"
                        ),
                        description=(
                            f"Character appears in {row['total_appearances']} "
                            f"episodes "
                            f"but has no defined character arc"
                        ),
                        character_id=char_id,
                    )
                )

            # Check for inconsistent character development
            if (
                row["initial_state"]
                and row["character_arc"]
                and row["growth_trajectory"]
                and "regression" in row["growth_trajectory"].lower()
                and "positive" in row["character_arc"].lower()
            ):
                issues.append(
                    ContinuityIssue(
                        issue_type="character_arc_inconsistent",
                        severity="medium",
                        title=(
                            f"Character '{char_name}' has inconsistent arc and growth"
                        ),
                        description=(
                            "Character arc described as positive but growth "
                            "trajectory indicates regression"
                        ),
                        character_id=char_id,
                    )
                )

        return issues

    def _validate_world_elements(self, script_id: str) -> list[ContinuityIssue]:
        """Validate world building element consistency.

        Args:
            script_id: Script identifier

        Returns:
            List of world element-related continuity issues
        """
        issues: list[ContinuityIssue] = []

        # Get world elements with usage information
        elements = self.bible_ops.get_world_elements_by_type(script_id)

        for element in elements:
            # Check for important elements with low usage
            if element.importance_level >= 4 and element.usage_frequency <= 1:
                issues.append(
                    ContinuityIssue(
                        issue_type="world_element_underused",
                        severity="low",
                        title=(
                            f"Important world element '{element.name}' is underused"
                        ),
                        description=(
                            f"Element marked as importance level "
                            f"{element.importance_level} "
                            f"but only used {element.usage_frequency} times"
                        ),
                        world_element_id=str(element.id),
                    )
                )

            # Check for rule violations in established rules
            if element.established_rules:
                for rule_key, rule_value in element.established_rules.items():
                    if (
                        isinstance(rule_value, dict)
                        and "violated" in rule_value
                        and rule_value["violated"]
                    ):
                        issues.append(
                            ContinuityIssue(
                                issue_type="world_element_rule_violation",
                                severity="high",
                                title=(
                                    f"Rule violation for world element '{element.name}'"
                                ),
                                description=(
                                    f"Rule '{rule_key}' has been violated: "
                                    f"{rule_value.get('description', 'No details')}"
                                ),
                                world_element_id=str(element.id),
                            )
                        )

        return issues

    def _validate_cross_episode_consistency(
        self, script_id: str
    ) -> list[ContinuityIssue]:
        """Validate consistency across episodes in a series.

        Args:
            script_id: Script identifier

        Returns:
            List of cross-episode continuity issues
        """
        issues: list[ContinuityIssue] = []

        # Get episode information
        episodes_rows = self.connection.fetch_all(
            """
            SELECT e.*, s.number as season_number
            FROM episodes e
            LEFT JOIN seasons s ON e.season_id = s.id
            WHERE e.script_id = ?
            ORDER BY s.number, e.number
            """,
            (script_id,),
        )

        if len(episodes_rows) < 2:
            return issues  # Need at least 2 episodes for cross-episode validation

        # Check for character appearance gaps
        char_appearances = self.connection.fetch_all(
            """
            SELECT DISTINCT se.character_id, se.character_name, sc.episode_id,
                   e.number as episode_number, s.number as season_number
            FROM scene_elements se
            JOIN scenes sc ON se.scene_id = sc.id
            JOIN episodes e ON sc.episode_id = e.id
            LEFT JOIN seasons s ON e.season_id = s.id
            WHERE se.script_id = ? AND se.character_id IS NOT NULL
            ORDER BY se.character_id, s.number, e.number
            """,
            (script_id,),
        )

        # Group appearances by character
        character_episodes: dict[str, list[Any]] = {}
        for row in char_appearances:
            char_id = row["character_id"]
            if char_id not in character_episodes:
                character_episodes[char_id] = []
            character_episodes[char_id].append(row)

        # Check for unexplained character absences
        for char_id, appearances in character_episodes.items():
            if len(appearances) < 3:
                continue  # Skip characters with few appearances

            char_name = appearances[0]["character_name"]

            # Check for gaps in appearances
            prev_ep = None
            for appearance in appearances:
                if prev_ep:
                    # Calculate episode gap (simplified - assumes sequential numbering)
                    current_ep = appearance["episode_number"]
                    prev_ep_num = prev_ep["episode_number"]

                    if current_ep - prev_ep_num > 5:  # Gap of more than 5 episodes
                        issues.append(
                            ContinuityIssue(
                                issue_type="character_absence_gap",
                                severity="low",
                                title=(
                                    f"Character '{char_name}' has unexplained absence"
                                ),
                                description=(
                                    f"Character absent from episode {prev_ep_num + 1} "
                                    f"to {current_ep - 1} without explanation"
                                ),
                                character_id=char_id,
                                episode_id=appearance["episode_id"],
                            )
                        )
                prev_ep = appearance

        return issues

    def _is_series(self, script_id: str) -> bool:
        """Check if the script is a series (has multiple episodes).

        Args:
            script_id: Script identifier

        Returns:
            True if script is a series
        """
        row = self.connection.fetch_one(
            "SELECT is_series FROM scripts WHERE id = ?", (script_id,)
        )
        return bool(row["is_series"]) if row else False

    def create_continuity_notes_from_issues(
        self,
        script_id: str,
        issues: list[ContinuityIssue],
        reported_by: str | None = None,
    ) -> list[str]:
        """Create continuity notes from validation issues.

        Args:
            script_id: Script identifier
            issues: List of continuity issues
            reported_by: Person who reported the issues

        Returns:
            List of created note IDs
        """
        note_ids = []

        for issue in issues:
            # Check if a similar note already exists
            existing_notes = self.bible_ops.get_continuity_notes(
                script_id=script_id,
                status="open",
                note_type=self._map_issue_type_to_note_type(issue.issue_type),
            )

            # Skip if similar note exists
            if any(note.title == issue.title for note in existing_notes):
                continue

            note_data = {
                "episode_id": issue.episode_id,
                "scene_id": issue.scene_id,
                "character_id": issue.character_id,
                "reported_by": reported_by or "Continuity Validator",
            }

            # Add issue-specific metadata
            for key, value in issue.metadata.items():
                note_data[key] = value

            note_id = self.bible_ops.create_continuity_note(
                script_id=script_id,
                note_type=self._map_issue_type_to_note_type(issue.issue_type),
                title=issue.title,
                description=issue.description,
                severity=issue.severity,
                **note_data,
            )

            note_ids.append(note_id)

        logger.info(
            f"Created {len(note_ids)} continuity notes from {len(issues)} issues"
        )
        return note_ids

    def _map_issue_type_to_note_type(self, issue_type: str) -> str:
        """Map issue type to continuity note type.

        Args:
            issue_type: Issue type from validation

        Returns:
            Appropriate note type
        """
        mapping = {
            "knowledge_temporal_violation": "error",
            "knowledge_contradiction": "inconsistency",
            "timeline_episode_order": "inconsistency",
            "timeline_date_order": "inconsistency",
            "plot_thread_stagnant": "reminder",
            "plot_thread_incomplete_resolution": "question",
            "plot_thread_abandoned": "reminder",
            "character_arc_missing": "reminder",
            "character_arc_inconsistent": "inconsistency",
            "world_element_underused": "reminder",
            "world_element_rule_violation": "error",
            "character_absence_gap": "question",
        }
        return mapping.get(issue_type, "question")

    def update_knowledge_verification_status(
        self, script_id: str, auto_verify_obvious: bool = True
    ) -> int:
        """Update verification status of character knowledge entries.

        Args:
            script_id: Script identifier
            auto_verify_obvious: Whether to auto-verify obvious knowledge

        Returns:
            Number of knowledge entries updated
        """
        updated_count = 0

        # Get all unverified knowledge
        knowledge_rows = self.connection.fetch_all(
            """
            SELECT ck.*, c.name as character_name
            FROM character_knowledge ck
            JOIN characters c ON ck.character_id = c.id
            WHERE ck.script_id = ? AND ck.verification_status = 'unverified'
            """,
            (script_id,),
        )

        for row in knowledge_rows:
            new_status = VerificationStatus.UNVERIFIED

            # Auto-verify knowledge that is acquired and used in the same episode
            if auto_verify_obvious and (
                (
                    row["acquired_episode_id"]
                    and row["first_used_episode_id"]
                    and row["acquired_episode_id"] == row["first_used_episode_id"]
                )
                or (
                    row["confidence_level"] >= 0.9
                    and row["acquisition_method"] in ["witnessed", "told"]
                )
            ):
                new_status = VerificationStatus.VERIFIED

            # Check for violations (knowledge used before acquisition)
            if (
                row["acquired_episode_id"]
                and row["first_used_episode_id"]
                and row["first_used_episode_id"] < row["acquired_episode_id"]
            ):
                new_status = VerificationStatus.VIOLATED

            if new_status != VerificationStatus.UNVERIFIED:
                with self.connection.transaction() as conn:
                    conn.execute(
                        "UPDATE character_knowledge "
                        "SET verification_status = ? WHERE id = ?",
                        (new_status, row["id"]),
                    )
                updated_count += 1

        logger.info(
            f"Updated verification status for {updated_count} knowledge entries"
        )
        return updated_count

    def generate_continuity_report(self, script_id: str) -> dict[str, Any]:
        """Generate a comprehensive continuity report.

        Args:
            script_id: Script identifier

        Returns:
            Dictionary containing continuity report data
        """
        # Run validation
        issues = self.validate_script_continuity(script_id)

        # Get existing continuity notes
        existing_notes = self.bible_ops.get_continuity_notes(script_id)

        # Categorize issues by type and severity
        issue_stats: dict[str, Any] = {
            "total_issues": len(issues),
            "by_type": {},
            "by_severity": {"low": 0, "medium": 0, "high": 0, "critical": 0},
        }

        for issue in issues:
            # Count by type
            if issue.issue_type not in issue_stats["by_type"]:
                issue_stats["by_type"][issue.issue_type] = 0
            issue_stats["by_type"][issue.issue_type] += 1

            # Count by severity
            if issue.severity in issue_stats["by_severity"]:
                issue_stats["by_severity"][issue.severity] += 1

        # Categorize existing notes
        note_stats: dict[str, Any] = {
            "total_notes": len(existing_notes),
            "by_status": {},
            "by_type": {},
            "by_severity": {"low": 0, "medium": 0, "high": 0, "critical": 0},
        }

        for note in existing_notes:
            # Count by status
            if note.status not in note_stats["by_status"]:
                note_stats["by_status"][note.status] = 0
            note_stats["by_status"][note.status] += 1

            # Count by type
            if note.note_type not in note_stats["by_type"]:
                note_stats["by_type"][note.note_type] = 0
            note_stats["by_type"][note.note_type] += 1

            # Count by severity
            if note.severity in note_stats["by_severity"]:
                note_stats["by_severity"][note.severity] += 1

        # Get script info
        script_row = self.connection.fetch_one(
            "SELECT title, is_series FROM scripts WHERE id = ?", (script_id,)
        )

        return {
            "script_id": script_id,
            "script_title": script_row["title"] if script_row else "Unknown",
            "is_series": bool(script_row["is_series"]) if script_row else False,
            "generated_at": datetime.now(UTC).isoformat(),
            "validation_results": {
                "issues_found": issues,
                "issue_statistics": issue_stats,
            },
            "existing_notes": {
                "notes": existing_notes,
                "note_statistics": note_stats,
            },
            "recommendations": self._generate_recommendations(issues, existing_notes),
        }

    def _generate_recommendations(
        self, issues: list[ContinuityIssue], existing_notes: list[ContinuityNote]
    ) -> list[str]:
        """Generate recommendations based on validation results.

        Args:
            issues: List of found issues
            existing_notes: List of existing continuity notes

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # High severity issue recommendations
        high_severity_issues = [i for i in issues if i.severity == "high"]
        if high_severity_issues:
            recommendations.append(
                f"Address {len(high_severity_issues)} high-severity "
                f"continuity issues immediately"
            )

        # Unresolved note recommendations
        open_notes = [n for n in existing_notes if n.status == NoteStatus.OPEN]
        if len(open_notes) > 10:
            recommendations.append(
                f"Review and resolve {len(open_notes)} open continuity notes"
            )

        # Character arc recommendations
        arc_issues = [i for i in issues if "character_arc" in i.issue_type]
        if arc_issues:
            recommendations.append(
                "Define character arcs for major characters to improve "
                "story consistency"
            )

        # Timeline recommendations
        timeline_issues = [i for i in issues if "timeline" in i.issue_type]
        if timeline_issues:
            recommendations.append(
                "Review timeline ordering and story chronology for consistency"
            )

        # Knowledge tracking recommendations
        knowledge_issues = [i for i in issues if "knowledge" in i.issue_type]
        if knowledge_issues:
            recommendations.append(
                "Implement more rigorous character knowledge tracking"
            )

        if not recommendations:
            recommendations.append("Continuity appears to be well-maintained")

        return recommendations

"""Shared test utilities and fixtures for relationship analyzer tests.

This module provides common test data, fixtures, and helper functions
used across multiple relationship analyzer test files to reduce duplication
and improve maintainability.
"""

import json
from datetime import datetime
from typing import Any
from unittest.mock import Mock

import pytest

from scriptrag.analyzers.relationships import CharacterRelationshipsAnalyzer


class RelationshipTestData:
    """Common test data for relationship analyzer tests."""

    @staticmethod
    def basic_bible_characters() -> dict[str, Any]:
        """Get basic bible characters configuration for testing."""
        return {
            "version": 1,
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "characters": [
                {"canonical": "JANE SMITH", "aliases": ["JANE", "MS. SMITH"]},
                {
                    "canonical": "BOB JOHNSON",
                    "aliases": ["BOB", "BOBBY", "MR. JOHNSON"],
                },
            ],
        }

    @staticmethod
    def collision_bible_characters() -> dict[str, Any]:
        """Get bible characters with canonical name collisions for testing."""
        return {
            "version": 1,
            "characters": [
                {"canonical": "JOHN", "aliases": ["JOHNNY", "J"]},
                {"canonical": "JOHNNY", "aliases": ["JOHNNY BOY", "J-DAWG"]},
                {"canonical": "ROBERT", "aliases": ["BOB", "BOBBY", "ROB"]},
                {"canonical": "BOB", "aliases": ["BOBBY", "B"]},
                {"canonical": "BOBBY", "aliases": ["B-MAN"]},
            ],
        }

    @staticmethod
    def special_chars_bible_characters() -> dict[str, Any]:
        """Get bible characters with special characters for testing."""
        return {
            "version": 1,
            "characters": [
                {"canonical": "MR. SMITH", "aliases": ["SMITH", "MR. S"]},
                {"canonical": "JANE (YOUNG)", "aliases": ["JANE", "YOUNG JANE"]},
                {"canonical": "JOHN-DOE", "aliases": ["JOHN", "DOE", "J-D"]},
            ],
        }

    @staticmethod
    def minimal_bible_characters() -> dict[str, Any]:
        """Get minimal bible characters configuration for testing."""
        return {
            "version": 1,
            "characters": [
                {"canonical": "ALICE", "aliases": ["A"]},
            ],
        }

    @staticmethod
    def empty_bible_characters() -> dict[str, Any]:
        """Get empty bible characters configuration for testing."""
        return {
            "version": 1,
            "characters": [],
        }


class SceneTestData:
    """Common scene data for relationship analyzer tests."""

    @staticmethod
    def basic_scene() -> dict[str, Any]:
        """Get a basic scene for testing."""
        return {
            "heading": "INT. APARTMENT - DAY",
            "dialogue": [
                {"character": "JANE", "text": "Hello, Bob."},
                {"character": "BOB", "text": "Hi Jane!"},
            ],
            "action": [
                "Jane enters the room.",
                "Bob waves from the couch.",
            ],
        }

    @staticmethod
    def scene_with_parentheticals() -> dict[str, Any]:
        """Get a scene with parentheticals in character names."""
        return {
            "heading": "INT. OFFICE - DAY",
            "dialogue": [
                {"character": "JANE (CONT'D)", "text": "We have to go."},
                {"character": "BOB (O.S.)", "text": "I'm on my way."},
            ],
            "action": [
                "Ms. Smith gathers her things.",
                "Mr. Johnson is heard from the hallway.",
            ],
        }

    @staticmethod
    def scene_with_mentions_only() -> dict[str, Any]:
        """Get a scene with only action mentions, no dialogue."""
        return {
            "heading": "EXT. PARK - DAY",
            "dialogue": [],
            "action": [
                "Jane walks through the park.",
                "She sees Bob in the distance.",
                "Bobby waves to Ms. Smith.",
            ],
        }

    @staticmethod
    def empty_scene() -> dict[str, Any]:
        """Get an empty scene for testing."""
        return {
            "heading": "INT. ROOM - DAY",
            "dialogue": [],
            "action": [],
        }


class RelationshipTestHelpers:
    """Helper functions for relationship analyzer tests."""

    @staticmethod
    def create_analyzer_with_config(
        bible_characters: dict[str, Any] | None = None,
    ) -> CharacterRelationshipsAnalyzer:
        """Create an analyzer with the given bible characters config.

        Args:
            bible_characters: Bible characters configuration, or None for no config

        Returns:
            Configured CharacterRelationshipsAnalyzer instance
        """
        if bible_characters is None:
            return CharacterRelationshipsAnalyzer()
        return CharacterRelationshipsAnalyzer(
            config={"bible_characters": bible_characters}
        )

    @staticmethod
    async def create_initialized_analyzer(
        bible_characters: dict[str, Any] | None = None,
    ) -> CharacterRelationshipsAnalyzer:
        """Create and initialize an analyzer with the given config.

        Args:
            bible_characters: Bible characters configuration, or None for no config

        Returns:
            Initialized CharacterRelationshipsAnalyzer instance
        """
        analyzer = RelationshipTestHelpers.create_analyzer_with_config(bible_characters)
        await analyzer.initialize()
        return analyzer

    @staticmethod
    def mock_db_with_bible_data(
        bible_characters: dict[str, Any] | None = None,
    ) -> Mock:
        """Create a mock database connection with bible character data.

        Args:
            bible_characters: Bible characters to return from mock DB

        Returns:
            Mock connection object configured for testing
        """
        mock_conn = Mock()
        mock_cursor = Mock()

        if bible_characters:
            mock_cursor.fetchone.return_value = (json.dumps(bible_characters),)
        else:
            mock_cursor.fetchone.return_value = None

        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        return mock_conn

    @staticmethod
    def assert_relationship_result_structure(result: dict[str, Any]) -> None:
        """Assert that a relationship analysis result has the expected structure.

        Args:
            result: The analysis result to check
        """
        assert "present" in result
        assert "speaking" in result
        assert "co_presence_pairs" in result
        assert "speaking_edges" in result
        assert "stats" in result
        assert "present_count" in result["stats"]
        assert "speaking_count" in result["stats"]
        assert result["stats"]["present_count"] == len(result["present"])
        assert result["stats"]["speaking_count"] == len(result["speaking"])

    @staticmethod
    def assert_characters_present(
        result: dict[str, Any], expected_characters: set[str]
    ) -> None:
        """Assert that specific characters are marked as present.

        Args:
            result: The analysis result
            expected_characters: Set of canonical character names expected
        """
        assert set(result["present"]) == expected_characters

    @staticmethod
    def assert_characters_speaking(
        result: dict[str, Any], expected_speakers: set[str]
    ) -> None:
        """Assert that specific characters are marked as speaking.

        Args:
            result: The analysis result
            expected_speakers: Set of canonical character names expected
        """
        assert set(result["speaking"]) == expected_speakers

    @staticmethod
    def assert_co_presence_pairs(
        result: dict[str, Any], expected_pairs: list[list[str]]
    ) -> None:
        """Assert that specific co-presence pairs exist.

        Args:
            result: The analysis result
            expected_pairs: List of character pairs (as 2-element lists)
        """
        # Sort pairs for comparison (order within pair matters for consistency)
        actual_pairs = [sorted(pair) for pair in result["co_presence_pairs"]]
        expected_sorted = [sorted(pair) for pair in expected_pairs]
        assert sorted(actual_pairs) == sorted(expected_sorted)


@pytest.fixture
def relationship_test_data():
    """Provide access to common test data."""
    return RelationshipTestData()


@pytest.fixture
def scene_test_data():
    """Provide access to common scene test data."""
    return SceneTestData()


@pytest.fixture
def relationship_helpers():
    """Provide access to test helper functions."""
    return RelationshipTestHelpers()


@pytest.fixture
async def basic_analyzer():
    """Create and initialize a basic analyzer with standard test data."""
    bible_chars = RelationshipTestData.basic_bible_characters()
    return await RelationshipTestHelpers.create_initialized_analyzer(bible_chars)


@pytest.fixture
def mock_empty_db():
    """Create a mock database with no bible character data."""
    return RelationshipTestHelpers.mock_db_with_bible_data(None)


@pytest.fixture
def mock_basic_db():
    """Create a mock database with basic bible character data."""
    bible_chars = RelationshipTestData.basic_bible_characters()
    return RelationshipTestHelpers.mock_db_with_bible_data(bible_chars)

"""Tests for content extraction with Fountain edge cases."""

from uuid import uuid4

import pytest

from scriptrag.database import DatabaseConnection, initialize_database
from scriptrag.database.content_extractor import ContentExtractor


@pytest.fixture
def db_connection(tmp_path):
    """Create test database connection."""
    db_path = tmp_path / "test.db"
    initialize_database(db_path)
    return DatabaseConnection(db_path)


@pytest.fixture
def content_extractor(db_connection):
    """Create content extractor instance."""
    return ContentExtractor(db_connection)


class TestContentExtractorEdgeCases:
    """Test content extraction with Fountain format edge cases."""

    def test_dialogue_with_special_formatting(self, content_extractor, db_connection):
        """Test extraction of dialogue with special formatting like parentheticals."""
        # Create test script and scene
        script_id = str(uuid4())
        scene_id = str(uuid4())

        db_connection.execute(
            "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
            (script_id, "Test Script", "Test Author"),
        )

        db_connection.execute(
            """INSERT INTO scenes (id, script_id, heading, script_order)
            VALUES (?, ?, ?, ?)""",
            (scene_id, script_id, "INT. OFFICE - DAY", 1),
        )

        # Add dialogue with parentheticals and special formatting
        elements = [
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "Hello there!",
                "Hello there!",
                "JOHN",
                None,
                1,
            ),
            (
                str(uuid4()),
                scene_id,
                "parenthetical",
                "(whispering)",
                "(whispering)",
                "JOHN",
                None,
                2,
            ),
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "Can you hear me?",
                "Can you hear me?",
                "JOHN",
                None,
                3,
            ),
            (str(uuid4()), scene_id, "dialogue", "YES!", "YES!", "MARY", None, 4),
            (
                str(uuid4()),
                scene_id,
                "parenthetical",
                "(shouting; angry)",
                "(shouting; angry)",
                "MARY",
                None,
                5,
            ),
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "I can hear you just fine!",
                "I can hear you just fine!",
                "MARY",
                None,
                6,
            ),
        ]

        for elem in elements:
            db_connection.execute(
                """INSERT INTO scene_elements (
                    id, scene_id, element_type, text, raw_text,
                    character_name, character_id, order_in_scene)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                elem,
            )

        # Extract content
        contents = content_extractor.extract_scene_content(scene_id)

        # Verify dialogue extraction handles parentheticals properly
        dialogue_content = next(
            (c for c in contents if c["entity_type"] == "scene_dialogue"), None
        )
        assert dialogue_content is not None
        assert "JOHN: Hello there!" in dialogue_content["content"]
        assert "JOHN: Can you hear me?" in dialogue_content["content"]
        assert "MARY: YES!" in dialogue_content["content"]
        assert "MARY: I can hear you just fine!" in dialogue_content["content"]
        # Parentheticals should not be in dialogue content
        assert "(whispering)" not in dialogue_content["content"]
        assert "(shouting; angry)" not in dialogue_content["content"]

    def test_action_lines_with_embedded_emphasis(
        self, content_extractor, db_connection
    ):
        """Test extraction of action lines with embedded emphasis (*bold*, _italic_)."""
        script_id = str(uuid4())
        scene_id = str(uuid4())

        db_connection.execute(
            "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
            (script_id, "Test Script", "Test Author"),
        )

        db_connection.execute(
            """INSERT INTO scenes (id, script_id, heading, script_order)
            VALUES (?, ?, ?, ?)""",
            (scene_id, script_id, "EXT. BATTLEFIELD - NIGHT", 1),
        )

        # Add action lines with various emphasis styles
        actions = [
            (
                str(uuid4()),
                scene_id,
                "action",
                "The soldier *runs* across the field.",
                "The soldier *runs* across the field.",
                1,
            ),
            (
                str(uuid4()),
                scene_id,
                "action",
                "An _explosion_ rocks the ground.",
                "An _explosion_ rocks the ground.",
                2,
            ),
            (
                str(uuid4()),
                scene_id,
                "action",
                "He **dives** behind cover, _breathing heavily_.",
                "He **dives** behind cover, _breathing heavily_.",
                3,
            ),
            (
                str(uuid4()),
                scene_id,
                "action",
                "The sound of *gunfire* echoes through the ***smoke***.",
                "The sound of *gunfire* echoes through the ***smoke***.",
                4,
            ),
        ]

        for action in actions:
            db_connection.execute(
                """INSERT INTO scene_elements (
                    id, scene_id, element_type, text, raw_text, order_in_scene)
                VALUES (?, ?, ?, ?, ?, ?)""",
                action,
            )

        # Extract content
        contents = content_extractor.extract_scene_content(scene_id)

        # Verify action extraction preserves emphasis markers
        action_content = next(
            (c for c in contents if c["entity_type"] == "scene_action"), None
        )
        assert action_content is not None
        assert "*runs*" in action_content["content"]
        assert "_explosion_" in action_content["content"]
        assert "**dives**" in action_content["content"]
        assert "_breathing heavily_" in action_content["content"]
        assert "***smoke***" in action_content["content"]

    def test_character_names_with_extensions(self, content_extractor, db_connection):
        """Test extraction with character names that have extensions (V.O., etc)."""
        script_id = str(uuid4())
        scene_id = str(uuid4())
        char_id = str(uuid4())

        db_connection.execute(
            "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
            (script_id, "Test Script", "Test Author"),
        )

        db_connection.execute(
            """INSERT INTO scenes (id, script_id, heading, script_order)
            VALUES (?, ?, ?, ?)""",
            (scene_id, script_id, "INT. APARTMENT - NIGHT", 1),
        )

        # Create character
        db_connection.execute(
            """INSERT INTO characters (id, script_id, name, description)
            VALUES (?, ?, ?, ?)""",
            (char_id, script_id, "SARAH", "Main character"),
        )

        # Add dialogue with character extensions
        dialogues = [
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "Hello? Is anyone there?",
                "Hello? Is anyone there?",
                "SARAH",
                char_id,
                1,
            ),
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "I am everywhere and nowhere.",
                "I am everywhere and nowhere.",
                "SARAH (V.O.)",
                char_id,
                2,
            ),
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "Wait, I hear something outside.",
                "Wait, I hear something outside.",
                "SARAH",
                char_id,
                3,
            ),
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "Help! Someone help me!",
                "Help! Someone help me!",
                "SARAH (O.S.)",
                char_id,
                4,
            ),
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "This is just a recording.",
                "This is just a recording.",
                "SARAH (CONT'D)",
                char_id,
                5,
            ),
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "Testing, testing...",
                "Testing, testing...",
                "SARAH (FILTERED)",
                char_id,
                6,
            ),
        ]

        for dialogue in dialogues:
            db_connection.execute(
                """INSERT INTO scene_elements (
                    id, scene_id, element_type, text, raw_text,
                    character_name, character_id, order_in_scene)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                dialogue,
            )

        # Extract content
        contents = content_extractor.extract_scene_content(scene_id)

        # Verify dialogue extraction handles character extensions
        dialogue_content = next(
            (c for c in contents if c["entity_type"] == "scene_dialogue"), None
        )
        assert dialogue_content is not None
        assert "SARAH: Hello? Is anyone there?" in dialogue_content["content"]
        assert (
            "SARAH (V.O.): I am everywhere and nowhere." in dialogue_content["content"]
        )
        assert "SARAH (O.S.): Help! Someone help me!" in dialogue_content["content"]
        assert (
            "SARAH (CONT'D): This is just a recording." in dialogue_content["content"]
        )
        assert "SARAH (FILTERED): Testing, testing..." in dialogue_content["content"]

    def test_dual_dialogue_handling(self, content_extractor, db_connection):
        """Test extraction of dual dialogue (two characters speaking simultaneously)."""
        script_id = str(uuid4())
        scene_id = str(uuid4())

        db_connection.execute(
            "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
            (script_id, "Test Script", "Test Author"),
        )

        db_connection.execute(
            """INSERT INTO scenes (id, script_id, heading, script_order)
            VALUES (?, ?, ?, ?)""",
            (scene_id, script_id, "INT. COURTROOM - DAY", 1),
        )

        # Add dual dialogue elements
        elements = [
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "Your Honor, I object!",
                "Your Honor, I object!",
                "PROSECUTOR",
                '{"dual_dialogue": true}',
                1,
            ),
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "This is outrageous!",
                "This is outrageous!",
                "DEFENSE",
                '{"dual_dialogue": true}',
                2,
            ),
            (
                str(uuid4()),
                scene_id,
                "action",
                "The JUDGE bangs his gavel.",
                "The JUDGE bangs his gavel.",
                None,
                None,
                3,
            ),
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "Order! Order in the court!",
                "Order! Order in the court!",
                "JUDGE",
                None,
                4,
            ),
        ]

        for elem in elements:
            db_connection.execute(
                """INSERT INTO scene_elements (
                    id, scene_id, element_type, text, raw_text,
                    character_name, metadata_json, order_in_scene)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                elem,
            )

        # Extract content
        contents = content_extractor.extract_scene_content(scene_id)

        # Verify both dual dialogue lines are captured
        dialogue_content = next(
            (c for c in contents if c["entity_type"] == "scene_dialogue"), None
        )
        assert dialogue_content is not None
        assert "PROSECUTOR: Your Honor, I object!" in dialogue_content["content"]
        assert "DEFENSE: This is outrageous!" in dialogue_content["content"]
        assert "JUDGE: Order! Order in the court!" in dialogue_content["content"]

    def test_complex_transitions(self, content_extractor, db_connection):
        """Test extraction with complex scene transitions."""
        script_id = str(uuid4())
        scene_id = str(uuid4())

        db_connection.execute(
            "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
            (script_id, "Test Script", "Test Author"),
        )

        db_connection.execute(
            """INSERT INTO scenes (id, script_id, heading, description, script_order)
            VALUES (?, ?, ?, ?, ?)""",
            (
                scene_id,
                script_id,
                "INT./EXT. CAR/STREET - DAY - MOVING",
                "Complex transition between interior and exterior",
                1,
            ),
        )

        # Add elements with transitions
        elements = [
            (
                str(uuid4()),
                scene_id,
                "action",
                "The car speeds through traffic.",
                "The car speeds through traffic.",
                1,
            ),
            (str(uuid4()), scene_id, "transition", "SMASH CUT TO:", "SMASH CUT TO:", 2),
            (
                str(uuid4()),
                scene_id,
                "action",
                "CLOSE ON the driver's terrified face.",
                "CLOSE ON the driver's terrified face.",
                3,
            ),
            (str(uuid4()), scene_id, "transition", "MATCH CUT TO:", "MATCH CUT TO:", 4),
            (
                str(uuid4()),
                scene_id,
                "action",
                "The same expression on a poster.",
                "The same expression on a poster.",
                5,
            ),
            (
                str(uuid4()),
                scene_id,
                "transition",
                "FADE TO BLACK.",
                "FADE TO BLACK.",
                6,
            ),
        ]

        for elem in elements:
            db_connection.execute(
                """INSERT INTO scene_elements (
                    id, scene_id, element_type, text, raw_text, order_in_scene)
                VALUES (?, ?, ?, ?, ?, ?)""",
                elem,
            )

        # Extract content
        contents = content_extractor.extract_scene_content(scene_id)

        # Verify scene content includes description and heading
        scene_content = next((c for c in contents if c["entity_type"] == "scene"), None)
        assert scene_content is not None
        assert "INT./EXT. CAR/STREET - DAY - MOVING" in scene_content["content"]
        assert (
            "Complex transition between interior and exterior"
            in scene_content["content"]
        )

        # Verify transitions are included in the full text
        assert "SMASH CUT TO:" in scene_content["content"]
        assert "MATCH CUT TO:" in scene_content["content"]
        assert "FADE TO BLACK." in scene_content["content"]

    def test_malformed_fountain_syntax(self, content_extractor, db_connection):
        """Test extraction handles malformed or edge case Fountain syntax gracefully."""
        script_id = str(uuid4())
        scene_id = str(uuid4())

        db_connection.execute(
            "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
            (script_id, "Test Script", "Test Author"),
        )

        db_connection.execute(
            """INSERT INTO scenes (id, script_id, heading, script_order)
            VALUES (?, ?, ?, ?)""",
            (scene_id, script_id, "INT. LAB - DAY", 1),
        )

        # Add various malformed elements
        elements = [
            (str(uuid4()), scene_id, "dialogue", "", "", "EMPTY_SPEAKER", None, 1),
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "Text with no character",
                "Text with no character",
                None,
                None,
                2,
            ),
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "Multiple\n\nNewlines\n\n\nIn dialogue!",
                "Multiple\n\nNewlines\n\n\nIn dialogue!",
                "WEIRD",
                None,
                4,
            ),
            (
                str(uuid4()),
                scene_id,
                "character",
                "@CHARACTER_NAME_WITH_SYMBOL",
                "@CHARACTER_NAME_WITH_SYMBOL",
                None,
                None,
                5,
            ),
            (
                str(uuid4()),
                scene_id,
                "dialogue",
                "Text with @@@ special ### characters $$$",
                "Text with @@@ special ### characters $$$",
                "ROBOT",
                None,
                6,
            ),
            (
                str(uuid4()),
                scene_id,
                "action",
                "> Quoted action line that should not be",
                "> Quoted action line that should not be",
                None,
                None,
                7,
            ),
            (
                str(uuid4()),
                scene_id,
                "note",
                "[[This is a note that should be ignored]]",
                "[[This is a note that should be ignored]]",
                None,
                None,
                8,
            ),
        ]

        for elem in elements:
            if elem[3] is not None:  # Skip null text element
                db_connection.execute(
                    """INSERT INTO scene_elements (
                        id, scene_id, element_type, text, raw_text,
                        character_name, character_id, order_in_scene)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    elem,
                )

        # Extract content - should not crash
        contents = content_extractor.extract_scene_content(scene_id)

        # Verify extraction handles edge cases
        assert len(contents) > 0

        dialogue_content = next(
            (c for c in contents if c["entity_type"] == "scene_dialogue"), None
        )
        if dialogue_content:
            # Empty dialogue should be skipped or handled
            assert "EMPTY_SPEAKER:" in dialogue_content["content"]
            # Dialogue with no character should use UNKNOWN
            assert "UNKNOWN: Text with no character" in dialogue_content["content"]
            # Multi-line dialogue should be preserved
            assert (
                "WEIRD: Multiple\n\nNewlines\n\n\nIn dialogue!"
                in dialogue_content["content"]
            )
            # Special characters should be preserved
            assert (
                "ROBOT: Text with @@@ special ### characters $$$"
                in dialogue_content["content"]
            )

    def test_scene_without_elements(self, content_extractor, db_connection):
        """Test extraction of scene with no elements."""
        script_id = str(uuid4())
        scene_id = str(uuid4())

        db_connection.execute(
            "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
            (script_id, "Test Script", "Test Author"),
        )

        db_connection.execute(
            """INSERT INTO scenes (id, script_id, heading, description, script_order)
            VALUES (?, ?, ?, ?, ?)""",
            (
                scene_id,
                script_id,
                "INT. EMPTY ROOM - DAY",
                "A completely empty room with nothing in it.",
                1,
            ),
        )

        # Extract content from empty scene
        contents = content_extractor.extract_scene_content(scene_id)

        # Should still create scene content with heading and description
        assert len(contents) == 1
        scene_content = contents[0]
        assert scene_content["entity_type"] == "scene"
        assert "INT. EMPTY ROOM - DAY" in scene_content["content"]
        assert "A completely empty room with nothing in it." in scene_content["content"]
        assert scene_content["metadata"]["element_count"] == 0

    def test_character_with_no_dialogue(self, content_extractor, db_connection):
        """Test extraction of character who appears but has no dialogue."""
        script_id = str(uuid4())
        char_id = str(uuid4())

        db_connection.execute(
            "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
            (script_id, "Test Script", "Test Author"),
        )

        db_connection.execute(
            """INSERT INTO characters (id, script_id, name, description)
            VALUES (?, ?, ?, ?)""",
            (
                char_id,
                script_id,
                "SILENT BOB",
                "A character who never speaks, only appears in action lines.",
            ),
        )

        # Extract character content
        contents = content_extractor.extract_character_content(char_id)

        # Should create character profile without dialogue embedding
        assert len(contents) == 1
        char_content = contents[0]
        assert char_content["entity_type"] == "character"
        assert "SILENT BOB" in char_content["content"]
        assert "A character who never speaks" in char_content["content"]
        assert char_content["metadata"]["dialogue_count"] == 0

    def test_location_with_mixed_formats(self, content_extractor, db_connection):
        """Test extraction of location with various heading formats."""
        script_id = str(uuid4())
        location_id = str(uuid4())

        db_connection.execute(
            "INSERT INTO scripts (id, title, author) VALUES (?, ?, ?)",
            (script_id, "Test Script", "Test Author"),
        )

        # Create location with complex format
        db_connection.execute(
            """INSERT INTO locations (
                id, script_id, raw_text, name, interior, time_of_day)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                location_id,
                script_id,
                "INT./EXT. SUBMARINE - UNDERWATER - CONTINUOUS",
                "SUBMARINE",
                1,
                "CONTINUOUS",
            ),
        )

        # Create scenes at this location
        for i, heading in enumerate(
            [
                "INT. SUBMARINE - UNDERWATER - CONTINUOUS",
                "EXT. SUBMARINE - UNDERWATER - LATER",
                "I/E SUBMARINE - SURFACE - DAY",
            ]
        ):
            scene_id = str(uuid4())
            db_connection.execute(
                """INSERT INTO scenes (
                    id, script_id, heading, location_id, description, script_order)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    scene_id,
                    script_id,
                    heading,
                    location_id,
                    f"Scene {i + 1} at submarine location",
                    i + 1,
                ),
            )

        # Extract location content
        contents = content_extractor.extract_location_content(location_id)

        assert len(contents) == 1
        loc_content = contents[0]
        assert loc_content["entity_type"] == "location"
        assert "INT./EXT. SUBMARINE - UNDERWATER - CONTINUOUS" in loc_content["content"]
        assert "INTERIOR SUBMARINE - CONTINUOUS" in loc_content["content"]
        assert loc_content["metadata"]["scene_count"] == 3

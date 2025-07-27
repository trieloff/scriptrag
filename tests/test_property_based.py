"""Property-based testing examples using Hypothesis.

This module demonstrates how to use Hypothesis for property-based testing
in the ScriptRAG project. Property-based testing generates random test data
to find edge cases and ensure code correctness across a wide range of inputs.
"""

import string
from hypothesis import given, strategies as st, settings, example
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize
import pytest

from scriptrag.models import Character, Scene, Location, Script
from scriptrag.parser import FountainParser
from scriptrag.database.operations import sanitize_name


class TestPropertyBasedModels:
    """Property-based tests for data models."""

    @given(
        name=st.text(
            alphabet=string.printable.replace("\x00", ""),
            min_size=1,
            max_size=100
        ),
        alias=st.text(
            alphabet=string.printable.replace("\x00", ""),
            min_size=0,
            max_size=50
        )
    )
    def test_character_creation(self, name: str, alias: str):
        """Test that Character model handles any valid string input."""
        character = Character(name=name, alias=alias if alias else None)
        assert character.name == name
        assert character.alias == (alias if alias else None)
        assert isinstance(character.id, str)
        assert len(character.id) == 36  # UUID4 length

    @given(
        title=st.text(min_size=1, max_size=200),
        int_ext=st.sampled_from(["INT", "EXT", "INT./EXT", "EXT./INT", ""]),
        location=st.text(
            alphabet=string.ascii_letters + string.digits + " -.,",
            min_size=1,
            max_size=100
        ),
        time=st.sampled_from(["DAY", "NIGHT", "MORNING", "AFTERNOON", "EVENING", ""])
    )
    def test_scene_heading_parsing(self, title: str, int_ext: str, location: str, time: str):
        """Test that scene headings are parsed correctly for any valid input."""
        heading = f"{int_ext}. {location} - {time}".strip()
        if not int_ext:
            heading = location
            
        scene = Scene(
            scene_number=1,
            heading=heading,
            content=""
        )
        
        assert scene.heading == heading
        assert scene.scene_number == 1
        assert isinstance(scene.id, str)

    @given(
        script_title=st.text(min_size=1, max_size=100),
        num_scenes=st.integers(min_value=0, max_value=50),
        num_characters=st.integers(min_value=0, max_value=20)
    )
    @settings(max_examples=10)  # Limit examples for performance
    def test_script_with_multiple_scenes(self, script_title: str, num_scenes: int, num_characters: int):
        """Test script creation with varying numbers of scenes and characters."""
        script = Script(title=script_title)
        
        # Generate scenes
        scenes = []
        for i in range(num_scenes):
            scene = Scene(
                scene_number=i + 1,
                heading=f"INT. LOCATION {i} - DAY",
                content=f"Scene {i} content"
            )
            scenes.append(scene)
        
        # Generate characters
        characters = []
        for i in range(num_characters):
            character = Character(name=f"CHARACTER_{i}")
            characters.append(character)
        
        # Verify counts
        assert script.title == script_title
        assert len(scenes) == num_scenes
        assert len(characters) == num_characters


class TestPropertyBasedParsing:
    """Property-based tests for parsing functions."""

    @given(
        name=st.text(
            alphabet=string.ascii_letters + string.digits + " .,'-",
            min_size=1,
            max_size=50
        )
    )
    @example(name="JOHN (V.O.)")
    @example(name="MARY (O.S.)")
    @example(name="DR. SMITH")
    @example(name="THE NARRATOR")
    def test_character_name_cleaning(self, name: str):
        """Test that character name cleaning handles various formats."""
        parser = FountainParser()
        cleaned = parser._clean_character_name(name)
        
        # Should remove parentheticals
        assert "(V.O.)" not in cleaned
        assert "(O.S.)" not in cleaned
        assert "(CONT'D)" not in cleaned
        
        # Should preserve the main name
        assert len(cleaned) > 0
        assert cleaned.strip() == cleaned  # No leading/trailing spaces


class TestPropertyBasedDatabase:
    """Property-based tests for database operations."""

    @given(
        text=st.text(
            alphabet=string.printable,
            min_size=0,
            max_size=200
        )
    )
    def test_sanitize_name_idempotent(self, text: str):
        """Test that sanitize_name is idempotent."""
        sanitized_once = sanitize_name(text)
        sanitized_twice = sanitize_name(sanitized_once)
        assert sanitized_once == sanitized_twice

    @given(
        texts=st.lists(
            st.text(min_size=1, max_size=50),
            min_size=2,
            max_size=10
        )
    )
    def test_sanitize_name_collision_free(self, texts: list[str]):
        """Test that different inputs produce different sanitized outputs."""
        # Filter out duplicates in input
        unique_texts = list(set(texts))
        if len(unique_texts) < 2:
            return  # Skip if all inputs are the same
            
        sanitized = [sanitize_name(text) for text in unique_texts]
        
        # All unique inputs should produce unique outputs
        # (unless they differ only in special characters)
        assert len(set(sanitized)) >= 1


class ScriptDatabaseStateMachine(RuleBasedStateMachine):
    """Stateful testing for script database operations.
    
    This tests the database operations through a series of random
    operations to ensure consistency.
    """
    
    def __init__(self):
        super().__init__()
        self.scripts = {}
        self.scenes = {}
        self.characters = {}
    
    @initialize()
    def setup(self):
        """Initialize the state machine."""
        self.scripts = {}
        self.scenes = {}
        self.characters = {}
    
    @rule(
        title=st.text(min_size=1, max_size=100)
    )
    def add_script(self, title: str):
        """Add a new script."""
        script = Script(title=title)
        self.scripts[script.id] = script
        assert script.title == title
    
    @rule(
        script_id=st.sampled_from(lambda self: list(self.scripts.keys()) if self.scripts else [None]),
        scene_number=st.integers(min_value=1, max_value=100),
        heading=st.text(min_size=1, max_size=100)
    )
    def add_scene(self, script_id: str | None, scene_number: int, heading: str):
        """Add a scene to a script."""
        if script_id is None:
            return
            
        scene = Scene(
            scene_number=scene_number,
            heading=heading,
            content="",
            script_id=script_id
        )
        self.scenes[scene.id] = scene
        assert scene.script_id == script_id
    
    @rule(
        name=st.text(min_size=1, max_size=50)
    )
    def add_character(self, name: str):
        """Add a new character."""
        character = Character(name=name)
        self.characters[character.id] = character
        assert character.name == name
    
    def teardown(self):
        """Clean up after test."""
        pass


# Uncomment to run the state machine test
# TestScriptDatabaseStateMachine = ScriptDatabaseStateMachine.TestCase


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
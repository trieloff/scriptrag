"""Tests for base models and core entities."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from scriptrag.models import (
    Action,
    BaseEntity,
    Character,
    Dialogue,
    ElementType,
    Location,
    Parenthetical,
    Scene,
    SceneElement,
    Script,
    Transition,
)


class TestBaseEntity:
    """Test BaseEntity base class."""

    def test_base_entity_defaults(self):
        """Test BaseEntity creates default values."""
        entity = BaseEntity()

        assert isinstance(entity.id, UUID)
        assert isinstance(entity.created_at, datetime)
        assert isinstance(entity.updated_at, datetime)
        assert entity.metadata == {}

    def test_base_entity_custom_values(self):
        """Test BaseEntity with custom values."""
        test_id = uuid4()
        test_time = datetime(2024, 1, 1, 12, 0, 0)
        test_metadata = {"key": "value", "count": 42}

        entity = BaseEntity(
            id=test_id,
            created_at=test_time,
            updated_at=test_time,
            metadata=test_metadata,
        )

        assert entity.id == test_id
        assert entity.created_at == test_time
        assert entity.updated_at == test_time
        assert entity.metadata == test_metadata

    def test_uuid_serialization(self):
        """Test UUID serialization to string."""
        entity = BaseEntity()
        serialized = entity.model_dump()

        assert isinstance(serialized["id"], str)
        assert serialized["id"] == str(entity.id)

    def test_datetime_serialization(self):
        """Test datetime serialization to ISO format."""
        test_time = datetime(2024, 1, 1, 12, 0, 0)
        entity = BaseEntity(created_at=test_time, updated_at=test_time)
        serialized = entity.model_dump()

        assert serialized["created_at"] == "2024-01-01T12:00:00"
        assert serialized["updated_at"] == "2024-01-01T12:00:00"

    def test_metadata_mutation(self):
        """Test that metadata can be mutated."""
        entity = BaseEntity()
        entity.metadata["new_key"] = "new_value"

        assert entity.metadata == {"new_key": "new_value"}


class TestLocation:
    """Test Location model."""

    def test_location_creation(self):
        """Test creating a location."""
        location = Location(
            interior=True,
            name="COFFEE SHOP",
            time="DAY",
            raw_text="INT. COFFEE SHOP - DAY",
        )

        assert location.interior is True
        assert location.name == "COFFEE SHOP"
        assert location.time == "DAY"
        assert location.raw_text == "INT. COFFEE SHOP - DAY"

    def test_location_exterior(self):
        """Test exterior location."""
        location = Location(
            interior=False, name="PARK", time="NIGHT", raw_text="EXT. PARK - NIGHT"
        )

        assert location.interior is False
        assert str(location) == "EXT. PARK - NIGHT"

    def test_location_no_time(self):
        """Test location without time."""
        location = Location(
            interior=True, name="OFFICE", time=None, raw_text="INT. OFFICE"
        )

        assert location.time is None
        assert str(location) == "INT. OFFICE"

    def test_location_name_validation(self):
        """Test location name validation."""
        # Empty name should fail
        with pytest.raises(ValidationError) as exc_info:
            Location(interior=True, name="", raw_text="INT. - DAY")
        assert "Location name cannot be empty" in str(exc_info.value)

        # Whitespace only should fail
        with pytest.raises(ValidationError) as exc_info:
            Location(interior=True, name="   ", raw_text="INT.    - DAY")
        assert "Location name cannot be empty" in str(exc_info.value)

    def test_location_name_normalization(self):
        """Test location name is normalized to uppercase."""
        location = Location(
            interior=True, name="coffee shop", raw_text="INT. coffee shop - DAY"
        )

        assert location.name == "COFFEE SHOP"

    def test_location_str_format(self):
        """Test location string formatting."""
        # Interior with time
        loc1 = Location(interior=True, name="OFFICE", time="DAY", raw_text="")
        assert str(loc1) == "INT. OFFICE - DAY"

        # Exterior with time
        loc2 = Location(interior=False, name="STREET", time="NIGHT", raw_text="")
        assert str(loc2) == "EXT. STREET - NIGHT"

        # Interior without time
        loc3 = Location(interior=True, name="WAREHOUSE", time=None, raw_text="")
        assert str(loc3) == "INT. WAREHOUSE"


class TestCharacter:
    """Test Character model."""

    def test_character_creation(self):
        """Test creating a character."""
        character = Character(
            name="JOHN DOE", description="The protagonist", aliases=["JOHN", "MR. DOE"]
        )

        assert character.name == "JOHN DOE"
        assert character.description == "The protagonist"
        assert character.aliases == ["JOHN", "MR. DOE"]
        assert isinstance(character.id, UUID)

    def test_character_minimal(self):
        """Test character with minimal data."""
        character = Character(name="JANE")

        assert character.name == "JANE"
        assert character.description is None
        assert character.aliases == []

    def test_character_name_validation(self):
        """Test character name validation."""
        # Empty name should fail
        with pytest.raises(ValidationError) as exc_info:
            Character(name="")
        assert "Character name cannot be empty" in str(exc_info.value)

        # Whitespace only should fail
        with pytest.raises(ValidationError) as exc_info:
            Character(name="   ")
        assert "Character name cannot be empty" in str(exc_info.value)

    def test_character_name_normalization(self):
        """Test character name is normalized to uppercase."""
        character = Character(name="john doe")
        assert character.name == "JOHN DOE"

    def test_character_inherits_base_entity(self):
        """Test Character inherits from BaseEntity."""
        character = Character(name="TEST")

        # Should have BaseEntity fields
        assert hasattr(character, "id")
        assert hasattr(character, "created_at")
        assert hasattr(character, "updated_at")
        assert hasattr(character, "metadata")

        # Can use metadata
        character.metadata["role"] = "protagonist"
        assert character.metadata["role"] == "protagonist"


class TestSceneElement:
    """Test SceneElement and its subclasses."""

    def test_scene_element_base(self):
        """Test SceneElement base class."""
        scene_id = uuid4()
        element = SceneElement(
            element_type=ElementType.ACTION,
            text="Character enters the room.",
            raw_text="Character enters the room.",
            scene_id=scene_id,
            order_in_scene=1,
        )

        assert element.element_type == ElementType.ACTION
        assert element.text == "Character enters the room."
        assert element.raw_text == "Character enters the room."
        assert element.scene_id == scene_id
        assert element.order_in_scene == 1

    def test_action_element(self):
        """Test Action element."""
        scene_id = uuid4()
        action = Action(
            text="The door slams shut.",
            raw_text="The door slams shut.",
            scene_id=scene_id,
            order_in_scene=2,
        )

        assert action.element_type == ElementType.ACTION
        assert isinstance(action, SceneElement)
        assert isinstance(action, Action)

    def test_dialogue_element(self):
        """Test Dialogue element."""
        scene_id = uuid4()
        character_id = uuid4()
        dialogue = Dialogue(
            text="Hello, world!",
            raw_text="Hello, world!",
            scene_id=scene_id,
            order_in_scene=3,
            character_id=character_id,
            character_name="JOHN",
        )

        assert dialogue.element_type == ElementType.DIALOGUE
        assert dialogue.character_id == character_id
        assert dialogue.character_name == "JOHN"

    def test_parenthetical_element(self):
        """Test Parenthetical element."""
        scene_id = uuid4()
        dialogue_id = uuid4()
        parenthetical = Parenthetical(
            text="(sarcastically)",
            raw_text="(sarcastically)",
            scene_id=scene_id,
            order_in_scene=4,
            associated_dialogue_id=dialogue_id,
        )

        assert parenthetical.element_type == ElementType.PARENTHETICAL
        assert parenthetical.associated_dialogue_id == dialogue_id

    def test_parenthetical_without_dialogue(self):
        """Test Parenthetical without associated dialogue."""
        scene_id = uuid4()
        parenthetical = Parenthetical(
            text="(beat)",
            raw_text="(beat)",
            scene_id=scene_id,
            order_in_scene=5,
            associated_dialogue_id=None,
        )

        assert parenthetical.associated_dialogue_id is None

    def test_transition_element(self):
        """Test Transition element."""
        scene_id = uuid4()
        transition = Transition(
            text="CUT TO:", raw_text="CUT TO:", scene_id=scene_id, order_in_scene=6
        )

        assert transition.element_type == ElementType.TRANSITION


class TestScene:
    """Test Scene model."""

    def test_scene_creation(self):
        """Test creating a scene."""
        script_id = uuid4()
        location = Location(
            interior=True, name="OFFICE", time="DAY", raw_text="INT. OFFICE - DAY"
        )

        scene = Scene(
            location=location,
            heading="INT. OFFICE - DAY",
            description="A busy office scene",
            script_order=1,
            temporal_order=1,
            logical_order=1,
            script_id=script_id,
        )

        assert scene.location == location
        assert scene.heading == "INT. OFFICE - DAY"
        assert scene.description == "A busy office scene"
        assert scene.script_order == 1
        assert scene.temporal_order == 1
        assert scene.logical_order == 1
        assert scene.script_id == script_id

    def test_scene_minimal(self):
        """Test scene with minimal data."""
        script_id = uuid4()
        scene = Scene(script_order=5, script_id=script_id)

        assert scene.location is None
        assert scene.heading is None
        assert scene.description is None
        assert scene.temporal_order is None
        assert scene.logical_order is None
        assert scene.episode_id is None
        assert scene.season_id is None
        assert scene.elements == []
        assert scene.characters == []

    def test_scene_with_elements(self):
        """Test scene with elements."""
        script_id = uuid4()
        scene_id = uuid4()

        # Create elements
        action = Action(
            text="Door opens",
            raw_text="Door opens",
            scene_id=scene_id,
            order_in_scene=1,
        )

        dialogue = Dialogue(
            text="Hello!",
            raw_text="Hello!",
            scene_id=scene_id,
            order_in_scene=2,
            character_id=uuid4(),
            character_name="JOHN",
        )

        scene = Scene(
            id=scene_id,
            script_order=1,
            script_id=script_id,
            elements=[action, dialogue],
        )

        assert len(scene.elements) == 2
        assert scene.elements[0] == action
        assert scene.elements[1] == dialogue

    def test_scene_with_characters(self):
        """Test scene with character references."""
        script_id = uuid4()
        char_ids = [uuid4() for _ in range(3)]

        scene = Scene(script_order=1, script_id=script_id, characters=char_ids)

        assert scene.characters == char_ids
        assert len(scene.characters) == 3

    def test_scene_time_metadata(self):
        """Test scene time metadata."""
        scene = Scene(
            script_order=1,
            script_id=uuid4(),
            estimated_duration_minutes=5.5,
            time_of_day="MORNING",
            date_in_story="Day 3",
        )

        assert scene.estimated_duration_minutes == 5.5
        assert scene.time_of_day == "MORNING"
        assert scene.date_in_story == "Day 3"

    def test_scene_with_episode_season(self):
        """Test scene with episode and season references."""
        script_id = uuid4()
        episode_id = uuid4()
        season_id = uuid4()

        scene = Scene(
            script_order=1,
            script_id=script_id,
            episode_id=episode_id,
            season_id=season_id,
        )

        assert scene.episode_id == episode_id
        assert scene.season_id == season_id


class TestScript:
    """Test Script model."""

    def test_script_creation(self):
        """Test creating a script."""
        script = Script(
            title="Test Screenplay",
            format="screenplay",
            author="John Doe",
            description="A test screenplay",
            genre="Drama",
            logline="A compelling story about testing",
        )

        assert script.title == "Test Screenplay"
        assert script.format == "screenplay"
        assert script.author == "John Doe"
        assert script.description == "A test screenplay"
        assert script.genre == "Drama"
        assert script.logline == "A compelling story about testing"

    def test_script_minimal(self):
        """Test script with minimal data."""
        script = Script(title="Minimal Script")

        assert script.title == "Minimal Script"
        assert script.format == "screenplay"  # Default
        assert script.author is None
        assert script.is_series is False  # Default
        assert script.seasons == []
        assert script.episodes == []
        assert script.scenes == []
        assert script.characters == []
        assert script.title_page == {}

    def test_script_title_validation(self):
        """Test script title validation."""
        # Empty title should fail
        with pytest.raises(ValidationError) as exc_info:
            Script(title="")
        assert "Script title cannot be empty" in str(exc_info.value)

        # Whitespace only should fail
        with pytest.raises(ValidationError) as exc_info:
            Script(title="   ")
        assert "Script title cannot be empty" in str(exc_info.value)

    def test_script_title_normalization(self):
        """Test script title is normalized."""
        script = Script(title="  Test Script  ")
        assert script.title == "Test Script"

    def test_script_source_info(self):
        """Test script source information."""
        fountain_text = "Title: Test\n\nFADE IN:"

        script = Script(
            title="Test",
            fountain_source=fountain_text,
            source_file="/path/to/script.fountain",
        )

        assert script.fountain_source == fountain_text
        assert script.source_file == "/path/to/script.fountain"

    def test_script_as_series(self):
        """Test script configured as series."""
        season_ids = [uuid4() for _ in range(2)]
        episode_ids = [uuid4() for _ in range(10)]

        script = Script(
            title="Test Series",
            format="teleplay",
            is_series=True,
            seasons=season_ids,
            episodes=episode_ids,
        )

        assert script.is_series is True
        assert script.format == "teleplay"
        assert len(script.seasons) == 2
        assert len(script.episodes) == 10

    def test_script_title_page(self):
        """Test script title page metadata."""
        title_page = {
            "Title": "Test Script",
            "Author": "John Doe",
            "Draft date": "1/1/2024",
            "Contact": "john@example.com",
        }

        script = Script(title="Test Script", title_page=title_page)

        assert script.title_page == title_page
        assert script.title_page["Author"] == "John Doe"

    def test_script_with_content_refs(self):
        """Test script with content references."""
        scene_ids = [uuid4() for _ in range(20)]
        char_ids = [uuid4() for _ in range(5)]

        script = Script(title="Full Script", scenes=scene_ids, characters=char_ids)

        assert len(script.scenes) == 20
        assert len(script.characters) == 5
        assert all(isinstance(sid, UUID) for sid in script.scenes)
        assert all(isinstance(cid, UUID) for cid in script.characters)

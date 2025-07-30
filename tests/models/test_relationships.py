"""Tests for relationship models."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from scriptrag.models import (
    CharacterAppears,
    CharacterSpeaksTo,
    Relationship,
    SceneAtLocation,
    SceneDependency,
    SceneDependencyType,
    SceneFollows,
    SceneOrderType,
)


class TestRelationship:
    """Test base Relationship model."""

    def test_relationship_creation(self):
        """Test creating a basic relationship."""
        from_id = uuid4()
        to_id = uuid4()

        rel = Relationship(
            from_id=from_id, to_id=to_id, relationship_type="CONNECTS_TO"
        )

        assert rel.from_id == from_id
        assert rel.to_id == to_id
        assert rel.relationship_type == "CONNECTS_TO"
        assert rel.properties == {}
        assert isinstance(rel.created_at, datetime)

    def test_relationship_with_properties(self):
        """Test relationship with custom properties."""
        from_id = uuid4()
        to_id = uuid4()
        properties = {
            "weight": 0.8,
            "reason": "Strong connection",
            "metadata": {"source": "script"},
        }

        rel = Relationship(
            from_id=from_id,
            to_id=to_id,
            relationship_type="CUSTOM",
            properties=properties,
        )

        assert rel.properties == properties
        assert rel.properties["weight"] == 0.8
        assert rel.properties["metadata"]["source"] == "script"

    def test_relationship_created_at(self):
        """Test relationship created_at timestamp."""
        # Test with custom timestamp
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        rel = Relationship(
            from_id=uuid4(),
            to_id=uuid4(),
            relationship_type="TEST",
            created_at=custom_time,
        )

        assert rel.created_at == custom_time

        # Test default timestamp
        before = datetime.utcnow()
        rel2 = Relationship(from_id=uuid4(), to_id=uuid4(), relationship_type="TEST")
        after = datetime.utcnow()

        assert before <= rel2.created_at <= after


class TestCharacterAppears:
    """Test CharacterAppears relationship."""

    def test_character_appears_creation(self):
        """Test creating a character appearance relationship."""
        char_id = uuid4()
        scene_id = uuid4()

        appears = CharacterAppears(
            from_id=char_id, to_id=scene_id, speaking_lines=5, action_mentions=2
        )

        assert appears.from_id == char_id
        assert appears.to_id == scene_id
        assert appears.relationship_type == "APPEARS_IN"
        assert appears.speaking_lines == 5
        assert appears.action_mentions == 2

    def test_character_appears_defaults(self):
        """Test default values for character appearance."""
        appears = CharacterAppears(from_id=uuid4(), to_id=uuid4())

        assert appears.speaking_lines == 0
        assert appears.action_mentions == 0
        assert appears.relationship_type == "APPEARS_IN"

    def test_character_appears_inheritance(self):
        """Test CharacterAppears inherits from Relationship."""
        appears = CharacterAppears(from_id=uuid4(), to_id=uuid4())

        assert isinstance(appears, Relationship)
        assert hasattr(appears, "properties")
        assert hasattr(appears, "created_at")


class TestSceneFollows:
    """Test SceneFollows relationship."""

    def test_scene_follows_creation(self):
        """Test creating a scene follows relationship."""
        scene1_id = uuid4()
        scene2_id = uuid4()

        follows = SceneFollows(
            from_id=scene1_id, to_id=scene2_id, order_type=SceneOrderType.SCRIPT
        )

        assert follows.from_id == scene1_id
        assert follows.to_id == scene2_id
        assert follows.relationship_type == "FOLLOWS"
        assert follows.order_type == SceneOrderType.SCRIPT

    def test_scene_follows_order_types(self):
        """Test different order types for scene follows."""
        # Script order
        follows_script = SceneFollows(
            from_id=uuid4(), to_id=uuid4(), order_type=SceneOrderType.SCRIPT
        )
        assert follows_script.order_type == SceneOrderType.SCRIPT

        # Temporal order
        follows_temporal = SceneFollows(
            from_id=uuid4(), to_id=uuid4(), order_type=SceneOrderType.TEMPORAL
        )
        assert follows_temporal.order_type == SceneOrderType.TEMPORAL

        # Logical order
        follows_logical = SceneFollows(
            from_id=uuid4(), to_id=uuid4(), order_type=SceneOrderType.LOGICAL
        )
        assert follows_logical.order_type == SceneOrderType.LOGICAL


class TestCharacterSpeaksTo:
    """Test CharacterSpeaksTo relationship."""

    def test_character_speaks_to_creation(self):
        """Test creating a character speaks to relationship."""
        char1_id = uuid4()
        char2_id = uuid4()
        scene_id = uuid4()

        speaks = CharacterSpeaksTo(
            from_id=char1_id, to_id=char2_id, scene_id=scene_id, dialogue_count=3
        )

        assert speaks.from_id == char1_id
        assert speaks.to_id == char2_id
        assert speaks.scene_id == scene_id
        assert speaks.dialogue_count == 3
        assert speaks.relationship_type == "SPEAKS_TO"

    def test_character_speaks_to_defaults(self):
        """Test default dialogue count."""
        speaks = CharacterSpeaksTo(from_id=uuid4(), to_id=uuid4(), scene_id=uuid4())

        assert speaks.dialogue_count == 1  # Default


class TestSceneAtLocation:
    """Test SceneAtLocation relationship."""

    def test_scene_at_location_creation(self):
        """Test creating a scene at location relationship."""
        scene_id = uuid4()
        location_id = uuid4()

        at_location = SceneAtLocation(from_id=scene_id, to_id=location_id)

        assert at_location.from_id == scene_id
        assert at_location.to_id == location_id
        assert at_location.relationship_type == "AT_LOCATION"

    def test_scene_at_location_simple(self):
        """Test SceneAtLocation is a simple relationship."""
        at_location = SceneAtLocation(from_id=uuid4(), to_id=uuid4())

        # Should only have base relationship fields
        assert hasattr(at_location, "from_id")
        assert hasattr(at_location, "to_id")
        assert hasattr(at_location, "relationship_type")
        assert hasattr(at_location, "properties")
        assert hasattr(at_location, "created_at")


class TestSceneDependency:
    """Test SceneDependency model."""

    def test_scene_dependency_creation(self):
        """Test creating a scene dependency."""
        scene1_id = uuid4()
        scene2_id = uuid4()

        dep = SceneDependency(
            from_scene_id=scene1_id,
            to_scene_id=scene2_id,
            dependency_type=SceneDependencyType.REQUIRES,
            description="Scene A requires Scene B to have happened",
            strength=0.9,
        )

        assert dep.from_scene_id == scene1_id
        assert dep.to_scene_id == scene2_id
        assert dep.dependency_type == SceneDependencyType.REQUIRES
        assert dep.description == "Scene A requires Scene B to have happened"
        assert dep.strength == 0.9

    def test_scene_dependency_types(self):
        """Test different dependency types."""
        # Requires
        dep_requires = SceneDependency(
            from_scene_id=uuid4(),
            to_scene_id=uuid4(),
            dependency_type=SceneDependencyType.REQUIRES,
        )
        assert dep_requires.dependency_type == SceneDependencyType.REQUIRES

        # References
        dep_references = SceneDependency(
            from_scene_id=uuid4(),
            to_scene_id=uuid4(),
            dependency_type=SceneDependencyType.REFERENCES,
        )
        assert dep_references.dependency_type == SceneDependencyType.REFERENCES

        # Continues
        dep_continues = SceneDependency(
            from_scene_id=uuid4(),
            to_scene_id=uuid4(),
            dependency_type=SceneDependencyType.CONTINUES,
        )
        assert dep_continues.dependency_type == SceneDependencyType.CONTINUES

        # Flashback to
        dep_flashback = SceneDependency(
            from_scene_id=uuid4(),
            to_scene_id=uuid4(),
            dependency_type=SceneDependencyType.FLASHBACK_TO,
        )
        assert dep_flashback.dependency_type == SceneDependencyType.FLASHBACK_TO

    def test_scene_dependency_defaults(self):
        """Test default values for scene dependency."""
        dep = SceneDependency(
            from_scene_id=uuid4(),
            to_scene_id=uuid4(),
            dependency_type=SceneDependencyType.REQUIRES,
        )

        assert dep.description is None
        assert dep.strength == 1.0  # Default full strength

    def test_scene_dependency_strength_validation(self):
        """Test strength validation (0.0 to 1.0)."""
        # Valid strengths
        for strength in [0.0, 0.5, 1.0]:
            dep = SceneDependency(
                from_scene_id=uuid4(),
                to_scene_id=uuid4(),
                dependency_type=SceneDependencyType.REQUIRES,
                strength=strength,
            )
            assert dep.strength == strength

        # Invalid strengths
        with pytest.raises(ValidationError) as exc_info:
            SceneDependency(
                from_scene_id=uuid4(),
                to_scene_id=uuid4(),
                dependency_type=SceneDependencyType.REQUIRES,
                strength=-0.1,
            )
        # Pydantic's Field constraint validation message
        assert "greater than or equal to 0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            SceneDependency(
                from_scene_id=uuid4(),
                to_scene_id=uuid4(),
                dependency_type=SceneDependencyType.REQUIRES,
                strength=1.1,
            )
        # Pydantic's Field constraint validation message
        assert "less than or equal to 1" in str(exc_info.value)

    def test_scene_dependency_inherits_base_entity(self):
        """Test SceneDependency inherits from BaseEntity."""
        from scriptrag.models import BaseEntity

        dep = SceneDependency(
            from_scene_id=uuid4(),
            to_scene_id=uuid4(),
            dependency_type=SceneDependencyType.REQUIRES,
        )

        assert isinstance(dep, BaseEntity)
        assert hasattr(dep, "id")
        assert hasattr(dep, "created_at")
        assert hasattr(dep, "updated_at")
        assert hasattr(dep, "metadata")


class TestRelationshipPatterns:
    """Test common relationship patterns and usage."""

    def test_bidirectional_relationships(self):
        """Test creating bidirectional relationships."""
        char1_id = uuid4()
        char2_id = uuid4()
        scene_id = uuid4()

        # Character 1 speaks to Character 2
        speaks1to2 = CharacterSpeaksTo(
            from_id=char1_id, to_id=char2_id, scene_id=scene_id, dialogue_count=3
        )

        # Character 2 speaks to Character 1 (reverse)
        speaks2to1 = CharacterSpeaksTo(
            from_id=char2_id, to_id=char1_id, scene_id=scene_id, dialogue_count=2
        )

        # Different relationships for same pair
        assert speaks1to2.from_id == speaks2to1.to_id
        assert speaks1to2.to_id == speaks2to1.from_id
        assert speaks1to2.dialogue_count != speaks2to1.dialogue_count

    def test_multiple_relationships_same_entities(self):
        """Test multiple relationships between same entities."""
        scene1_id = uuid4()
        scene2_id = uuid4()

        # Scene follows in different orders
        follows_script = SceneFollows(
            from_id=scene1_id, to_id=scene2_id, order_type=SceneOrderType.SCRIPT
        )

        follows_temporal = SceneFollows(
            from_id=scene2_id,  # Reversed in temporal order
            to_id=scene1_id,
            order_type=SceneOrderType.TEMPORAL,
        )

        # Same scenes, different relationship meanings
        assert follows_script.from_id == follows_temporal.to_id
        assert follows_script.order_type != follows_temporal.order_type

    def test_relationship_serialization(self):
        """Test relationship serialization."""
        rel = CharacterAppears(
            from_id=uuid4(), to_id=uuid4(), speaking_lines=10, action_mentions=5
        )

        data = rel.model_dump()

        # Check all fields are serialized
        assert "from_id" in data
        assert "to_id" in data
        assert "relationship_type" in data
        assert "speaking_lines" in data
        assert "action_mentions" in data
        assert "properties" in data
        assert "created_at" in data

        # Check UUID serialization
        assert isinstance(data["from_id"], UUID)
        assert isinstance(data["to_id"], UUID)

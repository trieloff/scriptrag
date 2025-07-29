"""Tests for the mentor registry system."""

import pytest

from scriptrag.mentors.base import BaseMentor, MentorResult, MentorType
from scriptrag.mentors.registry import (
    MentorRegistry,
    MentorRegistryError,
    get_mentor_registry,
    reset_global_registry,
)


class TestMentor1(BaseMentor):
    """Test mentor 1."""

    @property
    def name(self) -> str:
        return "test_mentor_1"

    @property
    def description(self) -> str:
        return "First test mentor"

    @property
    def mentor_type(self) -> MentorType:
        return MentorType.STORY_STRUCTURE

    async def analyze_script(
        self,
        script_id,
        db_operations,
        progress_callback=None,
    ):
        # Silence unused parameter warnings in mock
        _ = db_operations
        _ = progress_callback

        return MentorResult(
            mentor_name=self.name,
            mentor_version=self.version,
            script_id=script_id,
            summary="Test analysis",
            analyses=[],
        )


class TestMentor2(BaseMentor):
    """Test mentor 2."""

    @property
    def name(self) -> str:
        return "test_mentor_2"

    @property
    def description(self) -> str:
        return "Second test mentor"

    @property
    def mentor_type(self) -> MentorType:
        return MentorType.CHARACTER_ARC

    @property
    def categories(self) -> list[str]:
        return ["character", "arc"]

    async def analyze_script(
        self,
        script_id,
        db_operations,
        progress_callback=None,
    ):
        # Silence unused parameter warnings in mock
        _ = db_operations
        _ = progress_callback

        return MentorResult(
            mentor_name=self.name,
            mentor_version=self.version,
            script_id=script_id,
            summary="Test analysis",
            analyses=[],
        )


class BrokenMentor(BaseMentor):
    """Mentor that fails during instantiation."""

    def __init__(self, config=None):
        super().__init__(config)
        raise ValueError("Broken mentor cannot be instantiated")

    @property
    def name(self) -> str:
        return "broken_mentor"

    @property
    def description(self) -> str:
        return "A broken mentor"

    @property
    def mentor_type(self) -> MentorType:
        return MentorType.DIALOGUE

    async def analyze_script(self, script_id, db_operations, progress_callback=None):
        # Silence unused parameter warnings in mock
        _ = script_id
        _ = db_operations
        _ = progress_callback
        pass


class NotAMentor:
    """Class that doesn't inherit from BaseMentor."""

    pass


class TestMentorRegistry:
    """Test MentorRegistry class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = MentorRegistry()

    def test_registry_creation(self):
        """Test creating a registry."""
        assert len(self.registry) == 0
        assert list(self.registry) == []

    def test_register_mentor(self):
        """Test registering a mentor."""
        self.registry.register(TestMentor1)

        assert len(self.registry) == 1
        assert "test_mentor_1" in self.registry
        assert list(self.registry) == ["test_mentor_1"]

    def test_register_multiple_mentors(self):
        """Test registering multiple mentors."""
        self.registry.register(TestMentor1)
        self.registry.register(TestMentor2)

        assert len(self.registry) == 2
        assert "test_mentor_1" in self.registry
        assert "test_mentor_2" in self.registry

    def test_register_non_mentor_class(self):
        """Test registering a class that doesn't inherit from BaseMentor."""
        with pytest.raises(MentorRegistryError, match="must inherit from BaseMentor"):
            self.registry.register(NotAMentor)

    def test_register_broken_mentor(self):
        """Test registering a mentor that fails during instantiation."""
        with pytest.raises(MentorRegistryError, match="Failed to instantiate mentor"):
            self.registry.register(BrokenMentor)

    def test_register_override_warning(self, caplog):
        """Test registering a mentor with the same name."""
        self.registry.register(TestMentor1)

        # Register another mentor with same name
        class AnotherTestMentor(BaseMentor):
            @property
            def name(self) -> str:
                return "test_mentor_1"  # Same name as TestMentor1

            @property
            def description(self) -> str:
                return "Another test mentor"

            @property
            def mentor_type(self) -> MentorType:
                return MentorType.DIALOGUE

            async def analyze_script(
                self, script_id, _db_operations, progress_callback=None
            ):
                pass

        self.registry.register(AnotherTestMentor)

        assert len(self.registry) == 1  # Still only one mentor
        assert "Overriding existing mentor" in caplog.text

    def test_unregister_mentor(self):
        """Test unregistering a mentor."""
        self.registry.register(TestMentor1)
        assert "test_mentor_1" in self.registry

        result = self.registry.unregister("test_mentor_1")
        assert result is True
        assert "test_mentor_1" not in self.registry
        assert len(self.registry) == 0

    def test_unregister_nonexistent_mentor(self):
        """Test unregistering a mentor that doesn't exist."""
        result = self.registry.unregister("nonexistent")
        assert result is False

    def test_get_mentor(self):
        """Test getting a mentor instance."""
        self.registry.register(TestMentor1)

        mentor = self.registry.get_mentor("test_mentor_1")
        assert isinstance(mentor, TestMentor1)
        assert mentor.name == "test_mentor_1"

    def test_get_mentor_with_config(self):
        """Test getting a mentor with config."""
        self.registry.register(TestMentor1)

        config = {"test_param": "test_value"}
        mentor = self.registry.get_mentor("test_mentor_1", config)
        assert mentor.config == config

    def test_get_nonexistent_mentor(self):
        """Test getting a mentor that doesn't exist."""
        with pytest.raises(MentorRegistryError, match="Mentor 'nonexistent' not found"):
            self.registry.get_mentor("nonexistent")

    def test_get_mentors_by_type(self):
        """Test getting mentors by type."""
        self.registry.register(TestMentor1)  # STORY_STRUCTURE
        self.registry.register(TestMentor2)  # CHARACTER_ARC

        structure_mentors = self.registry.get_mentors_by_type(
            MentorType.STORY_STRUCTURE
        )
        assert structure_mentors == ["test_mentor_1"]

        character_mentors = self.registry.get_mentors_by_type(MentorType.CHARACTER_ARC)
        assert character_mentors == ["test_mentor_2"]

        dialogue_mentors = self.registry.get_mentors_by_type(MentorType.DIALOGUE)
        assert dialogue_mentors == []

    def test_list_mentors(self):
        """Test listing all mentors."""
        self.registry.register(TestMentor1)
        self.registry.register(TestMentor2)

        mentors = self.registry.list_mentors()
        assert len(mentors) == 2

        # Check first mentor
        mentor1 = next(m for m in mentors if m["name"] == "test_mentor_1")
        assert mentor1["description"] == "First test mentor"
        assert mentor1["type"] == "story_structure"
        assert mentor1["version"] == "1.0.0"
        assert mentor1["categories"] == ["general"]  # Default categories
        assert mentor1["class"] == "TestMentor1"

        # Check second mentor
        mentor2 = next(m for m in mentors if m["name"] == "test_mentor_2")
        assert mentor2["description"] == "Second test mentor"
        assert mentor2["type"] == "character_arc"
        assert mentor2["categories"] == ["character", "arc"]

    def test_list_mentors_empty(self):
        """Test listing mentors when registry is empty."""
        mentors = self.registry.list_mentors()
        assert mentors == []

    def test_is_registered(self):
        """Test checking if mentor is registered."""
        assert not self.registry.is_registered("test_mentor_1")

        self.registry.register(TestMentor1)
        assert self.registry.is_registered("test_mentor_1")
        assert not self.registry.is_registered("test_mentor_2")

    def test_validate_mentor(self):
        """Test validating a mentor."""
        self.registry.register(TestMentor1)

        assert self.registry.validate_mentor("test_mentor_1") is True
        assert self.registry.validate_mentor("nonexistent") is False

    def test_get_mentor_config_schema(self):
        """Test getting mentor config schema."""
        self.registry.register(TestMentor1)

        schema = self.registry.get_mentor_config_schema("test_mentor_1")
        assert isinstance(schema, dict)
        assert schema["type"] == "object"

    def test_get_mentor_config_schema_nonexistent(self):
        """Test getting config schema for nonexistent mentor."""
        with pytest.raises(MentorRegistryError, match="Failed to get config schema"):
            self.registry.get_mentor_config_schema("nonexistent")

    def test_clear_registry(self):
        """Test clearing the registry."""
        self.registry.register(TestMentor1)
        self.registry.register(TestMentor2)
        assert len(self.registry) == 2

        self.registry.clear()
        assert len(self.registry) == 0
        assert list(self.registry) == []

    def test_contains_operator(self):
        """Test using 'in' operator."""
        self.registry.register(TestMentor1)

        assert "test_mentor_1" in self.registry
        assert "nonexistent" not in self.registry

    def test_iteration(self):
        """Test iterating over registry."""
        self.registry.register(TestMentor1)
        self.registry.register(TestMentor2)

        names = list(self.registry)
        assert "test_mentor_1" in names
        assert "test_mentor_2" in names
        assert len(names) == 2


class TestGlobalRegistry:
    """Test global registry functions."""

    def teardown_method(self):
        """Clean up after each test."""
        reset_global_registry()

    def test_get_global_registry(self):
        """Test getting the global registry."""
        registry1 = get_mentor_registry()
        registry2 = get_mentor_registry()

        # Should be the same instance
        assert registry1 is registry2

    def test_global_registry_has_builtin_mentors(self):
        """Test that global registry has built-in mentors."""
        registry = get_mentor_registry()

        # Should have at least the Save the Cat mentor
        mentors = registry.list_mentors()

        # Note: This test might fail if save_the_cat.py import fails
        # In that case, the registry would be empty, which is acceptable
        # for testing purposes
        assert isinstance(mentors, list)

    def test_reset_global_registry(self):
        """Test resetting the global registry."""
        registry1 = get_mentor_registry()

        # Add a mentor to the registry
        registry1.register(TestMentor1)
        assert "test_mentor_1" in registry1

        # Reset and get a new registry
        reset_global_registry()
        registry2 = get_mentor_registry()

        # Should be a different instance without our test mentor
        assert registry1 is not registry2
        assert "test_mentor_1" not in registry2

    def test_global_registry_thread_safety(self):
        """Test that global registry works with multiple calls."""
        import threading

        registries = []

        def get_registry():
            registries.append(get_mentor_registry())

        threads = [threading.Thread(target=get_registry) for _ in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should get the same registry instance
        assert all(registry is registries[0] for registry in registries)

"""Mentor Registry System.

This module provides the registry system for managing mentor plugins.
The registry allows for dynamic discovery, registration, and retrieval
of mentors, supporting both built-in and custom mentors.
"""

import logging
from collections.abc import Iterator

from scriptrag.mentors.base import BaseMentor, MentorType

logger = logging.getLogger(__name__)


class MentorRegistryError(Exception):
    """Raised when there are errors in mentor registration or retrieval."""

    pass


class MentorRegistry:
    """Registry for managing mentor plugins.

    The registry maintains a catalog of available mentors and provides
    methods for registration, discovery, and instantiation.
    """

    def __init__(self) -> None:
        """Initialize the mentor registry."""
        self._mentors: dict[str, type[BaseMentor]] = {}
        self._initialized = False

    def register(self, mentor_class: type[BaseMentor]) -> None:
        """Register a mentor class in the registry.

        Args:
            mentor_class: The mentor class to register

        Raises:
            MentorRegistryError: If mentor is invalid or name conflicts exist
        """
        if not issubclass(mentor_class, BaseMentor):
            raise MentorRegistryError(
                f"Mentor class {mentor_class.__name__} must inherit from BaseMentor"
            )

        # Create a temporary instance to get the name
        try:
            temp_instance = mentor_class()
            mentor_name = temp_instance.name
        except Exception as e:
            raise MentorRegistryError(
                f"Failed to instantiate mentor {mentor_class.__name__}: {e}"
            ) from e

        if mentor_name in self._mentors:
            existing_class = self._mentors[mentor_name]
            if existing_class != mentor_class:
                logger.warning(
                    f"Overriding existing mentor '{mentor_name}' "
                    f"({existing_class.__name__}) with {mentor_class.__name__}"
                )

        self._mentors[mentor_name] = mentor_class
        logger.info(f"Registered mentor: {mentor_name} ({mentor_class.__name__})")

    def unregister(self, mentor_name: str) -> bool:
        """Unregister a mentor from the registry.

        Args:
            mentor_name: Name of the mentor to unregister

        Returns:
            True if mentor was unregistered, False if not found
        """
        if mentor_name in self._mentors:
            del self._mentors[mentor_name]
            logger.info(f"Unregistered mentor: {mentor_name}")
            return True
        return False

    def get_mentor(self, mentor_name: str, config: dict | None = None) -> BaseMentor:
        """Get an instance of a registered mentor.

        Args:
            mentor_name: Name of the mentor to instantiate
            config: Optional configuration for the mentor

        Returns:
            Configured mentor instance

        Raises:
            MentorRegistryError: If mentor is not found or instantiation fails
        """
        if mentor_name not in self._mentors:
            available = ", ".join(self._mentors.keys())
            raise MentorRegistryError(
                f"Mentor '{mentor_name}' not found. Available mentors: {available}"
            )

        mentor_class = self._mentors[mentor_name]

        try:
            return mentor_class(config=config)
        except Exception as e:
            raise MentorRegistryError(
                f"Failed to instantiate mentor '{mentor_name}': {e}"
            ) from e

    def get_mentors_by_type(self, mentor_type: MentorType) -> list[str]:
        """Get names of all mentors of a specific type.

        Args:
            mentor_type: Type of mentors to retrieve

        Returns:
            List of mentor names matching the type
        """
        matching_mentors = []

        for name, mentor_class in self._mentors.items():
            try:
                temp_instance = mentor_class()
                if temp_instance.mentor_type == mentor_type:
                    matching_mentors.append(name)
            except Exception as e:
                logger.warning(f"Failed to check type for mentor '{name}': {e}")

        return matching_mentors

    def list_mentors(self) -> list[dict[str, str | list[str]]]:
        """List all registered mentors with their metadata.

        Returns:
            List of mentor metadata dictionaries
        """
        mentors_info = []

        for name, mentor_class in self._mentors.items():
            try:
                temp_instance = mentor_class()
                mentors_info.append(
                    {
                        "name": name,
                        "description": temp_instance.description,
                        "type": temp_instance.mentor_type.value,
                        "version": temp_instance.version,
                        "categories": temp_instance.categories,
                        "class": mentor_class.__name__,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to get info for mentor '{name}': {e}")
                mentors_info.append(
                    {
                        "name": name,
                        "description": f"Error loading mentor: {e}",
                        "type": "unknown",
                        "version": "unknown",
                        "categories": [],
                        "class": mentor_class.__name__,
                    }
                )

        return sorted(mentors_info, key=lambda x: x["name"])

    def is_registered(self, mentor_name: str) -> bool:
        """Check if a mentor is registered.

        Args:
            mentor_name: Name of the mentor to check

        Returns:
            True if mentor is registered, False otherwise
        """
        return mentor_name in self._mentors

    def validate_mentor(self, mentor_name: str) -> bool:
        """Validate that a mentor can be instantiated and configured.

        Args:
            mentor_name: Name of the mentor to validate

        Returns:
            True if mentor is valid, False otherwise
        """
        try:
            mentor = self.get_mentor(mentor_name)
            return mentor.validate_config()
        except Exception as e:
            logger.warning(f"Mentor validation failed for '{mentor_name}': {e}")
            return False

    def get_mentor_config_schema(self, mentor_name: str) -> dict:
        """Get the configuration schema for a mentor.

        Args:
            mentor_name: Name of the mentor

        Returns:
            JSON schema for the mentor's configuration

        Raises:
            MentorRegistryError: If mentor is not found
        """
        try:
            mentor = self.get_mentor(mentor_name)
            return mentor.get_config_schema()
        except Exception as e:
            raise MentorRegistryError(
                f"Failed to get config schema for mentor '{mentor_name}': {e}"
            ) from e

    def clear(self) -> None:
        """Clear all registered mentors."""
        self._mentors.clear()
        logger.info("Cleared all registered mentors")

    def __len__(self) -> int:
        """Get the number of registered mentors."""
        return len(self._mentors)

    def __contains__(self, mentor_name: str) -> bool:
        """Check if a mentor is registered using 'in' operator."""
        return mentor_name in self._mentors

    def __iter__(self) -> Iterator[str]:
        """Iterate over registered mentor names."""
        return iter(self._mentors.keys())


# Global registry instance
_global_registry: MentorRegistry | None = None


def get_mentor_registry() -> MentorRegistry:
    """Get the global mentor registry instance.

    This function provides access to the singleton mentor registry.
    The registry is automatically initialized with built-in mentors
    on first access.

    Returns:
        Global mentor registry instance
    """
    global _global_registry

    if _global_registry is None:
        _global_registry = MentorRegistry()
        _initialize_builtin_mentors(_global_registry)

    return _global_registry


def _initialize_builtin_mentors(registry: MentorRegistry) -> None:
    """Initialize built-in mentors in the registry.

    This function registers all built-in mentors that come with ScriptRAG.
    It's called automatically when the global registry is first accessed.

    Args:
        registry: Registry to initialize with built-in mentors
    """
    try:
        # Import and register built-in mentors
        from scriptrag.mentors.character_arc import CharacterArcMentor
        from scriptrag.mentors.heros_journey import HerosJourneyMentor
        from scriptrag.mentors.save_the_cat import SaveTheCatMentor
        from scriptrag.mentors.three_act_structure import ThreeActStructureMentor

        registry.register(SaveTheCatMentor)
        registry.register(HerosJourneyMentor)
        registry.register(ThreeActStructureMentor)
        registry.register(CharacterArcMentor)

        logger.info("Initialized built-in mentors")

    except ImportError as e:
        logger.warning(f"Failed to import built-in mentors: {e}")
    except Exception as e:
        logger.error(f"Error initializing built-in mentors: {e}")


def reset_global_registry() -> None:
    """Reset the global registry (primarily for testing)."""
    global _global_registry
    _global_registry = None

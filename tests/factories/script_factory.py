"""Factory classes for Script-related test data."""

from scriptrag.parser.fountain_models import Scene, Script
from tests.factories.scene_factory import SceneFactory


class ScriptFactory:
    """Factory for creating Script instances for testing."""

    @staticmethod
    def create(
        title: str | None = "Test Script",
        author: str | None = "Test Author",
        scenes: list[Scene] | None = None,
        metadata: dict | None = None,
    ) -> Script:
        """Create a Script instance with sensible defaults."""
        if scenes is None:
            scenes = [
                SceneFactory.create(number=1),
                SceneFactory.create(number=2, heading="INT. OFFICE - NIGHT"),
                SceneFactory.create(number=3, heading="EXT. STREET - DAY"),
            ]

        if metadata is None:
            metadata = {}

        return Script(
            title=title,
            author=author,
            scenes=scenes,
            metadata=metadata,
        )

    @staticmethod
    def create_tv_script(
        title: str = "Breaking Bad",
        season: int = 1,
        episode: int = 1,
        episode_title: str = "Pilot",
    ) -> Script:
        """Create a TV script with episode metadata."""
        metadata = {
            "season": season,
            "episode": episode,
            "episode_title": episode_title,
            "series_title": title,
        }

        scenes = [
            SceneFactory.create_exterior(
                number=1,
                location="DESERT",
                time_of_day="DAY",
            ),
            SceneFactory.create_with_dialogue(
                number=2,
                character="WALTER",
                dialogue_text="We need to cook.",
            ),
        ]

        return Script(
            title=f"{title} - S{season:02d}E{episode:02d} - {episode_title}",
            author="Vince Gilligan",
            scenes=scenes,
            metadata=metadata,
        )

"""Tests for series-specific models (Episode, Season)."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from scriptrag.models import Episode, Season


class TestEpisode:
    """Test Episode model."""

    def test_episode_creation(self):
        """Test creating an episode."""
        season_id = uuid4()
        script_id = uuid4()

        episode = Episode(
            title="Pilot",
            number=1,
            season_id=season_id,
            script_id=script_id,
            description="The first episode",
            writer="John Doe",
            director="Jane Smith",
        )

        assert episode.title == "Pilot"
        assert episode.number == 1
        assert episode.season_id == season_id
        assert episode.script_id == script_id
        assert episode.description == "The first episode"
        assert episode.writer == "John Doe"
        assert episode.director == "Jane Smith"

    def test_episode_minimal(self):
        """Test episode with minimal data."""
        episode = Episode(
            title="Episode 1", number=1, season_id=uuid4(), script_id=uuid4()
        )

        assert episode.title == "Episode 1"
        assert episode.description is None
        assert episode.air_date is None
        assert episode.writer is None
        assert episode.director is None
        assert episode.scenes == []
        assert episode.characters == []

    def test_episode_with_air_date(self):
        """Test episode with air date."""
        air_date = datetime(2024, 3, 15, 20, 0, 0)

        episode = Episode(
            title="Spring Premiere",
            number=10,
            season_id=uuid4(),
            script_id=uuid4(),
            air_date=air_date,
        )

        assert episode.air_date == air_date

    def test_episode_number_validation(self):
        """Test episode number must be positive."""
        # Valid episode numbers
        for num in [1, 10, 100]:
            episode = Episode(
                title=f"Episode {num}", number=num, season_id=uuid4(), script_id=uuid4()
            )
            assert episode.number == num

        # Invalid episode numbers
        for num in [0, -1, -10]:
            with pytest.raises(ValidationError) as exc_info:
                Episode(
                    title="Bad Episode",
                    number=num,
                    season_id=uuid4(),
                    script_id=uuid4(),
                )
            assert "Episode number must be positive" in str(exc_info.value)

    def test_episode_with_content_refs(self):
        """Test episode with scene and character references."""
        scene_ids = [uuid4() for _ in range(10)]
        char_ids = [uuid4() for _ in range(5)]

        episode = Episode(
            title="Action Episode",
            number=5,
            season_id=uuid4(),
            script_id=uuid4(),
            scenes=scene_ids,
            characters=char_ids,
        )

        assert len(episode.scenes) == 10
        assert len(episode.characters) == 5
        assert all(isinstance(sid, UUID) for sid in episode.scenes)
        assert all(isinstance(cid, UUID) for cid in episode.characters)

    def test_episode_inherits_base_entity(self):
        """Test Episode inherits from BaseEntity."""
        from scriptrag.models import BaseEntity

        episode = Episode(title="Test", number=1, season_id=uuid4(), script_id=uuid4())

        assert isinstance(episode, BaseEntity)
        assert hasattr(episode, "id")
        assert hasattr(episode, "created_at")
        assert hasattr(episode, "updated_at")
        assert hasattr(episode, "metadata")

    def test_episode_serialization(self):
        """Test episode serialization."""
        episode = Episode(
            title="Serialization Test",
            number=7,
            season_id=uuid4(),
            script_id=uuid4(),
            air_date=datetime(2024, 5, 1, 21, 0, 0),
            scenes=[uuid4(), uuid4()],
        )

        data = episode.model_dump()

        assert data["title"] == "Serialization Test"
        assert data["number"] == 7
        # Note: UUIDs are not automatically serialized to strings by model_dump()
        # unless mode='json' is used
        assert isinstance(data["season_id"], UUID)
        assert isinstance(data["script_id"], UUID)
        assert isinstance(data["air_date"], datetime)
        assert len(data["scenes"]) == 2

        # For JSON serialization, use mode='json'
        json_data = episode.model_dump(mode="json")
        assert isinstance(json_data["season_id"], str)
        assert isinstance(json_data["script_id"], str)
        assert isinstance(json_data["air_date"], str)


class TestSeason:
    """Test Season model."""

    def test_season_creation(self):
        """Test creating a season."""
        script_id = uuid4()

        season = Season(
            number=1,
            title="Season One: Origins",
            script_id=script_id,
            description="The first season introduces our heroes",
            year=2024,
        )

        assert season.number == 1
        assert season.title == "Season One: Origins"
        assert season.script_id == script_id
        assert season.description == "The first season introduces our heroes"
        assert season.year == 2024

    def test_season_minimal(self):
        """Test season with minimal data."""
        season = Season(number=2, script_id=uuid4())

        assert season.number == 2
        assert season.title is None
        assert season.description is None
        assert season.year is None
        assert season.episodes == []

    def test_season_number_validation(self):
        """Test season number must be positive."""
        # Valid season numbers
        for num in [1, 5, 20]:
            season = Season(number=num, script_id=uuid4())
            assert season.number == num

        # Invalid season numbers
        for num in [0, -1, -5]:
            with pytest.raises(ValidationError) as exc_info:
                Season(number=num, script_id=uuid4())
            assert "Season number must be positive" in str(exc_info.value)

    def test_season_with_episodes(self):
        """Test season with episode references."""
        episode_ids = [uuid4() for _ in range(13)]  # 13 episode season

        season = Season(
            number=3, title="The Third Year", script_id=uuid4(), episodes=episode_ids
        )

        assert len(season.episodes) == 13
        assert all(isinstance(eid, UUID) for eid in season.episodes)

    def test_season_year_bounds(self):
        """Test season year reasonable bounds."""
        # Valid years
        for year in [1900, 1950, 2000, 2024, 2030]:
            season = Season(number=1, script_id=uuid4(), year=year)
            assert season.year == year

        # Note: The model doesn't enforce year bounds, so any integer is valid
        # This is reasonable as seasons could be set in different time periods

    def test_season_inherits_base_entity(self):
        """Test Season inherits from BaseEntity."""
        from scriptrag.models import BaseEntity

        season = Season(number=1, script_id=uuid4())

        assert isinstance(season, BaseEntity)
        assert hasattr(season, "id")
        assert hasattr(season, "created_at")
        assert hasattr(season, "updated_at")
        assert hasattr(season, "metadata")

    def test_season_metadata_usage(self):
        """Test using metadata for additional season info."""
        season = Season(number=4, title="The Final Season", script_id=uuid4())

        # Add production metadata
        season.metadata["production_code"] = "S04"
        season.metadata["filming_location"] = "Vancouver"
        season.metadata["budget_millions"] = 50

        assert season.metadata["production_code"] == "S04"
        assert season.metadata["filming_location"] == "Vancouver"
        assert season.metadata["budget_millions"] == 50

    def test_season_serialization(self):
        """Test season serialization."""
        season = Season(
            number=2,
            title="Return of the Heroes",
            script_id=uuid4(),
            year=2025,
            episodes=[uuid4() for _ in range(10)],
        )

        data = season.model_dump()

        assert data["number"] == 2
        assert data["title"] == "Return of the Heroes"
        assert data["year"] == 2025
        assert len(data["episodes"]) == 10
        assert isinstance(data["script_id"], UUID)  # UUID not serialized by default

        # For JSON serialization
        json_data = season.model_dump(mode="json")
        assert isinstance(json_data["script_id"], str)


class TestEpisodeSeasonRelationship:
    """Test the relationship between episodes and seasons."""

    def test_consistent_script_ids(self):
        """Test that episodes and seasons can share script IDs."""
        script_id = uuid4()

        # Create a season
        season = Season(number=1, script_id=script_id)

        # Create episodes for that season
        episodes = []
        for i in range(1, 11):
            episode = Episode(
                title=f"Episode {i}",
                number=i,
                season_id=season.id,
                script_id=script_id,  # Same script ID
            )
            episodes.append(episode)

        # All should have same script ID
        assert all(ep.script_id == script_id for ep in episodes)
        assert all(ep.season_id == season.id for ep in episodes)

    def test_episode_ordering_within_season(self):
        """Test episode ordering within a season."""
        season_id = uuid4()
        script_id = uuid4()

        # Create episodes with specific numbers
        episodes = []
        for num in [1, 2, 5, 3, 4]:  # Out of order creation
            episode = Episode(
                title=f"Episode {num}",
                number=num,
                season_id=season_id,
                script_id=script_id,
            )
            episodes.append(episode)

        # Sort by episode number
        sorted_episodes = sorted(episodes, key=lambda e: e.number)

        # Verify ordering
        assert [e.number for e in sorted_episodes] == [1, 2, 3, 4, 5]

    def test_multi_season_series(self):
        """Test modeling a multi-season series."""
        script_id = uuid4()

        # Create multiple seasons
        seasons = []
        for season_num in range(1, 4):
            season = Season(
                number=season_num,
                title=f"Season {season_num}",
                script_id=script_id,
                year=2023 + season_num,
            )
            seasons.append(season)

        # Create episodes for each season
        all_episodes = []
        for season in seasons:
            season_episodes = []
            for ep_num in range(1, 11):  # 10 episodes per season
                episode = Episode(
                    title=f"S{season.number}E{ep_num}",
                    number=ep_num,
                    season_id=season.id,
                    script_id=script_id,
                )
                season_episodes.append(episode.id)
                all_episodes.append(episode)

            # Update season with episode IDs
            season.episodes = season_episodes

        # Verify structure
        assert len(seasons) == 3
        assert len(all_episodes) == 30  # 3 seasons x 10 episodes
        assert all(len(s.episodes) == 10 for s in seasons)

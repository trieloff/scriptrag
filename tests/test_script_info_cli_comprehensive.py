"""Comprehensive tests for script info CLI command to improve coverage."""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from scriptrag.cli import app
from scriptrag.models import (
    Action,
    Character,
    Dialogue,
    Location,
    Parenthetical,
    Scene,
    Script,
    Transition,
)


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


class TestScriptInfoCoverage:
    """Additional tests to improve coverage of the script info command."""

    def test_info_command_long_screenplay_over_130_pages(self, cli_runner, tmp_path):
        """Test insights for screenplay over 130 pages."""
        parser = Mock()
        script = Script(title="Epic Script", author="Author")

        # Create enough content for >130 pages (130 * 250 = 32500 words)
        scenes = []
        for i in range(50):
            scene = Scene(
                heading=f"INT. LOCATION {i} - DAY", script_order=i, script_id=uuid4()
            )
            # Each scene has 700 words = 35000 total
            scene.elements = [
                Action(
                    text=" ".join(["word"] * 700),
                    raw_text=" ".join(["word"] * 700),
                    scene_id=scene.id,
                    order_in_scene=0,
                )
            ]
            scenes.append(scene)

        parser.parse_file.return_value = script
        parser.get_scenes.return_value = scenes
        parser.get_characters.return_value = []

        test_file = tmp_path / "test.fountain"
        test_file.write_text("Long screenplay")

        with patch.object(
            __import__("scriptrag.parser", fromlist=["FountainParser"]),
            "FountainParser",
            return_value=parser,
        ):
            result = cli_runner.invoke(app, ["script", "info", str(test_file)])

        assert result.exit_code == 0
        assert "Long screenplay" in result.stdout
        assert "Consider trimming to standard length" in result.stdout

    def test_info_command_good_length_screenplay(self, cli_runner, tmp_path):
        """Test insights for screenplay of good length (90-130 pages)."""
        parser = Mock()
        script = Script(title="Good Length Script", author="Author")

        # Create content for ~100 pages (100 * 250 = 25000 words)
        scenes = []
        for i in range(25):
            scene = Scene(
                heading=f"INT. LOCATION {i} - DAY", script_order=i, script_id=uuid4()
            )
            # Each scene has 1000 words = 25000 total
            scene.elements = [
                Action(
                    text=" ".join(["word"] * 1000),
                    raw_text=" ".join(["word"] * 1000),
                    scene_id=scene.id,
                    order_in_scene=0,
                )
            ]
            scenes.append(scene)

        parser.parse_file.return_value = script
        parser.get_scenes.return_value = scenes
        parser.get_characters.return_value = []

        test_file = tmp_path / "test.fountain"
        test_file.write_text("Good length screenplay")

        with patch.object(
            __import__("scriptrag.parser", fromlist=["FountainParser"]),
            "FountainParser",
            return_value=parser,
        ):
            result = cli_runner.invoke(app, ["script", "info", str(test_file)])

        assert result.exit_code == 0
        assert "Good length" in result.stdout
        assert "Screenplay is within standard feature range" in result.stdout

    def test_info_command_exterior_heavy_screenplay(self, cli_runner, tmp_path):
        """Test insights for exterior-heavy screenplay."""
        parser = Mock()
        script = Script(title="Outdoor Script", author="Author")

        scenes = []
        # Create mostly exterior scenes
        for i in range(10):
            location = Location(
                interior=(i < 2),  # Only first 2 are interior
                name=f"LOCATION {i}",
                time="DAY",
                raw_text=f"{'INT' if i < 2 else 'EXT'}. LOCATION {i} - DAY",
            )
            scene = Scene(
                location=location,
                heading=location.raw_text,
                script_order=i,
                script_id=uuid4(),
            )
            scene.elements = [
                Action(
                    text="Action",
                    raw_text="Action",
                    scene_id=scene.id,
                    order_in_scene=0,
                )
            ]
            scenes.append(scene)

        parser.parse_file.return_value = script
        parser.get_scenes.return_value = scenes
        parser.get_characters.return_value = []

        test_file = tmp_path / "test.fountain"
        test_file.write_text("Outdoor screenplay")

        with patch.object(
            __import__("scriptrag.parser", fromlist=["FountainParser"]),
            "FountainParser",
            return_value=parser,
        ):
            result = cli_runner.invoke(app, ["script", "info", str(test_file)])

        assert result.exit_code == 0
        assert "Exterior heavy" in result.stdout
        assert "Many outdoor scenes - weather dependent" in result.stdout

    def test_info_command_small_cast(self, cli_runner, tmp_path):
        """Test insights for small cast (< 5 characters)."""
        parser = Mock()
        script = Script(title="Intimate Script", author="Author")

        # Create just 3 characters
        characters = [
            Character(name="ALICE"),
            Character(name="BOB"),
            Character(name="CHARLIE"),
        ]

        scene = Scene(heading="INT. ROOM - DAY", script_order=1, script_id=uuid4())
        scene.elements = [
            Action(
                text="Small cast",
                raw_text="Small cast",
                scene_id=scene.id,
                order_in_scene=0,
            )
        ]

        parser.parse_file.return_value = script
        parser.get_scenes.return_value = [scene]
        parser.get_characters.return_value = characters

        test_file = tmp_path / "test.fountain"
        test_file.write_text("Small cast screenplay")

        with patch.object(
            __import__("scriptrag.parser", fromlist=["FountainParser"]),
            "FountainParser",
            return_value=parser,
        ):
            result = cli_runner.invoke(app, ["script", "info", str(test_file)])

        assert result.exit_code == 0
        assert "Small cast" in result.stdout
        assert "Intimate character-driven story" in result.stdout

    def test_info_command_action_heavy_screenplay(self, cli_runner, tmp_path):
        """Test insights for action-heavy screenplay."""
        parser = Mock()
        script = Script(title="Action Script", author="Author")

        scene = Scene(
            heading="EXT. BATTLEFIELD - DAY", script_order=1, script_id=uuid4()
        )

        # Many action lines, few dialogue lines
        scene.elements = []
        for i in range(20):
            scene.elements.append(
                Action(
                    text=f"Action sequence {i}",
                    raw_text=f"Action sequence {i}",
                    scene_id=scene.id,
                    order_in_scene=i,
                )
            )

        # Add just a couple dialogue lines
        scene.elements.append(
            Dialogue(
                text="Charge!",
                raw_text="Charge!",
                scene_id=scene.id,
                order_in_scene=20,
                character_id=uuid4(),
                character_name="SOLDIER",
            )
        )

        parser.parse_file.return_value = script
        parser.get_scenes.return_value = [scene]
        parser.get_characters.return_value = [Character(name="SOLDIER")]

        test_file = tmp_path / "test.fountain"
        test_file.write_text("Action heavy")

        with patch.object(
            __import__("scriptrag.parser", fromlist=["FountainParser"]),
            "FountainParser",
            return_value=parser,
        ):
            result = cli_runner.invoke(app, ["script", "info", str(test_file)])

        assert result.exit_code == 0
        assert "Action heavy" in result.stdout
        assert "Visual storytelling emphasized" in result.stdout

    def test_info_command_no_dialogue_or_action(self, cli_runner, tmp_path):
        """Test screenplay with no dialogue or action lines."""
        parser = Mock()
        script = Script(title="Empty Script", author="Author")

        scene = Scene(heading="INT. VOID - TIMELESS", script_order=1, script_id=uuid4())
        scene.elements = []  # No elements

        parser.parse_file.return_value = script
        parser.get_scenes.return_value = [scene]
        parser.get_characters.return_value = []

        test_file = tmp_path / "test.fountain"
        test_file.write_text("Empty screenplay")

        with patch.object(
            __import__("scriptrag.parser", fromlist=["FountainParser"]),
            "FountainParser",
            return_value=parser,
        ):
            result = cli_runner.invoke(app, ["script", "info", str(test_file)])

        assert result.exit_code == 0
        # Should not crash even with no dialogue/action
        assert "Total Scenes" in result.stdout

    def test_info_command_minimal_insights_screenplay(self, cli_runner, tmp_path):
        """Test screenplay that triggers only the good length insight."""
        parser = Mock()
        script = Script(title="Balanced Script", author="Author")

        # Create content that triggers minimal insights
        # - Good length (90-130 pages): 100 pages = 25000 words
        # - Balance INT/EXT without triggering ratios (not 3:1 or 1:2)
        # - Moderate character count (5-50)
        # - Balanced dialogue/action ratio (between 30-70%)
        scenes = []
        for i in range(20):  # Moderate scene count
            location = Location(
                interior=(i % 3 != 0),  # 2:1 INT/EXT ratio (not extreme)
                name=f"LOCATION {i}",
                time="DAY",
                raw_text=f"{'INT' if i % 3 != 0 else 'EXT'}. LOCATION {i} - DAY",
            )
            scene = Scene(
                location=location,
                heading=location.raw_text,
                script_order=i,
                script_id=uuid4(),
            )

            # Create balanced content
            scene.elements = []
            # 1250 words per scene = 25000 total = 100 pages
            # Balanced dialogue and action ratio
            scene.elements.append(
                Action(
                    text=" ".join(["action"] * 300),
                    raw_text=" ".join(["action"] * 300),
                    scene_id=scene.id,
                    order_in_scene=0,
                )
            )
            scene.elements.append(
                Dialogue(
                    text=" ".join(["dialogue"] * 325),
                    raw_text=" ".join(["dialogue"] * 325),
                    scene_id=scene.id,
                    order_in_scene=1,
                    character_id=uuid4(),
                    character_name=f"CHAR{i % 10}",
                )
            )
            scene.elements.append(
                Action(
                    text=" ".join(["more"] * 300),
                    raw_text=" ".join(["more"] * 300),
                    scene_id=scene.id,
                    order_in_scene=2,
                )
            )
            scene.elements.append(
                Dialogue(
                    text=" ".join(["dialog2"] * 325),
                    raw_text=" ".join(["dialog2"] * 325),
                    scene_id=scene.id,
                    order_in_scene=3,
                    character_id=uuid4(),
                    character_name=f"CHAR{(i + 1) % 10}",
                )
            )
            scenes.append(scene)

        # Moderate character count (not < 5 or > 50)
        characters = [Character(name=f"CHAR{i}") for i in range(15)]

        parser.parse_file.return_value = script
        parser.get_scenes.return_value = scenes
        parser.get_characters.return_value = characters

        test_file = tmp_path / "test.fountain"
        test_file.write_text("Balanced screenplay")

        with patch.object(
            __import__("scriptrag.parser", fromlist=["FountainParser"]),
            "FountainParser",
            return_value=parser,
        ):
            result = cli_runner.invoke(app, ["script", "info", str(test_file)])

        assert result.exit_code == 0
        # Should only have the "Good length" insight
        assert "Good length" in result.stdout
        assert "Screenplay is within standard feature range" in result.stdout
        # Should not have other insights
        assert "Interior heavy" not in result.stdout
        assert "Exterior heavy" not in result.stdout
        assert "Small cast" not in result.stdout
        assert "Large cast" not in result.stdout
        assert "Dialogue heavy" not in result.stdout
        assert "Action heavy" not in result.stdout

    def test_info_command_no_title_page_metadata(self, cli_runner, tmp_path):
        """Test screenplay with no title page metadata."""
        parser = Mock()
        script = Script(
            title="Untitled",
            author=None,  # No author
            title_page={},  # Empty title page
        )

        scene = Scene(heading="FADE IN:", script_order=1, script_id=uuid4())
        scene.elements = []

        parser.parse_file.return_value = script
        parser.get_scenes.return_value = [scene]
        parser.get_characters.return_value = []

        test_file = tmp_path / "test.fountain"
        test_file.write_text("No metadata")

        with patch.object(
            __import__("scriptrag.parser", fromlist=["FountainParser"]),
            "FountainParser",
            return_value=parser,
        ):
            result = cli_runner.invoke(app, ["script", "info", str(test_file)])

        assert result.exit_code == 0
        assert "by Unknown" in result.stdout  # Default when no author

    def test_info_command_scenes_without_location(self, cli_runner, tmp_path):
        """Test scenes without location information."""
        parser = Mock()
        script = Script(title="No Location Script", author="Author")

        # Create scenes with no location
        scenes = []
        for i in range(3):
            scene = Scene(
                location=None,  # No location
                heading=f"SCENE {i}",
                script_order=i,
                script_id=uuid4(),
            )
            scene.elements = [
                Action(
                    text="Action",
                    raw_text="Action",
                    scene_id=scene.id,
                    order_in_scene=0,
                )
            ]
            scenes.append(scene)

        parser.parse_file.return_value = script
        parser.get_scenes.return_value = scenes
        parser.get_characters.return_value = []

        test_file = tmp_path / "test.fountain"
        test_file.write_text("No locations")

        with patch.object(
            __import__("scriptrag.parser", fromlist=["FountainParser"]),
            "FountainParser",
            return_value=parser,
        ):
            result = cli_runner.invoke(app, ["script", "info", str(test_file)])

        assert result.exit_code == 0
        assert "No Location" in result.stdout
        assert "100.0%" in result.stdout  # All scenes have no location

    def test_info_command_unexpected_exception(self, cli_runner, tmp_path):
        """Test handling of unexpected exceptions during parsing."""
        parser = Mock()
        parser.parse_file.side_effect = Exception("Unexpected error")

        test_file = tmp_path / "test.fountain"
        test_file.write_text("Will cause error")

        with patch.object(
            __import__("scriptrag.parser", fromlist=["FountainParser"]),
            "FountainParser",
            return_value=parser,
        ):
            result = cli_runner.invoke(app, ["script", "info", str(test_file)])

        assert result.exit_code == 0
        assert "Unexpected error" in result.stdout

    def test_info_command_with_parentheticals_and_transitions(
        self, cli_runner, tmp_path
    ):
        """Test screenplay with parentheticals and transitions."""
        parser = Mock()
        script = Script(title="Full Elements Script", author="Author")

        scene = Scene(heading="INT. ROOM - DAY", script_order=1, script_id=uuid4())

        # Add various element types
        scene.elements = [
            Action(
                text="Character enters",
                raw_text="Character enters",
                scene_id=scene.id,
                order_in_scene=0,
            ),
            Dialogue(
                text="Hello there",
                raw_text="Hello there",
                scene_id=scene.id,
                order_in_scene=1,
                character_id=uuid4(),
                character_name="ALICE",
            ),
            Parenthetical(
                text="smiling",
                raw_text="(smiling)",
                scene_id=scene.id,
                order_in_scene=2,
            ),
            Dialogue(
                text="How are you?",
                raw_text="How are you?",
                scene_id=scene.id,
                order_in_scene=3,
                character_id=uuid4(),
                character_name="ALICE",
            ),
            Transition(
                text="CUT TO:", raw_text="CUT TO:", scene_id=scene.id, order_in_scene=4
            ),
        ]

        parser.parse_file.return_value = script
        parser.get_scenes.return_value = [scene]
        parser.get_characters.return_value = [Character(name="ALICE")]

        test_file = tmp_path / "test.fountain"
        test_file.write_text("Full elements")

        with patch.object(
            __import__("scriptrag.parser", fromlist=["FountainParser"]),
            "FountainParser",
            return_value=parser,
        ):
            result = cli_runner.invoke(app, ["script", "info", str(test_file)])

        assert result.exit_code == 0
        # Should count parentheticals and transitions properly
        assert "Total Words" in result.stdout

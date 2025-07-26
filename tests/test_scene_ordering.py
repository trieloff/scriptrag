"""Tests for scene ordering functionality."""

import pytest

from scriptrag.database import DatabaseConnection, GraphOperations
from scriptrag.database.scene_ordering import SceneOrderingOperations
from scriptrag.models import (
    Scene,
    SceneDependency,
    SceneDependencyType,
    SceneOrderType,
    Script,
)


@pytest.fixture
def ordering_ops(db_connection: DatabaseConnection) -> SceneOrderingOperations:
    """Create scene ordering operations instance."""
    return SceneOrderingOperations(db_connection)


@pytest.fixture
def graph_ops(db_connection: DatabaseConnection) -> GraphOperations:
    """Create graph operations instance."""
    return GraphOperations(db_connection)


@pytest.fixture
def sample_script(graph_ops: GraphOperations) -> tuple[str, Script]:
    """Create a sample script with scenes."""
    script = Script(
        title="Test Screenplay",
        author="Test Author",
        format="screenplay",
    )

    # Create script in database
    _ = graph_ops.create_script_graph(script)

    # Store script record
    with graph_ops.connection.transaction() as conn:
        conn.execute(
            """
            INSERT INTO scripts (id, title, author, format)
            VALUES (?, ?, ?, ?)
            """,
            (str(script.id), script.title, script.author, script.format),
        )

    return str(script.id), script


@pytest.fixture
def sample_scenes(
    graph_ops: GraphOperations,
    sample_script: tuple[str, Script],
) -> list[Scene]:
    """Create sample scenes for testing."""
    script_id, _ = sample_script
    scenes = []

    # Create scenes with various temporal indicators
    scene_data = [
        {
            "heading": "INT. COFFEE SHOP - MORNING",
            "description": "Sarah enters the coffee shop for the first time.",
            "time_of_day": "MORNING",
            "script_order": 1,
        },
        {
            "heading": "INT. OFFICE - DAY",
            "description": "Sarah meets her new boss.",
            "time_of_day": "DAY",
            "script_order": 2,
        },
        {
            "heading": "INT. COFFEE SHOP - FLASHBACK - NIGHT",
            "description": "Sarah remembers meeting John years earlier.",
            "time_of_day": "NIGHT",
            "script_order": 3,
        },
        {
            "heading": "INT. APARTMENT - EVENING",
            "description": "Sarah reflects on her first day.",
            "time_of_day": "EVENING",
            "script_order": 4,
        },
        {
            "heading": "INT. OFFICE - CONTINUOUS",
            "description": "The meeting continues.",
            "time_of_day": "DAY",
            "script_order": 5,
        },
    ]

    # Insert scenes into database
    with graph_ops.connection.transaction() as conn:
        for data in scene_data:
            scene = Scene(
                script_id=script_id,
                heading=data["heading"],
                description=data["description"],
                script_order=data["script_order"],
                time_of_day=data["time_of_day"],
            )

            conn.execute(
                """
                INSERT INTO scenes
                (id, script_id, heading, description, script_order, time_of_day)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(scene.id),
                    script_id,
                    scene.heading,
                    scene.description,
                    scene.script_order,
                    scene.time_of_day,
                ),
            )

            # Add scene elements for analysis
            conn.execute(
                """
                INSERT INTO scene_elements
                (id, scene_id, element_type, text, raw_text, order_in_scene)
                VALUES (?, ?, 'action', ?, ?, 1)
                """,
                (
                    str(scene.id) + "_action",
                    str(scene.id),
                    data["description"],
                    data["description"],
                ),
            )

            scenes.append(scene)

    return scenes


class TestSceneOrderingOperations:
    """Test scene ordering operations."""

    def test_ensure_script_order(
        self,
        ordering_ops: SceneOrderingOperations,
        sample_scenes: list[Scene],
    ) -> None:
        """Test ensuring scenes have proper script order."""
        script_id = str(sample_scenes[0].script_id)

        # Ensure script order
        success = ordering_ops.ensure_script_order(script_id)
        assert success

        # Verify all scenes have sequential order
        with ordering_ops.connection.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, script_order
                FROM scenes
                WHERE script_id = ?
                ORDER BY script_order
                """,
                (script_id,),
            )
            rows = cursor.fetchall()

            for i, (_, order) in enumerate(rows):
                assert order == i + 1

    def test_reorder_scenes(
        self,
        ordering_ops: SceneOrderingOperations,
        sample_scenes: list[Scene],
    ) -> None:
        """Test reordering scenes."""
        script_id = str(sample_scenes[0].script_id)

        # Reverse the scene order
        scene_ids = [str(s.id) for s in reversed(sample_scenes)]

        success = ordering_ops.reorder_scenes(
            script_id,
            scene_ids,
            SceneOrderType.SCRIPT,
        )
        assert success

        # Verify new order
        with ordering_ops.connection.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, script_order
                FROM scenes
                WHERE script_id = ?
                ORDER BY script_order
                """,
                (script_id,),
            )
            rows = cursor.fetchall()

            for i, (scene_id, _) in enumerate(rows):
                assert scene_id == scene_ids[i]

    def test_infer_temporal_order(
        self,
        ordering_ops: SceneOrderingOperations,
        sample_scenes: list[Scene],
    ) -> None:
        """Test inferring temporal order from scene content."""
        script_id = str(sample_scenes[0].script_id)

        # Infer temporal order
        temporal_order = ordering_ops.infer_temporal_order(script_id)

        assert len(temporal_order) == len(sample_scenes)

        # The flashback scene should be first temporally
        flashback_scene = sample_scenes[2]
        assert temporal_order[str(flashback_scene.id)] == 1

        # Morning should come before evening
        morning_scene = sample_scenes[0]
        evening_scene = sample_scenes[3]
        assert (
            temporal_order[str(morning_scene.id)]
            < temporal_order[str(evening_scene.id)]
        )

    def test_analyze_logical_dependencies(
        self,
        ordering_ops: SceneOrderingOperations,
        sample_scenes: list[Scene],
    ) -> None:
        """Test analyzing logical dependencies between scenes."""
        script_id = str(sample_scenes[0].script_id)

        # Add character to scenes for dependency analysis
        with ordering_ops.connection.transaction() as conn:
            # Add Sarah to scenes 1, 2, 4, 5
            for i in [0, 1, 3, 4]:
                conn.execute(
                    """
                    INSERT INTO scene_elements
                    (id, scene_id, element_type, text, raw_text,
                     order_in_scene, character_name)
                    VALUES (?, ?, 'dialogue', 'Hello', 'Hello', 2, 'SARAH')
                    """,
                    (
                        str(sample_scenes[i].id) + "_dialogue",
                        str(sample_scenes[i].id),
                    ),
                )

        # Analyze dependencies
        dependencies = ordering_ops.analyze_logical_dependencies(script_id)

        # Should find dependencies
        assert len(dependencies) > 0

        # Continuous scene should depend on previous
        continuous_deps = [
            d
            for d in dependencies
            if d.dependency_type == SceneDependencyType.CONTINUES
        ]
        assert len(continuous_deps) > 0

    def test_get_scene_dependencies(
        self,
        ordering_ops: SceneOrderingOperations,
        sample_scenes: list[Scene],
    ) -> None:
        """Test getting dependencies for a specific scene."""
        # Create a test dependency
        dep = SceneDependency(
            from_scene_id=sample_scenes[4].id,  # CONTINUOUS scene
            to_scene_id=sample_scenes[1].id,  # OFFICE scene
            dependency_type=SceneDependencyType.CONTINUES,
            description="Scene continues from previous",
            strength=0.9,
        )

        # Store dependency
        with ordering_ops.connection.transaction() as conn:
            conn.execute(
                """
                INSERT INTO scene_dependencies
                (id, from_scene_id, to_scene_id, dependency_type,
                 description, strength)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(dep.id),
                    str(dep.from_scene_id),
                    str(dep.to_scene_id),
                    dep.dependency_type.value,
                    dep.description,
                    dep.strength,
                ),
            )

        # Get outgoing dependencies
        outgoing = ordering_ops.get_scene_dependencies(
            str(sample_scenes[4].id),
            "from",
        )
        assert len(outgoing) == 1
        assert outgoing[0]["dependency_type"] == "continues"

        # Get incoming dependencies
        incoming = ordering_ops.get_scene_dependencies(
            str(sample_scenes[1].id),
            "to",
        )
        assert len(incoming) == 1

    def test_get_logical_order(
        self,
        ordering_ops: SceneOrderingOperations,
        sample_scenes: list[Scene],
    ) -> None:
        """Test calculating logical order based on dependencies."""
        script_id = str(sample_scenes[0].script_id)

        # Create strong dependencies
        with ordering_ops.connection.transaction() as conn:
            # Scene 5 depends on Scene 2
            conn.execute(
                """
                INSERT INTO scene_dependencies
                (id, from_scene_id, to_scene_id, dependency_type,
                 description, strength)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "dep_1",
                    str(sample_scenes[4].id),
                    str(sample_scenes[1].id),
                    "continues",
                    "Continuation",
                    0.9,
                ),
            )

        # Calculate logical order
        logical_order = ordering_ops.get_logical_order(script_id)

        assert len(logical_order) == len(sample_scenes)

        # Scene 2 should come before Scene 5 in logical order
        scene_2_idx = logical_order.index(str(sample_scenes[1].id))
        scene_5_idx = logical_order.index(str(sample_scenes[4].id))
        assert scene_2_idx < scene_5_idx

    def test_validate_ordering_consistency(
        self,
        ordering_ops: SceneOrderingOperations,
        sample_scenes: list[Scene],
    ) -> None:
        """Test validating ordering consistency."""
        script_id = str(sample_scenes[0].script_id)

        # Validate initial state
        result = ordering_ops.validate_ordering_consistency(script_id)

        assert result["is_valid"]
        assert len(result["conflicts"]) == 0

        # Create an inconsistent dependency
        with ordering_ops.connection.transaction() as conn:
            # Update logical order
            conn.execute(
                """
                UPDATE scenes SET logical_order = ? WHERE id = ?
                """,
                (1, str(sample_scenes[4].id)),
            )
            conn.execute(
                """
                UPDATE scenes SET logical_order = ? WHERE id = ?
                """,
                (2, str(sample_scenes[1].id)),
            )

            # Add dependency that violates this order
            conn.execute(
                """
                INSERT INTO scene_dependencies
                (id, from_scene_id, to_scene_id, dependency_type,
                 description, strength)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "bad_dep",
                    str(sample_scenes[4].id),
                    str(sample_scenes[1].id),
                    "requires",
                    "Violating dependency",
                    0.8,
                ),
            )

        # Validate again
        result = ordering_ops.validate_ordering_consistency(script_id)

        assert not result["is_valid"]
        assert len(result["conflicts"]) > 0
        assert result["conflicts"][0]["type"] == "dependency_violation"


class TestGraphOperationsOrdering:
    """Test scene ordering through GraphOperations."""

    def test_reorder_scenes_updates_graph(
        self,
        graph_ops: GraphOperations,
        sample_scenes: list[Scene],
        sample_script: tuple[str, Script],
    ) -> None:
        """Test that reordering scenes updates graph edges."""
        script_id, script = sample_script

        # Create script node in graph first
        script_node_id = graph_ops.create_script_graph(script)

        # Create scene nodes in graph
        scene_nodes = []
        for scene in sample_scenes:
            node_id = graph_ops.create_scene_node(
                scene,
                script_node_id,
            )
            scene_nodes.append(node_id)

        # Create initial sequence
        graph_ops.create_scene_sequence(scene_nodes, SceneOrderType.SCRIPT)

        # Reorder scenes
        reversed_ids = [str(s.id) for s in reversed(sample_scenes)]
        success = graph_ops.reorder_scenes(
            script_id,
            reversed_ids,
            SceneOrderType.SCRIPT,
        )
        assert success

    def test_get_script_scenes_with_ordering(
        self,
        graph_ops: GraphOperations,
        sample_scenes: list[Scene],
        sample_script: tuple[str, Script],
    ) -> None:
        """Test getting scenes in different orders."""
        script_id, script = sample_script

        # Create script node in graph first
        script_node_id = graph_ops.create_script_graph(script)

        # Create scene nodes
        for scene in sample_scenes:
            graph_ops.create_scene_node(scene, script_node_id)

        # Get scenes in script order
        script_ordered = graph_ops.get_script_scenes(
            script_node_id,
            SceneOrderType.SCRIPT,
        )
        assert len(script_ordered) == len(sample_scenes)

        # Verify script order
        for i, node in enumerate(script_ordered):
            assert node.properties["script_order"] == i + 1

"""Additional comprehensive tests for MCP server tool methods."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from scriptrag.mcp_server import ScriptRAGMCPServer
from scriptrag.models import Script


@pytest.fixture
def mcp_server_with_db(tmp_path):
    """Create MCP server with initialized database."""
    from scriptrag.config import ScriptRAGSettings
    from scriptrag.database.migrations import initialize_database

    # Create test settings
    settings = MagicMock(spec=ScriptRAGSettings)
    mcp_settings = MagicMock()
    mcp_settings.host = "localhost"
    mcp_settings.port = 8080
    mcp_settings.max_resources = 100
    mcp_settings.enable_all_tools = True
    settings.mcp = mcp_settings

    # Setup database
    test_db_path = tmp_path / "test.db"
    settings.database = MagicMock()
    settings.database.path = test_db_path
    settings.get_database_path = MagicMock(return_value=test_db_path)

    # Initialize database
    initialize_database(test_db_path)

    # Create server
    with patch("scriptrag.mcp_server.ScriptRAG"):
        return ScriptRAGMCPServer(settings)


class TestGetSceneDetailsTool:
    """Tests for get_scene_details tool."""

    @pytest.mark.asyncio
    async def test_get_scene_details_basic(
        self, mcp_server_with_db, sample_script, sample_scene
    ):
        """Test basic scene details retrieval."""
        from scriptrag.database.connection import DatabaseConnection

        # CONSPIRACY FIX: Create a proper script with scenes in the database
        # Use the same database path that the server will use
        db_path = str(mcp_server_with_db.config.get_database_path())

        # CRITICAL: Use get_connection() to ensure same connection pool
        with DatabaseConnection(db_path) as db_conn, db_conn.get_connection() as conn:
            # Store the script first
            conn.execute(
                """
                INSERT INTO scripts (id, title, author, format, genre,
                description, is_series)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(sample_script.id),
                    sample_script.title,
                    sample_script.author,
                    sample_script.format,
                    sample_script.genre,
                    sample_script.description,
                    sample_script.is_series,
                ),
            )

            # Update scene to use the script_id
            sample_scene.script_id = sample_script.id

            # Store the scene
            conn.execute(
                """
                INSERT INTO scenes (id, script_id, heading, description,
                script_order, temporal_order, estimated_duration_minutes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(sample_scene.id),
                    str(sample_scene.script_id),
                    sample_scene.heading,
                    sample_scene.description,
                    sample_scene.script_order,
                    sample_scene.temporal_order,
                    sample_scene.estimated_duration_minutes,
                ),
            )
            conn.commit()

        # Add script to cache - CRITICAL: Use the actual script ID as the cache key
        script_cache_id = str(sample_script.id)
        mcp_server_with_db._scripts_cache[script_cache_id] = sample_script

        # Now the scene exists and can be retrieved
        result = await mcp_server_with_db._tool_get_scene_details(
            {"script_id": script_cache_id, "scene_id": str(sample_scene.id)}
        )

        assert result["script_id"] == script_cache_id
        assert result["scene_id"] == str(sample_scene.id)
        assert "heading" in result
        assert "action" in result
        assert "dialogue" in result
        assert "characters" in result
        assert "page_number" in result

    @pytest.mark.asyncio
    async def test_get_scene_details_missing_params(self, mcp_server_with_db):
        """Test with missing parameters."""
        with pytest.raises(ValueError, match="script_id and scene_id are required"):
            await mcp_server_with_db._tool_get_scene_details({"script_id": "test"})


class TestGetCharacterRelationshipsTool:
    """Tests for get_character_relationships tool."""

    @pytest.mark.asyncio
    async def test_get_character_relationships_basic(self, mcp_server_with_db):
        """Test basic character relationships retrieval."""
        from scriptrag.models import Script

        # Add script to cache for testing
        script = Script(title="Test", source_file="test.fountain")
        mcp_server_with_db._scripts_cache["script_0"] = script

        result = await mcp_server_with_db._tool_get_character_relationships(
            {"script_id": "script_0", "character_name": "JOHN"}
        )

        assert result["script_id"] == "script_0"
        assert result["character_name"] == "JOHN"
        assert "relationships" in result
        assert "total_characters" in result

    @pytest.mark.asyncio
    async def test_get_character_relationships_no_character(self, mcp_server_with_db):
        """Test relationships for all characters."""
        from scriptrag.models import Script

        # Add script to cache for testing
        script = Script(title="Test", source_file="test.fountain")
        mcp_server_with_db._scripts_cache["script_0"] = script

        result = await mcp_server_with_db._tool_get_character_relationships(
            {"script_id": "script_0"}
        )

        assert result["character_name"] is None
        assert isinstance(result["relationships"], list)


class TestWorldElementTool:
    """Tests for add_world_element tool."""

    @pytest.mark.asyncio
    async def test_add_world_element_all_types(self, mcp_server_with_db):
        """Test adding different types of world elements."""
        from scriptrag.models import Script

        # Add script to cache for testing
        script = Script(title="Test", source_file="test.fountain")
        mcp_server_with_db._scripts_cache["script_0"] = script

        element_types = [
            "location",
            "technology",
            "culture",
            "history",
            "rule",
            "other",
        ]

        with patch("scriptrag.database.bible.ScriptBibleOperations") as mock_bible:
            mock_bible.return_value.create_world_element.return_value = "element_123"

            for element_type in element_types:
                result = await mcp_server_with_db._tool_add_world_element(
                    {
                        "script_id": "script_0",
                        "element_type": element_type,
                        "name": f"Test {element_type}",
                        "description": f"Description for {element_type}",
                        "importance_level": 3,
                    }
                )

                assert result["element_id"] == "element_123"
                assert result["element_type"] == element_type
                assert result["created"] is True


class TestTimelineEventTool:
    """Tests for create_timeline_event tool."""

    @pytest.mark.asyncio
    async def test_create_timeline_event_all_types(self, mcp_server_with_db):
        """Test creating different types of timeline events."""
        event_types = ["story", "backstory", "flashback", "flashforward", "parallel"]

        with patch("scriptrag.database.bible.ScriptBibleOperations") as mock_bible:
            mock_bible.return_value.add_timeline_event.return_value = "event_123"

            for event_type in event_types:
                result = await mcp_server_with_db._tool_create_timeline_event(
                    {
                        "timeline_id": "timeline_0",
                        "script_id": "script_0",
                        "event_name": f"{event_type.capitalize()} Event",
                        "event_type": event_type,
                        "description": f"Description for {event_type}",
                        "story_date": "2024-01-01",
                        "episode_id": "ep_01",
                    }
                )

                assert result["event_id"] == "event_123"
                assert result["event_name"] == f"{event_type.capitalize()} Event"
                assert result["created"] is True


class TestCharacterProfileTool:
    """Tests for create_character_profile tool."""

    @pytest.mark.asyncio
    async def test_create_character_profile_full(self, mcp_server_with_db):
        """Test creating a complete character profile."""
        from scriptrag.models import Script

        # Add script to cache for testing
        script = Script(title="Test", source_file="test.fountain")
        mcp_server_with_db._scripts_cache["script_0"] = script

        with patch("scriptrag.database.bible.ScriptBibleOperations") as mock_bible:
            mock_bible.return_value.create_character_profile.return_value = (
                "profile_123"
            )

            result = await mcp_server_with_db._tool_create_character_profile(
                {
                    "character_id": "char_123",
                    "script_id": "script_0",
                    "age": 35,
                    "occupation": "Detective",
                    "background": "Former military",
                    "goals": "Solve the case",
                    "fears": "Losing family",
                    "character_arc": "From cynical to hopeful",
                }
            )

            assert result["profile_id"] == "profile_123"
            assert result["character_id"] == "char_123"
            assert result["created"] is True


class TestContinuityReportTool:
    """Tests for get_continuity_report tool."""

    @pytest.mark.asyncio
    async def test_get_continuity_report(self, mcp_server_with_db):
        """Test generating continuity report."""
        with patch(
            "scriptrag.database.continuity.ContinuityValidator"
        ) as mock_validator:
            mock_report = {
                "script_title": "Test Script",
                "is_series": True,
                "validation_results": {
                    "issue_statistics": {
                        "total_issues": 5,
                        "by_severity": {"low": 2, "medium": 2, "high": 1},
                    }
                },
                "existing_notes": {
                    "note_statistics": {"by_status": {"open": 3, "resolved": 2}}
                },
                "recommendations": ["Review timeline", "Check character consistency"],
            }
            mock_validator.return_value.generate_continuity_report.return_value = (
                mock_report
            )

            result = await mcp_server_with_db._tool_get_continuity_report(
                {"script_id": "script_0"}
            )

            assert result["script_id"] == "script_0"
            assert result["script_title"] == "Test Script"
            assert result["is_series"] is True
            assert result["total_issues"] == 5
            assert result["open_notes"] == 3
            assert len(result["recommendations"]) == 2


class TestMentorStatisticsTool:
    """Tests for get_mentor_statistics tool."""

    @pytest.mark.asyncio
    async def test_get_mentor_statistics(self, mcp_server_with_db):
        """Test getting mentor statistics."""
        with (
            patch("scriptrag.database.connection.DatabaseConnection"),
            patch("scriptrag.mentors.MentorDatabaseOperations") as mock_db,
        ):
            mock_stats = {
                "total_analyses": 25,
                "by_mentor": {"McKee": 15, "Snyder": 10},
                "by_severity": {"info": 5, "suggestion": 10, "warning": 8, "error": 2},
                "by_category": {"structure": 12, "character": 8, "dialogue": 5},
            }
            mock_db.return_value.get_mentor_statistics.return_value = mock_stats

            script_id = str(uuid4())
            result = await mcp_server_with_db._tool_get_mentor_statistics(
                {"script_id": script_id}
            )

            assert result["script_id"] == script_id
            assert result["statistics"]["total_analyses"] == 25
            assert result["statistics"]["by_mentor"]["McKee"] == 15


class TestGetMentorResultsTool:
    """Tests for get_mentor_results tool."""

    @pytest.mark.asyncio
    async def test_get_mentor_results_with_limit(self, mcp_server_with_db):
        """Test getting mentor results with custom limit."""
        with (
            patch("scriptrag.database.connection.DatabaseConnection"),
            patch("scriptrag.mentors.MentorDatabaseOperations") as mock_db,
        ):
            # Create mock results
            mock_results = []
            for i in range(20):
                result = MagicMock()
                result.id = uuid4()
                result.mentor_name = "McKee"
                result.mentor_version = "1.0"
                result.summary = f"Analysis {i}"
                result.score = 0.8
                result.analysis_date.isoformat.return_value = "2024-01-01T12:00:00"
                result.analyses = []
                result.error_count = 0
                result.warning_count = 2
                result.suggestion_count = 5
                mock_results.append(result)

            mock_db.return_value.get_script_mentor_results.return_value = mock_results

            # Test with custom limit
            script_id = str(uuid4())
            result = await mcp_server_with_db._tool_get_mentor_results(
                {"script_id": script_id, "mentor_name": "McKee", "limit": 5}
            )

            assert result["results_count"] == 5
            assert len(result["results"]) == 5


class TestAnalyzeScriptWithMentorTool:
    """Tests for analyze_script_with_mentor tool."""

    @pytest.mark.asyncio
    async def test_analyze_script_save_disabled(self, mcp_server_with_db):
        """Test analyzing script without saving results."""
        with (
            patch("scriptrag.mentors.get_mentor_registry") as mock_registry,
            patch("scriptrag.database.connection.DatabaseConnection"),
            patch("scriptrag.database.operations.GraphOperations"),
            patch("scriptrag.mentors.MentorDatabaseOperations") as mock_db,
        ):
            # Setup mock mentor
            mock_mentor = AsyncMock()
            mock_result = MagicMock()
            mock_result.id = uuid4()
            mock_result.mentor_name = "McKee"
            mock_result.mentor_version = "1.0"
            mock_result.script_id = uuid4()
            mock_result.summary = "Good structure"
            mock_result.score = 0.85
            mock_result.analysis_date.isoformat.return_value = "2024-01-01T12:00:00"
            mock_result.execution_time_ms = 1500
            mock_result.analyses = []
            mock_result.error_count = 0
            mock_result.warning_count = 1
            mock_result.suggestion_count = 3

            mock_mentor.analyze_script.return_value = mock_result
            mock_registry.return_value.is_registered.return_value = True
            mock_registry.return_value.get_mentor.return_value = mock_mentor

            result = await mcp_server_with_db._tool_analyze_script_with_mentor(
                {
                    "script_id": str(uuid4()),
                    "mentor_name": "McKee",
                    "config": {"strict_mode": True},
                    "save_results": False,
                }
            )

            assert result["mentor_name"] == "McKee"
            assert result["saved_to_database"] is False
            mock_db.return_value.store_mentor_result.assert_not_called()


class TestAddCharacterKnowledgeTool:
    """Tests for add_character_knowledge tool."""

    @pytest.mark.asyncio
    async def test_add_character_knowledge_type_validation(self, mcp_server_with_db):
        """Test type validation in add_character_knowledge."""
        # Test with invalid types (not strings)
        with pytest.raises(TypeError, match="script_id must be a string"):
            await mcp_server_with_db._tool_add_character_knowledge(
                {
                    "script_id": 123,  # Invalid: not a string
                    "character_name": "JOHN",
                    "knowledge_type": "fact",
                    "knowledge_subject": "secret",
                }
            )

    @pytest.mark.asyncio
    async def test_add_character_knowledge_with_episode(self, mcp_server_with_db):
        """Test adding character knowledge with episode reference."""
        from scriptrag.database.connection import DatabaseConnection
        from scriptrag.models import Script

        # Add script to cache for testing
        script = Script(title="Test", source_file="test.fountain")
        script_id = str(script.id)
        mcp_server_with_db._scripts_cache[script_id] = script

        with DatabaseConnection(
            str(mcp_server_with_db.config.get_database_path())
        ) as conn:
            # First, insert the script into the database
            conn.execute(
                """
                INSERT INTO scripts (id, title, format, created_at, updated_at)
                VALUES (?, ?, 'screenplay', datetime('now'), datetime('now'))
                """,
                (script_id, script.title),
            )

            # Setup test data
            conn.execute(
                """
                INSERT INTO characters (
                    id, name, description, script_id, created_at, updated_at
                )
                VALUES (?, 'JOHN', '', ?, datetime('now'), datetime('now'))
            """,
                (str(uuid4()), script_id),
            )

            conn.execute(
                """
                INSERT INTO episodes (
                    id, script_id, title, number, created_at, updated_at
                )
                VALUES (?, ?, 'Pilot', 1, datetime('now'), datetime('now'))
            """,
                (str(uuid4()), script_id),
            )

            with patch("scriptrag.database.bible.ScriptBibleOperations") as mock_bible:
                mock_bible.return_value.add_character_knowledge.return_value = (
                    "knowledge_123"
                )

                result = await mcp_server_with_db._tool_add_character_knowledge(
                    {
                        "script_id": script_id,
                        "character_name": "JOHN",
                        "knowledge_type": "secret",
                        "knowledge_subject": "Identity",
                        "knowledge_description": "John is actually an undercover agent",
                        "acquired_episode": "Pilot",
                        "acquisition_method": "Revealed by partner",
                    }
                )

                assert result["knowledge_id"] == "knowledge_123"
                assert result["character_name"] == "JOHN"


class TestParseScriptToolEdgeCases:
    """Additional edge case tests for parse_script tool."""

    @pytest.mark.asyncio
    async def test_parse_script_path_traversal_attempt(self, mcp_server_with_db):
        """Test security: path traversal attempts are resolved."""
        # Path.resolve() should handle this safely
        test_path = "../../../etc/passwd"

        with pytest.raises(ValueError, match="(File not found|Invalid file type)"):
            await mcp_server_with_db._tool_parse_script({"path": test_path})

    @pytest.mark.asyncio
    async def test_parse_script_empty_file(self, mcp_server_with_db, tmp_path):
        """Test parsing empty fountain file."""
        test_file = tmp_path / "empty.fountain"
        test_file.write_text("")

        mock_script = Script(title="Untitled", source_file=str(test_file))
        mcp_server_with_db.scriptrag.parse_fountain = MagicMock(
            return_value=mock_script
        )

        result = await mcp_server_with_db._tool_parse_script({"path": str(test_file)})

        assert result["title"] == "Untitled"
        assert result["scenes_count"] == 0
        assert result["characters"] == []


class TestSearchScenesToolEdgeCases:
    """Additional edge case tests for search_scenes tool."""

    @pytest.mark.asyncio
    async def test_search_scenes_special_characters(self, mcp_server_with_db):
        """Test searching with special SQL characters."""
        from scriptrag.database.connection import DatabaseConnection
        from scriptrag.database.operations import GraphOperations

        script = Script(title="Test", source_file="test.fountain")
        script_id = f"script_{script.id.hex[:8]}"
        mcp_server_with_db._scripts_cache[script_id] = script

        with DatabaseConnection(
            str(mcp_server_with_db.config.get_database_path())
        ) as conn:
            graph_ops = GraphOperations(conn)
            script_node_id = graph_ops.create_script_graph(script)
            conn.execute(
                "UPDATE nodes SET entity_id = ? WHERE id = ?",
                (script_id, script_node_id),
            )

        # Should handle special characters safely
        result = await mcp_server_with_db._tool_search_scenes(
            {
                "script_id": script_id,
                "query": "'; DROP TABLE scenes; --",
                "location": "INT. ROOM' OR '1'='1",
                "characters": ["JOHN'; DELETE FROM characters; --"],
            }
        )

        assert result["total_matches"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_search_scenes_large_limit(self, mcp_server_with_db):
        """Test search with very large limit."""
        script = Script(title="Test", source_file="test.fountain")
        mcp_server_with_db._scripts_cache["script_0"] = script

        result = await mcp_server_with_db._tool_search_scenes(
            {"script_id": "script_0", "limit": 999999}
        )

        # Should handle large limits gracefully
        assert result["total_matches"] == 0


class TestToolIntegration:
    """Integration tests for tool interactions."""

    @pytest.mark.asyncio
    async def test_parse_and_search_workflow(self, mcp_server_with_db, tmp_path):
        """Test complete workflow: parse script then search scenes."""
        # Create test fountain file
        test_file = tmp_path / "test.fountain"
        test_file.write_text("""Title: Test Script

FADE IN:

INT. COFFEE SHOP - DAY

JOHN sits at a table, drinking coffee.

JOHN
This coffee is excellent.

FADE OUT.""")

        # Mock parse
        mock_script = Script(title="Test Script", source_file=str(test_file))
        mock_script.scenes = [MagicMock()]
        mock_script.characters = {"JOHN"}
        mcp_server_with_db.scriptrag.parse_fountain = MagicMock(
            return_value=mock_script
        )

        # Parse script
        parse_result = await mcp_server_with_db._tool_parse_script(
            {"path": str(test_file)}
        )
        script_id = parse_result["script_id"]

        # Verify script is cached
        assert script_id in mcp_server_with_db._scripts_cache

        # Search scenes
        search_result = await mcp_server_with_db._tool_search_scenes(
            {"script_id": script_id, "query": "coffee"}
        )

        assert search_result["script_id"] == script_id


class TestToolParameterValidation:
    """Tests for parameter validation across tools."""

    @pytest.mark.asyncio
    async def test_update_scene_invalid_dialogue_format(self, mcp_server_with_db):
        """Test update_scene with invalid dialogue format."""
        from scriptrag.database.connection import DatabaseConnection
        from scriptrag.database.operations import GraphOperations
        from scriptrag.models import Scene

        script = Script(title="Test", source_file="test.fountain")
        script_id = str(script.id)
        mcp_server_with_db._scripts_cache[script_id] = script

        # Create a scene first
        with DatabaseConnection(
            str(mcp_server_with_db.config.get_database_path())
        ) as conn:
            graph_ops = GraphOperations(conn)
            script_node_id = graph_ops.create_script_graph(script)
            conn.execute(
                "UPDATE nodes SET entity_id = ? WHERE id = ?",
                (script_id, script_node_id),
            )

            scene = Scene(
                id=uuid4(),
                heading="INT. ROOM - DAY",
                description="",
                script_order=1,
                script_id=script.id,
            )
            graph_ops.create_scene_node(scene, script_node_id)

            # Try updating with invalid dialogue (missing text)
            # The tool should handle this gracefully
            result = await mcp_server_with_db._tool_update_scene(
                {
                    "script_id": script_id,
                    "scene_id": scene.id,
                    "dialogue": [
                        {"character": "JOHN"}  # Missing "text" field
                    ],
                }
            )

            # Should still succeed but not add dialogue
            assert result["updated"] is True

    @pytest.mark.asyncio
    async def test_inject_scene_empty_heading(self, mcp_server_with_db):
        """Test inject_scene with empty heading."""
        with pytest.raises(
            ValueError, match="script_id, position, and heading are required"
        ):
            await mcp_server_with_db._tool_inject_scene(
                {
                    "script_id": "script_0",
                    "position": 0,
                    "heading": "",  # Empty heading
                }
            )

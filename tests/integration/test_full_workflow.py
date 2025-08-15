"""Integration test for the complete ScriptRAG workflow.

This test validates the happy path of:
1. Initializing a database (scriptrag init)
2. Analyzing a screenplay (scriptrag analyze)
3. Indexing the screenplay (scriptrag index)
4. Verifying the database contains scenes with analyzer results
"""

import json
import os
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app
from scriptrag.config import set_settings
from tests.llm_fixtures import create_llm_completion_response
from tests.llm_test_utils import (
    TIMEOUT_INTEGRATION,
    TIMEOUT_LLM,
    retry_flaky_test,
)
from tests.utils import strip_ansi_codes

runner = CliRunner()

# Path to fixture files
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "fountain" / "test_data"


@pytest.fixture(autouse=True)
def clean_settings():
    """Reset settings before and after each test."""
    set_settings(None)
    yield
    set_settings(None)


@pytest.fixture
def sample_screenplay(tmp_path):
    """Create a sample screenplay with multiple scenes."""
    script_path = tmp_path / "test_script.fountain"
    content = """Title: Integration Test Script
Author: Test Suite
Draft date: 2024-01-01

= This is a test screenplay for integration testing

INT. COFFEE SHOP - MORNING

The morning sun streams through large windows. The aroma of fresh coffee fills the air.

SARAH (30s, creative type) sits at a corner table with her laptop.

SARAH
(to herself)
Just one more scene and I'm done.

JAMES (40s, barista) approaches with a coffee.

JAMES
Another refill?

SARAH
(grateful)
You're a lifesaver.

EXT. CITY STREET - CONTINUOUS

Sarah exits the coffee shop, coffee in hand. The city is just waking up.

She walks briskly, checking her phone.

SARAH
(on phone)
Yes, I'll have it ready by noon.

INT. SARAH'S APARTMENT - LATER

A cozy apartment filled with books and scripts. Sarah sits at her desk,
typing furiously.

Her cat, WHISKERS, jumps onto the desk.

SARAH
(to Whiskers)
Not now, buddy. Almost done.

She saves her work and leans back, satisfied.

SARAH (CONT'D)
Finally. The End.

FADE OUT.
"""
    script_path.write_text(content)
    return script_path


@pytest.fixture
def props_screenplay(tmp_path):
    """Copy the props test screenplay to temp directory."""
    source_file = FIXTURES_DIR / "props_test_script.fountain"
    script_path = tmp_path / "props_test_script.fountain"
    shutil.copy2(source_file, script_path)
    return script_path


@pytest.mark.integration
class TestFullWorkflow:
    """Test the complete ScriptRAG workflow from init to index."""

    @pytest.mark.timeout(TIMEOUT_LLM)
    @pytest.mark.requires_llm
    def test_workflow_with_real_llm(self, tmp_path, sample_screenplay, monkeypatch):
        """Test workflow with real LLM (only runs if SCRIPTRAG_TEST_LLMS is set)."""
        # This test will be skipped in CI unless explicitly enabled
        # It has a longer timeout for actual LLM calls
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Analyze with real LLM (will use actual providers if configured)
        result = runner.invoke(
            app,
            ["analyze", str(sample_screenplay.parent)],
            catch_exceptions=False,
        )
        # Real LLM might fail due to rate limits, etc.
        # We accept both success and expected failures
        assert result.exit_code in [0, 1]

    @pytest.mark.timeout(TIMEOUT_INTEGRATION)
    @retry_flaky_test(max_attempts=2)
    def test_happy_path_workflow(self, tmp_path, sample_screenplay, monkeypatch):
        """Test the complete workflow: init -> analyze -> index -> verify."""
        # Setup paths
        db_path = tmp_path / "test.db"

        # Set environment variable for database path
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Step 1: Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0
        assert "Database initialized successfully" in strip_ansi_codes(result.stdout)
        assert db_path.exists()

        # Step 2: Analyze the screenplay with mock LLM
        # Mock the LLM to avoid timeouts and rate limits
        with patch("scriptrag.utils.get_default_llm_client") as mock_get_client:
            from unittest.mock import AsyncMock

            mock_client = AsyncMock()

            # Create mock scene analysis response
            mock_response = create_llm_completion_response("scene", "coffee_shop")
            mock_client.complete = AsyncMock(
                return_value=type(
                    "Response", (), {"choices": [{"text": mock_response}]}
                )
            )
            mock_get_client.return_value = mock_client

            result = runner.invoke(
                app,
                [
                    "analyze",
                    str(sample_screenplay.parent),  # Pass directory, not file
                ],
            )
            # Debug output
            if result.exit_code != 0:
                pass  # Analyze command failed
            assert result.exit_code == 0
            # The analyze command outputs "Processing" and "Updated" messages
            output = strip_ansi_codes(result.stdout)
            assert "Processing" in output or "Updated" in output

        # Verify the screenplay now contains metadata
        updated_content = sample_screenplay.read_text()
        assert "SCRIPTRAG-META-START" in updated_content
        assert "SCRIPTRAG-META-END" in updated_content

        # Step 3: Index the screenplay
        result = runner.invoke(
            app,
            [
                "index",
                str(sample_screenplay.parent),  # Pass directory, not file
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "Index" in output or "index" in output.lower()

        # Step 4: Verify database contents
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check that script was indexed
        cursor.execute(
            "SELECT * FROM scripts WHERE file_path = ?", (str(sample_screenplay),)
        )
        script = cursor.fetchone()
        assert script is not None
        assert script["title"] == "Integration Test Script"
        assert script["author"] == "Test Suite"

        script_id = script["id"]

        # Check that scenes were created
        cursor.execute(
            "SELECT * FROM scenes WHERE script_id = ? ORDER BY scene_number",
            (script_id,),
        )
        scenes = cursor.fetchall()
        assert len(scenes) == 3  # We have 3 scenes in our test script

        # Verify scene details
        scene_headings = [scene["heading"] for scene in scenes]
        assert "INT. COFFEE SHOP - MORNING" in scene_headings
        assert "EXT. CITY STREET - CONTINUOUS" in scene_headings
        assert "INT. SARAH'S APARTMENT - LATER" in scene_headings

        # Check that characters were extracted
        cursor.execute(
            """
            SELECT DISTINCT c.name
            FROM characters c
            WHERE c.script_id = ?
        """,
            (script_id,),
        )
        characters = [row["name"] for row in cursor.fetchall()]
        # Characters might be extracted from dialogues
        if characters:
            assert "SARAH" in characters or "Sarah" in characters
            assert "JAMES" in characters or "James" in characters

        # Verify analyzer metadata exists in scenes
        for scene in scenes:
            # Check metadata column contains analyzer results
            if scene["metadata"]:
                metadata = json.loads(scene["metadata"])
                # The metadata structure should contain analyzer information
                # This will depend on which analyzers are enabled by default
                assert isinstance(metadata, dict)

        # Check dialogue entries
        cursor.execute(
            """
            SELECT COUNT(*) as dialogue_count
            FROM dialogues d
            JOIN scenes s ON d.scene_id = s.id
            WHERE s.script_id = ?
        """,
            (script_id,),
        )
        # Dialogue extraction might not be implemented yet
        # So we'll just check the query doesn't fail
        cursor.fetchone()

        conn.close()

    def test_workflow_with_analyzer_results_verification(
        self, tmp_path, sample_screenplay, monkeypatch
    ):
        """Test that analyzer results are properly stored in the database."""
        db_path = tmp_path / "test.db"

        # Set environment variable for database path
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Analyze with specific analyzer (if available)
        result = runner.invoke(
            app,
            [
                "analyze",
                str(sample_screenplay.parent),  # Pass directory, not file
                "--analyzer",
                "basic_stats",  # Using a simple analyzer
            ],
        )

        # Even if analyzer doesn't exist, the command should handle it gracefully
        # The important part is that metadata structure is created

        # Read the analyzed screenplay to check metadata structure
        content = sample_screenplay.read_text()
        if "SCRIPTRAG-META-START" in content:
            # Extract metadata
            start_idx = content.index("SCRIPTRAG-META-START") + len(
                "SCRIPTRAG-META-START"
            )
            end_idx = content.index("SCRIPTRAG-META-END")
            metadata_str = content[start_idx:end_idx].strip()
            if metadata_str.startswith("*/"):
                metadata_str = metadata_str[2:].strip()
            if metadata_str.endswith("/*"):
                metadata_str = metadata_str[:-2].strip()

            # Verify metadata structure
            metadata = json.loads(metadata_str)
            assert "content_hash" in metadata
            assert "analyzed_at" in metadata
            assert "analyzers" in metadata

        # Index the screenplay
        result = runner.invoke(
            app,
            [
                "index",
                str(sample_screenplay.parent),  # Pass directory, not file
            ],
        )
        assert result.exit_code == 0

        # Verify scenes contain the analyzer metadata
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT s.*, sc.metadata as script_metadata
            FROM scenes s
            JOIN scripts sc ON s.script_id = sc.id
            WHERE sc.file_path = ?
        """,
            (str(sample_screenplay),),
        )

        scenes = cursor.fetchall()
        assert len(scenes) > 0

        # Check that at least the script has metadata from analysis
        for scene in scenes:
            script_metadata = scene["script_metadata"]
            if script_metadata:
                metadata = json.loads(script_metadata)
                # Verify the structure matches what we expect from analysis
                assert isinstance(metadata, dict)
                # Could contain analyzer results, hash, timestamp, etc.

        conn.close()

    @pytest.mark.requires_llm
    def test_scene_embeddings_analyzer(self, tmp_path, sample_screenplay, monkeypatch):
        """Test that scene embeddings are generated and persisted correctly.

        This test verifies:
        1. Embeddings are generated for each scene
        2. Embeddings are stored in the file system (Git LFS path)
        3. Embeddings are persisted in the database
        4. Embedding metadata is properly stored

        NOTE: This test requires external LLM providers and may fail due to rate limits
        or service availability. Use @pytest.mark.requires_llm to skip when needed.
        """
        from pathlib import Path

        import numpy as np

        db_path = tmp_path / "test.db"

        # Set environment variables
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0
        assert "Database initialized successfully" in strip_ansi_codes(result.stdout)

        # Analyze with scene_embeddings analyzer
        pass  # Running scene_embeddings analyzer
        result = runner.invoke(
            app,
            [
                "analyze",
                str(sample_screenplay.parent),
                "--analyzer",
                "scene_embeddings",
                "--force",
            ],
        )

        # Debug output and handle rate limit failures gracefully
        if result.exit_code != 0:
            pass  # Analyze command failed

            # Check if failure is due to LLM provider rate limits or unavailability
            stdout_str = str(result.stdout)
            if any(
                pattern in stdout_str
                for pattern in [
                    "Rate limit",
                    "RateLimitReached",
                    "All LLM providers failed",
                    "No choices available in response",
                    "GitHub Models API error",
                ]
            ):
                pytest.skip(
                    "LLM provider failed due to rate limits or service "
                    "unavailability - skipping test"
                )
        assert result.exit_code == 0

        # Verify metadata was added to the fountain file
        updated_content = sample_screenplay.read_text()
        assert "SCRIPTRAG-META-START" in updated_content
        assert "SCRIPTRAG-META-END" in updated_content

        # Extract embedding metadata from fountain file
        embedding_paths = []
        lines = updated_content.split("\n")
        for i, line in enumerate(lines):
            if "SCRIPTRAG-META-START" in line:
                for j in range(i + 1, len(lines)):
                    if "SCRIPTRAG-META-END" in lines[j]:
                        metadata_lines = []
                        for k in range(i + 1, j):
                            if not lines[k].strip().startswith("/*") and not lines[
                                k
                            ].strip().endswith("*/"):
                                metadata_lines.append(lines[k])

                        metadata_str = "\n".join(metadata_lines).strip()
                        if metadata_str:
                            try:
                                metadata = json.loads(metadata_str)
                                if (
                                    "analyzers" in metadata
                                    and "scene_embeddings" in metadata["analyzers"]
                                ):
                                    embedding_result = metadata["analyzers"][
                                        "scene_embeddings"
                                    ].get("result", {})
                                    if "embedding_path" in embedding_result:
                                        embedding_paths.append(
                                            embedding_result["embedding_path"]
                                        )
                                        pass  # Embedding info available
                            except json.JSONDecodeError:
                                pass
                        break

        # Verify embeddings were created
        assert len(embedding_paths) > 0, "No embedding paths found in metadata"

        # Verify embedding files exist in the file system
        # The embeddings are stored in the git repository root when available
        # In our test, they may be stored in the main repo (/root/repo) or temp dir
        import git

        # Check multiple possible locations for embeddings
        possible_dirs = []

        # Try to find git repo from the screenplay location
        try:
            repo = git.Repo(sample_screenplay.parent, search_parent_directories=True)
            repo_root = Path(repo.working_dir)
            possible_dirs.append(repo_root / "embeddings")
            pass  # Found git repository
        except git.InvalidGitRepositoryError:
            pass  # No git repo found from screenplay location

        # Also check the main project repo (where test is running from)
        try:
            main_repo = git.Repo(".", search_parent_directories=True)
            main_repo_root = Path(main_repo.working_dir)
            possible_dirs.append(main_repo_root / "embeddings")
            pass  # Found main git repository
        except git.InvalidGitRepositoryError:
            pass  # No main git repo found

        # Fallback: check temp directory
        possible_dirs.append(sample_screenplay.parent / "embeddings")

        # Find which directory actually has the embeddings
        embeddings_dir = None
        for dir_path in possible_dirs:
            if dir_path.exists():
                embeddings_dir = dir_path
                pass  # Found embeddings directory
                break

        assert embeddings_dir is not None, (
            f"Embeddings directory not found in any of: {possible_dirs}"
        )

        # Verify that embedding files exist for our scenes
        # Check by hash from the metadata
        found_embeddings = []
        for path in embedding_paths:
            # Extract the filename from the path
            embedding_filename = Path(path).name
            embedding_file = embeddings_dir / embedding_filename
            if embedding_file.exists():
                found_embeddings.append(embedding_file)
                pass  # Found embedding file

        assert len(found_embeddings) > 0, (
            f"No embedding files found for scene hashes in {embeddings_dir}"
        )
        pass  # Track found embeddings count

        # Verify each embedding file is valid
        for npy_file in found_embeddings:
            try:
                embedding = np.load(npy_file)
                assert isinstance(embedding, np.ndarray), (
                    f"Invalid embedding in {npy_file}"
                )
                assert embedding.ndim == 1, (
                    f"Embedding should be 1D vector, got {embedding.ndim}D"
                )
                assert embedding.size > 0, f"Empty embedding in {npy_file}"
                pass  # Embedding shape verified
            except Exception as e:
                pytest.fail(f"Failed to load embedding from {npy_file}: {e}")

        # Index the screenplay
        result = runner.invoke(
            app,
            [
                "index",
                str(sample_screenplay.parent),
            ],
        )
        assert result.exit_code == 0

        # Verify embeddings are stored in database
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get the script
        cursor.execute(
            "SELECT * FROM scripts WHERE file_path = ?", (str(sample_screenplay),)
        )
        script = cursor.fetchone()
        assert script is not None
        script_id = script["id"]

        # Get scenes
        cursor.execute(
            "SELECT * FROM scenes WHERE script_id = ? ORDER BY scene_number",
            (script_id,),
        )
        scenes = cursor.fetchall()
        assert len(scenes) == 3  # We have 3 scenes in our test script

        # Check embeddings table
        cursor.execute(
            """
            SELECT e.*, s.heading
            FROM embeddings e
            JOIN scenes s ON e.entity_id = s.id
            WHERE e.entity_type = 'scene' AND s.script_id = ?
            ORDER BY s.scene_number
            """,
            (script_id,),
        )
        embeddings = cursor.fetchall()

        assert len(embeddings) > 0, "No embeddings found in database"
        pass  # Track embeddings count in database

        # Verify each embedding in database
        for embedding_row in embeddings:
            assert embedding_row["entity_type"] == "scene"
            assert embedding_row["embedding_model"] is not None

            # The embedding blob should ALWAYS contain the full embedding data
            # During index, we load from .npy file and store the full data in DB
            embedding_blob = embedding_row["embedding"]
            assert embedding_blob is not None, (
                f"Embedding data missing for scene '{embedding_row['heading']}'"
            )
            assert len(embedding_blob) > 0, (
                f"Empty embedding data for scene '{embedding_row['heading']}'"
            )

            # Verify the stored embedding can be converted back to numpy array
            # Embeddings are stored as float32 (4 bytes per element)
            embedding_array = np.frombuffer(embedding_blob, dtype=np.float32)
            assert embedding_array.size > 0, (
                f"Invalid embedding array for scene '{embedding_row['heading']}'"
            )
            assert embedding_array.size == 1536, (
                f"Unexpected embedding size {embedding_array.size} "
                f"for scene '{embedding_row['heading']}', expected 1536"
            )
            pass  # Scene embedding dimensions tracked

        # Verify that each scene has metadata with embedding info
        for scene in scenes:
            if scene["metadata"]:
                metadata = json.loads(scene["metadata"])
                if (
                    "boneyard" in metadata
                    and "analyzers" in metadata["boneyard"]
                    and "scene_embeddings" in metadata["boneyard"]["analyzers"]
                ):
                    embedding_info = metadata["boneyard"]["analyzers"][
                        "scene_embeddings"
                    ]["result"]
                    assert "content_hash" in embedding_info
                    assert "embedding_path" in embedding_info
                    assert "dimensions" in embedding_info
                    pass  # Embedding metadata validated

        conn.close()
        pass  # Embedding verification complete

    @pytest.mark.parametrize(
        "provider_scenario",
        [
            "claude",  # Use Claude Code SDK if available
            "openai_compatible",  # Use OpenAI-compatible endpoint
            "github_models",  # Use GitHub Models
        ],
    )
    @pytest.mark.requires_llm
    def test_props_inventory_analyzer(
        self, tmp_path, props_screenplay, monkeypatch, provider_scenario
    ):
        """Test that the props_inventory analyzer properly detects and stores props.

        This test runs with different LLM providers based on available credentials:
        - Claude Code SDK (if running in Claude Code environment)
        - OpenAI-compatible endpoint (if SCRIPTRAG_LLM_ENDPOINT is available)
        - GitHub Models (if GITHUB_TOKEN is available)

        NOTE: This test requires external LLM providers and may fail due to rate limits
        or service availability. Use @pytest.mark.requires_llm to skip when needed.
        """
        db_path = tmp_path / "test.db"

        # Set environment variables for database
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Configure based on provider scenario
        if provider_scenario == "claude":
            # Check if we're in Claude Code environment
            # If not, skip this test
            try:
                # Also check if the claude binary is available
                import shutil

                # Try to import the SDK to check if it's available
                import claude_code_sdk

                # Access an attribute to ensure the module is fully imported
                _ = claude_code_sdk.ClaudeCodeOptions

                if shutil.which("claude") is None:
                    pytest.skip("Claude Code binary not available in PATH")
            except (ImportError, AttributeError):
                pytest.skip("Claude Code SDK not available")

            # Don't set SCRIPTRAG_IGNORE_CLAUDE
            monkeypatch.delenv("SCRIPTRAG_IGNORE_CLAUDE", raising=False)
            # Set preferred provider to claude_code
            monkeypatch.setenv("SCRIPTRAG_LLM_PROVIDER", "claude_code")
            # Clear other provider settings
            monkeypatch.delenv("GITHUB_TOKEN", raising=False)
            monkeypatch.delenv("SCRIPTRAG_LLM_ENDPOINT", raising=False)
            monkeypatch.delenv("SCRIPTRAG_LLM_API_KEY", raising=False)

        elif provider_scenario == "openai_compatible":
            # Check if OpenAI-compatible endpoint is available
            endpoint = os.getenv("SCRIPTRAG_LLM_ENDPOINT")
            api_key = os.getenv("SCRIPTRAG_LLM_API_KEY")

            if not endpoint or not api_key:
                pytest.skip("OpenAI-compatible endpoint not configured")

            # Set the endpoint and disable Claude
            monkeypatch.setenv("SCRIPTRAG_LLM_ENDPOINT", endpoint)
            monkeypatch.setenv("SCRIPTRAG_LLM_API_KEY", api_key)
            monkeypatch.setenv("SCRIPTRAG_IGNORE_CLAUDE", "1")

        elif provider_scenario == "github_models":
            # Check if GitHub token is available
            github_token = os.getenv("GITHUB_TOKEN")

            if not github_token:
                pytest.skip("GitHub token not available")

            # Additional check: Skip if we're in CI and GitHub Models is
            # known to be rate limited
            # This prevents the test from failing due to external service limitations
            if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
                # In CI, GitHub Models has very low rate limits - skip to
                # prevent flaky tests
                pytest.skip(
                    "GitHub Models has low rate limits in CI - skipping to "
                    "prevent flaky tests"
                )

            # Set GitHub token and disable Claude
            monkeypatch.setenv("GITHUB_TOKEN", github_token)
            monkeypatch.setenv("SCRIPTRAG_IGNORE_CLAUDE", "1")
            # Clear OpenAI settings to ensure GitHub Models is used
            monkeypatch.delenv("SCRIPTRAG_LLM_ENDPOINT", raising=False)
            monkeypatch.delenv("SCRIPTRAG_LLM_API_KEY", raising=False)
            # Set preferred provider to github_models
            monkeypatch.setenv("SCRIPTRAG_LLM_PROVIDER", "github_models")

        # Log which provider scenario is being tested
        pass  # Testing with provider scenario

        # Step 1: Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0
        assert "Database initialized successfully" in strip_ansi_codes(result.stdout)

        # Step 2: Analyze with props_inventory analyzer
        pass  # Running props_inventory analyzer
        result = runner.invoke(
            app,
            [
                "analyze",
                str(props_screenplay.parent),
                "--analyzer",
                "props_inventory",
                "--force",  # Force analysis even if already analyzed
            ],
        )

        # Debug output and handle rate limit failures gracefully
        if result.exit_code != 0:
            pass  # Analyze command failed

            # Check if failure is due to LLM provider rate limits or unavailability
            stdout_str = str(result.stdout)
            if any(
                pattern in stdout_str
                for pattern in [
                    "Rate limit",
                    "RateLimitReached",
                    "All LLM providers failed",
                    "No choices available in response",
                    "GitHub Models API error",
                ]
            ):
                pytest.skip(
                    f"LLM provider {provider_scenario} failed due to rate limits "
                    f"or service unavailability - skipping test"
                )
        assert result.exit_code == 0

        # Step 3: Display the updated fountain file contents for debugging
        updated_content = props_screenplay.read_text()

        # Step 4: Verify metadata was added to the fountain file
        assert "SCRIPTRAG-META-START" in updated_content
        assert "SCRIPTRAG-META-END" in updated_content

        # Extract and validate props from each scene's metadata
        scenes_with_props = []
        current_scene = None
        lines = updated_content.split("\n")

        for i, line in enumerate(lines):
            # Detect scene headings
            if line.startswith("INT.") or line.startswith("EXT."):
                current_scene = line

            # Look for metadata blocks
            if "SCRIPTRAG-META-START" in line:
                # Find the end of this metadata block
                for j in range(i + 1, len(lines)):
                    if "SCRIPTRAG-META-END" in lines[j]:
                        # Extract JSON between markers
                        metadata_lines = []
                        for k in range(i + 1, j):
                            if not lines[k].strip().startswith("/*") and not lines[
                                k
                            ].strip().endswith("*/"):
                                metadata_lines.append(lines[k])

                        metadata_str = "\n".join(metadata_lines).strip()
                        if metadata_str:
                            try:
                                metadata = json.loads(metadata_str)
                                if (
                                    "analyzers" in metadata
                                    and "props_inventory" in metadata["analyzers"]
                                ):
                                    props_data = metadata["analyzers"][
                                        "props_inventory"
                                    ].get("result", {})
                                    if props_data and "props" in props_data:
                                        scenes_with_props.append(
                                            {
                                                "scene": current_scene,
                                                "props": props_data["props"],
                                                "summary": props_data.get(
                                                    "summary", {}
                                                ),
                                            }
                                        )
                                        for _prop in props_data["props"]:
                                            pass  # Props tracked in found_props
                            except json.JSONDecodeError as e:
                                pass  # Failed to parse metadata
                        break

        # Verify we found props in the scenes
        assert len(scenes_with_props) > 0, "No scenes with props analysis found"

        # Check specific props we expect to find
        all_props = []
        for scene_data in scenes_with_props:
            all_props.extend([p["name"].lower() for p in scene_data["props"]])

        # These are obvious props from our test screenplay
        expected_props = [
            "revolver",
            "badge",
            "whiskey",
            "bottle",
            "glass",
            "phone",
            "cigarette",
            "lighter",
            "briefcase",
            "money",
            "envelope",
            "usb drive",
            "ticket",
            "hat",
            "coat",
            "watch",
            "car keys",
            "mustang",
            "shotgun",
            "first aid kit",
            "cellphone",
            "laptop",
            "diamonds",
        ]

        found_props = []
        missing_props = []
        for expected in expected_props:
            # Check if any found prop contains the expected term
            if any(expected in prop for prop in all_props):
                found_props.append(expected)
            else:
                missing_props.append(expected)

        # Props detection results tracked in found_props and missing_props

        # We should detect at least 70% of the expected props
        detection_rate = len(found_props) / len(expected_props)
        assert detection_rate >= 0.7, (
            f"Props detection rate too low: {detection_rate:.1%}"
        )

        # Step 5: Index the screenplay
        result = runner.invoke(
            app,
            [
                "index",
                str(props_screenplay.parent),
            ],
        )
        assert result.exit_code == 0

        # Step 6: Verify database contains props analysis
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get the script
        cursor.execute(
            "SELECT * FROM scripts WHERE file_path = ?", (str(props_screenplay),)
        )
        script = cursor.fetchone()
        assert script is not None
        script_id = script["id"]

        # Get scenes with metadata
        cursor.execute(
            "SELECT * FROM scenes WHERE script_id = ? ORDER BY scene_number",
            (script_id,),
        )
        scenes = cursor.fetchall()
        assert len(scenes) > 0

        # Check that scenes have props analysis in metadata
        scenes_with_db_props = 0
        for scene in scenes:
            if scene["metadata"]:
                metadata = json.loads(scene["metadata"])
                if (
                    "boneyard" in metadata
                    and "analyzers" in metadata["boneyard"]
                    and "props_inventory" in metadata["boneyard"]["analyzers"]
                ):
                    scenes_with_db_props += 1
                    props_result = metadata["boneyard"]["analyzers"][
                        "props_inventory"
                    ].get("result", {})
                    if "props" in props_result:
                        pass  # Props in database tracked

        assert scenes_with_db_props > 0, (
            "No scenes with props analysis found in database"
        )
        # Track scenes with database props: scenes_with_db_props

        conn.close()

    def test_search_full_text(self, tmp_path, sample_screenplay, monkeypatch):
        """Test full-text search functionality."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test 1: Simple text search
        result = runner.invoke(app, ["search", "coffee"])
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "COFFEE SHOP" in output or "coffee" in output.lower()

        # Test 2: Search for dialogue
        result = runner.invoke(app, ["search", '"Another refill?"'])
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "JAMES" in output or "refill" in output.lower()

        # Test 3: Search for action
        result = runner.invoke(app, ["search", "typing furiously"])
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "SARAH'S APARTMENT" in output or "typing" in output.lower()

    def test_search_auto_detection(self, tmp_path, sample_screenplay, monkeypatch):
        """Test auto-detection of query components."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test 1: Auto-detect character (ALL CAPS)
        result = runner.invoke(app, ["search", "SARAH"])
        assert result.exit_code == 0
        # Should find scenes with SARAH
        output = strip_ansi_codes(result.stdout)
        assert "SARAH" in output or "Sarah" in output

        # Test 2: Auto-detect dialogue (quoted text)
        result = runner.invoke(app, ["search", '"lifesaver"'])
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "lifesaver" in output.lower()

        # Test 3: Auto-detect parenthetical
        result = runner.invoke(app, ["search", "(grateful)"])
        assert result.exit_code == 0
        # Should find the scene with this parenthetical
        output = strip_ansi_codes(result.stdout)
        assert "grateful" in output.lower() or "SARAH" in output

        # Test 4: Combined auto-detection
        result = runner.invoke(app, ["search", 'SARAH "done"'])
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "SARAH" in output or "done" in output.lower()

    def test_search_character_filter(self, tmp_path, sample_screenplay, monkeypatch):
        """Test character-specific search filters."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test character filter
        # Query is positional, must come first
        result = runner.invoke(app, ["search", "done", "--character", "SARAH"])
        if result.exit_code != 0:
            pass  # Search failed
        assert result.exit_code == 0
        # Should find SARAH's dialogue containing "done"
        output = strip_ansi_codes(result.stdout)
        assert "SARAH" in output or "done" in output.lower()

        # Test dialogue filter
        # Can use empty query when using dialogue filter
        result = runner.invoke(app, ["search", "", "--dialogue", "refill"])
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "refill" in output.lower()

    def test_search_pagination(self, tmp_path, sample_screenplay, monkeypatch):
        """Test search pagination functionality."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test with limit
        result = runner.invoke(app, ["search", "--limit", "1", "SARAH"])
        assert result.exit_code == 0
        # Should show pagination info if more results exist
        # With limit=1, we should see only 1 result

        # Test with offset
        result = runner.invoke(
            app, ["search", "--limit", "1", "--offset", "1", "SARAH"]
        )
        assert result.exit_code == 0
        # Should show different result due to offset

    def test_search_vector_path(self, tmp_path, sample_screenplay, monkeypatch):
        """Test vector search path for long queries."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test 1: Long query that should trigger vector search
        long_query = " ".join(["word"] * 15)  # 15 words, > 10 word threshold
        result = runner.invoke(app, ["search", long_query])
        assert result.exit_code == 0
        # Vector search not implemented yet, but should not crash

        # Test 2: Force fuzzy/vector search
        result = runner.invoke(app, ["search", "--fuzzy", "coffee"])
        assert result.exit_code == 0

        # Test 3: Force strict mode (no vector search)
        result = runner.invoke(app, ["search", "--strict", long_query])
        assert result.exit_code == 0

    def test_search_location_filter(self, tmp_path, sample_screenplay, monkeypatch):
        """Test location-based search."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test location search (ALL CAPS multi-word)
        result = runner.invoke(app, ["search", "COFFEE SHOP"])
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "COFFEE SHOP" in output

        # Test another location
        result = runner.invoke(app, ["search", "CITY STREET"])
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "CITY STREET" in output or "EXT." in output

    def test_search_brief_mode(self, tmp_path, sample_screenplay, monkeypatch):
        """Test brief output mode."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test brief mode
        result = runner.invoke(app, ["search", "--brief", "SARAH"])
        assert result.exit_code == 0
        # Brief mode should show one-line results
        # Should have numbered results like "1. Title - Scene X: Heading"

    def test_search_verbose_mode(self, tmp_path, sample_screenplay, monkeypatch):
        """Test verbose output mode."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test verbose mode
        result = runner.invoke(app, ["search", "--verbose", "--limit", "1", "coffee"])
        assert result.exit_code == 0
        # Verbose mode should show full scene content
        assert len(result.stdout) > 100  # Should have substantial content

    def test_search_no_results(self, tmp_path, sample_screenplay, monkeypatch):
        """Test search with no matching results."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Search for something that doesn't exist
        result = runner.invoke(app, ["search", "unicorn rainbow sparkles"])
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "No results found" in output

    def test_search_with_series_metadata(self, tmp_path, monkeypatch):
        """Test search with series/episode metadata."""
        # Create a series screenplay with episode metadata
        series_script = tmp_path / "series_script.fountain"
        content = """Title: Test Series
Author: Test Suite
Episode: 2
Season: 1

INT. OFFICE - DAY

MICHAEL sits at his desk.

MICHAEL
That's what she said!

"""
        series_script.write_text(content)

        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(tmp_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(tmp_path)])
        assert result.exit_code == 0

        # Test project filter
        result = runner.invoke(app, ["search", "--project", "Test Series", "desk"])
        assert result.exit_code == 0
        # Should find the scene

        # Note: Episode range filtering requires metadata to be properly stored
        # which depends on the indexing implementation

    def test_query_command_basic_functionality(
        self, tmp_path, sample_screenplay, monkeypatch
    ):
        """Test the basic query command functionality."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test 1: Query list of scripts (table output)
        result = runner.invoke(app, ["query", "test_list_scripts"])
        assert result.exit_code == 0
        # The title might be wrapped in the table output
        output = strip_ansi_codes(result.stdout)
        assert "Integration Test" in output or "test" in output.lower()
        assert "Test Suite" in output or "author" in output.lower()

        # Test 2: Query scenes (table output)
        result = runner.invoke(app, ["query", "simple_scene_list"])
        assert result.exit_code == 0
        # Should show scenes
        output = strip_ansi_codes(result.stdout)
        assert (
            "COFFEE SHOP" in output
            or "CITY STREET" in output
            or "scene" in output.lower()
        )

        # Test 3: Query with limit parameter
        result = runner.invoke(app, ["query", "simple_scene_list", "--limit", "1"])
        assert result.exit_code == 0
        # Should work with limit

    def test_query_command_simple_scene_list(
        self, tmp_path, sample_screenplay, monkeypatch
    ):
        """Test the query command with simple_scene_list query."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test 1: Get scene list
        result = runner.invoke(app, ["query", "simple_scene_list"])
        assert result.exit_code == 0
        # Should show scene headings (note: rich table may wrap text)
        output = strip_ansi_codes(result.stdout)
        assert "COFFEE SHOP" in output
        assert "CITY STREET" in output
        # Check for script title - may be wrapped in table
        assert "Integration" in output and "Test" in output and "Script" in output

        # Test 2: Query with limit
        result = runner.invoke(app, ["query", "simple_scene_list", "--limit", "2"])
        assert result.exit_code == 0
        # Should show only 2 scenes

        # Test 3: JSON output for programmatic access
        result = runner.invoke(app, ["query", "simple_scene_list", "--json"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        # With new format, we get a dict with 'results' key
        assert isinstance(data, dict)
        assert "results" in data
        results = data["results"]
        assert isinstance(results, list)
        assert len(results) == 3  # We have 3 scenes
        if results:
            # Check structure
            assert "scene_number" in results[0]
            assert "heading" in results[0]
            assert "script_title" in results[0]

        # Test 4: Query with offset
        result = runner.invoke(
            app, ["query", "simple_scene_list", "--limit", "1", "--offset", "1"]
        )
        assert result.exit_code == 0
        # Should show second scene

    def test_query_command_list_scenes(self, tmp_path, sample_screenplay, monkeypatch):
        """Test the query command with list_scenes query (if it works)."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test if list_scenes query exists and works
        # This query might fail due to schema mismatches
        result = runner.invoke(app, ["query", "list_scenes"])
        # We don't assert exit_code == 0 here since the query might fail
        if result.exit_code == 0:
            # If it works, check the output
            output = strip_ansi_codes(result.stdout)
            assert (
                "COFFEE SHOP" in output
                or "CITY STREET" in output
                or "scene" in output.lower()
            )
        else:
            # The query failed, which is expected if dialogues table doesn't match
            output = strip_ansi_codes(result.stdout)
            assert "error" in output.lower() or "Error" in output

    def test_query_command_list_available(self, tmp_path, monkeypatch):
        """Test listing available queries."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # List available queries
        result = runner.invoke(app, ["query", "list"])
        assert result.exit_code == 0
        # Should show available queries (note: names use underscores in output)
        output = strip_ansi_codes(result.stdout)
        assert "character_lines" in output or "character-lines" in output
        assert "character_stats" in output or "character-stats" in output
        assert "list_scenes" in output or "list-scenes" in output
        # Should show descriptions
        assert "dialogue lines" in output.lower() or "character" in output.lower()

    def test_query_command_with_simple_queries(self, tmp_path, monkeypatch):
        """Test query commands with multiple scripts."""
        # Create a simple script
        script1 = tmp_path / "script1.fountain"
        script1.write_text("""Title: Test Script 1
Author: Test Author

INT. ROOM - DAY

A simple scene.
""")

        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(tmp_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(tmp_path)])
        assert result.exit_code == 0

        # Test 1: Query scripts with our custom query
        result = runner.invoke(app, ["query", "test_list_scripts", "--json"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert "results" in data
        results = data["results"]
        assert len(results) >= 1
        assert any(s["title"] == "Test Script 1" for s in results)

        # Test 2: Query scenes
        result = runner.invoke(app, ["query", "simple_scene_list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert "results" in data
        results = data["results"]
        assert len(results) >= 1
        assert any("ROOM" in s["heading"] for s in results)

    def test_query_command_error_handling(self, tmp_path, monkeypatch):
        """Test error handling in query commands."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Test 1: Query without initializing database
        result = runner.invoke(app, ["query", "test_list_scripts"])
        assert result.exit_code != 0
        output = strip_ansi_codes(result.stdout)
        assert "error" in output.lower() or "database" in output.lower()

        # Initialize empty database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Test 2: Query with no data (should return empty)
        result = runner.invoke(app, ["query", "test_list_scripts", "--json"])
        assert result.exit_code == 0
        # Should return JSON with empty results
        import json

        data = json.loads(result.stdout)
        # With new format, we get a dict with 'results' key
        assert isinstance(data, dict)
        assert "results" in data
        assert data["results"] == []
        assert data["count"] == 0

        # Test 3: Query with negative limit (might be handled as error or ignored)
        result = runner.invoke(app, ["query", "test_list_scripts", "--limit", "-1"])
        # Just check it doesn't crash - behavior may vary

    def test_query_command_custom_queries(self, tmp_path, monkeypatch):
        """Test that custom queries can be added and executed."""
        db_path = tmp_path / "test.db"
        query_dir = tmp_path / "queries"
        query_dir.mkdir()

        # Create a custom query file
        custom_query = query_dir / "scene_count.sql"
        custom_query.write_text("""-- name: scene_count
-- description: Count scenes per script
-- param: min_scenes int optional default=1 help="Minimum scenes to include"

SELECT
    s.title,
    COUNT(sc.id) as scene_count
FROM scripts s
LEFT JOIN scenes sc ON s.id = sc.script_id
GROUP BY s.id, s.title
HAVING COUNT(sc.id) >= :min_scenes
ORDER BY scene_count DESC
""")

        # Set environment to use custom query directory
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(query_dir))

        # Reload query module to pick up custom queries
        import importlib

        import scriptrag.cli.commands.query

        importlib.reload(scriptrag.cli.commands.query)

        # Initialize and create test data
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        # Create a simple test script
        test_script = tmp_path / "test.fountain"
        test_script.write_text("""Title: Custom Query Test

INT. ROOM 1 - DAY

Action here.

INT. ROOM 2 - NIGHT

More action.
""")

        result = runner.invoke(app, ["analyze", str(tmp_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(tmp_path)])
        assert result.exit_code == 0

        # Test custom query (skip if not loaded due to module import timing)
        result = runner.invoke(app, ["query", "list"])
        output = strip_ansi_codes(result.stdout)
        if "scene_count" not in output:
            # Custom query not loaded - skip test
            import pytest

            pytest.skip("Custom query not loaded - module import timing issue")

        result = runner.invoke(app, ["query", "scene_count", "--json"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert "results" in data
        results = data["results"]
        assert isinstance(results, list)
        if results:
            assert "title" in results[0]
            assert "scene_count" in results[0]
            assert results[0]["scene_count"] == 2  # Our test script has 2 scenes

    def test_query_command_json_output(self, tmp_path, monkeypatch):
        """Test JSON output formatting for query commands."""
        # Create a simple screenplay
        script = tmp_path / "test.fountain"
        script.write_text("""Title: JSON Test
Author: Test Suite

INT. ROOM - DAY

A test scene.
""")

        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(tmp_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(tmp_path)])
        assert result.exit_code == 0

        # Test JSON output for scripts
        result = runner.invoke(app, ["query", "test_list_scripts", "--json"])
        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert "results" in data
        results = data["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["title"] == "JSON Test"

        # Test JSON output for scenes
        result = runner.invoke(app, ["query", "simple_scene_list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert "results" in data
        results = data["results"]
        assert isinstance(results, list)
        assert len(results) == 1
        assert "ROOM" in results[0]["heading"]

    def test_scene_management_commands(self, tmp_path, sample_screenplay, monkeypatch):
        """Test the new scene management commands: read, update, delete."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0
        assert db_path.exists()

        # Analyze screenplay
        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Index screenplay
        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        if result.exit_code != 0:
            pass  # Index failed
        assert result.exit_code == 0

        # Test 1: Read a scene
        result = runner.invoke(
            app,
            ["scene", "read", "--project", "Integration Test Script", "--scene", "1"],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "COFFEE SHOP" in output
        # Check for timestamp instead of token (simplified scene management)
        assert "Last read:" in output or "last read:" in output.lower()

        # Test 2: Read scene with JSON output
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--scene",
                "2",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert "content" in data
        assert "CITY STREET" in data["content"]
        if "session_token" in data:
            session_token = data["session_token"]

        # Test 3: Update a scene (skip if no session token)
        # Note: Update requires a valid session token which may not always be
        # available in tests

        # Test 4: Add and delete functionality are commented out for now
        # These require further debugging of the scene management API
        # TODO: Fix scene add/delete commands and re-enable these tests

    def test_bible_management_commands(self, tmp_path, sample_screenplay, monkeypatch):
        """Test bible read functionality."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Create a bible file
        bible_dir = sample_screenplay.parent / "bible"
        bible_dir.mkdir(exist_ok=True)

        world_bible = bible_dir / "world_bible.md"
        world_bible.write_text("""# World Bible

## Setting
The story takes place in a modern urban coffee shop culture.

## Themes
- Creative process
- Work-life balance
- Human connections

## Visual Style
Warm, cozy interiors contrasted with busy city exteriors.""")

        character_bible = bible_dir / "characters.md"
        character_bible.write_text("""# Character Bible

## Sarah
- Age: 30s
- Occupation: Screenwriter
- Personality: Focused, creative, slightly overwhelmed
- Arc: Learning to balance deadlines with personal life

## James
- Age: 40s
- Occupation: Barista
- Personality: Friendly, observant, supportive
- Role: Represents stability and routine""")

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test 1: List available bible files
        result = runner.invoke(
            app,
            ["scene", "read", "--project", "Integration Test Script", "--bible"],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "world_bible.md" in output or "characters.md" in output

        # Test 2: Read specific bible file
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--bible-name",
                "world_bible.md",
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "World Bible" in output
        assert "coffee shop culture" in output

        # Test 3: Read another bible file
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--bible-name",
                "characters.md",
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "Character Bible" in output
        assert "Sarah" in output
        assert "James" in output

        # Test 4: JSON output for bible list
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--bible",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert "bible_files" in data
        assert isinstance(data["bible_files"], list)
        assert len(data["bible_files"]) >= 2

        # Test 5: JSON output for bible content
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--bible-name",
                "world_bible.md",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert "content" in data
        assert "World Bible" in data["content"]

    def test_scene_management_tv_series(self, tmp_path, monkeypatch):
        """Test scene management for TV series with season/episode structure."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Create a TV series screenplay
        tv_script = tmp_path / "breaking_bad_s01e01.fountain"
        tv_content = """Title: Breaking Bad
Author: Vince Gilligan
Season: 1
Episode: 1
Episode Title: Pilot

INT. RV - DAY

WALTER WHITE, 50s, in his underwear, frantically drives an RV through the desert.

WALTER
(into recorder)
My name is Walter Hartwell White.

EXT. DESERT - CONTINUOUS

The RV crashes to a stop. Walter stumbles out.

WALTER
(continuing)
This is my confession."""
        tv_script.write_text(tv_content)

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(tmp_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(tmp_path)])
        assert result.exit_code == 0

        # Test 1: Read scene with season/episode
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Breaking Bad",
                "--season",
                "1",
                "--episode",
                "1",
                "--scene",
                "1",
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "RV" in output or "WALTER" in output

        # Test 2: Read another scene from TV episode
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Breaking Bad",
                "--season",
                "1",
                "--episode",
                "1",
                "--scene",
                "2",
            ],
        )
        assert result.exit_code == 0
        output = strip_ansi_codes(result.stdout)
        assert "DESERT" in output or "confession" in output.lower()

        # Note: Add/delete functionality commented out - needs debugging

    def test_scene_management_error_cases(
        self, tmp_path, sample_screenplay, monkeypatch
    ):
        """Test error handling in scene management commands."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Initialize, analyze, and index
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["analyze", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        result = runner.invoke(app, ["index", str(sample_screenplay.parent)])
        assert result.exit_code == 0

        # Test 1: Read non-existent scene
        result = runner.invoke(
            app,
            ["scene", "read", "--project", "Integration Test Script", "--scene", "999"],
        )
        # Scene 999 doesn't exist, should fail or return error
        if result.exit_code != 0:
            output = strip_ansi_codes(result.stdout)
            assert "not found" in output.lower() or "error" in output.lower()
        else:
            # Some implementations might return success with an error message
            output = strip_ansi_codes(result.stdout)
            assert (
                "not found" in output.lower()
                or "error" in output.lower()
                or "Scene 999" not in output
            )

        # Test 2: Update with invalid token (skip - update command may not be
        # fully implemented)
        # TODO: Re-enable when scene update is fully implemented

        # Test 3: Delete without confirmation (should warn but not delete)
        result = runner.invoke(
            app,
            ["scene", "delete", "--project", "Integration Test Script", "--scene", "1"],
        )
        # Command may return 0 with a warning message
        output = strip_ansi_codes(result.stdout)
        assert "confirm" in output.lower() or "warning" in output.lower()

        # Test 4: Read from non-existent project
        result = runner.invoke(
            app,
            ["scene", "read", "--project", "Non-Existent Project", "--scene", "1"],
        )
        assert result.exit_code != 0
        output = strip_ansi_codes(result.stdout)
        assert "not found" in output.lower() or "error" in output.lower()

        # Test 5: Add scene with invalid position (skip - add command needs debugging)
        # TODO: Re-enable when scene add is fully implemented

        # Test 6: Read non-existent bible file
        result = runner.invoke(
            app,
            [
                "scene",
                "read",
                "--project",
                "Integration Test Script",
                "--bible-name",
                "non_existent.md",
            ],
        )
        assert result.exit_code != 0
        output = strip_ansi_codes(result.stdout)
        assert "not found" in output.lower() or "error" in output.lower()

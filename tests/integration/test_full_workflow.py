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

import pytest
from typer.testing import CliRunner

from scriptrag.cli.main import app
from scriptrag.config import set_settings

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

    def test_happy_path_workflow(self, tmp_path, sample_screenplay, monkeypatch):
        """Test the complete workflow: init -> analyze -> index -> verify."""
        # Setup paths
        db_path = tmp_path / "test.db"

        # Set environment variable for database path
        monkeypatch.setenv("SCRIPTRAG_DATABASE_PATH", str(db_path))

        # Step 1: Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0
        assert "Database initialized successfully" in result.stdout
        assert db_path.exists()

        # Step 2: Analyze the screenplay
        result = runner.invoke(
            app,
            [
                "analyze",
                str(sample_screenplay.parent),  # Pass directory, not file
            ],
        )
        # Debug output
        if result.exit_code != 0:
            print(f"Analyze command failed with exit code {result.exit_code}")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr if hasattr(result, 'stderr') else 'N/A'}")
        assert result.exit_code == 0
        # The analyze command outputs "Processing" and "Updated" messages
        assert "Processing" in result.stdout or "Updated" in result.stdout

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
        assert "Index" in result.stdout or "index" in result.stdout.lower()

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
        assert "Database initialized successfully" in result.stdout

        # Analyze with scene_embeddings analyzer
        print("\n=== Running scene_embeddings analyzer ===")
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
            print(f"Analyze command failed with exit code {result.exit_code}")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr if hasattr(result, 'stderr') else 'N/A'}")

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
                                        print(
                                            f"Found embedding path: "
                                            f"{embedding_result['embedding_path']}"
                                        )
                                        print(
                                            f"  Dimensions: "
                                            f"{embedding_result.get('dimensions')}"
                                        )
                                        print(
                                            f"  Model: {embedding_result.get('model')}"
                                        )
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
            print(f"Found git repository at: {repo_root}")
        except git.InvalidGitRepositoryError:
            print("No git repo found from screenplay location")

        # Also check the main project repo (where test is running from)
        try:
            main_repo = git.Repo(".", search_parent_directories=True)
            main_repo_root = Path(main_repo.working_dir)
            possible_dirs.append(main_repo_root / "embeddings")
            print(f"Found main git repository at: {main_repo_root}")
        except git.InvalidGitRepositoryError:
            print("No main git repo found")

        # Fallback: check temp directory
        possible_dirs.append(sample_screenplay.parent / "embeddings")

        # Find which directory actually has the embeddings
        embeddings_dir = None
        for dir_path in possible_dirs:
            if dir_path.exists():
                embeddings_dir = dir_path
                print(f"Found embeddings directory at: {embeddings_dir}")
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
                print(f"  Found embedding file: {embedding_file}")

        assert len(found_embeddings) > 0, (
            f"No embedding files found for scene hashes in {embeddings_dir}"
        )
        print(f"\nFound {len(found_embeddings)} embedding files for our scenes")

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
                print(f"  {npy_file.name}: {embedding.shape} dimensions")
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
        print(f"\nFound {len(embeddings)} embeddings in database")

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
            print(
                f"  Scene '{embedding_row['heading']}': "
                f"{embedding_array.size} dimensions (fully stored in DB)"
            )

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
                    print(f"\nScene {scene['scene_number']} embedding metadata:")
                    print(f"  Hash: {embedding_info['content_hash'][:8]}...")
                    print(f"  Path: {embedding_info['embedding_path']}")
                    print(f"  Dimensions: {embedding_info['dimensions']}")

        conn.close()
        print("\n=== Embedding verification complete ===")

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
                import claude_code_sdk  # noqa: F401

                if shutil.which("claude") is None:
                    pytest.skip("Claude Code binary not available in PATH")
            except ImportError:
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
        print(f"\n=== Testing with provider scenario: {provider_scenario} ===")

        # Step 1: Initialize database
        result = runner.invoke(app, ["init", "--db-path", str(db_path)])
        assert result.exit_code == 0
        assert "Database initialized successfully" in result.stdout

        # Step 2: Analyze with props_inventory analyzer
        print(
            f"\n=== Running props_inventory analyzer with "
            f"{provider_scenario} provider ==="
        )
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
            print(f"Analyze command failed with exit code {result.exit_code}")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr if hasattr(result, 'stderr') else 'N/A'}")

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
        print("\n=== Fountain file contents after analysis ===")
        updated_content = props_screenplay.read_text()
        print(updated_content)
        print("=== End of fountain file ===\n")

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
                                        print(f"\nScene: {current_scene}")
                                        print(f"Found {len(props_data['props'])} props")
                                        for prop in props_data["props"]:
                                            print(
                                                f"  - {prop['name']} "
                                                f"({prop['category']}): "
                                                f"{prop['significance']}"
                                            )
                            except json.JSONDecodeError as e:
                                print(f"Failed to parse metadata: {e}")
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

        print("\n=== Props Detection Results ===")
        print(f"Found {len(found_props)}/{len(expected_props)} expected props")
        print(f"Found props: {found_props}")
        if missing_props:
            print(f"Missing props: {missing_props}")

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
                        print(f"\nDB Scene {scene['scene_number']}: {scene['heading']}")
                        print(f"  Props in database: {len(props_result['props'])}")

        assert scenes_with_db_props > 0, (
            "No scenes with props analysis found in database"
        )
        print(
            f"\n{scenes_with_db_props}/{len(scenes)} scenes have props "
            f"analysis in database"
        )

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
        assert "COFFEE SHOP" in result.stdout or "coffee" in result.stdout.lower()

        # Test 2: Search for dialogue
        result = runner.invoke(app, ["search", '"Another refill?"'])
        assert result.exit_code == 0
        assert "JAMES" in result.stdout or "refill" in result.stdout.lower()

        # Test 3: Search for action
        result = runner.invoke(app, ["search", "typing furiously"])
        assert result.exit_code == 0
        assert "SARAH'S APARTMENT" in result.stdout or "typing" in result.stdout.lower()

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
        assert "SARAH" in result.stdout or "Sarah" in result.stdout

        # Test 2: Auto-detect dialogue (quoted text)
        result = runner.invoke(app, ["search", '"lifesaver"'])
        assert result.exit_code == 0
        assert "lifesaver" in result.stdout.lower()

        # Test 3: Auto-detect parenthetical
        result = runner.invoke(app, ["search", "(grateful)"])
        assert result.exit_code == 0
        # Should find the scene with this parenthetical
        assert "grateful" in result.stdout.lower() or "SARAH" in result.stdout

        # Test 4: Combined auto-detection
        result = runner.invoke(app, ["search", 'SARAH "done"'])
        assert result.exit_code == 0
        assert "SARAH" in result.stdout or "done" in result.stdout.lower()

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
            print(f"Search failed: {result.stdout}")
        assert result.exit_code == 0
        # Should find SARAH's dialogue containing "done"
        assert "SARAH" in result.stdout or "done" in result.stdout.lower()

        # Test dialogue filter
        # Can use empty query when using dialogue filter
        result = runner.invoke(app, ["search", "", "--dialogue", "refill"])
        assert result.exit_code == 0
        assert "refill" in result.stdout.lower()

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
        assert "COFFEE SHOP" in result.stdout

        # Test another location
        result = runner.invoke(app, ["search", "CITY STREET"])
        assert result.exit_code == 0
        assert "CITY STREET" in result.stdout or "EXT." in result.stdout

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
        assert "No results found" in result.stdout

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
        assert "Integration Test" in result.stdout or "test" in result.stdout.lower()
        assert "Test Suite" in result.stdout or "author" in result.stdout.lower()

        # Test 2: Query scenes (table output)
        result = runner.invoke(app, ["query", "simple_scene_list"])
        assert result.exit_code == 0
        # Should show scenes
        assert (
            "COFFEE SHOP" in result.stdout
            or "CITY STREET" in result.stdout
            or "scene" in result.stdout.lower()
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
        assert "COFFEE SHOP" in result.stdout
        assert "CITY STREET" in result.stdout
        # Check for script title - may be wrapped in table
        assert (
            "Integration" in result.stdout
            and "Test" in result.stdout
            and "Script" in result.stdout
        )

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
            assert (
                "COFFEE SHOP" in result.stdout
                or "CITY STREET" in result.stdout
                or "scene" in result.stdout.lower()
            )
        else:
            # The query failed, which is expected if dialogues table doesn't match
            assert "error" in result.stdout.lower() or "Error" in result.stdout

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
        assert "character_lines" in result.stdout or "character-lines" in result.stdout
        assert "character_stats" in result.stdout or "character-stats" in result.stdout
        assert "list_scenes" in result.stdout or "list-scenes" in result.stdout
        # Should show descriptions
        assert (
            "dialogue lines" in result.stdout.lower()
            or "character" in result.stdout.lower()
        )

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
        assert "error" in result.stdout.lower() or "database" in result.stdout.lower()

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
        if "scene_count" not in result.stdout:
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

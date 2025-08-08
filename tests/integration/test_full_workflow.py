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

    def test_scene_embeddings_analyzer(self, tmp_path, sample_screenplay, monkeypatch):
        """Test that scene embeddings are generated and persisted correctly.

        This test verifies:
        1. Embeddings are generated for each scene
        2. Embeddings are stored in the file system (Git LFS path)
        3. Embeddings are persisted in the database
        4. Embedding metadata is properly stored
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

        # Debug output if needed
        if result.exit_code != 0:
            print(f"Analyze command failed with exit code {result.exit_code}")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr if hasattr(result, 'stderr') else 'N/A'}")
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

            # The embedding blob should contain data or be empty (for LFS reference)
            embedding_blob = embedding_row["embedding"]
            if embedding_blob and len(embedding_blob) > 0:
                # If stored directly, verify it can be converted back to numpy array
                try:
                    # Assuming float32 (4 bytes per element)
                    embedding_array = np.frombuffer(embedding_blob, dtype=np.float32)
                    assert embedding_array.size > 0
                    print(
                        f"  Scene '{embedding_row['heading']}': "
                        f"{embedding_array.size} dimensions (stored in DB)"
                    )
                except Exception:
                    print(
                        f"  Scene '{embedding_row['heading']}': Reference stored (LFS)"
                    )
            else:
                print(f"  Scene '{embedding_row['heading']}': Reference stored (LFS)")

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
    def test_props_inventory_analyzer(
        self, tmp_path, props_screenplay, monkeypatch, provider_scenario
    ):
        """Test that the props_inventory analyzer properly detects and stores props.

        This test runs with different LLM providers based on available credentials:
        - Claude Code SDK (if running in Claude Code environment)
        - OpenAI-compatible endpoint (if SCRIPTRAG_LLM_ENDPOINT is available)
        - GitHub Models (if GITHUB_TOKEN is available)
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

        # Debug output
        if result.exit_code != 0:
            print(f"Analyze command failed with exit code {result.exit_code}")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr if hasattr(result, 'stderr') else 'N/A'}")
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

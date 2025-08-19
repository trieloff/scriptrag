import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from scriptrag.agents.context_query import ContextParameters


@dataclass
class _FakeScene:
    content_hash: str


@dataclass
class _FakeScript:
    # Intentionally omit file_path to force metadata fallback path
    metadata: dict = field(default_factory=dict)
    scenes: list = field(default_factory=list)


@pytest.mark.unit
def test_context_params_uses_metadata_source_file_when_no_file_path(tmp_path: Path):
    """
    Verify script_id derives from metadata['source_file'] when file_path is absent.
    """
    source_file = tmp_path / "project" / "script.fountain"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("TITLE: Test\n\nINT. ROOM - DAY\n")

    # Fake script missing file_path but with metadata['source_file'] set
    script = _FakeScript(
        metadata={"source_file": str(source_file)},
        scenes=[_FakeScene(content_hash="scene_hash_demo")],
    )

    # Provide a scene dict with raw text to trigger hash computation path
    scene_dict = {"original_text": "Some scene content"}

    params = ContextParameters.from_scene(
        scene=scene_dict, script=script, settings=None
    )

    # Expect script_id computed from metadata['source_file'] and file_path populated
    expected_id = hashlib.sha256(str(source_file).encode()).hexdigest()[:12]
    assert params.script_id == expected_id
    assert params.file_path == str(source_file)

    # Project name should default to parent directory name when settings is None
    assert params.project_name == source_file.parent.name

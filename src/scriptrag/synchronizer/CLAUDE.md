# Git Synchronizer Component

This directory contains the Git synchronization system that manages Git hooks, detects changes, and orchestrates the processing pipeline.

## Architecture Role

The Git Synchronizer is a **processing component** that:

- Reads from Fountain Files in Git Repository
- Writes to Git LFS storage for embeddings
- Calls Fountain Parser and Database Indexer
- Manages Git hooks for automatic processing

## Key Responsibilities

1. **Git Hook Management**
   - Install/configure pre-commit hooks
   - Detect changed scenes via content hashes
   - Trigger processing pipeline

2. **Change Detection**
   - Compare content hashes
   - Identify new/modified/deleted scenes
   - Track file moves and renames

3. **Pipeline Orchestration**
   - Coordinate parser → extractor → embeddings flow
   - Update boneyard metadata in Fountain files
   - Manage Git LFS operations

## Implementation Guidelines

```python
import git
from typing import List, Set, Dict, Optional
from pathlib import Path
import json

from ..models import Scene, ChangeSet
from ..parser import FountainParser
from ..storage.git import GitStorage
from ..exceptions import SynchronizerError


class GitSynchronizer:
    """Manage Git operations and change detection."""

    def __init__(
        self,
        repo_path: Optional[Path] = None,
        parser: Optional[FountainParser] = None
    ):
        self.repo_path = repo_path or Path.cwd()
        self.repo = git.Repo(self.repo_path)
        self.parser = parser or FountainParser()
        self.git_storage = GitStorage(self.repo)

    def install_hooks(self):
        """Install Git hooks for automatic processing."""
        hooks_dir = self.repo_path / ".git" / "hooks"

        # Pre-commit hook
        pre_commit = hooks_dir / "pre-commit"
        pre_commit.write_text('''#!/bin/bash
# ScriptRAG pre-commit hook
scriptrag sync --staged
''')
        pre_commit.chmod(0o755)

        # Post-checkout hook
        post_checkout = hooks_dir / "post-checkout"
        post_checkout.write_text('''#!/bin/bash
# ScriptRAG post-checkout hook
scriptrag sync --all
''')
        post_checkout.chmod(0o755)

    def detect_changes(self, staged_only: bool = False) -> ChangeSet:
        """Detect changed Fountain files and scenes."""
        changes = ChangeSet()

        # Get modified fountain files
        if staged_only:
            files = self._get_staged_fountain_files()
        else:
            files = self._get_modified_fountain_files()

        for file_path in files:
            old_scenes = self._get_scenes_from_blob(file_path, "HEAD")
            new_scenes = self._parse_current_file(file_path)

            # Compare by content hash
            old_hashes = {s.content_hash for s in old_scenes}
            new_hashes = {s.content_hash for s in new_scenes}

            changes.added.update(new_hashes - old_hashes)
            changes.removed.update(old_hashes - new_hashes)
            changes.modified_files.add(file_path)

        return changes

    def process_changes(self, changes: ChangeSet):
        """Process detected changes through pipeline."""
        for file_path in changes.modified_files:
            # Parse current file
            script = self.parser.parse_file(file_path)

            # Process only changed scenes
            for scene in script.scenes:
                if scene.content_hash in changes.added:
                    # Trigger processing pipeline
                    self._process_new_scene(scene, file_path)

            # Update file with new boneyard data
            self._update_fountain_file(file_path, script)
```

## Change Detection

```python
def _get_scenes_from_blob(
    self,
    file_path: Path,
    ref: str
) -> List[Scene]:
    """Extract scenes from a git blob."""
    try:
        # Get file content from git
        blob = self.repo.oid[ref + ":" + str(file_path)]
        content = blob.data.decode('utf-8')

        # Parse scenes
        script = self.parser.parse(content)
        return script.scenes
    except KeyError:
        # File doesn't exist in ref
        return []

def _compare_scenes(
    self,
    old_scenes: List[Scene],
    new_scenes: List[Scene]
) -> Dict[str, List[Scene]]:
    """Compare scenes by content hash."""
    old_by_hash = {s.content_hash: s for s in old_scenes}
    new_by_hash = {s.content_hash: s for s in new_scenes}

    return {
        "added": [s for h, s in new_by_hash.items()
                  if h not in old_by_hash],
        "removed": [s for h, s in old_by_hash.items()
                    if h not in new_by_hash],
        "unchanged": [s for h, s in new_by_hash.items()
                      if h in old_by_hash]
    }
```

## Boneyard Update

```python
def _update_fountain_file(self, file_path: Path, script: Script):
    """Update Fountain file with new boneyard metadata."""
    content = file_path.read_text()

    for scene in script.scenes:
        if scene.has_new_metadata:
            # Find scene in content
            scene_start = content.find(scene.original_text)
            if scene_start == -1:
                continue

            # Find or create boneyard section
            boneyard_marker = "/* SCRIPTRAG-META-START"
            boneyard_start = content.find(
                boneyard_marker,
                scene_start
            )

            if boneyard_start == -1:
                # Insert new boneyard
                insert_pos = scene_start + len(scene.original_text)
                content = (
                    content[:insert_pos] +
                    "\n" + self._create_boneyard(scene) + "\n" +
                    content[insert_pos:]
                )
            else:
                # Update existing boneyard
                boneyard_end = content.find(
                    "SCRIPTRAG-META-END */",
                    boneyard_start
                ) + len("SCRIPTRAG-META-END */")

                content = (
                    content[:boneyard_start] +
                    self._create_boneyard(scene) +
                    content[boneyard_end:]
                )

    # Write updated content
    file_path.write_text(content)
```

## Git LFS Management

```python
def _track_embeddings(self):
    """Ensure embeddings are tracked by Git LFS."""
    gitattributes = self.repo_path / ".gitattributes"
    lfs_pattern = "embeddings/*.npz filter=lfs diff=lfs merge=lfs -text"

    if gitattributes.exists():
        content = gitattributes.read_text()
        if lfs_pattern not in content:
            content += f"\n{lfs_pattern}\n"
            gitattributes.write_text(content)
    else:
        gitattributes.write_text(f"{lfs_pattern}\n")

    # Initialize LFS if needed
    self.repo.git.lfs("track", "embeddings/*.npz")
```

## Pipeline Coordination

```python
def _process_new_scene(self, scene: Scene, file_path: Path):
    """Coordinate processing pipeline for a scene."""
    # This triggers the processing pipeline:
    # 1. Parser has already parsed the scene
    # 2. Send to Content Extractor
    # 3. Then to Embedding Generator
    # 4. Store results back in boneyard

    # In practice, this might use an event system
    # or direct component communication
    pass
```

## Error Handling

1. **Git Errors**: Handle detached HEAD, conflicts
2. **Parse Errors**: Skip invalid files with warning
3. **LFS Errors**: Retry with fallback to regular git
4. **Hook Errors**: Don't block commit, log errors

## Testing

Key test scenarios:

- Hook installation and execution
- Change detection accuracy
- Boneyard update logic
- Git LFS operations
- Error recovery

## Integration Points

- **Reads from**: Fountain Files in Git Repository
- **Writes to**: Git LFS storage backend
- **Calls**: Fountain Parser
- **Calls**: Database Indexer
- **Called by**: CLI/MCP interfaces

## Configuration

```yaml
synchronizer:
  auto_process: true
  install_hooks: true
  process_staged_only: false
  lfs_enabled: true
  max_file_size: 100MB
  ignore_patterns:
    - "*.draft.fountain"
    - "archive/**"
```

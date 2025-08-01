# Git Storage Component

This directory implements Git repository operations for storing and retrieving Fountain files, Script Bibles, and Custom Insight Agents.

## Architecture Role

Git Storage is a **Place** in the FMC architecture that:

- Stores Fountain files with boneyard metadata
- Stores Script Bible markdown files
- Stores Custom Insight Agent definitions
- Provides version control and branching

## Key Responsibilities

1. **File Operations**
   - Read/write Fountain files
   - Manage Script Bible documents
   - Handle Insight Agent files

2. **Git Operations**
   - Track changes
   - Handle commits
   - Manage branches
   - Resolve conflicts

3. **Path Management**
   - Validate paths within repository
   - Handle cross-platform paths
   - Prevent directory traversal

## Implementation Guidelines

```python
import git
from pathlib import Path
from typing import List, Optional, Dict
import json

from ...models import GitFile, FileType
from ...exceptions import StorageError, NotFoundError


class GitStorage:
    """Manage files in Git repository."""

    def __init__(self, repo_path: Optional[Path] = None):
        self.repo_path = repo_path or Path.cwd()
        self.repo = git.Repo(self.repo_path)
        self._validate_repo()

    def read_fountain(self, path: Path) -> str:
        """Read a Fountain file from the repository."""
        full_path = self._resolve_path(path, FileType.FOUNTAIN)

        if not full_path.exists():
            raise NotFoundError(f"Fountain file not found: {path}")

        return full_path.read_text(encoding='utf-8')

    def write_fountain(self, path: Path, content: str) -> None:
        """Write a Fountain file to the repository."""
        full_path = self._resolve_path(path, FileType.FOUNTAIN)

        # Ensure parent directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        full_path.write_text(content, encoding='utf-8')

        # Stage for commit
        self.repo.index.add([str(full_path)])

    def list_fountain_files(self) -> List[Path]:
        """List all Fountain files in the repository."""
        return [
            Path(item.path)
            for item in self.repo.tree().traverse()
            if item.path.endswith('.fountain')
        ]
```

## Script Bible Management

```python
def read_bible(self, character_id: str) -> str:
    """Read a character bible markdown file."""
    bible_path = self._get_bible_path(character_id)

    if not bible_path.exists():
        raise NotFoundError(
            f"Bible not found for character: {character_id}"
        )

    return bible_path.read_text(encoding='utf-8')

def write_bible(
    self,
    character_id: str,
    content: str,
    commit_message: Optional[str] = None
) -> None:
    """Write a character bible markdown file."""
    bible_path = self._get_bible_path(character_id)

    # Ensure bibles directory exists
    bible_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    bible_path.write_text(content, encoding='utf-8')

    # Commit if message provided
    if commit_message:
        self.repo.index.add([str(bible_path)])
        self.repo.index.commit(commit_message)

def _get_bible_path(self, character_id: str) -> Path:
    """Get path for character bible."""
    # Format: bibles/{series_id}/{character_name}.md
    series_id, char_name = character_id.split(':', 1)
    safe_name = self._sanitize_filename(char_name)
    return self.repo_path / "bibles" / series_id / f"{safe_name}.md"
```

## Insight Agent Storage

```python
def list_custom_agents(self) -> List[Path]:
    """List all custom insight agent files."""
    agents_dir = self.repo_path / "insight-agents"
    if not agents_dir.exists():
        return []

    return list(agents_dir.glob("*.md"))

def read_agent(self, agent_name: str) -> str:
    """Read an insight agent definition."""
    agent_path = self.repo_path / "insight-agents" / f"{agent_name}.md"

    if not agent_path.exists():
        raise NotFoundError(f"Agent not found: {agent_name}")

    return agent_path.read_text(encoding='utf-8')

def write_agent(
    self,
    agent_name: str,
    content: str
) -> None:
    """Write an insight agent definition."""
    agents_dir = self.repo_path / "insight-agents"
    agents_dir.mkdir(exist_ok=True)

    agent_path = agents_dir / f"{agent_name}.md"
    agent_path.write_text(content, encoding='utf-8')

    # Add to git
    self.repo.index.add([str(agent_path)])
```

## Path Security

```python
def _resolve_path(
    self,
    path: Path,
    file_type: FileType
) -> Path:
    """Resolve and validate a path within the repository."""
    # Convert to Path object
    path = Path(path)

    # Check for directory traversal
    try:
        # Resolve to absolute path
        full_path = (self.repo_path / path).resolve()

        # Ensure it's within repo
        full_path.relative_to(self.repo_path.resolve())
    except ValueError:
        raise StorageError(
            f"Path outside repository: {path}"
        )

    # Validate file extension
    if file_type == FileType.FOUNTAIN and not path.suffix == '.fountain':
        raise StorageError(
            f"Invalid fountain file: {path}"
        )

    return full_path

def _sanitize_filename(self, name: str) -> str:
    """Sanitize a filename for safe storage."""
    # Remove/replace unsafe characters
    safe_chars = set('abcdefghijklmnopqrstuvwxyz'
                     'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                     '0123456789-_')

    return ''.join(c if c in safe_chars else '_' for c in name)
```

## Git Operations

```python
def get_file_history(
    self,
    path: Path,
    limit: int = 10
) -> List[Dict]:
    """Get commit history for a file."""
    commits = list(self.repo.iter_commits(
        paths=str(path),
        max_count=limit
    ))

    return [
        {
            'hash': commit.hexsha,
            'author': str(commit.author),
            'date': commit.authored_datetime,
            'message': commit.message
        }
        for commit in commits
    ]

def get_file_at_revision(
    self,
    path: Path,
    revision: str
) -> str:
    """Get file content at specific revision."""
    try:
        blob = self.repo.oid[revision + ':' + str(path)]
        return blob.data.decode('utf-8')
    except KeyError:
        raise NotFoundError(
            f"File {path} not found at revision {revision}"
        )
```

## Performance Considerations

1. **Lazy Loading**: Don't load file content until needed
2. **Caching**: Cache frequently accessed files
3. **Batch Operations**: Stage multiple files before commit
4. **Large Files**: Use Git LFS for binary data

## Error Handling

1. **Permission Errors**: Handle read-only repositories
2. **Merge Conflicts**: Detect and report conflicts
3. **Invalid Paths**: Validate all user-provided paths
4. **Encoding Issues**: Handle non-UTF-8 files gracefully

## Testing

Key test scenarios:

- File CRUD operations
- Path validation and security
- Git operations (history, revisions)
- Concurrent access
- Large file handling
- Cross-platform paths

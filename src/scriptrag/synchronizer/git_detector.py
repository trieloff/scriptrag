"""Git-based change detection for ScriptRAG."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import git
    from git import Repo
except ImportError as e:
    raise ImportError(
        "GitPython is required for git integration. Install with: pip install gitpython"
    ) from e

from scriptrag.config import get_logger

logger = get_logger(__name__)


@dataclass
class BlameInfo:
    """Information from git blame for a set of lines."""

    commit_hash: str
    author: str
    timestamp: datetime
    lines: list[int]


@dataclass
class SceneBlame:
    """Blame information for a scene."""

    last_modified: datetime
    last_author: str
    commit_history: list[BlameInfo]


@dataclass
class FileChange:
    """Represents a change to a file."""

    path: Path
    commit_hash: str
    timestamp: datetime
    author: str
    added_lines: list[tuple[int, str]]  # (line_number, content)
    removed_lines: list[tuple[int, str]]


class GitChangeDetector:
    """Detect scene changes using git history."""

    def __init__(self, repo_path: Path | None = None):
        """Initialize detector.

        Args:
            repo_path: Path to git repository root. If None, uses current directory.
        """
        self.repo_path = repo_path or Path.cwd()
        self._verify_git_repo()

    def _verify_git_repo(self) -> None:
        """Verify that we're in a git repository."""
        try:
            self.repo = Repo(self.repo_path)
            logger.debug(f"Git repository found at: {self.repo.working_dir}")
        except (git.InvalidGitRepositoryError, git.NoSuchPathError) as e:
            raise RuntimeError(f"Not a git repository: {self.repo_path}") from e

    def get_file_changes(
        self,
        file_path: Path,
        since: datetime | None = None,
    ) -> list[FileChange]:
        """Get all changes to a file since a given date.

        Args:
            file_path: Path to the file
            since: Only get changes after this date

        Returns:
            List of changes to the file
        """
        changes = []

        # Make path relative to repo root
        try:
            relative_path = file_path.relative_to(self.repo.working_dir)
        except ValueError:
            # If file is not in repo, try as-is
            relative_path = file_path

        # Get commit history for file
        kwargs = {"paths": str(relative_path), "follow": True}
        if since:
            kwargs["since"] = since.isoformat()

        try:
            commits = list(self.repo.iter_commits(**kwargs))
        except git.GitCommandError as e:
            logger.warning(f"Failed to get git log for {file_path}: {e}")
            return []

        # Process each commit
        for commit in commits:
            # Get the diff for this commit
            if commit.parents:
                diffs = commit.parents[0].diff(
                    commit, paths=str(relative_path), create_patch=True
                )
            else:
                # Initial commit
                diffs = commit.diff(None, paths=str(relative_path), create_patch=True)

            for diff in diffs:
                added_lines = []
                removed_lines = []

                if diff.diff:
                    # Parse the diff text
                    lines = diff.diff.decode("utf-8", errors="replace").split("\n")
                    line_num = 0

                    for line in lines:
                        if line.startswith("@@"):
                            # Parse line numbers from diff header
                            import re
                            match = re.search(r"@@ -\d+,?\d* \+(\d+)", line)
                            if match:
                                line_num = int(match.group(1)) - 1
                        elif line.startswith("+") and not line.startswith("+++"):
                            line_num += 1
                            added_lines.append((line_num, line[1:]))
                        elif line.startswith("-") and not line.startswith("---"):
                            removed_lines.append((line_num, line[1:]))
                        elif not line.startswith("-"):
                            line_num += 1

                if added_lines or removed_lines:
                    changes.append(
                        FileChange(
                            path=file_path,
                            commit_hash=commit.hexsha,
                            timestamp=datetime.fromtimestamp(commit.committed_date),
                            author=commit.author.name,
                            added_lines=added_lines,
                            removed_lines=removed_lines,
                        )
                    )

        return changes

    def get_scene_blame(
        self,
        file_path: Path,
        scene_start_line: int,
        scene_end_line: int,
    ) -> SceneBlame | None:
        """Get blame information for a specific scene.

        Args:
            file_path: Path to the file
            scene_start_line: Starting line number of the scene (1-based)
            scene_end_line: Ending line number of the scene (1-based)

        Returns:
            SceneBlame object or None if blame fails
        """
        try:
            # Make path relative to repo root
            try:
                relative_path = file_path.relative_to(self.repo.working_dir)
            except ValueError:
                relative_path = file_path

            # Get blame information
            blame_data = self.repo.blame("HEAD", str(relative_path))

            scene_commits: dict[str, BlameInfo] = {}

            # Process blame data
            current_line = 1
            for commit, lines in blame_data:
                for _line in lines:
                    if scene_start_line <= current_line <= scene_end_line:
                        # This line is part of our scene
                        commit_hash = commit.hexsha

                        if commit_hash not in scene_commits:
                            scene_commits[commit_hash] = BlameInfo(
                                commit_hash=commit_hash,
                                author=commit.author.name,
                                timestamp=datetime.fromtimestamp(commit.committed_date),
                                lines=[],
                            )
                        scene_commits[commit_hash].lines.append(current_line)

                    current_line += 1

                    # Stop if we've passed the scene
                    if current_line > scene_end_line:
                        break

                if current_line > scene_end_line:
                    break

            if not scene_commits:
                return None

            # Find most recent modification
            most_recent = max(scene_commits.values(), key=lambda b: b.timestamp)

            return SceneBlame(
                last_modified=most_recent.timestamp,
                last_author=most_recent.author,
                commit_history=list(scene_commits.values()),
            )

        except git.GitCommandError as e:
            logger.warning(f"Failed to get git blame for {file_path}: {e}")
            return None

    def has_file_changed_since(
        self,
        file_path: Path,
        since: datetime,
    ) -> bool:
        """Check if a file has changed since a given date.

        Args:
            file_path: Path to check
            since: Date to check against

        Returns:
            True if file has changed since the date
        """
        changes = self.get_file_changes(file_path, since)
        return len(changes) > 0

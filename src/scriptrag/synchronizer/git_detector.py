"""Git-based change detection for ScriptRAG."""

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.debug(f"Git repository found at: {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
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
        # Build git log command
        cmd = [
            "git",
            "log",
            "--follow",  # Follow renames
            "--pretty=format:%H|%an|%aI",  # hash|author|timestamp
            "-p",  # Show patches
            str(file_path),
        ]

        if since:
            cmd.insert(3, f"--since={since.isoformat()}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to get git log for {file_path}: {e}")
            return []

        # Parse the output
        changes = []
        lines = result.stdout.strip().split("\n")
        i = 0

        while i < len(lines):
            if "|" in lines[i]:
                # This is a commit line
                parts = lines[i].split("|")
                if len(parts) >= 3:
                    commit_hash = parts[0]
                    author = parts[1]
                    timestamp_str = parts[2]

                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    except ValueError:
                        logger.warning(f"Failed to parse timestamp: {timestamp_str}")
                        timestamp = datetime.now()

                    # Skip to the diff part
                    i += 1
                    added_lines = []
                    removed_lines = []

                    # Look for diff lines
                    line_num = 0
                    while i < len(lines) and not ("|" in lines[i] and len(lines[i].split("|")) >= 3):
                        line = lines[i]
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
                        i += 1

                    if added_lines or removed_lines:
                        changes.append(
                            FileChange(
                                path=file_path,
                                commit_hash=commit_hash,
                                timestamp=timestamp,
                                author=author,
                                added_lines=added_lines,
                                removed_lines=removed_lines,
                            )
                        )
                else:
                    i += 1
            else:
                i += 1

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
            # Run git blame with porcelain format for easier parsing
            result = subprocess.run(
                ["git", "blame", "--porcelain", str(file_path)],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to get git blame for {file_path}: {e}")
            return None

        # Parse blame output
        lines = result.stdout.strip().split("\n")
        scene_commits: dict[str, BlameInfo] = {}
        i = 0
        current_line = 1

        while i < len(lines):
            if lines[i].startswith("\t"):
                # This is the actual line content
                if scene_start_line <= current_line <= scene_end_line:
                    # This line is part of our scene
                    # The previous lines contain the commit info
                    commit_hash = lines[i - 4].split()[0] if i >= 4 else ""
                    author = ""
                    timestamp = datetime.now()

                    # Look for author and timestamp in previous lines
                    for j in range(max(0, i - 10), i):
                        if lines[j].startswith("author "):
                            author = lines[j][7:]
                        elif lines[j].startswith("author-time "):
                            try:
                                timestamp = datetime.fromtimestamp(int(lines[j][12:]))
                            except ValueError:
                                pass

                    if commit_hash and commit_hash not in scene_commits:
                        scene_commits[commit_hash] = BlameInfo(
                            commit_hash=commit_hash,
                            author=author,
                            timestamp=timestamp,
                            lines=[],
                        )
                    if commit_hash:
                        scene_commits[commit_hash].lines.append(current_line)

                current_line += 1
            i += 1

        if not scene_commits:
            return None

        # Find most recent modification
        most_recent = max(scene_commits.values(), key=lambda b: b.timestamp)

        return SceneBlame(
            last_modified=most_recent.timestamp,
            last_author=most_recent.author,
            commit_history=list(scene_commits.values()),
        )

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
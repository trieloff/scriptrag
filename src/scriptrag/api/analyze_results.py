"""Result data structures for script analysis operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileResult:
    """Result data from analyzing a single screenplay file.

    Tracks the outcome of processing one Fountain file through the analysis
    pipeline, including whether any scenes were updated and error information.
    Used for reporting and debugging analysis operations.

    Attributes:
        path: Path to the Fountain file that was processed
        updated: True if any scenes in the file were updated with new analysis
        scenes_updated: Count of individual scenes that received new metadata
        error: Error message if processing failed, None if successful

    Example:
        >>> result = FileResult(
        ...     path=Path("my_script.fountain"),
        ...     updated=True,
        ...     scenes_updated=15
        ... )
        >>> print(f"Updated {result.scenes_updated} scenes")
    """

    path: Path
    updated: bool
    scenes_updated: int = 0
    error: str | None = None


@dataclass
class AnalyzeResult:
    """Aggregated results from analyzing multiple screenplay files.

    Contains outcome data from processing one or more Fountain files through
    the analysis pipeline. Provides both individual file results and summary
    statistics for batch operations.

    Attributes:
        files: List of FileResult objects, one for each processed file
        errors: List of error messages from failed operations that couldn't
               be attributed to specific files

    Properties:
        total_files_updated: Count of files that had at least one scene updated
        total_scenes_updated: Sum of all scenes updated across all files

    Example:
        >>> result = AnalyzeResult()
        >>> result.files.append(FileResult(Path("script1.fountain"), True, 10))
        >>> result.total_files_updated
        1
        >>> result.total_scenes_updated
        10
    """

    files: list[FileResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_files_updated(self) -> int:
        """Count of files that were updated."""
        return sum(1 for f in self.files if f.updated)

    @property
    def total_scenes_updated(self) -> int:
        """Total count of scenes updated across all files."""
        return sum(f.scenes_updated for f in self.files)

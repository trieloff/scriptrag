"""Bible file auto-detection for ScriptRAG."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar


class BibleAutoDetector:
    """Auto-detects script bible files in a project."""

    # Common patterns for bible files
    BIBLE_PATTERNS: ClassVar[list[str]] = [
        "*bible*.md",
        "*Bible*.md",
        "*worldbuilding*.md",
        "*Worldbuilding*.md",
        "*world_building*.md",
        "*World_Building*.md",
        "*backstory*.md",
        "*Backstory*.md",
        "*characters*.md",
        "*Characters*.md",
        "*lore*.md",
        "*Lore*.md",
        "*notes*.md",
        "*Notes*.md",
        "docs/*.md",
        "documentation/*.md",
        "world/*.md",
        "reference/*.md",
    ]

    # Patterns to exclude (not bible content)
    EXCLUDE_PATTERNS: ClassVar[list[str]] = [
        "README.md",
        "readme.md",
        "CHANGELOG.md",
        "changelog.md",
        "LICENSE.md",
        "license.md",
        "CONTRIBUTING.md",
        "contributing.md",
        ".github/*.md",
        "node_modules/**/*.md",
        ".venv/**/*.md",
        "venv/**/*.md",
    ]

    @classmethod
    def find_bible_files(
        cls, project_path: Path, script_path: Path | None = None
    ) -> list[Path]:
        """Find potential bible files in a project.

        Args:
            project_path: Root path of the project
            script_path: Optional path to the script file for proximity matching

        Returns:
            List of paths to potential bible files
        """
        bible_files: set[Path] = set()

        # Search using patterns
        for pattern in cls.BIBLE_PATTERNS:
            for file_path in project_path.rglob(pattern):
                if file_path.is_file() and not cls._should_exclude(
                    file_path, project_path
                ):
                    bible_files.add(file_path)

        # If we have a script path, also look for files in the same directory
        if script_path and script_path.parent != project_path:
            script_dir = script_path.parent
            for md_file in script_dir.glob("*.md"):
                if not cls._should_exclude(md_file, project_path):
                    # Check if file name suggests bible content
                    name_lower = md_file.stem.lower()
                    if any(
                        keyword in name_lower
                        for keyword in [
                            "bible",
                            "world",
                            "character",
                            "backstory",
                            "lore",
                            "note",
                            "ref",
                        ]
                    ):
                        bible_files.add(md_file)

        return sorted(bible_files)

    @classmethod
    def _should_exclude(cls, file_path: Path, project_path: Path) -> bool:
        """Check if a file should be excluded from bible detection.

        Args:
            file_path: Path to check
            project_path: Project root path

        Returns:
            True if file should be excluded
        """
        try:
            relative_path = file_path.relative_to(project_path)

            # Check against exclude patterns
            for pattern in cls.EXCLUDE_PATTERNS:
                if relative_path.match(pattern):
                    return True

            # Exclude hidden directories
            for part in relative_path.parts:
                if part.startswith(".") and part != ".":
                    return True

            return False
        except ValueError:
            # File is outside project path
            return True

"""Script listing API module for ScriptRAG."""

import re
from dataclasses import dataclass
from pathlib import Path

from scriptrag.config import get_logger
from scriptrag.parser import FountainParser

logger = get_logger(__name__)


@dataclass
class FountainMetadata:
    """Metadata extracted from a Fountain file."""

    file_path: Path
    title: str | None = None
    author: str | None = None
    episode_number: int | None = None
    season_number: int | None = None

    @property
    def display_title(self) -> str:
        """Get display title with series information if available."""
        if self.title:
            if self.season_number and self.episode_number:
                season = f"S{self.season_number:02d}"
                episode = f"E{self.episode_number:02d}"
                return f"{self.title} ({season}{episode})"
            if self.episode_number:
                return f"{self.title} (Episode {self.episode_number})"
            return self.title
        return self.file_path.stem

    @property
    def is_series(self) -> bool:
        """Check if this script is part of a series."""
        return self.season_number is not None or self.episode_number is not None


class ScriptLister:
    """API for listing and analyzing Fountain scripts."""

    def __init__(self) -> None:
        """Initialize script lister."""
        self._episode_pattern = re.compile(
            r"(?:Episode|Ep|E)\.?\s*(\d+)", re.IGNORECASE
        )
        self._season_pattern = re.compile(r"(?:Season|S)\.?\s*(\d+)", re.IGNORECASE)
        self._filename_episode_pattern = re.compile(
            r"[Ss](\d+)[Ee](\d+)|(\d+)x(\d+)|[Ee]pisode[\s_-]?(\d+)|[Ee]p[\s_-]?(\d+)",
            re.IGNORECASE,
        )
        self._parser = FountainParser()

    def list_scripts(
        self, path: Path | None = None, recursive: bool = True
    ) -> list[FountainMetadata]:
        """List all Fountain scripts in the given path.

        Args:
            path: Path to search for scripts. If None, uses current directory.
            recursive: Whether to search recursively.

        Returns:
            List of fountain metadata objects.
        """
        if path is None:
            path = Path.cwd()

        path = path.resolve()
        if not path.exists():
            logger.warning("Path does not exist", path=str(path))
            return []

        # Find all .fountain files
        if path.is_file():
            if path.suffix.lower() == ".fountain":
                return [self._parse_fountain_metadata(path)]
            return []

        pattern = "**/*.fountain" if recursive else "*.fountain"
        fountain_files = sorted(path.glob(pattern))

        logger.debug("Found fountain files", count=len(fountain_files), path=str(path))

        # Parse metadata from each file
        scripts = []
        for file_path in fountain_files:
            try:
                metadata = self._parse_fountain_metadata(file_path)
                scripts.append(metadata)
            except Exception as e:
                logger.error(
                    "Failed to parse fountain file",
                    path=str(file_path),
                    error=str(e),
                )

        return scripts

    def _parse_fountain_metadata(self, file_path: Path) -> FountainMetadata:
        """Parse metadata from a Fountain file.

        Args:
            file_path: Path to the Fountain file.

        Returns:
            Metadata extracted from the file.
        """
        metadata = FountainMetadata(file_path=file_path)

        try:
            # First try with FountainParser
            script = self._parser.parse_file(file_path)
            
            # Extract basic metadata
            metadata.title = script.title
            metadata.author = script.author
            
            # For episode/season info, also check the raw content for explicit fields
            # This handles cases where jouvence might not parse these custom fields
            content = file_path.read_text(encoding="utf-8")
            title_info = self._extract_title_page_info(content)
            
            # Use explicit episode/season fields if available
            if "episode_number" in title_info and title_info["episode_number"] is not None:
                metadata.episode_number = title_info["episode_number"]
            elif metadata.title:
                # Otherwise, try to extract from title
                title = re.sub(r"_\*\*(.+?)\*\*_", r"\1", metadata.title)
                ep_match = self._episode_pattern.search(title)
                if ep_match:
                    metadata.episode_number = int(ep_match.group(1))
                    
            if "season_number" in title_info and title_info["season_number"] is not None:
                metadata.season_number = title_info["season_number"]
            elif metadata.title:
                # Otherwise, try to extract from title
                title = re.sub(r"_\*\*(.+?)\*\*_", r"\1", metadata.title)
                season_match = self._season_pattern.search(title)
                if season_match:
                    metadata.season_number = int(season_match.group(1))
                    
        except Exception as e:
            logger.warning(
                "Failed to parse fountain file with parser, trying fallback",
                path=str(file_path),
                error=str(e),
            )
            # Fallback to basic parsing if jouvence fails
            try:
                self._parse_with_fallback(file_path, metadata)
            except Exception as fallback_error:
                logger.error(
                    "Fallback parsing also failed",
                    path=str(file_path),
                    error=str(fallback_error),
                )

        # If we couldn't determine episode/season from title page, try filename
        if metadata.episode_number is None or metadata.season_number is None:
            filename_info = self._extract_from_filename(file_path.stem)
            if metadata.episode_number is None:
                metadata.episode_number = filename_info.get("episode")
            if metadata.season_number is None:  # pragma: no cover
                metadata.season_number = filename_info.get("season")

        return metadata

    def _extract_title_page_info(self, content: str) -> dict[str, str | int | None]:
        """Extract title page information from Fountain content.
        
        This method is kept for backward compatibility with tests.
        
        Args:
            content: Raw fountain file content.
            
        Returns:
            Dictionary with extracted metadata.
        """
        info: dict[str, str | int | None] = {}
        
        # Title page is at the beginning, before the first blank line
        title_page_end = content.find("\n\n")
        if title_page_end == -1:
            title_page_content = content
        else:
            title_page_content = content[:title_page_end]
            
        # Process title page line by line to handle multi-line values
        lines = title_page_content.split("\n")
        current_key = None
        current_values = []
        
        title_page_pattern = re.compile(
            r"^(?P<key>[A-Za-z][A-Za-z\s]*?):\s*(?P<value>.*)$", re.MULTILINE
        )
        
        for line in lines:
            # Check if this is a key: value line
            key_match = title_page_pattern.match(line)
            if key_match:
                # Save previous key-value if exists
                if current_key:
                    self._process_title_page_value(
                        info, current_key, "\n".join(current_values)
                    )
                
                # Start new key-value
                current_key = key_match.group("key").strip().lower()
                value = key_match.group("value").strip()
                current_values = [value] if value else []
            elif current_key and line:  # pragma: no cover
                # Check if this is an indented continuation (3+ spaces or tab)
                if line.startswith("   ") or line.startswith("\t"):
                    current_values.append(line.strip())
        
        # Don't forget the last key-value pair
        if current_key:
            self._process_title_page_value(info, current_key, "\n".join(current_values))
        
        return info
    
    def _process_title_page_value(
        self, info: dict[str, str | int | None], key: str, value: str
    ) -> None:
        """Process a title page key-value pair.
        
        Args:
            info: Dictionary to update with extracted values.
            key: The key (lowercase).
            value: The value (may be multi-line).
        """
        # Normalize formatting marks (_**text**_ becomes text)
        value = re.sub(r"_\*\*(.+?)\*\*_", r"\1", value)
        
        if key == "title":
            info["title"] = value
            # Check for episode number in title
            ep_match = self._episode_pattern.search(value)
            if ep_match:
                info["episode_number"] = int(ep_match.group(1))
            # Check for season number in title
            season_match = self._season_pattern.search(value)
            if season_match:
                info["season_number"] = int(season_match.group(1))
        elif key in ("author", "authors", "written by", "writer", "writers"):
            info["author"] = value
        elif key == "episode":
            # Try to extract episode number
            ep_match = re.search(r"\d+", value)
            if ep_match:
                info["episode_number"] = int(ep_match.group())
        elif key == "season":
            # Try to extract season number
            season_match = re.search(r"\d+", value)
            if season_match:
                info["season_number"] = int(season_match.group())

    def _parse_with_fallback(self, file_path: Path, metadata: FountainMetadata) -> None:
        """Fallback parsing method using simple regex.
        
        Args:
            file_path: Path to the Fountain file
            metadata: Metadata object to update
        """
        content = file_path.read_text(encoding="utf-8")
        
        # Title page is at the beginning, before the first blank line
        title_page_end = content.find("\n\n")
        if title_page_end == -1:
            title_page_content = content
        else:
            title_page_content = content[:title_page_end]
            
        # Simple regex for title page
        title_match = re.search(r"^Title:\s*(.+)$", title_page_content, re.MULTILINE | re.IGNORECASE)
        if title_match:
            metadata.title = title_match.group(1).strip()
            
        author_match = re.search(
            r"^(?:Author|Authors|Written by|Writer|Writers):\s*(.+)$",
            title_page_content,
            re.MULTILINE | re.IGNORECASE
        )
        if author_match:
            metadata.author = author_match.group(1).strip()

    def _extract_from_filename(self, filename: str) -> dict[str, int | None]:
        """Extract episode and season numbers from filename.

        Args:
            filename: Filename without extension.

        Returns:
            Dictionary with season and episode numbers if found.
        """
        info: dict[str, int | None] = {"season": None, "episode": None}

        # Try various filename patterns
        match = self._filename_episode_pattern.search(filename)
        if match:
            groups = match.groups()
            if groups[0] and groups[1]:  # S##E## format
                info["season"] = int(groups[0])
                info["episode"] = int(groups[1])
            elif groups[2] and groups[3]:  # ##x## format
                info["season"] = int(groups[2])
                info["episode"] = int(groups[3])
            elif groups[4]:  # Episode ## format
                info["episode"] = int(groups[4])
            elif groups[5]:  # Ep ## format  # pragma: no cover
                info["episode"] = int(groups[5])

        return info
"""Bible parser for processing markdown script bible documents."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

from scriptrag.config import get_logger

logger = get_logger(__name__)


@dataclass
class BibleChunk:
    """Represents a chunk/section from a script bible document."""

    chunk_number: int
    heading: str | None
    level: int  # Heading level (0 for root, 1-6 for H1-H6)
    content: str
    content_hash: str
    parent_chunk_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Calculate metadata after initialization."""
        if "word_count" not in self.metadata:
            self.metadata["word_count"] = len(self.content.split())
        if "char_count" not in self.metadata:
            self.metadata["char_count"] = len(self.content)


@dataclass
class ParsedBible:
    """Result of parsing a bible document."""

    file_path: Path
    title: str | None
    chunks: list[BibleChunk]
    file_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BibleParser:
    """Parser for markdown-based script bible documents."""

    # Maximum file size in bytes (10 MB default)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    def __init__(self, max_file_size: int | None = None) -> None:
        """Initialize the bible parser.

        Args:
            max_file_size: Maximum file size in bytes (default 10MB)
        """
        self.md = MarkdownIt("commonmark")
        # Enable useful extensions
        self.md.enable(["table", "strikethrough"])
        self.max_file_size = max_file_size or self.MAX_FILE_SIZE

    def parse_file(self, file_path: Path) -> ParsedBible:
        """Parse a markdown bible file into chunks.

        Args:
            file_path: Path to the markdown file

        Returns:
            ParsedBible object containing chunks

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file cannot be parsed
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Bible file not found: {file_path}")

        # Check file size before reading
        file_size = file_path.stat().st_size
        if file_size > self.max_file_size:
            raise ValueError(
                f"Bible file {file_path} is too large ({file_size:,} bytes). "
                f"Maximum size is {self.max_file_size:,} bytes."
            )

        # Validate file path (prevent directory traversal)
        try:
            resolved_path = file_path.resolve(strict=True)
            # Ensure the path is within expected bounds
            if not resolved_path.is_file():
                raise ValueError(f"Path {file_path} is not a regular file")
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Invalid file path {file_path}: {e}") from e

        # Read file content
        content = resolved_path.read_text(encoding="utf-8")

        # Calculate file hash for change detection
        file_hash = hashlib.sha256(content.encode()).hexdigest()

        # Parse markdown to tokens
        tokens = self.md.parse(content)

        # Extract chunks based on heading structure
        chunks = self._extract_chunks(tokens, content)

        # Determine title (first H1 or filename)
        title = self._extract_title(chunks, file_path)

        # Add file-level metadata
        metadata = {
            "total_chunks": len(chunks),
            "total_words": sum(c.metadata.get("word_count", 0) for c in chunks),
            "total_chars": sum(c.metadata.get("char_count", 0) for c in chunks),
            "max_heading_level": max((c.level for c in chunks), default=0),
        }

        return ParsedBible(
            file_path=file_path,
            title=title,
            chunks=chunks,
            file_hash=file_hash,
            metadata=metadata,
        )

    def _extract_chunks(
        self, tokens: list[Token], original_content: str
    ) -> list[BibleChunk]:
        """Extract chunks from markdown tokens.

        Args:
            tokens: Parsed markdown tokens
            original_content: Original markdown content

        Returns:
            List of BibleChunk objects
        """
        chunks: list[BibleChunk] = []
        current_chunk_content: list[str] = []
        current_heading: str | None = None
        current_level = 0
        chunk_number = 0
        parent_stack: list[int] = []  # Stack of parent chunk IDs by level

        # Process tokens to identify structure
        i = 0
        while i < len(tokens):
            token = tokens[i]

            if token.type == "heading_open":
                # Save previous chunk if exists
                if current_chunk_content or current_heading is not None:
                    chunk = self._create_chunk(
                        chunk_number=chunk_number,
                        heading=current_heading,
                        level=current_level,
                        content="\n".join(current_chunk_content).strip(),
                        parent_id=self._get_parent_id(parent_stack, current_level),
                    )
                    chunks.append(chunk)
                    self._update_parent_stack(parent_stack, current_level, chunk_number)
                    chunk_number += 1
                    current_chunk_content = []

                # Extract heading level
                current_level = int(token.tag[1])  # h1 -> 1, h2 -> 2, etc.

                # Get heading text from next inline token
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    current_heading = tokens[i + 1].content
                    i += 2  # Skip inline token
                else:
                    current_heading = ""

            elif token.type == "heading_close":
                # Already handled in heading_open - nothing to do here
                pass

            elif token.type in ["paragraph_open", "blockquote_open", "list_item_open"]:
                # Start collecting content
                # Actual content comes in subsequent inline tokens
                pass

            elif token.type == "inline":
                # Add inline content to current chunk
                if token.content:
                    current_chunk_content.append(token.content)

            elif token.type == "code_block":
                # Add code blocks as-is
                if token.content:
                    current_chunk_content.append(f"```\n{token.content}\n```")

            elif token.type == "fence":
                # Add fenced code blocks
                if token.content:
                    lang = token.info or ""
                    current_chunk_content.append(f"```{lang}\n{token.content}\n```")

            elif token.type == "table_open":
                # Mark table start
                current_chunk_content.append("[TABLE]")

            elif token.type == "hr":
                # Horizontal rule might indicate section break
                # Save current chunk and start new one
                if current_chunk_content:
                    chunk = self._create_chunk(
                        chunk_number=chunk_number,
                        heading=current_heading,
                        level=current_level,
                        content="\n".join(current_chunk_content).strip(),
                        parent_id=self._get_parent_id(parent_stack, current_level),
                    )
                    chunks.append(chunk)
                    chunk_number += 1
                    current_chunk_content = []

            i += 1

        # Save final chunk if exists
        if current_chunk_content or (current_heading and not chunks):
            chunk = self._create_chunk(
                chunk_number=chunk_number,
                heading=current_heading,
                level=current_level,
                content="\n".join(current_chunk_content).strip(),
                parent_id=self._get_parent_id(parent_stack, current_level),
            )
            chunks.append(chunk)

        # If no chunks were created (e.g., document with no headings),
        # create a single chunk with all content
        if not chunks and original_content.strip():
            chunk = self._create_chunk(
                chunk_number=0,
                heading=None,
                level=0,
                content=original_content.strip(),
                parent_id=None,
            )
            chunks.append(chunk)

        return chunks

    def _create_chunk(
        self,
        chunk_number: int,
        heading: str | None,
        level: int,
        content: str,
        parent_id: int | None,
    ) -> BibleChunk:
        """Create a BibleChunk with computed hash.

        Args:
            chunk_number: Order in document
            heading: Section heading
            level: Heading level
            content: Chunk content
            parent_id: Parent chunk ID

        Returns:
            BibleChunk object
        """
        # Compute content hash for embedding lookups
        # Include heading in hash for uniqueness
        hash_content = f"{heading or ''}\n{content}"
        content_hash = hashlib.sha256(hash_content.encode()).hexdigest()

        return BibleChunk(
            chunk_number=chunk_number,
            heading=heading,
            level=level,
            content=content,
            content_hash=content_hash,
            parent_chunk_id=parent_id,
        )

    def _get_parent_id(self, parent_stack: list[int], level: int) -> int | None:
        """Get parent chunk ID for given level.

        Args:
            parent_stack: Stack of parent IDs by level
            level: Current heading level

        Returns:
            Parent chunk ID or None
        """
        # Find parent at the next lower level
        for i in range(level - 1, 0, -1):
            if i <= len(parent_stack):
                return parent_stack[i - 1] if i > 0 else None
        return None

    def _update_parent_stack(
        self, parent_stack: list[int], level: int, chunk_id: int
    ) -> None:
        """Update parent stack with new chunk.

        Args:
            parent_stack: Stack to update
            level: Level of new chunk
            chunk_id: ID of new chunk
        """
        # Ensure stack has enough levels
        while len(parent_stack) < level:
            parent_stack.append(-1)

        # Update stack at this level
        if level > 0:
            parent_stack[level - 1] = chunk_id

        # Clear deeper levels
        while len(parent_stack) > level:
            parent_stack.pop()

    def _extract_title(self, chunks: list[BibleChunk], file_path: Path) -> str:
        """Extract document title from chunks or filename.

        Args:
            chunks: List of document chunks
            file_path: Path to document file

        Returns:
            Document title
        """
        # Look for first H1 heading
        for chunk in chunks:
            if chunk.level == 1 and chunk.heading:
                return chunk.heading

        # Fallback to filename without extension
        return file_path.stem.replace("_", " ").replace("-", " ").title()

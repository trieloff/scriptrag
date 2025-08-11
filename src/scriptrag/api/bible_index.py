"""Bible indexing API module for ScriptRAG."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from scriptrag.analyzers.embedding import SceneEmbeddingAnalyzer
from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import ScriptRAGSettings, get_logger, get_settings
from scriptrag.parser.bible_parser import BibleParser, ParsedBible

logger = get_logger(__name__)


@dataclass
class BibleIndexResult:
    """Result from indexing a single bible document."""

    path: Path
    bible_id: int | None = None
    indexed: bool = False
    updated: bool = False
    chunks_indexed: int = 0
    embeddings_created: int = 0
    error: str | None = None


class BibleIndexer:
    """Handles indexing of script bible documents."""

    def __init__(
        self,
        settings: ScriptRAGSettings | None = None,
        db_ops: DatabaseOperations | None = None,
    ):
        """Initialize bible indexer.

        Args:
            settings: Configuration settings
            db_ops: Database operations handler
        """
        self.settings = settings or get_settings()
        self.db_ops = db_ops or DatabaseOperations(self.settings)
        self.parser = BibleParser(max_file_size=self.settings.bible_max_file_size)
        self.embedding_analyzer: SceneEmbeddingAnalyzer | None = None

    async def initialize_embedding_analyzer(self) -> None:
        """Initialize the embedding analyzer for bible chunks."""
        if self.embedding_analyzer is None:
            # Configure for bible embeddings using settings
            config = {
                "lfs_path": self.settings.bible_embeddings_path,
                "repo_path": ".",
                "embedding_model": self.settings.llm_embedding_model,
            }
            self.embedding_analyzer = SceneEmbeddingAnalyzer(config)
            await self.embedding_analyzer.initialize()
            logger.info(
                f"Initialized embedding analyzer for bible content at "
                f"{self.settings.bible_embeddings_path}"
            )

    async def index_bible(
        self,
        bible_path: Path,
        script_id: int,
        force: bool = False,
    ) -> BibleIndexResult:
        """Index a single bible document.

        Args:
            bible_path: Path to the bible markdown file
            script_id: ID of the associated script
            force: Force re-indexing even if unchanged

        Returns:
            BibleIndexResult with indexing details
        """
        result = BibleIndexResult(path=bible_path)

        try:
            # Parse the bible document
            parsed_bible = self.parser.parse_file(bible_path)

            # Use DatabaseOperations transaction context for proper error handling
            with self.db_ops.transaction() as conn:
                cursor = conn.cursor()

                # Check for existing bible entry
                cursor.execute(
                    """
                    SELECT id, file_hash FROM script_bibles
                    WHERE script_id = ? AND file_path = ?
                    """,
                    (script_id, str(bible_path)),
                )
                existing = cursor.fetchone()

                if existing:
                    bible_id, existing_hash = existing
                    if existing_hash == parsed_bible.file_hash and not force:
                        logger.info(f"Bible {bible_path} unchanged, skipping")
                        result.bible_id = bible_id
                        return result

                    # Update existing bible
                    result.bible_id = bible_id
                    result.updated = True
                    await self._update_bible(conn, bible_id, parsed_bible)
                else:
                    # Insert new bible
                    bible_id = await self._insert_bible(conn, script_id, parsed_bible)
                    result.bible_id = bible_id
                    result.indexed = True

                # Index chunks
                chunks_indexed = await self._index_chunks(conn, bible_id, parsed_bible)
                result.chunks_indexed = chunks_indexed

                # Generate embeddings if configured
                if self.settings.llm_embedding_model:
                    await self.initialize_embedding_analyzer()
                    embeddings_created = await self._generate_embeddings(
                        conn, bible_id, parsed_bible
                    )
                    result.embeddings_created = embeddings_created

                logger.info(
                    f"Successfully indexed bible {bible_path}: "
                    f"{chunks_indexed} chunks, {result.embeddings_created} embeddings"
                )
                # Note: commit happens automatically with transaction context

        except Exception as e:
            logger.error(f"Failed to index bible {bible_path}: {e}")
            result.error = str(e)

        return result

    async def _insert_bible(
        self,
        conn: sqlite3.Connection,
        script_id: int,
        parsed_bible: ParsedBible,
    ) -> int:
        """Insert a new bible into the database.

        Args:
            conn: Database connection
            script_id: Associated script ID
            parsed_bible: Parsed bible data

        Returns:
            ID of inserted bible
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO script_bibles (script_id, file_path, title, file_hash, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                script_id,
                str(parsed_bible.file_path),
                parsed_bible.title,
                parsed_bible.file_hash,
                json.dumps(parsed_bible.metadata),
            ),
        )
        return cursor.lastrowid or 0

    async def _update_bible(
        self,
        conn: sqlite3.Connection,
        bible_id: int,
        parsed_bible: ParsedBible,
    ) -> None:
        """Update an existing bible in the database.

        Args:
            conn: Database connection
            bible_id: ID of bible to update
            parsed_bible: New parsed bible data
        """
        cursor = conn.cursor()

        # Update bible metadata
        cursor.execute(
            """
            UPDATE script_bibles
            SET title = ?, file_hash = ?, metadata = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                parsed_bible.title,
                parsed_bible.file_hash,
                json.dumps(parsed_bible.metadata),
                bible_id,
            ),
        )

        # Delete old chunks (cascades to embeddings and references)
        cursor.execute("DELETE FROM bible_chunks WHERE bible_id = ?", (bible_id,))

    async def _index_chunks(
        self,
        conn: sqlite3.Connection,
        bible_id: int,
        parsed_bible: ParsedBible,
    ) -> int:
        """Index bible chunks into the database.

        Args:
            conn: Database connection
            bible_id: ID of the bible
            parsed_bible: Parsed bible data

        Returns:
            Number of chunks indexed
        """
        cursor = conn.cursor()
        chunks_indexed = 0

        # Create a mapping of chunk_number to database ID for parent references
        chunk_id_map: dict[int, int] = {}

        for chunk in parsed_bible.chunks:
            # Determine parent ID
            parent_id = None
            if (
                chunk.parent_chunk_id is not None
                and chunk.parent_chunk_id in chunk_id_map
            ):
                parent_id = chunk_id_map[chunk.parent_chunk_id]

            # Insert chunk
            cursor.execute(
                """
                INSERT INTO bible_chunks (
                    bible_id, chunk_number, heading, level, content,
                    content_hash, parent_chunk_id, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bible_id,
                    chunk.chunk_number,
                    chunk.heading,
                    chunk.level,
                    chunk.content,
                    chunk.content_hash,
                    parent_id,
                    json.dumps(chunk.metadata),
                ),
            )

            # Store the database ID for this chunk
            chunk_id = cursor.lastrowid
            if chunk_id:
                chunk_id_map[chunk.chunk_number] = chunk_id
                chunks_indexed += 1

        return chunks_indexed

    async def _generate_embeddings(
        self,
        conn: sqlite3.Connection,
        bible_id: int,
        parsed_bible: ParsedBible,  # noqa: ARG002
    ) -> int:
        """Generate and store embeddings for bible chunks.

        Args:
            conn: Database connection
            bible_id: ID of the bible
            parsed_bible: Parsed bible data

        Returns:
            Number of embeddings created
        """
        if not self.embedding_analyzer:
            return 0

        cursor = conn.cursor()
        embeddings_created = 0

        # Get chunk IDs from database
        cursor.execute(
            """
            SELECT id, content_hash, heading, content
            FROM bible_chunks
            WHERE bible_id = ?
            ORDER BY chunk_number
            """,
            (bible_id,),
        )
        chunks = cursor.fetchall()

        for chunk_id, _content_hash, heading, content in chunks:
            # Try to generate embedding with retry logic
            max_retries = 3
            retry_count = 0
            base_delay = 1.0  # Start with 1 second delay

            while retry_count < max_retries:
                try:
                    # Format chunk for embedding (similar to scene formatting)
                    chunk_data = {
                        "heading": heading or "",
                        "content": content,
                        "original_text": f"{heading or ''}\n\n{content}",
                    }

                    # Generate embedding using the analyzer
                    result = await self.embedding_analyzer.analyze(chunk_data)

                    if "error" not in result:
                        # Store embedding metadata in database
                        embedding_path = result.get("embedding_path", "")
                        dimensions = result.get("dimensions", 0)
                        model = result.get("model", "auto-selected")

                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO bible_embeddings (
                                chunk_id, embedding_model, embedding_path, dimensions
                            )
                            VALUES (?, ?, ?, ?)
                            """,
                            (chunk_id, model, embedding_path, dimensions),
                        )
                        embeddings_created += 1
                        logger.debug(
                            f"Created embedding for chunk {chunk_id}: {embedding_path}"
                        )
                        break  # Success, exit retry loop
                    # Error in result, treat as failure
                    raise ValueError(f"Embedding API error: {result.get('error')}")

                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logger.error(
                            f"Failed to generate embedding for chunk {chunk_id} after "
                            f"{max_retries} attempts: {e}"
                        )
                        break  # Give up on this chunk

                    # Calculate exponential backoff delay
                    delay = base_delay * (2 ** (retry_count - 1))
                    logger.warning(
                        f"Embedding generation failed for chunk {chunk_id}, "
                        f"retrying in {delay:.1f}s "
                        f"(attempt {retry_count}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(delay)

        return embeddings_created


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

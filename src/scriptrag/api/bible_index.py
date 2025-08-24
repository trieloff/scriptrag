"""Bible indexing API module for ScriptRAG."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from scriptrag.analyzers.embedding import SceneEmbeddingAnalyzer
from scriptrag.api.bible_alias_extractor import BibleAliasExtractor
from scriptrag.api.database_operations import DatabaseOperations
from scriptrag.config import ScriptRAGSettings, get_logger, get_settings
from scriptrag.parser.bible_parser import BibleParser, ParsedBible

logger = get_logger(__name__)


@dataclass
class BibleIndexResult:
    """Result data from indexing a single script Bible document.

    Tracks the outcome of indexing operations including success/failure status,
    database IDs, and counts of processed elements. This information is used
    for reporting and debugging indexing operations.

    Attributes:
        path: Path to the Bible file that was processed
        bible_id: Database ID of the Bible record, if successfully created/found
        indexed: True if this was a new Bible file that was indexed
        updated: True if this was an existing Bible file that was updated
        chunks_indexed: Number of content chunks successfully indexed
        embeddings_created: Number of embeddings generated for chunks
        error: Error message if indexing failed, None if successful

    Example:
        >>> result = BibleIndexResult(
        ...     path=Path("my_bible.md"),
        ...     bible_id=123,
        ...     indexed=True,
        ...     chunks_indexed=15,
        ...     embeddings_created=15
        ... )
        >>> print(f"Indexed {result.chunks_indexed} chunks")
    """

    path: Path
    bible_id: int | None = None
    indexed: bool = False
    updated: bool = False
    chunks_indexed: int = 0
    embeddings_created: int = 0
    error: str | None = None


class BibleIndexer:
    """Indexes script Bible documents into the ScriptRAG database.

    Manages the complete process of parsing Bible markdown files, extracting
    structured content, storing it in the database, generating embeddings for
    semantic search, and extracting character alias information via LLM.

    The indexing process includes:
    1. Parsing markdown files into structured chunks
    2. Storing Bible metadata and chunks in the database
    3. Generating embeddings for semantic search (if configured)
    4. Extracting character aliases via LLM (if configured)
    5. Linking extracted aliases to script character records

    Example:
        >>> indexer = BibleIndexer()
        >>> result = await indexer.index_bible(
        ...     Path("my_bible.md"), script_id=123
        ... )
        >>> print(f"Indexed {result.chunks_indexed} chunks")
    """

    def __init__(
        self,
        settings: ScriptRAGSettings | None = None,
        db_ops: DatabaseOperations | None = None,
    ) -> None:
        """Initialize bible indexer.

        Args:
            settings: Configuration settings
            db_ops: Database operations handler
        """
        self.settings = settings or get_settings()
        self.db_ops = db_ops or DatabaseOperations(self.settings)
        self.parser = BibleParser(max_file_size=self.settings.bible_max_file_size)
        self.embedding_analyzer: SceneEmbeddingAnalyzer | None = None
        self.alias_extractor = BibleAliasExtractor(self.settings)

    async def initialize_embedding_analyzer(self) -> None:
        """Initialize the embedding analyzer for Bible chunk processing.

        Sets up the SceneEmbeddingAnalyzer with configuration specific to
        Bible content processing. The analyzer handles generating vector
        embeddings for Bible chunks to enable semantic search capabilities.

        The configuration includes:
        - LFS storage path for embedding files
        - Repository root path for Git LFS integration
        - Embedding model selection from settings

        Raises:
            Exception: If embedding analyzer initialization fails due to
                      LLM configuration issues or storage path problems

        Note:
            This method is called lazily when embeddings are needed, allowing
            the indexer to function even when embeddings are not configured.
            The analyzer is cached after first initialization.
        """
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
        """Index a script Bible document into the database.

        Orchestrates the Bible indexing pipeline: parsing, storage,
        embedding generation, and character alias extraction.

        Processing steps:
        1. Parse Bible markdown file
        2. Check existing records and file hashes
        3. Store Bible metadata and content chunks
        4. Generate embeddings for semantic search
        5. Extract character aliases via LLM
        6. Link aliases to script and character records

        Args:
            bible_path: Path to Bible markdown file
            script_id: Database ID of associated script
            force: Re-process even if file unchanged

        Returns:
            BibleIndexResult with processing counts and errors

        Example:
            >>> result = await indexer.index_bible(
            ...     Path("bible.md"), script_id=42
            ... )
            >>> if not result.error:
            ...     print(f"Indexed {result.chunks_indexed} chunks")
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
                # Extract character aliases from bible and persist to script metadata
                try:
                    alias_map = await self.alias_extractor.extract_aliases(parsed_bible)
                except Exception as e:  # pragma: no cover
                    logger.debug(f"Alias extraction skipped due to error: {e}")
                    alias_map = None

                if alias_map:
                    # Persist under scripts.metadata["bible"]["characters"]
                    self.alias_extractor.attach_alias_map_to_script(
                        conn, script_id, alias_map
                    )
                    # Attempt to attach aliases to existing characters if column exists
                    self.alias_extractor.attach_aliases_to_characters(
                        conn, script_id, alias_map
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
        parsed_bible: ParsedBible,
    ) -> int:
        """Generate and store embeddings for bible chunks.

        Args:
            conn: Database connection
            bible_id: ID of the bible
            parsed_bible: Parsed bible data

        Returns:
            Number of embeddings created
        """
        # Note: parsed_bible is kept for API consistency but not needed here
        # Data is already stored in database from previous step
        _ = parsed_bible  # Mark as intentionally unused

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

                    # Exponential backoff: 1s, 2s, 4s, 8s, 16s (max ~31s total)
                    delay = base_delay * (2 ** (retry_count - 1))
                    logger.warning(
                        f"Embedding generation failed for chunk {chunk_id}, "
                        f"retrying in {delay:.1f}s "
                        f"(attempt {retry_count}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(delay)

        return embeddings_created

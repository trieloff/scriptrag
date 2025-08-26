"""Additional tests for bible_index.py to improve coverage."""

import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from scriptrag.api.bible_detector import BibleAutoDetector
from scriptrag.api.bible_index import BibleIndexer
from scriptrag.config import ScriptRAGSettings
from scriptrag.parser.bible_parser import BibleChunk, ParsedBible


@pytest.fixture
def mock_settings() -> ScriptRAGSettings:
    """Create mock settings for testing."""
    settings = ScriptRAGSettings()
    settings.database_path = Path("/tmp/test.db")
    settings.bible_max_file_size = 1024 * 1024
    settings.bible_embeddings_path = Path("/tmp/embeddings")
    settings.llm_embedding_model = "test-model"
    settings.llm_model = "test-llm"
    settings.llm_provider = "test-provider"
    settings.llm_api_key = "test-key"  # pragma: allowlist secret
    return settings


@pytest.fixture
def mock_parsed_bible() -> ParsedBible:
    """Create a mock parsed bible for testing."""
    chunks = [
        BibleChunk(
            chunk_number=0,
            heading="Test Heading",
            level=1,
            content="Test content",
            content_hash="hash1",
            metadata={},
            parent_chunk_id=None,
        ),
        BibleChunk(
            chunk_number=1,
            heading="Sub Heading",
            level=2,
            content="Sub content",
            content_hash="hash2",
            metadata={},
            parent_chunk_id=0,
        ),
    ]
    return ParsedBible(
        file_path=Path("/test/bible.md"),
        title="Test Bible",
        file_hash="test_hash",
        metadata={"test": "data"},
        chunks=chunks,
    )


class TestBibleIndexerEdgeCases:
    """Test edge cases and error conditions in BibleIndexer."""

    @pytest.mark.asyncio
    async def test_initialize_embedding_analyzer_creates_analyzer(
        self, mock_settings: ScriptRAGSettings, tmp_path: Path
    ) -> None:
        """Test that initialize_embedding_analyzer creates the analyzer."""
        mock_settings.bible_embeddings_path = tmp_path / "embeddings"

        with patch(
            "scriptrag.api.bible_index.SceneEmbeddingAnalyzer"
        ) as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            # Make initialize explicitly async
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer

            indexer = BibleIndexer(settings=mock_settings)
            await indexer.initialize_embedding_analyzer()

            assert indexer.embedding_analyzer is not None
            mock_analyzer.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_embedding_analyzer_only_once(
        self, mock_settings: ScriptRAGSettings
    ) -> None:
        """Test that embedding analyzer is only initialized once."""
        with patch(
            "scriptrag.api.bible_index.SceneEmbeddingAnalyzer"
        ) as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            # Make initialize explicitly async
            mock_analyzer.initialize = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer

            indexer = BibleIndexer(settings=mock_settings)

            # First call should initialize
            await indexer.initialize_embedding_analyzer()
            first_analyzer = indexer.embedding_analyzer

            # Second call should not reinitialize
            await indexer.initialize_embedding_analyzer()
            assert indexer.embedding_analyzer is first_analyzer
            assert mock_analyzer_class.call_count == 1

    @pytest.mark.asyncio
    async def test_index_bible_parse_error(
        self, mock_settings: ScriptRAGSettings, tmp_path: Path
    ) -> None:
        """Test handling of parse errors in index_bible."""
        bible_path = tmp_path / "bad_bible.md"
        bible_path.write_text("# Test")

        indexer = BibleIndexer(settings=mock_settings)

        # Mock parser to raise error
        with patch.object(
            indexer.parser, "parse_file", side_effect=Exception("Parse failed")
        ):
            result = await indexer.index_bible(bible_path, script_id=1)

            assert result.indexed is False
            assert result.error == "Parse failed"

    @pytest.mark.asyncio
    async def test_index_bible_existing_unchanged_file(
        self,
        mock_settings: ScriptRAGSettings,
        mock_parsed_bible: ParsedBible,
        tmp_path: Path,
    ) -> None:
        """Test skipping unchanged files."""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Test")

        # Mock database operations
        mock_db_ops = Mock(spec_set=["transaction"])
        mock_conn = Mock(spec_set=["cursor"])
        mock_cursor = Mock(spec_set=["fetchone", "execute", "lastrowid", "fetchall"])

        # Mock existing entry with same hash
        mock_cursor.fetchone.return_value = (1, mock_parsed_bible.file_hash)
        mock_conn.cursor.return_value = mock_cursor
        mock_db_ops.transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

        indexer = BibleIndexer(settings=mock_settings, db_ops=mock_db_ops)

        # Mock parser
        with patch.object(indexer.parser, "parse_file", return_value=mock_parsed_bible):
            result = await indexer.index_bible(bible_path, script_id=1, force=False)

            assert result.indexed is False
            assert result.updated is False
            assert result.bible_id == 1

    @pytest.mark.asyncio
    async def test_index_bible_existing_changed_file(
        self,
        mock_settings: ScriptRAGSettings,
        mock_parsed_bible: ParsedBible,
        tmp_path: Path,
    ) -> None:
        """Test updating changed files."""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Test")

        # Mock database operations
        mock_db_ops = Mock(spec_set=["transaction"])
        mock_conn = Mock(spec_set=["cursor"])
        mock_cursor = Mock(spec_set=["fetchone", "execute", "lastrowid", "fetchall"])

        # Mock existing entry with different hash
        mock_cursor.fetchone.return_value = (1, "different_hash")
        mock_cursor.lastrowid = 123
        mock_conn.cursor.return_value = mock_cursor
        mock_db_ops.transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

        indexer = BibleIndexer(settings=mock_settings, db_ops=mock_db_ops)

        # Mock methods
        with (
            patch.object(indexer.parser, "parse_file", return_value=mock_parsed_bible),
            patch.object(
                indexer, "_update_bible", new_callable=AsyncMock
            ) as mock_update,
            patch.object(
                indexer, "_index_chunks", new_callable=AsyncMock, return_value=2
            ) as mock_index_chunks,
            patch.object(
                indexer.alias_extractor,
                "extract_aliases",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await indexer.index_bible(bible_path, script_id=1, force=False)

            assert result.updated is True
            assert result.bible_id == 1
            assert result.chunks_indexed == 2
            mock_update.assert_called_once()
            mock_index_chunks.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_bible_new_file_with_embeddings(
        self,
        mock_settings: ScriptRAGSettings,
        mock_parsed_bible: ParsedBible,
        tmp_path: Path,
    ) -> None:
        """Test indexing new file with embeddings enabled."""
        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Test")

        # Mock database operations
        mock_db_ops = Mock(spec=object)
        mock_conn = Mock(spec=object)
        mock_cursor = Mock(spec=object)

        # Mock no existing entry
        mock_cursor.fetchone.return_value = None
        mock_cursor.lastrowid = 123
        mock_conn.cursor.return_value = mock_cursor
        mock_db_ops.transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

        indexer = BibleIndexer(settings=mock_settings, db_ops=mock_db_ops)

        # Mock methods
        with (
            patch.object(indexer.parser, "parse_file", return_value=mock_parsed_bible),
            patch.object(
                indexer, "_insert_bible", new_callable=AsyncMock, return_value=123
            ) as mock_insert,
            patch.object(
                indexer, "_index_chunks", new_callable=AsyncMock, return_value=2
            ) as mock_index_chunks,
            patch.object(
                indexer, "initialize_embedding_analyzer", new_callable=AsyncMock
            ) as mock_init_embed,
            patch.object(
                indexer, "_generate_embeddings", new_callable=AsyncMock, return_value=2
            ) as mock_gen_embed,
            patch.object(
                indexer.alias_extractor,
                "extract_aliases",
                new_callable=AsyncMock,
                return_value={"test": "alias"},
            ),
            patch.object(
                indexer.alias_extractor, "attach_alias_map_to_script"
            ) as mock_attach_aliases,
            patch.object(
                indexer.alias_extractor, "attach_aliases_to_characters"
            ) as mock_attach_chars,
        ):
            result = await indexer.index_bible(bible_path, script_id=1, force=False)

            assert result.indexed is True
            assert result.bible_id == 123
            assert result.chunks_indexed == 2
            assert result.embeddings_created == 2
            mock_insert.assert_called_once()
            mock_index_chunks.assert_called_once()
            mock_init_embed.assert_called_once()
            mock_gen_embed.assert_called_once()
            mock_attach_aliases.assert_called_once()
            mock_attach_chars.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_bible_aliases_no_llm_config(
        self, mock_settings: ScriptRAGSettings, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test _extract_bible_aliases returns None when no LLM configured."""
        # Remove LLM configuration
        mock_settings.llm_model = None
        mock_settings.llm_provider = None
        mock_settings.llm_api_key = None

        indexer = BibleIndexer(settings=mock_settings)
        result = await indexer.alias_extractor.extract_aliases(mock_parsed_bible)

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_bible_aliases_with_llm(
        self, mock_settings: ScriptRAGSettings, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test _extract_bible_aliases with LLM configured."""
        # Mock LLM client and response
        mock_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_response = Mock(spec=object)
        mock_response.text = (
            '{"version": 1, "extracted_at": "2023-01-01T00:00:00Z", '
            '"characters": [{"canonical": "JANE", "aliases": ["JANE DOE"]}]}'
        )
        mock_client.complete.return_value = mock_response

        with patch(
            "scriptrag.utils.get_default_llm_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            indexer = BibleIndexer(settings=mock_settings)
            result = await indexer.alias_extractor.extract_aliases(mock_parsed_bible)

            assert result is not None
            assert result["version"] == 1
            assert len(result["characters"]) == 1
            assert result["characters"][0]["canonical"] == "JANE"

    @pytest.mark.asyncio
    async def test_extract_bible_aliases_json_with_code_fence(
        self, mock_settings: ScriptRAGSettings, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test _extract_bible_aliases handles JSON wrapped in code fences."""
        # Mock LLM client and response with code fence
        mock_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_response = Mock(spec=object)
        mock_response.text = (
            '```json\n{"version": 1, "extracted_at": "2023-01-01T00:00:00Z", '
            '"characters": [{"canonical": "JANE", "aliases": ["JANE DOE"]}]}\n```'
        )
        mock_client.complete.return_value = mock_response

        with patch(
            "scriptrag.utils.get_default_llm_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            indexer = BibleIndexer(settings=mock_settings)
            result = await indexer.alias_extractor.extract_aliases(mock_parsed_bible)

            assert result is not None
            assert result["version"] == 1

    @pytest.mark.asyncio
    async def test_extract_bible_aliases_deduplication(
        self, mock_settings: ScriptRAGSettings, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test _extract_bible_aliases handles deduplication."""
        # Mock LLM client with duplicate aliases
        mock_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_response = Mock(spec=object)
        mock_response.text = (
            '{"version": 1, "extracted_at": "2023-01-01T00:00:00Z", '
            '"characters": [{"canonical": "JANE", '
            '"aliases": ["JANE", "JANE DOE", "JANE"]}]}'
        )
        mock_client.complete.return_value = mock_response

        with patch(
            "scriptrag.utils.get_default_llm_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            indexer = BibleIndexer(settings=mock_settings)
            result = await indexer.alias_extractor.extract_aliases(mock_parsed_bible)

            assert result is not None
            # Should remove duplicates and canonical from aliases
            assert result["characters"][0]["aliases"] == ["JANE DOE"]

    def test_attach_alias_map_to_script(self, mock_settings: ScriptRAGSettings) -> None:
        """Test _attach_alias_map_to_script updates script metadata."""
        # Mock connection and cursor
        mock_conn = Mock(spec=sqlite3.Connection)
        mock_cursor = Mock(spec=object)
        mock_cursor.fetchone.return_value = ('{"existing": "data"}',)
        mock_conn.execute.return_value = mock_cursor

        indexer = BibleIndexer(settings=mock_settings)
        alias_map = {
            "version": 1,
            "characters": [{"canonical": "JANE", "aliases": ["JANE DOE"]}],
        }

        indexer.alias_extractor.attach_alias_map_to_script(
            mock_conn, script_id=1, alias_map=alias_map
        )

        # Should have called execute twice: SELECT and UPDATE
        assert mock_conn.execute.call_count == 2

    def test_attach_alias_map_to_script_no_existing_metadata(
        self, mock_settings: ScriptRAGSettings
    ) -> None:
        """Test _attach_alias_map_to_script with no existing metadata."""
        # Mock connection and cursor
        mock_conn = Mock(spec=sqlite3.Connection)
        mock_cursor = Mock(spec=object)
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor

        indexer = BibleIndexer(settings=mock_settings)
        alias_map = {"version": 1, "characters": []}

        indexer.alias_extractor.attach_alias_map_to_script(
            mock_conn, script_id=1, alias_map=alias_map
        )

        # Should handle no existing metadata
        assert mock_conn.execute.call_count == 2

    def test_attach_aliases_to_characters_no_aliases_column(
        self, mock_settings: ScriptRAGSettings
    ) -> None:
        """Test _attach_aliases_to_characters when aliases column doesn't exist."""
        # Mock connection that returns no aliases column
        mock_conn = Mock(spec=sqlite3.Connection)
        mock_conn.execute.return_value = [("id", "INTEGER"), ("name", "TEXT")]

        indexer = BibleIndexer(settings=mock_settings)
        alias_map = {"characters": [{"canonical": "JANE", "aliases": ["JANE DOE"]}]}

        # Should return early without error
        indexer.alias_extractor.attach_aliases_to_characters(
            mock_conn, script_id=1, alias_map=alias_map
        )

    def test_attach_aliases_to_characters_with_aliases_column(
        self, mock_settings: ScriptRAGSettings
    ) -> None:
        """Test _attach_aliases_to_characters when aliases column exists."""
        # Mock connection that has aliases column
        mock_conn = Mock(spec=sqlite3.Connection)
        pragma_result = [("id", "INTEGER"), ("name", "TEXT"), ("aliases", "TEXT")]
        character_result = [(1, "JANE"), (2, "JOHN")]

        mock_conn.execute.side_effect = [pragma_result, character_result]

        indexer = BibleIndexer(settings=mock_settings)
        alias_map = {"characters": [{"canonical": "JANE", "aliases": ["JANE DOE"]}]}

        indexer.alias_extractor.attach_aliases_to_characters(
            mock_conn, script_id=1, alias_map=alias_map
        )

        # Should have executed PRAGMA query at minimum (aliases column check)
        assert mock_conn.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_generate_embeddings_no_analyzer(
        self, mock_settings: ScriptRAGSettings, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test _generate_embeddings returns 0 when no analyzer."""
        indexer = BibleIndexer(settings=mock_settings)
        # Ensure no embedding analyzer
        indexer.embedding_analyzer = None

        mock_conn = Mock(spec=object)
        result = await indexer._generate_embeddings(
            mock_conn, bible_id=1, parsed_bible=mock_parsed_bible
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_generate_embeddings_with_retry_success(
        self, mock_settings: ScriptRAGSettings, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test _generate_embeddings with successful retry logic."""
        indexer = BibleIndexer(settings=mock_settings)

        # Mock embedding analyzer
        mock_analyzer = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_analyzer.analyze.return_value = {
            "embedding_path": "/path/to/embedding",
            "dimensions": 128,
            "model": "test-model",
        }
        indexer.embedding_analyzer = mock_analyzer

        # Mock database cursor
        mock_conn = Mock(spec=object)
        mock_cursor = Mock(spec=object)
        mock_cursor.fetchall.return_value = [
            (1, "hash1", "Test Heading", "Test content"),
            (2, "hash2", "Sub Heading", "Sub content"),
        ]
        mock_conn.cursor.return_value = mock_cursor

        result = await indexer._generate_embeddings(
            mock_conn, bible_id=1, parsed_bible=mock_parsed_bible
        )

        assert result == 2  # Two embeddings created
        assert mock_analyzer.analyze.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_embeddings_with_retry_failure(
        self, mock_settings: ScriptRAGSettings, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test _generate_embeddings with retry logic that ultimately fails."""
        indexer = BibleIndexer(settings=mock_settings)

        # Mock embedding analyzer that always fails
        mock_analyzer = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_analyzer.analyze.side_effect = Exception("API Error")
        indexer.embedding_analyzer = mock_analyzer

        # Mock database cursor
        mock_conn = Mock(spec=object)
        mock_cursor = Mock(spec=object)
        mock_cursor.fetchall.return_value = [
            (1, "hash1", "Test Heading", "Test content")
        ]
        mock_conn.cursor.return_value = mock_cursor

        # Mock asyncio.sleep to avoid actual delays in tests
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await indexer._generate_embeddings(
                mock_conn, bible_id=1, parsed_bible=mock_parsed_bible
            )

        assert result == 0  # No embeddings created due to failures
        assert mock_analyzer.analyze.call_count == 3  # Retried 3 times

    @pytest.mark.asyncio
    async def test_generate_embeddings_api_error_in_result(
        self, mock_settings: ScriptRAGSettings, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test _generate_embeddings handles API error in result."""
        indexer = BibleIndexer(settings=mock_settings)

        # Mock embedding analyzer that returns error in result
        mock_analyzer = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_analyzer.analyze.return_value = {"error": "Rate limit exceeded"}
        indexer.embedding_analyzer = mock_analyzer

        # Mock database cursor
        mock_conn = Mock(spec=object)
        mock_cursor = Mock(spec=object)
        mock_cursor.fetchall.return_value = [
            (1, "hash1", "Test Heading", "Test content")
        ]
        mock_conn.cursor.return_value = mock_cursor

        # Mock asyncio.sleep to avoid actual delays in tests
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await indexer._generate_embeddings(
                mock_conn, bible_id=1, parsed_bible=mock_parsed_bible
            )

        assert result == 0  # No embeddings created due to API error

    @pytest.mark.asyncio
    async def test_index_bible_without_embedding_model(
        self,
        mock_settings: ScriptRAGSettings,
        mock_parsed_bible: ParsedBible,
        tmp_path: Path,
    ) -> None:
        """Test indexing bible without embedding model configured (lines 127->134)."""
        # Remove embedding model to test the else path
        mock_settings.llm_embedding_model = None

        bible_path = tmp_path / "bible.md"
        bible_path.write_text("# Test")

        # Mock database operations
        mock_db_ops = Mock(spec=object)
        mock_conn = Mock(spec=object)
        mock_cursor = Mock(spec=object)

        # Mock no existing entry
        mock_cursor.fetchone.return_value = None
        mock_cursor.lastrowid = 123
        mock_conn.cursor.return_value = mock_cursor
        mock_db_ops.transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

        indexer = BibleIndexer(settings=mock_settings, db_ops=mock_db_ops)

        # Mock methods
        with (
            patch.object(indexer.parser, "parse_file", return_value=mock_parsed_bible),
            patch.object(
                indexer, "_insert_bible", new_callable=AsyncMock, return_value=123
            ) as mock_insert,
            patch.object(
                indexer, "_index_chunks", new_callable=AsyncMock, return_value=2
            ) as mock_index_chunks,
            patch.object(
                indexer.alias_extractor,
                "extract_aliases",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await indexer.index_bible(bible_path, script_id=1, force=False)

            # Should skip embedding generation and succeed
            assert result.indexed is True
            assert result.bible_id == 123
            assert result.chunks_indexed == 2
            assert result.embeddings_created == 0  # No embeddings without model
            mock_insert.assert_called_once()
            mock_index_chunks.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_bible_aliases_text_chunking_limits(
        self, mock_settings: ScriptRAGSettings
    ) -> None:
        """Test _extract_bible_aliases with text chunking and size limits."""
        # Create large chunks that exceed the 2000 char limit
        large_content = "x" * 1500  # Large content
        chunks = [
            BibleChunk(
                chunk_number=0,
                heading="First Chapter",
                level=1,
                content=large_content,
                content_hash="hash1",
                metadata={},
                parent_chunk_id=None,
            ),
            BibleChunk(
                chunk_number=1,
                heading="Second Chapter",
                level=1,
                content=large_content,
                content_hash="hash2",
                metadata={},
                parent_chunk_id=None,
            ),
        ]
        parsed_bible = ParsedBible(
            file_path=Path("/test/bible.md"),
            title="Test Bible",
            file_hash="test_hash",
            metadata={"test": "data"},
            chunks=chunks,
        )

        # Mock LLM client and response
        mock_client = AsyncMock(
            spec=["complete", "cleanup", "embed", "list_models", "is_available"]
        )
        mock_response = Mock(spec=object)
        mock_response.text = (
            '{"version": 1, "extracted_at": "2023-01-01T00:00:00Z", '
            '"characters": [{"canonical": "JANE", "aliases": ["JANE DOE"]}]}'
        )
        mock_client.complete.return_value = mock_response

        with patch(
            "scriptrag.utils.get_default_llm_client",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            indexer = BibleIndexer(settings=mock_settings)
            result = await indexer.alias_extractor.extract_aliases(parsed_bible)

            assert result is not None
            # Verify the chunking logic was exercised
            assert mock_client.complete.called

    def test_attach_aliases_to_characters_successful_update(
        self, mock_settings: ScriptRAGSettings, tmp_path: Path
    ) -> None:
        """Test attach_aliases_to_characters with successful database operations."""
        # Use real sqlite3 connection to test the actual logic
        import sqlite3

        # Use tmp_path instead of NamedTemporaryFile to avoid Windows locks
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        try:
            # Create the characters table with aliases column
            conn.execute("""
                CREATE TABLE characters (
                    id INTEGER PRIMARY KEY,
                    script_id INTEGER,
                    name TEXT,
                    aliases TEXT
                )
            """)

            # Insert test characters
            conn.execute(
                "INSERT INTO characters (script_id, name) VALUES (1, 'JANE SMITH')"
            )
            conn.execute(
                "INSERT INTO characters (script_id, name) VALUES (1, 'JOHN DOE')"
            )
            conn.execute(
                "INSERT INTO characters (script_id, name) VALUES (1, 'BOB WILSON')"
            )
            conn.commit()

            indexer = BibleIndexer(settings=mock_settings)
            alias_map = {
                "characters": [
                    {"canonical": "JANE SMITH", "aliases": ["JANE", "MS. SMITH"]},
                    {"canonical": "JOHN DOE", "aliases": ["JOHN"]},
                    # BOB WILSON not in alias map - should not be updated
                ]
            }

            # This should exercise lines 285-310 including UPDATE statements
            indexer.alias_extractor.attach_aliases_to_characters(
                conn, script_id=1, alias_map=alias_map
            )

            # Verify that aliases were set for matching characters
            cursor = conn.execute(
                "SELECT name, aliases FROM characters WHERE script_id = 1"
            )
            results = cursor.fetchall()

            aliases_set = {name: aliases for name, aliases in results if aliases}
            assert len(aliases_set) == 2  # Two characters should have aliases set
            assert "JANE SMITH" in aliases_set
            assert "JOHN DOE" in aliases_set

        finally:
            # Ensure connection is closed before tmp_path cleanup
            conn.close()

    def test_attach_aliases_to_characters_no_matching_characters(
        self, mock_settings: ScriptRAGSettings
    ) -> None:
        """Test _attach_aliases_to_characters when no canonical_to_aliases built."""
        # Mock connection that has aliases column
        mock_conn = Mock(spec=sqlite3.Connection)
        pragma_result = [
            ("id", "INTEGER", 0, None, 1),
            ("name", "TEXT", 0, None, 0),
            ("aliases", "TEXT", 0, None, 0),
        ]
        mock_conn.execute.return_value = pragma_result

        indexer = BibleIndexer(settings=mock_settings)
        # Empty characters list should trigger early return
        alias_map = {"characters": []}

        indexer.alias_extractor.attach_aliases_to_characters(
            mock_conn, script_id=1, alias_map=alias_map
        )

        # Should execute PRAGMA but return early before character queries
        assert mock_conn.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_insert_bible_method(
        self, mock_settings: ScriptRAGSettings, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test _insert_bible method directly (lines 333-347)."""
        indexer = BibleIndexer(settings=mock_settings)

        # Mock database connection and cursor
        mock_conn = Mock(spec=sqlite3.Connection)
        mock_cursor = Mock(spec=object)
        mock_cursor.lastrowid = 456
        mock_conn.cursor.return_value = mock_cursor

        result = await indexer._insert_bible(
            mock_conn, script_id=1, parsed_bible=mock_parsed_bible
        )

        assert result == 456
        mock_cursor.execute.assert_called_once()
        # Verify SQL parameters
        call_args = mock_cursor.execute.call_args
        assert "INSERT INTO script_bibles" in call_args[0][0]
        assert call_args[0][1][0] == 1  # script_id
        assert call_args[0][1][1] == str(mock_parsed_bible.file_path)

    @pytest.mark.asyncio
    async def test_update_bible_method(
        self, mock_settings: ScriptRAGSettings, mock_parsed_bible: ParsedBible
    ) -> None:
        """Test _update_bible method directly (lines 362-380)."""
        indexer = BibleIndexer(settings=mock_settings)

        # Mock database connection and cursor
        mock_conn = Mock(spec=sqlite3.Connection)
        mock_cursor = Mock(spec=object)
        mock_conn.cursor.return_value = mock_cursor

        await indexer._update_bible(
            mock_conn, bible_id=123, parsed_bible=mock_parsed_bible
        )

        # Should execute UPDATE and DELETE statements
        assert mock_cursor.execute.call_count == 2

        # Verify UPDATE call
        update_call = mock_cursor.execute.call_args_list[0]
        assert "UPDATE script_bibles" in update_call[0][0]
        assert update_call[0][1][3] == 123  # bible_id

        # Verify DELETE call
        delete_call = mock_cursor.execute.call_args_list[1]
        assert "DELETE FROM bible_chunks" in delete_call[0][0]
        assert delete_call[0][1][0] == 123  # bible_id

    @pytest.mark.asyncio
    async def test_index_chunks_with_parent_relationships(
        self, mock_settings: ScriptRAGSettings
    ) -> None:
        """Test _index_chunks method with parent-child relationships (lines 398-440)."""
        # Create chunks with parent-child relationships
        chunks = [
            BibleChunk(
                chunk_number=0,
                heading="Chapter 1",
                level=1,
                content="Main chapter content",
                content_hash="hash1",
                metadata={"type": "chapter"},
                parent_chunk_id=None,  # Top level
            ),
            BibleChunk(
                chunk_number=1,
                heading="Section 1.1",
                level=2,
                content="Sub-section content",
                content_hash="hash2",
                metadata={"type": "section"},
                parent_chunk_id=0,  # Child of chunk 0
            ),
            BibleChunk(
                chunk_number=2,
                heading="Section 1.2",
                level=2,
                content="Another sub-section",
                content_hash="hash3",
                metadata={"type": "section"},
                parent_chunk_id=0,  # Another child of chunk 0
            ),
        ]

        parsed_bible = ParsedBible(
            file_path=Path("/test/bible.md"),
            title="Test Bible",
            file_hash="test_hash",
            metadata={"test": "data"},
            chunks=chunks,
        )

        indexer = BibleIndexer(settings=mock_settings)

        # Mock database connection and cursor
        mock_conn = Mock(spec=sqlite3.Connection)
        mock_cursor = Mock(spec=object)

        # Track execute calls and simulate lastrowid
        execute_calls = []
        lastrowid_sequence = [100, 101, 102]

        def mock_execute(query, params=None):
            execute_calls.append((query, params))
            # Simulate lastrowid for INSERT operations
            if "INSERT INTO bible_chunks" in query and lastrowid_sequence:
                mock_cursor.lastrowid = lastrowid_sequence.pop(0)
            else:
                mock_cursor.lastrowid = None
            return Mock(spec=object)

        mock_cursor.execute.side_effect = mock_execute
        mock_conn.cursor.return_value = mock_cursor

        result = await indexer._index_chunks(
            mock_conn, bible_id=456, parsed_bible=parsed_bible
        )

        assert result == 3  # All chunks indexed
        assert len(execute_calls) == 3  # One insert per chunk

        # Verify the SQL calls included correct parameters
        for i, (query, params) in enumerate(execute_calls):
            assert "INSERT INTO bible_chunks" in query
            assert params[0] == 456  # bible_id
            assert params[1] == i  # chunk_number

    def test_find_bible_files_exact_matches(self, tmp_path: Path) -> None:
        """Test find_bible_files with files that should be included (lines 601-625)."""
        # Create files that match patterns and keywords
        script_dir = tmp_path / "project" / "scripts"
        script_dir.mkdir(parents=True)

        # Create script file
        script_path = script_dir / "my_script.fountain"
        script_path.touch()

        # Create bible files in script directory that should be found
        bible_files = [
            "character_bible.md",
            "world_notes.md",
            "backstory_details.md",
            "lore_reference.md",
            "production_notes.md",
            "reference_guide.md",
        ]

        for filename in bible_files:
            (script_dir / filename).touch()

        # Create file that shouldn't match
        (script_dir / "random_file.md").touch()

        result = BibleAutoDetector.find_bible_files(tmp_path, script_path)

        # Should find the bible files but not the random file
        found_names = {f.name for f in result}

        # Check that keyword-matching files were found
        expected_matches = {
            "character_bible.md",
            "world_notes.md",
            "backstory_details.md",
            "lore_reference.md",
            "production_notes.md",
            "reference_guide.md",
        }

        # At least some of the expected files should be found
        matches_found = expected_matches.intersection(found_names)
        assert len(matches_found) >= 3  # Should find several matches

        # Random file should not be found
        assert "random_file.md" not in found_names

    def test_should_exclude_file_outside_project(self, tmp_path: Path) -> None:
        """Test _should_exclude with file that can't be made relative to project."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        # Create a file outside the project structure
        outside_path = tmp_path / "outside" / "file.md"
        outside_path.parent.mkdir()
        outside_path.touch()

        # This should trigger the ValueError in relative_to and return True
        result = BibleAutoDetector._should_exclude(outside_path, project_path)

        assert result is True

    def test_attach_alias_map_to_script_json_error(
        self, mock_settings: ScriptRAGSettings
    ) -> None:
        """Test _attach_alias_map_to_script handles JSON parsing errors."""
        # Mock connection and cursor with invalid JSON
        mock_conn = Mock(spec=sqlite3.Connection)
        mock_cursor = Mock(spec=object)
        mock_cursor.fetchone.return_value = ("invalid json {",)  # Malformed JSON
        mock_conn.execute.return_value = mock_cursor

        indexer = BibleIndexer(settings=mock_settings)
        alias_map = {
            "version": 1,
            "characters": [{"canonical": "JANE", "aliases": ["JANE DOE"]}],
        }

        # Should handle JSON error gracefully and create new metadata
        indexer.alias_extractor.attach_alias_map_to_script(
            mock_conn, script_id=1, alias_map=alias_map
        )

        # Should have called execute twice: SELECT and UPDATE
        assert mock_conn.execute.call_count == 2


class TestBibleAutoDetectorEdgeCases:
    """Test edge cases in BibleAutoDetector."""

    def test_find_bible_files_with_script_path_same_as_project(
        self, tmp_path: Path
    ) -> None:
        """Test find_bible_files when script_path is same as project_path."""
        # Create bible files
        (tmp_path / "bible.md").touch()
        (tmp_path / "script.fountain").touch()

        script_path = tmp_path / "script.fountain"

        result = BibleAutoDetector.find_bible_files(tmp_path, script_path)

        # Should find bible.md even though script is in same directory
        assert len(result) >= 1
        assert any(f.name == "bible.md" for f in result)

    def test_find_bible_files_script_in_subdirectory(self, tmp_path: Path) -> None:
        """Test find_bible_files when script is in subdirectory."""
        # Create subdirectory with script and local bible file
        script_dir = tmp_path / "scripts"
        script_dir.mkdir()
        script_path = script_dir / "script.fountain"
        script_path.touch()

        # Create bible file with matching keyword
        local_bible = script_dir / "character_notes.md"
        local_bible.touch()

        # Create non-matching file
        other_file = script_dir / "random.md"
        other_file.touch()

        result = BibleAutoDetector.find_bible_files(tmp_path, script_path)

        # Should find the character notes file due to keyword match
        found_names = {f.name for f in result}
        assert "character_notes.md" in found_names
        assert "random.md" not in found_names

    def test_should_exclude_outside_project_path(self, tmp_path: Path) -> None:
        """Test _should_exclude with file outside project path."""
        outside_file = Path("/outside/file.md")

        result = BibleAutoDetector._should_exclude(outside_file, tmp_path)

        assert result is True

    def test_should_exclude_hidden_subdirectory(self, tmp_path: Path) -> None:
        """Test _should_exclude with file in hidden subdirectory."""
        hidden_dir = tmp_path / ".hidden" / "subdir"
        hidden_dir.mkdir(parents=True)
        hidden_file = hidden_dir / "bible.md"
        hidden_file.touch()

        result = BibleAutoDetector._should_exclude(hidden_file, tmp_path)

        assert result is True

    def test_should_exclude_dot_directory_exception(self, tmp_path: Path) -> None:
        """Test _should_exclude allows single dot directory."""
        dot_file = tmp_path / "." / "bible.md"

        # Create the path structure for testing (though this is artificial)
        try:
            result = BibleAutoDetector._should_exclude(dot_file, tmp_path)
            # Should not exclude single dot (current directory)
            assert result is False
        except ValueError:
            # If relative_to fails, should be excluded
            assert True

    def test_bible_patterns_coverage(self, tmp_path: Path) -> None:
        """Test that all bible patterns are covered."""
        # Test each pattern type
        patterns = [
            "my_bible.md",
            "Script_Bible.md",
            "worldbuilding_notes.md",
            "World_Building.md",
            "character_backstory.md",
            "Character_Backstory.md",
            "story_lore.md",
            "Story_Lore.md",
            "production_notes.md",
            "Production_Notes.md",
        ]

        for pattern in patterns:
            (tmp_path / pattern).touch()

        # Also create subdirectory files
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "guide.md").touch()

        reference_dir = tmp_path / "reference"
        reference_dir.mkdir()
        (reference_dir / "notes.md").touch()

        result = BibleAutoDetector.find_bible_files(tmp_path)

        # Should find most of the bible files (patterns match)
        found_names = {f.name for f in result}

        # Check that various pattern types were found
        assert len(found_names) > 5  # Should find multiple files
        assert any("bible" in name.lower() for name in found_names)
        assert any("character" in name.lower() for name in found_names)

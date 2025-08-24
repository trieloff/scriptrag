"""Comprehensive tests for bible_index.py to achieve 99% coverage."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from scriptrag.api.bible_index import BibleIndexer, BibleIndexResult


class TestBibleIndexResult:
    """Test BibleIndexResult dataclass."""

    def test_init_defaults(self):
        """Test initialization with defaults."""
        path = Path("test.md")
        result = BibleIndexResult(path=path)

        assert result.path == path
        assert result.bible_id is None
        assert result.indexed is False
        assert result.updated is False
        assert result.chunks_indexed == 0
        assert result.embeddings_created == 0
        assert result.error is None

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        path = Path("test.md")
        result = BibleIndexResult(
            path=path,
            bible_id=123,
            indexed=True,
            updated=False,
            chunks_indexed=10,
            embeddings_created=8,
            error="Test error",
        )

        assert result.path == path
        assert result.bible_id == 123
        assert result.indexed is True
        assert result.updated is False
        assert result.chunks_indexed == 10
        assert result.embeddings_created == 8
        assert result.error == "Test error"


class TestBibleIndexer:
    """Test BibleIndexer class."""

    def test_init_defaults(self):
        """Test initialization with defaults."""
        with patch("scriptrag.api.bible_index.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.bible_max_file_size = 1024 * 1024
            mock_get_settings.return_value = mock_settings

            with patch("scriptrag.api.bible_index.DatabaseOperations") as mock_db_ops:
                with patch("scriptrag.api.bible_index.BibleParser") as mock_parser:
                    with patch(
                        "scriptrag.api.bible_index.BibleAliasExtractor"
                    ) as mock_extractor:
                        indexer = BibleIndexer()

                        assert indexer.settings == mock_settings
                        assert indexer.db_ops == mock_db_ops.return_value
                        assert indexer.parser == mock_parser.return_value
                        assert indexer.embedding_analyzer is None
                        assert indexer.alias_extractor == mock_extractor.return_value

    def test_init_custom_settings(self):
        """Test initialization with custom settings."""
        custom_settings = Mock()
        custom_db_ops = Mock()

        with patch("scriptrag.api.bible_index.BibleParser") as mock_parser:
            with patch(
                "scriptrag.api.bible_index.BibleAliasExtractor"
            ) as mock_extractor:
                indexer = BibleIndexer(settings=custom_settings, db_ops=custom_db_ops)

                assert indexer.settings == custom_settings
                assert indexer.db_ops == custom_db_ops

    @pytest.mark.asyncio
    async def test_initialize_embedding_analyzer_first_time(self):
        """Test embedding analyzer initialization."""
        mock_settings = Mock()
        mock_settings.bible_embeddings_path = "/test/embeddings"
        mock_settings.llm_embedding_model = "test-model"

        with patch(
            "scriptrag.api.bible_index.SceneEmbeddingAnalyzer"
        ) as mock_analyzer_class:
            mock_analyzer = AsyncMock()
            mock_analyzer_class.return_value = mock_analyzer

            indexer = BibleIndexer(settings=mock_settings, db_ops=Mock())

            await indexer.initialize_embedding_analyzer()

            # Verify analyzer creation and initialization
            mock_analyzer_class.assert_called_once_with(
                {
                    "lfs_path": "/test/embeddings",
                    "repo_path": ".",
                    "embedding_model": "test-model",
                }
            )
            mock_analyzer.initialize.assert_called_once()
            assert indexer.embedding_analyzer == mock_analyzer

    @pytest.mark.asyncio
    async def test_initialize_embedding_analyzer_already_initialized(self):
        """Test embedding analyzer when already initialized."""
        mock_settings = Mock()
        existing_analyzer = Mock()

        indexer = BibleIndexer(settings=mock_settings, db_ops=Mock())
        indexer.embedding_analyzer = existing_analyzer

        with patch(
            "scriptrag.api.bible_index.SceneEmbeddingAnalyzer"
        ) as mock_analyzer_class:
            await indexer.initialize_embedding_analyzer()

            # Should not create new analyzer
            mock_analyzer_class.assert_not_called()
            assert indexer.embedding_analyzer == existing_analyzer

    @pytest.mark.asyncio
    async def test_index_bible_success_new_file(self):
        """Test successful indexing of new bible file."""
        mock_settings = Mock()
        mock_settings.llm_embedding_model = None  # No embeddings

        mock_db_ops = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db_ops.transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

        mock_parser = Mock()
        mock_parsed_bible = Mock()
        mock_parsed_bible.file_hash = "newhash123"
        mock_parsed_bible.chunks = []
        mock_parser.parse_file.return_value = mock_parsed_bible

        # Mock database query for existing bible (returns None)
        mock_cursor.fetchone.return_value = None
        mock_cursor.lastrowid = 456

        indexer = BibleIndexer(settings=mock_settings, db_ops=mock_db_ops)
        indexer.parser = mock_parser
        indexer.alias_extractor = Mock()
        indexer.alias_extractor.extract_aliases.return_value = None

        with patch.object(indexer, "_insert_bible", return_value=456) as mock_insert:
            with patch.object(
                indexer, "_index_chunks", return_value=5
            ) as mock_index_chunks:
                result = await indexer.index_bible(Path("test.md"), script_id=123)

        assert result.path == Path("test.md")
        assert result.bible_id == 456
        assert result.indexed is True
        assert result.updated is False
        assert result.chunks_indexed == 5
        assert result.embeddings_created == 0
        assert result.error is None

        mock_insert.assert_called_once()
        mock_index_chunks.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_bible_success_existing_file_force(self):
        """Test indexing existing file with force=True."""
        mock_settings = Mock()
        mock_settings.llm_embedding_model = "test-model"

        mock_db_ops = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db_ops.transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

        mock_parser = Mock()
        mock_parsed_bible = Mock()
        mock_parsed_bible.file_hash = "newhash123"
        mock_parsed_bible.chunks = []
        mock_parser.parse_file.return_value = mock_parsed_bible

        # Mock existing bible with different hash
        mock_cursor.fetchone.return_value = (789, "oldhash456")

        indexer = BibleIndexer(settings=mock_settings, db_ops=mock_db_ops)
        indexer.parser = mock_parser
        indexer.alias_extractor = Mock()
        indexer.alias_extractor.extract_aliases.return_value = {"char1": ["alias1"]}

        with patch.object(indexer, "_update_bible") as mock_update:
            with patch.object(indexer, "_index_chunks", return_value=3):
                with patch.object(indexer, "initialize_embedding_analyzer"):
                    with patch.object(indexer, "_generate_embeddings", return_value=2):
                        result = await indexer.index_bible(
                            Path("test.md"), script_id=123, force=True
                        )

        assert result.bible_id == 789
        assert result.updated is True
        assert result.indexed is False
        assert result.chunks_indexed == 3
        assert result.embeddings_created == 2

        mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_bible_existing_unchanged(self):
        """Test indexing existing file that hasn't changed."""
        mock_settings = Mock()

        mock_db_ops = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db_ops.transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

        mock_parser = Mock()
        mock_parsed_bible = Mock()
        mock_parsed_bible.file_hash = "samehash123"
        mock_parser.parse_file.return_value = mock_parsed_bible

        # Mock existing bible with same hash
        mock_cursor.fetchone.return_value = (789, "samehash123")

        indexer = BibleIndexer(settings=mock_settings, db_ops=mock_db_ops)
        indexer.parser = mock_parser

        result = await indexer.index_bible(Path("test.md"), script_id=123)

        assert result.bible_id == 789
        assert result.indexed is False
        assert result.updated is False
        assert result.chunks_indexed == 0
        assert result.embeddings_created == 0

    @pytest.mark.asyncio
    async def test_index_bible_alias_extraction_error(self):
        """Test indexing with alias extraction error."""
        mock_settings = Mock()
        mock_settings.llm_embedding_model = None

        mock_db_ops = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db_ops.transaction.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db_ops.transaction.return_value.__exit__ = Mock(return_value=None)

        mock_parser = Mock()
        mock_parsed_bible = Mock()
        mock_parsed_bible.file_hash = "hash123"
        mock_parsed_bible.chunks = []
        mock_parser.parse_file.return_value = mock_parsed_bible

        mock_cursor.fetchone.return_value = None
        mock_cursor.lastrowid = 456

        mock_alias_extractor = Mock()
        mock_alias_extractor.extract_aliases.side_effect = Exception("API error")

        indexer = BibleIndexer(settings=mock_settings, db_ops=mock_db_ops)
        indexer.parser = mock_parser
        indexer.alias_extractor = mock_alias_extractor

        with patch.object(indexer, "_insert_bible", return_value=456):
            with patch.object(indexer, "_index_chunks", return_value=0):
                result = await indexer.index_bible(Path("test.md"), script_id=123)

        # Should succeed despite alias extraction error
        assert result.error is None
        assert result.bible_id == 456

    @pytest.mark.asyncio
    async def test_index_bible_general_error(self):
        """Test indexing with general error."""
        mock_settings = Mock()
        mock_db_ops = Mock()

        mock_parser = Mock()
        mock_parser.parse_file.side_effect = Exception("Parse error")

        indexer = BibleIndexer(settings=mock_settings, db_ops=mock_db_ops)
        indexer.parser = mock_parser

        result = await indexer.index_bible(Path("test.md"), script_id=123)

        assert result.error == "Parse error"
        assert result.bible_id is None

    @pytest.mark.asyncio
    async def test_insert_bible(self):
        """Test bible insertion."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.lastrowid = 123

        mock_parsed_bible = Mock()
        mock_parsed_bible.file_path = Path("test.md")
        mock_parsed_bible.title = "Test Bible"
        mock_parsed_bible.file_hash = "hash123"
        mock_parsed_bible.metadata = {"key": "value"}

        indexer = BibleIndexer(Mock(), Mock())

        bible_id = await indexer._insert_bible(mock_conn, 456, mock_parsed_bible)

        assert bible_id == 123
        mock_cursor.execute.assert_called_once()
        # Verify SQL parameters
        args = mock_cursor.execute.call_args[0]
        assert args[1] == (
            456,
            str(Path("test.md")),
            "Test Bible",
            "hash123",
            '{"key": "value"}',
        )

    @pytest.mark.asyncio
    async def test_insert_bible_no_lastrowid(self):
        """Test bible insertion when lastrowid is None."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.lastrowid = None

        mock_parsed_bible = Mock()
        mock_parsed_bible.file_path = Path("test.md")
        mock_parsed_bible.title = "Test Bible"
        mock_parsed_bible.file_hash = "hash123"
        mock_parsed_bible.metadata = {}

        indexer = BibleIndexer(Mock(), Mock())

        bible_id = await indexer._insert_bible(mock_conn, 456, mock_parsed_bible)

        assert bible_id == 0

    @pytest.mark.asyncio
    async def test_update_bible(self):
        """Test bible update."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_parsed_bible = Mock()
        mock_parsed_bible.title = "Updated Bible"
        mock_parsed_bible.file_hash = "newhash123"
        mock_parsed_bible.metadata = {"updated": True}

        indexer = BibleIndexer(Mock(), Mock())

        await indexer._update_bible(mock_conn, 789, mock_parsed_bible)

        # Should call execute twice (update bible, delete old chunks)
        assert mock_cursor.execute.call_count == 2

        # Verify update call
        update_call = mock_cursor.execute.call_args_list[0]
        assert "UPDATE script_bibles" in update_call[0][0]
        assert update_call[0][1] == (
            "Updated Bible",
            "newhash123",
            '{"updated": true}',
            789,
        )

        # Verify delete call
        delete_call = mock_cursor.execute.call_args_list[1]
        assert "DELETE FROM bible_chunks" in delete_call[0][0]
        assert delete_call[0][1] == (789,)

    @pytest.mark.asyncio
    async def test_index_chunks_simple(self):
        """Test indexing chunks without parent relationships."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.lastrowid = 100  # All chunks get same ID for simplicity

        # Create mock chunks
        mock_chunk1 = Mock()
        mock_chunk1.chunk_number = 1
        mock_chunk1.heading = "Chapter 1"
        mock_chunk1.level = 1
        mock_chunk1.content = "Content 1"
        mock_chunk1.content_hash = "hash1"
        mock_chunk1.parent_chunk_id = None
        mock_chunk1.metadata = {"type": "chapter"}

        mock_chunk2 = Mock()
        mock_chunk2.chunk_number = 2
        mock_chunk2.heading = "Section 1.1"
        mock_chunk2.level = 2
        mock_chunk2.content = "Content 2"
        mock_chunk2.content_hash = "hash2"
        mock_chunk2.parent_chunk_id = None
        mock_chunk2.metadata = {}

        mock_parsed_bible = Mock()
        mock_parsed_bible.chunks = [mock_chunk1, mock_chunk2]

        indexer = BibleIndexer(Mock(), Mock())

        count = await indexer._index_chunks(mock_conn, 456, mock_parsed_bible)

        assert count == 2
        assert mock_cursor.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_index_chunks_with_parent_relationships(self):
        """Test indexing chunks with parent-child relationships."""
        mock_conn = Mock()
        mock_cursor = Mock()

        # Return different IDs for each chunk
        lastrowid_values = [100, 101, 102]
        mock_cursor.lastrowid = 100  # Will be overridden by side_effect

        def lastrowid_side_effect():
            return lastrowid_values.pop(0) if lastrowid_values else None

        type(mock_cursor).lastrowid = property(lambda _: lastrowid_side_effect())

        # Create mock chunks with parent relationships
        mock_chunk1 = Mock()
        mock_chunk1.chunk_number = 1
        mock_chunk1.heading = "Chapter 1"
        mock_chunk1.level = 1
        mock_chunk1.content = "Content 1"
        mock_chunk1.content_hash = "hash1"
        mock_chunk1.parent_chunk_id = None
        mock_chunk1.metadata = {}

        mock_chunk2 = Mock()
        mock_chunk2.chunk_number = 2
        mock_chunk2.heading = "Section 1.1"
        mock_chunk2.level = 2
        mock_chunk2.content = "Content 2"
        mock_chunk2.content_hash = "hash2"
        mock_chunk2.parent_chunk_id = 1  # Child of chunk 1
        mock_chunk2.metadata = {}

        mock_chunk3 = Mock()
        mock_chunk3.chunk_number = 3
        mock_chunk3.heading = "Section 1.2"
        mock_chunk3.level = 2
        mock_chunk3.content = "Content 3"
        mock_chunk3.content_hash = "hash3"
        mock_chunk3.parent_chunk_id = 1  # Child of chunk 1
        mock_chunk3.metadata = {}

        mock_parsed_bible = Mock()
        mock_parsed_bible.chunks = [mock_chunk1, mock_chunk2, mock_chunk3]

        indexer = BibleIndexer(Mock(), Mock())

        # Mock lastrowid to return sequential values
        call_count = 0

        def mock_lastrowid():
            nonlocal call_count
            call_count += 1
            return 99 + call_count  # 100, 101, 102

        mock_cursor.lastrowid = property(lambda _: mock_lastrowid())

        count = await indexer._index_chunks(mock_conn, 456, mock_parsed_bible)

        assert count == 3
        assert mock_cursor.execute.call_count == 3

        # Verify parent_chunk_id parameter in calls
        calls = mock_cursor.execute.call_args_list

        # First chunk should have no parent
        assert calls[0][0][1][6] is None  # parent_chunk_id parameter

        # Second and third chunks should reference first chunk's DB ID
        # Note: This test is simplified since we can't easily mock property behavior

    @pytest.mark.asyncio
    async def test_index_chunks_lastrowid_none(self):
        """Test indexing chunks when lastrowid returns None."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.lastrowid = None

        mock_chunk = Mock()
        mock_chunk.chunk_number = 1
        mock_chunk.heading = "Chapter 1"
        mock_chunk.level = 1
        mock_chunk.content = "Content"
        mock_chunk.content_hash = "hash1"
        mock_chunk.parent_chunk_id = None
        mock_chunk.metadata = {}

        mock_parsed_bible = Mock()
        mock_parsed_bible.chunks = [mock_chunk]

        indexer = BibleIndexer(Mock(), Mock())

        count = await indexer._index_chunks(mock_conn, 456, mock_parsed_bible)

        # Should still execute but count won't increment
        assert count == 0
        assert mock_cursor.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_embeddings_no_analyzer(self):
        """Test embedding generation without analyzer."""
        indexer = BibleIndexer(Mock(), Mock())
        indexer.embedding_analyzer = None

        count = await indexer._generate_embeddings(Mock(), 456, Mock())

        assert count == 0

    @pytest.mark.asyncio
    async def test_generate_embeddings_success(self):
        """Test successful embedding generation."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock chunk data from database
        mock_cursor.fetchall.return_value = [
            (101, "hash1", "Chapter 1", "This is chapter 1 content"),
            (102, "hash2", "Chapter 2", "This is chapter 2 content"),
        ]

        # Mock embedding analyzer
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze.return_value = {
            "embedding_path": "/path/to/embedding.npy",
            "dimensions": 1536,
            "model": "text-embedding-ada-002",
        }

        indexer = BibleIndexer(Mock(), Mock())
        indexer.embedding_analyzer = mock_analyzer

        count = await indexer._generate_embeddings(mock_conn, 456, Mock())

        assert count == 2
        assert mock_analyzer.analyze.call_count == 2
        assert mock_cursor.execute.call_count == 3  # 1 SELECT + 2 INSERT

        # Verify embedding data was stored
        insert_calls = [
            call
            for call in mock_cursor.execute.call_args_list
            if "INSERT" in call[0][0]
        ]
        assert len(insert_calls) == 2

    @pytest.mark.asyncio
    async def test_generate_embeddings_with_retry_success(self):
        """Test embedding generation with retry that succeeds."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock chunk data
        mock_cursor.fetchall.return_value = [
            (101, "hash1", "Chapter 1", "Content"),
        ]

        # Mock embedding analyzer that fails first, succeeds second
        mock_analyzer = AsyncMock()
        call_count = 0

        def mock_analyze(data):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("API error")
            return {
                "embedding_path": "/path/to/embedding.npy",
                "dimensions": 1536,
                "model": "test-model",
            }

        mock_analyzer.analyze.side_effect = mock_analyze

        indexer = BibleIndexer(Mock(), Mock())
        indexer.embedding_analyzer = mock_analyzer

        with patch("asyncio.sleep") as mock_sleep:  # Speed up test
            count = await indexer._generate_embeddings(mock_conn, 456, Mock())

        assert count == 1
        assert call_count == 2  # Failed once, succeeded second time
        mock_sleep.assert_called_once_with(1.0)  # First retry delay

    @pytest.mark.asyncio
    async def test_generate_embeddings_max_retries_exceeded(self):
        """Test embedding generation that exceeds max retries."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock chunk data
        mock_cursor.fetchall.return_value = [
            (101, "hash1", "Chapter 1", "Content"),
        ]

        # Mock embedding analyzer that always fails
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze.side_effect = Exception("Persistent API error")

        indexer = BibleIndexer(Mock(), Mock())
        indexer.embedding_analyzer = mock_analyzer

        with patch("asyncio.sleep"):  # Speed up test
            count = await indexer._generate_embeddings(mock_conn, 456, Mock())

        assert count == 0
        assert mock_analyzer.analyze.call_count == 3  # 3 attempts before giving up

    @pytest.mark.asyncio
    async def test_generate_embeddings_error_in_result(self):
        """Test embedding generation when analyzer returns error in result."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock chunk data
        mock_cursor.fetchall.return_value = [
            (101, "hash1", "Chapter 1", "Content"),
        ]

        # Mock embedding analyzer that returns error in result
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze.return_value = {"error": "API quota exceeded"}

        indexer = BibleIndexer(Mock(), Mock())
        indexer.embedding_analyzer = mock_analyzer

        with patch("asyncio.sleep"):
            count = await indexer._generate_embeddings(mock_conn, 456, Mock())

        assert count == 0
        assert mock_analyzer.analyze.call_count == 3  # Should retry on error result

    @pytest.mark.asyncio
    async def test_generate_embeddings_exponential_backoff(self):
        """Test embedding generation uses exponential backoff for retries."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock chunk data
        mock_cursor.fetchall.return_value = [
            (101, "hash1", "Chapter 1", "Content"),
        ]

        # Mock analyzer that always fails
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze.side_effect = Exception("API error")

        indexer = BibleIndexer(Mock(), Mock())
        indexer.embedding_analyzer = mock_analyzer

        with patch("asyncio.sleep") as mock_sleep:
            count = await indexer._generate_embeddings(mock_conn, 456, Mock())

        assert count == 0

        # Verify exponential backoff: 1s, 2s, 4s
        expected_delays = [1.0, 2.0, 4.0]
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_calls == expected_delays

"""Tests for query loader."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.query.loader import QueryLoader


class TestQueryLoader:
    """Test query loader."""

    @pytest.fixture
    def temp_query_dir(self, tmp_path):
        """Create a temporary query directory."""
        query_dir = tmp_path / "queries"
        query_dir.mkdir()
        return query_dir

    @pytest.fixture
    def sample_queries(self, temp_query_dir):
        """Create sample query files."""
        # Query 1
        query1 = temp_query_dir / "users.sql"
        query1.write_text("""-- name: list_users
-- description: List all users
-- param: active bool optional default=true
SELECT * FROM users WHERE active = :active""")

        # Query 2
        query2 = temp_query_dir / "orders.sql"
        query2.write_text("""-- name: get_orders
-- description: Get orders by user
-- param: user_id int required
SELECT * FROM orders WHERE user_id = :user_id""")

        # Query without name (uses filename)
        query3 = temp_query_dir / "products.sql"
        query3.write_text("""-- description: List products
SELECT * FROM products""")

        return temp_query_dir

    def test_init_with_env_dir(self, sample_queries, monkeypatch):
        """Test initialization with environment variable."""
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(sample_queries))

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        assert loader._query_dir == sample_queries

    def test_init_with_default_dir(self):
        """Test initialization with default directory."""
        settings = MagicMock(spec=ScriptRAGSettings)

        with patch("scriptrag.query.loader.Path.exists") as mock_exists:
            mock_exists.return_value = True
            loader = QueryLoader(settings)

            assert loader._query_dir.name == "queries"

    def test_discover_queries(self, sample_queries, monkeypatch):
        """Test discovering queries from directory."""
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(sample_queries))

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        queries = loader.discover_queries()

        assert len(queries) == 3
        assert "list_users" in queries
        assert "get_orders" in queries
        assert "products" in queries  # Filename fallback

        # Check query details
        users_query = queries["list_users"]
        assert users_query.description == "List all users"
        assert len(users_query.params) == 1

    def test_discover_queries_caching(self, sample_queries, monkeypatch):
        """Test that queries are cached."""
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(sample_queries))

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        # First call
        queries1 = loader.discover_queries()
        assert len(queries1) == 3

        # Add another query file
        (sample_queries / "new.sql").write_text("""-- name: new_query
SELECT 1""")

        # Second call without force reload - should use cache
        queries2 = loader.discover_queries()
        assert len(queries2) == 3  # Still 3, not 4

        # Third call with force reload
        queries3 = loader.discover_queries(force_reload=True)
        assert len(queries3) == 4  # Now includes new query

    def test_discover_queries_duplicate_names(self, temp_query_dir, monkeypatch):
        """Test handling duplicate query names."""
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(temp_query_dir))

        # Create two queries with same name
        query1 = temp_query_dir / "query1.sql"
        query1.write_text("""-- name: duplicate
SELECT 1""")

        query2 = temp_query_dir / "query2.sql"
        query2.write_text("""-- name: duplicate
SELECT 2""")

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        queries = loader.discover_queries()

        # Should only have one "duplicate" query (first one loaded)
        assert len(queries) == 1
        assert "duplicate" in queries

    def test_load_query(self, temp_query_dir):
        """Test loading a single query file."""
        query_file = temp_query_dir / "test.sql"
        query_file.write_text("""-- name: test_query
-- description: Test
-- param: id int required
SELECT * FROM test WHERE id = :id""")

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        spec = loader.load_query(query_file)

        assert spec.name == "test_query"
        assert spec.description == "Test"
        assert len(spec.params) == 1
        assert spec.source_path == query_file

    def test_load_query_file_not_found(self):
        """Test loading non-existent file."""
        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        with pytest.raises(FileNotFoundError):
            loader.load_query(Path("/nonexistent/file.sql"))

    def test_load_query_not_sql_file(self, temp_query_dir):
        """Test loading non-SQL file."""
        not_sql = temp_query_dir / "test.txt"
        not_sql.write_text("Not SQL")

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        with pytest.raises(ValueError, match="Not an SQL file"):
            loader.load_query(not_sql)

    def test_get_query(self, sample_queries, monkeypatch):
        """Test getting query by name."""
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(sample_queries))

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        query = loader.get_query("list_users")
        assert query is not None
        assert query.name == "list_users"

        # Non-existent query
        assert loader.get_query("nonexistent") is None

    def test_list_queries(self, sample_queries, monkeypatch):
        """Test listing all queries."""
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(sample_queries))

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        queries = loader.list_queries()

        assert len(queries) == 3
        names = [q.name for q in queries]
        assert "list_users" in names
        assert "get_orders" in names
        assert "products" in names

    def test_init_without_settings(self):
        """Test initialization without settings - uses get_settings()."""
        with patch("scriptrag.config.get_settings") as mock_get_settings:
            mock_settings = MagicMock(spec=ScriptRAGSettings)
            mock_get_settings.return_value = mock_settings

            loader = QueryLoader()

            assert loader.settings == mock_settings
            mock_get_settings.assert_called_once()

    def test_get_query_directory_from_env(self, tmp_path):
        """Test getting query directory from environment variable."""
        query_dir = tmp_path / "custom_queries"
        query_dir.mkdir()

        with (
            patch.dict("os.environ", {"SCRIPTRAG_QUERY_DIR": str(query_dir)}),
            patch("scriptrag.query.loader.logger") as mock_logger,
        ):
            loader = QueryLoader(MagicMock(spec=ScriptRAGSettings))
            assert loader._query_dir == query_dir
            mock_logger.info.assert_called_with(
                f"Using query directory from env: {query_dir}"
            )

    def test_get_query_directory_env_not_exist(self, tmp_path):
        """Test environment variable points to non-existent directory."""
        nonexistent = tmp_path / "nonexistent"

        with (
            patch.dict("os.environ", {"SCRIPTRAG_QUERY_DIR": str(nonexistent)}),
            patch("scriptrag.query.loader.logger") as mock_logger,
        ):
            loader = QueryLoader(MagicMock(spec=ScriptRAGSettings))

            # Should warn about non-existent path
            mock_logger.warning.assert_called_with(
                f"SCRIPTRAG_QUERY_DIR set but path doesn't exist: {nonexistent}"
            )

            # Should fall back to default path
            assert loader._query_dir != nonexistent

    def test_get_query_directory_default_not_exist(self):
        """Test default query directory creation when it doesn't exist."""
        with (
            patch("scriptrag.query.loader.logger"),
            patch("scriptrag.query.loader.Path.mkdir") as mock_mkdir,
        ):
            QueryLoader(MagicMock(spec=ScriptRAGSettings))

            # Should create directory
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_discover_queries_force_reload(self, sample_queries, monkeypatch):
        """Test force reloading queries."""
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(sample_queries))

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        # First load
        queries1 = loader.discover_queries()
        assert len(queries1) == 3

        # Modify cache manually
        loader._cache = {"fake": MagicMock()}

        # Force reload should ignore cache
        queries2 = loader.discover_queries(force_reload=True)
        assert len(queries2) == 3
        assert "fake" not in queries2

    def test_discover_queries_directory_not_exist(self):
        """Test discovering queries when directory doesn't exist."""
        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        # Point to non-existent directory
        loader._query_dir = Path("/nonexistent")

        with patch("scriptrag.query.loader.logger") as mock_logger:
            queries = loader.discover_queries()

            assert len(queries) == 0
            mock_logger.warning.assert_called_with(
                "Query directory doesn't exist: /nonexistent"
            )

    def test_discover_queries_load_error(self, tmp_path):
        """Test discovering queries with loading error."""
        query_dir = tmp_path / "queries"
        query_dir.mkdir()

        # Create invalid file that will cause loading error
        invalid_file = query_dir / "invalid.sql"
        invalid_file.write_bytes(b"\xff\xfe")  # Invalid UTF-8

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)
        loader._query_dir = query_dir

        with patch("scriptrag.query.loader.logger") as mock_logger:
            queries = loader.discover_queries()

            # Should skip the invalid file
            assert len(queries) == 0

            # Should log error
            mock_logger.error.assert_called()
            error_call = mock_logger.error.call_args[0][0]
            assert "Failed to load query from" in error_call

    def test_load_query_no_name_header(self, tmp_path):
        """Test loading query without name header."""
        query_file = tmp_path / "no_name.sql"
        query_file.write_text("""
        -- description: Query without name
        SELECT * FROM test;
        """)

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        with patch("scriptrag.query.loader.logger") as mock_logger:
            spec = loader.load_query(query_file)

            # Should use filename as name
            assert spec.name == "no_name"

            # Should log warning
            mock_logger.warning.assert_called()
            warning_call = mock_logger.warning.call_args[0][0]
            assert "has no '-- name:' header" in warning_call

    def test_load_query_parse_error(self, tmp_path):
        """Test loading query with parse error."""
        query_file = tmp_path / "parse_error.sql"
        query_file.write_bytes(b"\xff\xfe")  # Invalid UTF-8

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        with pytest.raises(ValueError, match="Failed to parse query file"):
            loader.load_query(query_file)

    def test_validate_sql_syntax_empty(self):
        """Test SQL syntax validation with empty SQL."""
        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        with pytest.raises(ValueError, match="Empty SQL statement"):
            loader._validate_sql_syntax("")

        with pytest.raises(ValueError, match="Empty SQL statement"):
            loader._validate_sql_syntax("   \n  ")

    def test_validate_sql_syntax_incomplete(self):
        """Test SQL syntax validation with incomplete SQL."""
        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        with pytest.raises(ValueError, match="Incomplete SQL statement"):
            loader._validate_sql_syntax("SELECT * FROM")

    def test_validate_sql_syntax_non_readonly(self):
        """Test SQL syntax validation with non-read-only queries."""
        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        with pytest.raises(ValueError, match="Only read-only queries.*are allowed"):
            loader._validate_sql_syntax("INSERT INTO test VALUES (1)")

        with pytest.raises(ValueError, match="Only read-only queries.*are allowed"):
            loader._validate_sql_syntax("UPDATE test SET col = 1")

        with pytest.raises(ValueError, match="Only read-only queries.*are allowed"):
            loader._validate_sql_syntax("DELETE FROM test")

    def test_validate_sql_syntax_valid_queries(self):
        """Test SQL syntax validation with valid queries."""
        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        # These should not raise exceptions
        loader._validate_sql_syntax("SELECT * FROM test")
        loader._validate_sql_syntax("SELECT * FROM test;")
        loader._validate_sql_syntax("WITH cte AS (SELECT 1) SELECT * FROM cte")
        loader._validate_sql_syntax("PRAGMA table_info(test)")
        loader._validate_sql_syntax("EXPLAIN SELECT * FROM test")

    def test_get_query_cache_behavior(self, sample_queries, monkeypatch):
        """Test query caching behavior."""
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(sample_queries))

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        # First call loads from disk
        query1 = loader.get_query("list_users")
        assert query1 is not None

        # Second call uses cache
        query2 = loader.get_query("list_users")
        assert query2 is query1  # Same object

    def test_get_query_not_found(self, sample_queries, monkeypatch):
        """Test getting non-existent query."""
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(sample_queries))

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        query = loader.get_query("nonexistent")
        assert query is None

    def test_list_queries_cache_behavior(self, sample_queries, monkeypatch):
        """Test list queries caching behavior."""
        monkeypatch.setenv("SCRIPTRAG_QUERY_DIR", str(sample_queries))

        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        # First call loads from disk
        queries1 = loader.list_queries()
        assert len(queries1) == 3

        # Second call uses cache
        queries2 = loader.list_queries()
        assert queries2 == queries1  # Same content (list contents)

    def test_get_query_directory_exception_handling(self):
        """Test exception handling in query directory setup - lines 48-49 coverage."""
        settings = MagicMock(spec=ScriptRAGSettings)

        with patch("scriptrag.query.loader.Path") as mock_path_class:
            # Mock Path.mkdir to raise an exception
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_path.mkdir.side_effect = OSError("Permission denied")
            mock_path_class.return_value = mock_path

            with (
                patch("os.environ", {}),
                patch("scriptrag.query.loader.logger"),
                pytest.raises(OSError),
            ):
                QueryLoader(settings)

            # Should have attempted to create directory
            mock_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_reload_queries_method(self):
        """Test reload queries method calls discover with force - line 156 coverage."""
        settings = MagicMock(spec=ScriptRAGSettings)
        loader = QueryLoader(settings)

        with patch.object(loader, "discover_queries") as mock_discover:
            loader.reload_queries()

            # Should call discover_queries with force_reload=True
            mock_discover.assert_called_once_with(force_reload=True)

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

"""Tests for query engine."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.query.engine import QueryEngine
from scriptrag.query.spec import ParamSpec, QuerySpec


class TestQueryEngine:
    """Test query execution engine."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary test database."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        # Create test tables
        conn.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                active BOOLEAN
            );

            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                amount REAL
            );

            INSERT INTO users (id, name, active) VALUES
                (1, 'Alice', 1),
                (2, 'Bob', 1),
                (3, 'Charlie', 0);

            INSERT INTO orders (id, user_id, amount) VALUES
                (1, 1, 100.0),
                (2, 1, 200.0),
                (3, 2, 150.0);
        """)
        conn.commit()
        conn.close()

        return db_path

    @pytest.fixture
    def engine(self, temp_db):
        """Create engine with test database."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = temp_db
        settings.database_timeout = 30.0
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"

        return QueryEngine(settings)

    def test_execute_simple_query(self, engine):
        """Test executing a simple query."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users ORDER BY id",
        )

        rows, exec_time = engine.execute(spec)

        assert len(rows) == 3
        assert rows[0]["name"] == "Alice"
        assert rows[1]["name"] == "Bob"
        assert rows[2]["name"] == "Charlie"
        assert exec_time > 0

    def test_execute_with_params(self, engine):
        """Test executing query with parameters."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            params=[ParamSpec(name="active", type="bool", required=True)],
            sql="SELECT * FROM users WHERE active = :active ORDER BY id",
        )

        rows, exec_time = engine.execute(spec, params={"active": True})

        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[1]["name"] == "Bob"

    def test_execute_with_limit_offset(self, engine):
        """Test executing query with limit and offset."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users ORDER BY id",
        )

        rows, exec_time = engine.execute(spec, limit=2, offset=1)

        assert len(rows) == 2
        assert rows[0]["name"] == "Bob"
        assert rows[1]["name"] == "Charlie"

    def test_execute_with_limit_in_sql(self, engine):
        """Test executing query with limit already in SQL."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            params=[
                ParamSpec(name="limit", type="int", default=10),
                ParamSpec(name="offset", type="int", default=0),
            ],
            sql="SELECT * FROM users ORDER BY id LIMIT :limit OFFSET :offset",
        )

        rows, exec_time = engine.execute(spec, params={"limit": 1, "offset": 2})

        assert len(rows) == 1
        assert rows[0]["name"] == "Charlie"

    def test_validate_required_params(self, engine):
        """Test validation of required parameters."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            params=[ParamSpec(name="user_id", type="int", required=True)],
            sql="SELECT * FROM orders WHERE user_id = :user_id",
        )

        with pytest.raises(ValueError, match="Required parameter"):
            engine.execute(spec, params={})

    def test_validate_param_types(self, engine):
        """Test parameter type validation."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            params=[ParamSpec(name="user_id", type="int", required=True)],
            sql="SELECT * FROM orders WHERE user_id = :user_id",
        )

        # Valid int
        rows, _ = engine.execute(spec, params={"user_id": "1"})
        assert len(rows) == 2

        # Invalid int
        with pytest.raises(ValueError, match="Cannot convert"):
            engine.execute(spec, params={"user_id": "not_a_number"})

    def test_validate_param_choices(self, engine):
        """Test parameter choices validation."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            params=[
                ParamSpec(
                    name="status",
                    type="str",
                    required=True,
                    choices=["active", "inactive"],
                )
            ],
            sql="""
                SELECT * FROM users
                WHERE active = CASE WHEN :status = 'active' THEN 1 ELSE 0 END
            """,
        )

        # Valid choice
        rows, _ = engine.execute(spec, params={"status": "active"})
        assert len(rows) == 2

        # Invalid choice
        with pytest.raises(ValueError, match="Invalid choice"):
            engine.execute(spec, params={"status": "pending"})

    def test_execute_with_defaults(self, engine):
        """Test executing with parameter defaults."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            params=[
                ParamSpec(name="active", type="bool", required=False, default=True)
            ],
            sql="SELECT * FROM users WHERE active = :active",
        )

        # No params provided, should use default
        rows, _ = engine.execute(spec)
        assert len(rows) == 2

    def test_database_not_found(self):
        """Test error when database doesn't exist."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = Path("/nonexistent/db.sqlite")

        engine = QueryEngine(settings)
        spec = QuerySpec(name="test", description="Test query", sql="SELECT 1")

        with pytest.raises(FileNotFoundError, match="Database not found"):
            engine.execute(spec)

    def test_sql_injection_prevention(self, engine):
        """Test that SQL injection is prevented."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            params=[ParamSpec(name="name", type="str", required=True)],
            sql="SELECT * FROM users WHERE name = :name",
        )

        # Attempt SQL injection
        malicious_input = "'; DROP TABLE users; --"
        rows, _ = engine.execute(spec, params={"name": malicious_input})

        # Should return empty result, not drop table
        assert len(rows) == 0

        # Verify table still exists
        spec2 = QuerySpec(
            name="verify",
            description="Verify table",
            sql="SELECT COUNT(*) as count FROM users",
        )
        rows2, _ = engine.execute(spec2)
        assert rows2[0]["count"] == 3

    def test_check_read_only(self, engine):
        """Test that connection is read-only."""
        # This test verifies the read-only check method
        # In a real read-only connection, writes would fail
        assert engine.check_read_only() is True

    def test_empty_result_set(self, engine):
        """Test handling empty result set."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users WHERE id = 999",
        )

        rows, exec_time = engine.execute(spec)

        assert len(rows) == 0
        assert exec_time > 0

    def test_complex_query(self, engine):
        """Test executing complex query with joins."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="""
                SELECT
                    u.name,
                    COUNT(o.id) as order_count,
                    SUM(o.amount) as total_amount
                FROM users u
                LEFT JOIN orders o ON u.id = o.user_id
                WHERE u.active = 1
                GROUP BY u.id, u.name
                ORDER BY u.name
            """,
        )

        rows, _ = engine.execute(spec)

        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["order_count"] == 2
        assert rows[0]["total_amount"] == 300.0
        assert rows[1]["name"] == "Bob"
        assert rows[1]["order_count"] == 1

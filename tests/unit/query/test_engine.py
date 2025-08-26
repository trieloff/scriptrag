"""Tests for query engine."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scriptrag.config import ScriptRAGSettings
from scriptrag.exceptions import ValidationError
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
        settings.database_journal_mode = "WAL"
        settings.database_synchronous = "NORMAL"
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"
        settings.database_foreign_keys = True
        settings.database_timeout = 30.0

        # Ensure the database file exists before creating engine
        assert temp_db.exists(), f"Test database should exist at {temp_db}"

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
        assert exec_time >= 0  # Windows can report 0.0 for very fast operations

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

        with pytest.raises(ValidationError, match="Required parameter"):
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
        with pytest.raises(ValidationError, match="Cannot convert"):
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
        with pytest.raises(ValidationError, match="Invalid choice"):
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
        settings.database_journal_mode = "WAL"
        settings.database_synchronous = "NORMAL"
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"
        settings.database_foreign_keys = True
        settings.database_timeout = 30.0

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
        assert exec_time >= 0  # Windows can report 0.0 for very fast operations

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

    def test_init_without_settings(self):
        """Test initialization without settings - uses get_settings()."""
        with patch("scriptrag.query.engine.get_settings") as mock_get_settings:
            mock_settings = MagicMock(spec=ScriptRAGSettings)
            mock_settings.database_path = Path("/test/db.sqlite")
            mock_settings.database_journal_mode = "WAL"
            mock_settings.database_synchronous = "NORMAL"
            mock_settings.database_cache_size = -2000
            mock_settings.database_temp_store = "MEMORY"
            mock_settings.database_foreign_keys = True
            mock_settings.database_timeout = 30.0
            mock_get_settings.return_value = mock_settings

            engine = QueryEngine()

            assert engine.settings == mock_settings
            assert engine.db_path == mock_settings.database_path
            # Called at least once (may be called multiple times due to property access)
            assert mock_get_settings.called

    def test_execute_with_limit_no_offset_in_sql(self, engine):
        """Test executing query with limit but no offset in original SQL."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users ORDER BY id",
        )

        rows, exec_time = engine.execute(spec, limit=2)

        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[1]["name"] == "Bob"

    def test_execute_with_offset_no_limit_in_sql(self, engine):
        """Test executing query with offset but no limit in original SQL."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users ORDER BY id",
        )

        rows, exec_time = engine.execute(spec, offset=1)

        assert len(rows) == 2
        assert rows[0]["name"] == "Bob"
        assert rows[1]["name"] == "Charlie"

    def test_execute_modify_limit_with_offset(self, engine):
        """Test modifying query that has LIMIT but adding OFFSET."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            params=[ParamSpec(name="limit", type="int", default=10)],
            sql="SELECT * FROM users ORDER BY id LIMIT :limit",
        )

        rows, exec_time = engine.execute(spec, params={"limit": 2}, offset=1)

        assert len(rows) == 2
        assert rows[0]["name"] == "Bob"
        assert rows[1]["name"] == "Charlie"

    def test_database_operational_error_no_table(self, engine):
        """Test handling of 'no such table' operational error."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM nonexistent_table",
        )

        with pytest.raises(ValueError, match="Table not found in query"):
            engine.execute(spec)

    def test_database_operational_error_no_column(self, engine):
        """Test handling of 'no such column' operational error."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT nonexistent_column FROM users",
        )

        with pytest.raises(ValueError, match="Column not found in query"):
            engine.execute(spec)

    def test_database_operational_error_generic(self, engine):
        """Test handling of generic operational error."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users ORDER BY nonexistent_column",
        )

        with pytest.raises(ValueError, match="Column not found in query"):
            engine.execute(spec)

    def test_database_integrity_error(self, engine):
        """Test handling of integrity error."""
        # Create a scenario that would cause integrity error
        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="INSERT INTO users (id, name, active) VALUES (1, 'Duplicate', 1)",
        )

        # This would normally cause integrity error due to primary key constraint
        # But since we use read-only connection, it will fail differently
        with pytest.raises((ValueError, sqlite3.OperationalError)):
            engine.execute(spec)

    def test_database_programming_error(self, temp_db):
        """Test handling of programming error."""
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = temp_db
        settings.database_journal_mode = "WAL"
        settings.database_synchronous = "NORMAL"
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"
        settings.database_foreign_keys = True
        settings.database_timeout = 30.0

        engine = QueryEngine(settings)

        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users WHERE",  # Invalid SQL syntax
        )

        with pytest.raises(ValueError, match="Database error in query"):
            engine.execute(spec)

    def test_generic_exception_in_execute(self, tmp_path):
        """Test handling of generic exception during query execution."""
        # Create engine without temp_db fixture to avoid real database
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = tmp_path / "test.db"
        settings.database_journal_mode = "WAL"
        settings.database_synchronous = "NORMAL"
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"
        settings.database_foreign_keys = True
        settings.database_timeout = 30.0

        # Create the database file so it exists
        settings.database_path.touch()

        engine = QueryEngine(settings)

        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users",
        )

        # Mock to raise a generic exception during SQL execution
        with patch("scriptrag.query.engine.get_read_only_connection") as mock_conn:
            # Mock context manager
            mock_context = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "__enter__",
                    "__exit__",
                    "execute",
                ]
            )
            mock_conn.return_value.__enter__.return_value = mock_context
            mock_context.execute.side_effect = RuntimeError("Unexpected database error")

            with pytest.raises(ValueError, match="Query execution failed"):
                engine.execute(spec)

    def test_check_read_only_not_readonly_detected_original(self, tmp_path):
        """Test read-only check when connection is NOT read-only."""
        # Create engine without temp_db fixture
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = tmp_path / "test.db"
        settings.database_journal_mode = "WAL"
        settings.database_synchronous = "NORMAL"
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"
        settings.database_foreign_keys = True
        settings.database_timeout = 30.0

        # Create the database file so it exists
        settings.database_path.touch()

        engine = QueryEngine(settings)

        with patch("scriptrag.query.engine.get_read_only_connection") as mock_conn:
            mock_db_conn = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "execute",
                    "fetchall",
                    "fetchone",
                    "commit",
                    "__enter__",
                    "__exit__",
                ]
            )
            # Mock successful write operation (should not happen in read-only)
            mock_db_conn.execute.return_value = None
            mock_db_conn.commit.return_value = None
            mock_conn.return_value.__enter__.return_value = mock_db_conn

            with pytest.raises(
                RuntimeError, match="Database connection is not read-only"
            ):
                engine.check_read_only()

    def test_check_read_only_with_readonly_error(self, engine):
        """Test read-only check when read-only error is raised."""
        with patch("scriptrag.query.engine.get_read_only_connection") as mock_conn:
            mock_db_conn = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "execute",
                    "fetchall",
                    "fetchone",
                    "__enter__",
                    "__exit__",
                ]
            )
            # Mock read-only error
            mock_db_conn.execute.side_effect = sqlite3.OperationalError(
                "database is read-only"
            )
            mock_conn.return_value.__enter__.return_value = mock_db_conn

            result = engine.check_read_only()
            assert result is True

    def test_check_read_only_with_other_error(self, engine):
        """Test read-only check with non-read-only error."""
        with patch("scriptrag.query.engine.get_read_only_connection") as mock_conn:
            mock_db_conn = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "execute",
                    "fetchall",
                    "fetchone",
                    "__enter__",
                    "__exit__",
                ]
            )
            # Mock other error that should be treated as read-only
            mock_db_conn.execute.side_effect = sqlite3.OperationalError(
                "some other error"
            )
            mock_conn.return_value.__enter__.return_value = mock_db_conn

            result = engine.check_read_only()
            assert result is True

    def test_validate_params_extra_params_warning(self, engine):
        """Test validation with extra parameters not in spec."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            params=[ParamSpec(name="user_id", type="int", required=True)],
            sql="SELECT * FROM orders WHERE user_id = :user_id",
        )

        with patch("scriptrag.query.engine.logger") as mock_logger:
            rows, _ = engine.execute(
                spec, params={"user_id": 1, "extra_param": "value"}
            )

            # Should log warning about extra parameter
            mock_logger.warning.assert_called_with(
                "Parameter 'extra_param' not defined in query spec, passing as-is"
            )

            assert len(rows) == 2  # Should still execute successfully

    def test_execute_with_limit_only_no_offset_wrapping(self, engine):
        """Test executing query with limit only (no offset) - line 88 coverage."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users ORDER BY id",
        )

        # Test case where has_limit=False, has_offset=False, limit provided, no offset
        # This should hit line 88: sql = f"SELECT * FROM ({sql}) LIMIT :limit"
        rows, exec_time = engine.execute(spec, limit=2)

        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[1]["name"] == "Bob"

    def test_execute_with_offset_only_no_limit_wrapping(self, engine):
        """Test executing query with offset only (no limit) - line 102 coverage."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users ORDER BY id",
        )

        # Test case where has_limit=False, has_offset=False, offset provided, no limit
        # This should hit line 102: sql = f"SELECT * FROM ({sql}) OFFSET :offset"
        rows, exec_time = engine.execute(spec, offset=1)

        assert len(rows) == 2
        assert rows[0]["name"] == "Bob"
        assert rows[1]["name"] == "Charlie"

    def test_database_integrity_error_handling(self, tmp_path):
        """Test handling of integrity error - lines 140-142 coverage."""
        # Create engine with a connection that can potentially raise IntegrityError
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = tmp_path / "test.db"
        settings.database_journal_mode = "WAL"
        settings.database_synchronous = "NORMAL"
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"
        settings.database_foreign_keys = True
        settings.database_timeout = 30.0

        # Create the database file so it exists
        settings.database_path.touch()

        engine = QueryEngine(settings)

        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users",
        )

        # Mock to raise IntegrityError
        with patch("scriptrag.query.engine.get_read_only_connection") as mock_conn:
            mock_db_conn = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "execute",
                    "fetchall",
                    "fetchone",
                    "__enter__",
                    "__exit__",
                ]
            )
            mock_db_conn.execute.side_effect = sqlite3.IntegrityError(
                "UNIQUE constraint failed"
            )
            mock_conn.return_value.__enter__.return_value = mock_db_conn

            with pytest.raises(ValueError, match="Integrity error in query"):
                engine.execute(spec)

    def test_database_programming_error_handling(self, tmp_path):
        """Test handling of programming error - lines 143-145 coverage."""
        # Create engine
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = tmp_path / "test.db"
        settings.database_journal_mode = "WAL"
        settings.database_synchronous = "NORMAL"
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"
        settings.database_foreign_keys = True
        settings.database_timeout = 30.0

        # Create the database file so it exists
        settings.database_path.touch()

        engine = QueryEngine(settings)

        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users",
        )

        # Mock to raise ProgrammingError
        with patch("scriptrag.query.engine.get_read_only_connection") as mock_conn:
            mock_db_conn = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "execute",
                    "fetchall",
                    "fetchone",
                    "__enter__",
                    "__exit__",
                ]
            )
            mock_db_conn.execute.side_effect = sqlite3.ProgrammingError(
                "SQL syntax error"
            )
            mock_conn.return_value.__enter__.return_value = mock_db_conn

            with pytest.raises(ValueError, match="SQL error in query"):
                engine.execute(spec)

    def test_generic_exception_handling(self, tmp_path):
        """Test handling of generic exception - lines 146-148 coverage."""
        # Create engine
        settings = MagicMock(spec=ScriptRAGSettings)
        settings.database_path = tmp_path / "test.db"
        settings.database_journal_mode = "WAL"
        settings.database_synchronous = "NORMAL"
        settings.database_cache_size = -2000
        settings.database_temp_store = "MEMORY"
        settings.database_foreign_keys = True
        settings.database_timeout = 30.0

        # Create the database file so it exists
        settings.database_path.touch()

        engine = QueryEngine(settings)

        spec = QuerySpec(
            name="test",
            description="Test query",
            sql="SELECT * FROM users",
        )

        # Mock to raise generic Exception
        with patch("scriptrag.query.engine.get_read_only_connection") as mock_conn:
            mock_db_conn = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "execute",
                    "fetchall",
                    "fetchone",
                    "__enter__",
                    "__exit__",
                ]
            )
            mock_db_conn.execute.side_effect = RuntimeError("Unexpected database error")
            mock_conn.return_value.__enter__.return_value = mock_db_conn

            with pytest.raises(ValueError, match="Query execution failed"):
                engine.execute(spec)

    def test_check_read_only_write_succeeds_error(self, engine):
        """Test check_read_only when write operation succeeds."""
        with patch("scriptrag.query.engine.get_read_only_connection") as mock_conn:
            mock_db_conn = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "execute",
                    "fetchall",
                    "fetchone",
                    "commit",
                    "__enter__",
                    "__exit__",
                ]
            )
            # Mock successful write operation (should not happen in read-only)
            mock_db_conn.execute.return_value = None
            mock_db_conn.commit.return_value = None
            mock_conn.return_value.__enter__.return_value = mock_db_conn

            with pytest.raises(
                RuntimeError, match="Database connection is not read-only"
            ):
                engine.check_read_only()

    def test_check_read_only_reraise_runtime_error(self, engine):
        """Test check_read_only re-raises RuntimeError - lines 205-207 coverage."""
        with patch("scriptrag.query.engine.get_read_only_connection") as mock_conn:
            mock_db_conn = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "execute",
                    "fetchall",
                    "fetchone",
                    "__enter__",
                    "__exit__",
                ]
            )
            # Mock the specific RuntimeError that should be re-raised
            mock_db_conn.execute.side_effect = RuntimeError(
                "Database connection is not read-only!"
            )
            mock_conn.return_value.__enter__.return_value = mock_db_conn

            with pytest.raises(
                RuntimeError, match="Database connection is not read-only"
            ):
                engine.check_read_only()

    def test_check_read_only_other_exception_returns_true(self, engine):
        """Test check_read_only with other exceptions returns True."""
        with patch("scriptrag.query.engine.get_read_only_connection") as mock_conn:
            mock_db_conn = MagicMock(
                spec=[
                    "content",
                    "model",
                    "provider",
                    "usage",
                    "execute",
                    "fetchall",
                    "fetchone",
                    "__enter__",
                    "__exit__",
                ]
            )
            # Mock other exception that should result in True
            mock_db_conn.execute.side_effect = ValueError("Some other error")
            mock_conn.return_value.__enter__.return_value = mock_db_conn

            result = engine.check_read_only()
            assert result is True

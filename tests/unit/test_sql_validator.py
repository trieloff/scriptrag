"""Unit tests for SQL validator."""

import pytest

from scriptrag.api.sql_validator import SQLValidationError, SQLValidator


class TestSQLValidator:
    """Test SQLValidator class."""

    @pytest.fixture
    def validator(self):
        """Create SQL validator instance."""
        return SQLValidator()

    def test_validate_file_size_within_limit(self, validator, tmp_path):
        """Test file size validation passes for small files."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("CREATE TABLE test (id INTEGER);")

        # Should not raise
        validator.validate_file_size(sql_file)

    def test_validate_file_size_exceeds_limit(self, validator, tmp_path):
        """Test file size validation fails for large files."""
        sql_file = tmp_path / "test.sql"
        # Write > 5MB of data
        large_content = "-- " + "x" * (5 * 1024 * 1024 + 1)
        sql_file.write_text(large_content)

        with pytest.raises(SQLValidationError) as exc_info:
            validator.validate_file_size(sql_file)
        assert "exceeds maximum allowed size" in str(exc_info.value)

    def test_validate_sql_content_valid_ddl(self, validator):
        """Test validation passes for valid DDL statements."""
        valid_sql = (
            "-- Create tables\n"
            "CREATE TABLE users (\n"
            "    id INTEGER PRIMARY KEY,\n"
            "    name TEXT NOT NULL\n"
            ");\n"
            "\n"
            "CREATE INDEX idx_users_name ON users (name);\n"
            "\n"
            "CREATE TRIGGER update_timestamp\n"
            "AFTER UPDATE ON users\n"
            "BEGIN\n"
            "    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = new.id;\n"
            "END;\n"
            "\n"
            "PRAGMA foreign_keys = ON;"
        )

        # Should not raise
        validator.validate_sql_content(valid_sql, "test.sql")

    def test_validate_sql_content_with_schema_version_insert(self, validator):
        """Test validation allows INSERT INTO schema_version."""
        sql_with_insert = (
            "CREATE TABLE schema_version (\n"
            "    version INTEGER PRIMARY KEY,\n"
            "    description TEXT\n"
            ");\n"
            "\n"
            "INSERT INTO schema_version (version, description)\n"
            "VALUES (1, 'Initial schema');"
        )

        # Should not raise
        validator.validate_sql_content(sql_with_insert, "test.sql")

    def test_validate_sql_content_disallowed_delete(self, validator):
        """Test validation fails for DELETE statements."""
        sql_with_delete = """
        CREATE TABLE users (id INTEGER);
        DELETE FROM users WHERE id = 1;
        """

        with pytest.raises(SQLValidationError) as exc_info:
            validator.validate_sql_content(sql_with_delete, "test.sql")
        assert "Disallowed SQL pattern" in str(exc_info.value)

    def test_validate_sql_content_disallowed_update(self, validator):
        """Test validation fails for UPDATE statements."""
        sql_with_update = """
        CREATE TABLE users (name TEXT);
        UPDATE users SET name = 'test';
        """

        with pytest.raises(SQLValidationError) as exc_info:
            validator.validate_sql_content(sql_with_update, "test.sql")
        assert "Disallowed SQL pattern" in str(exc_info.value)

    def test_validate_sql_content_disallowed_drop_database(self, validator):
        """Test validation fails for DROP DATABASE."""
        sql_with_drop_db = "DROP DATABASE test;"

        with pytest.raises(SQLValidationError) as exc_info:
            validator.validate_sql_content(sql_with_drop_db, "test.sql")
        assert "Disallowed SQL pattern" in str(exc_info.value)

    def test_validate_sql_content_disallowed_attach(self, validator):
        """Test validation fails for ATTACH DATABASE."""
        sql_with_attach = "ATTACH DATABASE 'other.db' AS other;"

        with pytest.raises(SQLValidationError) as exc_info:
            validator.validate_sql_content(sql_with_attach, "test.sql")
        assert "Disallowed SQL pattern" in str(exc_info.value)

    def test_validate_sql_content_disallowed_load_extension(self, validator):
        """Test validation fails for LOAD EXTENSION."""
        sql_with_load = "SELECT load_extension('malicious.so');"

        with pytest.raises(SQLValidationError) as exc_info:
            validator.validate_sql_content(sql_with_load, "test.sql")
        # SELECT statements are not recognized DDL, which is what we want
        assert "not a recognized DDL statement" in str(exc_info.value)

    def test_validate_sql_content_unrecognized_statement(self, validator):
        """Test validation fails for unrecognized statements."""
        sql_with_select = """
        CREATE TABLE users (id INTEGER);
        SELECT * FROM users;
        """

        with pytest.raises(SQLValidationError) as exc_info:
            validator.validate_sql_content(sql_with_select, "test.sql")
        assert "not a recognized DDL statement" in str(exc_info.value)

    def test_validate_sql_content_general_insert_not_allowed(self, validator):
        """Test validation fails for INSERT into other tables."""
        sql_with_insert = """
        CREATE TABLE users (id INTEGER, name TEXT);
        INSERT INTO users (id, name) VALUES (1, 'test');
        """

        with pytest.raises(SQLValidationError) as exc_info:
            validator.validate_sql_content(sql_with_insert, "test.sql")
        assert "not a recognized DDL statement" in str(exc_info.value)

    def test_validate_database_path_valid(self, validator, tmp_path):
        """Test database path validation passes for valid paths."""
        valid_paths = [
            tmp_path / "test.db",
            tmp_path / "test.sqlite",
            tmp_path / "test.sqlite3",
            tmp_path / "nested" / "path" / "test.db",
        ]

        for path in valid_paths:
            # Should not raise
            validator.validate_database_path(path)

    def test_validate_database_path_invalid_extension(self, validator, tmp_path):
        """Test database path validation fails for invalid extensions."""
        invalid_path = tmp_path / "test.txt"

        with pytest.raises(SQLValidationError) as exc_info:
            validator.validate_database_path(invalid_path)
        assert "must have one of these extensions" in str(exc_info.value)

    def test_validate_database_path_traversal(self, validator, tmp_path):
        """Test database path validation fails for path traversal."""
        traversal_path = tmp_path / ".." / "etc" / "passwd"

        with pytest.raises(SQLValidationError) as exc_info:
            validator.validate_database_path(traversal_path)
        assert "path traversal attempt" in str(exc_info.value)

    def test_split_sql_statements(self, validator):
        """Test SQL statement splitting handles multi-line statements."""
        sql_content = (
            "CREATE TABLE users (\n"
            "    id INTEGER PRIMARY KEY,\n"
            "    name TEXT\n"
            ");\n"
            "\n"
            "CREATE INDEX idx_name ON users (name);\n"
            "\n"
            "INSERT INTO schema_version (version, description)\n"
            "VALUES (1, 'Version with; semicolon');"
        )

        statements = validator._split_sql_statements(sql_content)
        assert len(statements) == 3
        assert "CREATE TABLE users" in statements[0]
        assert "CREATE INDEX idx_name" in statements[1]
        assert "INSERT INTO schema_version" in statements[2]
        assert "semicolon');" in statements[2]  # Semicolon in string preserved

    def test_case_insensitive_validation(self, validator):
        """Test validation is case-insensitive."""
        mixed_case_sql = """
        create table Users (ID integer);
        CREATE INDEX idx ON Users (ID);
        pragma FOREIGN_KEYS = on;
        """

        # Should not raise
        validator.validate_sql_content(mixed_case_sql, "test.sql")

    def test_empty_statements_allowed(self, validator):
        """Test empty statements and comments are allowed."""
        sql_with_empties = (
            "-- Comment line\n"
            "\n"
            "CREATE TABLE test (id INTEGER);\n"
            "\n"
            "-- Another comment\n"
            ";\n"
            "\n"
        )

        # Should not raise
        validator.validate_sql_content(sql_with_empties, "test.sql")

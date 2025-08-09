"""Tests for query spec parser."""

import pytest

from scriptrag.query.spec import HeaderParser, ParamSpec, QuerySpec


class TestHeaderParser:
    """Test SQL header parsing."""

    def test_parse_basic_query(self):
        """Test parsing a basic query with name and description."""
        sql = """-- name: test_query
-- description: A test query
SELECT * FROM users"""

        spec = HeaderParser.parse(sql)

        assert spec.name == "test_query"
        assert spec.description == "A test query"
        assert spec.sql == "SELECT * FROM users"
        assert len(spec.params) == 0

    def test_parse_query_with_params(self):
        """Test parsing query with parameters."""
        sql = """-- name: user_query
-- description: Get user by ID
-- param: user_id int required help="User ID"
-- param: active bool optional default=true help="Filter active users"
SELECT * FROM users WHERE id = :user_id"""

        spec = HeaderParser.parse(sql)

        assert spec.name == "user_query"
        assert len(spec.params) == 2

        # Check first param
        param1 = spec.params[0]
        assert param1.name == "user_id"
        assert param1.type == "int"
        assert param1.required is True
        assert param1.help == "User ID"

        # Check second param
        param2 = spec.params[1]
        assert param2.name == "active"
        assert param2.type == "bool"
        assert param2.required is False
        assert param2.default is True

    def test_parse_param_with_choices(self):
        """Test parsing parameter with choices."""
        sql = """-- name: filter_query
-- param: status str required choices=pending|approved|rejected help="Status filter"
SELECT * FROM items"""

        spec = HeaderParser.parse(sql)

        assert len(spec.params) == 1
        param = spec.params[0]
        assert param.choices == ["pending", "approved", "rejected"]

    def test_parse_all_param_types(self):
        """Test parsing all parameter types."""
        sql = """-- name: type_test
-- param: str_param str required
-- param: int_param int optional default=10
-- param: float_param float optional default=3.14
-- param: bool_param bool optional default=false
SELECT 1"""

        spec = HeaderParser.parse(sql)

        assert len(spec.params) == 4
        assert spec.params[0].type == "str"
        assert spec.params[1].type == "int"
        assert spec.params[1].default == 10
        assert spec.params[2].type == "float"
        assert spec.params[2].default == 3.14
        assert spec.params[3].type == "bool"
        assert spec.params[3].default is False

    def test_parse_without_name(self):
        """Test parsing query without name (uses filename fallback)."""
        sql = """-- description: No name query
SELECT * FROM users"""

        from pathlib import Path

        spec = HeaderParser.parse(sql, source_path=Path("my_query.sql"))

        assert spec.name == "my_query"
        assert spec.description == "No name query"

    def test_parse_multiline_sql(self):
        """Test parsing multiline SQL."""
        sql = """-- name: complex_query
-- description: Complex query

SELECT
    u.id,
    u.name,
    COUNT(o.id) as order_count
FROM
    users u
    LEFT JOIN orders o ON u.id = o.user_id
GROUP BY
    u.id, u.name
ORDER BY
    order_count DESC"""

        spec = HeaderParser.parse(sql)

        assert spec.name == "complex_query"
        assert "SELECT" in spec.sql
        assert "FROM" in spec.sql
        assert "GROUP BY" in spec.sql


class TestParamSpec:
    """Test parameter specification."""

    def test_cast_str(self):
        """Test casting to string."""
        param = ParamSpec(name="test", type="str", required=True)

        assert param.cast_value("hello") == "hello"
        assert param.cast_value(123) == "123"
        assert param.cast_value(True) == "True"

    def test_cast_int(self):
        """Test casting to integer."""
        param = ParamSpec(name="test", type="int", required=True)

        assert param.cast_value(42) == 42
        assert param.cast_value("42") == 42

        with pytest.raises(ValueError, match="Cannot convert"):
            param.cast_value("not_a_number")

    def test_cast_float(self):
        """Test casting to float."""
        param = ParamSpec(name="test", type="float", required=True)

        assert param.cast_value(3.14) == 3.14
        assert param.cast_value("3.14") == 3.14
        assert param.cast_value(3) == 3.0

        with pytest.raises(ValueError, match="Cannot convert"):
            param.cast_value("not_a_float")

    def test_cast_bool(self):
        """Test casting to boolean."""
        param = ParamSpec(name="test", type="bool", required=True)

        # Test various true values
        assert param.cast_value(True) is True
        assert param.cast_value("true") is True
        assert param.cast_value("True") is True
        assert param.cast_value("1") is True
        assert param.cast_value("yes") is True
        assert param.cast_value("y") is True
        assert param.cast_value("on") is True

        # Test various false values
        assert param.cast_value(False) is False
        assert param.cast_value("false") is False
        assert param.cast_value("False") is False
        assert param.cast_value("0") is False
        assert param.cast_value("no") is False
        assert param.cast_value("n") is False
        assert param.cast_value("off") is False

        with pytest.raises(ValueError, match="Cannot convert"):
            param.cast_value("maybe")

    def test_required_param(self):
        """Test required parameter validation."""
        param = ParamSpec(name="test", type="str", required=True)

        with pytest.raises(ValueError, match="Required parameter"):
            param.cast_value(None)

    def test_optional_param_with_default(self):
        """Test optional parameter with default."""
        param = ParamSpec(name="test", type="int", required=False, default=42)

        assert param.cast_value(None) == 42
        assert param.cast_value(100) == 100

    def test_param_with_choices(self):
        """Test parameter with choices validation."""
        param = ParamSpec(
            name="test", type="str", required=True, choices=["a", "b", "c"]
        )

        assert param.cast_value("a") == "a"
        assert param.cast_value("b") == "b"

        with pytest.raises(ValueError, match="Invalid choice"):
            param.cast_value("d")


class TestQuerySpec:
    """Test query specification."""

    def test_get_param(self):
        """Test getting parameter by name."""
        spec = QuerySpec(
            name="test",
            description="Test query",
            params=[
                ParamSpec(name="param1", type="str"),
                ParamSpec(name="param2", type="int"),
            ],
        )

        assert spec.get_param("param1").type == "str"
        assert spec.get_param("param2").type == "int"
        assert spec.get_param("nonexistent") is None

    def test_has_limit_offset(self):
        """Test checking for limit/offset parameters."""
        # Query with limit/offset params
        spec1 = QuerySpec(
            name="test1",
            description="Test",
            params=[
                ParamSpec(name="limit", type="int"),
                ParamSpec(name="offset", type="int"),
            ],
            sql="SELECT * FROM users",
        )
        has_limit, has_offset = spec1.has_limit_offset()
        assert has_limit is True
        assert has_offset is True

        # Query with limit/offset in SQL
        spec2 = QuerySpec(
            name="test2",
            description="Test",
            sql="SELECT * FROM users LIMIT :limit OFFSET :offset",
        )
        has_limit, has_offset = spec2.has_limit_offset()
        assert has_limit is True
        assert has_offset is True

        # Query without limit/offset
        spec3 = QuerySpec(name="test3", description="Test", sql="SELECT * FROM users")
        has_limit, has_offset = spec3.has_limit_offset()
        assert has_limit is False
        assert has_offset is False

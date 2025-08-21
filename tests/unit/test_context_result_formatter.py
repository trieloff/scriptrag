"""Unit tests for ContextResultFormatter.format_as_table method."""

from scriptrag.agents.context_query import ContextResultFormatter


class TestContextResultFormatter:
    """Test suite for ContextResultFormatter."""

    def test_format_as_table_empty_rows(self):
        """Test formatting with empty rows list."""
        result = ContextResultFormatter.format_as_table([])
        assert result == "No results found"

    def test_format_as_table_max_rows_zero(self):
        """Test formatting with max_rows=0 (edge case that was causing IndexError)."""
        rows = [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob", "age": 25},
        ]
        result = ContextResultFormatter.format_as_table(rows, max_rows=0)
        assert result == "No results to display (max_rows limit reached)"

    def test_format_as_table_negative_max_rows(self):
        """Test formatting with negative max_rows value."""
        rows = [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob", "age": 25},
        ]
        # Python list slicing with negative values: rows[:-1] gives all but last row
        result = ContextResultFormatter.format_as_table(rows, max_rows=-1)
        # Should show first row only (all but the last one)
        lines = result.strip().split("\n")
        assert "1 | Alice | 30" in result
        assert "2 | Bob | 25" not in result  # Last row should be excluded

    def test_format_as_table_normal_case(self):
        """Test normal table formatting."""
        rows = [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob", "age": 25},
        ]
        result = ContextResultFormatter.format_as_table(rows)

        # Check that it returns a markdown table
        lines = result.strip().split("\n")
        assert len(lines) >= 4  # Header, separator, and at least 2 data rows
        assert "id | name | age" in lines[0]
        assert "---" in lines[1]  # Separator line
        assert "1 | Alice | 30" in lines[2]
        assert "2 | Bob | 25" in lines[3]

    def test_format_as_table_with_truncation(self):
        """Test table formatting with row limit."""
        rows = [
            {"id": i, "name": f"User{i}", "value": i * 10}
            for i in range(1, 11)  # 10 rows
        ]
        result = ContextResultFormatter.format_as_table(rows, max_rows=3)

        lines = result.strip().split("\n")
        # Should have header, separator, 3 data rows, empty line, and truncation message
        assert (
            len(lines) == 7
        )  # Header + separator + 3 rows + empty line + truncation note
        assert "... and 7 more rows" in lines[-1]

    def test_format_as_table_with_none_values(self):
        """Test formatting with None values in data."""
        rows = [
            {"id": 1, "name": "Alice", "age": None},
            {"id": 2, "name": None, "age": 25},
        ]
        result = ContextResultFormatter.format_as_table(rows)

        lines = result.strip().split("\n")
        # None values should be converted to empty strings
        assert "1 | Alice |" in lines[2]  # None at end becomes empty
        assert "2 |  | 25" in lines[3]  # None in middle has space

    def test_format_as_table_with_missing_keys(self):
        """Test formatting when rows have inconsistent keys."""
        rows = [
            {"id": 1, "name": "Alice", "age": 30},
            {"id": 2, "name": "Bob"},  # Missing 'age' key
        ]
        result = ContextResultFormatter.format_as_table(rows)

        lines = result.strip().split("\n")
        # Missing key should be handled gracefully - empty value at the end
        assert "2 | Bob |" in lines[3]

    def test_format_as_table_single_row(self):
        """Test formatting with a single row."""
        rows = [{"id": 1, "name": "Alice", "age": 30}]
        result = ContextResultFormatter.format_as_table(rows)

        lines = result.strip().split("\n")
        assert len(lines) == 3  # Header, separator, 1 data row
        assert "id | name | age" in lines[0]
        assert "1 | Alice | 30" in lines[2]

    def test_format_as_table_max_rows_equals_row_count(self):
        """Test when max_rows equals the number of rows."""
        rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        result = ContextResultFormatter.format_as_table(rows, max_rows=2)

        lines = result.strip().split("\n")
        # Should show all rows without truncation message
        assert len(lines) == 4  # Header, separator, 2 data rows
        assert "... and" not in result  # No truncation message

    def test_format_as_table_max_rows_greater_than_row_count(self):
        """Test when max_rows is greater than available rows."""
        rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        result = ContextResultFormatter.format_as_table(rows, max_rows=10)

        lines = result.strip().split("\n")
        # Should show all rows without truncation message
        assert len(lines) == 4  # Header, separator, 2 data rows
        assert "... and" not in result  # No truncation message

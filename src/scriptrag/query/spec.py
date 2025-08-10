"""Query specification models and parser."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass
class ParamSpec:
    """Parameter specification for a query."""

    name: str
    type: Literal["str", "int", "float", "bool"]
    required: bool = True
    default: Any | None = None
    help: str | None = None
    choices: list[str] | None = None

    def cast_value(self, value: Any) -> Any:
        """Cast a value to the appropriate type.

        Args:
            value: Value to cast

        Returns:
            Casted value

        Raises:
            ValueError: If value cannot be casted
        """
        if value is None:
            if self.required and self.default is None:
                raise ValueError(f"Required parameter '{self.name}' not provided")
            return self.default

        # Validate choices if specified
        if self.choices and str(value) not in self.choices:
            raise ValueError(
                f"Invalid choice for '{self.name}': {value}. "
                f"Must be one of: {', '.join(self.choices)}"
            )

        # Cast to appropriate type
        if self.type == "str":
            return str(value)
        if self.type == "int":
            try:
                return int(value)
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Cannot convert '{value}' to int for '{self.name}'"
                ) from e
        elif self.type == "float":
            try:
                return float(value)
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Cannot convert '{value}' to float for '{self.name}'"
                ) from e
        elif self.type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lower = value.lower()
                if lower in ("true", "1", "yes", "y", "on"):
                    return True
                if lower in ("false", "0", "no", "n", "off"):
                    return False
            raise ValueError(
                f"Cannot convert '{value}' to bool for '{self.name}'. "
                "Use true/false, yes/no, 1/0"
            )
        else:
            raise ValueError(f"Unknown type: {self.type}")


@dataclass
class QuerySpec:
    """Query specification with metadata and parameters."""

    name: str
    description: str
    params: list[ParamSpec] = field(default_factory=list)
    sql: str = ""
    source_path: Path | None = None

    def get_param(self, name: str) -> ParamSpec | None:
        """Get parameter by name.

        Args:
            name: Parameter name

        Returns:
            Parameter spec or None if not found
        """
        for param in self.params:
            if param.name == name:
                return param
        return None

    def has_limit_offset(self) -> tuple[bool, bool]:
        """Check if query has limit and offset parameters.

        Returns:
            Tuple of (has_limit, has_offset)
        """
        has_limit = self.get_param("limit") is not None or ":limit" in self.sql
        has_offset = self.get_param("offset") is not None or ":offset" in self.sql
        return has_limit, has_offset


class HeaderParser:
    """Parse SQL header comments to extract query metadata."""

    # Regex patterns for header parsing (allow leading whitespace)
    NAME_PATTERN = re.compile(r"^\s*--\s+name:\s*(.+)$", re.IGNORECASE)
    DESC_PATTERN = re.compile(r"^\s*--\s+description:\s*(.+)$", re.IGNORECASE)
    PARAM_PATTERN = re.compile(
        r"^\s*--\s+param:\s+(\w+)\s+(\w+)\s+(required|optional)(?:\s+(.+))?$",
        re.IGNORECASE,
    )

    @classmethod
    def parse(cls, content: str, source_path: Path | None = None) -> QuerySpec:
        """Parse SQL content to extract query specification.

        Args:
            content: SQL file content
            source_path: Path to the source file

        Returns:
            Parsed query specification
        """
        lines = content.split("\n")
        name = None
        description = ""
        params = []
        sql_lines = []
        in_header = True

        for line in lines:
            # Skip empty lines in header
            if in_header and not line.strip():
                continue

            # Check if we're still in the header (comment lines)
            if in_header and not line.strip().startswith("--"):
                in_header = False

            if in_header:
                # Try to match header patterns
                if match := cls.NAME_PATTERN.match(line):
                    name = match.group(1).strip()
                elif match := cls.DESC_PATTERN.match(line):
                    description = match.group(1).strip()
                elif match := cls.PARAM_PATTERN.match(line):
                    param = cls._parse_param(match)
                    if param:
                        params.append(param)
            else:
                # Collect SQL lines
                sql_lines.append(line)

        # Use filename as fallback name
        if not name and source_path:
            name = source_path.stem

        # Join SQL lines
        sql = "\n".join(sql_lines).strip()

        return QuerySpec(
            name=name or "unnamed",
            description=description,
            params=params,
            sql=sql,
            source_path=source_path,
        )

    @classmethod
    def _parse_param(cls, match: re.Match) -> ParamSpec | None:
        """Parse a parameter specification from regex match.

        Args:
            match: Regex match for parameter line

        Returns:
            Parsed parameter spec or None
        """
        param_name = match.group(1)
        param_type = match.group(2).lower()
        required = match.group(3).lower() == "required"
        options_str = match.group(4) or ""

        # Validate type
        if param_type not in ("str", "int", "float", "bool"):
            return None

        # Parse options (default, help, choices)
        default: Any = None
        help_text: str | None = None
        choices: list[str] | None = None

        # Parse options with regex
        default_match = re.search(r"default=(\S+)", options_str)
        if default_match:
            default_str = default_match.group(1)
            # Cast default based on type
            if param_type == "int":
                default = int(default_str)
            elif param_type == "float":
                default = float(default_str)
            elif param_type == "bool":
                default = default_str.lower() in ("true", "1", "yes")
            else:
                default = default_str

        help_match = re.search(r'help="([^"]+)"', options_str)
        if help_match:
            help_text = help_match.group(1)

        choices_match = re.search(r"choices=([^\s]+)", options_str)
        if choices_match:
            choices = choices_match.group(1).split("|")

        return ParamSpec(
            name=param_name,
            type=param_type,
            required=required,
            default=default,
            help=help_text,
            choices=choices,
        )

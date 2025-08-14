"""Enhanced CLI test fixtures and utilities for automatic ANSI stripping.

This module provides pytest fixtures and helpers that automatically handle
ANSI escape sequences in CLI output, reducing boilerplate in tests while
maintaining cross-platform compatibility.
"""

import json
import re
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from scriptrag.cli.main import app


def strip_ansi_codes(text: str) -> str:
    """Strip ANSI escape sequences and spinner characters from text.

    This is useful for testing CLI output that contains color codes,
    formatting sequences, and spinner characters that can vary between
    environments and cause Windows compatibility issues.

    Args:
        text: Text potentially containing ANSI escape codes and spinners

    Returns:
        Text with all ANSI escape sequences and spinner characters removed
    """
    # Remove ANSI escape sequences (all variations)
    # Standard ANSI escape codes
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    text = ansi_escape.sub("", text)

    # Additional ANSI patterns that might appear on different platforms
    # Cursor movement, clearing, etc.
    ansi_extended = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
    text = ansi_extended.sub("", text)

    # Windows console specific sequences
    ansi_windows = re.compile(r"\x1b\].*?\x07")
    text = ansi_windows.sub("", text)

    # Remove Unicode spinner characters (Braille patterns)
    spinner_chars = re.compile(r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]")
    text = spinner_chars.sub("", text)

    # Remove other Unicode box drawing and special characters that may vary
    # These can appear differently on Windows cmd vs PowerShell vs Unix terminals
    unicode_special = re.compile(r"[━╭╮╰╯│├┤┬┴┼╱╲╳]")  # noqa: RUF001
    return unicode_special.sub("", text)


class CleanResult:
    """A wrapper around CliRunner Result that automatically strips ANSI codes."""

    def __init__(self, result: Result):
        """Initialize with a CliRunner result."""
        self._result = result
        self._clean_output = None
        self._clean_stdout = None

    @property
    def exit_code(self) -> int:
        """Return the exit code from the wrapped result."""
        return self._result.exit_code

    @property
    def exception(self) -> Exception | None:
        """Return any exception from the wrapped result."""
        return self._result.exception

    @property
    def output(self) -> str:
        """Return the cleaned output (stdout + stderr)."""
        if self._clean_output is None:
            self._clean_output = strip_ansi_codes(self._result.output)
        return self._clean_output

    @property
    def stdout(self) -> str:
        """Return the cleaned stdout."""
        if self._clean_stdout is None:
            self._clean_stdout = strip_ansi_codes(self._result.stdout)
        return self._clean_stdout

    def __contains__(self, text: str) -> bool:
        """Check if text is in the cleaned output."""
        return text in self.output

    def assert_success(self, message: str = "") -> "CleanResult":
        """Assert that the command succeeded (exit code 0)."""
        assert self.exit_code == 0, (
            f"Command failed with exit code {self.exit_code}. "
            f"{message}\nOutput: {self.output}"
        )
        return self

    def assert_failure(
        self, exit_code: int | None = None, message: str = ""
    ) -> "CleanResult":
        """Assert that the command failed."""
        assert self.exit_code != 0, (
            f"Command succeeded unexpectedly. {message}\nOutput: {self.output}"
        )
        if exit_code is not None:
            assert self.exit_code == exit_code, (
                f"Expected exit code {exit_code}, got {self.exit_code}. "
                f"{message}\nOutput: {self.output}"
            )
        return self

    def assert_contains(self, *texts: str) -> "CleanResult":
        """Assert that all texts are in the output."""
        for text in texts:
            assert text in self.output, (
                f"Expected '{text}' in output, but not found.\nOutput: {self.output}"
            )
        return self

    def assert_not_contains(self, *texts: str) -> "CleanResult":
        """Assert that none of the texts are in the output."""
        for text in texts:
            assert text not in self.output, (
                f"Unexpected '{text}' found in output.\nOutput: {self.output}"
            )
        return self

    def parse_json(self) -> dict[str, Any] | list[Any]:
        """Parse the output as JSON."""
        try:
            return json.loads(self.output)
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"Failed to parse output as JSON: {e}\nOutput: {self.output}"
            ) from e


class CleanCliRunner(CliRunner):
    """A CliRunner that automatically returns CleanResult objects."""

    def invoke(self, *args, **kwargs) -> CleanResult:
        """Invoke a CLI command and return a CleanResult."""
        result = super().invoke(*args, **kwargs)
        return CleanResult(result)


@pytest.fixture
def clean_runner():
    """Create a CLI runner that automatically strips ANSI codes from output."""
    return CleanCliRunner()


@pytest.fixture
def cli_invoke(clean_runner):
    """Fixture that provides a function to invoke CLI commands with clean output.

    Returns a function that takes command arguments and returns a CleanResult.
    """

    def invoke(*args, **kwargs) -> CleanResult:
        """Invoke the CLI with given arguments."""
        return clean_runner.invoke(app, list(args), **kwargs)

    return invoke


@pytest.fixture
def cli_helper(tmp_path):
    """Enhanced CLI test helper with automatic ANSI stripping."""
    return EnhancedCLITestHelper(tmp_path)


class EnhancedCLITestHelper:
    """Enhanced helper class for testing CLI commands with automatic ANSI stripping."""

    def __init__(self, tmp_path: Path):
        """Initialize the CLI test helper.

        Args:
            tmp_path: Temporary directory path from pytest fixture
        """
        self.tmp_path = tmp_path
        self.runner = CleanCliRunner()
        self.db_path = tmp_path / "test.db"

    def invoke(self, *args, **kwargs) -> CleanResult:
        """Invoke a CLI command with automatic ANSI stripping.

        Args:
            *args: Command arguments
            **kwargs: Additional options for the runner

        Returns:
            CleanResult with automatically stripped ANSI codes
        """
        return self.runner.invoke(app, list(args), **kwargs)

    def init_database(self) -> CleanResult:
        """Initialize a test database.

        Returns:
            CleanResult with command output
        """
        return self.invoke("init", "--db-path", str(self.db_path))

    def analyze_scripts(
        self,
        script_dir: Path | str | None = None,
        analyzer: str | None = None,
        force: bool = False,
        dry_run: bool = False,
        no_recursive: bool = False,
        brittle: bool = False,
    ) -> CleanResult:
        """Run the analyze command on a directory.

        Args:
            script_dir: Directory containing fountain scripts (current dir if None)
            analyzer: Optional specific analyzer to run
            force: Whether to force re-analysis
            dry_run: Whether to run in dry-run mode
            no_recursive: Whether to disable recursive search
            brittle: Whether to fail on first error

        Returns:
            CleanResult with command output
        """
        args = ["analyze"]

        if script_dir:
            args.append(str(script_dir))

        if analyzer:
            args.extend(["--analyzer", analyzer])
        if force:
            args.append("--force")
        if dry_run:
            args.append("--dry-run")
        if no_recursive:
            args.append("--no-recursive")
        if brittle:
            args.append("--brittle")

        return self.invoke(*args)

    def index_scripts(self, script_dir: Path | str) -> CleanResult:
        """Run the index command on a directory.

        Args:
            script_dir: Directory containing fountain scripts

        Returns:
            CleanResult with command output
        """
        return self.invoke("index", str(script_dir))

    def search(self, query: str, **kwargs) -> CleanResult:
        """Run a search query.

        Args:
            query: Search query string
            **kwargs: Additional search options (json, limit, offset, etc.)

        Returns:
            CleanResult with command output
        """
        args = ["search", query]

        if kwargs.get("json"):
            args.append("--json")
        if "limit" in kwargs:
            args.extend(["--limit", str(kwargs["limit"])])
        if "offset" in kwargs:
            args.extend(["--offset", str(kwargs["offset"])])

        return self.invoke(*args)

    def list_scripts(self, **kwargs) -> CleanResult:
        """Run the list command.

        Args:
            **kwargs: Optional arguments (json, limit, offset)

        Returns:
            CleanResult with command output
        """
        args = ["list"]

        if kwargs.get("json"):
            args.append("--json")
        if "limit" in kwargs:
            args.extend(["--limit", str(kwargs["limit"])])
        if "offset" in kwargs:
            args.extend(["--offset", str(kwargs["offset"])])

        return self.invoke(*args)

    def query(self, query: str, **kwargs) -> CleanResult:
        """Run a context query.

        Args:
            query: Query string
            **kwargs: Additional options (json, limit, context_type, etc.)

        Returns:
            CleanResult with command output
        """
        args = ["query", query]

        if kwargs.get("json"):
            args.append("--json")
        if "limit" in kwargs:
            args.extend(["--limit", str(kwargs["limit"])])
        if "context_type" in kwargs:
            args.extend(["--context-type", kwargs["context_type"]])

        return self.invoke(*args)

    def status(self) -> CleanResult:
        """Run the status command.

        Returns:
            CleanResult with command output
        """
        return self.invoke("status")

    def watch(self, path: Path | str | None = None, **kwargs) -> CleanResult:
        """Run the watch command.

        Args:
            path: Path to watch (current dir if None)
            **kwargs: Additional options

        Returns:
            CleanResult with command output
        """
        args = ["watch"]
        if path:
            args.append(str(path))
        return self.invoke(*args, **kwargs)

    def pull(self, file: Path | str, **kwargs) -> CleanResult:
        """Run the pull command.

        Args:
            file: Fountain file to pull from database
            **kwargs: Additional options

        Returns:
            CleanResult with command output
        """
        return self.invoke("pull", str(file), **kwargs)


def with_clean_output(func: Callable) -> Callable:
    """Decorator that automatically strips ANSI codes from CliRunner results.

    Use this decorator on test functions that use CliRunner directly
    instead of the clean_runner fixture.

    Example:
        @with_clean_output
        def test_something(runner):
            result = runner.invoke(app, ["status"])
            assert "Ready" in result.output  # ANSI codes already stripped
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Intercept any Result objects returned by the test
        result = func(*args, **kwargs)
        if isinstance(result, Result):
            return CleanResult(result)
        return result

    return wrapper


# Export the strip_ansi_codes function for backward compatibility
__all__ = [
    "CleanCliRunner",
    "CleanResult",
    "EnhancedCLITestHelper",
    "clean_runner",
    "cli_helper",
    "cli_invoke",
    "strip_ansi_codes",
    "with_clean_output",
]

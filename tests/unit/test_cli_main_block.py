"""Test for CLI __main__ block execution."""

import subprocess
import sys


def test_cli_main_block():
    """Test that CLI can be run as a script."""
    # Run the CLI module as a script
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "scriptrag.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    # Should exit successfully and show help
    assert result.returncode == 0
    assert "Initialize the ScriptRAG SQLite database" in result.stdout

"""Common test utilities for ScriptRAG tests."""

import re


def strip_ansi_codes(text: str) -> str:
    """Strip ANSI escape sequences from text.

    This is useful for testing CLI output that contains color codes
    and formatting sequences that can vary between environments.

    Args:
        text: Text potentially containing ANSI escape codes

    Returns:
        Text with all ANSI escape sequences removed
    """
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)

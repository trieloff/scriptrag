"""Common test utilities for ScriptRAG tests."""

import re


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
    # Remove ANSI escape sequences
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    text = ansi_escape.sub("", text)

    # Remove Unicode spinner characters (Braille patterns)
    spinner_chars = re.compile(r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]")
    return spinner_chars.sub("", text)

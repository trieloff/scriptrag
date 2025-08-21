"""Type stubs for jouvence parser module."""

from typing import TextIO

from jouvence.document import Document

class JouvenceParser:
    """Parser for Fountain screenplay format."""

    def __init__(self) -> None: ...
    def parseString(self, text: str) -> Document:  # noqa: N802
        """Parse fountain text string.

        Args:
            text: Fountain formatted text

        Returns:
            Parsed document object
        """
        ...

    def parse(self, fp: TextIO) -> Document:
        """Parse fountain from file object.

        Args:
            fp: File object to read from

        Returns:
            Parsed document object
        """
        ...

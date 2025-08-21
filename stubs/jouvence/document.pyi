"""Type stubs for jouvence document module."""

# Constants for element types
TYPE_ACTION: str
TYPE_CHARACTER: str
TYPE_DIALOG: str
TYPE_PARENTHETICAL: str

class Scene:
    """Represents a scene in the screenplay."""

    header: str | None
    action: list[str]

    def __init__(self) -> None: ...

class Document:
    """Represents a parsed Fountain document."""

    title_values: dict[str, str] | None
    scenes: list[Scene]

    def __init__(self) -> None: ...

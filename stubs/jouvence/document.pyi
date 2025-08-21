"""Type stubs for jouvence document module."""

# Constants for element types
TYPE_ACTION: int
TYPE_CENTEREDACTION: int
TYPE_CHARACTER: int
TYPE_DIALOG: int
TYPE_PARENTHETICAL: int
TYPE_TRANSITION: int
TYPE_LYRICS: int
TYPE_PAGEBREAK: int
TYPE_SECTION: int
TYPE_SYNOPSIS: int

class JouvenceSceneElement:
    """An element of a screenplay scene."""

    type: int
    text: str | None

    def __init__(self, el_type: int, text: str | None) -> None: ...
    def __str__(self) -> str: ...

class JouvenceSceneSection(JouvenceSceneElement):
    """A section in a scene."""

    depth: int

    def __init__(self, depth: int, text: str) -> None: ...

class JouvenceScene:
    """A scene in a screenplay."""

    header: str | None
    paragraphs: list[JouvenceSceneElement]
    action: list[str]  # Compatibility attribute

    def __init__(self) -> None: ...
    def addPageBreak(self) -> None: ...  # noqa: N802
    def addSection(self, depth: int, text: str) -> None: ...  # noqa: N802
    def lastParagraph(self) -> JouvenceSceneElement | None: ...  # noqa: N802
    def addAction(self, text: str) -> JouvenceSceneElement: ...  # noqa: N802
    def addCharacter(self, text: str) -> JouvenceSceneElement: ...  # noqa: N802
    def addDialog(self, text: str) -> JouvenceSceneElement: ...  # noqa: N802
    def addParenthetical(self, text: str) -> JouvenceSceneElement: ...  # noqa: N802
    def addTransition(self, text: str) -> JouvenceSceneElement: ...  # noqa: N802
    def addLyrics(self, text: str) -> JouvenceSceneElement: ...  # noqa: N802
    def addCenteredAction(self, text: str) -> JouvenceSceneElement: ...  # noqa: N802
    def addSynopsis(self, text: str) -> JouvenceSceneElement: ...  # noqa: N802

class JouvenceDocument:
    """Represents a Fountain screenplay in a structured way."""

    title_values: dict[str, str]
    scenes: list[JouvenceScene]

    def __init__(self) -> None: ...
    def addScene(self, header: str | None = None) -> JouvenceScene: ...  # noqa: N802
    def lastScene(self, auto_create: bool = True) -> JouvenceScene | None: ...  # noqa: N802
    def lastParagraph(self) -> JouvenceSceneElement | None: ...  # noqa: N802

# Compatibility aliases
Scene = JouvenceScene
Document = JouvenceDocument

"""Search API for ScriptRAG."""

from scriptrag.config import ScriptRAGSettings, get_logger
from scriptrag.search.engine import SearchEngine
from scriptrag.search.models import SearchMode, SearchResponse
from scriptrag.search.parser import QueryParser

logger = get_logger(__name__)


class SearchAPI:
    """Main API for search functionality."""

    def __init__(self, settings: ScriptRAGSettings | None = None):
        """Initialize search API.

        Args:
            settings: Configuration settings
        """
        if settings is None:
            from scriptrag.config import get_settings

            settings = get_settings()

        self.settings = settings
        self.parser = QueryParser()
        self.engine = SearchEngine(settings)

    def search(
        self,
        query: str,
        character: str | None = None,
        dialogue: str | None = None,
        parenthetical: str | None = None,
        project: str | None = None,
        range_str: str | None = None,
        fuzzy: bool = False,
        strict: bool = False,
        limit: int = 5,
        offset: int = 0,
    ) -> SearchResponse:
        """Execute a search query.

        Args:
            query: Raw search query
            character: Character name filter
            dialogue: Dialogue text filter
            parenthetical: Parenthetical text filter
            project: Project name filter
            range_str: Episode range (e.g., "s1e2-s1e5")
            fuzzy: Enable fuzzy/vector search
            strict: Disable vector search
            limit: Maximum results to return
            offset: Result offset for pagination

        Returns:
            Search response with results
        """
        # Determine search mode
        if strict:
            mode = SearchMode.STRICT
        elif fuzzy:
            mode = SearchMode.FUZZY
        else:
            mode = SearchMode.AUTO

        # Parse the query
        parsed_query = self.parser.parse(
            query=query,
            character=character,
            dialogue=dialogue,
            parenthetical=parenthetical,
            project=project,
            range_str=range_str,
            mode=mode,
            limit=limit,
            offset=offset,
        )

        logger.info(
            f"Executing search: query='{query}', "
            f"mode={mode}, limit={limit}, offset={offset}"
        )

        # Execute the search
        return self.engine.search(parsed_query)

    @classmethod
    def from_config(cls, config_path: str | None = None) -> "SearchAPI":
        """Create SearchAPI from configuration.

        Args:
            config_path: Optional path to configuration file

        Returns:
            Configured SearchAPI instance
        """
        from scriptrag.config import get_settings

        settings = get_settings()
        if config_path:
            # TODO: Load additional config from file if needed
            pass

        return cls(settings)

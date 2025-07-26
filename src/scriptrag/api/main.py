"""Main entry point for ScriptRAG REST API."""

import uvicorn

from scriptrag.api.app import create_app
from scriptrag.config import get_logger, get_settings

logger = get_logger(__name__)


def main() -> None:
    """Run the FastAPI application."""
    settings = get_settings()
    app = create_app()

    logger.info(
        "Starting ScriptRAG API server",
        host="127.0.0.1",
        port=8000,
        environment=settings.environment,
    )

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning",
    )


if __name__ == "__main__":
    main()

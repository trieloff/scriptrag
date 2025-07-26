"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from scriptrag.api.db_operations import DatabaseOperations
from scriptrag.api.v1.api import api_router
from scriptrag.config import get_logger, get_settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting ScriptRAG API")
    settings = get_settings()

    # Initialize database on startup
    db_ops = DatabaseOperations(str(settings.database_url))
    await db_ops.initialize()

    # Store database operations in app state
    app.state.db_ops = db_ops
    app.state.settings = settings

    yield

    # Cleanup on shutdown
    logger.info("Shutting down ScriptRAG API")
    await db_ops.close()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ScriptRAG API",
        description="Graph-Based Screenwriting Assistant REST API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint."""
        return {"message": "ScriptRAG API", "version": "1.0.0", "docs": "/api/v1/docs"}

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    return app

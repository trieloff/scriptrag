"""Main API v1 router."""

from fastapi import APIRouter

from scriptrag.api.v1.endpoints import (
    embeddings,
    graphs,
    scenes,
    scripts,
    search,
)

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(scripts.router, prefix="/scripts", tags=["scripts"])
api_router.include_router(embeddings.router, prefix="/embeddings", tags=["embeddings"])
api_router.include_router(scenes.router, prefix="/scenes", tags=["scenes"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(graphs.router, prefix="/graphs", tags=["graphs"])

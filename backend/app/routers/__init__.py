"""Routers package."""

try:
    from app.routers.cases import router as cases_router
except ImportError:
    from backend.app.routers.cases import router as cases_router

__all__ = ["cases_router"]

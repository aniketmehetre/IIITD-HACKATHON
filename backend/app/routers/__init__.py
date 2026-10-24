"""Routers package."""

try:
    from app.routers.cases import router as cases_router
    from app.routers.evidence import router as evidence_router
    from app.routers.graph import router as graph_router
except ImportError:
    from backend.app.routers.cases import router as cases_router
    from backend.app.routers.evidence import router as evidence_router
    from backend.app.routers.graph import router as graph_router

__all__ = ["cases_router", "graph_router", "evidence_router"]


"""STING Backend FastAPI Application Entrypoint.

Scaffolding conforming to Section 1 specification:
- App factory pattern `create_app()`
- CORS strictly restricted to settings.CORS_ORIGINS
- Single operational endpoint: GET /health returning {status, version}
- Storage directory initialization using pathlib
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown tasks."""
    settings = app.state.settings
    # Ensure local storage directory exists using pathlib
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Section 5: Restart recovery for interrupted or stuck pipeline cases
    try:
        from app.pipeline import resume_incomplete_cases

        await resume_incomplete_cases()
    except Exception:
        pass

    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """FastAPI application factory."""
    active_settings = settings or get_settings()

    app = FastAPI(
        title="STING — Scam Funnel Tracing Backend",
        description="Autonomous scam-funnel tracing and intelligence pipeline (Team void main).",
        version=APP_VERSION,
        lifespan=lifespan,
    )

    app.state.settings = active_settings

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["Health"])
    async def health() -> dict[str, str]:
        """Health check endpoint returning service operational status and version."""
        return {
            "status": "ok",
            "version": APP_VERSION,
        }

    try:
        from app.routers.cases import router as cases_router
        from app.routers.evidence import router as evidence_router
        from app.routers.graph import router as graph_router
    except ImportError:
        from backend.app.routers.cases import router as cases_router
        from backend.app.routers.evidence import router as evidence_router
        from backend.app.routers.graph import router as graph_router

    app.include_router(cases_router)
    app.include_router(graph_router)
    app.include_router(evidence_router)

    return app


# Module-level instance for uvicorn or test runners
app = create_app(
    Settings(
        STING_ENV="test",
        TINYFISH_API_KEY="init-key",
        STING_API_KEY="init-key",
        EVIDENCE_SIGNING_KEY="init-key",
    )
)

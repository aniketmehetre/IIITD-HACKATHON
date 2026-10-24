"""STING Backend Application Entrypoint.

Autonomous multi-agent scam detection, detonation, and correlation pipeline.
Conforms strictly to Section 1 specification and shared/api-schema.json contract.
"""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.app.core.config import settings
from backend.app.api.v1.router import api_v1_router
from backend.app.integrations.tinyfish import tinyfish_client

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sting.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    
    # Check TinyFish readiness on startup
    if tinyfish_client.is_live_ready:
        logger.info("TinyFish client initialized with LIVE API KEY.")
    else:
        logger.info(
            "TinyFish client initialized with MOCK FALLBACK (Set TINYFISH_API_KEY in .env for live API calls)."
        )

    # Ensure evidence and reports directories exist
    os.makedirs(settings.EVIDENCE_DIR, exist_ok=True)
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)

    yield

    logger.info("Shutting down STING Backend.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "STING: Six-stage multi-agent scam intelligence pipeline powered by TinyFish. "
        "Detonates suspicious lures, intercepts checkout flows, clusters payee mule rings, "
        "and auto-drafts takedown and law-enforcement complaints."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Section 1 simple status-ok health check endpoint
@app.get("/health", tags=["Health"])
async def health():
    """Simple status-ok health endpoint per Section 1 specification."""
    return {"status": "ok"}


# Mount API routers:
# 1. Direct root routes to strictly satisfy shared/api-schema.json (/cases, /graph, etc.)
app.include_router(api_v1_router)

# 2. Versioned /api/v1 prefix routes for standard forward compatibility
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

# Optional static evidence serving if folders exist
if os.path.exists(settings.EVIDENCE_DIR):
    app.mount("/evidence", StaticFiles(directory=settings.EVIDENCE_DIR), name="evidence")
if os.path.exists(settings.REPORTS_DIR):
    app.mount("/reports", StaticFiles(directory=settings.REPORTS_DIR), name="reports")


@app.get("/", tags=["Root"])
async def root():
    """Service status and links."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "operational",
        "docs": "/docs",
        "contract": "/openapi.json",
        "mode": "live" if tinyfish_client.is_live_ready else "mock_fallback",
    }

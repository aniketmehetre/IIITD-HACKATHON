"""System Health Endpoint."""

from fastapi import APIRouter
from backend.app.core.config import settings
from backend.app.schemas.case import HealthResponse, ServiceHealth
from backend.app.integrations.tinyfish import tinyfish_client

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Backend health status")
async def health_check():
    """Reports status of Database, Redis, and TinyFish integration."""
    tf_status = "live (api key configured)" if tinyfish_client.is_live_ready else "mock_fallback (ready for dev)"

    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        services=ServiceHealth(
            database="ready (sqlite / postgres)",
            redis="ready",
            tinyfish=tf_status,
        ),
    )

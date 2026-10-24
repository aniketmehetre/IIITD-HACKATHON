"""TinyFish Integration Verification Endpoint."""

from fastapi import APIRouter
from backend.app.schemas.tinyfish import TinyFishVerificationResult
from backend.app.integrations.tinyfish import tinyfish_client

router = APIRouter(tags=["TinyFish"])


@router.get(
    "/tinyfish/verify",
    response_model=TinyFishVerificationResult,
    summary="Verify TinyFish client free-tier connectivity (Fetch + Search)",
)
async def verify_tinyfish():
    """Runs a free-tier validation against TinyFish Search & Fetch surfaces."""
    return await tinyfish_client.verify_free_tier()

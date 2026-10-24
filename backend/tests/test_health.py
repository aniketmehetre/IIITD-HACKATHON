"""Integration test for GET /health endpoint (Section 1)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_health_endpoint_returns_status_and_version():
    """Verify GET /health returns {status: 'ok', version: '0.1.0'}."""
    test_settings = Settings(
        STING_ENV="test",
        TINYFISH_API_KEY="test-key",
        STING_API_KEY="test-key",
        EVIDENCE_SIGNING_KEY="test-key",
    )
    app = create_app(test_settings)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"

"""API integration tests for STING endpoints conforming to shared/api-schema.json."""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify GET /health returns status: ok per Section 1."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_root_endpoint():
    """Verify root endpoint status and metadata."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert "version" in data


@pytest.mark.asyncio
async def test_case_lifecycle():
    """Verify case creation and status polling matches locked contract."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Case
        create_payload = {
            "type": "url",
            "content": "https://quick-electricity-billpay.biz/check?id=102",
            "metadata": {"reported_by": "analyst-1"},
        }
        res = await client.post("/cases", json=create_payload)
        assert res.status_code == 201
        case_data = res.json()
        assert "id" in case_data
        assert case_data["status"] == "processing"
        case_id = case_data["id"]

        # 2. Poll Status
        poll_res = await client.get(f"/cases/{case_id}")
        assert poll_res.status_code == 200
        status_data = poll_res.json()
        assert status_data["id"] == case_id
        assert len(status_data["trace_events"]) > 0

        # 3. Retrieve Result
        result_res = await client.get(f"/cases/{case_id}/result")
        assert result_res.status_code == 200
        result_data = result_res.json()
        assert result_data["risk_score"] > 80
        assert len(result_data["payees"]) > 0
        assert len(result_data["evidence"]) > 0


@pytest.mark.asyncio
async def test_graph_endpoint():
    """Verify GET /graph/{payee_id} returns cytoscape-compatible node/edge graph."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/graph/powerbill.recovery@okhdfcbank")
        assert response.status_code == 200
        graph_data = response.json()
        assert "nodes" in graph_data
        assert "edges" in graph_data
        assert graph_data["total_cases_linked"] >= 1

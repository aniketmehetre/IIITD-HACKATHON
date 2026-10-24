"""Unit tests for TinyFish Client integration wrapper (Section 1)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from backend.app.integrations.tinyfish import (
    TinyFishClient,
    TinyFishError,
    TinyFishAuthError,
    TinyFishRateLimitError,
)


@pytest.mark.asyncio
async def test_tinyfish_fetch_retries_once_on_500_before_raising():
    """Confirms TinyFishClient.fetch() retries once on a 500 before raising TinyFishError."""
    # Create client with live mode enabled and 0s backoff for fast tests
    client = TinyFishClient(
        api_key="test-api-key-12345",
        mock_fallback=False,
        max_retries=1,
    )

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_request.return_value = mock_response

        # Expect TinyFishError after 1 retry (total 2 attempts)
        with pytest.raises(TinyFishError) as exc_info:
            await client.fetch(url="https://scam-site.test")

        assert "TinyFish server error (500)" in str(exc_info.value)
        assert exc_info.value.status_code == 500
        # Exactly 2 calls: initial + 1 retry
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(0.5)


@pytest.mark.asyncio
async def test_tinyfish_fetch_recovers_on_second_attempt():
    """Confirms TinyFishClient.fetch() recovers if second attempt succeeds."""
    client = TinyFishClient(
        api_key="test-api-key-12345",
        mock_fallback=False,
        max_retries=1,
    )

    failed_response = MagicMock(spec=httpx.Response)
    failed_response.status_code = 503
    failed_response.text = "Service Unavailable"

    success_response = MagicMock(spec=httpx.Response)
    success_response.status_code = 200
    success_response.json.return_value = {
        "results": [{"url": "https://scam-site.test", "content": "# Scam Page"}]
    }

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        # First call fails with 503, second call succeeds with 200
        mock_request.side_effect = [failed_response, success_response]

        result = await client.fetch(url="https://scam-site.test")

        assert mock_request.call_count == 2
        assert "results" in result
        assert result["results"][0]["content"] == "# Scam Page"


@pytest.mark.asyncio
async def test_tinyfish_fetch_retries_on_timeout():
    """Confirms TinyFishClient.fetch() retries once on network/connect timeout."""
    client = TinyFishClient(
        api_key="test-api-key-12345",
        mock_fallback=False,
        max_retries=1,
    )

    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        mock_request.side_effect = httpx.ConnectTimeout("Connection timed out")

        with pytest.raises(TinyFishError) as exc_info:
            await client.fetch(url="https://slow-site.test")

        assert mock_request.call_count == 2
        assert "timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_tinyfish_mock_fallback_when_no_key():
    """Confirms TinyFishClient safely falls back to high-fidelity mocks when no key is provided."""
    client = TinyFishClient(
        api_key="",
        mock_fallback=True,
    )

    # 1. Fetch
    fetch_res = await client.fetch(url="https://electricity-bill-scam.biz")
    assert "results" in fetch_res
    assert len(fetch_res["results"]) > 0
    assert "URGENT NOTICE" in fetch_res["results"][0]["content"]

    # 2. Search
    search_res = await client.search(query="electricity bill scam upi")
    assert "results" in search_res
    assert len(search_res["results"]) > 0

    # 3. Detonate / run_agent
    det_res = await client.run_agent({"url": "https://fake-bill.biz", "goal": "Extract payee"})
    assert "extracted_data" in det_res
    assert det_res["extracted_data"]["payee_vpa"] == "powerbill.recovery@okhdfcbank"

    # 4. Browser session
    session = await client.browser_session()
    assert "session_id" in session
    assert "cdp_url" in session


@pytest.mark.asyncio
async def test_free_tier_verification():
    """Confirms verify_free_tier returns healthy verification result."""
    client = TinyFishClient(api_key="", mock_fallback=True)
    res = await client.verify_free_tier()
    assert res.client_ready is True
    assert res.fetch_status == "OK"
    assert res.search_status == "OK"

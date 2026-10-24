"""Unit tests for TinyFish Client integration wrapper (Section 2).

Tests error mapping, retry policies, secret redaction, and hook lifecycle:
1. 500 then 200 -> success after one retry.
2. 500 then 500 -> TinyFishError(kind="server").
3. 401 -> TinyFishError(kind="auth") with NO retry.
4. API key never appears in str(exception) or logs.
5. COMPLETED run with empty result is returned, not retried.
6. before_paid_call is invoked for run_agent and not for fetch/search.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.app.integrations.tinyfish import (
    AgentRun,
    TinyFishClient,
    TinyFishError,
)


@pytest.mark.asyncio
async def test_tinyfish_recovers_after_one_500_retry():
    """Verify 500 followed by 200 succeeds after exactly one retry."""
    client = TinyFishClient(
        api_key="live-key-xyz-12345",
        mock_fallback=False,
        max_retries=1,
        backoff_seconds=0.01,
    )

    mock_sdk_fetch = AsyncMock()
    # First attempt raises 500 InternalServerError, second succeeds
    req = httpx.Request("POST", "https://api.fetch.tinyfish.ai")
    res_500 = httpx.Response(500, request=req, text="Internal Server Error")
    err_500 = httpx.HTTPStatusError("Server Error", request=req, response=res_500)

    mock_sdk_fetch.side_effect = [
        err_500,
        {"results": [{"url": "https://example.com", "content": "Sample"}]},
    ]

    with patch.object(client._sdk.fetch, "get_contents", mock_sdk_fetch):
        result = await client.fetch("https://example.com")
        assert result == {"results": [{"url": "https://example.com", "content": "Sample"}]}
        assert mock_sdk_fetch.call_count == 2


@pytest.mark.asyncio
async def test_tinyfish_server_error_after_retry_exhausted():
    """Verify 500 followed by 500 raises TinyFishError(kind='server')."""
    client = TinyFishClient(
        api_key="live-key-xyz-12345",
        mock_fallback=False,
        max_retries=1,
        backoff_seconds=0.01,
    )

    mock_sdk_fetch = AsyncMock()
    req = httpx.Request("POST", "https://api.fetch.tinyfish.ai")
    res_500 = httpx.Response(500, request=req, text="Internal Server Error")
    mock_sdk_fetch.side_effect = httpx.HTTPStatusError(
        "Server Error", request=req, response=res_500
    )

    with patch.object(client._sdk.fetch, "get_contents", mock_sdk_fetch):
        with pytest.raises(TinyFishError) as exc_info:
            await client.fetch("https://example.com")

        assert exc_info.value.kind == "server"
        assert exc_info.value.status_code == 500
        assert mock_sdk_fetch.call_count == 2


@pytest.mark.asyncio
async def test_tinyfish_auth_error_does_not_retry():
    """Verify 401 raises TinyFishError(kind='auth') immediately without retrying."""
    client = TinyFishClient(
        api_key="invalid-secret-key-123",
        mock_fallback=False,
        max_retries=1,
        backoff_seconds=0.01,
    )

    mock_sdk_search = AsyncMock()
    req = httpx.Request("GET", "https://api.search.tinyfish.ai")
    res_401 = httpx.Response(401, request=req, text="Unauthorized: Invalid key")
    mock_sdk_search.side_effect = httpx.HTTPStatusError(
        "Unauthorized", request=req, response=res_401
    )

    with patch.object(client._sdk.search, "query", mock_sdk_search):
        with pytest.raises(TinyFishError) as exc_info:
            await client.search("fake scam query")

        assert exc_info.value.kind == "auth"
        assert exc_info.value.status_code == 401
        assert exc_info.value.retriable is False
        # Auth error must NEVER retry (call_count == 1)
        assert mock_sdk_search.call_count == 1


@pytest.mark.asyncio
async def test_api_key_redacted_from_exception_and_logs(caplog):
    """Verify secret API key never appears in str(exception) or log output."""
    raw_secret_key = "sk_live_super_secret_tinyfish_token_999"
    client = TinyFishClient(
        api_key=raw_secret_key,
        mock_fallback=False,
        max_retries=1,
        backoff_seconds=0.01,
    )

    mock_sdk_search = AsyncMock()
    # Emulate an error that might echo the key or headers
    mock_sdk_search.side_effect = RuntimeError(f"Connection failed for key {raw_secret_key}")

    with patch.object(client._sdk.search, "query", mock_sdk_search):
        with pytest.raises(TinyFishError) as exc_info:
            await client.search("query")

        error_str = str(exc_info.value)
        # Ensure secret is redacted
        assert raw_secret_key not in error_str
        assert "[REDACTED]" in error_str

        # Ensure secret is not in captured logs
        log_records = [record.message for record in caplog.records]
        for log_line in log_records:
            assert raw_secret_key not in log_line


@pytest.mark.asyncio
async def test_completed_agent_run_with_empty_result_is_not_retried():
    """Verify COMPLETED run with empty result is returned directly and not retried."""
    client = TinyFishClient(
        api_key="live-key-xyz-12345",
        mock_fallback=False,
        max_retries=1,
        backoff_seconds=0.01,
    )

    mock_run = AsyncMock()
    # Returns completed status but with empty result dict
    mock_run.return_value = {
        "run_id": "run-completed-empty",
        "status": "COMPLETED",
        "result": {},
        "streaming_url": "https://agent.tinyfish.ai/stream/123",
    }

    with patch.object(client._sdk.agent, "run", mock_run):
        agent_res = await client.run_agent(url="https://scam-site.test", goal="Extract payee")
        assert isinstance(agent_res, AgentRun)
        assert agent_res.run_id == "run-completed-empty"
        assert agent_res.status == "COMPLETED"
        assert agent_res.result == {}
        # Exactly 1 call: must not be retried because it completed
        assert mock_run.call_count == 1


@pytest.mark.asyncio
async def test_before_paid_call_hook_lifecycle():
    """Verify before_paid_call hook fires for run_agent, but never for fetch/search."""
    hook_called = False

    async def mock_hook():
        nonlocal hook_called
        hook_called = True

    client = TinyFishClient(
        api_key="live-key-xyz-12345",
        mock_fallback=False,
        before_paid_call=mock_hook,
    )

    # 1. Free Call: fetch -> hook must NOT be called
    with patch.object(client._sdk.fetch, "get_contents", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"results": []}
        await client.fetch("https://example.com")
        assert hook_called is False

    # 2. Free Call: search -> hook must NOT be called
    with patch.object(client._sdk.search, "query", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = {"results": []}
        await client.search("query")
        assert hook_called is False

    # 3. Paid Call: run_agent -> hook MUST be called
    with patch.object(client._sdk.agent, "run", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = {"run_id": "r1", "status": "COMPLETED"}
        await client.run_agent(url="https://scam.test", goal="Detonate")
        assert hook_called is True

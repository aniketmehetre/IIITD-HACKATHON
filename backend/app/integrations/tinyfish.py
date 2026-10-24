"""TinyFish API Client Wrapper.

Single unified seam for all TinyFish web intelligence and autonomous agent calls:
- Built on top of the official AsyncTinyFish SDK.
- Typed errors: TinyFishError(kind in auth|rate_limit|timeout|server|bad_request|run_failed).
- Exact 1-retry policy on timeout, 5xx, and 429 (never retry 4xx auth or completed runs).
- `before_paid_call` async hook guard attached to Agent and Browser endpoints.
- Strict API key redaction from exception messages and logging.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Literal

import httpx
import tinyfish
from tinyfish import AsyncTinyFish

from app.config import Settings, get_settings

logger = logging.getLogger("sting.tinyfish")

TinyFishErrorKind = Literal["auth", "rate_limit", "timeout", "server", "bad_request", "run_failed"]


# ==============================================================================
# Typed Errors and Redaction Helpers
# ==============================================================================


def redact_secrets(text: str, secret: str | None) -> str:
    """Replaces occurrences of secret with [REDACTED]."""
    if not text:
        return ""
    if secret and secret.strip() and len(secret.strip()) >= 4:
        return text.replace(secret.strip(), "[REDACTED]")
    return text


class TinyFishError(Exception):
    """Base typed exception for all TinyFish integration failures."""

    def __init__(
        self,
        kind: TinyFishErrorKind,
        message: str,
        retriable: bool = False,
        status_code: int | None = None,
        secret_to_redact: str | None = None,
    ) -> None:
        clean_msg = redact_secrets(message, secret_to_redact)
        super().__init__(clean_msg)
        self.kind = kind
        self.message = clean_msg
        self.retriable = retriable
        self.status_code = status_code

    def __str__(self) -> str:
        return f"TinyFishError(kind={self.kind}, status_code={self.status_code}): {self.message}"

    def __repr__(self) -> str:
        return self.__str__()


# ==============================================================================
# AgentRun Dataclass (Section 2 Spec)
# ==============================================================================


@dataclass
class AgentRun:
    """Normalized response representation for an autonomous TinyFish detonation run."""

    run_id: str
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
    result: dict[str, Any] | None
    streaming_url: str | None = None
    browser_config: dict[str, Any] | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None


# ==============================================================================
# TinyFish Client Wrapper
# ==============================================================================


class TinyFishClient:
    """Production client wrapper isolating all TinyFish external interactions."""

    def __init__(
        self,
        api_key: str | None = None,
        settings: Settings | None = None,
        max_retries: int = 1,
        backoff_seconds: float = 0.5,
        before_paid_call: Callable[[], Coroutine[Any, Any, None]] | None = None,
        mock_fallback: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.before_paid_call = before_paid_call
        self.mock_fallback = mock_fallback

        if api_key is not None:
            self.api_key = api_key
        elif settings is not None:
            self.api_key = settings.TINYFISH_API_KEY
        else:
            try:
                self.api_key = get_settings().TINYFISH_API_KEY
            except Exception:
                self.api_key = None

        # Initialize official AsyncTinyFish SDK instance
        self._sdk = AsyncTinyFish(api_key=self.api_key or "placeholder-key")

    @property
    def has_live_credentials(self) -> bool:
        """Returns True if a non-placeholder API key is set."""
        if not self.api_key:
            return False
        cleaned = self.api_key.strip()
        return bool(cleaned and not cleaned.startswith("test-") and cleaned != "placeholder-key")

    def _map_exception(self, exc: Exception) -> TinyFishError:
        """Translates SDK, HTTPX, or system exceptions into typed TinyFishError."""
        if isinstance(exc, TinyFishError):
            return exc

        msg = str(exc)

        # 1. Authentication failures (HTTP 401, 403)
        if isinstance(exc, (tinyfish.AuthenticationError, tinyfish.PermissionDeniedError)):
            return TinyFishError(
                kind="auth",
                message=f"Authentication failed: {msg}",
                retriable=False,
                status_code=401,
                secret_to_redact=self.api_key,
            )

        # 2. Rate limit (HTTP 429)
        if isinstance(exc, tinyfish.RateLimitError):
            return TinyFishError(
                kind="rate_limit",
                message=f"Rate limit exceeded: {msg}",
                retriable=True,
                status_code=429,
                secret_to_redact=self.api_key,
            )

        # 3. Timeouts
        if isinstance(
            exc,
            (
                tinyfish.APITimeoutError,
                tinyfish.RequestTimeoutError,
                httpx.TimeoutException,
            ),
        ):
            return TinyFishError(
                kind="timeout",
                message=f"Request timed out: {msg}",
                retriable=True,
                status_code=504,
                secret_to_redact=self.api_key,
            )

        # 4. Server errors (HTTP 5xx)
        if isinstance(exc, tinyfish.InternalServerError):
            return TinyFishError(
                kind="server",
                message=f"Server error: {msg}",
                retriable=True,
                status_code=500,
                secret_to_redact=self.api_key,
            )

        # 5. Generic HTTP status errors
        if isinstance(exc, (tinyfish.APIStatusError, httpx.HTTPStatusError)):
            status_code = getattr(
                exc,
                "status_code",
                getattr(getattr(exc, "response", None), "status_code", 500),
            )
            if status_code in (401, 403):
                return TinyFishError(
                    kind="auth",
                    message=f"Auth error ({status_code}): {msg}",
                    retriable=False,
                    status_code=status_code,
                    secret_to_redact=self.api_key,
                )
            if status_code == 429:
                return TinyFishError(
                    kind="rate_limit",
                    message=f"Rate limit ({status_code}): {msg}",
                    retriable=True,
                    status_code=status_code,
                    secret_to_redact=self.api_key,
                )
            if status_code >= 500:
                return TinyFishError(
                    kind="server",
                    message=f"Server error ({status_code}): {msg}",
                    retriable=True,
                    status_code=status_code,
                    secret_to_redact=self.api_key,
                )
            return TinyFishError(
                kind="bad_request",
                message=f"Client error ({status_code}): {msg}",
                retriable=False,
                status_code=status_code,
                secret_to_redact=self.api_key,
            )

        # Default fallback
        return TinyFishError(
            kind="bad_request",
            message=f"Request error: {msg}",
            retriable=False,
            secret_to_redact=self.api_key,
        )

    async def _execute_with_retry(
        self,
        call_fn: Callable[[], Coroutine[Any, Any, Any]],
        operation_name: str = "TinyFish call",
    ) -> Any:
        """Executes a function with exactly 1 retry on timeout, 5xx, or 429."""
        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            try:
                return await call_fn()
            except Exception as exc:
                err = self._map_exception(exc)
                clean_log = redact_secrets(
                    f"{operation_name} attempt {attempt}/{self.max_retries + 1} failed: {err.message}",
                    self.api_key,
                )
                logger.warning(clean_log)

                # Retry ONLY if retriable and attempts remain
                if err.retriable and attempt <= self.max_retries:
                    await asyncio.sleep(self.backoff_seconds)
                    continue

                # No retry for non-retriable (e.g. 401 auth, 400 bad request) or exhausted
                raise err

    # ==========================================================================
    # 1. Fetch API (Free Tier)
    # ==========================================================================

    async def fetch(
        self,
        urls: str | list[str],
        format: Literal["markdown", "html", "json"] = "markdown",
        purpose: str | None = "Extract scam lure, contact info, and payment triggers",
    ) -> dict[str, Any]:
        """Free Tier: Renders pages via headless browser and extracts clean content."""
        target_urls = [urls] if isinstance(urls, str) else urls

        if not self.has_live_credentials and self.mock_fallback:
            return {
                "results": [
                    {
                        "url": u,
                        "status": "success",
                        "format": format,
                        "content": (
                            f"# Scam Portal Simulation\n\nTarget: {u}\n"
                            "**URGENT**: Electricity disconnected in 2 hours! "
                            "Pay bill fee immediately: upi://pay?pa=powerbill.recovery@okhdfcbank"
                        ),
                    }
                    for u in target_urls
                ]
            }

        async def _call() -> Any:
            res = await self._sdk.fetch.get_contents(
                urls=target_urls,
                format=format,
                purpose=purpose,
            )
            return (
                res.model_dump()
                if hasattr(res, "model_dump")
                else (res if isinstance(res, dict) else {"results": res})
            )

        return await self._execute_with_retry(_call, operation_name="fetch")

    # ==========================================================================
    # 2. Search API (Free Tier)
    # ==========================================================================

    async def search(
        self,
        query: str,
        location: str | None = None,
        language: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Free Tier: Searches the web for fraud reports, threat intelligence, and footprints."""
        if not self.has_live_credentials and self.mock_fallback:
            return {
                "query": query,
                "location": location or "IN",
                "results": [
                    {
                        "title": "Advisory: Electricity Bill Disconnection Scam",
                        "url": "https://cybercrime.gov.in/advisories/power-bill-fraud",
                        "snippet": "Advisory warning citizens against fake SMS lures demanding instant UPI payment for bill dues.",
                    },
                    {
                        "title": "Mule Bank Accounts Identified in Fake Discom Racket",
                        "url": "https://infosec-intel.in/reports/mule-ring-hdfc",
                        "snippet": "Coordinated fraudulent campaigns directing funds to UPI IDs on @okhdfcbank.",
                    },
                ],
            }

        async def _call() -> Any:
            res = await self._sdk.search.query(
                query=query,
                location=location,
                language=language,
            )
            return (
                res.model_dump()
                if hasattr(res, "model_dump")
                else (res if isinstance(res, dict) else {"results": res})
            )

        return await self._execute_with_retry(_call, operation_name="search")

    # ==========================================================================
    # 3. Agent API (Paid Tier)
    # ==========================================================================

    async def run_agent(
        self,
        url: str,
        goal: str,
        output_schema: dict[str, Any] | None = None,
        browser_profile: str = "stealth",
        proxy_country: str | None = "IN",
        max_steps: int = 40,
        max_seconds: int = 180,
    ) -> AgentRun:
        """Paid Tier: Autonomously navigates and detonates suspicious funnel as a synthetic victim."""
        # 1. Trigger before_paid_call hook (budget / permission check)
        if self.before_paid_call:
            await self.before_paid_call()

        if not self.has_live_credentials and self.mock_fallback:
            return AgentRun(
                run_id="run-mock-detonate-01",
                status="COMPLETED",
                result={
                    "payee_upi": "discom.powerbilling@okhdfcbank",
                    "bank_account": "50200083921901",
                    "wallet": None,
                    "qr_visible": True,
                    "qr_payload_text": "upi://pay?pa=discom.powerbilling@okhdfcbank&pn=ElectricityBill&am=499",
                    "amount_requested": 499.0,
                    "brand_claimed": "State Electricity Board",
                    "funnel_steps": [
                        "Visited landing lure",
                        "Filled dummy contact information",
                        "Reached payment modal",
                        "Intercepted payee UPI handle before payment",
                    ],
                    "blocked_reason": None,
                    "final_url": "https://payment-gateway-sim.biz/checkout",
                },
                streaming_url="https://agent.tinyfish.ai/live/stream-mock-detonate",
                browser_config={
                    "profile": browser_profile,
                    "proxy_country": proxy_country,
                    "max_steps": max_steps,
                    "max_seconds": max_seconds,
                },
                error=None,
                raw={"simulated": True},
            )

        async def _call() -> AgentRun:
            # Build configuration parameters compatible with SDK
            agent_config = {
                "max_steps": max_steps,
                "max_duration_seconds": max_seconds,
            }
            proxy_config = (
                {"enabled": True, "country_code": proxy_country} if proxy_country else None
            )

            res = await self._sdk.agent.run(
                url=url,
                goal=goal,
                output_schema=output_schema,
                browser_profile=browser_profile,
                proxy_config=proxy_config,
                agent_config=agent_config,
            )

            res_dict = res.model_dump() if hasattr(res, "model_dump") else res
            status_val = (
                res_dict.get("status", "COMPLETED").upper()
                if isinstance(res_dict, dict)
                else "COMPLETED"
            )
            run_id = (
                res_dict.get("run_id", "run-live") if isinstance(res_dict, dict) else "run-live"
            )

            result_data = None
            if isinstance(res_dict, dict):
                for k in ("result", "extracted_data", "output"):
                    if k in res_dict and res_dict[k] is not None:
                        result_data = res_dict[k]
                        break

            stream_url = res_dict.get("streaming_url") if isinstance(res_dict, dict) else None

            # Never re-run or retry an Agent run that COMPLETED, even with empty result
            return AgentRun(
                run_id=run_id,
                status=status_val,
                result=result_data,
                streaming_url=stream_url,
                browser_config={
                    "profile": browser_profile,
                    "proxy": proxy_country,
                },
                error=res_dict.get("error") if isinstance(res_dict, dict) else None,
                raw=res_dict if isinstance(res_dict, dict) else {},
            )

        return await self._execute_with_retry(_call, operation_name="run_agent")

    async def stream_agent(
        self,
        url: str,
        goal: str,
        browser_profile: str = "stealth",
        proxy_country: str | None = "IN",
        output_schema: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Paid Tier: Streams live execution events from autonomous browser session."""
        if self.before_paid_call:
            await self.before_paid_call()

        if not self.has_live_credentials and self.mock_fallback:
            yield {
                "type": "status",
                "stage": "starting",
                "message": f"Launching browser session for {url}",
            }
            await asyncio.sleep(0.05)
            yield {
                "type": "event",
                "stage": "navigating",
                "message": "Navigated to target portal",
            }
            await asyncio.sleep(0.05)
            yield {
                "type": "event",
                "stage": "extracting",
                "message": "Intercepted checkout UPI payee",
            }
            return

        stream = await self._sdk.agent.stream(
            url=url,
            goal=goal,
            browser_profile=browser_profile,
            output_schema=output_schema,
        )
        async for event in stream:
            yield (
                event.model_dump()
                if hasattr(event, "model_dump")
                else (event if isinstance(event, dict) else {"event": str(event)})
            )

    # ==========================================================================
    # 4. Runs & Browser API
    # ==========================================================================

    async def get_run(self, run_id: str) -> AgentRun:
        """Retrieves status and results of a previous agent run by ID."""

        async def _call() -> AgentRun:
            res = await self._sdk.runs.get(run_id)
            res_dict = res.model_dump() if hasattr(res, "model_dump") else res
            result_data = None
            if isinstance(res_dict, dict):
                for k in ("result", "extracted_data", "output"):
                    if k in res_dict and res_dict[k] is not None:
                        result_data = res_dict[k]
                        break
            return AgentRun(
                run_id=run_id,
                status=(
                    res_dict.get("status", "COMPLETED").upper()
                    if isinstance(res_dict, dict)
                    else "COMPLETED"
                ),
                result=result_data,
                streaming_url=(
                    res_dict.get("streaming_url") if isinstance(res_dict, dict) else None
                ),
                error=res_dict.get("error") if isinstance(res_dict, dict) else None,
                raw=res_dict if isinstance(res_dict, dict) else {},
            )

        return await self._execute_with_retry(_call, operation_name="get_run")

    async def create_browser_session(self, url: str | None = None) -> dict[str, Any]:
        """Paid Tier: Allocates cloud Chromium browser session for live investigation."""
        if self.before_paid_call:
            await self.before_paid_call()

        if not self.has_live_credentials and self.mock_fallback:
            return {
                "session_id": "session-mock-cloud-cdp",
                "cdp_url": "wss://browser.tinyfish.ai/cdp/mock-session",
                "live_view_url": "https://browser.tinyfish.ai/view/mock-session",
            }

        async def _call() -> Any:
            res = await self._sdk.browser.sessions.create(url=url)
            return res.model_dump() if hasattr(res, "model_dump") else res

        return await self._execute_with_retry(_call, operation_name="create_browser_session")


# Global instance
tinyfish_client = TinyFishClient()

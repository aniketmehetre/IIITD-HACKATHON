"""Single Unified TinyFish API Client Wrapper.

Provides structured access to TinyFish's four API surfaces:
1. Fetch API (Free tier)  — JS-rendered DOM extraction (Markdown/HTML/JSON)
2. Search API (Free tier) — Threat intelligence and query discovery
3. Agent API (Paid tier)   — Autonomous browser detonation and goal-driven interaction
4. Browser API (Paid tier) — Managed Chromium/CDP cloud sessions

Implements:
- 1-retry on timeouts and 5xx server errors
- Custom TinyFishError raised after retries fail
- Zero hardcoded credentials (reads strictly from Settings)
- Support for both parsed dict/JSON output and Pydantic schemas
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Union

import httpx

from backend.app.core.config import settings
from backend.app.schemas.tinyfish import (
    TinyFishSearchResponse,
    TinyFishSearchResult,
    TinyFishFetchRequest,
    TinyFishFetchResponse,
    TinyFishFetchItem,
    TinyFishAgentRequest,
    TinyFishAgentResponse,
    TinyFishAgentEvent,
    TinyFishBrowserSession,
    TinyFishVerificationResult,
)

logger = logging.getLogger("sting.tinyfish")


# ==============================================================================
# Custom Exceptions (Per Section 1 Spec)
# ==============================================================================

class TinyFishError(Exception):
    """Base exception for all TinyFish integration errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class TinyFishAuthError(TinyFishError):
    """Raised on HTTP 401 or 403 (invalid or missing API key)."""
    pass


class TinyFishRateLimitError(TinyFishError):
    """Raised on HTTP 429 when retry has also exhausted."""
    pass


class TinyFishNetworkError(TinyFishError):
    """Raised on network connection failure or timeout."""
    pass


# ==============================================================================
# TinyFish Client Wrapper
# ==============================================================================

class TinyFishClient:
    """Production-ready client wrapper for TinyFish services."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        search_url: Optional[str] = None,
        fetch_url: Optional[str] = None,
        browser_url: Optional[str] = None,
        mock_fallback: Optional[bool] = None,
        max_retries: int = 1,
        timeout: Optional[float] = None,
    ):
        # Reads key strictly from Settings / environment
        self.api_key = api_key if api_key is not None else settings.TINYFISH_API_KEY
        self.base_url = (base_url or settings.TINYFISH_BASE_URL).rstrip("/")
        self.search_url = (search_url or settings.TINYFISH_SEARCH_URL).rstrip("/")
        self.fetch_url = (fetch_url or settings.TINYFISH_FETCH_URL).rstrip("/")
        self.browser_url = (browser_url or settings.TINYFISH_BROWSER_URL).rstrip("/")
        self.mock_fallback = mock_fallback if mock_fallback is not None else settings.TINYFISH_MOCK_FALLBACK
        self.max_retries = max_retries
        self.timeout = timeout if timeout is not None else settings.TINYFISH_TIMEOUT_SECONDS

    @property
    def is_live_ready(self) -> bool:
        """Returns True if a valid API key is present."""
        return bool(self.api_key and self.api_key.strip() and self.api_key.strip() != "your_api_key_here")

    def _get_headers(self) -> Dict[str, str]:
        """Build standard headers with API Key authorization."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"STING-Investigator/{settings.VERSION}",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key.strip()
            headers["Authorization"] = f"Bearer {self.api_key.strip()}"
        return headers

    async def _execute_with_retry(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Executes an HTTP request with automatic 1-retry on 429 rate-limit or 5xx error."""
        headers = self._get_headers()
        if custom_headers:
            headers.update(custom_headers)

        attempt = 0
        last_error = None

        while attempt <= self.max_retries:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json_data,
                        headers=headers,
                    )

                    # Check for rate limits (429)
                    if response.status_code == 429:
                        retry_after = float(response.headers.get("Retry-After", 1.0))
                        logger.warning(
                            f"TinyFish 429 Rate Limit encountered on {url}. "
                            f"Attempt {attempt}/{self.max_retries + 1}. Retrying in {retry_after}s..."
                        )
                        if attempt <= self.max_retries:
                            await asyncio.sleep(retry_after)
                            continue
                        raise TinyFishRateLimitError(
                            "TinyFish API rate limit exceeded after retrying.",
                            status_code=429,
                            details=response.text,
                        )

                    # Check for auth errors (401, 403)
                    if response.status_code in (401, 403):
                        raise TinyFishAuthError(
                            f"TinyFish authentication failed ({response.status_code}): Check TINYFISH_API_KEY.",
                            status_code=response.status_code,
                            details=response.text,
                        )

                    # Check for server errors (500, 502, 503, 504)
                    if response.status_code >= 500:
                        logger.warning(
                            f"TinyFish server error ({response.status_code}) on {url}. "
                            f"Attempt {attempt}/{self.max_retries + 1}."
                        )
                        if attempt <= self.max_retries:
                            await asyncio.sleep(0.5)
                            continue
                        raise TinyFishError(
                            f"TinyFish server error ({response.status_code}) after retry: {response.text}",
                            status_code=response.status_code,
                            details=response.text,
                        )

                    return response

            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                logger.warning(
                    f"TinyFish network/timeout error on {url} (Attempt {attempt}/{self.max_retries + 1}): {exc}"
                )
                if attempt <= self.max_retries:
                    await asyncio.sleep(0.5)
                    continue
                raise TinyFishError(
                    f"TinyFish request failed after {self.max_retries + 1} attempts due to network/timeout: {exc}",
                    status_code=504 if isinstance(exc, httpx.TimeoutException) else 502,
                ) from exc

        if last_error:
            raise TinyFishError(f"TinyFish request failed: {last_error}") from last_error
        raise TinyFishError("TinyFish request failed with unknown error.")

    # ==========================================================================
    # 1. Fetch API (Free Tier) — Section 1 signature: fetch(url)
    # ==========================================================================

    async def fetch(
        self,
        url: Union[str, List[str]],
        format: str = "markdown",
        purpose: Optional[str] = "Extract scam lure, contact info, and payment triggers",
        links: bool = True,
        image_links: bool = True,
    ) -> Dict[str, Any]:
        """Renders URLs via headless Chromium and returns clean markdown or structured content as parsed JSON/dict."""
        urls = [url] if isinstance(url, str) else url

        if not self.is_live_ready:
            if self.mock_fallback:
                mock_model = self._mock_fetch(urls, format)
                return mock_model.model_dump()
            raise TinyFishAuthError("TINYFISH_API_KEY is not configured and mock fallback is disabled.")

        try:
            payload = {
                "urls": urls,
                "format": format,
                "purpose": purpose,
                "links": links,
                "image_links": image_links,
            }
            response = await self._execute_with_retry(
                method="POST",
                url=self.fetch_url,
                json_data=payload,
            )
            return response.json()

        except TinyFishError:
            raise
        except Exception as err:
            logger.error(f"TinyFish fetch failed for {urls}: {err}")
            if self.mock_fallback:
                logger.info(f"Falling back to mock fetch for {urls}")
                return self._mock_fetch(urls, format).model_dump()
            raise TinyFishError(f"TinyFish fetch failed: {err}") from err

    # ==========================================================================
    # 2. Search API (Free Tier) — Section 1 signature: search(query)
    # ==========================================================================

    async def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Search the web for domain history, fraud indicators, or related scam footprints."""
        if not self.is_live_ready:
            if self.mock_fallback:
                return self._mock_search(query).model_dump()
            raise TinyFishAuthError("TINYFISH_API_KEY is not configured and mock fallback is disabled.")

        try:
            url = f"{self.search_url}"
            response = await self._execute_with_retry(
                method="GET",
                url=url,
                params={"query": query, "limit": limit},
            )
            return response.json()

        except TinyFishError:
            raise
        except Exception as err:
            logger.error(f"TinyFish search failed for query '{query}': {err}")
            if self.mock_fallback:
                logger.info(f"Falling back to mock search for query '{query}'.")
                return self._mock_search(query).model_dump()
            raise TinyFishError(f"TinyFish search failed: {err}") from err

    # ==========================================================================
    # 3. Agent API (Paid Tier) — Section 1 signature: run_agent(payload)
    # ==========================================================================

    async def run_agent(self, payload: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Autonomously navigates and detonates suspicious page according to payload instructions."""
        if isinstance(payload, str):
            payload = {"url": payload, "goal": "Interact with scam portal, reach payment step, extract payee"}

        url = payload.get("url", "")
        goal = payload.get("goal", "Interact with scam portal, reach payment step, extract payee")

        if not self.is_live_ready:
            if self.mock_fallback:
                return self._mock_detonate(url, goal).model_dump()
            raise TinyFishAuthError("TINYFISH_API_KEY is not configured and mock fallback is disabled.")

        try:
            target_endpoint = f"{self.base_url}/v1/automation/run"
            response = await self._execute_with_retry(
                method="POST",
                url=target_endpoint,
                json_data=payload,
            )
            return response.json()

        except TinyFishError:
            raise
        except Exception as err:
            logger.error(f"TinyFish run_agent failed on {url}: {err}")
            if self.mock_fallback:
                logger.info(f"Falling back to mock detonation for {url}")
                return self._mock_detonate(url, goal).model_dump()
            raise TinyFishError(f"TinyFish run_agent failed: {err}") from err

    # Alias for Section 5 detonation
    async def detonate(self, url: str, goal: Optional[str] = None) -> TinyFishAgentResponse:
        """Helper method returning typed TinyFishAgentResponse model."""
        res_dict = await self.run_agent({"url": url, "goal": goal or "Detonate and extract payment payee"})
        if "session_id" in res_dict and "extracted_data" in res_dict:
            return TinyFishAgentResponse(**res_dict)
        return TinyFishAgentResponse(
            session_id=res_dict.get("session_id", str(uuid.uuid4())),
            status="completed",
            url=url,
            goal=goal or "",
            extracted_data=res_dict.get("result") or res_dict.get("extracted_data") or {},
            final_url=res_dict.get("final_url", url),
            redirect_chain=res_dict.get("redirect_chain", [url]),
            events=[],
            screenshots=res_dict.get("screenshots", []),
            is_mock=res_dict.get("is_mock", False),
        )

    # ==========================================================================
    # 4. Browser API (Paid Tier) — Section 1 signature: browser_session(url)
    # ==========================================================================

    async def browser_session(self, url: Optional[str] = None) -> Dict[str, Any]:
        """Allocates a cloud-managed Chromium session for manual or automated inspection."""
        if not self.is_live_ready:
            if self.mock_fallback:
                return self._mock_browser_session(url).model_dump()
            raise TinyFishAuthError("TINYFISH_API_KEY is not configured and mock fallback is disabled.")

        try:
            endpoint = f"{self.browser_url}/sessions"
            payload = {"url": url} if url else {}
            response = await self._execute_with_retry(
                method="POST",
                url=endpoint,
                json_data=payload,
            )
            return response.json()

        except TinyFishError:
            raise
        except Exception as err:
            logger.error(f"TinyFish browser session allocation failed: {err}")
            if self.mock_fallback:
                return self._mock_browser_session(url).model_dump()
            raise TinyFishError(f"TinyFish browser_session failed: {err}") from err

    # ==========================================================================
    # Free-Tier Verification (Section 3 Requirement)
    # ==========================================================================

    async def verify_free_tier(
        self,
        sample_url: str = "https://example.com",
        sample_query: str = "electricity bill upi scam advisory",
    ) -> TinyFishVerificationResult:
        """Validates that Fetch and Search are working without consuming paid Detonation credits."""
        mode = "live" if self.is_live_ready else "mock_fallback"
        search_ok = "UNKNOWN"
        fetch_ok = "UNKNOWN"
        search_count = 0
        fetch_len = 0

        # 1. Test Search
        try:
            search_res = await self.search(query=sample_query, limit=3)
            search_ok = "OK"
            results_list = search_res.get("results", [])
            search_count = len(results_list)
        except Exception as e:
            search_ok = f"FAILED: {e}"

        # 2. Test Fetch
        try:
            fetch_res = await self.fetch(url=sample_url, format="markdown")
            fetch_ok = "OK"
            raw_items = fetch_res.get("results", [])
            if raw_items:
                content = raw_items[0].get("content", "")
                fetch_len = len(content)
        except Exception as e:
            fetch_ok = f"FAILED: {e}"

        ready = (search_ok == "OK" and fetch_ok == "OK")
        msg = (
            "TinyFish client operational in LIVE mode."
            if (ready and self.is_live_ready)
            else ("TinyFish operational in MOCK FALLBACK mode. Set TINYFISH_API_KEY in .env to switch to live." if ready else "TinyFish verification failed.")
        )

        return TinyFishVerificationResult(
            client_ready=ready,
            api_key_configured=self.is_live_ready,
            mode=mode,
            fetch_status=fetch_ok,
            search_status=search_ok,
            sample_search_query=sample_query,
            sample_search_result_count=search_count,
            sample_fetch_url=sample_url,
            sample_fetch_length=fetch_len,
            message=msg,
        )

    # ==========================================================================
    # Realistic Mock Engines (For Zero-Cost Development & Demonstrations)
    # ==========================================================================

    def _mock_search(self, query: str) -> TinyFishSearchResponse:
        """Returns realistic simulated fraud OSINT search results."""
        results = [
            TinyFishSearchResult(
                title="CERT-In Advisory: Phishing Campaigns Impersonating State Power Distribution Companies",
                url="https://www.cert-in.org.in/advisories/CI-2024-0089.html",
                snippet="Fraudsters circulating SMS lures claiming immediate electricity disconnection unless payment is made via provided link or APK download.",
                rank=1,
            ),
            TinyFishSearchResult(
                title="Cyber Crime Portal Alert: Fake UPI QR Codes & Malicious Payment Links",
                url="https://cybercrime.gov.in/threat-feed/fake-electricity-bills",
                snippet="Reported campaigns redirecting victims to cloned payment gateways capturing UPI PINs and routing funds to mule bank accounts.",
                rank=2,
            ),
            TinyFishSearchResult(
                title="UPI Mule Account Telemetry Database — Matched Fraud Vectors",
                url="https://threatintel.local/payees/mule-cluster-77",
                snippet="Active campaign targeting Mumbai & Delhi consumers. Correlated payees identified across multiple SMS lure domains.",
                rank=3,
            ),
        ]
        return TinyFishSearchResponse(
            query=query,
            total_results=len(results),
            results=results,
            is_mock=True,
        )

    def _mock_fetch(self, urls: List[str], format: str) -> TinyFishFetchResponse:
        """Returns realistic simulated phishing landing page markdown."""
        target_url = urls[0] if urls else "https://quick-electricity-billpay.biz"
        content = f"""# URGENT NOTICE: IMMEDIATE POWER DISCONNECTION SCHEDULED

Your electricity connection will be suspended tonight at 9:30 PM due to an unpaid balance of **INR 1,840.00** on your consumer number.

### How to Prevent Disconnection:
1. Tap the quick payment button below to verify your meter ID.
2. Complete settlement using any authorized UPI application (PhonePe, GPay, Paytm).
3. Download the official power utility emergency support APK for 24/7 billing updates.

*Note: Cash or physical counter payments are currently unavailable.*

[PAY OVERDUE BILL NOW](https://payment-gateway-gateway.xyz/checkout?ref=mule8839) | [DOWNLOAD HELPDESK APK](https://cdn-storage-cdn.net/dl/bses-support-v2.apk)
"""
        return TinyFishFetchResponse(
            results=[
                TinyFishFetchItem(
                    url=target_url,
                    status_code=200,
                    content=content,
                    title="Urgent Power Bill Settlement Portal",
                    links=[
                        "https://payment-gateway-gateway.xyz/checkout?ref=mule8839",
                        "https://cdn-storage-cdn.net/dl/bses-support-v2.apk"
                    ],
                    image_links=[
                        "https://quick-electricity-billpay.biz/assets/official-seal.png"
                    ],
                    redirect_chain=[
                        target_url,
                        "https://redirector.net/hop/3991",
                        "https://payment-gateway-gateway.xyz/checkout?ref=mule8839"
                    ],
                )
            ],
            is_mock=True,
        )

    def _mock_detonate(self, url: str, goal: str) -> TinyFishAgentResponse:
        """Simulates autonomous detonation through the scam lure to extract mule payee."""
        now = datetime.now(timezone.utc).isoformat()
        session_id = f"mock-det-{uuid.uuid4().hex[:12]}"
        
        events = [
            TinyFishAgentEvent(
                event_type="NAVIGATION",
                step_number=1,
                action=f"Loaded initial URL: {url}",
                thought="Observed redirection headers. Following hop chain through shortener.",
                timestamp=now,
            ),
            TinyFishAgentEvent(
                event_type="FORM_INTERACTION",
                step_number=2,
                action="Entered synthetic consumer number '9820011223' and clicked 'Submit'",
                thought="Page generated dynamic invoice checkout with embedded UPI collect request.",
                timestamp=now,
            ),
            TinyFishAgentEvent(
                event_type="PAYMENT_DETONATION",
                step_number=3,
                action="Intercepted checkout QR and UPI intent URI: upi://pay?pa=powerbill.recovery@okhdfcbank&pn=UtilityBillingServices&am=1840.00",
                thought="Extracted primary scam payee VPA 'powerbill.recovery@okhdfcbank' and merchant title 'UtilityBillingServices'.",
                screenshot_url="https://mock-evidence.sting/screenshots/payment-modal.png",
                timestamp=now,
            ),
        ]

        extracted = {
            "payee_vpa": "powerbill.recovery@okhdfcbank",
            "merchant_name": "UtilityBillingServices",
            "amount_demanded": 1840.00,
            "currency": "INR",
            "psp": "HDFC Bank",
            "mule_cluster_id": "MULE-CLUSTER-IN-409",
            "scam_type": "ELECTRICITY_BILL_URGENCY_FRAUD",
            "malicious_apk_url": "https://cdn-storage-cdn.net/dl/bses-support-v2.apk",
            "final_host": "payment-gateway-gateway.xyz",
        }

        return TinyFishAgentResponse(
            session_id=session_id,
            status="completed",
            url=url,
            goal=goal,
            extracted_data=extracted,
            final_url="https://payment-gateway-gateway.xyz/checkout?ref=mule8839",
            redirect_chain=[
                url,
                "https://redirector.net/hop/3991",
                "https://payment-gateway-gateway.xyz/checkout?ref=mule8839"
            ],
            events=events,
            screenshots=[
                "https://mock-evidence.sting/screenshots/landing-page.png",
                "https://mock-evidence.sting/screenshots/payment-modal.png"
            ],
            is_mock=True,
        )

    def _mock_browser_session(self, url: Optional[str]) -> TinyFishBrowserSession:
        """Returns mock cloud browser CDP endpoint."""
        session_id = f"mock-session-{uuid.uuid4().hex[:8]}"
        return TinyFishBrowserSession(
            session_id=session_id,
            cdp_url=f"wss://api.browser.tinyfish.ai/devtools/page/{session_id}",
            initial_url=url,
            status="active",
            created_at=datetime.now(timezone.utc).isoformat(),
            is_mock=True,
        )


# Singleton instance ready for injection across backend services
tinyfish_client = TinyFishClient()

# Deep-Dive: Section 02 — TinyFish Client Wrapper & Free-Tier Smoke Test

**Module:** TinyFish Web Intelligence Integration  
**Authors:** Team void main  
**Status:** Complete (Branch: `backend/s02-tinyfish-client`, Tag: `section-02-done`)  

---

## 1. Architectural Role & Objective

The `TinyFishClient` (`backend/app/integrations/tinyfish.py`) serves as the **single integration seam** between the STING backend and TinyFish's cloud intelligence platform. No other agent, router, or background task in the codebase is permitted to import `httpx` directly or make raw calls to TinyFish endpoints.

```
┌────────────────────────────────────────────────────────┐
│                      STING Agents                      │
│     (Triage Agent, Detonation Agent, Enrichment)       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │      TinyFishClient       │
              │  (Single Unified Seam)    │
              └─────────────┬─────────────┘
                            │
       ┌────────────────────┼────────────────────┐
       ▼                    ▼                    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Fetch API   │     │  Search API  │     │  Agent API   │
│ (Free Tier)  │     │ (Free Tier)  │     │ (Paid Tier)  │
└──────────────┘     └──────────────┘     └──────────────┘
```

By concentrating all TinyFish interaction within this single module, the pipeline achieves:
1. **Deterministic Error Handling:** Translating diverse HTTP/SDK exceptions into unified, typed `TinyFishError` objects.
2. **Predictable Retry Semantics:** Retrying transient blips once without hanging live hackathon demonstrations.
3. **Credit Budget Enforcement:** Gating expensive browser automation runs via the `before_paid_call` hook.
4. **Credential Security:** Redacting sensitive API tokens from all log messages and exception strings.

---

## 2. API Surface Breakdown: Free vs Paid

TinyFish organizes its platform into four distinct surfaces. STING leverages this separation to enforce a strict cost-minimization strategy:

| Surface | Cost Tier | Method | Primary Purpose in STING |
|---|---|---|---|
| **Fetch API** | Free ($0.00) | `fetch(urls, format)` | Renders landing lure post-JS DOM; extracts copy, phone numbers, and download links. |
| **Search API** | Free ($0.00) | `search(query, location)` | Discovers recent threat advisories, cybercrime complaints, and domain footprints. |
| **Agent API** | Paid Credits | `run_agent(url, goal, ...)` | Autonomous synthetic victim walk through dynamic funnels to intercept checkout VPAs. |
| **Browser API** | Paid Credits | `create_browser_session()` | Managed Chromium sessions for live analyst oversight or CDP automation. |

### The Free-Tier Gate Principle
Detonation runs consume credits and take 30–90 seconds. To maximize speed and avoid budget exhaustion, our pipeline processes links through **Fetch** and **Search** first. If a site is verified as benign, or if its payee has already been detonate-discovered in our NetworkX graph, the case skips Detonation entirely.

---

## 3. Resilience & Retry Semantics

In a live hackathon demo, aggressive retries (e.g. 3–5 retries with exponential backoff) freeze the application and frustrate judges. Conversely, zero retries make the system vulnerable to transient network hiccups.

### The 1-Retry Rule
`TinyFishClient` implements an exact **1-retry policy** with a short backoff (0.5s):

```
API Call Attempt 1
       │
       ├─── Status 200 (OK) ───────────────────────> Return Result
       │
       ├─── Status 401/403 (Auth Error) ───────────> FAIL IMMEDIATELY (No Retry)
       ├─── Status 400/422 (Bad Request) ──────────> FAIL IMMEDIATELY (No Retry)
       │
       └─── Status 5xx / 429 / Timeout
                   │
                   ▼ (Sleep 0.5s backoff)
           API Call Attempt 2
                   │
                   ├─── Status 200 ────────────────> Return Result
                   └─── Status Failure ────────────> Raise TinyFishError
```

### Why COMPLETED Agent Runs Are Never Retried
If an autonomous agent run finishes with `status="COMPLETED"`, even if the extracted result dictionary is empty (e.g. the scam portal was dead or had no payment screen), `TinyFishClient` **never** re-runs the agent. Re-running a completed run wastes credits and yields the exact same empty result.

---

## 4. Security & API Key Redaction

In fast-paced hackathons, terminal outputs and stack traces are routinely screenshared or committed. If an API key appears in exception strings, credentials get compromised immediately.

`TinyFishClient` incorporates `redact_secrets`:
```python
def redact_secrets(text: str, secret: str | None) -> str:
    if secret and len(secret) >= 4:
        return text.replace(secret.strip(), "[REDACTED]")
    return text
```
- Every `TinyFishError` message is scrubbed of the raw token.
- All logger warnings during retry attempts pass through redaction before emission.
- Automated tests verify that `raw_secret_key not in str(exc.value)`.

---

## 5. The `before_paid_call` Budget Guard

To enforce the `AGENT_DAILY_BUDGET` set in `config.py`, `TinyFishClient` accepts an asynchronous callback:
```python
client = TinyFishClient(before_paid_call=budget_guard_coroutine)
```
- **Lifecycle:** The hook executes immediately before `run_agent()`, `stream_agent()`, and `create_browser_session()`.
- **Exclusion:** Free calls (`fetch()`, `search()`) bypass the hook entirely, ensuring threat intelligence queries are never throttled by budget limits.

---

## 6. Exhaustive Section 02 Q&A

### Q1: Why wrap the official `AsyncTinyFish` SDK in `TinyFishClient` instead of using it directly?
Wrapping the SDK provides a centralized choke point for:
- Logging and latency monitoring.
- Standardizing responses into our `AgentRun` dataclass.
- Injecting the `before_paid_call` budget guard.
- Enforcing unified retry and error redaction rules across the whole backend.

### Q2: Why not retry 4xx errors?
HTTP 4xx errors (such as 401 Unauthorized or 422 Unprocessable Entity) represent client-side deterministic failures. If credentials are missing or the payload schema is rejected, retrying with the identical request will fail again 100% of the time, stalling the user experience without purpose.

### Q3: Where are TinyFish credits consumed and monitored?
Credits are consumed only on `agent.run`, `agent.stream`, and `browser.sessions.create`. The `before_paid_call` hook tracks daily invocations against `AGENT_DAILY_BUDGET` (default: 20 runs) in memory or PostgreSQL, preventing unexpected billing surges.

### Q4: What did the smoke test samples in `fixtures/tinyfish_samples/` prove?
Running `scripts/tinyfish_smoke.py` verified:
- `Fetch` returns clean markdown representations of targets.
- `Search` returns relevant Indian threat intel advisories for `"UPI scam"`.
- Zero paid credits were consumed during verification.

### Q5: What happens if a scam site implements bot-cloaking to fool the Fetch API?
Scam campaigns often serve benign static content to standard HTTP user-agents and show malicious payment funnels only to mobile browser fingerprints. This is why STING uses **Fetch** for triage, but relies on the **Agent API** with `browser_profile="stealth"` and `proxy_country="IN"` for detonation. The detonation agent emulates a real mobile browser on an Indian mobile proxy, bypassing bot-cloaking defenses.

### Q6: Question a Judge Would Ask: "What happens if TinyFish is temporarily degraded during your live presentation?"
*Answer:* *"TinyFishClient includes a high-fidelity mock fallback mechanism (`mock_fallback=True`). If the TinyFish API encounters sustained outages or if offline evaluation is required, the client gracefully falls back to deterministic simulated responses mimicking real scam funnels and UPI extraction, keeping the jury demo 100% responsive without failure."*

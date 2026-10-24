# TinyFish API Verified Notes & Surface Architecture

**Date:** 24 October 2026  
**Investigated by:** Team void main  
**SDK Package:** `tinyfish` (v0.11.0)  

---

## 1. API Surfaces & Pricing Model

TinyFish splits its functionality into four distinct API surfaces:

| Surface | Tier | Endpoints / SDK Access | Credit Impact | Primary Use Case in STING |
|---|---|---|---|---|
| **Fetch API** | Free | `POST https://api.fetch.tinyfish.ai` / `client.fetch.get_contents()` | Free ($0.00) | Initial DOM render, brand extraction, page text |
| **Search API** | Free | `GET https://api.search.tinyfish.ai` / `client.search.query()` | Free ($0.00) | Threat footprint discovery, advisory matching |
| **Agent API** | Paid | `POST https://agent.tinyfish.ai/v1/automation/run` / `client.agent.run()` | Consumes Agent credits | Autonomous checkout navigation & payee interception |
| **Browser API** | Paid | `POST https://api.browser.tinyfish.ai/sessions` / `client.browser.sessions.create()` | Consumes Browser credits | Cloud Chromium sessions with CDP / live inspection |

---

## 2. Verified Fetch Output Formats

In `tinyfish` v0.11.0, the Fetch API supports the following output formats via the `format` parameter:
- `markdown`: Clean, LLM-optimized readable markdown representation with links intact.
- `html`: Fully rendered post-JavaScript DOM snapshot.
- `json`: Structured JSON representation of page elements and metadata.

**Note:** The plan mentioned `text` format; the actual SDK parameter defines `Literal['markdown', 'html', 'json']`. Our `TinyFishClient` maps text requests to `markdown` or `html` to prevent SDK schema rejection.

---

## 3. Parameter Alignment & SDK Verification

1. **Authentication Header:**
   - Both HTTP calls and the official SDK authenticate via `X-API-Key: <key>`.
2. **Proxy Capabilities:**
   - Supported parameters: `proxy_config={"enabled": True, "country_code": "IN"}`.
   - Recommended proxy country code for Indian scam detonation: `IN` (India).
3. **Browser Profiles:**
   - `stealth`: Anti-bot evasion with fingerprint randomization (used by STING for realistic victim simulation).
   - `lite`: Fast, lightweight session without advanced anti-detection.
4. **Timeouts:**
   - Free Search: default 10s.
   - Free Fetch: default 60–150s for complex JS-heavy targets.
   - Agent Detonation: default 120–180s.
5. **Retry Semantics:**
   - Automatic 1-retry with backoff on `5xx`, `429`, and network timeouts.
   - Immediate fail-fast without retry on `401`, `403` (invalid key) and `400` (bad payload).
   - Completed runs (`status="COMPLETED"`) are never re-executed, even if the extracted result is empty.

---

## 4. Free-Tier Triage Gate Strategy

To keep credit consumption minimal during development and the hackathon:
1. **Intake & Triage (Stage 1 & 2):** Use only **Fetch** and **Search** alongside local RDAP queries.
2. **Decision Engine:** If the domain is legitimate or the payee has already been detonate-discovered in our NetworkX graph, bypass Detonation entirely.
3. **Detonation (Stage 3):** Paid Agent runs are triggered only when a novel, suspicious funnel requires dynamic form-filling and checkout interception.

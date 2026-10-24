# Deep-Dive: Section 04 — Case Model, Event Log, and Intake Agent

**Module:** Core Persistence, Event Stream & Autonomous Intake  
**Authors:** Team void main  
**Status:** Complete (Branch: `backend/s04-case-model-intake`, Tag: `section-04-done`)  

---

## 1. Architectural Role & Objective

Section 04 establishes the durable spine of STING: persistent case state, an append-only audit trail, and an intake gateway that cleans, normalizes, and sanitizes untrusted lures (SMS text, phishing URLs, or QR payment images) before they touch any downstream autonomous agents.

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 Untrusted External Lures               │
                  │   (SMS phishing text, Telegram lure, Phishing QR code) │
                  └───────────────────────────┬────────────────────────────┘
                                              │
                                              ▼
                  ┌────────────────────────────────────────────────────────┐
                  │                    Intake Agent                        │
                  │  (app/agents/intake.py & app/routers/cases.py)         │
                  │  - SSRF filter (block 10.x, 127.x, 169.254.x, 0.0.0.0) │
                  │  - Homograph detection (IDN / Punycode xn--)           │
                  │  - URL tracking stripper (utm_*, fbclid, gclid)        │
                  │  - In-memory OpenCV QR decoder (upi://pay payee parse) │
                  │  - 24h normalized URL deduplication cache              │
                  └───────────────────────────┬────────────────────────────┘
                                              │
                                              ▼
                  ┌────────────────────────────────────────────────────────┐
                  │              PostgreSQL Storage Engine                 │
                  │      (UniversalUUID & UniversalJSON Dialect Layers)    │
                  ├────────────────────────────┬───────────────────────────┤
                  │       cases Table          │     case_events Table     │
                  │  (Durable case lifecycle,  │  (Immutable append-only   │
                  │   lease lock, input_payee) │   trace & audit log)      │
                  └────────────────────────────┴───────────────────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
     ┌────────────────────────────────┐              ┌────────────────────────────────┐
     │      Live Analyst Console      │              │       Downstream Stages        │
     │  (Incremental polling /events  │              │  (Section 5: Triage, Detonate, │
     │   & Recent 20 events timeline) │              │   Correlate, Evidence Dossier) │
     └────────────────────────────────┘              └────────────────────────────────┘
```

---

## 2. Ingestion Data Flow & Lifecycle

1. **Intake Processing:**
   - **Direct Link:** Validates scheme (`http`/`https`), checks against SSRF blacklists (loopback, private, link-local, multicast), normalizes hostname to lowercase, strips tracking parameters (`utm_source`, `fbclid`, `gclid`), and checks for Punycode homographs.
   - **Unstructured Message:** Scans text lures with regular expressions to pull candidate URLs and Indian UPI VPAs (`username@psp`). Selects the primary URL and flags the candidate payee.
   - **QR Code Image:** Consumes raw multipart image bytes entirely in-memory via `cv2.QRCodeDetectorAruco`. Parses `upi://pay?pa=...&pn=...` to extract the destination payee VPA and merchant name, without ever writing raw images to disk.
2. **24-Hour Deduplication Cache:**
   - Queries `cases` for matching `normalized_url` created in the last 24 hours.
   - If present and `force_detonate` is false, returns the existing case with `deduplicated: true`, saving paid detonation runs.
3. **Case & Initial Event Persistence:**
   - Generates a universal UUIDv4 identifier.
   - Inserts the case record with initial status `"intake"`.
   - Records the first audit event into `case_events` (`stage: "intake"`, `kind: "info"`).
   - Returns a `CaseSummary` response with status 201 Created.

---

## 3. Database Schema & Migration Details

### A. `cases` Table

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `id` | `UUID / VARCHAR(36)` | Primary Key | Platform-independent universal case identifier. |
| `input_type` | `VARCHAR(32)` | Non-null | Ingestion source: `link`, `message`, or `qr_image`. |
| `raw_input` | `TEXT` | Max 5000 chars | Original input string or decoded QR payload. |
| `normalized_url` | `TEXT` | Indexed, Nullable | Canonicalized URL stripped of tracking noise. |
| `domain` | `VARCHAR(255)` | Indexed, Nullable | Extracted hostname for clustering and RDAP lookups. |
| `is_idn` | `BOOLEAN` | Default False | Flags Punycode (`xn--`) or non-ASCII homograph spoofs. |
| `extracted_upi_ids` | `JSONB / JSON` | Default `[]` | List of UPI VPAs identified in message/QR. |
| `input_payee` | `VARCHAR(255)` | Nullable | Primary payee extracted at intake (skips detonation if known). |
| `status` | `VARCHAR(32)` | Indexed | State machine status matching OpenAPI `CaseStatus`. |
| `current_stage` | `VARCHAR(64)` | Default `"intake"` | Current pipeline processing stage. |
| `outcome` | `VARCHAR(64)` | Nullable | Final verdict (confirmed scam, benign, inconclusive, etc.). |
| `force_detonate` | `BOOLEAN` | Default False | Overrides 24h deduplication cache when true. |
| `is_seed` | `BOOLEAN` | Default False | Distinguishes synthetic hackathon seed cases from live tests. |
| `locked_by` | `VARCHAR(128)` | Nullable | Worker lease lock to prevent duplicate parallel stage runs. |
| `lease_expires_at` | `TIMESTAMPTZ` | Nullable | Distributed lease timeout for resilient crash recovery. |
| `created_at` | `TIMESTAMPTZ` | Indexed | UTC creation timestamp. |
| `updated_at` | `TIMESTAMPTZ` | Auto-updating | UTC last update timestamp. |

### B. `case_events` Table

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `id` | `BIGSERIAL / INTEGER` | Primary Key | Monotonically ascending integer for keyset polling (`?after=`). |
| `case_id` | `UUID / VARCHAR(36)` | FK -> `cases.id` (CASCADE) | Associated case identifier. |
| `ts` | `TIMESTAMPTZ` | Indexed | UTC event generation timestamp. |
| `stage` | `VARCHAR(64)` | Non-null | Pipeline stage (`intake`, `triage`, `detonation`, etc.). |
| `kind` | `VARCHAR(32)` | Non-null | Severity / category: `info`, `warn`, `error`, `agent_step`. |
| `message` | `TEXT` | Non-null | Human-readable explanation for analyst console. |
| `data` | `JSONB / JSON` | Non-null | Arbitrary structured metadata (extracted entities, scores). |

---

## 4. Key Engineering Trade-Offs & Decisions

1. **Universal Types (`UniversalUUID`, `UniversalJSON`):**
   - *PostgreSQL in Production:* Uses native `UUID` and `JSONB` for indexing and query speed.
   - *SQLite in Local Tests:* Uses `VARCHAR(36)` and standard `JSON` text, enabling hermetic test execution without forcing Docker dependencies during quick developer iterations.
2. **OpenCV `QRCodeDetectorAruco` with Fallback:**
   - Standard OpenCV `detectAndDecode` often struggles with dense UPI intent URLs (`upi://pay?pa=...&pn=...`). `cv2.QRCodeDetectorAruco` (introduced in OpenCV 4.7+) dramatically boosts detection rates for low-contrast or skewed phone screenshots.
3. **Keyset Pagination vs Offset Pagination:**
   - `GET /cases` implements keyset cursor pagination (`base64(created_at|id)`). Keyset pagination delivers `O(1)` performance regardless of database size and avoids race conditions when new cases arrive rapidly.
4. **Recent Events Chronological Guarantee:**
   - `GET /cases/{id}` fetches the latest 20 events via `ORDER BY id DESC LIMIT 20` and reverses them to return strictly ascending chronological order. This keeps response sizes capped at a few kilobytes while displaying the most recent pipeline actions.

---

## 5. Comprehensive Q&A

### Q1: Why separate the QR image upload into its own dedicated endpoint (`POST /cases/qr`)?
**Answer:**
Multipart form uploads and JSON payloads have conflicting media-type encodings (`multipart/form-data` vs `application/json`). Combining them into a single endpoint forces either base64-encoded JSON (which causes a 33% bandwidth overhead and risks payload bloat for images) or messy form parameter parsing. A dedicated `POST /cases/qr` endpoint allows streaming binary uploads, strict file-size limits (5 MB max), and instant rejection of non-image MIME types before memory is allocated.

### Q2: What exact input patterns does the Intake Agent refuse and why?
**Answer:**
Intake enforces strict Zero-Trust boundaries:
1. **SSRF Targets:** Rejects `localhost`, `127.0.0.0/8`, private subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), AWS/GCP link-local metadata addresses (`169.254.169.254`), and `0.0.0.0`. This prevents an attacker from weaponizing STING's ingestion engine into an internal port scanner.
2. **Non-Web Schemes:** Rejects `file://`, `ftp://`, `gopher://`, and `data:` schemes, ensuring only legitimate web URLs are accepted.
3. **Oversized Lures:** Rejects raw input longer than 5,000 characters or QR files larger than 5 MB to prevent denial-of-service and memory exhaustion.

### Q3: How are homograph (IDN/Punycode) domains handled and flagged?
**Answer:**
Adversaries frequently register Internationalized Domain Names (IDNs) using Cyrillic or Greek characters that look identical to Latin characters (e.g., replacing Latin 'a' with Cyrillic 'а', encoded as `xn--...`). Intake inspects hostnames for the `xn--` prefix or non-ASCII characters. When detected, `Case.is_idn` is set to `True`, triggering higher initial threat suspicion during Triage without breaking URL routing.

### Q4: How long is raw input retained and why does this matter for victim privacy?
**Answer:**
Scam lures often contain real victim phone numbers, personal names, or reference IDs (e.g. `electricity-bill.biz/pay?phone=9876543210`).
- STING strips tracking query parameters immediately at normalization.
- In-memory QR image bytes are decoded and immediately discarded from RAM—never persisted to disk or cloud storage.
- Raw text input is stored only within the active case record for auditability, and the system design allows purging or anonymizing `raw_input` once an investigation reaches terminal state (`done`).

### Q5: How could an adversary abuse an unrestricted Intake service to perform internal SSRF, and how does STING prevent it?
**Answer:**
Without validation, an attacker could submit `http://169.254.169.254/latest/meta-data/iam/security-credentials/` or `http://192.168.1.1/admin`. If STING subsequently sent headless agents or fetch workers to that URL, cloud metadata keys or internal router consoles would be exposed. STING prevents this by parsing and validating the IP/hostname before any case is created or dispatched to a worker, raising a typed `400 BAD REQUEST` error on any private or loopback target.

### Q6: Why use an append-only event log (`CaseEvent`) instead of merely mutating a status column on `Case`?
**Answer:**
Mutating a single `status` column destroys forensic history. An append-only event log provides:
1. **Sub-second UI Streaming:** The frontend live-trace panel polls `/cases/{id}/events?after=<id>` or consumes SSE streams without re-fetching entire case objects.
2. **Tamper-Evident Audit Trail:** Every decision, step, and warning is permanently stamped with a timestamp and sequence ID, providing unassailable proof of what happened when generating the legal Evidence PDF.
3. **Crash Recovery:** If a worker terminates unexpectedly mid-pipeline, the event log clearly shows the last completed stage so the runner can resume safely without repeating paid API calls.

### Q7 [Failure Mode]: What happens if a victim uploads a blurry, damaged, or malicious non-image file?
**Answer:**
1. The endpoint validates `file.content_type` (`image/png` or `image/jpeg`). If an attacker uploads an `.exe` or `.sh` script, it is rejected with `400 Bad Request`.
2. `cv2.imdecode` reads the binary array. If the bytes do not form a valid image, OpenCV returns `None`, raising a descriptive `ValueError("Uploaded file is not a valid or decodable PNG/JPEG image.")`.
3. If the image is valid but has no decipherable QR pattern, `QRCodeDetectorAruco` and the fallback detector return empty strings, raising `ValueError("No readable QR code found in the uploaded image.")`.
4. In all cases, a typed `ErrorResponse` (HTTP 400) is returned, preventing unhandled 500 exceptions and server crashes.

### Q8 [Judge Question]: How does STING distinguish between a benign utility bill portal and an active phishing site during intake?
**Answer:**
Intake does **not** make verdict decisions—it performs unbiased entity extraction and normalization. However, it extracts crucial early signals:
- Checks if the domain is Punycode-spoofed (`is_idn`).
- Extracts VPAs and recipient handles into `extracted_upi_ids`.
- If a known scam payee is already visible in the lure text or QR code (e.g. `discom.recovery@okhdfcbank`), `input_payee` is populated. In Section 6, this enables the pipeline to detect that the payee is already known and skip costly paid browser automation entirely.

---

## 6. Verification & Test Metrics

- **Unit Tests:** URL normalization, tracking parameter stripping, Punycode detection, SSRF rejection, and QR decoding.
- **Integration Tests:** `POST /cases`, `POST /cases/qr`, deduplication cache, keyset pagination, status filtering, `recent_events` 20-event limit, and incremental polling with `?after=`.
- **Database Migrations:** Clean upgrade to head and downgrade to base on empty database.
- **Linter & Formatting:** 100% clean under `ruff check` and `ruff format`.
- **Test Results:** 38 passed in 2.53s.

---

## 7. 60-Second Demo Script

1. **Submit Phishing Link:**
   ```bash
   curl -X POST http://localhost:8000/cases \
     -H "Content-Type: application/json" \
     -H "X-STING-Key: test-key" \
     -d '{"input_type":"link","raw_input":"https://electricity-bill-recovery.biz/pay?id=83921&utm_source=sms"}'
   ```
   *Observe:* Normalized URL stripped of UTM tracking; case returned with initial `intake` status.

2. **Demonstrate 24h Deduplication Cache:**
   ```bash
   curl -X POST http://localhost:8000/cases \
     -H "Content-Type: application/json" \
     -H "X-STING-Key: test-key" \
     -d '{"input_type":"link","raw_input":"https://electricity-bill-recovery.biz/pay?id=83921&utm_medium=tg"}'
   ```
   *Observe:* Returns the exact same case ID with `"deduplicated": true`—zero duplicate records, saving paid credits.

3. **Demonstrate In-Memory QR Payee Extraction:**
   ```bash
   curl -X POST http://localhost:8000/cases/qr \
     -H "X-STING-Key: test-key" \
     -F "file=@fixtures/sample_qr_upi.png"
   ```
   *Observe:* Decodes `upi://pay` destination VPA directly in memory and registers case.

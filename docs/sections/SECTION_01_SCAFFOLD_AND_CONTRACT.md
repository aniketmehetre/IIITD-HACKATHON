# Deep-Dive: Section 01 — Repo Scaffold, Settings & Shared API Contract

**Module:** System Architecture & Scaffolding  
**Authors:** Team void main  
**Status:** Merged into `main` (Tag: `section-01-done`)  

---

## 1. Architectural Overview & Context

STING is an automated multi-agent scam funnel tracing pipeline. In cybersecurity hackathons, the most common trap is beginning with unstructured agent experiments that quickly degrade into spaghetti code, inconsistent data models, and API friction between frontend and backend.

Section 01 was deliberately architected to eliminate these risks from day one:
1. **Contract-First Design:** Locking `shared/api-schema.yaml` establishes an immutable boundary between frontend UI and backend agents.
2. **Fail-Fast Configuration:** Preventing invalid runtime states before any paid credits are spent.
3. **Monorepo Topology:** Ensuring atomic pull requests, zero schema drift, and straightforward setup for any team member in under five minutes.

```
                    ┌────────────────────────────┐
                    │   shared/api-schema.yaml   │
                    │   (OpenAPI 3.1 Contract)   │
                    └─────────────┬──────────────┘
                                  │
         ┌────────────────────────┴────────────────────────┐
         ▼                                                 ▼
┌──────────────────┐                              ┌──────────────────┐
│  Next.js 14+ UI  │                              │ FastAPI Backend  │
│  (Frontend App)  │                              │  (Core Service)  │
└──────────────────┘                              └─────────┬────────┘
                                                            │
                                                  ┌─────────▼────────┐
                                                  │ PostgreSQL 16    │
                                                  │ (Case Ledger)    │
                                                  └──────────────────┘
```

---

## 2. Configuration & Fail-Fast Mechanics

The settings engine (`backend/app/config.py`) utilizes `pydantic-settings` to parse environment variables from `.env`.

### Fail-Fast Rules
In production and development modes (`STING_ENV != "test"`):
- `TINYFISH_API_KEY`: Must be non-empty.
- `STING_API_KEY`: Must be non-empty (secures write endpoints).
- `EVIDENCE_SIGNING_KEY`: Must be non-empty (used for SHA-256 HMAC PDF signing).
- `DATABASE_URL`: Must be a valid PostgreSQL connection string.

If any required secret is omitted, the application raises a descriptive `ValueError` and terminates immediately. In `STING_ENV=test`, placeholder keys are automatically injected to permit isolated unit tests.

---

## 3. The OpenAPI 3.1 Contract (`shared/api-schema.yaml`)

The contract defines 13 operational and analytical endpoints:
- `GET /health`: Health and version check.
- `POST /cases`: JSON submission of suspicious URLs or message lures.
- `GET /cases`: Paginated list of recent cases with status filtering.
- `POST /cases/qr`: Multipart upload of scam QR code images for server-side decoding.
- `GET /cases/{id}`: Detailed case state including `recent_events` and `streaming_url`.
- `GET /cases/{id}/events`: Incremental trace event polling.
- `GET /cases/{id}/stream`: Server-Sent Events (SSE) live progress stream.
- `GET /cases/{id}/result`: Structured investigation findings (payee, attribution, cluster, evidence hash, report drafts).
- `GET /cases/{id}/evidence`: Cryptographically signed evidence PDF download.
- `POST /evidence/verify`: Multipart verification of evidence PDF integrity.
- `POST /cases/{id}/approve-report`: Mandatory human authorization gate for dispatching complaints.
- `GET /graph/overview`: Multi-campaign Cytoscape correlation graph.
- `GET /graph/{payee_id}`: Sub-graph localized to a specific payee or mule ring.
- `GET /metrics/summary`: Executive intelligence metrics.

---

## 4. Why Redis Was Eliminated

The original plan included Redis and `arq` for job queues. In Section 01, Redis was removed in favor of PostgreSQL-backed state tracking and an in-process async worker model (`PIPELINE_RUNNER=inprocess`):
- Eliminates multi-service container crashes on local Windows laptops.
- Removes memory contention during local evaluation.
- PostgreSQL 16 provides durability, transactional isolation, and full auditability for every case event.

---

## 5. Exhaustive Section 01 Q&A

### Q1: How does a new developer set up the codebase from scratch?
1. Clone repo: `git clone https://github.com/aniketmehetre/IIITD-HACKATHON.git`
2. Copy `.env.example` to `.env` and insert your `TINYFISH_API_KEY`.
3. Start database: `docker compose up -d`.
4. Run tests: `pytest backend/tests`.
5. Launch app: `uvicorn app.main:app --app-dir backend --reload`.

### Q2: What prevents secrets from leaking into Git?
The root `.gitignore` strictly blocks `.env`, `.env.*` (except `.env.example`), `*.pdf`, and `storage/`. Testing `git add .env` confirms git refuses to track it.

### Q3: How do the mock files in `shared/mocks/` benefit the frontend team?
Frontend engineers do not need to install Python or configure Docker. Running `npx @stoplight/prism-cli mock shared/api-schema.yaml -p 8000` starts an instant mock server returning schema-validated responses for every view.

### Q4: Why is ReportLab used instead of WeasyPrint?
WeasyPrint relies on GTK, Pango, and Cairo native libraries that frequently fail to compile or install cleanly on Windows environments. ReportLab is 100% pure Python/C-wheel, installs seamlessly on Windows, and has zero HTML-fetch attack surface.

### Q5: What if the database goes down during an investigation?
SQLAlchemy async transactions rollback automatically upon uncaught exceptions. The app fails cleanly without corrupting the case table or leaving zombie records.

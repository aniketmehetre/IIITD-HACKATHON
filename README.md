# STING — Autonomous Scam Detection & Intelligence Pipeline

> Team **void main** · IIIT-D Hackathon

STING is a six-stage, multi-agent scam investigation pipeline powered by **TinyFish** web intelligence infrastructure. It detonates suspicious links, walks dynamic payment funnels as a synthetic victim, intercepts checkout QR codes/UPI VPAs, correlates campaign mule rings via NetworkX graphs, and auto-drafts takedown and law-enforcement complaints.

---

## Architecture Overview

```
STING Pipeline
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Intake Agent │ ──> │ Triage Agent │ ──> │ Orchestrator │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
          ┌──────────────────────────────────────┴──────────────────────────────────────┐
          │ (If domain > 365d & benign)                                                │ (Suspect)
          ▼                                                                             ▼
  [Low-Risk Done]                                                              ┌─────────────────┐
                                                                               │ Payee in Graph? │
                                                                               └────────┬────────┘
                                                         ┌──────────────────────────────┴──────────────────────────────┐
                                                         │ (Known Payee - Skip Detonate)                               │ (New Lure)
                                                         ▼                                                             ▼
                                                ┌──────────────────┐                                         ┌──────────────────┐
                                                │ Correlation Node │                                         │ Detonation Agent │
                                                └────────┬─────────┘                                         │ (TinyFish Agent) │
                                                         │                                                   └────────┬─────────┘
                                                         │                                                            │
                                                         │                                                            ▼
                                                         │                                                   ┌──────────────────┐
                                                         │                                                   │ Enrichment Agent │
                                                         │                                                   │ (QR/UPI PSP/RDAP)│
                                                         │                                                   └────────┬─────────┘
                                                         │                                                            │
                                                         └───────────────────────┬────────────────────────────────────┘
                                                                                 ▼
                                                                     ┌──────────────────────┐
                                                                     │ Correlation Agent    │ (NetworkX Graph)
                                                                     └──────────┬───────────┘
                                                                                ▼
                                                                     ┌──────────────────────┐
                                                                     │ Evidence Agent       │ (WeasyPrint PDF + SHA-256)
                                                                     └──────────┬───────────┘
                                                                                ▼
                                                                     ┌──────────────────────┐
                                                                     │ Report-Drafting Agent│ (I4C, Bank Alert, CERT-In)
                                                                     └──────────┬───────────┘
                                                                                ▼
                                                                     ┌──────────────────────┐
                                                                     │ Human Approval Guard │ (POST /cases/:id/approve-report)
                                                                     └──────────────────────┘
```

---

## Monorepo Structure

```
sting/
├── backend/            # FastAPI, TinyFish client wrapper, multi-agent pipeline
│   ├── app/
│   │   ├── main.py     # FastAPI entrypoint (GET /health, /cases, /graph)
│   │   ├── config.py   # Pydantic settings loading from .env
│   │   ├── integrations/
│   │   │   └── tinyfish.py # Unified TinyFish client (Fetch, Search, Agent, Browser)
│   │   ├── models/     # Database models (PostgreSQL/SQLAlchemy)
│   │   ├── routers/    # API routes
│   │   └── schemas/    # Pydantic data transfer schemas
│   ├── tests/          # Comprehensive test suite (1-retry, rate-limit, mocks)
│   └── pyproject.toml
├── frontend/           # Next.js UI (scaffolded, active after research phase)
├── shared/
│   └── api-schema.json # Locked API specification & schema
├── docs/               # Architecture, implementation plan, and demo scripts
├── docker-compose.yml  # PostgreSQL & Redis infrastructure
├── .env.example        # Environment variable template
├── .gitignore
└── README.md
```

---

## Quickstart

### 1. Setup Environment
```bash
# Copy environment configuration
cp .env.example .env

# Configure your TinyFish API Key in .env:
# TINYFISH_API_KEY=your_key_here
```

### 2. Start Services via Docker
```bash
docker compose up -d postgres redis
```

### 3. Run Backend Locally
```bash
# Using Python virtual environment
.\venv\Scripts\uvicorn.exe backend.app.main:app --reload --port 8000
```

### 4. Run Test Suite
```bash
.\venv\Scripts\pytest.exe -v backend/tests
```

# STING Frontend Mocking Guide

Frontend development can proceed independently without running the live Python backend or waiting for external API access. You have two options for mocking against the locked contract in `shared/api-schema.yaml`.

---

## Option 1: Dynamic OpenAPI Mock Server (Prism) — Recommended

Prism runs an OpenAPI 3.1 mock server that validates incoming requests and serves realistic dummy responses adhering to `shared/api-schema.yaml`.

### Running Prism

From the project root:

```bash
# Run mock server on port 8000
npx @stoplight/prism-cli mock shared/api-schema.yaml -p 8000
```

On Windows PowerShell:
```powershell
npx --yes @stoplight/prism-cli mock shared/api-schema.yaml -p 8000
```

Once started:
- Health check: `http://localhost:8000/health`
- Submit Case: `POST http://localhost:8000/cases` (with header `X-STING-Key: any-mock-key`)
- Poll Case: `GET http://localhost:8000/cases/{id}`
- Graph: `GET http://localhost:8000/graph/overview`

Prism automatically returns responses matching the schema and rejects requests with missing or invalid parameters.

---

## Option 2: Static JSON Mock Server

Pre-generated, schema-validated JSON fixtures reside in `shared/mocks/`. You can serve them using any lightweight HTTP server:

```bash
# Using Python's built-in HTTP server
cd shared/mocks
python -m http.server 8080
```

Or using Node:
```bash
npx serve shared/mocks -p 8080
```

### Available Static Mocks

| Mock File | Endpoint Contract | Description |
|---|---|---|
| `health.json` | `GET /health` | Basic status and version |
| `cases_post.json` | `POST /cases` | Initial response when case is ingested |
| `cases_list.json` | `GET /cases` | Recent cases list with status filters |
| `case_detail.json` | `GET /cases/{id}` | Includes live streaming URL and last 20 stage events |
| `case_events.json` | `GET /cases/{id}/events` | Incremental stage trace events for live trace UI |
| `case_result.json` | `GET /cases/{id}/result` | Extracted payee, cluster attribution, evidence hash, and drafts |
| `evidence_verify.json` | `POST /evidence/verify` | PDF seal and hash verification outcome |
| `approve_report.json` | `POST /cases/{id}/approve-report` | Confirmation of human authorization for takedown reports |
| `graph_overview.json` | `GET /graph/overview` | Cytoscape.js nodes and edges for multi-campaign network |
| `graph_payee.json` | `GET /graph/{payee_id}` | Cytoscape.js localized cluster for a specific payee |
| `metrics_summary.json` | `GET /metrics/summary` | Aggregate platform statistics and ROI counters |

---

## Contract Compliance Rule

Frontend components must not invent endpoints or fields outside `shared/api-schema.yaml`. Any change to data contracts must be proposed to the backend lead before modifying UI models.

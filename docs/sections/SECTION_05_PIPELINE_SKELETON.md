# Deep-Dive: Section 05 — Pipeline Skeleton, Stubs, Branches, SSE & Recovery

**Module:** Autonomous Investigation Pipeline Engine  
**Authors:** Team void main  
**Status:** Complete (Branch: `backend/s05-pipeline-skeleton`, Tag: `section-05-done`)  

---

## 1. Architectural Role & Objective

Section 05 constructs the end-to-end execution backbone of STING before any heavy AI agents or paid browser automation tools are integrated. By deploying a **walking skeleton** of sequential stages returning canned stub contracts (`data.stub = true`), the pipeline eliminates integration risk on day one, proves the branching decision logic, validates real-time Server-Sent Events (SSE) streaming, and guarantees that crashed worker processes can recover without repeating expensive computations.

```
                      ┌────────────────────────────────────────┐
                      │        Candidate Intake (API)          │
                      │        (POST /cases | /cases/qr)       │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │          InProcessRunner               │
                      │  (One Case = One Runner Invocation)    │
                      │  - Atomic lease claim (60s lease)      │
                      │  - Concurrency Semaphore (max: 3)      │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │              intake Stage              │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │              triage Stage              │
                      │       (Free-tier signals extract)      │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                             ┌────────────────────────┐
                             │      decide Stage      │
                             └────────────┬───────────┘
                                          │
          ┌───────────────────────────────┼───────────────────────────────┐
          │                               │                               │
          ▼ [High Risk]                   ▼ [Known Payee / Site / Cluster]▼ [No Risk]
  ┌───────────────┐              ┌──────────────────┐            ┌───────────────┐
  │  detonation   │              │   SKIP Branches  │            │ inconclusive  │
  │ (Paid Agent)  │              │ (Bypasses Agent) │            │  (Terminal)   │
  └───────┬───────┘              └────────┬─────────┘            └───────────────┘
          │                               │
          └───────────────┬───────────────┘
                          ▼
              ┌───────────────────────┐
              │   enrichment Stage    │
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │   correlation Stage   │
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │    evidence Stage     │
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │     reports Stage     │
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │  awaiting_approval    │
              │  (Human Sign-off)     │
              └───────────────────────┘
```

---

## 2. Why a Walking Skeleton First?

In typical hackathon projects, teams build individual agents in silos and attempt to stitch them together hours before submission. This almost always leads to broken state transitions, mismatched data payloads, and orchestrator deadlocks.

STING adopts the **walking skeleton** pattern:
1. **End-to-End Integrity:** The entire journey—from URL ingestion, through triage, decision branching, detonation, enrichment, correlation, evidence assembly, to takedown drafting—runs end-to-end immediately.
2. **Deterministic UI Development:** The frontend can immediately consume real-time SSE event streams (`GET /cases/{id}/stream`), poll progress (`GET /cases/{id}/events`), and inspect forensic dossiers (`GET /cases/{id}/result`).
3. **Incremental Replacement:** Sections 6 through 11 replace individual stubs one by one. If an agent fails during development, the surrounding pipeline remains rock-solid.

---

## 3. Why Asyncio + PostgreSQL Instead of Redis, Celery, or LangGraph?

Many agentic architectures default to distributed task queues (Celery, RQ, BullMQ) or agent graph orchestrators (LangGraph). We deliberately chose an explicit stage table plus `asyncio` in PostgreSQL for compelling architectural reasons:

1. **Zero State Desynchronization:** In Celery or Redis-based systems, queue state and database state diverge during unhandled restarts or container evictions. In STING, the case status, lease lock, and audit event are written in a **single atomic PostgreSQL transaction**.
2. **Minimal Infrastructure:** Hackathon deployments fail most frequently at infrastructure boundaries (e.g. Redis container crashes, queue timeouts, serialization mismatches). STING runs with a single Postgres instance.
3. **Simplicity Over Distributed Complexity:** Scam investigation funnels are fundamentally linear workflows with a few decision forks. Implementing a distributed state machine or complex circular graph for a linear pipeline introduces debugging overhead without adding user value.

> **What to tell a Judge:**
> *"We applied the principle of architectural parsimony. A scam investigation funnel is a linear sequence with an early-out decision branch. By utilizing PostgreSQL's atomic conditional updates for worker leases and asyncio tasks for concurrency, we achieved zero-dependency reliability, sub-second latency, and crash recovery with zero Redis overhead."*

---

## 4. Worker Lease Locking & Concurrency Control

To guarantee that two workers, a background task, or a resumed server instance cannot execute the same case concurrently:
1. **Atomic Lease Claim:**
   ```sql
   UPDATE cases 
   SET locked_by = 'worker-pid-uuid', lease_expires_at = NOW() + INTERVAL '60 seconds'
   WHERE id = :case_id 
     AND status NOT IN ('awaiting_approval', 'done', 'inconclusive', 'failed')
     AND (locked_by IS NULL OR lease_expires_at < NOW() OR locked_by = 'worker-pid-uuid');
   ```
2. **Lease Renewal:** Prior to executing each stage callable, the worker extends `lease_expires_at` by 60 seconds.
3. **Graceful Release:** When reaching a terminal status (`awaiting_approval`, `done`, `inconclusive`, `failed`), the lease is cleared (`locked_by = NULL`, `lease_expires_at = NULL`).

---

## 5. Restart Recovery & The Idempotency Invariant

When the service reboots, `resume_incomplete_cases()` queries PostgreSQL for all cases in non-terminal states whose leases are unassigned or expired. Each interrupted case is resumed exactly at its last recorded stage.

### The Detonation Resumption Invariant
A resumed stage must be **strictly idempotent**:
- Triage simply re-fetches free page signals or reads existing ones.
- **Detonation Caution (Section 7):** When a resumed case enters `detonation`, it must **never** start a second paid TinyFish agent run! Instead, it checks if `case.streaming_url` or a run ID is already stored and polls the active run to completion.

---

## 6. Comprehensive Q&A

### Q1: What happens if the server crashes in the middle of executing a stage?
**Answer:**
When the worker process dies, its in-memory task vanishes, but PostgreSQL retains the exact state up to the last completed stage. The dead worker's lease lock expires after 60 seconds (`lease_expires_at < NOW()`). Upon server restart, `resume_incomplete_cases()` identifies the expired lease, reclaims the case, and resumes execution seamlessly from the interrupted stage.

### Q2: How would you scale this architecture beyond a single server process?
**Answer:**
The lease locking protocol is natively distributed. Because `UPDATE cases ... WHERE locked_by IS NULL OR lease_expires_at < NOW()` is executed directly against PostgreSQL with row-level locks, multiple backend worker containers running on Kubernetes can pull from the same `cases` table without stepping on each other. When scale requires hundreds of concurrent runs, the optional `arq` runner (using Redis streams) described in Section 12 can be toggled via `PIPELINE_RUNNER=arq`.

### Q3: How does the frontend consume Server-Sent Events (SSE) vs Polling?
**Answer:**
- **Live Stream (SSE):** The frontend live console connects to `GET /cases/{id}/stream`. The server streams new `stage_event` messages in real time as they are committed to `case_events`, closing with a `terminal` event once the investigation reaches `awaiting_approval`.
- **Incremental Polling:** For mobile clients or reconnection fallbacks, `GET /cases/{id}/events?after=<event_id>` returns only events created after the given cursor, minimizing network transfer.

### Q4: What does the `stub: true` flag in stage metadata protect against?
**Answer:**
The `stub: true` metadata tag guarantees complete transparency during development and testing. It prevents developers, automated QA scripts, or demo reviewers from confusing synthetic mock findings with live intelligence extracted by real TinyFish browser automation.

### Q5: How do the `decide` stage branches conserve paid API credits?
**Answer:**
TinyFish Agent runs consume paid credits. The `decide` stage checks three early-out conditions:
1. `SKIP_KNOWN_PAYEE`: The payee was already identified in the input lure and exists in our correlation graph.
2. `SKIP_KNOWN_SITE`: The domain was detonated within the last 7 days and has confirmed attribution.
3. `SKIP_KNOWN_CLUSTER`: The visual and structural fingerprint matches an established scam syndicate.
In all three cases, the pipeline skips `detonation` entirely and jumps directly to `enrichment`, saving 100% of the detonation cost.

### Q6: [Failure Mode]: What happens if an unhandled Python exception occurs inside a stage callable?
**Answer:**
The runner catches the exception, transitions the case to `status="failed"`, records `error_reason=str(exc)`, releases the lease, and commits a `CaseEvent(kind="error")`. This ensures that a bug in an agent never leaves a case permanently stuck in a processing state or leaks database connections.

### Q7: [Judge Question]: Why did you not use LangGraph or an agentic framework like CrewAI?
**Answer:**
LangGraph and CrewAI are valuable for non-deterministic multi-agent debates. However, forensic cybercrime investigation requires **strict deterministic reproducibility, auditability, and legal chain of custody**. A scam funnel is not a debate—it is an algorithmic pipeline: Ingest -> Triage -> Decide -> Detonate -> Enrich -> Correlate -> Evidence. Implementing this via explicit state machines and async callables gives us complete control over retries, leases, and database transactions without black-box framework abstractions.

---

## 7. Verification & Test Metrics

- **Unit & Integration Tests:** 9 comprehensive test scenarios covering happy path, 4 decision branches, exception failures, lease locks, lease takeover, restart recovery, SSE streaming, and result endpoints.
- **Full Test Suite:** 47 passed in 2.97s across the entire project.
- **Linter & Formatting:** 100% clean under `ruff check` and `ruff format`.

---

## 8. 60-Second Demo Script

1. **Start SSE Live Stream:**
   ```bash
   curl -N http://localhost:8000/cases/<case_id>/stream
   ```
   *Observe:* Emits real-time `stage_event` JSON events as each pipeline stage completes.

2. **Trigger Case Execution via Ingestion:**
   ```bash
   curl -X POST http://localhost:8000/cases \
     -H "Content-Type: application/json" \
     -H "X-STING-Key: test-key" \
     -d '{"input_type":"link","raw_input":"https://fake-recharge.biz/claim"}'
   ```
   *Observe:* Stream shows `intake` -> `triage` -> `decide` -> `detonation` -> `enrichment` -> `correlation` -> `evidence` -> `reports` -> `awaiting_approval`.

3. **Inspect Completed Dossier:**
   ```bash
   curl http://localhost:8000/cases/<case_id>/result
   ```
   *Observe:* Returns structured `InvestigationResult` with payee, cluster, evidence hash, and drafted takedown complaints.

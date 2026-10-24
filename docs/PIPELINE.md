# STING Pipeline Architecture & State Machine

**Module:** Autonomous Investigation Orchestration Engine  
**Authors:** Team void main  

---

## 1. Overview & Core Philosophy

STING is structured as a **linear stage pipeline with conditional branch points**. It intentionally avoids distributed actor frameworks (e.g. Celery, Redis, LangGraph, arq) in the core build to eliminate distributed race conditions, minimize external infrastructure, and guarantee that pipeline state survives process crashes without state desynchronization.

### Core Invariant: One Case = One Runner Invocation
Each case is claimed and executed by a single runner task from intake through all sequential stages. Stages never enqueue other stages asynchronously; state is persistently advanced in PostgreSQL within atomic transactions.

---

## 2. Mermaid State Transition Diagram

```mermaid
stateDiagram-v2
    [*] --> intake: POST /cases or /cases/qr

    intake --> triage: Intake Verified

    triage --> decide: Signals Extracted (RDAP, DOM, Brand)

    state decide <<choice>>
    decide --> detonation: DETONATE (Suspicious / High Risk)
    decide --> enrichment: SKIP_KNOWN_PAYEE (Payee already known)
    decide --> enrichment: SKIP_KNOWN_SITE (Domain seen recently)
    decide --> enrichment: SKIP_KNOWN_CLUSTER (Strong fingerprint match)
    decide --> inconclusive: INCONCLUSIVE (Benign / no threat indicators)

    detonation --> enrichment: Payment Destination Captured
    enrichment --> correlation: Bank, PSP & IFSC Resolved
    correlation --> evidence: Graph Cluster Formed
    evidence --> reports: Signed Forensic PDF Sealed
    reports --> awaiting_approval: Takedown Letters Drafted

    awaiting_approval --> done: Human Analyst Approves (/cases/{id}/approve-report)
    awaiting_approval --> failed: Rejected / Blocked

    inconclusive --> [*]
    done --> [*]
    failed --> [*]

    note right of decide
        Decision logic evaluates free-tier
        signals first to minimize paid TinyFish credits.
    end note

    note right of awaiting_approval
        Zero external actions dispatched
        without explicit human approval.
    end note
```

---

## 3. Worker Lease Locking Protocol

To prevent two concurrent workers, a resumed worker, or a retrying process from executing the same case simultaneously, STING uses an **atomic database lease lock**:

```mermaid
sequenceDiagram
    participant Worker as InProcessRunner (Worker)
    participant DB as PostgreSQL (cases table)
    participant Events as PostgreSQL (case_events)

    Worker->>DB: Atomic Claim: UPDATE cases SET locked_by='worker-pid-uuid', lease_expires_at=NOW()+60s WHERE id=case_id AND status NOT IN ('awaiting_approval', 'done', 'inconclusive', 'failed') AND (locked_by IS NULL OR lease_expires_at < NOW())
    DB-->>Worker: Returning 1 row (Claim Success)

    loop For Each Pipeline Stage
        Worker->>DB: Renew Lease: UPDATE cases SET lease_expires_at=NOW()+60s WHERE id=case_id AND locked_by='worker-pid-uuid'
        Worker->>Worker: Execute Stage Callable (with timeout)
        Worker->>DB: Advance Status: UPDATE cases SET status=next_stage, current_stage=next_stage
        Worker->>Events: Append Audit Event: INSERT INTO case_events (stage, kind, message, data)
        Note over DB,Events: Single Transaction Commit
    end

    Worker->>DB: Finalize & Release Lease: UPDATE cases SET locked_by=NULL, lease_expires_at=NULL, status='awaiting_approval'
```

---

## 4. Restart Recovery

When the STING backend restarts after a reboot or container crash:
1. `resume_incomplete_cases()` is invoked during application startup (`lifespan`).
2. It queries for all cases where `status NOT IN ('awaiting_approval', 'done', 'inconclusive', 'failed')` and `(locked_by IS NULL OR lease_expires_at < NOW())`.
3. Interrupted cases are picked up exactly at their current recorded stage.
4. All stages are strictly idempotent: re-executing a stage replaces temporary values and continues seamlessly.

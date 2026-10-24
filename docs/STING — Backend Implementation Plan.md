# STING — Backend Implementation Plan

Team void main · Sequential, Antigravity-ready build plan — 10 sections, each with a copy-pasteable prompt, a plain-language explanation, and a Q&A recap

This is the backend track only. Per the sequencing locked in the architecture doc, backend work starts now; frontend implementation is paused at the scaffold-preview stage until the reference/ideas research pass is done. Work through these sections in order — each depends on the ones before it, and each should land as its own commit (see the suggested commit messages) so the combined 25-commit target is hit without padding.

---

## Section 1 — Project scaffold, env, TinyFish client setup

**Antigravity prompt:**

```
Scaffold a FastAPI backend for a project called STING inside backend/. Use Python 3.11, Poetry for dependency management, structured as:

backend/
  app/
    main.py (FastAPI app entrypoint)
    config.py (pydantic Settings loading from .env)
    integrations/
      tinyfish.py (TinyFish API client wrapper)
    models/ (empty for now)
    routers/ (empty for now)
  tests/
  pyproject.toml
  .env.example

In config.py define a Settings class (pydantic-settings) with TINYFISH_API_KEY, TINYFISH_BASE_URL, DATABASE_URL, REDIS_URL, read from environment variables.

In integrations/tinyfish.py build a TinyFishClient class with async methods fetch(url), search(query), run_agent(payload), browser_session(url). Each method reads the key from Settings, calls out via httpx (async), retries once on timeout or 5xx, raises a custom TinyFishError after the retry fails, and returns parsed JSON. Never hardcode the API key.

Add .env.example with the four variable names (no values) and confirm .env is in .gitignore.

Add a GET /health endpoint in main.py returning a simple status-ok JSON response.

Write tests/test_tinyfish.py: mock httpx, confirm TinyFishClient.fetch() retries once on a 500 before raising TinyFishError.
```

**What this does:** everything downstream depends on this section. It gives you one place where TinyFish calls happen (so frontend and other agents never touch the raw API or the key directly), a fail-fast config system (the app won't start with a missing key instead of failing silently mid-demo), and a retry/error pattern baked in before any real feature code exists.

**Q&A**

- **Why wrap TinyFish calls in one client class instead of calling the API directly from each agent?** One seam means one place to change retry logic, swap base URLs, or add logging — and it's the only file that needs to know the API key exists.
- **Why retry only once, not three or five times?** A live demo needs predictable latency. Aggressive retries hide real outages behind long hangs; one retry catches transient blips without stalling a case.
- **What happens if TINYFISH\_API\_KEY is missing?** pydantic-settings fails at startup, not mid-request — you find out before the demo, not during it.

**Suggested commits:** backend: scaffold FastAPI app + config · backend: add TinyFish client wrapper with retry · backend: add .env.example, gitignore, health check

---

## Section 2 — Intake Agent + case model (PostgreSQL)

**Antigravity prompt:**

```
Add PostgreSQL via SQLAlchemy (async) and Alembic migrations to the backend.

In app/models/case.py define a Case model: id (UUID), input_type (enum: link, qr_image, message), raw_input (text), status (enum: intake, triage, detonating, enriching, clustering, awaiting_approval, done, failed), current_stage (text), created_at, updated_at.

In app/routers/cases.py add POST /cases: accepts input_type and raw_input, creates a Case row with status=intake, returns the case id and status. Add GET /cases/{id}: returns the case's current status, current_stage, and (once done) a placeholder result field.

Write an Alembic migration for the Case table.

Add tests/test_cases.py covering: creating a case returns a valid UUID and status of intake; fetching an unknown case id returns a 404.
```

**What this does:** this is the Intake Agent in its simplest form — it doesn't need TinyFish yet, it just needs to durably record that a case exists and answer 'what's its status' for polling, which is exactly the GET /cases/:id contract already locked in the architecture doc.

**Q&A**

- **Why a status enum instead of a free-text field?** The orchestrator (Section 10) will branch on this value. An enum catches a typo'd status at write time instead of silently breaking a later stage's lookup.
- **Why return a case id immediately instead of waiting for triage to finish?** The frontend needs something to poll against right away; case creation and case processing are decoupled on purpose.
- **Why Alembic instead of just letting SQLAlchemy create tables?** A real migration history is something a judge can look at in the repo, and it lets you change the schema later without dropping data.

**Suggested commits:** backend: add Case model + Alembic migration · backend: add POST/GET /cases endpoints

---

## Section 3 — Triage Agent (Fetch/Search, RDAP)

**Antigravity prompt:**

```
Add app/agents/triage.py with a function triage_case(case) returning a TriageResult.

TriageResult is a dataclass with: brand_match (string or none), domain_age_days (int or none), known_campaign (bool), should_detonate (bool), reasoning (string).

triage_case should: call TinyFishClient.fetch() to render the page, call TinyFishClient.search() with the extracted page title or brand to check for known-campaign matches, and do an RDAP lookup (use the rdap or whoisit library) on the domain to get domain_age_days. should_detonate is True unless the domain is older than 365 days AND no brand mismatch is found AND no known_campaign match — in that case it's False (likely legitimate) and the case should be marked done with a low-risk verdict instead of proceeding to detonation.

Wire this into the case flow: add a background task (FastAPI BackgroundTasks for now, Redis queue comes in Section 4) that runs triage_case after case creation and updates Case.status to either detonating or done based on should_detonate.

Add tests/test_triage.py mocking TinyFishClient and the RDAP lookup, covering both the should_detonate true and false paths.
```

**What this does:** this is the free-tier gate from the architecture doc — it's the component that decides whether a case is worth spending a paid Detonation Agent run on, using only free Fetch/Search calls and RDAP. Getting this right is what keeps your TinyFish bill low during the hackathon.

**Q&A**

- **Why RDAP instead of a generic WHOIS scrape?** RDAP returns structured JSON with a stable schema; WHOIS output format varies by registrar and is painful to parse reliably under time pressure.
- **What happens to a case that triage marks as not worth detonating?** It's marked done with a low-risk verdict — a real, demoable outcome, not a dead end, and worth showing to prove the free-tier gate actually works.
- **Why a dataclass for TriageResult instead of a plain dict?** Type-checked fields catch a missing or renamed key at development time instead of as a runtime error during the demo.

**Suggested commits:** backend: add Triage Agent (Fetch/Search/RDAP) · backend: wire triage into case creation flow

---

## Section 4 — Redis job queue + async run orchestration

**Antigravity prompt:**

```
Add Redis via redis-py (async) and a simple job queue using arq (or rq if arq isn't available) to replace the FastAPI BackgroundTasks from Section 3.

Add app/queue.py: defines the arq worker settings (Redis connection from Settings.REDIS_URL) and a function enqueue_case(case_id, job_name) that pushes a job.

Move triage_case into an arq-compatible task function run_triage(ctx, case_id). On POST /cases, after creating the Case row, call enqueue_case with the new case id and run_triage instead of using BackgroundTasks directly.

Add a Redis service (redis:7-alpine) to docker-compose.yml if not already present from the earlier repo scaffold.

Add a simple way to run the worker locally (a worker.py entrypoint or arq CLI command, documented in backend/README.md).

Add tests/test_queue.py that enqueues a fake job against a test Redis instance (or a mocked connection) and confirms it's picked up.
```

**What this does:** this is what lets Detonation Agent runs (Section 5 onward) happen asynchronously and in parallel instead of blocking the API while a TinyFish Agent session plays out, which can take real time. It's also what the Correlation Agent (Section 7) will hook into later to skip a redundant run.

**Q&A**

- **Why Redis/arq instead of just more BackgroundTasks?** BackgroundTasks run in-process and die if the server restarts mid-task; a real queue survives restarts and lets you run several cases in parallel without blocking the API.
- **Why dockerize Redis now instead of later?** Getting the full docker-compose stack running early means the first time you test the whole pipeline together isn't the night before the demo.
- **What if the worker crashes mid-run?** arq jobs are re-queued on failure up to a configurable retry count — worth setting that explicitly rather than relying on the default.

**Suggested commits:** backend: add Redis + arq job queue · backend: move triage to async job · backend: add Redis to docker-compose

---

## Section 5 — Detonation Agent (TinyFish Agent API)

**Antigravity prompt:**

```
Add app/agents/detonation.py with an arq task run_detonation(ctx, case_id).

It should: load the Case, call TinyFishClient.run_agent() with a payload instructing the agent to open the case's link as a mobile user on an India proxy, walk the funnel as a synthetic victim, fill forms with dummy data only, and stop at the payment screen. The payload must include a stealth profile flag and must never include real payment details.

Parse the TinyFish Agent response into a DetonationResult dataclass: payee_upi (string or none), bank_account (string or none), wallet (string or none), qr_payload (string or none), redirect_chain (list of URLs), screenshots (list of blob references).

Store the result on the Case row (a JSON column detonation_result is fine) and update status to enriching. On TinyFishError, retry the whole detonation once via the queue, then mark the case failed with a clear reason string.

Add tests/test_detonation.py mocking TinyFishClient.run_agent and covering: a successful run populates DetonationResult, and a failed run after retry marks the case as failed.
```

**What this does:** this is the core of the whole product — the synthetic-victim run that extracts a payee instead of just a verdict. Everything in Sections 1 through 4 exists to support this one call safely and cheaply.

**Q&A**

- **Why stop at the payment screen instead of going further?** That's the guardrail from the project's legal basis — nothing is ever paid, so there's no point at which real money or real data could move.
- **Why store the raw result as JSON instead of fully normalizing it into its own tables right away?** Speed for the hackathon — you get a working pipeline faster, and you can normalize later if time allows without blocking Sections 6 to 10.
- **What if TinyFish's Agent API can't complete the funnel (site changed, funnel broke)?** It's marked failed with a reason, not silently stuck — that's a real, explainable state for the demo if a live site misbehaves.

**Suggested commits:** backend: add Detonation Agent + TinyFish Agent API call · backend: add detonation result storage + failure handling

---

## Section 6 — Enrichment Agent (QR decode, UPI/PSP, wallets)

**Antigravity prompt:**

```
Add app/agents/enrichment.py with an arq task run_enrichment(ctx, case_id).

It should: load the Case's detonation_result. If qr_payload is present, decode it with pyzbar if it's an image reference, or parse it directly if it's already text. If payee_upi is present, resolve the UPI handle's PSP (payment service provider) suffix to a human-readable bank/provider name using a static lookup table of common Indian UPI handle suffixes. If wallet is present, do a basic lookup against a public block explorer API for that chain.

Store an EnrichmentResult (psp_name, qr_decoded_payload, wallet_chain, wallet_balance_hint) back on the Case row and update status to clustering.

Add tests/test_enrichment.py covering: UPI handle to PSP name resolution with a few known suffixes, and QR decode from a sample payload.
```

**What this does:** this turns raw identifiers from the Detonation Agent into something a bank fraud team or cyber cell can actually act on — a named PSP instead of a bare handle, a decoded QR instead of a blob.

**Q&A**

- **Why a static lookup table for PSP suffixes instead of calling an external API?** It's fast, free, and the handle-to-PSP mapping for major Indian providers doesn't change often — good tradeoff for a hackathon timeline.
- **What happens if the wallet lookup fails or the chain is unrecognized?** wallet\_chain and wallet\_balance\_hint stay null — the case still proceeds with whatever identifiers were resolved.
- **Why decode the QR here instead of during Detonation?** Separation of concerns — Detonation's job is capturing raw data under time pressure from a live site; Enrichment's job is making sense of it afterward, with no live-site time pressure.

**Suggested commits:** backend: add Enrichment Agent (QR decode, UPI/PSP lookup) · backend: add wallet lookup + enrichment storage

---

## Section 7 — Correlation Agent (networkx payee graph)

**Antigravity prompt:**

```
Add app/agents/correlation.py with a CampaignGraph class wrapping a networkx graph, persisted to PostgreSQL as a simple edge list table (payee_id, site_domain, case_id, first_seen).

Add a function check_known_payee(payee_upi) -> bool used by the orchestrator before enqueuing a Detonation run — if the payee_upi already exists in the graph, skip detonation and reuse the existing case's result.

Add a function add_case_to_graph(case) that, after enrichment completes, adds a node for the payee and an edge to the case's site domain, then updates Case.status to awaiting_approval.

Add GET /graph/{payee_id} per the API contract: returns the campaign graph for a known payee (list of connected site domains and case ids) as JSON, shaped for Cytoscape.js to consume directly.

Add tests/test_correlation.py covering: a new payee creates a new graph node, a repeat payee is correctly detected by check_known_payee, and GET /graph/{payee_id} returns the expected shape.
```

**What this does:** this is the project's actual differentiator — the thing that makes a second site sharing a known payee essentially free to flag, and it's what the orchestrator (Section 10) checks before ever spending a paid Detonation run.

**Q&A**

- **Why persist the graph to PostgreSQL instead of keeping it in memory?** The worker process could restart; a graph that resets on restart loses every correlation you've built so far, including mid-demo.
- **Why shape GET /graph/:id for Cytoscape.js specifically?** The frontend's Cluster panel (Section 8 of the frontend plan) uses Cytoscape.js directly — matching its expected node/edge shape avoids a transform step on either side.
- **What counts as 'the same payee' for a graph match?** Exact match on the resolved payee\_upi (and ideally bank\_account/wallet too) — worth being explicit about this if a judge asks, since fuzzy matching is a real but out-of-scope extension.

**Suggested commits:** backend: add Correlation Agent + payee graph model · backend: add GET /graph/:id endpoint

---

## Section 8 — Evidence Agent (WeasyPrint, SHA-256 hashing)

**Antigravity prompt:**

```
Add app/agents/evidence.py with a function build_evidence_pdf(case) -> EvidenceFile.

It should render an HTML template (Jinja2) containing: the case's redirect chain, screenshots, payee details, enrichment results, and a timestamp, then convert it to PDF with WeasyPrint. Compute a SHA-256 hash of the resulting PDF bytes and store both the PDF (to local disk or object storage, your choice) and its hash on the Case row.

Add GET /cases/{id}/result per the API contract: returns the final payee, graph summary, and a link to the evidence PDF (plus its hash) once status is awaiting_approval or later.

Add tests/test_evidence.py covering: PDF generation produces non-empty bytes, and the stored hash matches a fresh hash of the stored file.
```

**What this does:** this is what makes STING's output usable as actual evidence rather than just a UI screen — a hashed, timestamped PDF is what gives a bank or cyber cell something with chain-of-custody integrity, which ties directly back to the legal-basis section of the project doc.

**Q&A**

- **Why hash the PDF at all?** It proves the evidence wasn't altered after generation — a judge or a bank's legal team can verify the hash matches what was originally produced.
- **Why WeasyPrint instead of a headless-browser PDF export?** WeasyPrint is deterministic and lightweight for a template-driven document like this — no browser process to manage, and consistent output every run.
- **What goes in the PDF if a field (like wallet) is null?** Render it as 'not applicable' rather than omitting the row — a consistent template is easier to explain and easier to re-verify than one whose shape changes per case.

**Suggested commits:** backend: add Evidence Agent (WeasyPrint + SHA-256) · backend: add GET /cases/:id/result endpoint

---

## Section 9 — Report-Drafting Agent + human-approval endpoint

**Antigravity prompt:**

```
Add app/agents/report_draft.py with a function draft_reports(case) -> ReportDraft.

ReportDraft contains: i4c_report_text (plain-language summary for the National Cyber Crime Reporting Portal), bank_alert_payload (structured JSON for a bank webhook), cert_in_payload (structured JSON for infrastructure takedown). These are drafts only — nothing is ever sent automatically.

Add POST /cases/{id}/approve-report per the API contract: requires an explicit approved: true in the request body, and only then marks the case's reports as submitted (for the hackathon, 'submitted' can just mean logged/stored, not actually sent to a live external system) and sets Case.status to done. Without approved: true, return a 400.

Add tests/test_report_draft.py covering: a draft is generated correctly from a completed case, and POST /cases/{id}/approve-report without approved: true is rejected.
```

**What this does:** this is the human-in-the-loop guardrail made concrete in code — the exact mechanism that backs the 'no identifier is ever made public without explicit approval' line from the project's legal-basis section, so it's worth being able to point directly at this endpoint if a judge asks how that guardrail is actually enforced, not just claimed.

**Q&A**

- **Why require a literal approved: true instead of just hitting the endpoint?** It removes ambiguity — a bare POST can't accidentally submit a report; the approval has to be an explicit, unmistakable action.
- **Why draft three separate report formats instead of one generic one?** I4C, bank nodal officers, and CERT-In expect different shapes — drafting for the actual destination format is what makes 'pre-filled takedown reports' a real claim rather than a slide bullet.
- **Does this ever actually send anything externally?** Not for the hackathon build — submission is logged/stored only, which is both honest about scope and avoids needing real integration credentials for a demo.

**Suggested commits:** backend: add Report-Drafting Agent · backend: add POST /cases/:id/approve-report endpoint

---

## Section 10 — Orchestrator (LangGraph state machine)

**Antigravity prompt:**

```
Add app/orchestrator.py using LangGraph to define a state graph tying Sections 2 through 9 together: intake -> triage -> (conditional: done if should_detonate is False) -> check_known_payee (Correlation Agent) -> (conditional: skip straight to clustering if a known payee match is found) -> detonation -> enrichment -> correlation -> evidence -> report_draft -> awaiting_approval.

Each node in the graph should be a thin wrapper around the agent functions already built in Sections 3, 5, 6, 7, 8, and 9 — the orchestrator's job is only sequencing and the two conditional branches (should_detonate, known-payee skip), not reimplementing any agent logic.

Replace the manual enqueue_case calls scattered across earlier sections with a single entry point: on POST /cases, after the Case row is created, call orchestrator.start(case_id), which enqueues the graph's first step onto the Redis queue from Section 4.

Add tests/test_orchestrator.py covering: a full happy-path run through every node with all agents mocked, the should_detonate=False early-exit path, and the known-payee skip path.
```

**What this does:** this is the single coordination point the whole architecture doc was built around — the thing that decides, for every case, whether a fresh paid Detonation run is actually needed or whether the Correlation Agent's graph already covers it. With this section done, the backend's core pipeline is complete end to end.

**Q&A**

- **Why LangGraph instead of just a sequence of function calls?** The two conditional branches (low-risk early exit, known-payee skip) make this a real state machine, not a straight line — LangGraph makes those branches explicit and inspectable rather than buried in if-statements across files.
- **Why did earlier sections wire their own enqueue calls if the orchestrator was always going to own this?** Building each agent as a standalone, testable function first (Sections 3, 5 to 9) and only wiring them into a single flow at the end keeps every section independently demoable if something upstream isn't finished yet.
- **What's the actual backend deliverable after this section?** A working POST /cases that, for a real link, runs the full pipeline through to an awaiting\_approval case with a payee, a graph, and an evidence PDF — the whole backend half of the demo.

**Suggested commits:** backend: add LangGraph orchestrator · backend: wire orchestrator into POST /cases · backend: add orchestrator integration tests

---

## What's next

That's the full backend track — 10 sections, each independently testable and committable, landing comfortably past the 25-commit combined target once frontend sections are added later. When the reference/ideas research pass for the frontend wraps, send the findings over and the frontend implementation plan picks up the same way: one section at a time, each with its own Antigravity prompt, explanation, and Q&A, building against the `shared/api-schema.json` contract this backend plan implements end to end.

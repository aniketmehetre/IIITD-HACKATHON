# STING — Architecture & Repo Plan

Team void main (Amogh, Aniket) · Pre-implementation structure document

This document covers structure and architecture only. The section-by-section, Antigravity-ready implementation plan — with sequential prompts and a Q&A after every section — follows in a separate response, built on top of what's laid out here.

---

## 1. Why this document exists

Before either of you writes a line of code, three things need to be nailed down once so they never cause friction later: how TinyFish plugs into the pipeline, how the repo is structured so backend work and the frontend's research phase never collide, and what the exact contract between frontend and backend is. Backend development starts immediately after the TinyFish setup in Section 3. The frontend owner spends this same window researching references and locking the visual direction rather than writing code, and picks up implementation only once that phase is done, building straight against the contract locked in Section 5 — so nothing gets reworked when frontend coding starts. Get these three right and commit history stays clean throughout.

---

## 2. System architecture (recap, with TinyFish wired in)

Six stages, seven agents, one orchestrator — as established in the project context doc. Here's where TinyFish specifically sits:

| Stage | Agent | TinyFish surface used |
| --- | --- | --- |
| Intake | Intake Agent | none |
| Triage | Triage Agent | Fetch + Search (free tier) |
| Detonate | Detonation Agent | Agent API (paid, core capability) |
| Enrich | Enrichment Agent | Browser API (redirect chain, screenshots) |
| Cluster | Correlation Agent | none (networkx, internal) |
| Act | Evidence Agent, Report-Drafting Agent | Fetch (scheduled re-checks) |

The orchestrator (LangGraph-based) is the only component that decides whether a case needs a fresh TinyFish Agent API call or whether the Correlation Agent's graph already has the payee. This is the single most important architectural decision point in the whole system: it's what keeps paid API usage low and what keeps the demo fast.

---

## 3. TinyFish API — setup plan (do this first, before any feature code)

This has to be step one because every backend section depends on it being in place.

1. **Account and key provisioning.** One of you creates the TinyFish account and generates the API key. Store it only in a `.env` file, never committed — add `.env` to `.gitignore` in the very first commit, before the key ever touches the repo.
2. **Shared `.env.example`.** Commit a `.env.example` with every variable name but no real values (`TINYFISH_API_KEY=`, `TINYFISH_BASE_URL=`, etc.) so the other teammate can set up their own `.env` without ever seeing or needing the real key.
3. **A single TinyFish client wrapper.** All Fetch, Search, Agent, and Browser API calls go through one wrapper module (`backend/app/integrations/tinyfish.py` or equivalent), not scattered raw HTTP calls. This is a backend-owned file — frontend never touches it directly, only calls your own backend endpoints.
4. **Free-tier-first verification.** Before writing any Detonation logic, confirm Fetch and Search work end-to-end against a real or mock URL. This is a cheap, fast way to validate the API key and account setup without burning paid Agent API calls.
5. **Rate-limit and failure handling baked in from the start.** Decide now (not mid-build) what happens when TinyFish rate-limits or errors out — retry once, then surface a clear error to the orchestrator. This avoids a late scramble when it inevitably happens during the live demo.

This setup is Section 1 of the backend implementation plan in the next response.

---

## 4. Repository and branching strategy

**Structure: one monorepo, not two separate repos.** With a two-person team and a shared API contract, a monorepo keeps the schema, docs, and both codebases in sync in one place and avoids "which repo's README is current" confusion during judging.

```
sting/
├── backend/ # Amogh or Aniket — FastAPI, agents, TinyFish integration (active now)
├── frontend/ # the other — Next.js, scroll UI, graph view (scaffold only until research phase ends)
├── shared/ # API schema (OpenAPI/JSON schema), shared types
├── docs/ # this doc, the project context doc, demo script
├── docker-compose.yml
├── .env.example
└── README.md
```

**Branching model:**

- `main` — always demoable. Never commit broken code directly here.
- `backend/*` and `frontend/*` prefix branches — one owner per branch, e.g. `backend/detonation-agent`, `frontend/scroll-setup`.
- Merge to `main` via PR, even solo — this is what gives you a clean, reviewable commit history instead of one giant squash, and naturally helps you hit the 25-commit target without padding.
- **Nobody touches the other person's folder.** Backend owns `backend/`, frontend owns `frontend/`. The only shared-touch zone is `shared/`, and changes there should be flagged to the other person before merging, since both of you depend on it.
- No `frontend/*` branches open until the research phase wraps — only `backend/*` branches are active for now.

**Why this avoids collisions:** the two of you are working in entirely separate directory trees except for `shared/`. Git conflicts mostly happen when two people edit the same file — this structure makes that structurally rare rather than relying on communication alone.

---

## 5. The frontend/backend contract (lock this before building either side)

The fastest way for a two-person hackathon team to lose a day is for frontend to build against an assumed API shape that backend changes later. Fix this by defining the contract first, as a file in `shared/`, before either of you writes feature code:

```
// shared/api-schema.json (abbreviated)
POST /cases — create a case (link, QR image, or message)
GET /cases/:id — poll case status + current stage
GET /cases/:id/result — final payee, graph, evidence links
GET /graph/:payee_id — campaign graph for a known payee
POST /cases/:id/approve-report — human approval step
```

Both of you sign off on this shape in the first hour. After that:

- **Backend** builds against this contract and can mock responses with static JSON before any agent logic is real, so frontend is never blocked waiting for working agents.
- **Frontend** builds against the same mocked JSON once the research phase wraps and implementation begins, swapping in the real backend URL once both sides are stable. Because the contract is locked now, frontend can start coding later without reworking anything — the delay is intentional, not a blocked dependency.

Any change to this contract after hour one must be a flagged, explicit conversation between both of you — not a silent edit.

---

## 6. Commit strategy (hitting 25+ meaningful commits)

Don't pad commits artificially — judges and graders can tell, and GitHub shows timestamps. Instead, structure the work so meaningful commits happen naturally at this granularity:

- One commit per section (see breakdowns below), not one commit per whole stage. A section like "TinyFish client wrapper" is one commit; "Detonation Agent" might be two or three (initial scaffold, core logic, error handling).
- Commit messages follow a simple convention: `backend: add TinyFish Fetch/Search wrapper`, `frontend: wire Lenis scroll container`. This alone makes a 25-commit history read as organized progress rather than noise.
- With roughly 10 backend sections and 10 frontend sections (detailed in the next response), landing 1 to 2 commits per section comfortably clears 25 combined commits without anyone needing to artificially split work. Early commits will skew backend-heavy since frontend coding starts later — that's expected, not a gap to fill artificially.

---

## 7. Backend section breakdown (preview — full prompts come in the next response)

| # | Section | Depends on |
| --- | --- | --- |
| 1 | Project scaffold, env, TinyFish client setup | — |
| 2 | Intake Agent + case model (PostgreSQL) | 1 |
| 3 | Triage Agent (Fetch/Search, RDAP) | 1 |
| 4 | Redis job queue + async run orchestration | 1 |
| 5 | Detonation Agent (TinyFish Agent API) | 1, 4 |
| 6 | Enrichment Agent (QR decode, UPI/PSP, wallets) | 5 |
| 7 | Correlation Agent (networkx payee graph) | 6 |
| 8 | Evidence Agent (WeasyPrint, SHA-256 hashing) | 6, 7 |
| 9 | Report-Drafting Agent + human-approval endpoint | 8 |
| 10 | Orchestrator (LangGraph state machine tying 1–9 together) | all above |

Each of these becomes its own numbered section in the implementation response, and each one ends with a short Q&A recap before moving to the next — so you always understand what was just built and why before stacking the next piece on top.

---

## 8. Frontend section breakdown (preview — picked up once research phase is done)

| # | Section | Depends on |
| --- | --- | --- |
| 1 | Project scaffold (Next.js, Lenis install) | — |
| 2 | Mocked API client against `shared/api-schema.json` | — |
| 3 | Opening live-trace panel (anime.js / motion.dev) | 1 |
| 4 | Lenis scroll container + stage-panel shell | 1 |
| 5 | Stage 1–2 panels: Intake, Triage | 2, 4 |
| 6 | Stage 3 panel: Detonate (browser-mock visual) | 4 |
| 7 | Stage 4 panel: Enrich | 4 |
| 8 | Stage 5 panel: Cluster (Cytoscape.js graph view) | 4 |
| 9 | Stage 6 panel: Act (evidence card reveal) | 4 |
| 10 | Swap mocked client for real backend + end-to-end wiring | all above, backend §10 |

---

## 9. What's next

The next response picks this up with backend Section 1 only (TinyFish setup), delivered as a sequential, Antigravity-ready prompt with a short explanation-and-Q&A pass before moving to backend Section 2. Frontend implementation stays paused at the scaffold-preview stage until the research/ideas phase is done — once it is, frontend Section 1 picks up the same way, building straight against the contract locked in Section 5.

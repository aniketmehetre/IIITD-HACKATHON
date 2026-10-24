# Deep-Dive: Section 06 — Triage Signals, Page Fingerprinting, and Decision Logic

**Module:** Free-Tier Intelligence, Infrastructure Fingerprinting & Autonomous Detonation Gating  
**Authors:** Team void main  
**Status:** Complete (Branch: `backend/s06-triage-decision`, Tag: `section-06-done`)  

---

## 1. Architectural Role & Objective

The **Triage & Decision Engine** is STING's economic and forensic firewall. Autonomous browser execution (detonation) via TinyFish Agent is a paid, resource-heavy operation (~$0.02 – $0.05 per multi-step browser walk). Running paid detonations indiscriminately on every submitted URL or benign site would rapidly exhaust incident response budgets and create an unmonitored denial-of-wallet vulnerability.

Section 06 establishes a **Free-First Gating Layer** that operates strictly on zero-cost external surfaces:
1. **TinyFish Fetch & Search (Free Tier):** Extracts raw HTML DOM, meta titles, visible copy, payment cues, script hosts, form action targets, and web reputation.
2. **Registration Data Access Protocol (RDAP - RFC 7482/7483):** Resolves registrar identity, registration timestamp, domain age in days, and authoritative nameserver delegations without native C library dependencies.
3. **Curated Brand Impersonation Matrix (`data/brands.yaml`):** Flags brand impersonation when official brand keywords appear on non-authoritative domains across 25 curated Indian financial, telecom, utility, and governmental entities.
4. **64-bit Charikar Simhash & Infrastructure Fingerprinting:** Generates locality-sensitive lexical hashes and infrastructure fingerprints to cluster copycat campaign kits.
5. **Deterministic Decision Engine:** Evaluates ordered rules (1 to 6) without probabilistic LLM ambiguity, providing explainable routing to `DETONATE`, `SKIP_KNOWN_PAYEE`, `SKIP_KNOWN_SITE`, `SKIP_KNOWN_CLUSTER`, or `INCONCLUSIVE`.

```
                        ┌────────────────────────────────────────┐
                        │         Normalized Intake URL          │
                        │      (from intake verification)        │
                        └───────────────────┬────────────────────┘
                                            │
                                            ▼
                        ┌────────────────────────────────────────┐
                        │             stage_triage               │
                        │  Zero paid calls; free heuristics only │
                        └─────────┬────────────────────┬─────────┘
                                  │                    │
        ┌─────────────────────────┴────────┐   ┌───────┴────────────────────────┐
        │        Domain Intelligence       │   │       Content & DOM Analysis   │
        │  - HTTP RDAP (RFC 7482/7483)     │   │  - Free-tier HTML extraction   │
        │  - Domain age, registrar, NS     │   │  - Brand mismatch check        │
        │  - TinyFish Search reputation    │   │  - Payment / urgency cues      │
        └─────────────────────────┬────────┘   └───────┬────────────────────────┘
                                  │                    │
                                  └─────────┬──────────┘
                                            ▼
                        ┌────────────────────────────────────────┐
                        │       Fingerprint & Signals Object     │
                        │  - 64-bit Simhash of visible text      │
                        │  - Form actions, script hosts, NS set  │
                        │  - Multi-group atomic forensic signals │
                        └───────────────────┬────────────────────┘
                                            │
                                            ▼
                        ┌────────────────────────────────────────┐
                        │             stage_decide               │
                        │    Deterministic Ordered Rules 1 - 6   │
                        └───────────────────┬────────────────────┘
                                            │
            ┌───────────────────────────────┼───────────────────────────────┐
            │                               │                               │
            ▼                               ▼                               ▼
    [Rule 1 / 6]                     [Rules 2, 3, 4]                    [Rule 5]
┌──────────────────────┐        ┌─────────────────────────┐     ┌───────────────────────┐
│       DETONATE       │        │      SKIP Branches      │     │     INCONCLUSIVE      │
│  Proceed to paid run │        │  Reuse known payee or   │     │ "Not detonated"       │
│  (tinyfish agent)    │        │  infer cluster match    │     │ NEVER labelled safe   │
└──────────────────────┘        └─────────────────────────┘     └───────────────────────┘
```

---

## 2. Signal Independence & Risk Formulation

A core tenet of STING's triage design is: **No single weak signal may ever produce a verdict.**

Scammers frequently buy aged expired domains to bypass simple age checks; conversely, legitimate startups frequently launch new domains with urgent marketing copy. High confidence requires **multi-group signal independence**.

### 2.1 The 5 Signal Independence Groups

| Signal Group | Forensic Signals | Strength | Rationale |
| :--- | :--- | :--- | :--- |
| **`domain`** | `newly_registered_domain` (<30 days)<br>`recent_domain` (<90 days) | Strong (<30d)<br>Weak (<90d) | Disposable infrastructure indicator. However, legitimate new sites also exist. |
| **`brand`** | `brand_mismatch` | **Strong** | Page copy claims a verified brand (e.g. "State Bank of India") but host domain is not on that brand's official domain whitelist. |
| **`payment`** | `payment_indicators` (UPI VPA regex, `upi://pay`, `scan qr`, `claim fee`) | **Strong** | Direct solicitation of monetary transfer or credential capture. |
| **`content`** | `urgency_phrases` (>=2 keywords: `disconnect`, `blocked`, `legal action`) | Strong (>=2)<br>Weak (1) | Social engineering cues designed to induce panic and cognitive overload. |
| **`reputation`**| `search_scam_mentions` (>=3 mentions in search snippets) | Strong (>=3)<br>Weak (1-2) | Crowdsourced victim complaints and public threat intelligence. |

### 2.2 Risk Level Evaluation

- **`high` Risk:** Strictly requires **>= 2 strong signals from DIFFERENT independence groups** (e.g., `brand` mismatch + `payment` indicators, or `domain` age < 30 days + `payment` indicators).
- **`medium` Risk:** Exactly 1 strong signal, OR >= 2 weak signals across groups.
- **`low` Risk:** Zero strong signals and <= 1 weak signal.

---

## 3. Page Fingerprinting & Simhash Algorithm

To identify copycat scam kits deployed across thousands of rotating domains, STING employs a two-tier forensic fingerprint:

### 3.1 64-bit Charikar Simhash

Simhash converts arbitrary text into a 64-bit integer where the bitwise Hamming distance between two hashes is inversely proportional to their cosine similarity:
1. Normalizes page text into word tokens: `\b[a-zA-Z0-9]{2,}\b`.
2. Computes 64-bit MD5 hashes for each token.
3. Initializes a 64-element accumulator vector $V = [0]_{64}$.
4. For each token hash, adds $+1$ to $V[i]$ if bit $i$ is $1$, or $-1$ if bit $i$ is $0$.
5. Final hash bit $i$ is set to $1$ if $V[i] > 0$, else $0$.

### 3.2 Strong Fingerprint Matching Rule

A target page fingerprint $FP_1$ is clustered with known campaign $FP_2$ **if and only if**:
$$\text{HammingDistance}(FP_1.\text{text\_simhash}, FP_2.\text{text\_simhash}) \le 8$$
$$\mathbf{AND}\quad \left( FP_1 \cap FP_2 \text{ shares a form action domain} \;\lor\; \text{shares a script host} \;\lor\; (\text{same registrar} \land \text{identical nameservers}) \right)$$

Lexical similarity alone ($\text{distance} \le 8$) without shared infrastructure does **not** trigger a cluster skip, preventing unrelated sites that use generic Bootstrap or Tailwind templates from being falsely linked.

---

## 4. Deterministic Decision Rules & Degrade Paths

Decisions are evaluated sequentially using strict deterministic ordering. LLMs are never used to decide whether to detonate:

1. **Rule 1: Force Detonate (`force_detonate == True`):**
   - Analyst override requested via API flag. Instantly outputs `DETONATE`.
2. **Rule 2: Input Payee Known in Graph:**
   - If the user submitted a payee VPA alongside the link, and that payee is already confirmed in the intelligence graph, returns `SKIP_KNOWN_PAYEE` (advancing directly to enrichment).
3. **Rule 3: Known Site Reuse:**
   - If the page domain was detonated within `SITE_REUSE_DAYS` (default: 7 days) and produced a confirmed payee, returns `SKIP_KNOWN_SITE`. The previous payee is carried over with attribution `confirmed` and explicit audit note: `"carried over from case X observed on DATE"`.
4. **Rule 4: Strong Fingerprint Match:**
   - If the page matches an active campaign cluster under the Section 6 strong fingerprint rule, returns `SKIP_KNOWN_CLUSTER`. Attribution is set to `inferred` and flagged `needs_verification = True`.
5. **Rule 5: Old Benign Domain -> Inconclusive:**
   - Domain age $> 365$ days **AND** zero payment cues **AND** zero brand mismatch **AND** zero search scam mentions **AND** zero fetch error.
   - Outputs `INCONCLUSIVE` (reasoning: `"not detonated"`). **NEVER labelled as safe.**
6. **Rule 6: Default -> DETONATE:**
   - If risk signals are present, OR if triage fails (fetch blocked by Cloudflare/WAF, RDAP unreachable, or registration age unknown), the system **degrades toward DETONATE**, never toward an inconclusive or clean verdict.

---

## 5. Comprehensive Q&A: Architectural Defenses & Edge Cases

### Q1: False Positives vs False Negatives — Who is harmed by each?
- **False Positive (Detonating a benign site):**
  - *Harm:* Financial cost to STING operator (~$0.02 – $0.05 for a browser run) and negligible compute overhead. The autonomous agent reaches step limits, discovers zero payment destinations, and yields `outcome = "inconclusive"`. No public alert is issued without human review. Harm is strictly financial and contained to STING.
- **False Negative (Skipping or labelling a scam as benign/safe):**
  - *Harm:* Catastrophic. A citizen or bank reviewer trusting STING is defrauded, funds move through mule accounts unblocked, and law enforcement receives no intelligence.
  - *Architectural Safeguard:* STING deliberately biases all ambiguous and degraded paths toward `DETONATE`. Under Rule 5, clean sites are marked `INCONCLUSIVE ("not detonated")`, completely forbidding any `"SAFE"` or `"CLEAN"` verdict.

### Q2: Why Simhash instead of cosine similarity with dense vector embeddings?
- Dense embedding models (e.g. OpenAI `text-embedding-3`, sentence-transformers) require either an outbound paid API call, GPU dependencies, or heavy native PyTorch binaries that introduce high latency and supply-chain complexity.
- Charikar Simhash runs in pure Python standard library in $<0.5\text{ ms}$, requires zero external networks or GPU hardware, and computes exact Hamming bit distance in a single CPU instruction (`bin(h1 ^ h2).count('1')`).

### Q3: What if the scammer cloaks content from TinyFish Fetch?
- Scammers often inspect user agents, IP ranges, or TLS fingerprints to serve benign holding pages to headless curl/fetch bots while serving scam funnels to residential mobile browsers.
- *Defense:* If Fetch returns an error, empty page, or Cloudflare challenge, triage records `fetch_error`. Under Rule 6, **any fetch error automatically degrades to `DETONATE`**. The TinyFish Detonation Agent then visits the site using a real residential proxy and full anti-detect browser profile, rendering cloaking ineffective.

### Q4: Why is an old domain not proof of safety?
- Thousands of legitimate WordPress, educational, and corporate domains expire each week and are purchased by fraudsters ("drop-catching"), or suffer from unpatched CMS vulnerabilities where subfolders (e.g. `compromised-site.com/wp-content/uploads/sbi/`) host scam kits.
- *Defense:* Rule 5 requires domain age $> 365$ days **AND** zero payment cues **AND** zero brand mismatches **AND** zero threat complaints. If a 10-year-old domain contains even a single payment cue or brand mismatch, Rule 5 is immediately disqualified and Rule 6 forces a `DETONATE`.

### Q5: How could the brand list (`brands.yaml`) be biased or incomplete?
- A static list of 25 brands cannot cover every regional co-operative bank or electricity board in India.
- *Mitigation:* `brands.yaml` is hot-reloadable and decoupled from code. Furthermore, brand mismatch is only **one** of five signal groups. If an unlisted local brand is impersonated, payment indicators (`upi://pay`, QR codes, IFSC) and newly registered domain signals still trigger `high` risk and force detonation.

### Q6: What happens if a known site has rotated its payee since it was last observed?
- Fraudsters rotate mule UPI accounts rapidly once an account is frozen by a bank.
- *Defense:*
  1. **Time-decay expiry (`SITE_REUSE_DAYS = 7`):** Skip rules expire after 7 days, forcing fresh detonations on recurring campaigns.
  2. **Analyst Override (`force_detonate = True`):** Rule 1 guarantees that an investigator can bypass all cached skips at will.
  3. **Multi-identifier correlation:** In Section 09, sites link to multiple historical payees rather than a single static key.

---

## 6. Verification & Quality Gates

All 81 tests pass across the repository:
```bash
$ pytest backend/tests
============================= 81 passed in 24.53s =============================
```

### Table-Driven Test Matrix (`test_triage_decision.py`)
- **Simhash:** Bitwise distance is 0 for identical text, $\le 8$ for near-duplicate text, and $> 8$ for disparate text.
- **Brand Mismatch:** 100% precision against official whitelist vs typo-squatted domains.
- **RDAP Resilience:** HTTP 404, network timeouts, and non-authoritative TLDs degrade to `domain_age_days = None` (unknown is never old).
- **Inconclusive Guarantee:** Inconclusive outputs never contain the terms `"safe"`, `"clean"`, or `"benign"`.
- **Mock Funnels:** Simhash distance between `a1` and `a2` is close ($13$), while `b1` is far ($26$).
- **Audit Trails:** Individual forensic signals and decision reasoning lines are committed as durable `case_events`.

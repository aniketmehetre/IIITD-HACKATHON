# Deep-Dive: Section 09 — Campaign Correlation Graph & Seed Intelligence

**Module:** Multi-Site Cluster Intelligence, Union-Find Connected Components & Cytoscape Attribution Engine  
**Authors:** Team void main  
**Status:** Complete  

---

## 1. Architectural Role & Objective

A single isolated scam report (e.g., "power-bill-discom.biz sent money to payee `mule@okhdfcbank`") treats phishing as disconnected one-off incidents. In reality, cybercrime syndicates operate **industrialized campaigns**:
- A single syndicate deploys dozens of disposable domains using identical kit templates.
- When domains are banned, the syndicate rotates to fresh domain registrations while routing victim proceeds to a shared pool of mule bank accounts and UPI handles.
- Conversely, when a mule account is frozen, the syndicate switches the payment destination in their kit templates.

Section 09 establishes STING's primary forensic differentiator: **The Campaign Correlation Intelligence Graph**.
It correlates phishing sites and payee destinations into connected components using Disjoint-Set Union-Find over relational database records, exposing multi-domain mule networks to fraud investigators.

```
  [Phishing Domain 1] (confirmed) ──┐
                                     ├──► [Payee A: discom.powerbilling@okhdfcbank]
  [Phishing Domain 2] (confirmed) ──┘        │
                                             │
  [Phishing Domain 3] (inferred) ────────────┘
  (Matched via 64-bit Simhash & DNS)
```

---

## 2. Confirmed vs. Inferred Attribution Semantics

A fundamental danger in threat intelligence is overclaiming attribution. STING enforces honest forensic boundaries:

| Attribution Level | Confidence | Visual Representation | Definition & Policy |
| :--- | :--- | :--- | :--- |
| **`confirmed`** | **1.0 (100%)** | **Solid Edge** | The link was directly observed during a live browser detonation, decoded from a QR image, or provided directly in verified case intake. |
| **`inferred`** | **0.85 (85%)** | **Dashed Edge** | The site was **NOT** detonated. It matched an existing cluster via 64-bit lexical Simhash ($\le 8$) and shared DNS/form-action infrastructure under `SKIP_KNOWN_CLUSTER`. |

### The Inferred-to-Confirmed Upgrade Path:
If an inferred site is subsequently detonated (e.g., via analyst `force_detonate=True` or automated follow-up), and the extracted payee matches, STING automatically **upgrades** the edge from `inferred` to `confirmed` with 1.0 confidence. Inferred attribution is **never** presented as confirmed in API outputs.

---

## 3. Disjoint-Set Union-Find & Cytoscape Contract

To avoid double sources of truth, STING computes connected components directly from the relational tables (`sites`, `payees`, `edges`) using a fast in-memory Union-Find structure:
1. Every domain is represented as a node `domain:{domain}`.
2. Every normalized payee destination is a node `payee:{value_normalized}`.
3. Every edge joins the two sets into a unified `cluster_id` (e.g., `cluster-payee:discom.powerbilling@okhdfcbank`).
4. Endpoints serialize directly to the Cytoscape graph standard expected by modern SOC visualization suites:
   - `GET /graph/overview?limit=500&include_seed=true&min_cluster_size=1`
   - `GET /graph/{payee_id}`

---

## 4. Economic Accuracy: How the Skip Path Saves Paid Runs

STING's triage gating reduces investigative costs, but we make no exaggerated claims:
- **First Site of a New Campaign:** Costs 1 paid TinyFish browser detonation run. Payees cannot be guessed before detonation without a prior record.
- **Subsequent Sites in the Campaign:** Because syndicates reuse phishing kits (identical DOM structure, form actions, or nameservers), subsequent domains hit `SKIP_KNOWN_CLUSTER` or `SKIP_KNOWN_SITE`. They are correlated into the campaign cluster **at zero cost**, saving $0.03 – $0.05 per investigation.

---

## 5. Architectural Q&A

### Q1: Isn't it circular to check the payee before detonating if the payee is unknown until detonation?
**A:** No, because STING evaluates two independent pre-detonation signals that do not depend on detonation:
1. **The input itself:** Many victim complaints arrive with a screenshot, QR code, or SMS mentioning the payee ID. If that payee is already known, detonation is skipped (`SKIP_KNOWN_PAYEE`).
2. **The site and its fingerprint:** The domain, DOM simhash, registrar, and nameservers are extracted for free during triage. If these match an active cluster, detonation is skipped (`SKIP_KNOWN_CLUSTER`), or if the domain was detonated recently (`SKIP_KNOWN_SITE`), the prior confirmed payee is carried over.

### Q2: What if two unrelated scammers purchase and deploy the same generic scam kit from Telegram?
**A:** Sharing a kit implies shared template code, not necessarily a shared human operator. This is precisely why STING labels template-only matches as **`inferred` (dashed edge, needs verification)**. Confirmed attribution is reserved solely for verified payee matches.

### Q3: What happens if fraudsters rotate payees on a daily basis?
**A:** `find_site` enforces a strict `SITE_REUSE_DAYS` window (default 7 days). If an observation is older than 7 days, STING refuses to assume the payee is still active and triggers a fresh detonation. Furthermore, the analyst can force a re-detonation at any time using `force_detonate = True`.

### Q4: How does an incorrect inferred link cause harm, and what prevents that harm?
**A:** Inferred edges link domains to mule accounts. If a benign website were falsely linked to a criminal payee, that site could face wrongful takedown requests. STING prevents this by:
1. Requiring lexical near-duplication (Simhash $\le 8$) **AND** shared infrastructure (nameservers, form action domains).
2. Requiring mandatory analyst acknowledgement (`acknowledge_inferred=True`) before any report containing inferred links can be approved (Section 11).

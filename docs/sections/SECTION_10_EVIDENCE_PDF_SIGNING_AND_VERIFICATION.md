# Deep-Dive: Section 10 — Evidence PDF Generation, Cryptographic Signing & Verification

**Module:** Forensic Evidence Dossier, ReportLab Platypus Engine, HMAC Sealing & Hash-Chained Ledger  
**Authors:** Team void main  
**Status:** Complete  

---

## 1. Architectural Role & Forensic Requirements

When financial fraud, phishing, or electricity bill extortion syndicates are disrupted, raw threat intelligence alone is insufficient. Law enforcement agencies (e.g., State Police Cyber Cells, 1930 / I4C, National Cyber Crime Reporting Portal), telecom operators, and bank anti-fraud desks require **legally admissible, cryptographically verifiable forensic dossiers**.

An evidence dossier must satisfy four strict evidentiary standards:
1. **Chain of Custody:** The dossier must be irrevocably bound to an immutable audit record establishing exact capture timestamp, originating worker, and raw intake data.
2. **Tamper Evidence:** Any modification—even altering a single byte, comma, or timestamp in the generated report—must be immediately detectable by automated verification tools.
3. **Execution Safety (SSRF & Exploit Immunity):** Forensic systems process *untrusted, hostile content* originating directly from criminal phishing kits (e.g., weaponized SVG, `<script>` tags, SSRF-inducing `<img>` URLs, and path traversal vectors). Generating evidence must never compromise the reporting server.
4. **Offline Verifiability:** An investigator receiving a PDF report via email or USB drive must be able to upload the raw binary to `/evidence/verify` and cryptographically validate that it matches the sealed ledger record without needing access to internal databases.

```
                  ┌──────────────────────────────────────────────┐
                  │          Scam Investigation Case             │
                  │ (Case record, metadata, telemetry & timeline)│
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │    Canonical Evidence Bundle (JSON)          │
                  │   - Normalized fields, sorted keys, no spaces│
                  │   - bundle_sha256 = SHA256(canonical_json)   │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │    ReportLab Platypus Document Builder       │
                  │   - Zero HTML/CSS engine (SSRF Immune)       │
                  │   - Escaped Flowable Paragraphs & Tables     │
                  │   - Generates deterministic PDF byte-stream  │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │   Cryptographic Sealing & Hash-Chained Ledger│
                  │   - pdf_sha256 = SHA256(pdf_bytes)           │
                  │   - signature = HMAC-SHA256(key, pdf_sha256) │
                  │   - entry_hash = SHA256(prev:pdf:bundle:ts)  │
                  └──────────────────────────────────────────────┘
```

---

## 2. ReportLab Platypus vs. HTML-to-PDF Engines (SSRF Immunity)

A common architectural vulnerability in forensic and reporting software is relying on HTML-to-PDF rendering engines (such as Headless Chrome/Puppeteer, WeasyPrint, or wkhtmltopdf):

| Engine Type | Mechanism | Security Exposure | STING Selection |
| :--- | :--- | :--- | :--- |
| **Headless Chrome / Puppeteer** | Full Chromium DOM & JS rendering | **Severe:** SSRF via `fetch()` / `<img>` to cloud metadata (e.g., `http://169.254.169.254`), local file read via `file:///etc/passwd`, heavy memory footprint (100MB+ per process). | **REJECTED** |
| **WeasyPrint / wkhtmltopdf** | HTML5 / CSS3 rendering engines | **High:** SSRF via external stylesheet imports (`@import`), font downloads, and unauthenticated internal network probing. | **REJECTED** |
| **ReportLab Platypus** | Programmatic canvas & flowable document layout in pure Python | **Zero Network Exposure:** No HTML parsing, no external resource fetching, no socket binding, zero local filesystem access during document generation. | **SELECTED (STING Standard)** |

### Hostile Markup Containment:
Scammers frequently embed weaponized markup inside phishing landing pages (e.g., `<script>alert(1)</script>`, `<img src="http://169.254.169.254/latest/meta-data/">`). STING treats all input strings as potentially hostile:
- Every dynamic string (domain, URL, payee name, error trace) is sanitized with `html.escape()`.
- Text is inserted into ReportLab `Paragraph` flowables as inert, non-executable content.
- Null or missing fields are explicitly rendered as clean fallback indicators (`"Not observed"`, `"Not applicable"`) to guarantee documents never fail midway.

---

## 3. Cryptographic Sealing & Append-Only Hash Chain

STING guarantees non-repudiation and tamper-evidence via a two-layer cryptographic mechanism:

### Layer 1: Canonical Bundle SHA-256
Before PDF generation, all case data (identifiers, classification, timeline, payee details) is serialized into a canonical JSON representation:
- Keys are sorted lexicographically (`sort_keys=True`).
- Separators eliminate non-deterministic whitespace (`separators=(",", ":")`).
- Datetimes are formatted as ISO 8601 UTC strings.
- The canonical bundle hash is computed:
  $$\text{bundle\_sha256} = \text{SHA256}(\text{CanonicalJSON})$$

### Layer 2: PDF Sealing & HMAC-SHA256
Once the PDF bytes are synthesized:
$$\text{pdf\_sha256} = \text{SHA256}(\text{PDFBytes})$$
$$\text{signature} = \text{HMAC-SHA256}(\text{EVIDENCE\_SIGNING\_KEY}, \text{pdf\_sha256})$$

### Layer 3: Immutable Hash-Chained Evidence Ledger
Every generated evidence file is permanently recorded in the `evidence_ledger` database table. Like a lightweight forensic blockchain, each row cryptographically commits to the immediately preceding row:

$$\text{entry\_hash}_n = \text{SHA256}(\text{entry\_hash}_{n-1} : \text{pdf\_sha256}_n : \text{bundle\_sha256}_n : \text{created\_at}_n)$$

For the first entry in the database, $\text{entry\_hash}_0$ defaults to the `GENESIS_HASH` (`"0" * 64`).

```
  [Genesis Hash: 000...000]
             │
             ▼
  ┌─────────────────────────────┐
  │ Ledger Entry #1             │
  │ pdf_sha256: 3a9f...         │
  │ bundle_sha256: 8c1d...      │
  │ entry_hash: 5b4e... ────────┼────────┐
  └─────────────────────────────┘        │
                                         ▼
                          ┌─────────────────────────────┐
                          │ Ledger Entry #2             │
                          │ prev_hash: 5b4e...          │
                          │ pdf_sha256: 9e2a...         │
                          │ entry_hash: 7d1a... ────────┼────────┐
                          └─────────────────────────────┘        │
                                                                 ▼
                                                  ┌─────────────────────────────┐
                                                  │ Ledger Entry #3             │
                                                  │ prev_hash: 7d1a...          │
                                                  │ pdf_sha256: 1f0c...         │
                                                  │ entry_hash: 4c3b...         │
                                                  └─────────────────────────────┘
```

**Security Invariant:** If a malicious database administrator modifies or replaces a past PDF hash or deletes an entry, the entire downstream hash chain becomes invalid.

---

## 4. API Endpoints Contract

### 1. Download Forensic PDF
- **Endpoint:** `GET /cases/{id}/evidence`
- **Response:** Raw binary PDF stream (`application/pdf`)
- **Headers:** `Content-Disposition: inline; filename="case_{id}_evidence.pdf"`
- **Access Control:** Available as soon as the case reaches `evidence` stage or terminal completion.

### 2. Verify PDF Authenticity
- **Endpoint:** `POST /evidence/verify`
- **Payload:** `multipart/form-data` containing the uploaded PDF file.
- **Verification Logic:**
  1. Computes `SHA256(uploaded_bytes)`.
  2. Looks up the matching entry in `evidence_ledger`.
  3. Verifies `HMAC-SHA256` signature using server secret.
  4. Verifies hash-chain integrity: recomputes `entry_hash` from `(prev_entry_hash, pdf_sha256, bundle_sha256, created_at)` and asserts equality.
- **Response Example:**
```json
{
  "valid": true,
  "case_id": "41a31d9b-d7d8-4b72-bdf9-0db9bfd19bc1",
  "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "verified_at": "2026-10-24T18:55:00Z",
  "ledger_position": 42,
  "reason": "Cryptographic signature and SHA-256 hash match verified case record in hash-chained ledger."
}
```

---

## 5. Architectural Q&A

### Q1: Why not use headless Chrome or WeasyPrint to make the PDF look like a modern web dashboard?
**A:** Because rendering attacker-controlled web inputs through a browser engine creates an unacceptable attack surface for a forensic tool. Attackers could inject SSRF payloads (fetching AWS/GCP instance metadata), trigger local file inclusions (`file:///etc/shadow`), or execute arbitrary JavaScript during PDF creation. ReportLab Platypus constructs the PDF directly in Python byte code without opening network sockets or parsing untrusted HTML styles, guaranteeing SSRF immunity.

### Q2: How does STING handle malformed or maliciously crafted strings from untrusted scam pages in the PDF?
**A:** All dynamic values (domain names, user agents, captured URLs, error logs) are passed through `html.escape()` and wrapped in ReportLab `Paragraph` flowables. Furthermore, all fields use defensive null-coalescing (`val or "Not observed"`) so missing data renders as clean forensic placeholders rather than crashing the generation pipeline.

### Q3: Why HMAC-SHA256 instead of asymmetric public/private keys (e.g., Ed25519 or RSA)?
**A:** HMAC-SHA256 provides ultra-fast, zero-overhead symmetric verification suitable for automated backend ingestion and verification against the organization's signing secret. STING's architecture is modular: the `compute_hmac_signature` interface can be extended with an X.509 PKI / Ed25519 signer if external non-repudiation across third-party legal jurisdictions without shared secrets is required.

### Q4: What does the hash-chained ledger prevent that a standalone SHA-256 hash does not?
**A:** A standalone hash verifies file integrity against the current database row, but it cannot detect **database alteration or deletion**. If an insider or compromised account modifies a database row to match a forged document or deletes a case to cover up evidence, a standalone hash would accept the alteration. The hash chain ensures that tampering with any entry breaks the cryptographic link of all subsequent entries, exposing historical tampering immediately.

### Q5: How is non-repudiation maintained if an attacker tampers with even a single byte of an archived PDF?
**A:** Any alteration changes the SHA-256 digest of the PDF file. When uploaded to `/evidence/verify`, the computed hash will fail to match any entry in the ledger, immediately returning `{"valid": false, "reason": "PDF SHA-256 hash is not registered in the immutable evidence ledger."}`.

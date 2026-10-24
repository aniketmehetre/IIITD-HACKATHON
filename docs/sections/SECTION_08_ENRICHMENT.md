# Deep-Dive: Section 08 — Identifier Enrichment & Financial Rails Resolution

**Module:** Financial Identifier Resolution, NPCI PSP Mapping & Privacy-First Forensic Enrichment  
**Authors:** Team void main  
**Status:** Complete  

---

## 1. Architectural Role & Objective

A raw identifier extracted during detonation (e.g. `electricity.bill.recovery@okhdfcbank` or `50200083921901`) is insufficient for immediate law enforcement or banking triage. Incident response teams and cyber crime units (such as India's 1930 / I4C National Cyber Crime Reporting Portal) require **actionable jurisdiction and routing details**:
- Which Payment Service Provider (Google Pay, PhonePe, Paytm, BHIM) controls the handle?
- Which sponsor bank maintains the settlement pool on the UPI central switch?
- What is the 4-letter clearing bank code from the IFSC for freeze requests?
- Does a QR code embed hidden payee metadata or deep-link parameters?

Section 08 establishes a **deterministic, privacy-first enrichment engine** that translates raw extracted identifiers into structured forensic intelligence without exposing victim or account-holder personal data.

```
            ┌──────────────────────────────────────────────┐
            │          Extracted Raw Identifiers           │
            │  - UPI VPA: power.bill@okhdfcbank            │
            │  - Bank Account: 50200083921901 / HDFC0001234│
            │  - QR / Deep Link: upi://pay?...             │
            │  - Crypto Address: 0x71C84192...             │
            └──────────────────────┬───────────────────────┘
                                   │
                                   ▼
            ┌──────────────────────────────────────────────┐
            │               stage_enrichment               │
            │      Deterministic Resolution & Parsing      │
            └───────────┬──────────────┬───────────────┬───┘
                        │              │               │
      ┌─────────────────┴──────┐ ┌─────┴───────┐ ┌─────┴────────────────┐
      │     NPCI PSP Table     │ │ IFSC / Bank │ │   Crypto Classifier  │
      │   Resolve Handle & PSP │ │ 4-Letter ID │ │  EVM / Bitcoin / TRON│
      └─────────────────┬──────┘ └─────┬───────┘ └─────┬────────────────┘
                        │              │               │
                        └──────────────┼───────────────┘
                                       │
                                       ▼
            ┌──────────────────────────────────────────────┐
            │               EnrichmentResult               │
            │  - PSP: Google Pay                           │
            │  - Sponsor Bank: HDFC Bank (Code: HDFC)      │
            │  - Validated Account & Rail Hint             │
            │  - Canonical Normalized Payee Identifiers    │
            └──────────────────────────────────────────────┘
```

---

## 2. Official NPCI Mapping Table (`data/upi_psp.yaml`)

UPI handles in India operate as aliases over banking rails. Google Pay, PhonePe, and third-party apps do not hold banking licenses; they partner with scheduled commercial banks (e.g., Google Pay with HDFC, Axis, SBI, ICICI).

STING compiles this mapping strictly from the **National Payments Corporation of India (NPCI) official directory** (October 2026):
- `@okhdfcbank` &rarr; Google Pay / HDFC Bank (`HDFC`)
- `@ybl` &rarr; PhonePe / Yes Bank (`YESB`)
- `@ptsbi` &rarr; Paytm / State Bank of India (`SBIN`)
- `@apl` &rarr; Amazon Pay / Axis Bank (`UTIB`)
- `@stingtest` &rarr; STING Test PSP (synthetic benchmark)

### Strict Unverified Handle Policy
To eliminate hallucination or false routing:
- Any handle suffix **not present** in `data/upi_psp.yaml` resolves strictly to `"Unknown"`.
- The system never attempts fuzzy guesses or LLM extrapolation for financial routing codes.

---

## 3. Deliberate Data-Minimization: Zero PII Collection

A foundational design constraint of STING is: **Do NOT call any API that reveals an account holder's name or personal details.**

### Why STING Refuses Holder Lookups:
1. **Mule Account Protection:** The legal owner of a mule account is frequently a victim of identity theft, a coerced individual, or a compromised student. Displaying personal names without judicial oversight creates severe defamation and privacy risks.
2. **Attack Surface Reduction:** Querying live bank beneficiary APIs introduces private API credential leakage risks and opens the backend to tracking by fraudsters.
3. **Sufficient for Action:** Bank fraud desks and cyber cells only require the account number, IFSC, and transaction reference to freeze funds internally. They already possess the holder KYC in their core banking system.

---

## 4. Deep Link & Crypto Rails Parsing

1. **`upi://pay` Deep Link Parsing:**
   - Extracts merchant parameters (`pa`, `pn`, `am`, `cu`, `tn`, `mc`).
   - Translates QR codes intercepted in HTML DOM or image uploads into structured payee objects.
2. **IFSC Institution Derivation:**
   - Validates Indian Financial System Code regex: `^[A-Z]{4}0[A-Z0-9]{6}$`.
   - Derives the 4-letter RBI bank identifier (e.g., `SBIN`, `HDFC`, `ICIC`, `UTIB`).
3. **Cryptocurrency Public Key Analysis:**
   - Distinguishes Ethereum/EVM (`0x...`), Bitcoin Legacy/SegWit (`1/3/bc1...`), and TRON (`T...`).
   - Flags TRON TRC-20 addresses, which are overwhelmingly favored in utility and job scam cash-outs via USDT.

---

## 5. Architectural Q&A

### Q1: What would happen if a PSP mapping in `upi_psp.yaml` went stale or incorrect?
**A:** If an NPCI mapping were incorrect, an alert sent to a sponsor bank might reach the wrong institution's fraud desk (e.g., notifying Axis instead of HDFC). However:
- The raw UPI ID is always attached alongside the resolved metadata.
- Banks reconcile freezes against the central UPI switch, which routes on the true handle.
- The YAML file header cites the exact NPCI source and revision timestamp for auditable updates.

### Q2: Why doesn't STING perform account holder name lookups using UPI verification APIs?
**A:** This is a deliberate legal and data-minimization decision. Bank fraud teams and law enforcement already have authoritative access to core banking KYC records. STING exists to pinpoint perpetrator destinations, not to scrape private citizen personal data.

### Q3: What are a mule account holder's rights and risks, and why is human review required?
**A:** Many mule accounts belong to students or gig workers whose KYC documents were abused, or who were lured by "work from home" schemes without understanding the funds were proceeds of crime. Flagging an account triggers immediate account freezing. Mandatory human review (Section 11) prevents automated, reckless reporting from ruining innocent lives.

### Q4: What happens when an unfamiliar or private enterprise UPI handle is encountered?
**A:** The engine extracts the handle suffix, sets `psp_name = "Unknown"`, `sponsor_bank = "Unknown"`, and preserves the full string in `normalized_payees`. The pipeline proceeds without interruption, allowing downstream graph correlation and human reviewers to inspect the raw handle.

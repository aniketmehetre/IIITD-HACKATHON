"""Triage Agent for free-tier heuristic signal extraction, brand checks, and fingerprinting.

Conforms strictly to Section 6 specification:
- Consumes ONLY free-tier surfaces (TinyFish Fetch, TinyFish Search, RDAP).
- Extracts payment cues, urgency phrases, brand mismatches, and domain registration age.
- Assembles a forensic Fingerprint with 64-bit Simhash.
- Enforces signal independence: risk_level='high' strictly requires >= 2 strong signals
  from different independence groups.
"""

import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Optional

from app.agents.brands import check_brand_mismatch
from app.agents.fingerprint import (
    Fingerprint,
    compute_simhash,
    compute_title_hash,
    extract_html_fingerprint_features,
)
from app.integrations.rdap import RdapResult, lookup_rdap
from app.integrations.tinyfish import TinyFishClient

logger = logging.getLogger(__name__)

# Urgency phrase cues common in impersonation and extortion funnels
URGENCY_KEYWORDS = [
    "disconnect",
    "disconnection",
    "suspended",
    "suspension",
    "immediately",
    "within 24 hours",
    "account blocked",
    "urgent",
    "penalty",
    "legal action",
    "police",
    "expire",
    "expiring today",
]

# Payment indicator cues
PAYMENT_PATTERNS = [
    r"upi://pay",
    r"\b[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z0-9.\-_]{2,64}\b",
    r"scan qr",
    r"processing fee",
    r"claim fee",
    r"security deposit",
    r"recharge now",
    r"pay now",
    r"pending bill",
]


@dataclass
class Signal:
    """Atomic forensic signal with strength and independence categorization."""

    name: str
    value: Any
    strength: str  # "weak" | "strong"
    group: str  # "domain" | "brand" | "payment" | "content" | "reputation"
    description: str


@dataclass
class TriageResult:
    """Structured explainable output from Triage Agent."""

    url: str
    domain: str
    signals: list[Signal]
    fingerprint: Fingerprint
    risk_level: str  # "low" | "medium" | "high"
    reasoning: list[str] = field(default_factory=list)
    raw_title: Optional[str] = None
    fetch_error: Optional[str] = None
    domain_age_days: Optional[int] = None
    brand_claimed: Optional[str] = None
    brand_mismatch: bool = False
    payment_indicators_found: list[str] = field(default_factory=list)
    urgency_phrases_found: list[str] = field(default_factory=list)
    search_scam_mentions: int = 0

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "domain": self.domain,
            "risk_level": self.risk_level,
            "brand_mismatch": self.brand_mismatch,
            "brand_claimed": self.brand_claimed,
            "domain_age_days": self.domain_age_days,
            "search_scam_mentions": self.search_scam_mentions,
            "payment_indicators": self.payment_indicators_found,
            "urgency_phrases": self.urgency_phrases_found,
            "signals": [
                {
                    "name": s.name,
                    "value": s.value,
                    "strength": s.strength,
                    "group": s.group,
                    "description": s.description,
                }
                for s in self.signals
            ],
            "fingerprint": self.fingerprint.to_dict(),
            "reasoning": self.reasoning,
            "fetch_error": self.fetch_error,
        }


async def run_triage(
    url: str,
    tinyfish_client: Optional[TinyFishClient] = None,
    rdap_result_override: Optional[RdapResult] = None,
    html_override: Optional[str] = None,
) -> TriageResult:
    """Executes free-tier triage analysis on target URL."""
    parsed_url = urllib.parse.urlsplit(url)
    domain = parsed_url.hostname or "unknown"
    domain_lower = domain.lower()

    signals: list[Signal] = []
    reasoning: list[str] = []
    fetch_error: Optional[str] = None

    # 1. Fetch Page Content (Free tier)
    html_content = html_override or ""
    if not html_content and tinyfish_client:
        try:
            fetch_res = await tinyfish_client.fetch([url], format="html")
            if isinstance(fetch_res, dict) and "results" in fetch_res:
                results_list = fetch_res.get("results") or []
                if results_list and isinstance(results_list, list):
                    html_content = results_list[0].get("html") or results_list[0].get("content") or ""
            elif isinstance(fetch_res, list) and len(fetch_res) > 0:
                html_content = fetch_res[0].get("html") or fetch_res[0].get("content") or ""
        except Exception as exc:
            fetch_error = f"Fetch failed: {exc}"
            logger.warning("TinyFish fetch failed for %s: %s", url, exc)

    # 2. Extract DOM & Text Features
    title = None
    if html_content:
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL
        )
        if title_match:
            title = " ".join(title_match.group(1).split())

    visible_text, form_actions, script_hosts = extract_html_fingerprint_features(html_content, url)

    # 3. Detect Payment Indicators & Urgency Phrases
    combined_content = f"{title or ''} {visible_text}".lower()
    payment_found: list[str] = []
    for pat in PAYMENT_PATTERNS:
        matches = re.findall(pat, combined_content, re.IGNORECASE)
        if matches:
            payment_found.extend(
                matches if isinstance(matches[0], str) else [m[0] for m in matches]
            )

    # Deduplicate payment found
    payment_found = sorted(list(set([p.strip() for p in payment_found if p.strip()])))

    urgency_found: list[str] = [kw for kw in URGENCY_KEYWORDS if kw in combined_content]

    # Signal: Payment Intent
    if payment_found:
        signals.append(
            Signal(
                name="payment_indicators",
                value=payment_found,
                strength="strong",
                group="payment",
                description=f"Direct payment cues detected: {', '.join(payment_found[:3])}",
            )
        )
        reasoning.append(f"Found {len(payment_found)} payment indicator(s) in page copy.")

    # Signal: Content Urgency
    if urgency_found:
        strength = "strong" if len(urgency_found) >= 2 else "weak"
        signals.append(
            Signal(
                name="urgency_phrases",
                value=urgency_found,
                strength=strength,
                group="content",
                description=f"Urgency cues: {', '.join(urgency_found[:3])}",
            )
        )
        reasoning.append(f"Urgency / threat phrases detected ({len(urgency_found)} terms).")

    # 4. Brand Mismatch Check
    brand_mismatch, claimed_brand, brand_kws = check_brand_mismatch(
        domain=domain_lower,
        text=visible_text,
        title=title,
    )
    if brand_mismatch and claimed_brand:
        signals.append(
            Signal(
                name="brand_mismatch",
                value=claimed_brand,
                strength="strong",
                group="brand",
                description=f"Page claims brand '{claimed_brand}' on non-official domain '{domain}'.",
            )
        )
        reasoning.append(
            f"Brand mismatch: Impersonates '{claimed_brand}' using keywords [{', '.join(brand_kws[:2])}]."
        )

    # 5. RDAP Domain Age & Registration Lookup
    rdap_res = rdap_result_override
    if not rdap_res:
        rdap_res = await lookup_rdap(domain_lower)

    domain_age_days = rdap_res.domain_age_days
    if domain_age_days is not None:
        if domain_age_days < 30:
            signals.append(
                Signal(
                    name="newly_registered_domain",
                    value=domain_age_days,
                    strength="strong",
                    group="domain",
                    description=f"Domain registered only {domain_age_days} days ago (< 30 days).",
                )
            )
            reasoning.append(f"Suspiciously fresh domain age: {domain_age_days} days.")
        elif domain_age_days < 90:
            signals.append(
                Signal(
                    name="recent_domain",
                    value=domain_age_days,
                    strength="weak",
                    group="domain",
                    description=f"Domain registered {domain_age_days} days ago (< 90 days).",
                )
            )
    else:
        reasoning.append("RDAP registration age is unknown (unknown is not treated as old).")

    # 6. TinyFish Search Scam Mentions (Free tier)
    search_scam_mentions = 0
    if tinyfish_client and not fetch_error:
        try:
            search_query = f'"{domain_lower}" scam OR fraud OR complaint OR fake'
            search_res = await tinyfish_client.search(query=search_query, location="IN")
            results = search_res.get("results", []) if isinstance(search_res, dict) else []
            for item in results:
                t_low = (item.get("title") or "").lower()
                if any(k in t_low for k in ("scam", "fraud", "fake", "complaint", "phishing")):
                    search_scam_mentions += 1

            if search_scam_mentions >= 3:
                signals.append(
                    Signal(
                        name="search_scam_mentions",
                        value=search_scam_mentions,
                        strength="strong",
                        group="reputation",
                        description=f"{search_scam_mentions} search results cite scam/fraud complaints.",
                    )
                )
            elif search_scam_mentions >= 1:
                signals.append(
                    Signal(
                        name="search_scam_mentions",
                        value=search_scam_mentions,
                        strength="weak",
                        group="reputation",
                        description=f"{search_scam_mentions} search result mentions fraud cues.",
                    )
                )
        except Exception as exc:
            logger.debug("TinyFish search query failed: %s", exc)

    # 7. Compute Fingerprint
    text_simhash = compute_simhash(visible_text)
    fingerprint = Fingerprint(
        text_simhash=text_simhash,
        form_action_domains=form_actions,
        script_hosts=script_hosts,
        registrar=rdap_res.registrar,
        nameservers=rdap_res.nameservers,
        creation_week=rdap_res.creation_week,
        normalized_title_hash=compute_title_hash(title),
    )

    # 8. Compute Risk Level based on Signal Independence
    # High risk requires >= 2 strong signals from DIFFERENT groups
    strong_groups = set(s.group for s in signals if s.strength == "strong")
    weak_count = sum(1 for s in signals if s.strength == "weak")

    if len(strong_groups) >= 2:
        risk_level = "high"
    elif len(strong_groups) == 1 or weak_count >= 2:
        risk_level = "medium"
    else:
        risk_level = "low"

    return TriageResult(
        url=url,
        domain=domain_lower,
        signals=signals,
        fingerprint=fingerprint,
        risk_level=risk_level,
        reasoning=reasoning,
        raw_title=title,
        fetch_error=fetch_error,
        domain_age_days=domain_age_days,
        brand_claimed=claimed_brand,
        brand_mismatch=brand_mismatch,
        payment_indicators_found=payment_found,
        urgency_phrases_found=urgency_found,
        search_scam_mentions=search_scam_mentions,
    )

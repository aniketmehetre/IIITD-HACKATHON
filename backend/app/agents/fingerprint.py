"""Page structural and visual fingerprinting using 64-bit Simhash and infrastructure features.

Conforms strictly to Section 6 specification:
- 64-bit Simhash algorithm of normalized visible text / DOM.
- Extraction of form action domains and script host domains.
- Registrar and nameserver infrastructure tracking.
- Strong cluster matching rule: Hamming distance <= 8 AND >= 1 infrastructure link.
"""

import hashlib
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional


def compute_simhash(text: str) -> int:
    """Computes a 64-bit Charikar Simhash of text tokens."""
    # Split into word tokens and 3-grams
    tokens = re.findall(r"\b[a-zA-Z0-9]{2,}\b", text.lower())
    if not tokens:
        return 0

    v = [0] * 64
    for token in tokens:
        # MD5 digest truncated to 64 bits
        token_hash = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:16], 16)
        for i in range(64):
            if (token_hash >> i) & 1:
                v[i] += 1
            else:
                v[i] -= 1

    simhash = 0
    for i in range(64):
        if v[i] > 0:
            simhash |= 1 << i

    return simhash


def hamming_distance(h1: int, h2: int) -> int:
    """Calculates the bitwise Hamming distance between two 64-bit integers."""
    return bin(h1 ^ h2).count("1")


def compute_title_hash(title: Optional[str]) -> str:
    """Computes SHA-256 hash of normalized alphanumeric title."""
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", (title or "").lower())
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:16]


@dataclass
class Fingerprint:
    """Forensic fingerprint capturing page content and infrastructural markers."""

    text_simhash: int
    form_action_domains: list[str] = field(default_factory=list)
    script_hosts: list[str] = field(default_factory=list)
    registrar: Optional[str] = None
    nameservers: list[str] = field(default_factory=list)
    creation_week: Optional[str] = None
    normalized_title_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "text_simhash": self.text_simhash,
            "text_simhash_hex": hex(self.text_simhash),
            "form_action_domains": self.form_action_domains,
            "script_hosts": self.script_hosts,
            "registrar": self.registrar,
            "nameservers": self.nameservers,
            "creation_week": self.creation_week,
            "normalized_title_hash": self.normalized_title_hash,
        }


def extract_html_fingerprint_features(
    html: str,
    base_url: str,
) -> tuple[str, list[str], list[str]]:
    """Extracts visible text, form action domains, and script hosts from raw HTML.

    Returns:
        (visible_text, form_action_domains, script_hosts)
    """
    # 1. Extract script hosts
    script_hosts: set[str] = set()
    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
    for src in script_srcs:
        try:
            parsed = urllib.parse.urlsplit(urllib.parse.urljoin(base_url, src))
            if parsed.hostname:
                script_hosts.add(parsed.hostname.lower())
        except Exception:
            pass

    # 2. Extract form action domains
    form_action_domains: set[str] = set()
    form_actions = re.findall(r'<form[^>]+action=["\']([^"\']+)["\']', html, re.IGNORECASE)
    for act in form_actions:
        try:
            parsed = urllib.parse.urlsplit(urllib.parse.urljoin(base_url, act))
            if parsed.hostname:
                form_action_domains.add(parsed.hostname.lower())
        except Exception:
            pass

    # 3. Extract visible text
    cleaned = re.sub(r"<style.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<script.*?</script>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    visible_text = " ".join(cleaned.split())

    return visible_text, sorted(form_action_domains), sorted(script_hosts)


def is_strong_fingerprint_match(
    fp1: Fingerprint,
    fp2: Fingerprint,
) -> tuple[bool, list[str]]:
    """Evaluates whether two fingerprints match under Section 6 clustering criteria:

    - Simhash Hamming distance <= 8
    - AND at least one of:
      1) Shared form-action domain
      2) Shared script host
      3) Same registrar + identical nameservers
    """
    reasons: list[str] = []
    dist = hamming_distance(fp1.text_simhash, fp2.text_simhash)
    if dist > 8:
        return False, [f"Simhash Hamming distance ({dist}) exceeds threshold of 8."]

    reasons.append(f"Simhash distance {dist} <= 8 (lexical near-duplicate).")

    # Check shared form-action domains
    shared_forms = set(fp1.form_action_domains) & set(fp2.form_action_domains)
    if shared_forms:
        reasons.append(f"Shared form action domain: {', '.join(shared_forms)}")
        return True, reasons

    # Check shared script hosts
    shared_scripts = set(fp1.script_hosts) & set(fp2.script_hosts)
    if shared_scripts:
        reasons.append(f"Shared script host: {', '.join(shared_scripts)}")
        return True, reasons

    # Check registrar + nameservers
    if fp1.registrar and fp2.registrar and fp1.registrar.lower() == fp2.registrar.lower():
        if fp1.nameservers and fp2.nameservers and set(fp1.nameservers) == set(fp2.nameservers):
            reasons.append(
                f"Same registrar ({fp1.registrar}) and identical nameservers ({', '.join(fp1.nameservers)})"
            )
            return True, reasons

    return False, [f"Simhash distance {dist} <= 8, but zero shared infrastructure features."]

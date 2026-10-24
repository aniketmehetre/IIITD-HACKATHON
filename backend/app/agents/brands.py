"""Brand mismatch detection for Indian financial, telecom, utility, and government brands.

Conforms strictly to Section 6 specification:
- Loads official brands and domains from data/brands.yaml.
- Flags brand mismatch if brand keywords are present in page copy/title,
  but the domain is not in the brand's verified official domain list.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml


@lru_cache(maxsize=1)
def load_brands() -> list[dict]:
    """Loads and caches the brand impersonation database from data/brands.yaml."""
    possible_paths = [
        Path("data/brands.yaml"),
        Path("backend/data/brands.yaml"),
        Path(__file__).resolve().parent.parent.parent / "data" / "brands.yaml",
        Path(__file__).resolve().parent.parent.parent.parent / "data" / "brands.yaml",
    ]

    for p in possible_paths:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                return content.get("brands", [])

    return []


def is_official_domain(domain: str, official_domains: list[str]) -> bool:
    """Checks whether target domain is an official domain or subdomain."""
    norm_domain = domain.lower().strip()
    for official in official_domains:
        norm_official = official.lower().strip()
        if norm_domain == norm_official or norm_domain.endswith(f".{norm_official}"):
            return True
    return False


def check_brand_mismatch(
    domain: str,
    text: str,
    title: Optional[str] = None,
) -> tuple[bool, Optional[str], list[str]]:
    """Analyzes text and title for brand impersonation against official domains.

    Returns:
        (brand_mismatch, claimed_brand_name, matched_keywords)
    """
    brands = load_brands()
    combined_text = f"{title or ''} {text}".lower()

    for brand in brands:
        name = brand.get("name", "Unknown Brand")
        keywords = brand.get("keywords", [])
        official_domains = brand.get("official_domains", [])

        matched = [kw for kw in keywords if kw.lower() in combined_text]
        if matched:
            if not is_official_domain(domain, official_domains):
                return True, name, matched

    return False, None, []

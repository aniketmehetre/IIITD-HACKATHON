"""RDAP (Registration Data Access Protocol) client for domain intelligence.

Conforms strictly to Section 6 specification:
- HTTP-based RFC 7482/7483 lookup (cross-platform, zero native C library dependencies).
- Extracts domain creation date, domain age in days, registrar, and nameservers.
- Safe failure mode: If RDAP is unavailable or unresolvable, returns age = None (unknown).
  Unknown is never treated as old.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RDAP_BOOTSTRAP_URL = "https://rdap.org/domain"
DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass
class RdapResult:
    """Parsed RDAP domain registration metadata."""

    domain: str
    domain_age_days: Optional[int] = None
    creation_date: Optional[datetime] = None
    creation_week: Optional[str] = None
    registrar: Optional[str] = None
    nameservers: list[str] = field(default_factory=list)
    raw_status: Optional[str] = None
    error: Optional[str] = None


async def lookup_rdap(
    domain: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    client: Optional[httpx.AsyncClient] = None,
) -> RdapResult:
    """Performs an async RDAP lookup for target domain.

    Returns RdapResult with age, registrar, and nameservers.
    Gracefully degrades to age=None if unreachable.
    """
    cleaned_domain = domain.lower().strip()

    # Reject IP literals or local domains
    if cleaned_domain in ("localhost", "0.0.0.0") or "." not in cleaned_domain:
        return RdapResult(
            domain=cleaned_domain,
            error="Invalid domain for RDAP lookup.",
        )

    headers = {
        "Accept": "application/rdap+json, application/json",
        "User-Agent": "STING-Forensics/0.1.0",
    }
    url = f"{RDAP_BOOTSTRAP_URL}/{cleaned_domain}"

    try:
        if client:
            resp = await client.get(url, headers=headers, timeout=timeout)
        else:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as local_client:
                resp = await local_client.get(url, headers=headers)

        if resp.status_code != 200:
            return RdapResult(
                domain=cleaned_domain,
                error=f"RDAP query returned HTTP {resp.status_code}",
            )

        data = resp.json()

        # 1. Parse Registration Date
        creation_date = None
        for ev in data.get("events", []):
            if ev.get("eventAction") in ("registration", "transfer", "last changed"):
                if ev.get("eventAction") == "registration":
                    date_str = ev.get("eventDate")
                    if date_str:
                        try:
                            # Handle ISO 8601 strings (e.g. 2024-05-10T12:00:00Z)
                            creation_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            break
                        except ValueError:
                            pass

        domain_age_days = None
        creation_week = None
        if creation_date:
            now = datetime.now(timezone.utc)
            domain_age_days = max(0, (now - creation_date).days)
            creation_week = creation_date.strftime("%Y-W%W")

        # 2. Parse Registrar
        registrar = None
        for entity in data.get("entities", []):
            roles = entity.get("roles", [])
            if "registrar" in roles:
                vcard = entity.get("vcardArray", [])
                if len(vcard) > 1 and isinstance(vcard[1], list):
                    for entry in vcard[1]:
                        if entry[0] == "fn":
                            registrar = str(entry[3])
                            break
                if not registrar and "handle" in entity:
                    registrar = str(entity["handle"])

        # 3. Parse Nameservers
        nameservers: list[str] = []
        for ns in data.get("nameservers", []):
            ldh_name = ns.get("ldhName")
            if ldh_name:
                nameservers.append(ldh_name.lower().strip())

        return RdapResult(
            domain=cleaned_domain,
            domain_age_days=domain_age_days,
            creation_date=creation_date,
            creation_week=creation_week,
            registrar=registrar,
            nameservers=sorted(nameservers),
            raw_status="ok",
        )

    except Exception as exc:
        logger.debug("RDAP lookup failed for %s: %s", cleaned_domain, exc)
        return RdapResult(
            domain=cleaned_domain,
            error=str(exc),
        )

"""Enrichment Agent for Financial Payee Identifiers.

Resolves UPI handles to PSP and sponsor banks using official NPCI mapping, parses upi://
deep links, derives 4-letter bank codes from IFSC, detects crypto rails, and enforces
strict privacy/data-minimization (no holder name lookups).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse

import yaml
from pydantic import BaseModel, Field

from app.models.case import Case, CaseEvent

logger = logging.getLogger("sting.enrichment")

UPI_PSP_PATHS = [
    Path(__file__).resolve().parent.parent.parent / "data" / "upi_psp.yaml",
    Path(__file__).resolve().parent.parent / "data" / "upi_psp.yaml",
    Path("./data/upi_psp.yaml"),
]

IFSC_REGEX = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
ACCOUNT_REGEX = re.compile(r"^\d{8,20}$")
ETH_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")
BTC_REGEX = re.compile(r"^(1|3)[a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$")
TRON_REGEX = re.compile(r"^T[a-zA-Z0-9]{33}$")

# Cached handles mapping
_PSP_CACHE: Optional[dict[str, dict[str, str]]] = None


def get_upi_psp_table() -> dict[str, dict[str, str]]:
    """Loads and caches the official NPCI UPI handle mapping table."""
    global _PSP_CACHE
    if _PSP_CACHE is not None:
        return _PSP_CACHE

    loaded: dict[str, dict[str, str]] = {}
    for p in UPI_PSP_PATHS:
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8")
                data = yaml.safe_load(content)
                if data and "handles" in data:
                    loaded = data["handles"]
                    logger.debug("Loaded %d UPI handle mappings from %s", len(loaded), p)
                    break
            except Exception as exc:
                logger.warning("Failed to load upi_psp.yaml from %s: %s", p, exc)

    _PSP_CACHE = loaded
    return _PSP_CACHE


# ==============================================================================
# Data Models
# ==============================================================================


class QrDecodedPayload(BaseModel):
    """Structured fields decoded from upi://pay deep links or QR codes."""

    payee_vpa: Optional[str] = None
    payee_name: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = "INR"
    note: Optional[str] = None
    merchant_code: Optional[str] = None
    raw_uri: Optional[str] = None


class EnrichmentResult(BaseModel):
    """Enriched financial intelligence ready for bank fraud teams and cyber cells."""

    psp_name: Optional[str] = Field(
        default=None,
        description="Resolved UPI 3rd party app (e.g. Google Pay, PhonePe, Paytm)",
    )
    sponsor_bank: Optional[str] = Field(
        default=None,
        description="Sponsor banking partner handling settlement on the UPI switch",
    )
    ifsc_bank_code: Optional[str] = Field(
        default=None,
        description="4-letter institution code derived from IFSC (e.g. HDFC, SBIN)",
    )
    bank_account_valid: Optional[bool] = Field(
        default=None,
        description="Whether bank account number meets numerical length sanity",
    )
    upi_handle: Optional[str] = Field(
        default=None,
        description="Handle suffix extracted from VPA (e.g. @okhdfcbank)",
    )
    qr_decoded: Optional[QrDecodedPayload] = Field(
        default=None,
        description="Parsed parameters from upi://pay URI or QR payload",
    )
    wallet_chain: Optional[str] = Field(
        default=None,
        description="Blockchain network family (e.g. Ethereum, Bitcoin, TRON)",
    )
    wallet_hint: Optional[str] = Field(
        default=None,
        description="Rail and token standard hint (e.g. TRC-20 USDT)",
    )
    normalized_payees: list[str] = Field(
        default_factory=list,
        description="Canonical normalized payee identifiers for correlation and reporting",
    )


# ==============================================================================
# Enrichment Logic
# ==============================================================================


def resolve_upi_handle(vpa: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Resolves handle suffix, PSP name, sponsor bank, and bank code from a UPI VPA.

    Returns:
        (handle_suffix, psp_name, sponsor_bank, bank_code)
    """
    if not vpa or "@" not in vpa:
        return None, None, None, None

    parts = vpa.strip().lower().split("@")
    if len(parts) != 2:
        return None, None, None, None

    handle = f"@{parts[1]}"
    table = get_upi_psp_table()

    if handle in table:
        entry = table[handle]
        return (
            handle,
            entry.get("psp_name", "Unknown"),
            entry.get("sponsor_bank", "Unknown"),
            entry.get("bank_code", "Unknown"),
        )

    # NPCI list strict compliance: Unknown if unverified
    return handle, "Unknown", "Unknown", "Unknown"


def parse_upi_deep_link(uri_or_text: Optional[str]) -> Optional[QrDecodedPayload]:
    """Parses upi://pay deep links into structured parameters."""
    if not uri_or_text:
        return None

    cleaned = uri_or_text.strip()
    if not cleaned.lower().startswith("upi://pay"):
        return None

    try:
        parsed = urlparse(cleaned)
        qs = parse_qs(parsed.query)

        def _get_first(key: str) -> Optional[str]:
            val_list = qs.get(key)
            if val_list and len(val_list) > 0:
                return unquote(val_list[0]).strip()
            return None

        vpa = _get_first("pa")
        name = _get_first("pn")
        am_str = _get_first("am")
        cu = _get_first("cu") or "INR"
        tn = _get_first("tn")
        mc = _get_first("mc")

        amount: Optional[float] = None
        if am_str:
            try:
                amount = float(am_str)
            except ValueError:
                pass

        return QrDecodedPayload(
            payee_vpa=vpa.lower() if vpa else None,
            payee_name=name,
            amount=amount,
            currency=cu,
            note=tn,
            merchant_code=mc,
            raw_uri=cleaned[:1024],
        )
    except Exception as exc:
        logger.warning("Failed to parse upi://pay URI %s: %s", cleaned, exc)
        return None


def derive_bank_from_ifsc(ifsc: Optional[str]) -> Optional[str]:
    """Derives 4-letter bank institution code from IFSC format."""
    if not ifsc:
        return None
    cleaned = ifsc.strip().upper()
    if IFSC_REGEX.match(cleaned):
        return cleaned[:4]
    return None


def detect_wallet_chain(address: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Detects blockchain network by public key and address structure."""
    if not address:
        return None, None
    addr = address.strip()

    if ETH_REGEX.match(addr):
        return "Ethereum (EVM)", "EVM address format (ETH / BSC / Polygon)"
    if BTC_REGEX.match(addr):
        return "Bitcoin", "Bitcoin address (Legacy / SegWit)"
    if TRON_REGEX.match(addr):
        return "TRON", "TRON TRC-20 address (commonly used for USDT transfers)"

    return None, None


# ==============================================================================
# Agent Execution Seam
# ==============================================================================


async def run_enrichment(case: Case) -> EnrichmentResult:
    """Enriches extracted case identifiers without collecting excessive PII.

    Never fails the case on partial or unparseable inputs.
    """
    det = case.detonation_result or {}
    raw_vpa = det.get("payee_vpa") or case.input_payee
    if not raw_vpa and case.extracted_upi_ids:
        raw_vpa = case.extracted_upi_ids[0]

    qr_raw = det.get("qr_payload")
    account_num = det.get("account_number")
    raw_ifsc = det.get("ifsc")
    wallet_addr = det.get("wallet_address")

    # 1. Parse QR / Deep Link
    qr_decoded = parse_upi_deep_link(qr_raw)
    if qr_decoded and qr_decoded.payee_vpa and not raw_vpa:
        raw_vpa = qr_decoded.payee_vpa

    # 2. Resolve UPI Handle & PSP Bank
    handle_suffix: Optional[str] = None
    psp_name: Optional[str] = None
    sponsor_bank: Optional[str] = None
    bank_code: Optional[str] = None

    if raw_vpa:
        handle_suffix, psp_name, sponsor_bank, bank_code = resolve_upi_handle(raw_vpa)

    # 3. Validate Bank Account & IFSC
    ifsc_bank = derive_bank_from_ifsc(raw_ifsc)
    if not ifsc_bank and bank_code and bank_code != "Unknown":
        ifsc_bank = bank_code

    account_valid: Optional[bool] = None
    if account_num:
        clean_acc = re.sub(r"[\s\-]", "", str(account_num))
        account_valid = bool(ACCOUNT_REGEX.match(clean_acc))

    # 4. Detect Wallet Chain
    wallet_chain, wallet_hint = detect_wallet_chain(wallet_addr)

    # 5. Build Canonical Payees List
    normalized: list[str] = []
    if raw_vpa:
        normalized.append(raw_vpa.lower().strip())
    if qr_decoded and qr_decoded.payee_vpa and qr_decoded.payee_vpa.lower() not in normalized:
        normalized.append(qr_decoded.payee_vpa.lower())
    if account_num:
        clean_acc = re.sub(r"[\s\-]", "", str(account_num))
        acc_key = f"bank:{clean_acc}"
        if raw_ifsc:
            acc_key += f":{raw_ifsc.upper()}"
        normalized.append(acc_key)
    if wallet_addr:
        normalized.append(f"wallet:{wallet_addr.strip()}")

    result = EnrichmentResult(
        psp_name=psp_name,
        sponsor_bank=sponsor_bank,
        ifsc_bank_code=ifsc_bank,
        bank_account_valid=account_valid,
        upi_handle=handle_suffix,
        qr_decoded=qr_decoded,
        wallet_chain=wallet_chain,
        wallet_hint=wallet_hint,
        normalized_payees=normalized,
    )

    # Persist enrichment result
    case.enrichment_result = result.model_dump()
    return result

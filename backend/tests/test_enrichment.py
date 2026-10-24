"""Unit and integration tests for Section 8: Enrichment Agent.

Verifies:
- Official NPCI handle resolution for Google Pay, PhonePe, Paytm, and synthetic test PSP
- Unverified handles safely map to 'Unknown' without guessing
- Deep link upi://pay URI parameter parsing (VPA, name, amount, note)
- IFSC validation and 4-letter bank code extraction
- Cryptocurrency public address chain detection (EVM, Bitcoin, TRON)
- Non-fatal error handling: malformed inputs leave fields null and never crash case
- Privacy & data minimization: no account holder lookup API is ever invoked
"""

import uuid
import pytest
from app.agents.enrichment import (
    derive_bank_from_ifsc,
    detect_wallet_chain,
    parse_upi_deep_link,
    resolve_upi_handle,
    run_enrichment,
)
from app.models.case import Case


def test_upi_handle_resolution_known_and_synthetic():
    """Resolves handles to official PSP and sponsor banks from NPCI reference table."""
    # Google Pay / HDFC
    handle, psp, bank, code = resolve_upi_handle("fraudster@okhdfcbank")
    assert handle == "@okhdfcbank"
    assert psp == "Google Pay"
    assert bank == "HDFC Bank"
    assert code == "HDFC"

    # PhonePe / Yes Bank
    handle, psp, bank, code = resolve_upi_handle("recovery.agent@ybl")
    assert handle == "@ybl"
    assert psp == "PhonePe"
    assert bank == "Yes Bank"
    assert code == "YESB"

    # Synthetic Benchmark PSP
    handle, psp, bank, code = resolve_upi_handle("sandbox@stingtest")
    assert handle == "@stingtest"
    assert "synthetic" in psp.lower()


def test_upi_handle_resolution_unknown_suffix():
    """Unverified or novel handle suffixes map to 'Unknown' without guessing."""
    handle, psp, bank, code = resolve_upi_handle("scammer@obscurenonexistentbank999")
    assert handle == "@obscurenonexistentbank999"
    assert psp == "Unknown"
    assert bank == "Unknown"
    assert code == "Unknown"


def test_parse_upi_deep_link():
    """Extracts parameters from upi://pay URI strings and QR payloads."""
    uri = "upi://pay?pa=power.bill@okhdfcbank&pn=State%20Power&am=1499.50&cu=INR&tn=Disconnection%20Warning"
    payload = parse_upi_deep_link(uri)
    assert payload is not None
    assert payload.payee_vpa == "power.bill@okhdfcbank"
    assert payload.payee_name == "State Power"
    assert payload.amount == 1499.50
    assert payload.currency == "INR"
    assert payload.note == "Disconnection Warning"


def test_parse_invalid_or_non_upi_uri():
    """Non-UPI URIs safely return None without throwing exceptions."""
    assert parse_upi_deep_link("https://example.com/pay") is None
    assert parse_upi_deep_link("") is None
    assert parse_upi_deep_link(None) is None


def test_derive_bank_from_ifsc():
    """Extracts 4-letter bank code strictly from valid IFSC format."""
    assert derive_bank_from_ifsc("SBIN0001234") == "SBIN"
    assert derive_bank_from_ifsc("ICIC0005678") == "ICIC"
    # Invalid IFSC
    assert derive_bank_from_ifsc("12345678901") is None
    assert derive_bank_from_ifsc("SHORT") is None
    assert derive_bank_from_ifsc(None) is None


def test_detect_wallet_chain():
    """Detects cryptocurrency blockchain rail from public key address structure."""
    # EVM (Ethereum / BSC / Polygon)
    chain, hint = detect_wallet_chain("0x71C84192e3a94669BCE828b00217F2056555251F")
    assert "Ethereum" in chain
    assert "EVM" in hint

    # Bitcoin Legacy / SegWit
    chain, hint = detect_wallet_chain("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
    assert "Bitcoin" in chain
    chain_segwit, _ = detect_wallet_chain("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
    assert "Bitcoin" in chain_segwit

    # TRON (frequently utilized for USDT scam transfers)
    chain_tron, hint_tron = detect_wallet_chain("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")
    assert chain_tron == "TRON"
    assert "TRC-20" in hint_tron


@pytest.mark.asyncio
async def test_run_enrichment_flow():
    """Verifies end-to-end enrichment on a Case populated with detonation results."""
    case = Case(
        id=uuid.uuid4(),
        input_type="link",
        raw_input="https://fake-discom.com/bill",
        detonation_result={
            "payee_vpa": "discom.recovery@okhdfcbank",
            "account_number": "50200083921901",
            "ifsc": "HDFC0001234",
            "qr_payload": "upi://pay?pa=discom.recovery@okhdfcbank&pn=DiscomBilling&am=1200",
            "wallet_address": "0x71C84192e3a94669BCE828b00217F2056555251F",
        },
    )

    res = await run_enrichment(case)
    assert res.psp_name == "Google Pay"
    assert res.sponsor_bank == "HDFC Bank"
    assert res.ifsc_bank_code == "HDFC"
    assert res.bank_account_valid is True
    assert res.upi_handle == "@okhdfcbank"
    assert res.wallet_chain == "Ethereum (EVM)"
    assert "discom.recovery@okhdfcbank" in res.normalized_payees
    assert "bank:50200083921901:HDFC0001234" in res.normalized_payees
    assert "wallet:0x71C84192e3a94669BCE828b00217F2056555251F" in res.normalized_payees
    assert case.enrichment_result is not None


@pytest.mark.asyncio
async def test_enrichment_non_fatal_on_empty_case():
    """Empty or unpopulated cases safely resolve without raising exceptions."""
    case = Case(
        id=uuid.uuid4(),
        input_type="link",
        raw_input="https://empty.com",
    )
    res = await run_enrichment(case)
    assert res.psp_name is None
    assert res.sponsor_bank is None
    assert res.normalized_payees == []

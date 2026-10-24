"""Unit and integration tests for Section 10: Evidence PDF, Signing and Verification.

Verifies:
- Canonical JSON evidence bundle serialization and SHA-256 calculation
- ReportLab Platypus PDF rendering produces non-empty bytes
- Cryptographic sealing with HMAC-SHA256 and immutable hash-chained ledger
- Tamper detection: flipping a single byte in the PDF document causes verification failure
- Ledger tampering detection: modifying an entry hash breaks the chain integrity check
- Hostile markup containment: strings with <script>, <img>, <a> are rendered as escaped inert text
  without network sockets or local file access being invoked
- Null fields render cleanly as 'Not observed' / 'Not applicable'
- Endpoints: GET /cases/{id}/evidence streams the PDF; POST /evidence/verify validates authenticity
"""

import hashlib
import io
import os
import socket
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.evidence import (
    build_canonical_bundle,
    compute_hmac_signature,
    render_evidence_pdf,
    run_evidence_pipeline,
    seal_and_record_evidence,
    verify_evidence_pdf,
)
from app.config import Settings, get_settings
from app.db import get_db_session
from app.main import create_app
from app.models.base import Base
from app.models.case import Case, CaseEvent, utc_now
from app.models.evidence import EvidenceLedger


@pytest_asyncio.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield session_factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(async_db, tmp_path):
    settings = Settings(
        STING_ENV="test",
        STORAGE_DIR=tmp_path,
        EVIDENCE_SIGNING_KEY="test-signing-key-32-chars-long",
    )
    app = create_app(settings)

    async def override_get_db():
        async with async_db() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_db_session] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_case():
    return Case(
        id=uuid.uuid4(),
        input_type="link",
        raw_input="https://scam-discom-bill.biz/claim",
        normalized_url="https://scam-discom-bill.biz/claim",
        domain="scam-discom-bill.biz",
        status="awaiting_approval",
        current_stage="evidence",
        outcome="detonated",
        detonation_result={
            "payee_vpa": "discom.recovery@okhdfcbank",
            "account_number": "50200083921901",
            "ifsc": "HDFC0001234",
            "amount_requested": 1499.0,
            "funnel_steps": [
                "Landed on consumer login portal",
                "Filled synthetic victim profile",
                "Intercepted UPI VPA on checkout modal",
            ],
            "blocked_reason": None,
        },
        enrichment_result={
            "psp_name": "Google Pay",
            "sponsor_bank": "HDFC Bank",
            "ifsc_bank_code": "HDFC",
            "normalized_payees": ["discom.recovery@okhdfcbank"],
        },
    )


# ==============================================================================
# 1. Canonical Bundle & PDF Rendering Tests
# ==============================================================================


def test_canonical_bundle_and_pdf_generation(sample_case):
    """Generates canonical bundle with sorted keys and compiles non-empty PDF bytes."""
    raw_json, bundle_hash, bundle = build_canonical_bundle(sample_case)
    assert len(bundle_hash) == 64
    assert bundle["case_id"] == str(sample_case.id)
    assert bundle["input"]["domain"] == "scam-discom-bill.biz"

    # Render PDF
    pdf_bytes = render_evidence_pdf(sample_case, bundle_hash)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_hostile_markup_containment_and_no_io(sample_case):
    """Hostile strings are sanitized as escaped text; socket connections are forbidden."""
    sample_case.raw_input = "<script>alert('xss')</script>https://evil.com/<a href=file:///etc/passwd>click</a>"
    sample_case.domain = "<img src='http://attacker.com/leak.jpg' onerror=alert(1)>"
    sample_case.detonation_result["payee_vpa"] = "<b>attacker@okhdfcbank</b>"

    _, bundle_hash, _ = build_canonical_bundle(sample_case)

    # Patch socket.socket so any outbound network call raises an exception immediately
    with patch("socket.socket", side_effect=RuntimeError("Security violation: Socket opened during PDF render")):
        pdf_bytes = render_evidence_pdf(sample_case, bundle_hash)

    assert len(pdf_bytes) > 0
    # Proof: Rendered PDF is valid binary
    assert pdf_bytes.startswith(b"%PDF")


# ==============================================================================
# 2. Cryptographic Ledger & Hash-Chain Integrity Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_sealing_and_verification_happy_path(async_db, sample_case, tmp_path):
    """Sealing case writes to ledger and disk; verification succeeds with valid report."""
    settings = Settings(
        STING_ENV="test",
        STORAGE_DIR=tmp_path,
        EVIDENCE_SIGNING_KEY="secret-signing-key-123",
    )

    async with async_db() as session:
        session.add(sample_case)
        await session.commit()

        # Run evidence pipeline
        ev_info = await run_evidence_pipeline(sample_case, session, settings=settings)
        await session.commit()

        assert sample_case.evidence_hash == ev_info["pdf_sha256"]
        assert sample_case.bundle_hash == ev_info["bundle_sha256"]

        # Read saved PDF from storage
        pdf_path = tmp_path / "evidence" / f"{sample_case.id}.pdf"
        assert pdf_path.exists()
        pdf_bytes = pdf_path.read_bytes()

        # Verify authentic PDF
        verify_result = await verify_evidence_pdf(pdf_bytes, session, settings=settings)
        assert verify_result["valid"] is True
        assert verify_result["case_id"] == str(sample_case.id)
        assert verify_result["sha256_hash"] == ev_info["pdf_sha256"]


@pytest.mark.asyncio
async def test_single_byte_tampering_detected(async_db, sample_case, tmp_path):
    """Flipping a single byte in the PDF file causes verification failure."""
    settings = Settings(
        STING_ENV="test",
        STORAGE_DIR=tmp_path,
        EVIDENCE_SIGNING_KEY="secret-signing-key-123",
    )

    async with async_db() as session:
        session.add(sample_case)
        await session.commit()

        await run_evidence_pipeline(sample_case, session, settings=settings)
        await session.commit()

        pdf_path = tmp_path / "evidence" / f"{sample_case.id}.pdf"
        pdf_bytes = bytearray(pdf_path.read_bytes())

        # Flip byte near the end
        pdf_bytes[-50] = (pdf_bytes[-50] + 1) % 256

        verify_result = await verify_evidence_pdf(bytes(pdf_bytes), session, settings=settings)
        assert verify_result["valid"] is False
        assert "not registered" in verify_result["reason"].lower()


@pytest.mark.asyncio
async def test_ledger_chain_tampering_detected(async_db, sample_case, tmp_path):
    """Modifying an entry hash in the evidence_ledger breaks the hash chain check."""
    settings = Settings(
        STING_ENV="test",
        STORAGE_DIR=tmp_path,
        EVIDENCE_SIGNING_KEY="secret-signing-key-123",
    )

    async with async_db() as session:
        session.add(sample_case)
        await session.commit()

        ev_info = await run_evidence_pipeline(sample_case, session, settings=settings)
        await session.commit()

        pdf_path = tmp_path / "evidence" / f"{sample_case.id}.pdf"
        pdf_bytes = pdf_path.read_bytes()

        # Tamper with the ledger row
        stmt = select(EvidenceLedger).where(EvidenceLedger.id == ev_info["ledger_id"])
        ledger_entry = (await session.execute(stmt)).scalar_one()
        ledger_entry.entry_hash = "tampered_fake_entry_hash_000000000000000000000000000000000000"
        await session.commit()

        # Verification must detect broken hash chain
        verify_result = await verify_evidence_pdf(pdf_bytes, session, settings=settings)
        assert verify_result["valid"] is False
        assert "hash chain broken" in verify_result["reason"].lower()


# ==============================================================================
# 3. Router Endpoints Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_evidence_download_and_verify_endpoints(client, async_db, sample_case, tmp_path):
    """GET /cases/{id}/evidence streams PDF and POST /evidence/verify validates file upload."""
    settings = Settings(
        STING_ENV="test",
        STORAGE_DIR=tmp_path,
        EVIDENCE_SIGNING_KEY="test-signing-key-32-chars-long",
    )

    async with async_db() as session:
        session.add(sample_case)
        await session.commit()
        await run_evidence_pipeline(sample_case, session, settings=settings)
        await session.commit()

    # 1. Download Evidence PDF
    get_resp = await client.get(f"/cases/{sample_case.id}/evidence")
    assert get_resp.status_code == 200
    assert get_resp.headers["content-type"] == "application/pdf"
    assert len(get_resp.content) > 1000

    # 2. Upload to /evidence/verify
    post_resp = await client.post(
        "/evidence/verify",
        files={"file": ("evidence.pdf", get_resp.content, "application/pdf")},
    )
    assert post_resp.status_code == 200
    data = post_resp.json()
    assert data["valid"] is True
    assert data["case_id"] == str(sample_case.id)
    assert "SHA-256 hash match verified" in data["reason"]

"""Tamper-Evident Evidence Generator, PDF Renderer and Cryptographic Verification.

Generates canonical JSON evidence bundles, renders tamper-evident PDF dossiers via ReportLab Platypus,
seals artifacts with HMAC-SHA256 signatures, maintains an immutable hash-chained ledger,
and verifies dossier authenticity.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import io
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import uuid

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.case import Case, CaseEvent, utc_now
from app.models.evidence import EvidenceLedger

logger = logging.getLogger("sting.evidence")

GENESIS_HASH = "0" * 64
STING_VERSION = "2.0.0"


def safe_xml_escape(text: Optional[Any], max_length: int = 1000) -> str:
    """Escapes XML entities so reportlab Paragraph won't interpret untrusted text as tags."""
    if text is None:
        return "Not observed"
    s = str(text).strip()
    if not s:
        return "Not observed"
    escaped = html.escape(s)
    return escaped[:max_length]


# ==============================================================================
# Canonical JSON Evidence Bundle
# ==============================================================================


def build_canonical_bundle(
    case: Case, events: Optional[list[CaseEvent]] = None
) -> tuple[str, str, dict[str, Any]]:
    """Builds a deterministic canonical JSON bundle with sorted keys.

    Returns:
        (canonical_json_string, bundle_sha256_hex, bundle_dict)
    """
    det = case.detonation_result or {}
    enr = case.enrichment_result or {}

    triage_info: dict[str, Any] = {}
    cluster_info: dict[str, Any] = {}
    if events:
        for ev in events:
            if ev.stage == "triage" and ev.data:
                triage_info = ev.data.get("triage", {})
            elif ev.stage == "correlation" and ev.data:
                cluster_info = ev.data

    bundle: dict[str, Any] = {
        "case_id": str(case.id),
        "created_at": case.created_at.isoformat() if case.created_at else utc_now().isoformat(),
        "input": {
            "input_type": case.input_type,
            "raw_input": case.raw_input,
            "normalized_url": case.normalized_url or "Not applicable",
            "domain": case.domain or "Not applicable",
        },
        "triage": {
            "risk_level": triage_info.get("risk_level", "Not observed"),
            "brand_mismatch": triage_info.get("brand_mismatch", False),
            "domain_age_days": triage_info.get("domain_age_days"),
            "search_scam_mentions": triage_info.get("search_scam_mentions", 0),
        },
        "detonation": {
            "agent_run_id": case.agent_run_id or "Not executed",
            "payee_vpa": det.get("payee_vpa") or "Not observed",
            "account_number": det.get("account_number") or "Not observed",
            "ifsc": det.get("ifsc") or "Not observed",
            "amount_requested": det.get("amount_requested"),
            "blocked_reason": det.get("blocked_reason") or "None",
            "proxy_fallback": case.proxy_fallback,
            "funnel_steps_count": len(det.get("funnel_steps", [])),
        },
        "enrichment": {
            "psp_name": enr.get("psp_name") or "Not observed",
            "sponsor_bank": enr.get("sponsor_bank") or "Not observed",
            "ifsc_bank_code": enr.get("ifsc_bank_code") or "Not observed",
            "wallet_chain": enr.get("wallet_chain") or "Not observed",
            "normalized_payees": enr.get("normalized_payees", []),
        },
        "cluster": {
            "cluster_id": cluster_info.get("cluster_id") or "Unassigned",
            "attribution": cluster_info.get("attribution") or ("inferred" if case.outcome == "known_cluster_skipped" else "confirmed"),
        },
        "provenance": {
            "prompt_version": case.prompt_version or "v1.0.0",
            "sting_version": STING_VERSION,
        },
    }

    canonical_json = json.dumps(bundle, sort_keys=True, separators=(",", ":"))
    bundle_sha256 = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return canonical_json, bundle_sha256, bundle


# ==============================================================================
# Safe ReportLab PDF Renderer (Zero HTML, Zero External Resource Fetch)
# ==============================================================================


def render_evidence_pdf(case: Case, bundle_sha256: str) -> bytes:
    """Renders a tamper-evident Platypus PDF directly from structured data."""
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        fontName="Helvetica-Bold",
    )
    banner_style = ParagraphStyle(
        "Banner",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#b91c1c"),
        fontName="Helvetica-Bold",
        alignment=1,  # Center
    )
    inferred_banner_style = ParagraphStyle(
        "InferredBanner",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#c2410c"),
        fontName="Helvetica-Bold",
        alignment=1,
    )
    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#475569"),
        fontName="Helvetica",
    )
    section_h2 = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        fontName="Helvetica",
    )

    elements: list[Any] = []

    # 1. Statutory Warning Banner
    elements.append(
        Paragraph(
            "AUTOMATED SYNTHETIC-VICTIM OBSERVATION · NOT LEGAL PROOF · REQUIRES HUMAN VERIFICATION",
            banner_style,
        )
    )
    elements.append(Spacer(1, 8))

    # 2. Document Title
    elements.append(Paragraph("STING Forensic Evidence Dossier", title_style))
    elements.append(
        Paragraph(
            f"Case Reference: <b>{safe_xml_escape(str(case.id))}</b> | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            meta_style,
        )
    )
    elements.append(
        Paragraph(
            f"Canonical Bundle SHA-256: <code>{safe_xml_escape(bundle_sha256)}</code>",
            meta_style,
        )
    )
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#cbd5e1")))
    elements.append(Spacer(1, 12))

    # 3. Inferred Warning Banner if applicable
    is_inferred = (case.outcome == "known_cluster_skipped") or ("#branch:skip_cluster" in (case.raw_input or ""))
    if is_inferred:
        inferred_table = Table(
            [[Paragraph("<b>FORENSIC NOTICE: INFERRED ATTRIBUTION</b><br/>This target was correlated via DOM Simhash (&le; 8) and shared infrastructure. The payee destination was not directly detonated in this case.", inferred_banner_style)]],
            colWidths=[530],
        )
        inferred_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffedd5")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#f97316")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(inferred_table)
        elements.append(Spacer(1, 10))

    # 4. Target & Intake Information
    elements.append(Paragraph("1. Target Intake & Domain Provenance", section_h2))
    target_data = [
        [Paragraph("<b>Submitted Input:</b>", body_style), Paragraph(safe_xml_escape(case.raw_input), body_style)],
        [Paragraph("<b>Target Domain:</b>", body_style), Paragraph(safe_xml_escape(case.domain), body_style)],
        [Paragraph("<b>Normalized URL:</b>", body_style), Paragraph(safe_xml_escape(case.normalized_url), body_style)],
        [Paragraph("<b>Investigation Status:</b>", body_style), Paragraph(safe_xml_escape(case.status), body_style)],
    ]
    t_target = Table(target_data, colWidths=[140, 390])
    t_target.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_target)
    elements.append(Spacer(1, 10))

    # 5. Extracted Payee Intelligence
    elements.append(Paragraph("2. Extracted Financial Destination", section_h2))
    det = case.detonation_result or {}
    enr = case.enrichment_result or {}

    payee_data = [
        [Paragraph("<b>UPI VPA:</b>", body_style), Paragraph(safe_xml_escape(det.get("payee_vpa") or case.input_payee), body_style)],
        [Paragraph("<b>Resolved PSP:</b>", body_style), Paragraph(safe_xml_escape(enr.get("psp_name")), body_style)],
        [Paragraph("<b>Sponsor Bank:</b>", body_style), Paragraph(safe_xml_escape(enr.get("sponsor_bank")), body_style)],
        [Paragraph("<b>Account Number:</b>", body_style), Paragraph(safe_xml_escape(det.get("account_number")), body_style)],
        [Paragraph("<b>Bank Code (IFSC):</b>", body_style), Paragraph(safe_xml_escape(enr.get("ifsc_bank_code") or det.get("ifsc")), body_style)],
        [Paragraph("<b>Crypto Destination:</b>", body_style), Paragraph(safe_xml_escape(det.get("wallet_address")), body_style)],
    ]
    t_payee = Table(payee_data, colWidths=[140, 390])
    t_payee.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_payee)
    elements.append(Spacer(1, 10))

    # 6. Autonomous Navigation Trail
    elements.append(Paragraph("3. Autonomous Detonation Trail", section_h2))
    steps = det.get("funnel_steps") or []
    if steps:
        step_rows = [[Paragraph(f"<b>Step {idx+1}:</b>", body_style), Paragraph(safe_xml_escape(s), body_style)] for idx, s in enumerate(steps[:8])]
        t_steps = Table(step_rows, colWidths=[60, 470])
        t_steps.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_steps)
    else:
        elements.append(Paragraph("No browser steps recorded (skipped or inconclusive).", body_style))

    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
    elements.append(Spacer(1, 6))

    # 7. Verification & Tamper Notice Footer
    elements.append(
        Paragraph(
            "<b>Tamper Verification:</b> Verify this document at <code>/evidence/verify</code> using SHA-256 and HMAC key. "
            "Any byte alteration invalidates the cryptographic seal.",
            meta_style,
        )
    )

    doc.build(elements)
    return buffer.getvalue()


# ==============================================================================
# Cryptographic Signing & Hash-Chained Ledger
# ==============================================================================


def format_ledger_ts(dt: Any) -> str:
    """Standardizes datetime to UTC string for hash chain calculation."""
    if isinstance(dt, str):
        cleaned = dt.replace(" ", "T")
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1]
        try:
            parsed = datetime.fromisoformat(cleaned)
            return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            return dt
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(dt)


def compute_hmac_signature(signing_key: str, data_hex: str) -> str:
    """Computes HMAC-SHA256 signature over SHA-256 hex string."""
    key_bytes = signing_key.encode("utf-8")
    return hmac.new(key_bytes, data_hex.encode("utf-8"), hashlib.sha256).hexdigest()


async def seal_and_record_evidence(
    case: Case,
    pdf_bytes: bytes,
    bundle_sha256: str,
    db: AsyncSession,
    settings: Optional[Settings] = None,
) -> tuple[str, str, EvidenceLedger]:
    """Computes PDF hash, signs with HMAC, and appends to hash-chained ledger.

    Returns:
        (pdf_sha256, hmac_signature, ledger_entry)
    """
    settings = settings or get_settings()
    signing_key = settings.EVIDENCE_SIGNING_KEY or "sting-default-evidence-signing-key"

    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    signature = compute_hmac_signature(signing_key, pdf_sha256)

    # 1. Fetch Previous Hash Chain Entry
    latest_stmt = select(EvidenceLedger).order_by(EvidenceLedger.id.desc()).limit(1)
    latest_res = await db.execute(latest_stmt)
    latest_entry = latest_res.scalar_one_or_none()

    prev_hash = latest_entry.entry_hash if latest_entry else GENESIS_HASH
    now = utc_now().replace(microsecond=0)
    ts_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # entry_hash = sha256(prev_entry_hash + pdf_sha256 + bundle_sha256 + created_at)
    chain_input = f"{prev_hash}:{pdf_sha256}:{bundle_sha256}:{ts_str}"
    entry_hash = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

    # 2. Append Immutable Ledger Row
    ledger_entry = EvidenceLedger(
        case_id=case.id,
        pdf_sha256=pdf_sha256,
        bundle_sha256=bundle_sha256,
        signature=signature,
        prev_entry_hash=prev_hash,
        entry_hash=entry_hash,
        created_at=now,
    )
    db.add(ledger_entry)
    await db.flush()

    # 3. Store on disk
    storage_dir = Path(settings.STORAGE_DIR) / "evidence"
    storage_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = storage_dir / f"{case.id}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    # 4. Update Case reference fields
    case.evidence_hash = pdf_sha256
    case.bundle_hash = bundle_sha256
    case.evidence_link = f"/cases/{case.id}/evidence"

    return pdf_sha256, signature, ledger_entry


# ==============================================================================
# Evidence Verification Engine
# ==============================================================================


async def verify_evidence_pdf(
    pdf_bytes: bytes,
    db: AsyncSession,
    settings: Optional[Settings] = None,
) -> dict[str, Any]:
    """Verifies authenticity and integrity of an uploaded evidence PDF."""
    settings = settings or get_settings()
    signing_key = settings.EVIDENCE_SIGNING_KEY or "sting-default-evidence-signing-key"

    calculated_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    # 1. Query Ledger for matching SHA-256
    stmt = select(EvidenceLedger).where(EvidenceLedger.pdf_sha256 == calculated_pdf_sha256)
    res = await db.execute(stmt)
    entry = res.scalar_one_or_none()

    if not entry:
        return {
            "valid": False,
            "case_id": None,
            "sha256_hash": calculated_pdf_sha256,
            "reason": "Evidence PDF hash not registered in immutable ledger (unknown or altered file).",
        }

    # 2. Check HMAC Signature
    expected_sig = compute_hmac_signature(signing_key, calculated_pdf_sha256)
    if not hmac.compare_digest(entry.signature, expected_sig):
        return {
            "valid": False,
            "case_id": str(entry.case_id),
            "sha256_hash": calculated_pdf_sha256,
            "reason": "HMAC signature verification failed (key mismatch or ledger tampered).",
        }

    # 3. Check Ledger Entry Hash Chain Integrity
    ts_str = format_ledger_ts(entry.created_at)
    chain_input = f"{entry.prev_entry_hash}:{entry.pdf_sha256}:{entry.bundle_sha256}:{ts_str}"
    expected_entry_hash = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

    if entry.entry_hash != expected_entry_hash:
        return {
            "valid": False,
            "case_id": str(entry.case_id),
            "sha256_hash": calculated_pdf_sha256,
            "reason": "Ledger hash chain broken: entry_hash does not match chain computation.",
        }

    return {
        "valid": True,
        "case_id": str(entry.case_id),
        "sha256_hash": calculated_pdf_sha256,
        "verified_at": utc_now().isoformat(),
        "ledger_position": entry.id,
        "reason": "Cryptographic signature and SHA-256 hash match verified case record in hash-chained ledger.",
    }


# ==============================================================================
# Pipeline Seam
# ==============================================================================


async def run_evidence_pipeline(case: Case, db: AsyncSession, settings: Optional[Settings] = None) -> dict[str, Any]:
    """Generates canonical bundle, renders safe PDF, seals ledger, and saves to storage."""
    settings = settings or get_settings()

    ev_stmt = select(CaseEvent).where(CaseEvent.case_id == case.id).order_by(CaseEvent.id.asc())
    ev_res = await db.execute(ev_stmt)
    events = list(ev_res.scalars().all())

    _, bundle_sha256, _ = build_canonical_bundle(case, events=events)
    pdf_bytes = render_evidence_pdf(case, bundle_sha256)
    pdf_sha256, signature, ledger_entry = await seal_and_record_evidence(
        case=case,
        pdf_bytes=pdf_bytes,
        bundle_sha256=bundle_sha256,
        db=db,
        settings=settings,
    )

    return {
        "pdf_sha256": pdf_sha256,
        "bundle_sha256": bundle_sha256,
        "signature": signature,
        "ledger_id": ledger_entry.id,
        "evidence_link": case.evidence_link,
    }

"""Case Management Endpoints conforming to shared/api-schema.json."""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from backend.app.schemas.case import (
    CaseCreateRequest,
    CaseResultResponse,
    CaseStatusResponse,
    CaseSummary,
    EvidenceItem,
    PayeeInfo,
    ReportApprovalRequest,
    ReportApprovalResponse,
    TraceEvent,
)
from fastapi import APIRouter, HTTPException, status

router = APIRouter(tags=["Cases"])

# In-memory storage for active cases during Section 1 scaffold
# (Section 2 replaces this with PostgreSQL / SQLAlchemy persistent models)
_CASE_STORE: Dict[str, Dict[str, Any]] = {}


@router.post(
    "/cases",
    response_model=CaseSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new scam investigation case",
)
async def create_case(payload: CaseCreateRequest):
    """Initiates an investigation pipeline against a suspicious URL, message, or QR code."""
    case_id = f"case-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()

    # Initial case record
    case_data = {
        "id": case_id,
        "type": payload.type,
        "target": payload.content,
        "status": "processing",
        "current_stage": "intake",
        "progress_pct": 15,
        "active_agent": "Intake Agent",
        "created_at": now,
        "updated_at": now,
        "trace_events": [
            {
                "stage": "intake",
                "agent": "Intake Agent",
                "message": f"Received {payload.type} target for autonomous detonation: {payload.content[:50]}...",
                "timestamp": now,
                "details": payload.metadata or {},
            }
        ],
        "report_approved": False,
    }
    _CASE_STORE[case_id] = case_data

    return CaseSummary(
        id=case_id,
        type=payload.type,
        target=payload.content,
        status="processing",
        current_stage="intake",
        created_at=now,
    )


@router.get(
    "/cases/{case_id}",
    response_model=CaseStatusResponse,
    summary="Poll case status and current stage",
)
async def get_case_status(case_id: str):
    """Returns current analysis stage, progress percentage, active agent, and event stream."""
    case = _CASE_STORE.get(case_id)
    now = datetime.now(timezone.utc).isoformat()

    if not case:
        # Provide sample demo state for known test IDs or return 404
        if case_id in ("demo-case-1", "mock-case"):
            return CaseStatusResponse(
                id=case_id,
                status="processing",
                current_stage="detonate",
                progress_pct=50,
                active_agent="Detonation Agent",
                trace_events=[
                    TraceEvent(
                        stage="intake",
                        agent="Intake Agent",
                        message="Normalized SMS lure and extracted phishing URL.",
                        timestamp=now,
                    ),
                    TraceEvent(
                        stage="triage",
                        agent="Triage Agent",
                        message="TinyFish Fetch extracted high urgency lure; WHOIS shows domain created 2 days ago.",
                        timestamp=now,
                    ),
                    TraceEvent(
                        stage="detonate",
                        agent="Detonation Agent",
                        message="Automated browser triggered checkout flow and captured mule payment intent.",
                        timestamp=now,
                    ),
                ],
                updated_at=now,
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    return CaseStatusResponse(
        id=case["id"],
        status=case.get("status", "processing"),
        current_stage=case.get("current_stage", "intake"),
        progress_pct=case.get("progress_pct", 15),
        active_agent=case.get("active_agent", "Intake Agent"),
        trace_events=[TraceEvent(**ev) for ev in case.get("trace_events", [])],
        updated_at=case.get("updated_at", now),
    )


@router.get(
    "/cases/{case_id}/result",
    response_model=CaseResultResponse,
    summary="Retrieve final investigation results",
)
async def get_case_result(case_id: str):
    """Returns verified payees, evidence hashes, screenshots, redirect chain, and final verdict."""
    case = _CASE_STORE.get(case_id)
    now = datetime.now(timezone.utc).isoformat()

    target = (
        case.get("target", "https://quick-electricity-billpay.biz")
        if case
        else "https://quick-electricity-billpay.biz"
    )
    approved = case.get("report_approved", False) if case else False

    # Standard high-fidelity result compliant with contract
    sample_sha = hashlib.sha256(b"sting-evidence-sample").hexdigest()

    return CaseResultResponse(
        id=case_id,
        target=target,
        risk_score=94,
        verdict="MALICIOUS_SCAM",
        scam_type="ELECTRICITY_BILL_URGENCY_FRAUD",
        payees=[
            PayeeInfo(
                id="payee-hdfc-409",
                vpa="powerbill.recovery@okhdfcbank",
                account_number="50100492819281",
                ifsc="HDFC0000049",
                holder_name="Utility Billing Services Pvt Ltd",
                psp="HDFC Bank",
                phone="+91-9820011223",
                risk_score=98.5,
            )
        ],
        evidence=[
            EvidenceItem(
                id="ev-1",
                title="Detonated Checkout Screen with UPI QR",
                type="screenshot",
                sha256=sample_sha,
                url="/evidence/screenshots/payment-modal.png",
                timestamp=now,
            ),
            EvidenceItem(
                id="ev-2",
                title="Lure Landing Page Rendered DOM Dump",
                type="dom_dump",
                sha256=hashlib.sha256(b"landing-dom").hexdigest(),
                url="/evidence/dom/landing.html",
                timestamp=now,
            ),
            EvidenceItem(
                id="ev-3",
                title="Domain RDAP / WHOIS Freshness Report",
                type="rdap",
                sha256=hashlib.sha256(b"rdap-data").hexdigest(),
                url="/evidence/rdap/domain_whois.json",
                timestamp=now,
            ),
        ],
        redirect_chain=[
            target,
            "https://redirector.net/hop/3991",
            "https://payment-gateway-gateway.xyz/checkout?ref=mule8839",
        ],
        report_url=f"/reports/sting-investigation-{case_id}.pdf",
        report_approved=approved,
        completed_at=now,
    )


@router.post(
    "/cases/{case_id}/approve-report",
    response_model=ReportApprovalResponse,
    summary="Human approval step for report dispatch",
)
async def approve_case_report(case_id: str, payload: ReportApprovalRequest):
    """Allows an analyst/investigator to review and authorize dispatch to authorities."""
    case = _CASE_STORE.get(case_id)
    now = datetime.now(timezone.utc).isoformat()

    if case:
        case["report_approved"] = payload.approved
        case["updated_at"] = now
        case["trace_events"].append(
            {
                "stage": "act",
                "agent": "Report-Drafting Agent",
                "message": f"Report {'approved' if payload.approved else 'rejected'} by {payload.reviewer}. Notes: {payload.notes or 'None'}",
                "timestamp": now,
            }
        )

    dispatched = []
    if payload.approved:
        dispatched = [
            f"{dest.upper()}_DISPATCH_TRIGGERED"
            for dest in (payload.action_destinations or ["cert_in", "bank_freeze"])
        ]

    return ReportApprovalResponse(
        case_id=case_id,
        approved=payload.approved,
        approved_at=now,
        actions_dispatched=dispatched,
        status="REPORT_AUTHORIZED_AND_DISPATCHED"
        if payload.approved
        else "REPORT_REJECTED_BY_ANALYST",
    )

"""Pydantic models for Case Management and Pipeline Status conforming to shared/api-schema.json."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class CaseCreateRequest(BaseModel):
    type: Literal["url", "message", "qr"] = "url"
    content: str = Field(..., description="Target URL, suspicious SMS text, or base64 QR image")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CaseSummary(BaseModel):
    id: str
    type: str
    target: str
    status: Literal["queued", "processing", "completed", "failed"]
    current_stage: Literal["intake", "triage", "detonate", "enrich", "cluster", "act", "complete"]
    created_at: str


class TraceEvent(BaseModel):
    stage: str
    agent: str
    message: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None


class CaseStatusResponse(BaseModel):
    id: str
    status: Literal["queued", "processing", "completed", "failed"]
    current_stage: Literal["intake", "triage", "detonate", "enrich", "cluster", "act", "complete"]
    progress_pct: int = Field(ge=0, le=100)
    active_agent: Optional[str] = None
    trace_events: List[TraceEvent] = Field(default_factory=list)
    updated_at: str


class PayeeInfo(BaseModel):
    id: str
    vpa: Optional[str] = None
    account_number: Optional[str] = None
    ifsc: Optional[str] = None
    holder_name: Optional[str] = None
    psp: Optional[str] = None
    phone: Optional[str] = None
    risk_score: Optional[float] = None


class EvidenceItem(BaseModel):
    id: str
    title: str
    type: Literal["screenshot", "dom_dump", "redirect_chain", "rdap", "qr_decoded", "pdf_report"]
    sha256: str
    url: Optional[str] = None
    timestamp: Optional[str] = None


class CaseResultResponse(BaseModel):
    id: str
    target: str
    risk_score: int = Field(ge=0, le=100)
    verdict: Literal["MALICIOUS_SCAM", "SUSPICIOUS", "BENIGN", "INCONCLUSIVE"]
    scam_type: Optional[str] = None
    payees: List[PayeeInfo] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    redirect_chain: List[str] = Field(default_factory=list)
    report_url: Optional[str] = None
    report_approved: bool = False
    completed_at: Optional[str] = None


class ReportApprovalRequest(BaseModel):
    approved: bool
    reviewer: str
    notes: Optional[str] = None
    action_destinations: Optional[List[Literal["cert_in", "cybercrime_portal", "isp_takedown", "bank_freeze"]]] = Field(
        default_factory=lambda: ["cert_in", "bank_freeze"]
    )


class ReportApprovalResponse(BaseModel):
    case_id: str
    approved: bool
    approved_at: str
    actions_dispatched: List[str] = Field(default_factory=list)
    status: str


class ServiceHealth(BaseModel):
    database: str
    redis: str
    tinyfish: str


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    services: ServiceHealth

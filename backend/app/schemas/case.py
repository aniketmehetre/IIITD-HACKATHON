"""Pydantic models for Case Management and Pipeline Status conforming to shared/api-schema.yaml."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Contract Enums
CaseStatusType = Literal[
    "received",
    "intake",
    "triage",
    "detonating",
    "enriching",
    "correlating",
    "evidencing",
    "awaiting_approval",
    "done",
    "inconclusive",
    "failed",
]

OutcomeType = Literal[
    "confirmed_scam",
    "likely_benign",
    "known_payee_skipped",
    "known_site_skipped",
    "inconclusive",
    "failed",
    "payee_extracted",
    "known_payee",
    "known_cluster",
]


class CaseCreateRequest(BaseModel):
    """Payload for POST /cases."""

    input_type: Literal["link", "message"] = Field(
        ..., description="Input channel type: link or unstructured message"
    )
    raw_input: str = Field(
        ...,
        max_length=5000,
        description="Target URL or message text lure containing URLs or UPI IDs",
    )
    force_detonate: bool = Field(
        default=False,
        description="Bypass 24-hour deduplication cache and force fresh detonation",
    )


class StageEvent(BaseModel):
    """Atomic stage progress or audit log event."""

    id: str = Field(..., description="Unique event ID")
    stage: str = Field(..., description="Investigation stage")
    message: str = Field(..., description="Human-readable event description")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    level: Optional[str] = Field(default="info", description="info | warning | error")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CaseSummary(BaseModel):
    """Compact summary of an investigation case for listings and intake responses."""

    id: str
    input_type: str
    raw_input: str
    status: str
    outcome: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    is_seed: bool = False
    deduplicated: bool = False


class CaseDetail(BaseModel):
    """Full investigation case schema including live streaming URL and recent events."""

    id: str
    input_type: str
    raw_input: str
    status: str
    outcome: Optional[str] = None
    streaming_url: Optional[str] = None
    recent_events: List[StageEvent] = Field(default_factory=list)
    created_at: str
    updated_at: str


class CaseListResponse(BaseModel):
    """Paginated case listing response."""

    items: List[CaseSummary]
    total: int
    next_cursor: Optional[str] = None


class CaseEventsResponse(BaseModel):
    """Incremental event polling response."""

    events: List[StageEvent]


class ErrorResponse(BaseModel):
    """Standard typed API error response."""

    detail: str
    code: Optional[str] = None


# Shared API Contract Result Component
class ResultPayee(BaseModel):
    upi_vpa: str = Field(..., json_schema_extra={"example": "discom.powerbilling@okhdfcbank"})
    psp_name: str = Field(..., json_schema_extra={"example": "HDFC Bank (Google Pay)"})
    bank_account: Optional[str] = Field(
        default=None, json_schema_extra={"example": "50200083921901"}
    )
    ifsc: Optional[str] = Field(default=None, json_schema_extra={"example": "HDFC0001234"})
    wallet_address: Optional[str] = Field(default=None)


class ResultCluster(BaseModel):
    cluster_id: str = Field(..., json_schema_extra={"example": "cluster-electricity-mules-north"})
    size: int = Field(..., json_schema_extra={"example": 5})
    shared_identifiers: List[str] = Field(
        default_factory=list,
        json_schema_extra={"example": ["discom.powerbilling@okhdfcbank", "103.21.58.12"]},
    )


class ResultDrafts(BaseModel):
    i4c_complaint: str
    bank_alert: Dict[str, Any] = Field(default_factory=dict)
    cert_in_advisory: Dict[str, Any] = Field(default_factory=dict)


class InvestigationResult(BaseModel):
    """Investigation outcome and forensic dossier conforming to Result in api-schema.yaml."""

    case_id: str
    payee: ResultPayee
    attribution: Literal["confirmed", "inferred"] = "confirmed"
    cluster: ResultCluster
    evidence_hash: str
    drafts: ResultDrafts


# Legacy / Additional helpers for contract compatibility
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
    action_destinations: Optional[
        List[Literal["cert_in", "cybercrime_portal", "isp_takedown", "bank_freeze"]]
    ] = Field(default_factory=lambda: ["cert_in", "bank_freeze"])


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


# Aliases
TraceEvent = StageEvent
CaseResponse = CaseDetail

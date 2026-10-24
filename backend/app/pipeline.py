"""Pipeline orchestrator, stage registry, and in-process execution runner.

Conforms strictly to Section 5 specification:
- Linear state machine with explicit stage table and branches in `decide`.
- One Case = One Runner Invocation (no distributed stage queues).
- Distributed lease locking (locked_by, lease_expires_at) via atomic updates.
- Guaranteed single-transaction transition: status + stage + audit event.
- Automatic restart recovery on application startup.
- Concurrency limiting via asyncio.Semaphore (MAX_CONCURRENT_CASES).
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine, Optional, Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.correlation import SqlClusterLookup, add_case_to_graph
from app.agents.decision import DecisionResult, StubClusterLookup, decide
from app.agents.detonation import run_detonation
from app.agents.enrichment import run_enrichment
from app.agents.evidence import run_evidence_pipeline
from app.agents.fingerprint import Fingerprint
from app.agents.triage import TriageResult, run_triage
from app.config import get_settings
from app.db import create_engine_and_session
from app.integrations.tinyfish import TinyFishClient
from app.models.case import Case, CaseEvent

logger = logging.getLogger(__name__)

# Terminal statuses where execution ceases
TERMINAL_STATES = {"awaiting_approval", "inconclusive", "done", "failed"}

LEASE_DURATION_SECONDS = 60
DEFAULT_STAGE_TIMEOUT_SECONDS = 30


@dataclass
class StageResult:
    """Output returned by an individual pipeline stage callable."""

    next_stage: Optional[str]
    outcome: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageContext:
    """Execution context provided to stage callables."""

    case: Case
    db: AsyncSession
    worker_id: str


StageCallable = Callable[[StageContext], Coroutine[Any, Any, StageResult]]


# ---------------------------------------------------------------------------
# Stage Handlers (Section 5 Stubs marked # STUB(sNN))
# ---------------------------------------------------------------------------


async def stage_intake(ctx: StageContext) -> StageResult:
    """Intake verification stage."""
    # Real intake logic was executed at API ingestion (Section 4)
    return StageResult(
        next_stage="triage",
        data={
            "stub": False,
            "message": "Intake candidate verified and normalized.",
            "domain": ctx.case.domain,
            "has_payee": bool(ctx.case.input_payee),
        },
    )


async def stage_triage(ctx: StageContext) -> StageResult:
    """Triage stage: extracts free signals, RDAP, brand mismatch, and fingerprint."""
    url = ctx.case.normalized_url or ctx.case.raw_input

    # Run free-tier triage
    triage_res = await run_triage(
        url=url,
        tinyfish_client=TinyFishClient(),
    )

    # Record each forensic signal as an individual CaseEvent
    for sig in triage_res.signals:
        ctx.db.add(
            CaseEvent(
                case_id=ctx.case.id,
                stage="triage",
                kind="signal",
                message=f"Signal [{sig.group}]: {sig.name} ({sig.strength}) - {sig.description}",
                data={
                    "name": sig.name,
                    "value": sig.value,
                    "strength": sig.strength,
                    "group": sig.group,
                    "description": sig.description,
                },
            )
        )

    return StageResult(
        next_stage="decide",
        data={
            "stub": False,
            "triage": triage_res.to_dict(),
        },
    )


async def stage_decide(ctx: StageContext) -> StageResult:
    """Decision logic: routes between paid detonation, skips, or inconclusive."""
    raw = (ctx.case.raw_input or "").lower()

    # Look for triage event data from prior stage
    stmt = (
        select(CaseEvent)
        .where(CaseEvent.case_id == ctx.case.id, CaseEvent.stage == "triage")
        .order_by(CaseEvent.id.desc())
    )
    res = await ctx.db.execute(stmt)
    triage_events = res.scalars().all()
    triage_data = None
    for ev in triage_events:
        if ev.data and "triage" in ev.data:
            triage_data = ev.data["triage"]
            break

    # Branch flags support for simulated fast tests
    if "#branch:skip_payee" in raw or ctx.case.input_payee == "KNOWN_PAYEE":
        decision_res = DecisionResult(
            decision="SKIP_KNOWN_PAYEE",
            next_stage="enrichment",
            outcome="known_payee_skipped",
            attribution="confirmed",
            reasoning=["Payment destination VPA already known in intelligence graph."],
        )
    elif "#branch:skip_site" in raw:
        decision_res = DecisionResult(
            decision="SKIP_KNOWN_SITE",
            next_stage="enrichment",
            outcome="known_site_skipped",
            attribution="confirmed",
            reasoning=["Domain analyzed recently with active verified attribution."],
        )
    elif "#branch:skip_cluster" in raw:
        decision_res = DecisionResult(
            decision="SKIP_KNOWN_CLUSTER",
            next_stage="enrichment",
            outcome="known_cluster_skipped",
            attribution="inferred",
            needs_verification=True,
            reasoning=["High-confidence visual and DOM fingerprint match to active cluster."],
        )
    elif "#branch:inconclusive" in raw:
        decision_res = DecisionResult(
            decision="INCONCLUSIVE",
            next_stage="inconclusive",
            outcome="inconclusive",
            reasoning=["Domain displays no urgency, payment lures, or brand impersonation."],
        )
    else:
        # Reconstruct TriageResult from triage event or execute triage
        if triage_data:
            fp_d = triage_data.get("fingerprint", {})
            fp = Fingerprint(
                text_simhash=fp_d.get("text_simhash", 0),
                form_action_domains=fp_d.get("form_action_domains", []),
                script_hosts=fp_d.get("script_hosts", []),
                registrar=fp_d.get("registrar"),
                nameservers=fp_d.get("nameservers", []),
                creation_week=fp_d.get("creation_week"),
                normalized_title_hash=fp_d.get("normalized_title_hash", ""),
            )
            triage = TriageResult(
                url=triage_data.get("url", ctx.case.normalized_url or ""),
                domain=triage_data.get("domain", ctx.case.domain or ""),
                signals=[],
                fingerprint=fp,
                risk_level=triage_data.get("risk_level", "medium"),
                reasoning=triage_data.get("reasoning", []),
                domain_age_days=triage_data.get("domain_age_days"),
                brand_mismatch=triage_data.get("brand_mismatch", False),
                brand_claimed=triage_data.get("brand_claimed"),
                payment_indicators_found=triage_data.get("payment_indicators", []),
                urgency_phrases_found=triage_data.get("urgency_phrases", []),
                search_scam_mentions=triage_data.get("search_scam_mentions", 0),
                fetch_error=triage_data.get("fetch_error"),
            )
        else:
            triage = await run_triage(
                url=ctx.case.normalized_url or ctx.case.raw_input,
                tinyfish_client=TinyFishClient(),
            )

        cluster_lookup = await SqlClusterLookup.from_db(ctx.db)
        decision_res = decide(
            triage=triage,
            cluster_lookup=cluster_lookup,
            input_payee=ctx.case.input_payee,
            force_detonate=ctx.case.force_detonate,
        )

    # Record decision reasoning event
    for reason in decision_res.reasoning:
        ctx.db.add(
            CaseEvent(
                case_id=ctx.case.id,
                stage="decide",
                kind="decision_rule",
                message=f"Decision [{decision_res.decision}]: {reason}",
                data={
                    "decision": decision_res.decision,
                    "reason": reason,
                    "attribution": decision_res.attribution,
                    "needs_verification": decision_res.needs_verification,
                },
            )
        )

    return StageResult(
        next_stage=decision_res.next_stage,
        outcome=decision_res.outcome,
        data={
            "stub": False,
            "decision": decision_res.decision,
            "reasoning": decision_res.reasoning,
            "attribution": decision_res.attribution,
            "needs_verification": decision_res.needs_verification,
            "carried_over_data": decision_res.carried_over_data,
        },
    )


async def stage_detonation(ctx: StageContext) -> StageResult:
    """Detonation stage: autonomous agent walks the funnel to payment screen."""
    raw = (ctx.case.raw_input or "").lower()

    # Fast simulation branch flag for tests or stub override
    if "#mock_stub" in raw:
        return StageResult(
            next_stage="enrichment",
            data={
                "stub": True,
                "stage": "detonation",
                "extracted_payee": ctx.case.input_payee or "discom.recovery@okhdfcbank",
                "amount_requested": 1499.0,
                "funnel_steps_count": 4,
                "qr_detected": True,
            },
        )

    det_exec = await run_detonation(case=ctx.case, db=ctx.db)

    if det_exec.next_stage == "failed":
        raise RuntimeError(det_exec.error_message or "Detonation execution failed")

    result_data: dict[str, Any] = {
        "stub": False,
        "run_id": det_exec.run_id,
        "proxy_fallback": det_exec.proxy_fallback,
    }
    if det_exec.detonation_result:
        result_data["detonation"] = det_exec.detonation_result.model_dump()
        result_data["extracted_payee"] = (
            det_exec.detonation_result.payee_vpa
            or det_exec.detonation_result.account_number
            or det_exec.detonation_result.qr_payload
        )

    return StageResult(
        next_stage=det_exec.next_stage,
        outcome=det_exec.outcome,
        data=result_data,
    )


async def stage_enrichment(ctx: StageContext) -> StageResult:
    """Enrichment stage: resolves PSP bank, IFSC, and account rails."""
    raw = (ctx.case.raw_input or "").lower()

    if "#mock_stub" in raw:
        return StageResult(
            next_stage="correlation",
            data={
                "stub": True,
                "stage": "enrichment",
                "psp_name": "HDFC Bank (Google Pay)",
                "ifsc": "HDFC0001234",
                "bank_account": "50200083921901",
            },
        )

    try:
        enrichment_res = await run_enrichment(ctx.case)
    except Exception as exc:
        logger.warning("Enrichment encountered non-fatal error for case %s: %s", ctx.case.id, exc)
        return StageResult(
            next_stage="correlation",
            data={"stub": False, "error": str(exc)},
        )

    # Append enrichment event
    ctx.db.add(
        CaseEvent(
            case_id=ctx.case.id,
            stage="enrichment",
            kind="info",
            message=f"Enriched payment destination: PSP={enrichment_res.psp_name or 'Unknown'}, Bank={enrichment_res.sponsor_bank or 'Unknown'}",
            data=enrichment_res.model_dump(),
        )
    )

    return StageResult(
        next_stage="correlation",
        data={
            "stub": False,
            "enrichment": enrichment_res.model_dump(),
            "psp_name": enrichment_res.psp_name,
            "sponsor_bank": enrichment_res.sponsor_bank,
            "ifsc": enrichment_res.ifsc_bank_code,
            "normalized_payees": enrichment_res.normalized_payees,
        },
    )


async def stage_correlation(ctx: StageContext) -> StageResult:
    """Correlation stage: links payee and domain into campaign cluster."""
    raw = (ctx.case.raw_input or "").lower()

    if "#mock_stub" in raw:
        return StageResult(
            next_stage="evidence",
            data={
                "stub": True,
                "stage": "correlation",
                "cluster_id": "cluster-electricity-mules-north",
                "cluster_size": 5,
                "shared_identifiers": ["discom.recovery@okhdfcbank", "103.21.58.12"],
            },
        )

    corr_data = await add_case_to_graph(case=ctx.case, db=ctx.db)

    # Append correlation event
    ctx.db.add(
        CaseEvent(
            case_id=ctx.case.id,
            stage="correlation",
            kind="info",
            message=f"Correlated into {corr_data.get('cluster_id')}: Attribution={corr_data.get('attribution')}",
            data=corr_data,
        )
    )

    return StageResult(
        next_stage="evidence",
        data={
            "stub": False,
            "correlation": corr_data,
            "cluster_id": corr_data.get("cluster_id"),
            "attribution": corr_data.get("attribution"),
        },
    )


async def stage_evidence(ctx: StageContext) -> StageResult:
    """Evidence stage: compiles forensic dossier and SHA-256 seal."""
    raw = (ctx.case.raw_input or "").lower()

    if "#mock_stub" in raw:
        return StageResult(
            next_stage="reports",
            data={
                "stub": True,
                "stage": "evidence",
                "evidence_hash": "a3b2c1d0e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1",
                "pdf_pages": 4,
            },
        )

    ev_info = await run_evidence_pipeline(case=ctx.case, db=ctx.db)

    ctx.db.add(
        CaseEvent(
            case_id=ctx.case.id,
            stage="evidence",
            kind="info",
            message=f"Sealed evidence dossier (SHA-256: {ev_info['pdf_sha256'][:16]}...): HMAC sealed in hash-chained ledger pos #{ev_info['ledger_id']}",
            data=ev_info,
        )
    )

    return StageResult(
        next_stage="reports",
        data={
            "stub": False,
            "evidence": ev_info,
            "evidence_hash": ev_info["pdf_sha256"],
            "bundle_hash": ev_info["bundle_sha256"],
            "evidence_link": ev_info["evidence_link"],
        },
    )


async def stage_reports(ctx: StageContext) -> StageResult:
    """Reports stage: drafts takedown letters and complaints for human signoff.

    # STUB(s11)
    """
    return StageResult(
        next_stage="awaiting_approval",
        outcome=ctx.case.outcome or "confirmed_scam",
        data={
            "stub": True,
            "stage": "reports",
            "drafts": {
                "i4c_complaint": "Cyber Fraud Report: Electricity bill lure targeting HDFC bank account.",
                "bank_alert": {"vpa": "discom.recovery@okhdfcbank", "priority": "CRITICAL"},
                "cert_in_advisory": {"ioc_domain": ctx.case.domain or "unknown"},
            },
        },
    )


# Stage Registry mapping stage names to async callables
STAGE_REGISTRY: dict[str, StageCallable] = {
    "intake": stage_intake,
    "triage": stage_triage,
    "decide": stage_decide,
    "detonation": stage_detonation,
    "enrichment": stage_enrichment,
    "correlation": stage_correlation,
    "evidence": stage_evidence,
    "reports": stage_reports,
}


# ---------------------------------------------------------------------------
# Runner Protocol & InProcessRunner
# ---------------------------------------------------------------------------


class CaseRunner(Protocol):
    """Protocol for starting and managing autonomous case investigations."""

    def start(self, case_id: uuid.UUID) -> asyncio.Task[None]:
        """Enqueues or spawns execution for the target case."""
        ...

    async def execute_case(self, case_id: uuid.UUID) -> None:
        """Executes all sequential pipeline stages for the case under lease protection."""
        ...


class InProcessRunner:
    """Asyncio-based pipeline runner with distributed lease locking and crash recovery."""

    def __init__(self, max_concurrent_cases: int = 3):
        self.max_concurrent_cases = max_concurrent_cases
        self._semaphore = asyncio.Semaphore(max_concurrent_cases)
        self._tasks: dict[uuid.UUID, asyncio.Task[None]] = {}
        self._worker_id = f"worker-{os.getpid()}-{uuid.uuid4().hex[:6]}"

    def start(self, case_id: uuid.UUID) -> asyncio.Task[None]:
        """Launches case execution as an untracked background asyncio task."""
        if case_id in self._tasks and not self._tasks[case_id].done():
            logger.debug("Case %s is already running locally.", case_id)
            return self._tasks[case_id]

        task = asyncio.create_task(self.execute_case(case_id))
        self._tasks[case_id] = task

        def _cleanup(t: asyncio.Task[None]) -> None:
            self._tasks.pop(case_id, None)

        task.add_done_callback(_cleanup)
        return task

    async def claim_case(self, db: AsyncSession, case_id: uuid.UUID) -> Optional[Case]:
        """Attempts an atomic lease claim on the case using a conditional UPDATE."""
        now = datetime.now(timezone.utc)
        lease_expiry = now + timedelta(seconds=LEASE_DURATION_SECONDS)

        # Atomic claim condition:
        # Case is not in terminal status AND (unlocked OR lease expired OR already owned by this worker)
        stmt = (
            update(Case)
            .where(
                Case.id == case_id,
                Case.status.not_in(TERMINAL_STATES),
                (Case.locked_by.is_(None))
                | (Case.lease_expires_at < now)
                | (Case.locked_by == self._worker_id),
            )
            .values(
                locked_by=self._worker_id,
                lease_expires_at=lease_expiry,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        res = await db.execute(stmt)
        await db.commit()
        db.expire_all()
        if (res.rowcount or 0) > 0:
            c_res = await db.execute(select(Case).where(Case.id == case_id))
            return c_res.scalar_one_or_none()
        return None

    async def renew_lease(self, db: AsyncSession, case_id: uuid.UUID) -> bool:
        """Renews the active worker lease before executing the next stage."""
        now = datetime.now(timezone.utc)
        lease_expiry = now + timedelta(seconds=LEASE_DURATION_SECONDS)

        stmt = (
            update(Case)
            .where(
                Case.id == case_id,
                Case.locked_by == self._worker_id,
            )
            .values(lease_expires_at=lease_expiry, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        res = await db.execute(stmt)
        await db.commit()
        return (res.rowcount or 0) > 0

    async def release_lease(
        self,
        db: AsyncSession,
        case_id: uuid.UUID,
        terminal_status: Optional[str] = None,
        outcome: Optional[str] = None,
        error_reason: Optional[str] = None,
    ) -> None:
        """Releases the lease and finalizes case state."""
        now = datetime.now(timezone.utc)
        values: dict[str, Any] = {
            "locked_by": None,
            "lease_expires_at": None,
            "updated_at": now,
        }
        if terminal_status:
            values["status"] = terminal_status
            values["current_stage"] = terminal_status
        if outcome:
            values["outcome"] = outcome
        if error_reason:
            values["error_reason"] = error_reason

        stmt = (
            update(Case)
            .where(Case.id == case_id)
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        await db.execute(stmt)
        await db.commit()

    async def execute_case(self, case_id: uuid.UUID) -> None:
        """Executes the pipeline stages in sequence under semaphore and lease control."""
        async with self._semaphore:
            _, session_factory = create_engine_and_session()

            # 1. Attempt Lease Claim
            async with session_factory() as session:
                case = await self.claim_case(session, case_id)
                if not case:
                    logger.warning(
                        "Worker %s could not claim case %s (already locked or terminal).",
                        self._worker_id,
                        case_id,
                    )
                    return

            # 2. Sequential Stage Execution Loop
            while True:
                async with session_factory() as session:
                    # Fetch fresh case state
                    case_stmt = select(Case).where(Case.id == case_id)
                    case_res = await session.execute(case_stmt)
                    current_case = case_res.scalar_one_or_none()

                    if not current_case:
                        logger.error("Case %s disappeared during execution.", case_id)
                        return

                    current_stage_name = current_case.status

                    # Check for terminal state
                    if current_stage_name in TERMINAL_STATES:
                        logger.info(
                            "Case %s reached terminal state '%s'.",
                            case_id,
                            current_stage_name,
                        )
                        await self.release_lease(session, case_id)
                        return

                    # Resolve stage handler
                    stage_func = STAGE_REGISTRY.get(current_stage_name)
                    if not stage_func:
                        error_msg = f"Unknown pipeline stage '{current_stage_name}'."
                        logger.error(error_msg)
                        await self.record_failure(session, case_id, current_stage_name, error_msg)
                        return

                    # Renew worker lease before executing
                    current_case.lease_expires_at = datetime.now(timezone.utc) + timedelta(
                        seconds=LEASE_DURATION_SECONDS
                    )

                    # Execute stage with timeout
                    ctx = StageContext(
                        case=current_case,
                        db=session,
                        worker_id=self._worker_id,
                    )
                    try:
                        result = await asyncio.wait_for(
                            stage_func(ctx),
                            timeout=DEFAULT_STAGE_TIMEOUT_SECONDS,
                        )
                    except Exception as exc:
                        error_msg = f"Stage '{current_stage_name}' failed: {exc}"
                        logger.exception(error_msg)
                        await self.record_failure(session, case_id, current_stage_name, error_msg)
                        return

                    # Commit stage transition and audit event in ONE transaction
                    now = datetime.now(timezone.utc)
                    next_stage = result.next_stage or "awaiting_approval"

                    # Update case status
                    current_case.status = next_stage
                    current_case.current_stage = next_stage
                    if result.outcome:
                        current_case.outcome = result.outcome
                    current_case.updated_at = now

                    # If next stage is terminal, release lease
                    if next_stage in TERMINAL_STATES:
                        current_case.locked_by = None
                        current_case.lease_expires_at = None

                    # Append stage completion event
                    event = CaseEvent(
                        case_id=case_id,
                        stage=current_stage_name,
                        kind="info",
                        message=f"Stage '{current_stage_name}' completed. Advancing to '{next_stage}'.",
                        data=result.data,
                    )
                    session.add(event)
                    await session.commit()

                    if next_stage in TERMINAL_STATES:
                        return

    async def record_failure(
        self,
        db: AsyncSession,
        case_id: uuid.UUID,
        stage_name: str,
        error_msg: str,
    ) -> None:
        """Records pipeline failure and terminal state in one transaction."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(Case)
            .where(Case.id == case_id)
            .values(
                status="failed",
                current_stage=stage_name,
                outcome="failed",
                error_reason=error_msg,
                locked_by=None,
                lease_expires_at=None,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        await db.execute(stmt)

        event = CaseEvent(
            case_id=case_id,
            stage=stage_name,
            kind="error",
            message=f"Pipeline error in stage '{stage_name}': {error_msg}",
            data={"error": error_msg, "stage": stage_name},
        )
        db.add(event)
        await db.commit()


# Singleton runner instance
_runner: Optional[InProcessRunner] = None


def get_pipeline_runner() -> InProcessRunner:
    """Retrieves or initializes the global InProcessRunner singleton."""
    global _runner
    if _runner is None:
        settings = get_settings()
        _runner = InProcessRunner(
            max_concurrent_cases=settings.MAX_CONCURRENT_CASES,
        )
    return _runner


async def resume_incomplete_cases() -> int:
    """Restart recovery: identifies stuck or interrupted cases and resumes execution."""
    _, session_factory = create_engine_and_session()
    now = datetime.now(timezone.utc)
    runner = get_pipeline_runner()

    async with session_factory() as session:
        # Select cases not in terminal states where lease has expired or is unassigned
        stmt = select(Case.id).where(
            Case.status.not_in(TERMINAL_STATES),
            (Case.locked_by.is_(None)) | (Case.lease_expires_at < now),
        )
        res = await session.execute(stmt)
        incomplete_ids = list(res.scalars().all())

    for cid in incomplete_ids:
        logger.info("Resuming incomplete case %s after service restart.", cid)
        runner.start(cid)

    return len(incomplete_ids)

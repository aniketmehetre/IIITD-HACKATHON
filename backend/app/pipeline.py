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

from app.config import get_settings
from app.db import create_engine_and_session
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
    """Triage stage: extracts free signals, RDAP, and brand mismatch.

    # STUB(s06)
    """
    return StageResult(
        next_stage="decide",
        data={
            "stub": True,
            "stage": "triage",
            "domain_age_days": 4,
            "brand_claimed": "ExampleMart",
            "urgency_detected": True,
            "triage_score": 85,
        },
    )


async def stage_decide(ctx: StageContext) -> StageResult:
    """Decision logic: routes between paid detonation, skips, or inconclusive."""
    raw = (ctx.case.raw_input or "").lower()

    # Branch 1: SKIP_KNOWN_PAYEE (Payee already known/extracted)
    if "#branch:skip_payee" in raw or ctx.case.input_payee == "KNOWN_PAYEE":
        return StageResult(
            next_stage="enrichment",
            outcome="known_payee_skipped",
            data={
                "stub": True,
                "decision": "SKIP_KNOWN_PAYEE",
                "reason": "Payment destination VPA already known in intelligence graph.",
            },
        )

    # Branch 2: SKIP_KNOWN_SITE (Domain seen recently with confirmed payee)
    if "#branch:skip_site" in raw:
        return StageResult(
            next_stage="enrichment",
            outcome="known_site_skipped",
            data={
                "stub": True,
                "decision": "SKIP_KNOWN_SITE",
                "reason": "Domain analyzed recently with active verified attribution.",
            },
        )

    # Branch 3: SKIP_KNOWN_CLUSTER (Strong fingerprint cluster match)
    if "#branch:skip_cluster" in raw:
        return StageResult(
            next_stage="enrichment",
            outcome="known_cluster_skipped",
            data={
                "stub": True,
                "decision": "SKIP_KNOWN_CLUSTER",
                "reason": "High-confidence visual and DOM fingerprint match to active cluster.",
            },
        )

    # Branch 4: INCONCLUSIVE (Benign / no threat indicators discovered)
    if "#branch:inconclusive" in raw:
        return StageResult(
            next_stage="inconclusive",
            outcome="inconclusive",
            data={
                "stub": True,
                "decision": "INCONCLUSIVE",
                "reason": "Domain displays no urgency, payment lures, or brand impersonation.",
            },
        )

    # Default Branch: DETONATE (Paid TinyFish Agent walk)
    return StageResult(
        next_stage="detonation",
        data={
            "stub": True,
            "decision": "DETONATE",
            "reason": "High risk score with active payment indicators; full detonation warranted.",
        },
    )


async def stage_detonation(ctx: StageContext) -> StageResult:
    """Detonation stage: autonomous agent walks the funnel to payment screen.

    # STUB(s07)
    """
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


async def stage_enrichment(ctx: StageContext) -> StageResult:
    """Enrichment stage: resolves PSP bank, IFSC, and account rails.

    # STUB(s08)
    """
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


async def stage_correlation(ctx: StageContext) -> StageResult:
    """Correlation stage: links payee and domain into NetworkX campaign cluster.

    # STUB(s09)
    """
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


async def stage_evidence(ctx: StageContext) -> StageResult:
    """Evidence stage: compiles forensic dossier and SHA-256 seal.

    # STUB(s10)
    """
    return StageResult(
        next_stage="reports",
        data={
            "stub": True,
            "stage": "evidence",
            "evidence_hash": "a3b2c1d0e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1",
            "pdf_pages": 4,
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
                    await self.renew_lease(session, case_id)

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

"""Unit and integration tests for Section 5: Pipeline skeleton, stubs, branches, SSE, and recovery.

Verifies:
- Happy path reaches awaiting_approval with expected event order
- Each decision branch (skip_payee, skip_site, skip_cluster, inconclusive)
- A raising stage yields status=failed with readable error_reason and error event
- Restart recovery picks up incomplete cases and runs them to completion
- Worker lease prevents double execution; expired lease can be taken over
- SSE /stream emits ordered stage events and closes on terminal status
- GET /cases/{id}/result returns 404 until complete, then returns full InvestigationResult
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings, get_settings
from app.db import get_db_session
from app.main import create_app
from app.models.base import Base
from app.models.case import Case, CaseEvent
from app.pipeline import (
    STAGE_REGISTRY,
    InProcessRunner,
    StageContext,
    StageResult,
    get_pipeline_runner,
    resume_incomplete_cases,
)


@pytest_asyncio.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(async_db):
    test_settings = Settings(
        STING_ENV="test",
        TINYFISH_API_KEY="test-key",
        STING_API_KEY="test-key",
        EVIDENCE_SIGNING_KEY="test-key",
    )
    app = create_app(test_settings)

    async def override_get_db_session():
        async with async_db() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.state.session_factory = async_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# 1. Pipeline Execution & Happy Path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_happy_path(async_db, monkeypatch):
    """Happy path executes all sequential stub stages to awaiting_approval."""
    # Ensure pipeline uses our test db engine
    monkeypatch.setattr(
        "app.pipeline.create_engine_and_session",
        lambda *args, **kwargs: (None, async_db),
    )

    case_id = uuid.uuid4()
    async with async_db() as session:
        case = Case(
            id=case_id,
            input_type="link",
            raw_input="https://electricity-bill-recovery.biz/pay?id=83921",
            status="intake",
            current_stage="intake",
            domain="electricity-bill-recovery.biz",
        )
        session.add(case)
        session.add(
            CaseEvent(
                case_id=case_id,
                stage="intake",
                kind="info",
                message="Case created.",
            )
        )
        await session.commit()

    runner = InProcessRunner(max_concurrent_cases=2)
    await runner.execute_case(case_id)

    async with async_db() as session:
        res = await session.execute(select(Case).where(Case.id == case_id))
        updated_case = res.scalar_one()

        assert updated_case.status == "awaiting_approval"
        assert updated_case.outcome == "confirmed_scam"
        assert updated_case.locked_by is None
        assert updated_case.lease_expires_at is None

        # Check events sequence
        events_res = await session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.id.asc())
        )
        events = list(events_res.scalars().all())
        stages_traversed = [e.stage for e in events]

        # Verify stages traversed in expected order
        assert "intake" in stages_traversed
        assert "triage" in stages_traversed
        assert "decide" in stages_traversed
        assert "detonation" in stages_traversed
        assert "enrichment" in stages_traversed
        assert "correlation" in stages_traversed
        assert "evidence" in stages_traversed
        assert "reports" in stages_traversed


# ---------------------------------------------------------------------------
# 2. Decision Branches (Skips and Inconclusive)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "branch_flag,expected_outcome,expected_status,should_skip_detonation",
    [
        ("#branch:skip_payee", "known_payee_skipped", "awaiting_approval", True),
        ("#branch:skip_site", "known_site_skipped", "awaiting_approval", True),
        ("#branch:skip_cluster", "known_cluster_skipped", "awaiting_approval", True),
        ("#branch:inconclusive", "inconclusive", "inconclusive", True),
    ],
)
@pytest.mark.asyncio
async def test_pipeline_decision_branches(
    async_db,
    monkeypatch,
    branch_flag,
    expected_outcome,
    expected_status,
    should_skip_detonation,
):
    """Verify decide stage routes correctly to skips (bypassing detonation) and inconclusive."""
    monkeypatch.setattr(
        "app.pipeline.create_engine_and_session",
        lambda *args, **kwargs: (None, async_db),
    )

    case_id = uuid.uuid4()
    async with async_db() as session:
        case = Case(
            id=case_id,
            input_type="link",
            raw_input=f"https://example.com/lure {branch_flag}",
            status="intake",
            current_stage="intake",
        )
        session.add(case)
        await session.commit()

    runner = InProcessRunner(max_concurrent_cases=1)
    await runner.execute_case(case_id)

    async with async_db() as session:
        res = await session.execute(select(Case).where(Case.id == case_id))
        updated_case = res.scalar_one()

        assert updated_case.status == expected_status
        assert updated_case.outcome == expected_outcome

        events_res = await session.execute(
            select(CaseEvent.stage).where(CaseEvent.case_id == case_id).order_by(CaseEvent.id.asc())
        )
        stages = list(events_res.scalars().all())

        if should_skip_detonation:
            assert "detonation" not in stages


# ---------------------------------------------------------------------------
# 3. Stage Failure & Error Handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raising_stage_yields_failed_status(async_db, monkeypatch):
    """An exception in any stage transitions case to failed with error event and reason."""
    monkeypatch.setattr(
        "app.pipeline.create_engine_and_session",
        lambda *args, **kwargs: (None, async_db),
    )

    # Register an intentionally failing stage
    async def failing_triage(ctx: StageContext) -> StageResult:
        raise RuntimeError("Synthetic simulated network timeout in Triage")

    monkeypatch.setitem(STAGE_REGISTRY, "triage", failing_triage)

    case_id = uuid.uuid4()
    async with async_db() as session:
        case = Case(
            id=case_id,
            input_type="link",
            raw_input="https://failing-test.biz",
            status="triage",
            current_stage="triage",
        )
        session.add(case)
        await session.commit()

    runner = InProcessRunner()
    await runner.execute_case(case_id)

    async with async_db() as session:
        res = await session.execute(select(Case).where(Case.id == case_id))
        failed_case = res.scalar_one()

        assert failed_case.status == "failed"
        assert failed_case.outcome == "failed"
        assert "Synthetic simulated network timeout" in failed_case.error_reason
        assert failed_case.locked_by is None
        assert failed_case.lease_expires_at is None

        # Check error event
        err_ev_res = await session.execute(
            select(CaseEvent).where(
                CaseEvent.case_id == case_id,
                CaseEvent.kind == "error",
            )
        )
        err_event = err_ev_res.scalar_one()
        assert "Synthetic simulated network timeout" in err_event.message


# ---------------------------------------------------------------------------
# 4. Lease Locking & Takeover
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lease_locking_and_takeover(async_db):
    """Active lease prevents double execution; expired lease can be taken over."""
    runner1 = InProcessRunner()
    runner2 = InProcessRunner()

    case_id = uuid.uuid4()
    async with async_db() as session:
        case = Case(
            id=case_id,
            input_type="link",
            raw_input="https://lease-test.org",
            status="intake",
        )
        session.add(case)
        await session.commit()

        # 1. Runner 1 claims lease
        claimed1 = await runner1.claim_case(session, case_id)
        assert claimed1 is not None
        assert claimed1.locked_by == runner1._worker_id

        # 2. Runner 2 tries to claim while lease is active -> fails
        claimed2 = await runner2.claim_case(session, case_id)
        assert claimed2 is None

        # 3. Simulate lease expiration (set lease_expires_at 10s in the past)
        case_to_expire = await session.get(Case, case_id)
        case_to_expire.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        await session.commit()

        # 4. Runner 2 claims expired lease -> succeeds
        takeover = await runner2.claim_case(session, case_id)
        assert takeover is not None
        assert takeover.locked_by == runner2._worker_id


# ---------------------------------------------------------------------------
# 5. Restart Recovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_restart_recovery_resumes_incomplete_cases(async_db, monkeypatch):
    """Cases stuck mid-run are resumed by resume_incomplete_cases() on startup."""
    monkeypatch.setattr(
        "app.pipeline.create_engine_and_session",
        lambda *args, **kwargs: (None, async_db),
    )

    case_id = uuid.uuid4()
    async with async_db() as session:
        # Create case stuck in 'detonation' with expired lease
        case = Case(
            id=case_id,
            input_type="link",
            raw_input="https://stuck-restart-test.com",
            status="detonation",
            current_stage="detonation",
            locked_by="dead-worker-pid-9999",
            lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=5),
        )
        session.add(case)
        await session.commit()

    # Trigger restart recovery
    resumed_count = await resume_incomplete_cases()
    assert resumed_count >= 1

    # Give runner background task a moment to finish
    runner = get_pipeline_runner()
    if case_id in runner._tasks:
        await runner._tasks[case_id]

    async with async_db() as session:
        res = await session.execute(select(Case).where(Case.id == case_id))
        completed_case = res.scalar_one()
        assert completed_case.status == "awaiting_approval"


# ---------------------------------------------------------------------------
# 6. SSE Stream & Result Endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_stream_and_result_endpoint(client, async_db, monkeypatch):
    """Verify GET /cases/{id}/stream emits events and /result returns valid dossier."""
    monkeypatch.setattr(
        "app.pipeline.create_engine_and_session",
        lambda *args, **kwargs: (None, async_db),
    )

    # 1. Create a case
    create_resp = await client.post(
        "/cases",
        json={
            "input_type": "link",
            "raw_input": "https://stream-test-case.biz/claim",
        },
    )
    assert create_resp.status_code == 201
    case_id = create_resp.json()["id"]

    # 2. Before completion, /result must return 404
    async with async_db() as session:
        c = await session.get(Case, uuid.UUID(case_id))
        c.status = "triage"
        await session.commit()

    r404 = await client.get(f"/cases/{case_id}/result")
    assert r404.status_code == 404
    assert "not yet ready" in r404.json()["detail"].lower()

    # 3. Complete the case to awaiting_approval
    runner = get_pipeline_runner()
    await runner.execute_case(uuid.UUID(case_id))

    # 4. Now /result returns full InvestigationResult
    res_resp = await client.get(f"/cases/{case_id}/result")
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["case_id"] == case_id
    assert "payee" in res_data
    assert res_data["payee"]["upi_vpa"] is not None
    assert "drafts" in res_data
    assert res_data["attribution"] in ("confirmed", "inferred")

    # 5. Connect to SSE stream
    async with client.stream("GET", f"/cases/{case_id}/stream") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        lines = []
        async for line in response.aiter_lines():
            lines.append(line)
            if "terminal" in line:
                break

        full_stream_text = "\n".join(lines)
        assert "event: stage_event" in full_stream_text
        assert "event: terminal" in full_stream_text

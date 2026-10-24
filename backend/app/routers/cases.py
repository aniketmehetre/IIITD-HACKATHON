"""Cases API router for ingestion, querying, and event tracking.

Conforms strictly to Section 4 specifications and shared/api-schema.yaml contracts:
- POST /cases: JSON intake (link | message), deduplication within 24h, write first event.
- POST /cases/qr: Multipart image upload (PNG/JPEG <= 5MB), OpenCV decode, no image persistence.
- GET /cases: Recent cases list, keyset cursor pagination, status and include_seed filters.
- GET /cases/{id}: Case details with up to 20 recent events in chronological order.
- GET /cases/{id}/events: Incremental event polling with ?after cursor.
"""

import base64
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.intake import process_intake
from app.config import Settings, get_settings
from app.db import get_db_session
from app.models.case import Case, CaseEvent
from app.schemas.case import (
    CaseCreateRequest,
    CaseDetail,
    CaseEventsResponse,
    CaseListResponse,
    CaseSummary,
    ErrorResponse,
    StageEvent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["Cases"])

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


async def verify_sting_key(
    x_sting_key: Optional[str] = Header(None, alias="X-STING-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    """Validates the X-STING-Key header on mutating write operations."""
    if settings.STING_ENV == "test":
        if x_sting_key and settings.STING_API_KEY and x_sting_key != settings.STING_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid X-STING-Key header.",
            )
        return

    expected_key = settings.STING_API_KEY
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="STING API key is not configured on server.",
        )
    if not x_sting_key or x_sting_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-STING-Key header.",
        )


def _format_stage_event(event: CaseEvent) -> StageEvent:
    """Formats SQLAlchemy CaseEvent into API contract StageEvent."""
    level = "info"
    if event.kind == "warn":
        level = "warning"
    elif event.kind == "error":
        level = "error"

    return StageEvent(
        id=str(event.id),
        stage=event.stage,
        message=event.message,
        timestamp=event.ts.isoformat(),
        level=level,
        metadata=event.data or {},
    )


def _format_case_summary(case: Case, deduplicated: bool = False) -> CaseSummary:
    """Formats SQLAlchemy Case into API contract CaseSummary."""
    return CaseSummary(
        id=str(case.id),
        input_type=case.input_type,
        raw_input=case.raw_input,
        status=case.status,
        outcome=case.outcome,
        created_at=case.created_at.isoformat(),
        updated_at=case.updated_at.isoformat() if case.updated_at else case.created_at.isoformat(),
        is_seed=case.is_seed,
        deduplicated=deduplicated,
    )


@router.post(
    "",
    response_model=CaseSummary,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def submit_case(
    payload: CaseCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    _: None = Depends(verify_sting_key),
) -> CaseSummary:
    """Submit a suspicious link or message for autonomous investigation."""
    try:
        intake_res = process_intake(
            input_type=payload.input_type,
            raw_input=payload.raw_input,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    # 24-hour Deduplication check on normalized_url if available
    if intake_res.normalized_url and not payload.force_detonate:
        stmt = (
            select(Case)
            .where(
                Case.normalized_url == intake_res.normalized_url,
                Case.created_at >= cutoff,
            )
            .order_by(desc(Case.created_at))
            .limit(1)
        )
        res = await db.execute(stmt)
        existing_case = res.scalar_one_or_none()
        if existing_case:
            logger.debug(
                "Deduplicated case submission for normalized URL: %s",
                intake_res.normalized_url,
            )
            return _format_case_summary(existing_case, deduplicated=True)

    # Create new case
    new_case = Case(
        id=uuid.uuid4(),
        input_type=intake_res.input_type,
        raw_input=intake_res.raw_input,
        normalized_url=intake_res.normalized_url,
        domain=intake_res.domain,
        is_idn=intake_res.is_idn,
        extracted_upi_ids=intake_res.extracted_upi_ids,
        input_payee=intake_res.input_payee,
        status="intake",
        current_stage="intake",
        force_detonate=payload.force_detonate,
        is_seed=False,
    )
    db.add(new_case)
    await db.flush()

    # Append first event
    first_event = CaseEvent(
        case_id=new_case.id,
        stage="intake",
        kind="info",
        message="Case created and candidate ingested into pipeline.",
        data={
            "input_type": new_case.input_type,
            "domain": new_case.domain,
            "has_payee": bool(new_case.input_payee),
            "is_idn": new_case.is_idn,
        },
    )
    db.add(first_event)
    await db.commit()
    await db.refresh(new_case)

    return _format_case_summary(new_case, deduplicated=False)


@router.post(
    "/qr",
    response_model=CaseSummary,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def submit_qr_case(
    file: UploadFile = File(..., description="Uploaded QR code image (PNG/JPEG)"),
    force_detonate: bool = Form(default=False),
    db: AsyncSession = Depends(get_db_session),
    _: None = Depends(verify_sting_key),
) -> CaseSummary:
    """Upload a scam QR code image for decoding and autonomous intake."""
    if file.content_type not in ("image/png", "image/jpeg", "image/jpg"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{file.content_type}'. Upload must be image/png or image/jpeg.",
        )

    # Read binary bytes into memory (never saved to disk)
    image_bytes = await file.read()
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image file size ({len(image_bytes)} bytes) exceeds 5 MB maximum allowed limit.",
        )

    try:
        intake_res = process_intake(
            input_type="qr_image",
            raw_input="",
            image_bytes=image_bytes,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    # 24-hour Deduplication check if decoded QR yielded a normalized URL
    if intake_res.normalized_url and not force_detonate:
        stmt = (
            select(Case)
            .where(
                Case.normalized_url == intake_res.normalized_url,
                Case.created_at >= cutoff,
            )
            .order_by(desc(Case.created_at))
            .limit(1)
        )
        res = await db.execute(stmt)
        existing_case = res.scalar_one_or_none()
        if existing_case:
            return _format_case_summary(existing_case, deduplicated=True)

    new_case = Case(
        id=uuid.uuid4(),
        input_type="qr_image",
        raw_input=intake_res.raw_input,
        normalized_url=intake_res.normalized_url,
        domain=intake_res.domain,
        is_idn=intake_res.is_idn,
        extracted_upi_ids=intake_res.extracted_upi_ids,
        input_payee=intake_res.input_payee,
        status="intake",
        current_stage="intake",
        force_detonate=force_detonate,
        is_seed=False,
    )
    db.add(new_case)
    await db.flush()

    first_event = CaseEvent(
        case_id=new_case.id,
        stage="intake",
        kind="info",
        message="QR code image decoded and candidate ingested.",
        data={
            "input_type": "qr_image",
            "input_payee": new_case.input_payee,
            "normalized_url": new_case.normalized_url,
        },
    )
    db.add(first_event)
    await db.commit()
    await db.refresh(new_case)

    return _format_case_summary(new_case, deduplicated=False)


@router.get(
    "",
    response_model=CaseListResponse,
    responses={400: {"model": ErrorResponse}},
)
async def list_cases(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    include_seed: bool = Query(default=True),
    db: AsyncSession = Depends(get_db_session),
) -> CaseListResponse:
    """List recent investigation cases with keyset cursor pagination."""
    # Count total matching query
    count_query = select(func.count(Case.id))
    if not include_seed:
        count_query = count_query.where(Case.is_seed == False)  # noqa: E712
    if status_filter:
        count_query = count_query.where(Case.status == status_filter)

    total_count_res = await db.execute(count_query)
    total_count = total_count_res.scalar() or 0

    # Build main items query
    stmt = select(Case).order_by(desc(Case.created_at), desc(Case.id))
    if not include_seed:
        stmt = stmt.where(Case.is_seed == False)  # noqa: E712
    if status_filter:
        stmt = stmt.where(Case.status == status_filter)

    # Keyset pagination cursor format: base64(created_at_iso|case_id)
    if cursor:
        try:
            decoded = base64.b64decode(cursor.encode("utf-8")).decode("utf-8")
            cursor_ts_str, cursor_id_str = decoded.split("|", 1)
            cursor_ts = datetime.fromisoformat(cursor_ts_str)
            stmt = stmt.where(
                (Case.created_at < cursor_ts)
                | ((Case.created_at == cursor_ts) & (Case.id < uuid.UUID(cursor_id_str)))
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed pagination cursor.",
            )

    # Fetch limit + 1 to determine if next page exists
    stmt = stmt.limit(limit + 1)
    res = await db.execute(stmt)
    records = list(res.scalars().all())

    next_cursor = None
    if len(records) > limit:
        last_item = records[limit - 1]
        next_raw = f"{last_item.created_at.isoformat()}|{str(last_item.id)}"
        next_cursor = base64.b64encode(next_raw.encode("utf-8")).decode("utf-8")
        records = records[:limit]

    items = [_format_case_summary(c) for c in records]
    return CaseListResponse(
        items=items,
        total=total_count,
        next_cursor=next_cursor,
    )


@router.get(
    "/{id}",
    response_model=CaseDetail,
    responses={404: {"model": ErrorResponse}},
)
async def get_case(
    id: str,
    db: AsyncSession = Depends(get_db_session),
) -> CaseDetail:
    """Retrieve full case details and live progress including up to 20 recent events."""
    try:
        case_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{id}' not found.",
        )

    stmt = select(Case).where(Case.id == case_uuid).options(selectinload(Case.events))
    res = await db.execute(stmt)
    case_obj = res.scalar_one_or_none()

    if not case_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{id}' not found.",
        )

    # Fetch up to 20 recent events in chronological order
    # (ordered by id ascending of the latest 20 events)
    events_stmt = (
        select(CaseEvent)
        .where(CaseEvent.case_id == case_uuid)
        .order_by(desc(CaseEvent.id))
        .limit(20)
    )
    events_res = await db.execute(events_stmt)
    recent_events_desc = list(events_res.scalars().all())
    recent_events_asc = list(reversed(recent_events_desc))

    return CaseDetail(
        id=str(case_obj.id),
        input_type=case_obj.input_type,
        raw_input=case_obj.raw_input,
        status=case_obj.status,
        outcome=case_obj.outcome,
        streaming_url=case_obj.streaming_url,
        recent_events=[_format_stage_event(e) for e in recent_events_asc],
        created_at=case_obj.created_at.isoformat(),
        updated_at=case_obj.updated_at.isoformat()
        if case_obj.updated_at
        else case_obj.created_at.isoformat(),
    )


@router.get(
    "/{id}/events",
    response_model=CaseEventsResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_case_events(
    id: str,
    after: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> CaseEventsResponse:
    """Poll stage trace events occurring after the specified event ID."""
    try:
        case_uuid = uuid.UUID(id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{id}' not found.",
        )

    # Check case exists
    case_check = await db.execute(select(Case.id).where(Case.id == case_uuid))
    if not case_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{id}' not found.",
        )

    stmt = select(CaseEvent).where(CaseEvent.case_id == case_uuid)
    if after:
        try:
            after_id = int(after)
            stmt = stmt.where(CaseEvent.id > after_id)
        except ValueError:
            # If cursor is a timestamp or string, handle gracefully or ignore
            pass

    stmt = stmt.order_by(CaseEvent.id.asc())
    res = await db.execute(stmt)
    events = list(res.scalars().all())

    return CaseEventsResponse(events=[_format_stage_event(e) for e in events])

"""Unit and integration tests for Section 4: Case model, event log, and Intake.

Verifies:
- Message with 2 URLs and a UPI ID extracts correctly
- Tracking parameters stripped
- Punycode host flagged
- Localhost/10.x/169.254.x rejected (SSRF protection) with 400
- Oversized upload rejected (> 5000 chars or > 5MB)
- Fixture QR PNG decodes to UPI payee
- Dedupe returns existing case within 24h, and force_detonate bypasses dedupe
- Unknown id returns 404
- Events pagination with `after`
- GET /cases pagination, status filter, and include_seed
- recent_events never returns more than 20 and is in chronological order
- Migration applies cleanly and downgrades
"""

import tempfile
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import pytest
import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from app.agents.intake import (
    decode_qr_image,
    extract_from_message,
    process_intake,
    validate_and_normalize_url,
)
from app.config import Settings, get_settings
from app.db import get_db_session
from app.main import create_app
import app.models  # registers all models on Base.metadata
from app.models import (
    Base,
    Case,
    CaseEvent,
    Edge,
    EvidenceLedger,
    Payee,
    Site,
    UsageLedger,
)


# Test database setup (in-memory SQLite with aiosqlite)
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

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with async_db() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# 1. Intake Agent Unit Tests
# ---------------------------------------------------------------------------


def test_extract_from_message():
    """Message with 2 URLs and a UPI ID extracts primary URL and UPI ID."""
    text = (
        "Urgent: Electricity power disconnection notice! "
        "Pay pending dues at https://discom-recovery.biz/pay?bill=991 or backup "
        "https://bill-assist.in/portal. Payee UPI: billing.desk@okhdfcbank. Thank you!"
    )
    primary_url, upis = extract_from_message(text)
    assert primary_url == "https://discom-recovery.biz/pay?bill=991"
    assert "billing.desk@okhdfcbank" in upis


def test_strip_tracking_parameters():
    """Verify UTM and tracking query parameters are cleanly stripped."""
    url = "https://scam-store.com/checkout?utm_source=telegram&utm_medium=cpc&fbclid=12345&item=gold&gclid=xyz"
    normalized, domain, is_idn, is_ip = validate_and_normalize_url(url)
    assert normalized == "https://scam-store.com/checkout?item=gold"
    assert domain == "scam-store.com"
    assert not is_idn
    assert not is_ip


def test_punycode_host_flagged():
    """Verify Punycode and Unicode homograph hosts are detected and flagged."""
    url = "https://xn--e1awd7f.com/login"
    normalized, domain, is_idn, is_ip = validate_and_normalize_url(url)
    assert is_idn is True
    assert domain == "xn--e1awd7f.com"


@pytest.mark.parametrize(
    "forbidden_url",
    [
        "http://localhost:8000/admin",
        "http://127.0.0.1/status",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/router",
        "http://172.16.0.1/secrets",
        "http://169.254.169.254/latest/meta-data",
        "http://0.0.0.0:80",
        "file:///etc/passwd",
        "ftp://example.com/files",
    ],
)
def test_ssrf_and_forbidden_targets_rejected(forbidden_url):
    """Localhost, private/link-local ranges, non-http schemes rejected."""
    with pytest.raises(ValueError) as excinfo:
        validate_and_normalize_url(forbidden_url)
    assert (
        "SSRF" in str(excinfo.value)
        or "Invalid URL scheme" in str(excinfo.value)
        or "forbidden" in str(excinfo.value)
    )


def test_oversized_raw_input_rejected():
    """Raw input exceeding 5000 characters is rejected."""
    oversized = "A" * 5001
    with pytest.raises(ValueError) as excinfo:
        process_intake("message", oversized)
    assert "exceeds 5000 character" in str(excinfo.value)


def test_fixture_qr_png_decodes():
    """Verify a fixture QR PNG decodes to a valid UPI payee."""
    encoder = cv2.QRCodeEncoder.create()
    qr = encoder.encode("upi://pay?pa=discom.recovery@okhdfcbank&pn=DiscomBilling")
    scaled = cv2.resize(qr, (qr.shape[1] * 8, qr.shape[0] * 8), interpolation=cv2.INTER_NEAREST)
    _, buf = cv2.imencode(".png", scaled)
    kind, payee, payload = decode_qr_image(buf.tobytes())
    assert kind == "upi"
    assert payee == "discom.recovery@okhdfcbank"
    assert "upi://pay" in payload


# ---------------------------------------------------------------------------
# 2. Endpoint Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_case_link_success(client):
    """POST /cases with a valid link creates case and initial event."""
    resp = await client.post(
        "/cases",
        json={
            "input_type": "link",
            "raw_input": "https://electricity-bill-recovery.biz/pay?id=83921&utm_source=sms",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["input_type"] == "link"
    assert data["status"] == "intake"
    assert data["deduplicated"] is False


@pytest.mark.asyncio
async def test_deduplication_within_24h(client):
    """Submitting the same normalized URL within 24h returns existing case with deduplicated=True."""
    url = "https://fresh-scam-lure.biz/claim?user=12"
    # First submission
    r1 = await client.post(
        "/cases",
        json={"input_type": "link", "raw_input": url},
    )
    assert r1.status_code == 201
    c1 = r1.json()
    assert c1["deduplicated"] is False

    # Second submission within 24h (same normalized URL)
    r2 = await client.post(
        "/cases",
        json={"input_type": "link", "raw_input": f"{url}&utm_medium=social"},
    )
    assert r2.status_code == 201
    c2 = r2.json()
    assert c2["id"] == c1["id"]
    assert c2["deduplicated"] is True

    # Third submission with force_detonate=True bypasses dedupe
    r3 = await client.post(
        "/cases",
        json={"input_type": "link", "raw_input": url, "force_detonate": True},
    )
    assert r3.status_code == 201
    c3 = r3.json()
    assert c3["id"] != c1["id"]
    assert c3["deduplicated"] is False


@pytest.mark.asyncio
async def test_post_case_invalid_ssrf_returns_400(client):
    """Attempting SSRF via POST /cases returns typed 400 ErrorResponse, not 500."""
    resp = await client.post(
        "/cases",
        json={
            "input_type": "link",
            "raw_input": "http://169.254.169.254/latest/meta-data",
        },
    )
    assert resp.status_code == 400
    err = resp.json()
    assert "detail" in err
    assert "SSRF" in err["detail"] or "forbidden" in err["detail"]


@pytest.mark.asyncio
async def test_post_qr_endpoint(client):
    """POST /cases/qr decodes uploaded QR image and creates case."""
    encoder = cv2.QRCodeEncoder.create()
    qr = encoder.encode("upi://pay?pa=scammer.fast@okaxis&pn=ElectricityOffice")
    scaled = cv2.resize(qr, (qr.shape[1] * 8, qr.shape[0] * 8), interpolation=cv2.INTER_NEAREST)
    _, buf = cv2.imencode(".png", scaled)

    files = {"file": ("test_qr.png", buf.tobytes(), "image/png")}
    resp = await client.post("/cases/qr", files=files)
    assert resp.status_code == 201
    data = resp.json()
    assert data["input_type"] == "qr_image"
    assert "scammer.fast@okaxis" in data["raw_input"]


@pytest.mark.asyncio
async def test_post_qr_oversized_rejected(client):
    """Uploading QR image larger than 5 MB is rejected with 400."""
    oversized_bytes = b"0" * (5 * 1024 * 1024 + 10)
    files = {"file": ("big.png", oversized_bytes, "image/png")}
    resp = await client.post("/cases/qr", files=files)
    assert resp.status_code == 400
    assert "exceeds 5 MB" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_case_detail_and_not_found(client):
    """GET /cases/{id} returns details and 404 for unknown case ID."""
    # Unknown ID -> 404
    missing_id = str(uuid.uuid4())
    r404 = await client.get(f"/cases/{missing_id}")
    assert r404.status_code == 404
    assert "not found" in r404.json()["detail"].lower()

    # Valid case
    create_resp = await client.post(
        "/cases",
        json={"input_type": "link", "raw_input": "https://scam-lookup.org/lure"},
    )
    case_id = create_resp.json()["id"]

    get_resp = await client.get(f"/cases/{case_id}")
    assert get_resp.status_code == 200
    case_detail = get_resp.json()
    assert case_detail["id"] == case_id
    assert len(case_detail["recent_events"]) == 1
    assert case_detail["recent_events"][0]["stage"] == "intake"


@pytest.mark.asyncio
async def test_recent_events_limit_and_order(client, async_db):
    """recent_events never returns more than 20 and is in chronological order."""
    create_resp = await client.post(
        "/cases",
        json={"input_type": "link", "raw_input": "https://event-limit-test.com/run"},
    )
    case_id_str = create_resp.json()["id"]
    case_uuid = uuid.UUID(case_id_str)

    # Insert 25 additional events directly into DB
    async with async_db() as session:
        for i in range(1, 26):
            ev = CaseEvent(
                case_id=case_uuid,
                ts=datetime.now(timezone.utc) + timedelta(seconds=i),
                stage="triage",
                kind="info",
                message=f"Event number {i}",
                data={"seq": i},
            )
            session.add(ev)
        await session.commit()

    # Fetch case detail
    get_resp = await client.get(f"/cases/{case_id_str}")
    assert get_resp.status_code == 200
    events = get_resp.json()["recent_events"]
    assert len(events) == 20
    # Chronological order check: messages should ascend in sequence
    seqs = [e["metadata"].get("seq") for e in events if "seq" in e["metadata"]]
    assert seqs == sorted(seqs)
    # Most recent event (seq 25) should be present at the end
    assert seqs[-1] == 25


@pytest.mark.asyncio
async def test_get_case_events_incremental_polling(client, async_db):
    """GET /cases/{id}/events returns full event history and respects `after` parameter."""
    create_resp = await client.post(
        "/cases",
        json={"input_type": "link", "raw_input": "https://polling-test.com/lure"},
    )
    case_id = create_resp.json()["id"]
    case_uuid = uuid.UUID(case_id)

    async with async_db() as session:
        for i in range(1, 4):
            session.add(
                CaseEvent(
                    case_id=case_uuid,
                    stage="detonation",
                    kind="agent_step",
                    message=f"Step {i}",
                    data={"step": i},
                )
            )
        await session.commit()

    # Fetch all events
    resp_all = await client.get(f"/cases/{case_id}/events")
    assert resp_all.status_code == 200
    all_events = resp_all.json()["events"]
    assert len(all_events) == 4  # 1 initial + 3 new

    first_event_id = all_events[0]["id"]

    # Poll with after=<first_event_id>
    resp_after = await client.get(f"/cases/{case_id}/events?after={first_event_id}")
    assert resp_after.status_code == 200
    filtered_events = resp_after.json()["events"]
    assert len(filtered_events) == 3


@pytest.mark.asyncio
async def test_get_cases_pagination_status_and_include_seed(client, async_db):
    """GET /cases supports pagination, status filter, and include_seed flag."""
    # Seed a known set of cases directly
    now = datetime.now(timezone.utc)
    async with async_db() as session:
        # 3 standard cases
        for i in range(3):
            session.add(
                Case(
                    id=uuid.uuid4(),
                    input_type="link",
                    raw_input=f"https://site-{i}.org",
                    status="intake",
                    created_at=now - timedelta(minutes=i),
                    is_seed=False,
                )
            )
        # 1 completed case
        session.add(
            Case(
                id=uuid.uuid4(),
                input_type="link",
                raw_input="https://completed-site.org",
                status="done",
                created_at=now - timedelta(minutes=10),
                is_seed=False,
            )
        )
        # 1 seed case
        session.add(
            Case(
                id=uuid.uuid4(),
                input_type="link",
                raw_input="https://seed-site.org",
                status="intake",
                created_at=now - timedelta(minutes=15),
                is_seed=True,
            )
        )
        await session.commit()

    # Test limit pagination
    res_page1 = await client.get("/cases?limit=2")
    assert res_page1.status_code == 200
    page1 = res_page1.json()
    assert len(page1["items"]) == 2
    assert page1["total"] == 5
    assert page1["next_cursor"] is not None

    # Fetch page 2 using cursor
    res_page2 = await client.get(f"/cases?limit=2&cursor={page1['next_cursor']}")
    assert res_page2.status_code == 200
    page2 = res_page2.json()
    assert len(page2["items"]) == 2

    # Status filter
    res_done = await client.get("/cases?status=done")
    assert res_done.status_code == 200
    done_items = res_done.json()["items"]
    assert len(done_items) == 1
    assert done_items[0]["status"] == "done"

    # include_seed=false
    res_no_seed = await client.get("/cases?include_seed=false")
    assert res_no_seed.status_code == 200
    assert res_no_seed.json()["total"] == 4


# ---------------------------------------------------------------------------
# 3. Database Migration Test
# ---------------------------------------------------------------------------


def test_alembic_migration_upgrade_and_downgrade():
    """Alembic migration applies cleanly on an empty database and downgrades."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = f.name

    try:
        cfg = Config(str(Path("alembic.ini").resolve()))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{temp_db_path}")

        # Run upgrade to head
        command.upgrade(cfg, "head")

        # Run downgrade to base
        command.downgrade(cfg, "base")
    finally:
        db_file = Path(temp_db_path)
        if db_file.exists():
            db_file.unlink(missing_ok=True)

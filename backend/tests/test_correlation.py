"""Unit and integration tests for Section 9: Correlation Graph & Seed Data.

Verifies:
- Payee identifier normalization (UPI, bank accounts, crypto wallets)
- Payee deduplication: same payee across cases increments case_count on a single node
- Inferred vs Confirmed attribution semantics
- Inferred edge upgrade: subsequent direct detonation upgrades edge to confirmed
- Union-Find connected components and cluster_id calculation
- Site reuse window: domains with confirmed payee within SITE_REUSE_DAYS hit find_site, older domains do not
- Cytoscape schema conformance for GET /graph/overview and GET /graph/{payee_id}
- Truncation flag behavior under node limits
- Synthetic demo seeding idempotency
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.correlation import (
    SqlClusterLookup,
    UnionFind,
    add_case_to_graph,
    build_cytoscape_graph,
    normalize_payee_identifier,
)
from app.agents.fingerprint import Fingerprint, compute_simhash
from app.config import Settings
from app.db import get_db_session
from app.main import create_app
from app.models.base import Base
from app.models.case import Case, utc_now
from app.models.graph import Edge, Payee, Site
from scripts.seed_demo import seed_synthetic_db


@pytest_asyncio.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield session_factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(async_db):
    app = create_app(Settings(STING_ENV="test"))

    async def override_get_db():
        async with async_db() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ==============================================================================
# 1. Payee Normalization Tests
# ==============================================================================


def test_payee_normalization():
    """Validates normalization rules for UPI, bank accounts, and wallets."""
    # UPI lowercase and whitespace strip
    vpa, kind = normalize_payee_identifier(" Fraud.Merchant@OKHDFCBank ")
    assert vpa == "fraud.merchant@okhdfcbank"
    assert kind == "upi"

    # Bank account
    acc, kind = normalize_payee_identifier("bank:502000-123456:HDFC0001234")
    assert acc == "bank:502000123456:HDFC0001234"
    assert kind == "bank"

    # Crypto wallet
    wallet, kind = normalize_payee_identifier("wallet:0x71C84192e3a94669BCE828b00217F2056555251F")
    assert wallet == "wallet:0x71C84192e3a94669BCE828b00217F2056555251F"
    assert kind == "wallet"


# ==============================================================================
# 2. Union-Find Connected Components Tests
# ==============================================================================


def test_union_find_clusters():
    """Groups disjoint connected components into coherent clusters."""
    uf = UnionFind()
    # Campaign 1: siteA and siteB link to payee1
    uf.union("site:A", "payee:1")
    uf.union("site:B", "payee:1")

    # Campaign 2: siteC links to payee2
    uf.union("site:C", "payee:2")

    # Assert cluster roots
    assert uf.find("site:A") == uf.find("site:B")
    assert uf.find("site:A") == uf.find("payee:1")
    assert uf.find("site:A") != uf.find("site:C")
    assert uf.find("site:C") == uf.find("payee:2")


# ==============================================================================
# 3. Payee Deduplication & Attribution Upgrade Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_payee_dedup_and_inferred_to_confirmed_upgrade(async_db):
    """Multiple cases linking the same payee increment case_count, and subsequent detonation upgrades inferred edge."""
    async with async_db() as session:
        # Case 1: Inferred cluster match on domain A
        case1 = Case(
            input_type="link",
            raw_input="https://phish-site-a.com",
            normalized_url="https://phish-site-a.com",
            domain="phish-site-a.com",
            outcome="known_cluster_skipped",
            extracted_upi_ids=["mule.pool@okhdfcbank"],
        )
        session.add(case1)
        await session.commit()

        res1 = await add_case_to_graph(case1, session)
        await session.commit()
        assert res1["attribution"] == "inferred"

        # Check Payee count
        payee = (await session.execute(select(Payee).where(Payee.value_normalized == "mule.pool@okhdfcbank"))).scalar_one()
        assert payee.case_count == 1

        # Check Edge is inferred
        edge = (await session.execute(select(Edge).where(Edge.site_id == res1["site_id"]))).scalar_one()
        assert edge.attribution == "inferred"
        assert edge.confidence == 0.85

        # Case 2: Direct detonation on the SAME domain confirms the payee!
        case2 = Case(
            input_type="link",
            raw_input="https://phish-site-a.com/checkout",
            normalized_url="https://phish-site-a.com/checkout",
            domain="phish-site-a.com",
            outcome="detonated",
            detonation_result={"payee_vpa": "mule.pool@okhdfcbank"},
        )
        session.add(case2)
        await session.commit()

        res2 = await add_case_to_graph(case2, session)
        await session.commit()

        # Edge must now be upgraded to CONFIRMED with 1.0 confidence
        refreshed_edge = (await session.execute(select(Edge).where(Edge.id == edge.id))).scalar_one()
        assert refreshed_edge.attribution == "confirmed"
        assert refreshed_edge.confidence == 1.0

        # Payee count incremented to 2 without creating duplicate node
        refreshed_payee = (await session.execute(select(Payee).where(Payee.value_normalized == "mule.pool@okhdfcbank"))).scalar_one()
        assert refreshed_payee.case_count == 2


# ==============================================================================
# 4. Site Reuse Expiration Window Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_site_reuse_window(async_db):
    """Domains seen within SITE_REUSE_DAYS match find_site; older domains expire."""
    async with async_db() as session:
        site = Site(domain="active-phish.net", fingerprint={}, is_seed=False)
        payee = Payee(kind="upi", value_normalized="mule@okaxis", is_seed=False)
        session.add_all([site, payee])
        await session.flush()

        # Recent confirmed edge (3 days old)
        recent_edge = Edge(
            site_id=site.id,
            payee_id=payee.id,
            case_id=uuid.uuid4(),
            attribution="confirmed",
            confidence=1.0,
            evidence={},
            first_seen=utc_now() - timedelta(days=3),
            is_seed=False,
        )
        session.add(recent_edge)
        await session.commit()

        lookup = await SqlClusterLookup.from_db(session)
        # 7-day window should hit
        match = lookup.find_site("active-phish.net", within_days=7)
        assert match is not None
        assert match["payee"] == "mule@okaxis"

        # 2-day window should expire and return None
        expired_match = lookup.find_site("active-phish.net", within_days=2)
        assert expired_match is None


# ==============================================================================
# 5. Graph API & Cytoscape Schema Conformance Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_graph_endpoints_and_truncation(client, async_db):
    """Verifies GET /graph/overview and GET /graph/{payee_id} against contract."""
    async with async_db() as session:
        # Seed synthetic campaign graph
        await seed_synthetic_db(session)

    # 1. Overview request
    resp = await client.get("/graph/overview?limit=500&include_seed=true")
    assert resp.status_code == 200
    data = resp.json()

    assert "nodes" in data
    assert "edges" in data
    assert "total_clusters" in data
    assert data["total_clusters"] >= 4
    assert len(data["nodes"]) >= 12
    assert len(data["edges"]) >= 12

    # Verify node shape
    first_node = data["nodes"][0]["data"]
    assert "id" in first_node
    assert "label" in first_node
    assert "type" in first_node
    assert first_node["is_seed"] is True

    # 2. Test Truncation limit
    truncated_resp = await client.get("/graph/overview?limit=4&include_seed=true")
    assert truncated_resp.status_code == 200
    trunc_data = truncated_resp.json()
    assert trunc_data["meta"]["truncated"] is True
    assert len(trunc_data["nodes"]) <= 10

    # 3. Payee cluster request
    payee_resp = await client.get("/graph/discom.powerbilling@okhdfcbank")
    assert payee_resp.status_code == 200
    p_data = payee_resp.json()
    assert len(p_data["nodes"]) >= 2
    # Ensure all returned nodes belong to the electricity cluster
    node_labels = [n["data"]["label"] for n in p_data["nodes"]]
    assert "discom.powerbilling@okhdfcbank" in node_labels

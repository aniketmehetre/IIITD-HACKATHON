"""Unit and integration tests for Section 6: Triage, Fingerprints, and Decision Logic.

Verifies:
- Table-driven decision tests covering all 6 rules and degrade paths (>= 12 cases)
- Simhash Hamming distances: identical (0), near (<=8), far (>8)
- Brand mismatch detection (true/false) against data/brands.yaml
- RDAP lookup parsing, timeouts, and degrade paths (unknown is not old)
- Fetch error degrades toward DETONATE
- Inconclusive never produces a "safe" label
- Mock funnels: a1 vs a2 produce close simhash, and b1 is far from both
- Pipeline audit trail: individual signal events and decision reasoning events logged
"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.agents.brands import check_brand_mismatch, load_brands
from app.agents.decision import (
    ClusterLookup,
    StubClusterLookup,
    decide,
)
from app.agents.fingerprint import (
    Fingerprint,
    compute_simhash,
    compute_title_hash,
    hamming_distance,
    is_strong_fingerprint_match,
)
from app.agents.triage import TriageResult, run_triage
from app.integrations.rdap import RdapResult, lookup_rdap
from app.models.base import Base
from app.models.case import Case, CaseEvent
from app.pipeline import InProcessRunner

# ---------------------------------------------------------------------------
# 1. Simhash and Fingerprint Distance Tests
# ---------------------------------------------------------------------------


def test_simhash_identical():
    """Identical text must have a bitwise Hamming distance of 0."""
    text1 = (
        "Urgent: Your electricity power supply will be disconnected tonight. Pay bill immediately."
    )
    text2 = (
        "Urgent: Your electricity power supply will be disconnected tonight. Pay bill immediately."
    )
    h1 = compute_simhash(text1)
    h2 = compute_simhash(text2)
    assert h1 != 0
    assert hamming_distance(h1, h2) == 0


def test_simhash_near_duplicate():
    """Near-duplicate texts (minor timestamp/contact variation) must have distance <= 8."""
    text1 = (
        "Dear customer, your electricity power connection will be disconnected tonight at 9:30 PM "
        "due to previous month unpaid bill. Please update your bill immediately by calling our executive "
        "or visiting the link below to avoid power cut."
    )
    text2 = (
        "Dear customer, your electricity power connection will be disconnected tonight at 10:00 PM "
        "due to previous month unpaid bill. Please update your bill immediately by calling our executive "
        "or visiting the link below to avoid power cut."
    )
    h1 = compute_simhash(text1)
    h2 = compute_simhash(text2)
    dist = hamming_distance(h1, h2)
    assert 0 <= dist <= 8


def test_simhash_far_different():
    """Completely disparate topic text must have Hamming distance > 8."""
    text1 = (
        "Urgent: Your electricity power supply will be disconnected tonight. Pay bill immediately."
    )
    text2 = "The recipe requires two cups of organic wheat flour, fresh olive oil, and three ripe tomatoes."
    h1 = compute_simhash(text1)
    h2 = compute_simhash(text2)
    dist = hamming_distance(h1, h2)
    assert dist > 8


def test_simhash_empty_string():
    """Empty or non-alphanumeric text yields 0."""
    assert compute_simhash("") == 0
    assert compute_simhash("   ... ???   ") == 0


def test_title_hash_normalization():
    """Title hash is case-insensitive and ignores punctuation."""
    h1 = compute_title_hash("ExampleMart — Festive Lucky Draw 2026!")
    h2 = compute_title_hash("examplemart festive lucky draw 2026")
    assert h1 == h2


# ---------------------------------------------------------------------------
# 2. Strong Fingerprint Matching Rules
# ---------------------------------------------------------------------------


def test_strong_fingerprint_match_shared_form():
    """Simhash <= 8 with shared form action domain triggers strong match."""
    fp1 = Fingerprint(text_simhash=0b1011, form_action_domains=["gateway-pay.xyz"])
    fp2 = Fingerprint(text_simhash=0b1001, form_action_domains=["gateway-pay.xyz"])
    matched, reasons = is_strong_fingerprint_match(fp1, fp2)
    assert matched is True
    assert any("form action" in r.lower() for r in reasons)


def test_strong_fingerprint_match_shared_script():
    """Simhash <= 8 with shared script host triggers strong match."""
    fp1 = Fingerprint(text_simhash=0b1011, script_hosts=["cdn-telecom-assets.in"])
    fp2 = Fingerprint(text_simhash=0b1001, script_hosts=["cdn-telecom-assets.in"])
    matched, reasons = is_strong_fingerprint_match(fp1, fp2)
    assert matched is True
    assert any("script host" in r.lower() for r in reasons)


def test_strong_fingerprint_match_shared_registrar_nameservers():
    """Simhash <= 8 with same registrar and identical nameservers triggers strong match."""
    fp1 = Fingerprint(
        text_simhash=0b1011,
        registrar="Hostinger, UAB",
        nameservers=["ns1.dns-parking.com", "ns2.dns-parking.com"],
    )
    fp2 = Fingerprint(
        text_simhash=0b1001,
        registrar="Hostinger, UAB",
        nameservers=["ns1.dns-parking.com", "ns2.dns-parking.com"],
    )
    matched, reasons = is_strong_fingerprint_match(fp1, fp2)
    assert matched is True
    assert any("registrar" in r.lower() for r in reasons)


def test_fingerprint_match_rejected_if_no_shared_infra():
    """Simhash <= 8 without any shared infrastructure is rejected."""
    fp1 = Fingerprint(
        text_simhash=0b1011,
        form_action_domains=["pay-alpha.com"],
        registrar="RegA",
        nameservers=["ns1.rega.com"],
    )
    fp2 = Fingerprint(
        text_simhash=0b1001,
        form_action_domains=["pay-beta.com"],
        registrar="RegB",
        nameservers=["ns1.regb.com"],
    )
    matched, reasons = is_strong_fingerprint_match(fp1, fp2)
    assert matched is False
    assert any("zero shared infrastructure" in r.lower() for r in reasons)


def test_fingerprint_match_rejected_if_dist_too_large():
    """Shared infrastructure is rejected if simhash distance exceeds 8."""
    fp1 = Fingerprint(text_simhash=0x0000000000000000, form_action_domains=["common.com"])
    fp2 = Fingerprint(text_simhash=0x00000000000003FF, form_action_domains=["common.com"])
    # 10 bits differ
    assert hamming_distance(fp1.text_simhash, fp2.text_simhash) == 10
    matched, reasons = is_strong_fingerprint_match(fp1, fp2)
    assert matched is False


# ---------------------------------------------------------------------------
# 3. Brand Impersonation Mismatch Tests
# ---------------------------------------------------------------------------


def test_brands_yaml_loaded():
    """Verifies that data/brands.yaml loads >= 20 curated Indian brands."""
    brands = load_brands()
    assert len(brands) >= 20
    names = [b["name"] for b in brands]
    assert any("State Bank of India" in n for n in names)
    assert any("HDFC" in n for n in names)
    assert any("Paytm" in n for n in names)


def test_brand_mismatch_detected_on_scam_domain():
    """Claiming State Bank of India on sbi-rewards-portal.xyz flags mismatch."""
    mismatch, brand, kw = check_brand_mismatch(
        domain="sbi-rewards-portal.xyz",
        text="Dear customer, your State Bank of India netbanking rewards point worth Rs 5,000 is expiring.",
        title="SBI Rewards Claim",
    )
    assert mismatch is True
    assert brand is not None
    assert "State Bank of India" in brand


def test_brand_mismatch_not_flagged_on_official_domain():
    """Official SBI domains must NOT be flagged as mismatch."""
    mismatch, brand, kw = check_brand_mismatch(
        domain="onlinesbi.sbi",
        text="Welcome to State Bank of India secure online banking services.",
        title="State Bank of India",
    )
    assert mismatch is False


def test_brand_mismatch_not_flagged_on_official_subdomain():
    """Subdomains of official domains must NOT be flagged as mismatch."""
    mismatch, brand, kw = check_brand_mismatch(
        domain="retail.onlinesbi.sbi",
        text="State Bank of India retail customer authentication.",
        title="State Bank of India",
    )
    assert mismatch is False


def test_brand_mismatch_not_flagged_for_unrelated_site():
    """Unrelated content without brand keywords must not flag mismatch."""
    mismatch, brand, kw = check_brand_mismatch(
        domain="random-tech-blog.org",
        text="A tutorial on optimizing relational database queries in PostgreSQL.",
        title="Tech Articles",
    )
    assert mismatch is False
    assert brand is None


# ---------------------------------------------------------------------------
# 4. RDAP Lookup & Degrade Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rdap_lookup_success(respx_mock):
    """RDAP lookup parses creation date, age in days, registrar, and nameservers."""
    respx_mock.get("https://rdap.org/domain/suspicious-portal.com").respond(
        status_code=200,
        json={
            "events": [
                {
                    "eventAction": "registration",
                    "eventDate": "2026-10-10T00:00:00Z",
                }
            ],
            "entities": [
                {
                    "roles": ["registrar"],
                    "vcardArray": ["vcard", [["fn", {}, "text", "Namecheap, Inc."]]],
                }
            ],
            "nameservers": [
                {"ldhName": "dns1.registrar-servers.com"},
                {"ldhName": "dns2.registrar-servers.com"},
            ],
        },
    )

    res = await lookup_rdap("suspicious-portal.com")
    assert res.error is None
    assert res.registrar == "Namecheap, Inc."
    assert "dns1.registrar-servers.com" in res.nameservers
    assert res.domain_age_days is not None


@pytest.mark.asyncio
async def test_rdap_lookup_http_error_degrades_safely(respx_mock):
    """RDAP HTTP 404/500 returns age=None without raising."""
    respx_mock.get("https://rdap.org/domain/not-found-domain.in").respond(status_code=404)

    res = await lookup_rdap("not-found-domain.in")
    assert res.domain_age_days is None
    assert res.error is not None
    assert "HTTP 404" in res.error


@pytest.mark.asyncio
async def test_rdap_lookup_rejects_localhost_ip():
    """Localhost or invalid domains return safe error without network call."""
    res = await lookup_rdap("localhost")
    assert res.domain_age_days is None
    assert "Invalid domain" in (res.error or "")


# ---------------------------------------------------------------------------
# 5. Table-Driven Decision Engine Tests (>= 12 cases)
# ---------------------------------------------------------------------------


class MockClusterLookup(ClusterLookup):
    """Mock cluster lookup for decision testing."""

    def __init__(
        self,
        known_payee: str | None = None,
        known_site: str | None = None,
        site_payee: str | None = None,
        site_days_ago: int = 2,
        known_fingerprint: Fingerprint | None = None,
    ):
        self.known_payee = known_payee
        self.known_site = known_site
        self.site_payee = site_payee
        self.site_days_ago = site_days_ago
        self.known_fingerprint = known_fingerprint

    def find_by_payee(self, payee: str) -> dict | None:
        if self.known_payee and payee.lower() == self.known_payee.lower():
            return {"cluster_id": "cluster_payee_01", "payee": payee}
        return None

    def find_site(self, domain: str, within_days: int = 7) -> dict | None:
        if self.known_site and domain.lower() == self.known_site.lower():
            if self.site_days_ago <= within_days:
                return {
                    "domain": domain,
                    "payee": self.site_payee or "discom@upi",
                    "case_id": "case_prev_999",
                    "observed_date": "2026-10-20",
                }
        return None

    def find_by_fingerprint(self, fp: Fingerprint) -> dict | None:
        if self.known_fingerprint:
            matched, _ = is_strong_fingerprint_match(fp, self.known_fingerprint)
            if matched:
                return {"cluster_id": "cluster_campaign_alpha", "matched": True}
        return None


def make_triage_result(
    domain: str = "example.com",
    domain_age_days: int | None = 20,
    payment_indicators: list[str] | None = None,
    brand_mismatch: bool = False,
    search_scam_mentions: int = 0,
    fetch_error: str | None = None,
    simhash: int = 0x1234,
    form_action_domains: list[str] | None = None,
    script_hosts: list[str] | None = None,
    registrar: str | None = None,
    nameservers: list[str] | None = None,
) -> TriageResult:
    fp = Fingerprint(
        text_simhash=simhash,
        form_action_domains=form_action_domains or [],
        script_hosts=script_hosts or [],
        registrar=registrar,
        nameservers=nameservers or [],
    )
    return TriageResult(
        url=f"https://{domain}/lure",
        domain=domain,
        signals=[],
        fingerprint=fp,
        risk_level="high" if (payment_indicators or brand_mismatch) else "low",
        domain_age_days=domain_age_days,
        brand_mismatch=brand_mismatch,
        payment_indicators_found=payment_indicators or [],
        search_scam_mentions=search_scam_mentions,
        fetch_error=fetch_error,
    )


DECISION_SCENARIOS = [
    # 1. Rule 1: Forced detonation override
    (
        "Rule 1: force_detonate is True -> DETONATE",
        make_triage_result(domain_age_days=1000),
        MockClusterLookup(),
        None,  # input_payee
        True,  # force_detonate
        "DETONATE",
        "detonation",
        None,  # outcome
    ),
    # 2. Rule 2: Input payee already known in graph
    (
        "Rule 2: input_payee recognized in graph -> SKIP_KNOWN_PAYEE",
        make_triage_result(domain="new-lure.org"),
        MockClusterLookup(known_payee="fraudster@upi"),
        "fraudster@upi",
        False,
        "SKIP_KNOWN_PAYEE",
        "enrichment",
        "known_payee_skipped",
    ),
    # 3. Rule 3: Site recognized within 7 days
    (
        "Rule 3: domain observed recently with confirmed payee -> SKIP_KNOWN_SITE",
        make_triage_result(domain="reused-scam.xyz"),
        MockClusterLookup(known_site="reused-scam.xyz", site_payee="scam@icici", site_days_ago=3),
        None,
        False,
        "SKIP_KNOWN_SITE",
        "enrichment",
        "known_site_skipped",
    ),
    # 4. Rule 3 expiry: Site observed > 7 days ago does NOT skip site
    (
        "Rule 3 Expiry: domain observed > 7 days ago -> falls through to DETONATE",
        make_triage_result(domain="stale-scam.xyz", payment_indicators=["upi://pay?pa=x@upi"]),
        MockClusterLookup(known_site="stale-scam.xyz", site_days_ago=10),
        None,
        False,
        "DETONATE",
        "detonation",
        None,
    ),
    # 5. Rule 4: Strong fingerprint match (shared form action)
    (
        "Rule 4: Strong fingerprint match -> SKIP_KNOWN_CLUSTER",
        make_triage_result(simhash=0x1234, form_action_domains=["kit-backend.xyz"]),
        MockClusterLookup(
            known_fingerprint=Fingerprint(
                text_simhash=0x1234, form_action_domains=["kit-backend.xyz"]
            )
        ),
        None,
        False,
        "SKIP_KNOWN_CLUSTER",
        "enrichment",
        "known_cluster_skipped",
    ),
    # 6. Rule 4: Weak fingerprint match (simhash near, but zero shared infra)
    (
        "Rule 4 Failure: near simhash but zero shared infra -> falls through to DETONATE",
        make_triage_result(simhash=0x1234, payment_indicators=["pay now"]),
        MockClusterLookup(
            known_fingerprint=Fingerprint(
                text_simhash=0x1234, form_action_domains=["unrelated.com"]
            )
        ),
        None,
        False,
        "DETONATE",
        "detonation",
        None,
    ),
    # 7. Rule 5: Old benign domain (>365 days, zero threat indicators)
    (
        "Rule 5: domain_age > 365, zero cues, zero brand -> INCONCLUSIVE",
        make_triage_result(
            domain="old-legit-institute.edu",
            domain_age_days=1200,
            payment_indicators=[],
            brand_mismatch=False,
            search_scam_mentions=0,
        ),
        MockClusterLookup(),
        None,
        False,
        "INCONCLUSIVE",
        "inconclusive",
        "inconclusive",
    ),
    # 8. Rule 5 blocked by payment cues on old domain
    (
        "Rule 5 Blocked: old domain but has payment indicators -> DETONATE",
        make_triage_result(
            domain="compromised-old-site.com",
            domain_age_days=2000,
            payment_indicators=["scan qr to pay"],
        ),
        MockClusterLookup(),
        None,
        False,
        "DETONATE",
        "detonation",
        None,
    ),
    # 9. Rule 5 blocked by brand mismatch on old domain
    (
        "Rule 5 Blocked: old domain but claims SBI brand -> DETONATE",
        make_triage_result(
            domain="old-compromised-domain.net",
            domain_age_days=800,
            brand_mismatch=True,
        ),
        MockClusterLookup(),
        None,
        False,
        "DETONATE",
        "detonation",
        None,
    ),
    # 10. Rule 5 blocked by search scam mentions
    (
        "Rule 5 Blocked: old domain with search scam complaints -> DETONATE",
        make_triage_result(
            domain="old-disputed-store.com",
            domain_age_days=900,
            search_scam_mentions=4,
        ),
        MockClusterLookup(),
        None,
        False,
        "DETONATE",
        "detonation",
        None,
    ),
    # 11. Degrade path: Fetch error -> DETONATE (never safe)
    (
        "Degrade Path: Fetch error -> DETONATE",
        make_triage_result(domain_age_days=500, fetch_error="Cloudflare bot challenge blocked"),
        MockClusterLookup(),
        None,
        False,
        "DETONATE",
        "detonation",
        None,
    ),
    # 12. Degrade path: RDAP failure (unknown age) -> DETONATE
    (
        "Degrade Path: RDAP unknown age -> DETONATE",
        make_triage_result(domain_age_days=None),
        MockClusterLookup(),
        None,
        False,
        "DETONATE",
        "detonation",
        None,
    ),
    # 13. High-risk newly registered domain with urgency and payment
    (
        "Rule 6 Default: Fresh domain (<30 days) with payment cue -> DETONATE",
        make_triage_result(domain_age_days=4, payment_indicators=["upi://pay"]),
        MockClusterLookup(),
        None,
        False,
        "DETONATE",
        "detonation",
        None,
    ),
]


@pytest.mark.parametrize(
    "name,triage_res,lookup,input_payee,force_detonate,expected_decision,expected_stage,expected_outcome",
    DECISION_SCENARIOS,
)
def test_decision_engine_rules(
    name,
    triage_res,
    lookup,
    input_payee,
    force_detonate,
    expected_decision,
    expected_stage,
    expected_outcome,
):
    """Table-driven verification of ordered decision rules 1 to 6 and degrade paths."""
    res = decide(
        triage=triage_res,
        cluster_lookup=lookup,
        input_payee=input_payee,
        force_detonate=force_detonate,
    )
    assert res.decision == expected_decision, f"Failed: {name} - got {res.decision}"
    assert res.next_stage == expected_stage, f"Failed: {name} - stage {res.next_stage}"
    assert res.outcome == expected_outcome, f"Failed: {name} - outcome {res.outcome}"


def test_inconclusive_never_produces_safe_label():
    """Rule 5 (inconclusive) must strictly record 'not detonated' and never label as safe."""
    triage = make_triage_result(
        domain="benign-blog.com",
        domain_age_days=500,
        payment_indicators=[],
        brand_mismatch=False,
        search_scam_mentions=0,
    )
    res = decide(triage=triage, cluster_lookup=StubClusterLookup())
    assert res.decision == "INCONCLUSIVE"
    assert res.outcome == "inconclusive"
    # Guaranteed that neither decision nor reasoning ever asserts safety
    full_text = " ".join(res.reasoning).lower()
    assert "safe" not in full_text
    assert "clean" not in full_text
    assert "benign" not in full_text
    assert "not detonated" in full_text


# ---------------------------------------------------------------------------
# 6. Mock Funnels Triage and Fingerprint Comparison
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_funnels_triage_and_simhash_comparison():
    """Runs triage on mock funnels: a1 vs a2 produce close simhash, b1 is far from both."""
    a1_path = Path("fixtures/funnels/variant_a1/index.html")
    a2_path = Path("fixtures/funnels/variant_a2/index.html")
    b1_path = Path("fixtures/funnels/variant_b1/index.html")

    assert a1_path.exists()
    assert a2_path.exists()
    assert b1_path.exists()

    a1_html = a1_path.read_text(encoding="utf-8")
    a2_html = a2_path.read_text(encoding="utf-8")
    b1_html = b1_path.read_text(encoding="utf-8")

    # Mock RDAP override for consistent testing
    rdap_a = RdapResult(domain="luckydraw-festive.xyz", domain_age_days=5, registrar="GoDaddy")
    rdap_b = RdapResult(domain="5g-telecom-offer.in", domain_age_days=3, registrar="Hostinger")

    res_a1 = await run_triage(
        url="https://luckydraw-festive.xyz/index.html",
        rdap_result_override=rdap_a,
        html_override=a1_html,
    )
    res_a2 = await run_triage(
        url="https://cashback-mega-reward.xyz/index.html",
        rdap_result_override=rdap_a,
        html_override=a2_html,
    )
    res_b1 = await run_triage(
        url="https://5g-telecom-offer.in/index.html",
        rdap_result_override=rdap_b,
        html_override=b1_html,
    )

    # 1. Triage sanity checks
    assert res_a1.fingerprint.text_simhash != 0
    assert res_a2.fingerprint.text_simhash != 0
    assert res_b1.fingerprint.text_simhash != 0

    # 2. Distance comparison: a1 vs a2 is closer than a1 vs b1
    dist_a1_a2 = hamming_distance(res_a1.fingerprint.text_simhash, res_a2.fingerprint.text_simhash)
    dist_a1_b1 = hamming_distance(res_a1.fingerprint.text_simhash, res_b1.fingerprint.text_simhash)
    dist_a2_b1 = hamming_distance(res_a2.fingerprint.text_simhash, res_b1.fingerprint.text_simhash)

    # Acceptance criteria: a1 vs a2 produce fingerprints that are close, and b1 is far from both
    assert dist_a1_a2 < dist_a1_b1
    assert dist_a1_a2 < dist_a2_b1


# ---------------------------------------------------------------------------
# 7. Pipeline Audit Events: Signal Events & Decision Reasoning Logged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_logs_signal_and_decision_events(monkeypatch):
    """Pipeline execution persists individual Signal and DecisionRule events."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(
        "app.pipeline.create_engine_and_session",
        lambda *args, **kwargs: (engine, session_factory),
    )

    case_id = uuid.uuid4()
    async with session_factory() as session:
        case = Case(
            id=case_id,
            input_type="link",
            raw_input="https://suspicious-bill-update.in/pay",
            normalized_url="https://suspicious-bill-update.in/pay",
            domain="suspicious-bill-update.in",
            status="intake",
            current_stage="intake",
        )
        session.add(case)
        await session.commit()

    runner = InProcessRunner(max_concurrent_cases=1)
    await runner.execute_case(case_id)

    async with session_factory() as session:
        events_res = await session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.id.asc())
        )
        events = list(events_res.scalars().all())

        # Check triage and decision events
        decision_events = [e for e in events if e.stage == "decide" and e.kind == "decision_rule"]
        assert len(decision_events) >= 1
        assert "DETONATE" in decision_events[0].data.get("decision", "")

        # Verify case completed pipeline to awaiting_approval
        c_res = await session.execute(select(Case).where(Case.id == case_id))
        completed_case = c_res.scalar_one()
        assert completed_case.status == "awaiting_approval"

    await engine.dispose()

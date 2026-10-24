"""Demo Seeding Script for STING Intelligence Platform.

Supports two distinct operation modes:
1. --synthetic-db: Zero paid calls. Injects 12 simulated phishing sites, 4 mule payees,
   and mixed confirmed/inferred edges flagged is_seed=True for demo visualization.
2. --live: Executes the pipeline sequentially over fixtures/funnel_urls.json:
   a1 (detonates) -> a2 (SKIP_KNOWN_CLUSTER) -> b1 (detonates) -> c1 (INCONCLUSIVE).

Usage:
  python scripts/seed_demo.py --synthetic-db
  python scripts/seed_demo.py --live
"""

import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import uuid

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "backend"))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.correlation import add_case_to_graph
from app.agents.fingerprint import Fingerprint, compute_simhash
from app.config import Settings, get_settings
from app.db import create_engine_and_session
from app.models.base import Base
from app.models.case import Case, CaseEvent, utc_now
from app.models.graph import Edge, Payee, Site
from app.pipeline import InProcessRunner


# ==============================================================================
# Synthetic Database Seeder (Zero Cost, Fully Labelled)
# ==============================================================================


SYNTHETIC_CAMPAIGNS = [
    # Campaign Alpha: Power Discom Impersonation Ring (HDFC / Google Pay)
    {
        "payee": "discom.powerbilling@okhdfcbank",
        "kind": "upi",
        "sponsor_bank": "HDFC Bank",
        "domains": [
            {"domain": "power-bill-discom-alert.biz", "confirmed": True, "simhash_base": "urgent electricity disconnect notice immediate payment"},
            {"domain": "state-electricity-bill-pay.org", "confirmed": True, "simhash_base": "urgent electricity disconnect notice immediate payment fee"},
            {"domain": "discom-bill-update-online.in", "confirmed": False, "simhash_base": "urgent electricity disconnect notice immediate payment"},
            {"domain": "bijli-bill-recovery-desk.net", "confirmed": False, "simhash_base": "urgent electricity disconnect notice immediate payment dues"},
        ],
    },
    # Campaign Beta: Instant Loan Processing Fee Racket (Yes Bank / PhonePe)
    {
        "payee": "instant.approval.desk@ybl",
        "kind": "upi",
        "sponsor_bank": "Yes Bank",
        "domains": [
            {"domain": "fast-mudra-loan-apply.com", "confirmed": True, "simhash_base": "pre approved loan sanction disbursal processing charges required"},
            {"domain": "pm-mudra-instant-approval.net", "confirmed": True, "simhash_base": "pre approved loan sanction disbursal processing charges required fee"},
            {"domain": "aadhaar-loan-express-payout.org", "confirmed": False, "simhash_base": "pre approved loan sanction disbursal processing charges required"},
        ],
    },
    # Campaign Gamma: Fake Job Offer & Work-from-Home Scam (TRON USDT)
    {
        "payee": "wallet:TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        "kind": "wallet",
        "sponsor_bank": "TRON Network",
        "domains": [
            {"domain": "wfh-global-daily-payouts.biz", "confirmed": True, "simhash_base": "hotel booking review task earn 5000 daily deposit usdt security deposit"},
            {"domain": "youtube-like-earn-money.online", "confirmed": False, "simhash_base": "hotel booking review task earn 5000 daily deposit usdt security deposit task"},
        ],
    },
    # Campaign Delta: Telecom KYC SIM Block Lure (Paytm Payments Bank)
    {
        "payee": "telecom.simverification@ptsbi",
        "kind": "upi",
        "sponsor_bank": "State Bank of India",
        "domains": [
            {"domain": "jio-airtel-sim-kyc-update.com", "confirmed": True, "simhash_base": "sim card will be deactivated within 24 hours kyc document fee"},
            {"domain": "telecom-service-desk-verify.in", "confirmed": True, "simhash_base": "sim card will be deactivated within 24 hours kyc document fee pay"},
            {"domain": "vip-sim-activation-portal.net", "confirmed": False, "simhash_base": "sim card will be deactivated within 24 hours kyc document fee"},
        ],
    },
]


async def seed_synthetic_db(session: AsyncSession) -> None:
    """Inserts pre-baked campaign graph nodes and edges flagged is_seed=True."""
    print("[*] Clearing prior synthetic seed data...")
    await session.execute(delete(Edge).where(Edge.is_seed == True))  # noqa: E712
    await session.execute(delete(Site).where(Site.is_seed == True))  # noqa: E712
    await session.execute(delete(Payee).where(Payee.is_seed == True))  # noqa: E712
    await session.execute(delete(Case).where(Case.is_seed == True))  # noqa: E712
    await session.commit()

    print("[*] Inserting 4 campaign clusters with 12 sites and cross-linked edges...")
    base_time = utc_now() - timedelta(days=14)

    total_sites = 0
    total_edges = 0

    for camp in SYNTHETIC_CAMPAIGNS:
        # Create Payee
        payee = Payee(
            kind=camp["kind"],
            value_normalized=camp["payee"],
            case_count=len(camp["domains"]),
            first_seen=base_time,
            last_seen=utc_now(),
            is_seed=True,
        )
        session.add(payee)
        await session.flush()

        for d_info in camp["domains"]:
            dom = d_info["domain"]
            simhash_val = compute_simhash(d_info["simhash_base"])
            fp = {
                "text_simhash": simhash_val,
                "form_action_domains": [f"gateway.{dom}", "checkout-cdn.net"],
                "script_hosts": ["analytics-tracker.biz", "fast-cdn-cloud.net"],
                "registrar": "NameCheap Inc",
                "nameservers": ["ns1.cloudflare.com", "ns2.cloudflare.com"],
                "creation_week": "2026-W38",
            }

            site = Site(
                domain=dom,
                fingerprint=fp,
                first_seen=base_time + timedelta(hours=total_sites * 12),
                last_seen=utc_now(),
                is_seed=True,
            )
            session.add(site)
            await session.flush()
            total_sites += 1

            # Seed Case representation
            case = Case(
                input_type="link",
                raw_input=f"https://{dom}/claim",
                normalized_url=f"https://{dom}/claim",
                domain=dom,
                status="awaiting_approval",
                current_stage="awaiting_approval",
                outcome="detonated" if d_info["confirmed"] else "known_cluster_skipped",
                is_seed=True,
                extracted_upi_ids=[camp["payee"]] if camp["kind"] == "upi" else [],
                detonation_result={
                    "payee_vpa": camp["payee"] if camp["kind"] == "upi" else None,
                    "blocked_reason": None,
                },
                enrichment_result={
                    "psp_name": camp["sponsor_bank"],
                    "normalized_payees": [camp["payee"]],
                },
            )
            session.add(case)
            await session.flush()

            # Create Edge
            attribution = "confirmed" if d_info["confirmed"] else "inferred"
            confidence = 1.0 if d_info["confirmed"] else 0.85
            edge = Edge(
                site_id=site.id,
                payee_id=payee.id,
                case_id=case.id,
                attribution=attribution,
                confidence=confidence,
                evidence={
                    "synthetic_seed": True,
                    "rationale": "Direct detonation" if d_info["confirmed"] else "Simhash distance <= 8 & shared DNS",
                },
                first_seen=site.first_seen,
                is_seed=True,
            )
            session.add(edge)
            total_edges += 1

    await session.commit()
    print(f"[+] Synthetic seeding complete! Injected {total_sites} sites, {len(SYNTHETIC_CAMPAIGNS)} payees, and {total_edges} edges.")
    print("    All data flagged with is_seed=True.")


# ==============================================================================
# Live Funnel Sequenced Pipeline Runner
# ==============================================================================


async def run_live_seed() -> None:
    """Executes sequential pipeline runs on mock funnels with budgeted runs."""
    urls_path = repo_root / "fixtures" / "funnel_urls.json"
    if not urls_path.exists():
        print(f"[!] Error: {urls_path} not found.")
        return

    with open(urls_path, "r", encoding="utf-8") as f:
        funnel_urls = json.load(f)

    runner = InProcessRunner()
    _, session_factory = create_engine_and_session()

    plan = [
        ("variant_a1", funnel_urls.get("variant_a1"), "Expected DETONATE (fresh campaign)"),
        ("variant_a2", funnel_urls.get("variant_a2"), "Expected SKIP_KNOWN_CLUSTER (inferred from a1)"),
        ("variant_b1", funnel_urls.get("variant_b1"), "Expected DETONATE (distinct campaign)"),
        ("variant_c1", funnel_urls.get("variant_c1"), "Expected INCONCLUSIVE (benign / no payment)"),
    ]

    print("\n" + "=" * 75)
    print("STING — Live Pipeline Funnel Demonstration")
    print("=" * 75)

    for label, url, expectation in plan:
        print(f"\n[*] Processing {label} ({url})...")
        print(f"    Target Policy: {expectation}")

        async with session_factory() as session:
            case = Case(
                input_type="link",
                raw_input=url,
                normalized_url=url,
                status="triage",
                current_stage="triage",
            )
            session.add(case)
            await session.commit()
            case_id = case.id

        await runner.execute_case(case_id)

        async with session_factory() as session:
            refreshed = await session.get(Case, case_id)
            print(f"    [+] Finished with status='{refreshed.status}', outcome='{refreshed.outcome}'")
            if refreshed.extracted_upi_ids:
                print(f"    [+] Extracted Payees: {refreshed.extracted_upi_ids}")

    print("\n[+] Live sequence complete!")


# ==============================================================================
# CLI Entrypoint
# ==============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="STING Demo Seeder")
    parser.add_argument("--synthetic-db", action="store_true", help="Insert pre-baked campaign graph data (0 paid calls)")
    parser.add_argument("--live", action="store_true", help="Run sequential live funnels through pipeline")
    args = parser.parse_args()

    if not args.synthetic_db and not args.live:
        print("Please specify either --synthetic-db or --live")
        parser.print_help()
        sys.exit(1)

    if args.synthetic_db:
        engine, session_factory = create_engine_and_session()
        async def _run_seed():
            import app.models  # ensure all models register on Base.metadata
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with session_factory() as session:
                await seed_synthetic_db(session)
        asyncio.run(_run_seed())

    elif args.live:
        asyncio.run(run_live_seed())


if __name__ == "__main__":
    main()

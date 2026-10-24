"""Deterministic decision engine for autonomous detonation gating.

Conforms strictly to Section 6 specification:
- Ordered deterministic rule evaluation (no LLM ambiguity).
- Gates paid TinyFish browser automation against 3 skip conditions and 1 inconclusive condition.
- Graceful degradation: failures (fetch block, RDAP down) degrade toward DETONATE,
  never toward a safe verdict.
- INCONCLUSIVE is strictly designated as 'not detonated' and never labelled as safe.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from app.agents.fingerprint import Fingerprint
from app.agents.triage import TriageResult

logger = logging.getLogger(__name__)


class ClusterLookup(Protocol):
    """Protocol for querying known payees, sites, and fingerprint clusters."""

    def find_by_payee(self, payee: str) -> Optional[dict[str, Any]]:
        """Look up whether a payee VPA exists in the correlation graph."""
        ...

    def find_site(self, domain: str, within_days: int = 7) -> Optional[dict[str, Any]]:
        """Look up whether a domain has been detonated recently with a confirmed payee."""
        ...

    def find_by_fingerprint(self, fp: Fingerprint) -> Optional[dict[str, Any]]:
        """Look up whether a fingerprint matches an active campaign cluster."""
        ...


class StubClusterLookup:
    """Stub implementation of ClusterLookup returning None (replaced in Section 9)."""

    def find_by_payee(self, payee: str) -> Optional[dict[str, Any]]:
        return None

    def find_site(self, domain: str, within_days: int = 7) -> Optional[dict[str, Any]]:
        return None

    def find_by_fingerprint(self, fp: Fingerprint) -> Optional[dict[str, Any]]:
        return None


@dataclass
class DecisionResult:
    """Explainable output from the decision engine."""

    decision: str  # "DETONATE" | "SKIP_KNOWN_PAYEE" | "SKIP_KNOWN_SITE" | "SKIP_KNOWN_CLUSTER" | "INCONCLUSIVE"
    next_stage: str  # "detonation" | "enrichment" | "inconclusive"
    outcome: Optional[str] = None
    attribution: Optional[str] = None  # "confirmed" | "inferred" | None
    needs_verification: bool = False
    reasoning: list[str] = field(default_factory=list)
    carried_over_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "next_stage": self.next_stage,
            "outcome": self.outcome,
            "attribution": self.attribution,
            "needs_verification": self.needs_verification,
            "reasoning": self.reasoning,
            "carried_over_data": self.carried_over_data,
        }


def decide(
    triage: TriageResult,
    cluster_lookup: Optional[ClusterLookup] = None,
    input_payee: Optional[str] = None,
    force_detonate: bool = False,
    site_reuse_days: int = 7,
) -> DecisionResult:
    """Evaluates ordered decision rules to determine whether to detonate or skip.

    Rules:
    1) force_detonate -> DETONATE
    2) input_payee already known in the graph -> SKIP_KNOWN_PAYEE
    3) domain seen recently with confirmed payee -> SKIP_KNOWN_SITE
    4) strong fingerprint match -> SKIP_KNOWN_CLUSTER
    5) domain age > 365 days AND no payment indicators AND no brand mismatch
       AND no scam mentions AND no cluster match -> INCONCLUSIVE ("not detonated")
    6) otherwise -> DETONATE
    """
    lookup = cluster_lookup or StubClusterLookup()
    reasons: list[str] = []

    # Rule 1: Forced Detonation Override
    if force_detonate:
        reasons.append("Analyst requested forced detonation (bypassing skip rules).")
        return DecisionResult(
            decision="DETONATE",
            next_stage="detonation",
            reasoning=reasons,
        )

    # Rule 2: Input Payee Already Known in Graph
    if input_payee:
        payee_match = lookup.find_by_payee(input_payee)
        if payee_match:
            reasons.append(
                f"Input payee '{input_payee}' already recognized in intelligence graph (Cluster: {payee_match.get('cluster_id')})."
            )
            return DecisionResult(
                decision="SKIP_KNOWN_PAYEE",
                next_stage="enrichment",
                outcome="known_payee_skipped",
                attribution="confirmed",
                reasoning=reasons,
                carried_over_data=payee_match,
            )

    # Rule 3: Known Site Reuse
    site_match = lookup.find_site(triage.domain, within_days=site_reuse_days)
    if site_match and site_match.get("payee"):
        case_id = site_match.get("case_id", "prior_case")
        obs_date = site_match.get("observed_date", "recent")
        reasons.append(f"Carried over from case {case_id} observed on {obs_date}.")
        return DecisionResult(
            decision="SKIP_KNOWN_SITE",
            next_stage="enrichment",
            outcome="known_site_skipped",
            attribution="confirmed",
            reasoning=reasons,
            carried_over_data={
                "payee": site_match.get("payee"),
                "case_id": case_id,
                "observed_date": obs_date,
            },
        )

    # Rule 4: Strong Fingerprint Cluster Match
    cluster_match = lookup.find_by_fingerprint(triage.fingerprint)
    if cluster_match:
        reasons.append(
            f"Strong fingerprint match to cluster '{cluster_match.get('cluster_id')}'; attribution inferred."
        )
        return DecisionResult(
            decision="SKIP_KNOWN_CLUSTER",
            next_stage="enrichment",
            outcome="known_cluster_skipped",
            attribution="inferred",
            needs_verification=True,
            reasoning=reasons,
            carried_over_data=cluster_match,
        )

    # Rule 5: Old Benign Domain -> Inconclusive (Never "Safe")
    # Strict conditions: age known > 365 days AND zero payment indicators
    # AND zero brand mismatch AND zero scam mentions AND no fetch error
    if (
        triage.domain_age_days is not None
        and triage.domain_age_days > 365
        and len(triage.payment_indicators_found) == 0
        and not triage.brand_mismatch
        and triage.search_scam_mentions == 0
        and not triage.fetch_error
    ):
        reasons.append(
            f"Domain age ({triage.domain_age_days} days) > 365 days with zero payment indicators, "
            "zero brand impersonation cues, and zero threat complaints. Not detonated."
        )
        return DecisionResult(
            decision="INCONCLUSIVE",
            next_stage="inconclusive",
            outcome="inconclusive",
            reasoning=reasons,
        )

    # Rule 6: Default -> DETONATE
    # Covers high risk, new domains, unverified indicators, or fetch/RDAP degrade paths
    if triage.fetch_error:
        reasons.append(f"Triage fetch error ({triage.fetch_error}); degrading toward detonation.")
    elif triage.domain_age_days is None:
        reasons.append("Domain registration age is unknown; degrading toward detonation.")
    else:
        reasons.append(
            f"Risk signals detected (Risk level: {triage.risk_level}); autonomous detonation warranted."
        )

    return DecisionResult(
        decision="DETONATE",
        next_stage="detonation",
        reasoning=reasons,
    )

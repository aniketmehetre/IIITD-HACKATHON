"""Campaign Correlation Engine, Graph Intelligence & Cluster Lookup.

Builds the campaign correlation graph linking scam sites and fraudulent payees.
Computes connected-component clusters using Union-Find and provides Cytoscape-compatible
graph representations with honest confirmed vs. inferred attribution semantics.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.decision import ClusterLookup
from app.agents.fingerprint import Fingerprint, is_strong_fingerprint_match
from app.models.case import Case, CaseEvent, utc_now
from app.models.graph import Edge, Payee, Site

logger = logging.getLogger("sting.correlation")


# ==============================================================================
# Payee Normalization Helpers
# ==============================================================================


def normalize_payee_identifier(raw: str) -> tuple[str, str]:
    """Normalizes a raw payee string into a canonical key and resolves kind.

    Returns:
        (canonical_normalized_string, kind)
    """
    clean = raw.strip()
    clean_lower = clean.lower()

    if clean_lower.startswith("bank:"):
        # Format: bank:<acc_number>[:<ifsc>]
        parts = clean.split(":")
        acc = re.sub(r"[\s\-]", "", parts[1])
        if len(parts) >= 3:
            ifsc = parts[2].strip().upper()
            return f"bank:{acc}:{ifsc}", "bank"
        return f"bank:{acc}", "bank"

    if clean_lower.startswith("wallet:"):
        addr = clean.split(":", 1)[1].strip()
        return f"wallet:{addr}", "wallet"

    if clean_lower.startswith("qr:"):
        uri = clean.split(":", 1)[1].strip()
        return f"qr:{uri[:100]}", "qr"

    if "@" in clean:
        # Standard UPI VPA: lowercase, stripped of spaces
        vpa_clean = clean_lower.replace(" ", "")
        return vpa_clean, "upi"

    # Default fallback
    return clean_lower, "upi"


# ==============================================================================
# Disjoint-Set Union-Find for Graph Connected Components
# ==============================================================================


class UnionFind:
    """Disjoint-set data structure for fast cluster identification."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def find(self, x: str) -> str:
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
            return x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: str, y: str) -> None:
        root_x = self.find(x)
        root_y = self.find(y)
        if root_x == root_y:
            return
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1


# ==============================================================================
# Database Cluster Lookup Implementation
# ==============================================================================


class SqlClusterLookup(ClusterLookup):
    """Production implementation of ClusterLookup querying the correlation graph in SQLite/PG."""

    def __init__(self, db: AsyncSession, sites: list[Site], payees: list[Payee], edges: list[Edge]):
        self._db = db
        self._sites = sites
        self._payees = payees
        self._edges = edges
        self._uf = UnionFind()
        self._build_clusters()

    def _build_clusters(self) -> None:
        for edge in self._edges:
            s_node = f"domain:{edge.site.domain}" if edge.site else f"site:{edge.site_id}"
            p_node = f"payee:{edge.payee.value_normalized}" if edge.payee else f"payee_id:{edge.payee_id}"
            self._uf.union(s_node, p_node)

    @classmethod
    async def from_db(cls, db: AsyncSession) -> SqlClusterLookup:
        """Asynchronously loads the active graph and initializes the lookup helper."""
        sites_res = await db.execute(select(Site))
        sites = list(sites_res.scalars().all())

        payees_res = await db.execute(select(Payee))
        payees = list(payees_res.scalars().all())

        edges_res = await db.execute(select(Edge).options(selectinload(Edge.site), selectinload(Edge.payee)))
        edges = list(edges_res.scalars().all())

        return cls(db=db, sites=sites, payees=payees, edges=edges)

    def find_by_payee(self, payee: str) -> Optional[dict[str, Any]]:
        """Look up whether a payee VPA exists in the correlation graph."""
        if not payee:
            return None
        norm_val, _ = normalize_payee_identifier(payee)
        for p in self._payees:
            if p.value_normalized.lower() == norm_val:
                p_node = f"payee:{p.value_normalized}"
                cluster_root = self._uf.find(p_node)
                return {
                    "payee": p.value_normalized,
                    "payee_id": p.id,
                    "kind": p.kind,
                    "cluster_id": f"cluster-{cluster_root}",
                    "case_count": p.case_count,
                    "first_seen": p.first_seen.isoformat(),
                    "is_seed": p.is_seed,
                }
        return None

    def find_site(self, domain: str, within_days: int = 7) -> Optional[dict[str, Any]]:
        """Look up whether a domain was detonated recently with a confirmed payee."""
        if not domain:
            return None
        d_lower = domain.strip().lower()
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=within_days)

        for edge in self._edges:
            if edge.site and edge.site.domain.lower() == d_lower and edge.attribution == "confirmed":
                if edge.first_seen >= cutoff and edge.payee:
                    return {
                        "site": edge.site.domain,
                        "payee": edge.payee.value_normalized,
                        "case_id": str(edge.case_id or ""),
                        "observed_date": edge.first_seen.strftime("%Y-%m-%d"),
                        "attribution": "confirmed",
                        "confidence": edge.confidence,
                        "is_seed": edge.is_seed,
                    }
        return None

    def find_by_fingerprint(self, fp: Fingerprint) -> Optional[dict[str, Any]]:
        """Look up whether a fingerprint matches an active campaign cluster."""
        if not fp or not fp.text_simhash:
            return None

        for site in self._sites:
            site_fp_dict = site.fingerprint or {}
            site_fp = Fingerprint(
                text_simhash=site_fp_dict.get("text_simhash", 0),
                form_action_domains=site_fp_dict.get("form_action_domains", []),
                script_hosts=site_fp_dict.get("script_hosts", []),
                registrar=site_fp_dict.get("registrar"),
                nameservers=site_fp_dict.get("nameservers", []),
                creation_week=site_fp_dict.get("creation_week"),
                normalized_title_hash=site_fp_dict.get("normalized_title_hash", ""),
            )

            is_match, reasons = is_strong_fingerprint_match(fp, site_fp)
            if is_match:
                # Find confirmed payees associated with this matching site
                site_edges = [e for e in self._edges if e.site_id == site.id and e.attribution == "confirmed"]
                carried_payees = [e.payee.value_normalized for e in site_edges if e.payee]
                primary_payee = carried_payees[0] if carried_payees else None

                s_node = f"domain:{site.domain}"
                cluster_root = self._uf.find(s_node)

                return {
                    "cluster_id": f"cluster-{cluster_root}",
                    "matching_domain": site.domain,
                    "payee": primary_payee,
                    "confidence": 0.85,
                    "matching_signals": reasons,
                    "is_seed": site.is_seed,
                }
        return None


# ==============================================================================
# Graph Update Operations
# ==============================================================================


async def add_case_to_graph(case: Case, db: AsyncSession) -> dict[str, Any]:
    """Upserts site, payees, and edges from a case result.

    Attribution rules:
    - Real detonation or input payee: attribution='confirmed', confidence=1.0.
    - SKIP_KNOWN_CLUSTER: attribution='inferred', confidence=0.85, needs_verification=True.
    - If a previously inferred edge is subsequently confirmed, upgrades it in place.
    """
    domain = (case.domain or "").strip().lower()
    if not domain and case.normalized_url:
        from urllib.parse import urlparse
        domain = (urlparse(case.normalized_url).hostname or "").strip().lower()

    if not domain:
        domain = "unknown-domain.biz"

    # Extract triage fingerprint if present
    fingerprint_dict: dict[str, Any] = {}
    ev_stmt = (
        select(CaseEvent)
        .where(CaseEvent.case_id == case.id, CaseEvent.stage == "triage")
        .order_by(CaseEvent.id.desc())
    )
    ev_res = await db.execute(ev_stmt)
    for ev in ev_res.scalars().all():
        if ev.data and "fingerprint" in ev.data:
            fingerprint_dict = ev.data.get("fingerprint", {})
            break

    # 1. Upsert Site
    site_stmt = select(Site).where(Site.domain == domain)
    site_res = await db.execute(site_stmt)
    site = site_res.scalar_one_or_none()

    now = utc_now()
    if not site:
        site = Site(
            domain=domain,
            fingerprint=fingerprint_dict,
            first_seen=now,
            last_seen=now,
            is_seed=case.is_seed,
        )
        db.add(site)
        await db.flush()
    else:
        site.last_seen = now
        if fingerprint_dict:
            site.fingerprint = fingerprint_dict

    # 2. Collect Payees
    raw_payees: list[str] = []
    if case.enrichment_result and "normalized_payees" in case.enrichment_result:
        raw_payees.extend(case.enrichment_result["normalized_payees"])
    if case.detonation_result:
        det = case.detonation_result
        if det.get("payee_vpa"):
            raw_payees.append(det["payee_vpa"])
        if det.get("account_number"):
            raw_payees.append(f"bank:{det['account_number']}")
        if det.get("wallet_address"):
            raw_payees.append(f"wallet:{det['wallet_address']}")
    if case.extracted_upi_ids:
        raw_payees.extend(case.extracted_upi_ids)
    if case.input_payee:
        raw_payees.append(case.input_payee)

    unique_normalized: dict[str, str] = {}
    for p in raw_payees:
        norm_val, kind = normalize_payee_identifier(p)
        if norm_val:
            unique_normalized[norm_val] = kind

    # 3. Determine Edge Attribution & Confidence
    is_inferred = (case.outcome == "known_cluster_skipped") or ("#branch:skip_cluster" in (case.raw_input or ""))
    attribution = "inferred" if is_inferred else "confirmed"
    confidence = 0.85 if is_inferred else 1.0

    created_or_updated_edges: list[int] = []

    for norm_val, kind in unique_normalized.items():
        # Upsert Payee
        payee_stmt = select(Payee).where(Payee.value_normalized == norm_val)
        payee_res = await db.execute(payee_stmt)
        payee = payee_res.scalar_one_or_none()

        if not payee:
            payee = Payee(
                kind=kind,
                value_normalized=norm_val,
                case_count=1,
                first_seen=now,
                last_seen=now,
                is_seed=case.is_seed,
            )
            db.add(payee)
            await db.flush()
        else:
            payee.case_count += 1
            payee.last_seen = now

        # Upsert Edge
        edge_stmt = select(Edge).where(Edge.site_id == site.id, Edge.payee_id == payee.id)
        edge_res = await db.execute(edge_stmt)
        edge = edge_res.scalar_one_or_none()

        if not edge:
            edge = Edge(
                site_id=site.id,
                payee_id=payee.id,
                case_id=case.id,
                attribution=attribution,
                confidence=confidence,
                evidence={
                    "case_input": case.raw_input,
                    "attribution_rationale": "Direct observation" if attribution == "confirmed" else "Simhash and DOM infrastructure fingerprint match",
                },
                first_seen=now,
                is_seed=case.is_seed,
            )
            db.add(edge)
            await db.flush()
        else:
            # Upgrade inferred to confirmed if real detonation occurs
            if edge.attribution == "inferred" and attribution == "confirmed":
                logger.info("Upgrading inferred edge %s between site %s and payee %s to CONFIRMED", edge.id, site.domain, payee.value_normalized)
                edge.attribution = "confirmed"
                edge.confidence = 1.0
                edge.case_id = case.id

        created_or_updated_edges.append(edge.id)

    # 4. Compute cluster_id for the case summary
    uf = UnionFind()
    edges_all_res = await db.execute(select(Edge).options(selectinload(Edge.site), selectinload(Edge.payee)))
    edges_all = list(edges_all_res.scalars().all())
    for e in edges_all:
        s_node = f"domain:{e.site.domain}" if e.site else f"site:{e.site_id}"
        p_node = f"payee:{e.payee.value_normalized}" if e.payee else f"payee_id:{e.payee_id}"
        uf.union(s_node, p_node)

    site_node = f"domain:{site.domain}"
    cluster_root = uf.find(site_node)

    return {
        "site_id": site.id,
        "domain": site.domain,
        "payees_linked": list(unique_normalized.keys()),
        "attribution": attribution,
        "cluster_id": f"cluster-{cluster_root}",
        "edges_updated": created_or_updated_edges,
    }


# ==============================================================================
# Cytoscape Graph Serialization
# ==============================================================================


async def build_cytoscape_graph(
    db: AsyncSession,
    payee_filter: Optional[str] = None,
    limit: int = 500,
    include_seed: bool = True,
    min_cluster_size: int = 1,
) -> dict[str, Any]:
    """Generates Cytoscape-formatted graph payload conforming to api-schema.yaml."""
    # 1. Load edges with loaded relationships
    edge_query = select(Edge).options(selectinload(Edge.site), selectinload(Edge.payee))
    if not include_seed:
        edge_query = edge_query.where(Edge.is_seed == False)  # noqa: E712

    edges_res = await db.execute(edge_query)
    all_edges = list(edges_res.scalars().all())

    # 2. Compute Clusters via Union-Find
    uf = UnionFind()
    for edge in all_edges:
        if edge.site and edge.payee:
            s_node = f"domain:{edge.site.domain}"
            p_node = f"payee:{edge.payee.value_normalized}"
            uf.union(s_node, p_node)

    # If filtering by specific payee, determine target cluster root
    target_cluster: Optional[str] = None
    if payee_filter:
        norm_filter, _ = normalize_payee_identifier(payee_filter)
        target_cluster = uf.find(f"payee:{norm_filter}")

    # 3. Filter and cluster nodes
    cluster_members: dict[str, set[str]] = {}
    for edge in all_edges:
        if edge.site and edge.payee:
            s_node = f"domain:{edge.site.domain}"
            p_node = f"payee:{edge.payee.value_normalized}"
            root = uf.find(s_node)
            cluster_members.setdefault(root, set()).update([s_node, p_node])

    # Rank clusters by size descending
    sorted_clusters = sorted(
        cluster_members.items(), key=lambda kv: len(kv[1]), reverse=True
    )

    selected_nodes: set[str] = set()
    total_clusters = len(sorted_clusters)

    for root, members in sorted_clusters:
        if target_cluster and root != target_cluster:
            continue
        if len(members) < min_cluster_size:
            continue
        if len(selected_nodes) + len(members) > limit and len(selected_nodes) > 0:
            break
        selected_nodes.update(members)

    truncated = len(selected_nodes) < sum(len(m) for _, m in sorted_clusters)

    # 4. Build Cytoscape Nodes & Edges
    cy_nodes: list[dict[str, Any]] = []
    cy_edges: list[dict[str, Any]] = []

    # Sites nodes
    sites_query = select(Site)
    if not include_seed:
        sites_query = sites_query.where(Site.is_seed == False)  # noqa: E712
    sites_res = await db.execute(sites_query)
    all_sites = {s.domain: s for s in sites_res.scalars().all()}

    # Payees nodes
    payees_query = select(Payee)
    if not include_seed:
        payees_query = payees_query.where(Payee.is_seed == False)  # noqa: E712
    payees_res = await db.execute(payees_query)
    all_payees = {p.value_normalized: p for p in payees_res.scalars().all()}

    for node_key in selected_nodes:
        if node_key.startswith("domain:"):
            dom = node_key.split("domain:", 1)[1]
            site_obj = all_sites.get(dom)
            first_seen_str = site_obj.first_seen.isoformat() if site_obj else utc_now().isoformat()
            is_seed_val = site_obj.is_seed if site_obj else False
            cy_nodes.append(
                {
                    "data": {
                        "id": f"node-{dom}",
                        "label": dom,
                        "type": "domain",
                        "first_seen": first_seen_str,
                        "is_seed": is_seed_val,
                    }
                }
            )
        elif node_key.startswith("payee:"):
            pval = node_key.split("payee:", 1)[1]
            p_obj = all_payees.get(pval)
            first_seen_str = p_obj.first_seen.isoformat() if p_obj else utc_now().isoformat()
            case_cnt = p_obj.case_count if p_obj else 1
            is_seed_val = p_obj.is_seed if p_obj else False
            cy_nodes.append(
                {
                    "data": {
                        "id": f"node-{pval}",
                        "label": pval,
                        "type": "payee",
                        "case_count": case_cnt,
                        "first_seen": first_seen_str,
                        "is_seed": is_seed_val,
                    }
                }
            )

    # Edges between selected nodes
    for edge in all_edges:
        if edge.site and edge.payee:
            s_node = f"domain:{edge.site.domain}"
            p_node = f"payee:{edge.payee.value_normalized}"
            if s_node in selected_nodes and p_node in selected_nodes:
                cy_edges.append(
                    {
                        "data": {
                            "id": f"edge-{edge.id}",
                            "source": f"node-{edge.site.domain}",
                            "target": f"node-{edge.payee.value_normalized}",
                            "attribution": edge.attribution,
                            "confidence": edge.confidence,
                            "relationship": "directs_payment_to",
                            "is_seed": edge.is_seed,
                        }
                    }
                )

    return {
        "nodes": cy_nodes,
        "edges": cy_edges,
        "total_clusters": total_clusters,
        "total_cases_linked": len(cy_edges),
        "meta": {
            "truncated": truncated,
            "total_nodes": len(cy_nodes),
            "total_clusters": total_clusters,
        },
    }

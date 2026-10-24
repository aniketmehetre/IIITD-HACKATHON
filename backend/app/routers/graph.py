"""FastAPI Router for Campaign Correlation Graph Endpoints.

Provides Cytoscape-compatible intelligence visualization endpoints:
- GET /graph/overview: whole network overview, largest clusters first
- GET /graph/{payee_id}: local cluster graph for a specific payee destination
"""

from typing import Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.correlation import build_cytoscape_graph
from app.db import get_db_session

router = APIRouter(prefix="/graph", tags=["graph"])


# ==============================================================================
# 1. Global Campaign Network Overview (Registered BEFORE /{payee_id})
# ==============================================================================


@router.get("/overview")
async def get_graph_overview(
    limit: int = Query(500, ge=1, le=2000, description="Max nodes to return"),
    include_seed: bool = Query(True, description="Whether to include synthetic demo seed nodes"),
    min_cluster_size: int = Query(1, ge=1, description="Minimum nodes in cluster to display"),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieves the global scam campaign correlation graph in Cytoscape format."""
    return await build_cytoscape_graph(
        db=db,
        payee_filter=None,
        limit=limit,
        include_seed=include_seed,
        min_cluster_size=min_cluster_size,
    )


# ==============================================================================
# 2. Local Payee Cluster Graph
# ==============================================================================


@router.get("/{payee_id}")
async def get_payee_cluster(
    payee_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieves the connected component cluster for a specific payee identifier."""
    return await build_cytoscape_graph(
        db=db,
        payee_filter=payee_id,
        limit=200,
        include_seed=True,
        min_cluster_size=1,
    )

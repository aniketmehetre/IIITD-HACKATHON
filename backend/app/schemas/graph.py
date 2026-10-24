"""Pydantic schemas for Correlation Graph visualization conforming to shared/api-schema.json."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    type: Literal["payee", "case", "domain", "phone", "account", "ip"]
    risk_score: Optional[float] = None
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    weight: Optional[float] = 1.0


class GraphData(BaseModel):
    payee_id: str
    total_cases_linked: int = 1
    estimated_loss_inr: Optional[float] = 0.0
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)

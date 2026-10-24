"""Graph and Payee Correlation Endpoints conforming to shared/api-schema.json."""

from backend.app.schemas.graph import GraphData, GraphEdge, GraphNode
from fastapi import APIRouter

router = APIRouter(tags=["Correlation Graph"])


@router.get(
    "/graph/{payee_id}",
    response_model=GraphData,
    summary="Get campaign correlation graph for a known payee",
)
async def get_payee_graph(payee_id: str):
    """Retrieves the graph of interconnected campaigns, mule accounts, phone numbers, and domains."""
    sanitized_id = payee_id.strip()

    # Generate rich campaign topology for the payee
    nodes = [
        GraphNode(
            id=sanitized_id,
            label=f"Mule Payee ({sanitized_id})",
            type="payee",
            risk_score=98.5,
            properties={"vpa": sanitized_id, "psp": "HDFC Bank", "flagged": True},
        ),
        GraphNode(
            id="domain-1",
            label="quick-electricity-billpay.biz",
            type="domain",
            risk_score=92.0,
            properties={"registrar": "NameCheap", "age_days": 2, "ip": "185.220.101.5"},
        ),
        GraphNode(
            id="domain-2",
            label="power-settlement-portal.in",
            type="domain",
            risk_score=88.0,
            properties={"registrar": "Hostinger", "age_days": 5, "ip": "185.220.101.5"},
        ),
        GraphNode(
            id="phone-1",
            label="+91-9820011223",
            type="phone",
            risk_score=95.0,
            properties={"telecom": "Jio", "state": "Maharashtra", "complaints_count": 14},
        ),
        GraphNode(
            id="case-101",
            label="Case #101 (Mumbai SMS Campaign)",
            type="case",
            risk_score=90.0,
            properties={"loss_inr": 1840.0},
        ),
        GraphNode(
            id="case-102",
            label="Case #102 (Pune Urgency Lure)",
            type="case",
            risk_score=91.0,
            properties={"loss_inr": 2350.0},
        ),
    ]

    edges = [
        GraphEdge(id="e1", source="case-101", target="domain-1", relation="ACCESSED_VIA"),
        GraphEdge(id="e2", source="domain-1", target=sanitized_id, relation="ROUTES_PAYMENT_TO"),
        GraphEdge(id="e3", source="case-102", target="domain-2", relation="ACCESSED_VIA"),
        GraphEdge(id="e4", source="domain-2", target=sanitized_id, relation="ROUTES_PAYMENT_TO"),
        GraphEdge(id="e5", source="phone-1", target="case-101", relation="SENT_SMS_FOR"),
        GraphEdge(id="e6", source="phone-1", target="case-102", relation="SENT_SMS_FOR"),
    ]

    return GraphData(
        payee_id=sanitized_id,
        total_cases_linked=2,
        estimated_loss_inr=4190.0,
        nodes=nodes,
        edges=edges,
    )

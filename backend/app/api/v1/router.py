"""API Version 1 Router aggregation."""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import cases, graph, health, tinyfish_verify

api_v1_router = APIRouter()

# Mount endpoints
api_v1_router.include_router(health.router)
api_v1_router.include_router(cases.router)
api_v1_router.include_router(graph.router)
api_v1_router.include_router(tinyfish_verify.router)

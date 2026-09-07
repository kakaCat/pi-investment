"""
Prometheus metrics endpoint for FastAPI

提供 /metrics 端点用于 Prometheus 抓取监控指标
"""
from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry

router = APIRouter(tags=["Metrics"])


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint
    
    Returns:
        Prometheus-formatted metrics (text/plain)
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

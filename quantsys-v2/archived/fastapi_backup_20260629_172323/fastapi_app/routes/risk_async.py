"""
风险指标 API (FastAPI 异步版本)

风险管理和指标查询
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog

from application.services.core_async_services import RiskCheckAsyncService
from adapters.outbound.repositories.risk_async_repository import RiskAsyncRepository
from infrastructure.persistence.orm.async_config import get_async_session_context

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/risk",
    tags=["Risk - 风险管理"]
)


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class SignalCheckRequest(BaseModel):
    signal: Dict


@router.get("/metrics", response_model=ApiResponse, summary="获取风险指标")
async def get_risk_metrics(
    symbol: Optional[str] = Query(None, description="股票代码"),
    metric_name: Optional[str] = Query(None, description="指标名称"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(100, description="返回数量")
):
    """
    查询风险指标数据
    """
    try:
        async with get_async_session_context() as session:
            risk_repo = RiskAsyncRepository(session)

            metrics = await risk_repo.get_risk_metrics(
                symbol=symbol,
                metric_name=metric_name,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )

            return {
                "success": True,
                "data": {
                    "items": metrics,
                    "count": len(metrics)
                }
            }
    except Exception as e:
        logger.exception(f"Get risk metrics failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/metrics/{symbol}/latest", response_model=ApiResponse, summary="获取最新风险指标")
async def get_latest_metrics(
    symbol: str,
    metric_names: Optional[List[str]] = Query(None, description="指标名称列表")
):
    """
    获取股票的最新风险指标
    """
    try:
        async with get_async_session_context() as session:
            risk_repo = RiskAsyncRepository(session)
            metrics = await risk_repo.get_latest_metrics(symbol, metric_names)

            return {
                "success": True,
                "data": {
                    "symbol": symbol,
                    "metrics": metrics
                }
            }
    except Exception as e:
        logger.exception(f"Get latest metrics failed: {e}")
        return {"success": False, "error": str(e)}


@router.post("/check/signal", response_model=ApiResponse, summary="信号风控检查")
async def check_signal(request: SignalCheckRequest):
    """
    对单个信号进行风控检查
    """
    try:
        service = RiskCheckAsyncService()
        passed, reason = await service.check_signal(request.signal)

        return {
            "success": True,
            "data": {
                "passed": passed,
                "reason": reason
            }
        }
    except Exception as e:
        logger.exception(f"Check signal failed: {e}")
        return {"success": False, "error": str(e)}


@router.post("/check/batch", response_model=ApiResponse, summary="批量风控检查")
async def batch_check_signals(signals: List[Dict]):
    """
    批量风控检查
    """
    try:
        service = RiskCheckAsyncService()
        approved, rejected = await service.batch_check(signals)

        return {
            "success": True,
            "data": {
                "approved": approved,
                "rejected": rejected,
                "approvedCount": len(approved),
                "rejectedCount": len(rejected)
            }
        }
    except Exception as e:
        logger.exception(f"Batch check failed: {e}")
        return {"success": False, "error": str(e)}

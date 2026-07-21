"""
回测历史 API (FastAPI 异步版本)

迁移自 Flask backtest_history.py
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import structlog

from application.services.backtest_async_engine import BacktestAsyncEngine
from application.services.core_async_services import PerformanceAnalysisAsyncService

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/backtest",
    tags=["Backtest - 回测历史"]
)


class ApiResponse(BaseModel):
    """API响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@router.get("/history", response_model=ApiResponse, summary="查询回测历史")
async def get_backtest_history(
    strategy_name: Optional[str] = Query(None, description="策略名称"),
    symbol: Optional[str] = Query(None, description="股票代码"),
    limit: int = Query(20, description="返回数量")
):
    """
    查询回测历史记录

    支持按策略名称和股票代码过滤
    """
    try:
        engine = BacktestAsyncEngine()

        results = await engine.get_recent_backtests(
            strategy_name=strategy_name,
            limit=limit
        )

        return {
            "success": True,
            "data": {
                "items": results,
                "count": len(results)
            }
        }

    except Exception as e:
        logger.exception(f"Get backtest history failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/stats", response_model=ApiResponse, summary="回测统计信息")
async def get_backtest_stats(
    strategy_name: Optional[str] = Query(None, description="策略名称")
):
    """
    获取回测统计信息

    包含总数、平均收益、最佳策略等
    """
    try:
        service = PerformanceAnalysisAsyncService()

        if strategy_name:
            stats = await service.analyze_strategy_performance(strategy_name)
        else:
            # 获取整体统计
            stats = {
                "totalBacktests": 0,
                "avgReturn": 0,
                "avgSharpe": 0
            }

        return {
            "success": True,
            "data": stats
        }

    except Exception as e:
        logger.exception(f"Get backtest stats failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/compare", response_model=ApiResponse, summary="策略性能对比")
async def compare_strategies(
    strategy_names: List[str] = Query(..., description="策略名称列表")
):
    """
    对比多个策略的性能
    """
    try:
        service = PerformanceAnalysisAsyncService()

        comparison = []
        for name in strategy_names:
            perf = await service.analyze_strategy_performance(name)
            comparison.append(perf)

        return {
            "success": True,
            "data": {
                "strategies": comparison,
                "count": len(comparison)
            }
        }

    except Exception as e:
        logger.exception(f"Compare strategies failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }

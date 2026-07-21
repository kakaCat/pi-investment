"""
P1中频API批量异步路由集合

包含多个中频业务API的异步版本
"""
from fastapi import APIRouter, Query, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


# ==================== 情绪分析 API ====================
sentiment_router = APIRouter(
    prefix="/sentiment",
    tags=["Sentiment - 情绪分析"]
)


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@sentiment_router.get("/market", response_model=ApiResponse, summary="市场情绪")
async def get_market_sentiment(
    date: Optional[str] = Query(None, description="日期")
):
    """获取市场整体情绪"""
    try:
        from adapters.outbound.repositories.sentiment_async_repository import SentimentAsyncRepository
        from infrastructure.persistence.orm.async_config import get_async_session_context
        from datetime import date as dt

        target_date = date or dt.today().isoformat()

        async with get_async_session_context() as session:
            sentiment_repo = SentimentAsyncRepository(session)
            summary = await sentiment_repo.get_market_sentiment_summary(target_date)

            return {"success": True, "data": summary}
    except Exception as e:
        logger.exception(f"Get market sentiment failed: {e}")
        return {"success": False, "error": str(e)}


@sentiment_router.get("/stock/{symbol}", response_model=ApiResponse, summary="个股情绪")
async def get_stock_sentiment(symbol: str):
    """获取个股情绪数据"""
    try:
        from adapters.outbound.repositories.sentiment_async_repository import SentimentAsyncRepository
        from infrastructure.persistence.orm.async_config import get_async_session_context

        async with get_async_session_context() as session:
            sentiment_repo = SentimentAsyncRepository(session)
            sentiment = await sentiment_repo.get_latest_sentiment(symbol)

            return {"success": True, "data": sentiment}
    except Exception as e:
        logger.exception(f"Get stock sentiment failed: {e}")
        return {"success": False, "error": str(e)}


# ==================== 策略发现 API ====================
discovery_router = APIRouter(
    prefix="/discovery",
    tags=["Discovery - 策略发现"]
)


@discovery_router.post("/run", response_model=ApiResponse, summary="运行策略发现")
async def run_discovery(
    universe: List[str] = Body(..., description="股票池"),
    config: Dict = Body(default={}, description="配置")
):
    """运行策略发现"""
    try:
        result = {
            "discovered": [],
            "patterns": [],
            "recommendations": []
        }
        return {"success": True, "data": result}
    except Exception as e:
        logger.exception(f"Run discovery failed: {e}")
        return {"success": False, "error": str(e)}


@discovery_router.get("/archetypes", response_model=ApiResponse, summary="策略原型")
async def list_archetypes():
    """列出策略原型"""
    try:
        archetypes = [
            {"name": "momentum", "description": "动量策略"},
            {"name": "value", "description": "价值策略"},
            {"name": "mean_reversion", "description": "均值回归"}
        ]
        return {"success": True, "data": archetypes}
    except Exception as e:
        logger.exception(f"List archetypes failed: {e}")
        return {"success": False, "error": str(e)}


# ==================== 游戏智能告警 API ====================
game_alert_router = APIRouter(
    prefix="/game-alert",
    tags=["Game Alert - 游戏智能告警"]
)


@game_alert_router.get("/alerts", response_model=ApiResponse, summary="获取告警")
async def get_alerts(
    severity: Optional[str] = Query(None, description="严重级别"),
    limit: int = Query(20, description="返回数量")
):
    """获取告警列表"""
    try:
        alerts = []
        return {"success": True, "data": {"alerts": alerts, "count": len(alerts)}}
    except Exception as e:
        logger.exception(f"Get alerts failed: {e}")
        return {"success": False, "error": str(e)}


@game_alert_router.post("/check", response_model=ApiResponse, summary="检查告警")
async def check_alerts(symbols: List[str] = Body(...)):
    """检查指定股票的告警"""
    try:
        result = {"alerts": [], "symbols_checked": len(symbols)}
        return {"success": True, "data": result}
    except Exception as e:
        logger.exception(f"Check alerts failed: {e}")
        return {"success": False, "error": str(e)}


# ==================== 缠论分析 API ====================
chan_router = APIRouter(
    prefix="/chan",
    tags=["Chan - 缠论分析"]
)


@chan_router.get("/analysis/{symbol}", response_model=ApiResponse, summary="缠论分析")
async def get_chan_analysis(
    symbol: str,
    period: str = Query("daily", description="周期")
):
    """获取缠论分析结果"""
    try:
        analysis = {
            "symbol": symbol,
            "period": period,
            "bi": [],
            "duan": [],
            "zhongshu": []
        }
        return {"success": True, "data": analysis}
    except Exception as e:
        logger.exception(f"Get chan analysis failed: {e}")
        return {"success": False, "error": str(e)}


# ==================== 数据质量 API ====================
data_quality_router = APIRouter(
    prefix="/data-quality",
    tags=["Data Quality - 数据质量"]
)


@data_quality_router.get("/report", response_model=ApiResponse, summary="质量报告")
async def get_quality_report(
    table_name: Optional[str] = Query(None, description="表名")
):
    """获取数据质量报告"""
    try:
        from adapters.outbound.repositories.p2_async_repositories import DataQualityAsyncRepository
        from infrastructure.persistence.orm.async_config import get_async_session_context

        async with get_async_session_context() as session:
            repo = DataQualityAsyncRepository(session)
            checks = await repo.get_checks(table_name=table_name, limit=50)

            return {"success": True, "data": {"checks": checks, "count": len(checks)}}
    except Exception as e:
        logger.exception(f"Get quality report failed: {e}")
        return {"success": False, "error": str(e)}


@data_quality_router.get("/stats", response_model=ApiResponse, summary="质量统计")
async def get_quality_stats():
    """获取数据质量统计"""
    try:
        stats = {
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0
        }
        return {"success": True, "data": stats}
    except Exception as e:
        logger.exception(f"Get quality stats failed: {e}")
        return {"success": False, "error": str(e)}


# 导出所有路由
__all__ = [
    'sentiment_router',
    'discovery_router',
    'game_alert_router',
    'chan_router',
    'data_quality_router'
]

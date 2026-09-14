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


# ===========================================================================
# 市场 / 个股情绪（2026-09-14，w-2129d492，REQ-48d896）
#
# 改造前：两个端点走 `SentimentAsyncRepository` → `quant.sentiment_data`。
# 该表**没有任何迁移创建过**、唯一写入方 save_sentiment **零调用**，
# 所以端点恒返回 {"success":true,"data":{}} / data:null —— 典型假成功。
#
# 改造后：
#   · /market  只读**已在库的真实表** quant.market_sentiment_daily
#              （不新建取数链 —— 数据早就在，只是以前没人读它）；
#   · /stock/{symbol} 用 provider 框架的千股千评（机构参与度/综合得分等）。
#
# ⚠️ 契约变更：旧 data 是 {"bullish","bearish","neutral","total"}（按个股情绪分类计数），
#    那是绑定在幻觉表上的口径。新 data 是**真实市场级指标**
#    （up_count/down_count/ad_ratio/fear_greed_index/volume_ratio/...）；
#    个股端点返回的是**千股千评指标**，不是"情绪分类"。
#    仓内消费方为零，故按真实口径输出。旧键已在响应里标注 deprecated。
# ===========================================================================


@sentiment_router.get("/market", response_model=ApiResponse, summary="市场情绪")
async def get_market_sentiment(
    date: Optional[str] = Query(None, description="日期")
):
    """市场整体情绪 —— 读 quant.market_sentiment_daily（真实数据）。

    真实口径：涨跌家数 / 涨跌家数比 / 新高新低 / 量能比 / 总成交额 / 波动率 / 恐贪指数。
    """
    try:
        from datetime import date as dt, datetime as _dt, timedelta as _td
        from adapters.outbound.repositories.market_perception_repository import (
            MarketSentimentDailyRepository,
        )

        target = None
        if date:
            target = _dt.fromisoformat(str(date)).date()

        repo = MarketSentimentDailyRepository()
        row = repo.get_by_date(target) if target else None
        if row is None:
            recent = repo.get_recent(days=5) or []
            row = recent[0] if recent else None
        if row is None:
            return {
                "success": True,
                "data": {
                    "empty": True,
                    "degraded": False,
                    "source": "quant.market_sentiment_daily",
                    "note": "库中暂无市场情绪数据（非假成功：确实无记录）",
                },
            }

        return {
            "success": True,
            "data": {
                "tradeDate": row.trade_date.isoformat() if row.trade_date else None,
                "upCount": row.up_count,
                "downCount": row.down_count,
                "flatCount": row.flat_count,
                "adRatio": row.ad_ratio,
                "newHighCount": row.new_high_count,
                "newLowCount": row.new_low_count,
                "volumeRatio": row.volume_ratio,
                "totalTurnover": row.total_turnover,
                "volatility": row.volatility,
                "fearGreedIndex": row.fear_greed_index,
                "coverage": row.coverage,
                "partial": row.partial,
                # 旧契约键（绑定在幻觉表上）——保留但明确标注，避免调用方误读
                "bullish": None,
                "bearish": None,
                "neutral": None,
                "total": None,
                "deprecated": ["bullish", "bearish", "neutral", "total"],
                "source": "quant.market_sentiment_daily",
                "degraded": False,
                "empty": False,
            },
        }
    except Exception as e:
        logger.exception(f"Get market sentiment failed: {e}")
        return {"success": False, "error": str(e)}


@sentiment_router.get("/stock/{symbol}", response_model=ApiResponse, summary="个股情绪")
async def get_stock_sentiment(symbol: str):
    """个股情绪 —— 来源为东财**千股千评**（机构参与度/综合得分/换手率/市盈率/主力成本）。

    2026-09-14（REQ-48d896）：原实现读幻觉表 quant.sentiment_data，恒返回 null。
    现复用 provider 框架的 get_stock_comment；**不把千股千评冒充成"情绪分类"**。
    未覆盖的标的显式返回 empty:true（而非 null + success:true 的假成功）。
    """
    try:
        from adapters.outbound.datasources import get_data_provider_manager

        result = get_data_provider_manager().get_stock_comment(symbol)
        if not result.get('success'):
            return {
                "success": False,
                "error": result.get('error') or "个股情绪数据源不可用",
                "attempted_sources": list(result.get('attempted_sources') or []),
            }

        inner = getattr(result.get('data'), 'data', None) or {}
        comment = inner.get('comment')
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "comment": comment,
                "empty": bool(inner.get('empty')),
                "source": result.get('source'),
                "sourceNote": "东财千股千评（机构参与度/综合得分等指标），非情绪分类",
                "degraded": False,
            },
        }
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
    symbol: Optional[str] = Query(None, description="股票代码过滤"),
    period: Optional[str] = Query(None, description="周期过滤，如 daily"),
    limit: int = Query(50, description="返回条数")
):
    """获取数据质量报告（数据源：quant.data_quality_records，按 check_date 倒序）

    2026-09-10 修复：原查询参数 table_name 对应的列在线上表（data_quality_records）中并不存在，
    ORM 又指向不存在的 data_quality_checks，异常被基类吞掉后恒返回空列表；
    现按真实列（symbol/period）过滤，取数失败不再静默返回空。
    """
    try:
        from adapters.outbound.repositories.p2_async_repositories import DataQualityAsyncRepository
        from infrastructure.persistence.orm.async_config import get_async_session_context

        async with get_async_session_context() as session:
            repo = DataQualityAsyncRepository(session)
            checks = await repo.get_checks(symbol=symbol, period=period, limit=limit)

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

"""M1 市场感知 API 路由（RFC 007）

7 个端点：
- POST /snapshot: 每日快照（调度任务调）
- POST /backfill-regime: 回填历史 regime
- POST /detect-themes: 手动触发主线检测（回放验收用）
- GET /regime: regime 时间序列查询
- GET /sentiment-history: 情绪时间序列查询
- GET /themes: 主线查询
- PUT /themes/{id}: LLM 回写 catalyst（盘后例程用）

规范：查询一律走 Repository（MarketRegimeRepository 等），路由层禁止裸 SQL。
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/market/perception", tags=["M1 Market Perception"])


def _get_service():
    from application.services.market_perception_service import MarketPerceptionService
    return MarketPerceptionService()


def _repos():
    from adapters.outbound.repositories import (
        MarketRegimeRepository, MarketSentimentDailyRepository,
        MarketThemeRepository,
    )
    return (MarketRegimeRepository(), MarketSentimentDailyRepository(),
            MarketThemeRepository())


# ------------------------------------------------------------------
# Request 模型
# ------------------------------------------------------------------
class BackfillRegimeRequest(BaseModel):
    days: int = Field(default=120, ge=1, le=365, description="回填天数")


class DetectThemesRequest(BaseModel):
    date: str = Field(..., description="交易日，格式 YYYY-MM-DD")
    top_n: int = Field(default=3, ge=1, le=10, description="Top N 主线")


class UpdateThemeCatalystRequest(BaseModel):
    theme: Optional[str] = Field(None, description="主题名（LLM 优化后）")
    catalyst: Optional[str] = Field(None, description="催化剂描述")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="置信度 [0,1]")


# ------------------------------------------------------------------
# 写端点（触发计算+落库）
# ------------------------------------------------------------------
@router.post("/snapshot")
async def daily_snapshot(trade_date: Optional[str] = Body(None, embed=True)):
    """每日快照：情绪 → regime → 主线，逐步容错。

    返回 all_steps_success / partial_success / failed_steps 明确部分失败语义。
    调度任务每日 15:30 调用（或手动回放验收）。
    """
    return _get_service().run_daily_snapshot(trade_date)


@router.post("/backfill-regime")
async def backfill_regime(req: BackfillRegimeRequest):
    """回填近 N 日 regime（历史 breadth 聚合 + 指数趋势，批量 upsert）。

    情绪分用映射近似，reason 字段标注 [回填近似]。
    """
    result = _get_service().backfill_regime(req.days)
    if not result.get('success'):
        raise HTTPException(status_code=500, detail=result.get('error', 'Backfill failed'))
    return result


@router.post("/detect-themes")
async def detect_themes(req: DetectThemesRequest):
    """手动触发主线检测（回放验收用）。

    正常流程由 snapshot 自动调用，此端点供独立验证。
    """
    result = _get_service().detect_and_store_themes(req.date, req.top_n)
    if not result.get('stored'):
        raise HTTPException(status_code=500,
                            detail=result.get('error', 'Theme detection failed'))
    return result


# ------------------------------------------------------------------
# 读端点（Repository 查询）
# ------------------------------------------------------------------
@router.get("/regime")
async def query_regime(days: int = 20):
    """查询 regime 时间序列（最近 N 天，倒序）。

    返回：regime + reason + 指标原始值。
    """
    regime_repo, _, _ = _repos()
    rows = regime_repo.get_recent(days)
    return {
        "success": True,
        "count": len(rows),
        "data": [r.to_dict() for r in rows],
    }


@router.get("/sentiment-history")
async def sentiment_history(days: int = 20):
    """查询情绪时间序列（最近 N 天，倒序）。

    返回：涨跌家数/新高新低/量能/波动率/恐慌贪婪指数 + coverage 自查。
    """
    _, sentiment_repo, _ = _repos()
    rows = sentiment_repo.get_recent(days)
    return {
        "success": True,
        "count": len(rows),
        "data": [r.to_dict() for r in rows],
    }


@router.get("/themes")
async def query_themes(date: Optional[str] = None):
    """查询指定日期的主线（不传 date 返回最新交易日）。

    返回：rank 1/2/3 + sector/limit_up_count/stocks/fund_flow/catalyst/confidence。
    """
    _, _, theme_repo = _repos()
    rows = theme_repo.get_by_date(date) if date else theme_repo.get_latest()
    if not rows:
        return {"success": False,
                "error": f"{'指定日期' if date else '最新'}无主线记录"}
    return {
        "success": True,
        "trade_date": rows[0].trade_date.isoformat() if rows[0].trade_date else None,
        "themes": [r.to_dict() for r in rows],
    }


@router.put("/themes/{theme_id}")
async def update_theme_catalyst(theme_id: int, req: UpdateThemeCatalystRequest):
    """LLM 回写 catalyst（盘后例程调用）。

    只允许更新 theme/catalyst/confidence 三字段（落库时生成的 sector/stocks 不可改）。
    """
    _, _, theme_repo = _repos()
    obj = theme_repo.update_catalyst(
        theme_id, theme=req.theme, catalyst=req.catalyst, confidence=req.confidence)
    if obj is None:
        raise HTTPException(
            status_code=404,
            detail=f"Theme ID {theme_id} 不存在或无可更新字段")
    return {"success": True, "updated": obj.to_dict()}


# ------------------------------------------------------------------
# M7-2 散户恐慌代理指标（Retail Panic Index）
# ------------------------------------------------------------------
@router.get("/panic-index")
async def retail_panic_index(trade_date: Optional[str] = None):
    """散户恐慌代理指标（连续 0-100，替代离散三档）。

    合成维度：散户资金流(30%) + 涨跌家数比(25%) + 恐慌贪婪指数(20%)
              + 量能(15%) + 波动率(10%)；缺失维度按剩余权重归一。
    等级：≥70 panic / 50-70 leaning_panic / 30-50 leaning_greed / <30 greed
    trade_date 缺省取最近一日。
    """
    from application.services.retail_panic_index_service import RetailPanicIndexService
    svc = RetailPanicIndexService()
    result = svc.compute_index(trade_date)
    return {"success": True, **result}


@router.get("/panic-index/series")
async def retail_panic_index_series(days: int = 20):
    """最近 N 日散户恐慌指数序列（观察恐慌-贪婪周期）。"""
    from application.services.retail_panic_index_service import RetailPanicIndexService
    svc = RetailPanicIndexService()
    series = svc.series(min(days, 60))
    return {"success": True, "series": series}

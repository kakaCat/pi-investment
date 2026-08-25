"""M1 市场感知 API 路由（RFC 007）

7 个端点：
- POST /snapshot: 每日快照（调度任务调）
- POST /backfill-regime: 回填历史 regime
- POST /detect-themes: 手动触发主线检测（回放验收用）
- GET /regime: regime 时间序列查询
- GET /sentiment-history: 情绪时间序列查询
- GET /themes: 主线查询
- PUT /themes/{id}: LLM 回写 catalyst（盘后例程用）
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from sqlalchemy import text

import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/market/perception", tags=["M1 Market Perception"])


def _get_session():
    from infrastructure.persistence.orm import get_session
    return get_session()


def _get_service():
    from application.services.market_perception_service import MarketPerceptionService
    return MarketPerceptionService()


# ------------------------------------------------------------------
# Request/Response 模型
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
# 端点实现
# ------------------------------------------------------------------
@router.post("/snapshot")
async def daily_snapshot(trade_date: Optional[str] = Body(None, embed=True)):
    """每日快照：情绪 → regime → 主线，逐步容错。

    调度任务每日 15:30 调用（或手动回放验收）。
    """
    svc = _get_service()
    result = svc.run_daily_snapshot(trade_date)
    return {
        "success": result.get('success', False),
        "trade_date": result.get('trade_date'),
        "steps": result.get('steps', {}),
    }


@router.post("/backfill-regime")
async def backfill_regime(req: BackfillRegimeRequest):
    """回填近 N 日 regime（纯 SQL 聚合历史）。

    情绪分用映射近似，reason 字段标注 [回填近似]。
    """
    svc = _get_service()
    result = svc.backfill_regime(req.days)
    if not result.get('success'):
        raise HTTPException(status_code=500, detail=result.get('error', 'Backfill failed'))
    return result


@router.post("/detect-themes")
async def detect_themes(req: DetectThemesRequest):
    """手动触发主线检测（回放验收用）。

    正常流程由 snapshot 自动调用，此端点供独立验证。
    """
    svc = _get_service()
    date_arg = req.date.replace('-', '')
    result = svc.detect_and_store_themes(req.date, req.top_n)
    if not result.get('stored'):
        raise HTTPException(status_code=500, detail=result.get('error', 'Theme detection failed'))
    return result


@router.get("/regime")
async def query_regime(days: int = 20):
    """查询 regime 时间序列（最近 N 天）。

    返回：regime + reason + 指标原始值。
    """
    session = _get_session()
    rows = session.execute(text("""
        SELECT trade_date, regime, index_trend_score, sentiment_score,
               volume_ratio, ad_ratio, reason
        FROM quant.market_regime
        ORDER BY trade_date DESC LIMIT :n
    """), {'n': days}).fetchall()

    return {
        "success": True,
        "count": len(rows),
        "data": [
            {
                "trade_date": str(r[0]),
                "regime": r[1],
                "index_trend_score": float(r[2]) if r[2] else None,
                "sentiment_score": float(r[3]) if r[3] else None,
                "volume_ratio": float(r[4]) if r[4] else None,
                "ad_ratio": float(r[5]) if r[5] else None,
                "reason": r[6],
            }
            for r in rows
        ],
    }


@router.get("/sentiment-history")
async def sentiment_history(days: int = 20):
    """查询情绪时间序列（最近 N 天）。

    返回：涨跌家数/新高新低/量能/波动率/恐慌贪婪指数 + coverage 自查。
    """
    session = _get_session()
    rows = session.execute(text("""
        SELECT trade_date, up_count, down_count, flat_count, ad_ratio,
               new_high_count, new_low_count, volume_ratio, total_turnover,
               volatility, fear_greed_index, coverage, partial
        FROM quant.market_sentiment_daily
        ORDER BY trade_date DESC LIMIT :n
    """), {'n': days}).fetchall()

    return {
        "success": True,
        "count": len(rows),
        "data": [
            {
                "trade_date": str(r[0]),
                "up_count": r[1], "down_count": r[2], "flat_count": r[3],
                "ad_ratio": float(r[4]) if r[4] else None,
                "new_high_count": r[5], "new_low_count": r[6],
                "volume_ratio": float(r[7]) if r[7] else None,
                "total_turnover": float(r[8]) if r[8] else None,
                "volatility": float(r[9]) if r[9] else None,
                "fear_greed_index": float(r[10]) if r[10] else None,
                "coverage": r[11],
                "partial": r[12],
            }
            for r in rows
        ],
    }


@router.get("/themes")
async def query_themes(date: Optional[str] = None):
    """查询指定日期的主线（不传 date 返回最新）。

    返回：rank 1/2/3 + sector/limit_up_count/stocks/fund_flow/catalyst/confidence。
    """
    session = _get_session()
    if date:
        cond = "WHERE trade_date = :d"
        params = {'d': date}
    else:
        cond = "WHERE trade_date = (SELECT MAX(trade_date) FROM quant.market_theme)"
        params = {}

    rows = session.execute(text(f"""
        SELECT id, trade_date, rank, theme, sector, limit_up_count,
               stocks, fund_flow, catalyst, confidence
        FROM quant.market_theme {cond} ORDER BY rank
    """), params).fetchall()

    if not rows:
        return {"success": False, "error": f"{'指定日期' if date else '最新'}无主线记录"}

    import json
    return {
        "success": True,
        "trade_date": str(rows[0][1]) if rows else None,
        "themes": [
            {
                "id": r[0], "trade_date": str(r[1]), "rank": r[2],
                "theme": r[3], "sector": r[4], "limit_up_count": r[5],
                "stocks": json.loads(r[6]) if r[6] else [],
                "fund_flow": float(r[7]) if r[7] else None,
                "catalyst": r[8], "confidence": float(r[9]) if r[9] else None,
            }
            for r in rows
        ],
    }


@router.put("/themes/{theme_id}")
async def update_theme_catalyst(theme_id: int, req: UpdateThemeCatalystRequest):
    """LLM 回写 catalyst（盘后例程调用）。

    只允许更新 theme/catalyst/confidence 三字段（落库时生成的 sector/stocks 不可改）。
    """
    if not any([req.theme, req.catalyst, req.confidence is not None]):
        raise HTTPException(status_code=400, detail="至少提供一个更新字段")

    session = _get_session()
    updates = []
    params = {'id': theme_id}
    if req.theme:
        updates.append("theme = :theme")
        params['theme'] = req.theme
    if req.catalyst:
        updates.append("catalyst = :catalyst")
        params['catalyst'] = req.catalyst
    if req.confidence is not None:
        updates.append("confidence = :confidence")
        params['confidence'] = req.confidence

    try:
        cur = session.execute(text(f"""
            UPDATE quant.market_theme
            SET {', '.join(updates)}
            WHERE id = :id
            RETURNING id, trade_date, rank, theme, catalyst, confidence
        """), params)
        row = cur.fetchone()
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"回写 catalyst 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if not row:
        raise HTTPException(status_code=404, detail=f"Theme ID {theme_id} 不存在")

    return {
        "success": True,
        "updated": {
            "id": row[0], "trade_date": str(row[1]), "rank": row[2],
            "theme": row[3], "catalyst": row[4], "confidence": float(row[5]) if row[5] else None,
        },
    }

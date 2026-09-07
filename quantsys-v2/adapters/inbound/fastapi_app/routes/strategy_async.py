"""策略执行 API - FastAPI 版（从 Flask strategy.py 迁移，响应契约保持一致）

POST /api/strategy/run  — 执行完整流水线
GET  /api/strategy/status — 获取当前策略状态
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body
import structlog

from adapters.inbound.fastapi_app.shared import error_response

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Strategy - 策略执行"])

# 与 Flask 一致的模块级 engine 单例
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from application.services.strategy_engine.engine import StrategyEngine
        _engine = StrategyEngine()
    return _engine


@router.post('/api/strategy/run')
def run_strategy(payload: Optional[Dict[str, Any]] = Body(None)):
    """执行策略流水线。"""
    try:
        data = payload or {}
        market = data.get("market", "A")
        total_capital = float(data.get("total_capital", 100000))

        if market not in ("A", "HK"):
            return error_response({"success": False, "error": "market must be 'A' or 'HK'"}, 400)

        engine = _get_engine()

        result = engine.run(
            market=market,
            sector_data=data.get("sector_data"),
            stock_data=data.get("stock_data"),
            ml_predictions=data.get("ml_predictions"),
        )

        if total_capital != 100000 and result.candidates:
            all_symbols = [s for stocks in result.candidates.values() for s in stocks]
            final_by_sector = engine._group_by_sector(all_symbols, result.candidates)
            result.allocation = engine._build_portfolio(final_by_sector, total_capital)

        return {
            "success": True,
            "data": {
                "market": result.market,
                "sectors": result.sectors,
                "sector_scores": result.sector_scores,
                "candidates": result.candidates,
                "final_portfolio": result.final_portfolio,
                "allocation": result.allocation,
                "ml_pass_rate": result.ml_pass_rate,
                "warnings": result.warnings,
            }
        }

    except Exception as e:
        logger.error(f"策略执行失败: {e}", exc_info=True)
        return error_response({"success": False, "error": str(e)}, 500)


@router.get('/api/strategy/status')
def get_strategy_status():
    """获取策略状态"""
    engine = _get_engine()

    return {
        "success": True,
        "data": {
            "a_consecutive_counts": engine.a_rotation.consecutive_top_count,
            "hk_consecutive_counts": engine.hk_rotation.consecutive_top_count,
        }
    }

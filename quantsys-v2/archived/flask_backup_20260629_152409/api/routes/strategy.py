"""
策略执行 API

POST /api/strategy/run  — 执行完整流水线
GET  /api/strategy/status — 获取当前策略状态
"""
import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

strategy_bp = Blueprint('strategy', __name__)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from application.services.strategy_engine.engine import StrategyEngine
        _engine = StrategyEngine()
    return _engine


@strategy_bp.route('/api/strategy/run', methods=['POST'])
def run_strategy():
    """
    执行策略流水线。

    Request body:
    {
        "market": "A",           // "A" 或 "HK"
        "sector_data": {         // 行业数据（可选）
            "momentum": {...},
            "flow": {...},
            "strength": {...}
        },
        "stock_data": [...],     // 股票因子数据（DataFrame JSON，可选）
        "ml_predictions": {...}, // ML预测结果（可选）
        "total_capital": 100000  // 总资金
    }
    """
    try:
        data = request.get_json() or {}
        market = data.get("market", "A")
        total_capital = float(data.get("total_capital", 100000))

        if market not in ("A", "HK"):
            return jsonify({"success": False, "error": "market must be 'A' or 'HK'"}), 400

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

        return jsonify({
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
        })

    except Exception as e:
        logger.error(f"策略执行失败: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@strategy_bp.route('/api/strategy/status', methods=['GET'])
def get_strategy_status():
    """获取策略状态"""
    engine = _get_engine()

    return jsonify({
        "success": True,
        "data": {
            "a_consecutive_counts": engine.a_rotation.consecutive_top_count,
            "hk_consecutive_counts": engine.hk_rotation.consecutive_top_count,
        }
    })

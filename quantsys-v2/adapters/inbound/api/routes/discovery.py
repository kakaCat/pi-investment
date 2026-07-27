"""
策略发现引擎 API Routes

POST /api/discovery/run        — 运行策略发现
GET  /api/discovery/archetypes — 列出所有策略原型
GET  /api/discovery/result/:id  — 查询历史发现结果（暂存内存）
"""
import logging
from flask import Blueprint, jsonify, request

from application.services.strategy_discovery_service import StrategyDiscoveryService

logger = logging.getLogger(__name__)

discovery_bp = Blueprint('discovery', __name__)

# 简易内存存储（重启丢失）— 已解耦到中立层，向后兼容再导出
from adapters.shared.discovery_state import _results_store


def _get_service() -> StrategyDiscoveryService:
    return StrategyDiscoveryService()


@discovery_bp.route('/api/discovery/run', methods=['POST'])
def run_discovery():
    """
    运行策略发现流水线。

    入参：
    {
        "symbols": ["600900", "600025", "600011"],
        "start_date": "2023-01-01",     // 可选，默认 2023-01-01
        "end_date": "2025-12-31",       // 可选，默认 2025-12-31
        "metric": "sharpe",             // 可选：sharpe / return / win_rate
        "max_combinations": 30,         // 可选，每个原型最大参数组合数
        "archetype_filter": ["RSI均值回归"]  // 可选，只测特定原型
    }

    返回：
    {
        "success": true,
        "data": {
            "run_id": "20260528_...",
            "archetype_summary": [...],
            "overall_top10": [...],
            "all_results": [...],
            "errors": [...]
        }
    }
    """
    data = request.get_json(silent=True) or {}

    symbols = data.get('symbols', [])
    if not symbols:
        return jsonify({'success': False, 'error': '缺少参数: symbols (股票代码列表)'}), 400

    start_date = data.get('start_date', '2023-01-01')
    end_date = data.get('end_date', '2025-12-31')
    metric = data.get('metric', 'sharpe')
    max_combinations = int(data.get('max_combinations', 30))
    archetype_filter = data.get('archetype_filter', None)

    logger.info(
        f"策略发现请求: symbols={len(symbols)}, metric={metric}, "
        f"date={start_date}~{end_date}"
    )

    try:
        service = _get_service()
        report = service.run(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            metric=metric,
            max_combinations=max_combinations,
            archery_filter=archetype_filter,
        )

        # 存储结果
        _results_store[report.run_id] = report

        return jsonify({
            'success': True,
            'data': report.to_dict(),
        })

    except Exception as e:
        logger.error(f"策略发现失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@discovery_bp.route('/api/discovery/archetypes', methods=['GET'])
def list_archetypes():
    """列出所有可用的策略原型模板"""
    try:
        service = _get_service()
        archetypes = service.list_archetypes()
        return jsonify({
            'success': True,
            'data': {
                'archetypes': archetypes,
                'total': len(archetypes),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@discovery_bp.route('/api/discovery/result/<run_id>', methods=['GET'])
def get_discovery_result(run_id: str):
    """获取历史发现结果"""
    report = _results_store.get(run_id)
    if not report:
        return jsonify({'success': False, 'error': f'未找到结果: {run_id}'}), 404

    return jsonify({
        'success': True,
        'data': report.to_dict(),
    })

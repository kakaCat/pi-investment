"""
股票池扫描 API 路由

新增功能：
1. POST /api/pools/{pool_id}/scan - 扫描指定股票池
2. POST /api/pools/scan-all - 扫描所有股票池
3. GET /api/pools/scan-results - 获取扫描历史
4. POST /api/pools/scan/schedule - 启动/停止定时扫描
"""
import logging
from flask import Blueprint, jsonify, request
from adapters.inbound.api.shared import handle_api_error, api_response

logger = logging.getLogger(__name__)

pool_scan_bp = Blueprint('pool_scan', __name__)


@pool_scan_bp.route('/api/pools/<int:pool_id>/scan', methods=['POST'])
@handle_api_error
def scan_pool(pool_id):
    """
    扫描指定股票池

    请求体:
    {
      "strategy_ids": [272, 273],  // 可选，默认[272, 273]
      "min_score": 70              // 可选，默认70
    }

    返回:
    {
      "success": true,
      "data": {
        "pool_id": 1,
        "pool_name": "新能源高波动",
        "scan_time": "2026-06-04T16:05:00",
        "symbols_scanned": 12,
        "signals_found": 3,
        "signals": [...]
      }
    }
    """
    from application.services.pool_scanner_service import pool_scanner_service

    data = request.get_json() or {}
    strategy_ids = data.get('strategy_ids')
    min_score = data.get('min_score', 70)

    result = pool_scanner_service.scan_pool(
        pool_id=pool_id,
        strategy_ids=strategy_ids,
        min_score=min_score
    )

    if not result['success']:
        return jsonify(result), 404

    return api_response(result)


@pool_scan_bp.route('/api/pools/scan-all', methods=['POST'])
@handle_api_error
def scan_all_pools():
    """
    扫描所有股票池

    请求体:
    {
      "strategy_ids": [272, 273],  // 可选
      "min_score": 70              // 可选
    }

    返回:
    {
      "success": true,
      "data": {
        "scan_time": "2026-06-04T16:05:00",
        "pools_scanned": 3,
        "total_signals": 8,
        "results": [...]
      }
    }
    """
    from application.services.pool_scanner_service import pool_scanner_service

    data = request.get_json() or {}
    strategy_ids = data.get('strategy_ids')
    min_score = data.get('min_score', 70)

    result = pool_scanner_service.scan_all_pools(
        strategy_ids=strategy_ids,
        min_score=min_score
    )

    return api_response(result)


@pool_scan_bp.route('/api/pools/scan/schedule', methods=['POST'])
@handle_api_error
def manage_scan_schedule():
    """
    启动/停止定时扫描

    请求体:
    {
      "action": "start" | "stop" | "trigger"
    }

    - start: 启动定时任务（每天16:05执行）
    - stop: 停止定时任务
    - trigger: 立即执行一次扫描

    返回:
    {
      "success": true,
      "message": "定时任务已启动"
    }
    """
    from application.services.pool_scan_scheduler import pool_scan_scheduler

    data = request.get_json() or {}
    action = data.get('action', 'start')

    if action == 'start':
        pool_scan_scheduler.start()
        return api_response({
            'status': 'running',
            'message': '股票池扫描定时任务已启动（每天16:05执行）'
        })

    elif action == 'stop':
        pool_scan_scheduler.stop()
        return api_response({
            'status': 'stopped',
            'message': '股票池扫描定时任务已停止'
        })

    elif action == 'trigger':
        pool_scan_scheduler.trigger_scan_now()
        return api_response({
            'status': 'triggered',
            'message': '已触发立即扫描'
        })

    else:
        return jsonify({
            'success': False,
            'error': f'无效的操作: {action}，支持: start/stop/trigger'
        }), 400


@pool_scan_bp.route('/api/pools/scan-results', methods=['GET'])
@handle_api_error
def get_scan_results():
    """
    获取扫描历史记录

    Query参数:
    - pool_id: 股票池ID（可选）
    - limit: 返回数量（默认20）

    返回:
    {
      "success": true,
      "data": {
        "results": [...],
        "count": 10
      }
    }
    """
    # TODO: 从数据库获取扫描历史
    # pool_id = request.args.get('pool_id', type=int)
    # limit = request.args.get('limit', 20, type=int)

    return api_response({
        'results': [],
        'count': 0,
        'message': '扫描历史功能开发中'
    })

"""
股票池扫描开关管理 API

新增功能：
1. PUT /api/pools/{pool_id}/scan-switch - 开启/关闭股票池扫描
2. GET /api/pools/scan-status - 查看所有股票池的扫描状态
"""
import logging
from flask import Blueprint, jsonify, request
from adapters.inbound.api.shared import handle_api_error, api_response

logger = logging.getLogger(__name__)

pool_scan_switch_bp = Blueprint('pool_scan_switch', __name__)


@pool_scan_switch_bp.route('/api/pools/<int:pool_id>/scan-switch', methods=['PUT'])
@handle_api_error
def toggle_pool_scan(pool_id):
    """
    开启/关闭股票池扫描

    请求体:
    {
      "enabled": true  // true=开启扫描, false=关闭扫描
    }

    返回:
    {
      "success": true,
      "data": {
        "pool_id": 1,
        "pool_name": "新能源高波动",
        "scan_enabled": true,
        "message": "股票池扫描已开启"
      }
    }
    """
    from adapters.outbound.repositories import StockPoolORMRepository

    data = request.get_json()
    if data is None:
        return jsonify({
            'success': False,
            'error': '请求体不能为空'
        }), 400

    enabled = data.get('enabled')
    if enabled is None:
        return jsonify({
            'success': False,
            'error': 'enabled 参数必需（true 或 false）'
        }), 400

    pool_repo = StockPoolORMRepository()

    # 获取股票池
    pool = pool_repo.get_pool_by_id(pool_id)
    if not pool:
        return jsonify({
            'success': False,
            'error': f'股票池 {pool_id} 不存在'
        }), 404

    # 更新扫描开关
    success = pool_repo.update_scan_enabled(pool_id, enabled)

    if not success:
        return jsonify({
            'success': False,
            'error': '更新失败'
        }), 500

    return api_response({
        'pool_id': pool_id,
        'pool_name': pool.get('name'),
        'scan_enabled': enabled,
        'message': f"股票池扫描已{'开启' if enabled else '关闭'}"
    })


@pool_scan_switch_bp.route('/api/pools/scan-status', methods=['GET'])
@handle_api_error
def get_scan_status():
    """
    查看所有股票池的扫描状态

    返回:
    {
      "success": true,
      "data": {
        "pools": [
          {
            "pool_id": 1,
            "pool_name": "新能源高波动",
            "pool_type": "custom",
            "scan_enabled": true,
            "symbols_count": 12
          }
        ],
        "summary": {
          "total": 3,
          "enabled": 2,
          "disabled": 1
        }
      }
    }
    """
    from adapters.outbound.repositories import StockPoolORMRepository

    pool_repo = StockPoolORMRepository()
    pools = pool_repo.get_all_pools()

    pools_status = []
    enabled_count = 0
    disabled_count = 0

    for pool in pools:
        scan_enabled = pool.get('scan_enabled', True)

        if scan_enabled:
            enabled_count += 1
        else:
            disabled_count += 1

        pools_status.append({
            'pool_id': pool['id'],
            'pool_name': pool.get('name'),
            'pool_type': pool.get('pool_type'),
            'scan_enabled': scan_enabled,
            'symbols_count': len(pool.get('symbols', []))
        })

    return api_response({
        'pools': pools_status,
        'summary': {
            'total': len(pools),
            'enabled': enabled_count,
            'disabled': disabled_count
        }
    })

"""
统一策略交易 API 路由

提供配置驱动的策略 API，支持所有策略版本（V13/V14/V15...）
避免重复代码，统一接口

API 端点：
    GET  /api/strategy/<strategy_name>/account-info  - 账户信息
    GET  /api/strategy/<strategy_name>/positions     - 持仓明细
    POST /api/strategy/<strategy_name>/rebalance     - 手动调仓
    POST /api/strategy/<strategy_name>/daily-check   - 每日检查
    GET  /api/strategy/list                          - 列出所有策略

使用示例：
    # V13
    curl http://localhost:5001/api/strategy/v13/account-info
    curl -X POST http://localhost:5001/api/strategy/v13/rebalance

    # V14
    curl http://localhost:5001/api/strategy/v14/account-info
    curl -X POST http://localhost:5001/api/strategy/v14/rebalance

    # 未来 V15（无需修改代码）
    curl http://localhost:5001/api/strategy/v15/account-info
"""
from flask import Blueprint, jsonify, request
import logging

from application.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)

# 创建统一策略蓝图（使用唯一名称避免冲突）
strategy_bp = Blueprint('strategy_trading_unified', __name__, url_prefix='/api/strategy')


@strategy_bp.route('/list', methods=['GET'])
def list_strategies():
    """
    列出所有可用策略

    Returns:
        {
            "success": true,
            "data": {
                "strategies": ["v13", "v14"],
                "count": 2
            }
        }
    """
    try:
        service = StrategyService()
        strategies = service.list_strategies()

        return jsonify({
            'success': True,
            'data': {
                'strategies': strategies,
                'count': len(strategies)
            }
        }), 200

    except Exception as e:
        logger.error(f"列出策略失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/<strategy_name>/account-info', methods=['GET'])
def get_account_info(strategy_name: str):
    """
    获取策略账户信息（统一接口）

    Args:
        strategy_name: 策略名称（v13/v14/v15...）

    Returns:
        {
            "success": true,
            "data": {
                "strategy_name": "v13",
                "account_name": "default",
                "total_value": 120000,
                "cash": 30000,
                "position_value": 90000,
                "positions_count": 5,
                "cumulative_return": 0.20,
                "last_rebalance_date": "2026-06-29",
                "config": {...}
            }
        }

    Examples:
        GET /api/strategy/v13/account-info
        GET /api/strategy/v14/account-info
    """
    try:
        service = StrategyService()
        account = service.get_account_info(strategy_name)

        return jsonify({
            'success': True,
            'data': account
        }), 200

    except ValueError as e:
        logger.warning(f"策略不存在: {strategy_name} - {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404

    except Exception as e:
        logger.error(f"获取账户信息失败: {strategy_name} - {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/<strategy_name>/positions', methods=['GET'])
def get_positions(strategy_name: str):
    """
    获取策略持仓明细（统一接口）

    Args:
        strategy_name: 策略名称

    Returns:
        {
            "success": true,
            "data": [
                {
                    "symbol": "600000",
                    "name": "浦发银行",
                    "shares": 1000,
                    "cost": 10.5,
                    "current_price": 11.2,
                    "market_value": 11200,
                    "profit": 700,
                    "profit_pct": 0.0667
                }
            ]
        }

    Examples:
        GET /api/strategy/v13/positions
        GET /api/strategy/v14/positions
    """
    try:
        service = StrategyService()
        positions = service.get_positions(strategy_name)

        return jsonify({
            'success': True,
            'data': positions
        }), 200

    except ValueError as e:
        logger.warning(f"策略不存在: {strategy_name} - {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404

    except Exception as e:
        logger.error(f"获取持仓失败: {strategy_name} - {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/<strategy_name>/rebalance', methods=['POST'])
def manual_rebalance(strategy_name: str):
    """
    手动触发调仓（统一接口）

    Args:
        strategy_name: 策略名称

    Request Body (可选):
        {
            "rebalance_days": 5,      // 可选：覆盖调仓周期
            "max_positions": 10       // 可选：覆盖最大持仓数
        }

    Returns:
        {
            "success": true,
            "data": {
                "strategy": "v13",
                "status": "success",
                "account_name": "default",
                "timestamp": "2026-06-30T15:30:00",
                "result": {...}
            }
        }

    Examples:
        POST /api/strategy/v13/rebalance
        POST /api/strategy/v14/rebalance
    """
    try:
        service = StrategyService()

        # 获取可选参数
        params = request.get_json() if request.is_json else {}

        result = service.manual_rebalance(strategy_name, **params)

        return jsonify({
            'success': True,
            'data': result
        }), 200

    except ValueError as e:
        logger.warning(f"策略不存在: {strategy_name} - {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404

    except Exception as e:
        logger.error(f"手动调仓失败: {strategy_name} - {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@strategy_bp.route('/<strategy_name>/daily-check', methods=['POST'])
def daily_check(strategy_name: str):
    """
    执行每日检查（统一接口）

    Args:
        strategy_name: 策略名称

    Request Body (可选):
        {
            "enable_stop_loss": true,    // 可选：是否启用止损
            "enable_rebalance": true     // 可选：是否启用调仓
        }

    Returns:
        {
            "success": true,
            "data": {
                "strategy": "v13",
                "status": "success",
                "account_name": "default",
                "timestamp": "2026-06-30T15:30:00",
                "initial_value": 120000,
                "final_value": 121500,
                "cash": 30000,
                "positions_count": 5,
                "cumulative_return": 0.215
            }
        }

    Examples:
        POST /api/strategy/v13/daily-check
        POST /api/strategy/v14/daily-check
    """
    try:
        service = StrategyService()

        # 获取可选参数
        params = request.get_json() if request.is_json else {}

        result = service.daily_check(strategy_name, **params)

        return jsonify({
            'success': True,
            'data': result
        }), 200

    except ValueError as e:
        logger.warning(f"策略不存在: {strategy_name} - {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404

    except Exception as e:
        logger.error(f"每日检查失败: {strategy_name} - {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def init_strategy_api(app):
    """
    初始化统一策略 API

    Args:
        app: Flask 应用实例
    """
    app.register_blueprint(strategy_bp)
    logger.info("✅ 统一策略 API 已注册: /api/strategy/*")

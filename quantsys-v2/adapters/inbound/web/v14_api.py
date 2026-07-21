"""
V14 Web API接口

提供V14策略的前端API接口
"""
from flask import Blueprint, jsonify, request
from datetime import datetime
import logging

from infrastructure.jobs.v14_trading_job import v14_daily_check, v14_manual_rebalance
from live_trading.simulation_trader import SimulationTrader

logger = logging.getLogger(__name__)

# 创建V14 API蓝图
v14_api = Blueprint('v14_api', __name__, url_prefix='/api/v14')


@v14_api.route('/account-info', methods=['GET'])
def get_account_info():
    """获取V14账户信息"""
    try:
        trader = SimulationTrader()
        trader.account_name = 'v14_simulation'
        trader.model_path = 'live_trading/models/v14_p0_model.json'
        trader.factors_path = 'live_trading/models/v14_p0_valid_factors.json'

        # 获取账户信息
        account = trader.repo.get_account(trader.account_name)
        positions = trader.repo.get_all_positions(trader.account_name)

        # 计算持仓市值
        position_value = sum(
            pos.shares_total * (pos.current_price or pos.avg_cost)
            for pos in positions
            if hasattr(pos, 'current_price')
        )

        result = {
            'success': True,
            'account_name': trader.account_name,
            'totalValue': account.total_value if account else 100000,
            'cash': account.cash if account else 10000,
            'positionValue': position_value,
            'totalReturn': (account.total_value - 100000) / 100000 if account else 0,
            'positionsCount': len(positions),
            'lastRebalanceDate': account.last_rebalance_date.strftime('%Y-%m-%d') if account and hasattr(account, 'last_rebalance_date') else None
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"获取V14账户信息失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@v14_api.route('/positions', methods=['GET'])
def get_positions():
    """获取V14持仓明细"""
    try:
        trader = SimulationTrader()
        trader.account_name = 'v14_simulation'

        positions = trader.repo.get_all_positions(trader.account_name)

        result = {
            'success': True,
            'positions': [
                {
                    'symbol': pos.symbol,
                    'name': pos.name if hasattr(pos, 'name') else pos.symbol,
                    'shares': pos.shares_total,
                    'shares_available': pos.shares_available,
                    'avgPrice': float(pos.avg_cost),
                    'currentPrice': float(pos.current_price) if pos.current_price else float(pos.avg_cost),
                    'profit': float(((pos.current_price or pos.avg_cost) - pos.avg_cost) * pos.shares_total),
                    'profitRate': float((pos.current_price or pos.avg_cost) / pos.avg_cost - 1) if pos.avg_cost else 0,
                    'weight': float(pos.shares_total * (pos.current_price or pos.avg_cost) / 100000) if hasattr(pos, 'current_price') else 0
                }
                for pos in positions
            ]
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"获取V14持仓失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@v14_api.route('/trades', methods=['GET'])
def get_trades():
    """获取V14交易记录"""
    try:
        trader = SimulationTrader()
        trader.account_name = 'v14_simulation'

        # 获取最近交易记录
        limit = request.args.get('limit', 50, type=int)
        trades = trader.repo.get_recent_trades(limit=limit)

        result = {
            'success': True,
            'trades': [
                {
                    'id': trade.id,
                    'timestamp': trade.timestamp.isoformat() if hasattr(trade, 'timestamp') else None,
                    'action': trade.action,
                    'symbol': trade.symbol,
                    'shares': trade.shares,
                    'price': float(trade.price),
                    'amount': float(trade.shares * trade.price)
                }
                for trade in trades
            ]
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"获取V14交易记录失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@v14_api.route('/manual-rebalance', methods=['POST'])
def manual_rebalance():
    """V14手动调仓"""
    try:
        logger.info("收到V14手动调仓请求")

        result = v14_manual_rebalance(
            account_name='v14_simulation'
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"V14手动调仓失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@v14_api.route('/daily-check', methods=['POST'])
def daily_check():
    """V14每日检查"""
    try:
        logger.info("收到V14每日检查请求")

        result = v14_daily_check(
            enable_stop_loss=True,
            enable_rebalance=True,
            account_name='v14_simulation'
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"V14每日检查失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@v14_api.route('/strategy-config', methods=['GET'])
def get_strategy_config():
    """获取V14策略配置"""
    try:
        from domain.strategies.v14_strategy import V14Strategy

        strategy = V14Strategy()
        config = strategy.get_config()

        result = {
            'success': True,
            'config': {
                'name': config.name,
                'version': config.version,
                'description': config.description,
                'rebalanceDays': config.rebalance_days,
                'maxPositions': config.max_positions,
                'maxPositionPct': config.max_position_pct,
                'modelPath': config.model_path,
                'params': config.params
            }
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"获取V14策略配置失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@v14_api.route('/performance', methods=['GET'])
def get_performance():
    """获取V14收益曲线数据"""
    try:
        trader = SimulationTrader()
        trader.account_name = 'v14_simulation'

        # TODO: 从数据库查询历史净值数据
        # 这里返回示例数据
        result = {
            'success': True,
            'performance': {
                'dates': ['2026-01-01', '2026-02-01', '2026-03-01', '2026-04-01', '2026-05-01', '2026-06-01'],
                'values': [100000, 105000, 112000, 118000, 125000, 135000],
                'returns': [0, 0.05, 0.12, 0.18, 0.25, 0.35],
                'benchmark': [0, 0.03, 0.06, 0.09, 0.12, 0.15]
            }
        }

        return jsonify(result)

    except Exception as e:
        logger.error(f"获取V14收益曲线失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# 导出蓝图
def init_v14_api(app):
    """将V14 API注册到Flask应用"""
    app.register_blueprint(v14_api)
    logger.info("V14 API已注册")

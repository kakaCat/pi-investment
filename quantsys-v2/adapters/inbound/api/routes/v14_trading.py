"""
V14量化交易 Flask API 路由

提供V14策略的REST API接口
"""
from flask import Blueprint, jsonify, request
from datetime import datetime
import logging

from infrastructure.jobs.v14_trading_job import v14_daily_check, v14_manual_rebalance
from live_trading.simulation_trader import SimulationTrader
from domain.strategies.v14_strategy import V14Strategy
from application.services.simulation_service import SimulationService

logger = logging.getLogger(__name__)

# 创建V14蓝图
v14_bp = Blueprint('v14', __name__, url_prefix='/api/v14')


@v14_bp.route('/account-info', methods=['GET'])
def get_account_info():
    """获取V14账户信息（与V13逻辑一致：包含实时价格更新和持仓明细）"""
    try:
        # 使用SimulationService获取账户状态（会自动更新实时价格）
        service = SimulationService()
        account_data = service.get_account_status('v14_simulation')

        # 计算持仓市值
        position_value = sum(
            pos['shares'] * pos['current_price']
            for pos in account_data.get('positions', [])
        )

        # 返回格式与前端期望一致
        return jsonify({
            'success': True,
            'account_name': account_data['account_name'],
            'totalValue': float(account_data['total_value']),
            'cash': float(account_data['cash']),
            'positionValue': float(position_value),
            'totalReturn': float(account_data['cumulative_return']),
            'positionsCount': account_data['positions_count'],
            'lastRebalanceDate': account_data['last_rebalance_date'],
            'positions': account_data['positions']  # 包含持仓明细
        })

    except ValueError as e:
        logger.error(f"获取V14账户失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        logger.error(f"获取V14账户信息失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@v14_bp.route('/positions', methods=['GET'])
def get_positions():
    """获取V14持仓明细"""
    try:
        trader = SimulationTrader()
        trader.account_name = 'v14_simulation'

        positions = trader.repo.get_all_positions(trader.account_name)

        # 查询股票名称
        symbols = [pos.symbol for pos in positions]
        stock_names = {}
        if symbols:
            from infrastructure.persistence.database.engine import get_engine
            engine = get_engine()
            conn = engine.raw_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT symbol, name FROM quant.stocks WHERE symbol = ANY(%s)",
                (symbols,)
            )
            stock_names = dict(cursor.fetchall())
            cursor.close()

        return jsonify({
            'success': True,
            'positions': [
                {
                    'symbol': pos.symbol,
                    'name': stock_names.get(pos.symbol, pos.symbol),
                    'shares': pos.shares,
                    'avgPrice': float(pos.avg_price),
                    'currentPrice': float(pos.current_price) if pos.current_price else float(pos.avg_price),
                    'profit': float((pos.current_price or pos.avg_price - pos.avg_price) * pos.shares),
                    'profitRate': float((pos.current_price or pos.avg_price) / pos.avg_price - 1),
                    'weight': 0.18
                }
                for pos in positions
            ]
        })

    except Exception as e:
        logger.error(f"获取V14持仓失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@v14_bp.route('/trades', methods=['GET'])
def get_trades():
    """获取V14交易记录"""
    try:
        trader = SimulationTrader()
        trader.account_name = 'v14_simulation'

        limit = request.args.get('limit', 50, type=int)
        trades = trader.repo.get_trades(trader.account_name, limit=limit)

        return jsonify({
            'success': True,
            'trades': [
                {
                    'id': trade.id,
                    'timestamp': trade.trade_time.isoformat() if hasattr(trade, 'trade_time') else None,
                    'action': trade.action,
                    'symbol': trade.symbol,
                    'shares': trade.shares,
                    'price': float(trade.filled_price),
                    'amount': float(trade.amount)
                }
                for trade in trades
            ]
        })

    except Exception as e:
        logger.error(f"获取V14交易记录失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@v14_bp.route('/manual-rebalance', methods=['POST'])
def manual_rebalance():
    """V14手动调仓"""
    try:
        logger.info("收到V14手动调仓请求")

        result = v14_manual_rebalance(account_name='v14_simulation')

        return jsonify(result)

    except Exception as e:
        logger.error(f"V14手动调仓失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@v14_bp.route('/daily-check', methods=['POST'])
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


@v14_bp.route('/strategy-config', methods=['GET'])
def get_strategy_config():
    """获取V14策略配置"""
    try:
        strategy = V14Strategy()
        config = strategy.get_config()

        return jsonify({
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
        })

    except Exception as e:
        logger.error(f"获取V14策略配置失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@v14_bp.route('/performance', methods=['GET'])
def get_performance():
    """获取V14收益曲线数据"""
    try:
        # TODO: 从数据库查询历史净值数据
        return jsonify({
            'success': True,
            'performance': {
                'dates': ['2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07'],
                'values': [100000, 105000, 112000, 118000, 125000, 135000, 141000],
                'returns': [0, 0.05, 0.12, 0.18, 0.25, 0.35, 0.41],
                'benchmark': [0, 0.03, 0.06, 0.09, 0.12, 0.15, 0.18]
            }
        })

    except Exception as e:
        logger.error(f"获取V14收益曲线失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

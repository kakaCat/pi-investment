"""
模拟交易路由

提供策略执行、账户管理、交易记录、绩效查询等 API
账户显式化：所有账户相关端点 account_name 必填，无 default 兜底
"""
from flask import Blueprint, request, jsonify
import logging
from collections import defaultdict
from datetime import datetime

from application.services.simulation_service import SimulationService
from application.services.account_trading_service import (
    AccountTradingService, TradingError,
)
from adapters.outbound.repositories.simulation_repository import (
    SimulationORMRepository,
)

logger = logging.getLogger(__name__)

simulation_bp = Blueprint('simulation', __name__)

_service = None


def get_service():
    global _service
    if _service is None:
        _service = SimulationService()
    return _service


def _get_repo():
    return SimulationORMRepository()


def _require_account_name(value):
    """account_name 必填校验，返回 (account_name, error_response)"""
    if value:
        return value, None
    repo = _get_repo()
    return None, (jsonify({
        'success': False,
        'error': 'account_name is required',
        'available_accounts': [a.account_name for a in repo.list_accounts()],
    }), 400)


def _require_existing_account(account_name):
    """账户存在性校验，返回 (account, error_response)"""
    repo = _get_repo()
    account = repo.get_account(account_name)
    if account:
        return account, None
    return None, (jsonify({
        'success': False,
        'error': f'账户不存在: {account_name}',
        'available_accounts': [a.account_name for a in repo.list_accounts()],
    }), 404)


@simulation_bp.route('/strategies', methods=['GET'])
def list_strategies():
    """列出所有可用策略"""
    try:
        strategies = get_service().list_strategies()
        return jsonify({
            'success': True,
            'data': strategies
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@simulation_bp.route('/strategies/<strategy_id>', methods=['GET'])
def get_strategy(strategy_id):
    """获取策略详情"""
    try:
        strategy = get_service().get_strategy_info(strategy_id)
        if not strategy:
            return jsonify({
                'success': False,
                'error': f'Strategy {strategy_id} not found'
            }), 404

        return jsonify({
            'success': True,
            'data': strategy
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@simulation_bp.route('/run', methods=['POST'])
def run_strategy():
    """执行策略"""
    try:
        data = request.get_json() or {}
        strategy_id = data.get('strategy_id')
        account_name, err = _require_account_name(data.get('account_name'))
        if err:
            return err
        _, err = _require_existing_account(account_name)
        if err:
            return err
        force_rebalance = data.get('force_rebalance', False)

        if not strategy_id:
            return jsonify({
                'success': False,
                'error': 'strategy_id is required'
            }), 400

        result = get_service().run_strategy(
            strategy_id,
            account_name=account_name,
            force_rebalance=force_rebalance
        )

        return jsonify({
            'success': True,
            'data': result
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@simulation_bp.route('/accounts', methods=['GET'])
def list_accounts():
    """账户发现：列出账户 + 摘要"""
    try:
        status = request.args.get('status', 'active')
        summaries = _get_repo().list_account_summaries(status=status)
        return jsonify({
            'success': True,
            'data': {'accounts': summaries, 'total': len(summaries)}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@simulation_bp.route('/accounts', methods=['POST'])
def create_account():
    """开户"""
    try:
        data = request.get_json() or {}
        account_name = data.get('account_name')
        initial_capital = data.get('initial_capital')
        display_name = data.get('display_name')
        strategy_name = data.get('strategy_name')

        if not account_name or initial_capital is None:
            return jsonify({
                'success': False,
                'error': 'account_name 和 initial_capital 必填'
            }), 400

        repo = _get_repo()
        if repo.get_account(account_name):
            return jsonify({
                'success': False,
                'error': f'账户已存在: {account_name}'
            }), 409

        repo.create_account(
            account_name=account_name,
            initial_capital=float(initial_capital),
            display_name=display_name,
            strategy_name=strategy_name)
        return jsonify({'success': True, 'data': {'account_name': account_name}}), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@simulation_bp.route('/accounts/<account_name>', methods=['GET'])
def get_account(account_name):
    """获取账户状态和持仓"""
    try:
        account = get_service().get_account_status(account_name)
        return jsonify({
            'success': True,
            'data': account
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@simulation_bp.route('/accounts/<account_name>/trade', methods=['POST'])
def manual_trade(account_name):
    """手工/代管交易（agent 虚拟仓核心端点）"""
    try:
        data = request.get_json() or {}
        svc = AccountTradingService()
        result = svc.execute_trade(
            account_name=account_name,
            action=data.get('action'),
            symbol=data.get('symbol'),
            shares=data.get('shares'),
            amount=data.get('amount'),
            price_limit=data.get('price_limit'),
            reason=data.get('reason'),
            max_positions=data.get('max_positions', 10),
            price=data.get('price'),  # 可选注入价格（回放/测试）
            allow_off_hours=bool(data.get('allow_off_hours', False)),  # 回放/测试绕过时段护栏
            execute_at=data.get('execute_at'),  # 条件委托：'market_open' 盘前挂单
        )
        return jsonify({'success': True, 'data': result})
    except TradingError as e:
        return jsonify({'success': False, 'error': str(e)}), e.status_code
    except Exception as e:
        logger.error(f"manual_trade failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@simulation_bp.route('/accounts/<account_name>/pending-orders', methods=['GET'])
def list_pending_orders(account_name):
    """挂单列表（默认只返回 pending，可用 ?status= 过滤，status=all 返回全部）"""
    try:
        status = request.args.get('status', 'pending')
        if status == 'all':
            status = None
        svc = AccountTradingService()
        orders = svc.repo.get_pending_orders(
            account_name=account_name, status=status)
        return jsonify({
            'success': True,
            'data': [o.to_dict() for o in orders]
        })
    except Exception as e:
        logger.error(f"list_pending_orders failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@simulation_bp.route('/accounts/<account_name>/pending-orders/<int:order_id>/cancel',
                     methods=['POST'])
def cancel_pending_order(account_name, order_id):
    """取消挂单（仅 pending 状态可取消）"""
    try:
        svc = AccountTradingService()
        result = svc.cancel_pending_order(account_name, order_id)
        return jsonify({'success': True, 'data': result})
    except TradingError as e:
        return jsonify({'success': False, 'error': str(e)}), e.status_code
    except Exception as e:
        logger.error(f"cancel_pending_order failed: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@simulation_bp.route('/trades', methods=['GET'])
def get_trades():
    """获取交易记录"""
    try:
        account_name, err = _require_account_name(request.args.get('account_name'))
        if err:
            return err
        _, err = _require_existing_account(account_name)
        if err:
            return err
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 100))

        trades = get_service().get_trades(
            account_name=account_name,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

        return jsonify({
            'success': True,
            'data': trades
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@simulation_bp.route('/execution-history', methods=['GET'])
def get_execution_history():
    """获取策略执行历史"""
    try:
        account_name, err = _require_account_name(request.args.get('account_name'))
        if err:
            return err
        strategy_id = request.args.get('strategy_id')
        limit = int(request.args.get('limit', 50))

        repo = _get_repo()

        # 获取交易记录作为执行历史的依据
        trades = repo.get_trades_by_account(account_name, limit)

        # 按日期分组交易记录
        history_by_date = defaultdict(list)

        for trade in trades:
            date = str(trade.trade_date) if hasattr(trade, 'trade_date') else None
            if date:
                history_by_date[date].append({
                    'symbol': trade.symbol,
                    'action': trade.action,
                    'shares': trade.shares,
                    'price': float(trade.filled_price) if trade.filled_price else 0
                })

        # 构造执行历史
        history = []
        for date, trades_list in sorted(history_by_date.items(), reverse=True):
            history.append({
                'date': date,
                'strategy_id': strategy_id or 'v13',
                'strategy_name': 'V13 XGBoost Multi-Factor',
                'status': 'completed',
                'trades_count': len(trades_list),
                'trades': trades_list
            })

        return jsonify({
            'success': True,
            'data': history[:limit]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@simulation_bp.route('/performance', methods=['GET'])
def get_performance():
    """获取账户收益曲线（优先读净值快照表，无快照回退交易重放）"""
    try:
        account_name, err = _require_account_name(request.args.get('account_name'))
        if err:
            return err
        account, err = _require_existing_account(account_name)
        if err:
            return err

        repo = _get_repo()
        initial_capital = float(account.initial_capital or 0)
        if initial_capital <= 0:
            initial_capital = 100000.0

        snaps = repo.get_equity_snapshots(account_name, limit=365)
        if snaps:
            equity_curve = [{
                'date': s.snapshot_date.isoformat(),
                'total_value': float(s.total_value or 0),
                'cash': float(s.cash or 0),
                'market_value': float(s.position_value or 0),
                'return': round(float(s.cumulative_return or 0) * 100, 2),
            } for s in reversed(snaps)]
            total_value = float(account.total_value or 0)
            return jsonify({
                'success': True,
                'data': {
                    'equity_curve': equity_curve,
                    'initial_capital': initial_capital,
                    'current_value': total_value,
                    'cumulative_return': round((total_value - initial_capital) / initial_capital * 100, 2),
                    'max_drawdown': round(float(account.max_drawdown or 0) * 100, 2),
                }
            })

        # ---- 回退：从交易记录重放（历史账户无快照时） ----
        trades = repo.get_trades_by_account(account_name)
        if not trades:
            return jsonify({
                'success': True,
                'data': {
                    'equity_curve': [{
                        'date': str(datetime.now().date()),
                        'total_value': initial_capital,
                        'cash': initial_capital,
                        'return': 0.0
                    }],
                    'initial_capital': initial_capital,
                    'current_value': initial_capital,
                    'cumulative_return': 0.0,
                    'max_drawdown': 0.0
                }
            })

        daily_cash = {}
        daily_positions = defaultdict(dict)
        current_positions = {}
        current_cash = initial_capital

        sorted_trades = sorted(trades, key=lambda t: t.trade_date)

        for trade in sorted_trades:
            date = str(trade.trade_date)
            symbol = trade.symbol
            shares = trade.shares
            price = float(trade.filled_price) if trade.filled_price else 0
            commission = float(trade.commission) if trade.commission else 0
            stamp_duty = float(trade.stamp_duty) if trade.stamp_duty else 0

            if trade.action.upper() == 'BUY':
                cost = price * shares + commission
                current_cash -= cost
                current_positions[symbol] = current_positions.get(symbol, 0) + shares
            elif trade.action.upper() == 'SELL':
                revenue = price * shares - commission - stamp_duty
                current_cash += revenue
                current_positions[symbol] = current_positions.get(symbol, 0) - shares
                if current_positions[symbol] <= 0:
                    del current_positions[symbol]

            daily_cash[date] = current_cash
            daily_positions[date] = dict(current_positions)

        equity_curve = []
        max_value = initial_capital
        max_drawdown = 0.0

        for date in sorted(daily_cash.keys()):
            cash = daily_cash[date]
            positions = daily_positions[date]

            position_market_value = sum(float(pos.market_value or 0) for pos in account.positions)

            if position_market_value == 0:
                for symbol, shares in positions.items():
                    for pos in account.positions:
                        if pos.symbol == symbol:
                            if pos.current_price is not None:
                                price = float(pos.current_price)
                            elif pos.avg_cost is not None:
                                price = float(pos.avg_cost)
                            else:
                                price = 0.0
                            position_market_value += price * shares
                            break

            total_value = cash + position_market_value
            cumulative_return = (total_value - initial_capital) / initial_capital * 100

            if total_value > max_value:
                max_value = total_value
            drawdown = (total_value - max_value) / max_value * 100
            if drawdown < max_drawdown:
                max_drawdown = drawdown

            equity_curve.append({
                'date': date,
                'total_value': round(total_value, 2),
                'cash': round(cash, 2),
                'market_value': round(position_market_value, 2),
                'return': round(cumulative_return, 2)
            })

        return jsonify({
            'success': True,
            'data': {
                'equity_curve': equity_curve,
                'initial_capital': initial_capital,
                'current_value': float(account.total_value or 0),
                'cumulative_return': round((float(account.total_value or 0) - initial_capital) / initial_capital * 100, 2),
                'max_drawdown': round(max_drawdown, 2) if max_drawdown else 0.0
            }
        })
    except Exception as e:
        logger.error(f"get_performance failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

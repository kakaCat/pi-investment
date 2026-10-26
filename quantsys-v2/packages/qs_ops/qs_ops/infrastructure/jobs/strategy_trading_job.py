"""
统一策略交易定时任务

提供配置驱动的定时任务，支持所有策略版本（V13/V14/V15...）
避免重复代码，统一接口

使用方式：
    # 通用接口
    strategy_daily_check('v13')
    strategy_daily_check('v14')
    strategy_daily_check('v15')

    # 向后兼容接口
    v13_daily_check()
    v14_daily_check()
"""
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# 添加项目路径

from qs_strategy.application.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)


def strategy_daily_check(strategy_name: str, **params):
    """
    策略每日检查（统一接口）

    Args:
        strategy_name: 策略名称（v13/v14/v15...）
        **params: 可选参数（覆盖配置）
            - enable_stop_loss: 是否启用止损检查（默认True）
            - enable_rebalance: 是否启用调仓（默认True）
            - rebalance_days: 覆盖调仓周期
            - max_positions: 覆盖最大持仓数

    Returns:
        dict: 执行结果
            - strategy: 策略名称
            - status: 'success' | 'failed'
            - account_name: 账户名称
            - timestamp: 执行时间
            - initial_value: 初始资产
            - final_value: 最终资产
            - cash: 现金
            - positions_count: 持仓数量
            - cumulative_return: 累计收益率

    Examples:
        # V13
        strategy_daily_check('v13')

        # V14
        strategy_daily_check('v14')

        # V15（未来，无需修改代码）
        strategy_daily_check('v15')

        # 带参数
        strategy_daily_check('v13', enable_stop_loss=False)
    """
    logger.info(f"{'='*70}")
    logger.info(f"{strategy_name.upper()} 模拟交易每日检查开始")
    logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*70}")

    try:
        service = StrategyService()

        # 获取策略配置
        config = service.get_config(strategy_name)
        logger.info(f"策略配置:")
        logger.info(f"  名称: {config['strategy']['name']}")
        logger.info(f"  版本: {config['strategy']['version']}")
        logger.info(f"  账户: {config['strategy']['account_name']}")
        logger.info(f"  调仓周期: {config['trading']['rebalance_days']}天")
        logger.info(f"  最大持仓: {config['trading']['max_positions']}只")

        # 执行每日检查
        result = service.daily_check(strategy_name, **params)

        logger.info(f"\n{'='*70}")
        logger.info(f"✅ {strategy_name.upper()} 模拟交易每日检查完成")
        logger.info(f"{'='*70}")
        logger.info(f"执行结果:")
        logger.info(f"  状态: {result['status']}")
        logger.info(f"  账户: {result['account_name']}")
        logger.info(f"  最终资产: ¥{result['final_value']:,.2f}")
        logger.info(f"  现金: ¥{result['cash']:,.2f}")
        logger.info(f"  持仓数量: {result['positions_count']}只")
        logger.info(f"  累计收益率: {result['cumulative_return']*100:.2f}%")
        logger.info(f"{'='*70}")

        return result

    except Exception as e:
        logger.error(f"{'='*70}")
        logger.error(f"❌ {strategy_name.upper()} 模拟交易每日检查失败")
        logger.error(f"{'='*70}")
        logger.error(f"错误信息: {e}")

        import traceback
        traceback.print_exc()

        return {
            'strategy': strategy_name,
            'status': 'failed',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


# ==================== 统一执行入口（StrategyExecutor） ====================

def strategy_execute_all(**params):
    """
    全策略每日执行（统一任务，替代 v13_daily_check / v14_daily_check）

    对当日执行所有启用策略。走 StrategyService/SimulationTrader 这条已接入
    真实账户、模型和交易持久化的链路；单一策略失败不会阻断其余策略。

    Args:
        **params: 可选参数
            - date: 交易日期（YYYY-MM-DD，默认今天；仅记录，状态仍按数据库调仓日推进）
            - strategies: 策略名列表（默认所有启用策略）
            - enable_stop_loss / enable_rebalance: 每日检查开关
            - enable_* 其它参数原样传给 strategy_daily_check

    Returns:
        dict: 合并结果
            - date: 交易日期
            - success: 全部策略成功/跳过才为 True
            - V13 / V14: 各策略结果键（大写版本号，失败含 error）
    """
    from qs_strategy.application.services.strategy_service import StrategyService

    date = params.get('date') or datetime.now().strftime('%Y-%m-%d')

    logger.info(f"{'='*70}")
    logger.info("全策略每日执行开始（StrategyService.daily_check）")
    logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*70}")

    try:
        strategy_service = StrategyService()
        strategies = params.get('strategies')
        if not strategies:
            strategies = [
                name for name in strategy_service.list_strategies()
                if strategy_service.get_config(name).get('strategy', {}).get('enabled', True)
            ]
        result = {'date': date, 'success': True}

        for strategy_name in strategies:
            version = str(strategy_name).upper()
            try:
                result[version] = strategy_daily_check(strategy_name, **params)
                status = result[version].get('status')
                if status == 'failed':
                    result['success'] = False
                logger.info(f"  {version}: {status}")
            except Exception as exc:  # noqa: BLE001 - one strategy must not block the rest
                logger.error(f"  {version}: failed: {exc}")
                result[version] = {'success': False, 'error': str(exc)}
                result['success'] = False

        logger.info(f"{'='*70}")
        logger.info(
            f"{'✅' if result['success'] else '❌'} 全策略每日执行完成"
            f"（overall success={result['success']}）"
        )
        logger.info(f"{'='*70}")

        return result

    except Exception as e:
        logger.error(f"❌ 全策略每日执行失败: {e}")

        import traceback
        traceback.print_exc()

        return {
            'success': False,
            'error': str(e),
            'date': date,
            'timestamp': datetime.now().isoformat()
        }


# ==================== 盘中风控任务（IntradayRiskService） ====================

class _PersistentSellAdapter:
    """将 SimulationTrader 适配为 IntradayRiskService 所需的
    ``trader.sell(symbol, quantity, price)`` 接口。

    broker.sell 只计算成交经济（滑点/佣金/印花税），不落库；本适配器
    补齐持久化副作用，与 SimulationTrader._execute_stop_loss 保持一致：
    现金更新 + 成交记录（含 realized_pnl）+ 持仓删除 + 账户状态保存。
    """

    def __init__(self, trader, trade_date: str):
        self._trader = trader
        self._trade_date = trade_date

    def sell(self, symbol, quantity, price):
        t = self._trader
        trade = t.broker.sell(symbol, quantity, price)
        t.cash += trade['total_revenue']

        t._record_sell_trade(symbol, quantity, price, trade, self._trade_date)

        if symbol in t.portfolio:
            del t.portfolio[symbol]
        t.repo.delete_position(t.account_name, symbol)
        t._save_account_to_db()

        logger.warning(f"盘中风控止损卖出 {symbol}: {quantity}股 @ ¥{price:.2f}")
        return trade


def _intraday_strategy_targets(params):
    """解析盘中风控要检查的策略账户。

    默认遍历所有启用策略并使用 YAML 中的 account_name；也保留显式
    account_name/strategy_name 参数，便于单账户排障和测试。
    """
    from qs_strategy.application.services.strategy_service import StrategyService

    service = StrategyService()

    if params.get('strategy_name'):
        return [(service.get_config(params['strategy_name']), params.get('account_name'))]

    if params.get('account_name'):
        return [(None, params['account_name'])]

    targets = []
    for name in service.list_strategies():
        config = service.get_config(name)
        if config.get('strategy', {}).get('enabled', True):
            targets.append((config, None))
    return targets


def intraday_risk_check(**params):
    """
    盘中风控检查（每30分钟，交易时段 10:00-14:30）

    遍历启用策略的真实账户，对所有持仓执行固定/移动止损检查。触发时
    经由 _PersistentSellAdapter 卖出并落库（飞书告警由服务内部发送）。

    Args:
        **params: 可选参数
            - date: 交易日期（YYYY-MM-DD，默认今天）
            - account_name: 只检查指定账户
            - strategy_name: 只检查指定策略配置
            - stop_loss_pct: 覆盖固定止损阈值
            - trailing_stop_pct: 覆盖移动止损阈值

    Returns:
        dict: 聚合结果
            - date/checked/actions/success: 保持既有顶层字段
            - accounts: 每个账户的明细结果
    """
    from application.risk import IntradayRiskService
    from live_trading.simulation_trader import SimulationTrader
    from adapters.outbound.repositories.simulation_position_repository import (
        SimulationPositionRepository,
    )

    date = params.get('date') or datetime.now().strftime('%Y-%m-%d')

    logger.info(f"{'='*70}")
    logger.info("盘中风控检查开始（IntradayRiskService.check_positions）")
    logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"交易日期: {date}")
    logger.info(f"{'='*70}")

    try:
        aggregate = {
            'success': True,
            'date': date,
            'checked': 0,
            'quote_failures': 0,
            'actions': [],
            'accounts': {},
        }

        for config, explicit_account in _intraday_strategy_targets(params):
            strategy_cfg = (config or {}).get('strategy', {})
            risk_cfg = (config or {}).get('risk', {})
            account_name = explicit_account or strategy_cfg.get('account_name')
            if not account_name:
                raise ValueError('盘中风控目标缺少 account_name')

            stop_loss_pct = params.get(
                'stop_loss_pct', risk_cfg.get('single_stock_stop_loss', -0.12))
            trailing_stop_pct = params.get(
                'trailing_stop_pct', risk_cfg.get('trailing_stop_pct', -0.08))

            trader = SimulationTrader(account_name=account_name)
            position_repo = SimulationPositionRepository()
            cached_positions = {
                p.symbol: p for p in position_repo.get_all_positions(account_name)
            }

            def observe_price(symbol, price, positions=cached_positions, repo=position_repo):
                position = positions.get(symbol)
                if not position:
                    return
                repo.upsert_position(
                    account_name=account_name,
                    symbol=symbol,
                    shares_total=position.shares_total,
                    avg_cost=position.avg_cost,
                    shares_available=position.shares_available,
                    current_price=price,
                )

            service = IntradayRiskService(
                position_repo=position_repo,
                trader=_PersistentSellAdapter(trader, date),
                engine=trader,
                stop_loss_pct=float(stop_loss_pct),
                trailing_stop_pct=float(trailing_stop_pct),
                price_provider=trader.get_price,
                price_observer=observe_price,
            )
            result = service.check_positions(date)
            aggregate['accounts'][account_name] = result
            aggregate['checked'] += result['checked']
            aggregate['quote_failures'] += result.get('quote_failures', 0)
            aggregate['actions'].extend(result['actions'])
            if not result['success']:
                aggregate['success'] = False

            logger.info(
                "账户 %s: 检查 %d 只持仓, 行情失败 %d, 止损动作 %d, success=%s",
                account_name,
                result['checked'],
                result.get('quote_failures', 0),
                len(result['actions']),
                result['success'],
            )

        logger.info(f"{'='*70}")
        logger.info(
            f"{'✅' if aggregate['success'] else '❌'} 盘中风控检查完成: "
            f"检查 {aggregate['checked']} 只持仓, "
            f"行情失败 {aggregate['quote_failures']} 只, "
            f"触发 {len(aggregate['actions'])} 个止损动作"
        )
        logger.info(f"{'='*70}")

        return aggregate

    except Exception as e:
        logger.error(f"❌ 盘中风控检查失败: {e}")

        import traceback
        traceback.print_exc()

        return {
            'success': False,
            'error': str(e),
            'date': date,
            'checked': 0,
            'quote_failures': 0,
            'actions': [],
            'timestamp': datetime.now().isoformat()
        }


# ==================== 向后兼容接口 ====================

def v13_daily_check(**params):
    """
    V13每日检查（向后兼容接口）

    这是一个兼容层，实际调用统一接口 strategy_daily_check('v13')

    Args:
        **params: 可选参数
            - model_path: 模型路径（会被配置覆盖）
            - factors_path: 因子路径（会被配置覆盖）
            - enable_stop_loss: 是否启用止损
            - enable_rebalance: 是否启用调仓

    Returns:
        dict: 执行结果（与原接口格式一致）

    Note:
        建议使用新接口 strategy_daily_check('v13')
    """
    logger.info("⚠️ 使用旧接口 v13_daily_check()，建议迁移到 strategy_daily_check('v13')")
    return strategy_daily_check('v13', **params)


def v14_daily_check(**params):
    """
    V14每日检查（向后兼容接口）

    这是一个兼容层，实际调用统一接口 strategy_daily_check('v14')

    Args:
        **params: 可选参数（同 v13_daily_check）

    Returns:
        dict: 执行结果（与原接口格式一致）

    Note:
        建议使用新接口 strategy_daily_check('v14')
    """
    logger.info("⚠️ 使用旧接口 v14_daily_check()，建议迁移到 strategy_daily_check('v14')")
    return strategy_daily_check('v14', **params)


def v13_manual_rebalance(**params):
    """
    V13手动调仓（向后兼容接口）

    Note:
        建议使用新接口: StrategyService().manual_rebalance('v13')
    """
    logger.info("⚠️ 使用旧接口 v13_manual_rebalance()，建议迁移到统一接口")
    service = StrategyService()
    return service.manual_rebalance('v13', **params)


def v14_manual_rebalance(**params):
    """
    V14手动调仓（向后兼容接口）

    Note:
        建议使用新接口: StrategyService().manual_rebalance('v14')
    """
    logger.info("⚠️ 使用旧接口 v14_manual_rebalance()，建议迁移到统一接口")
    service = StrategyService()
    return service.manual_rebalance('v14', **params)


# ==================== 测试入口 ====================

if __name__ == '__main__':
    """命令行测试"""
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python strategy_trading_job.py v13")
        print("  python strategy_trading_job.py v14")
        print("  python strategy_trading_job.py v15")
        sys.exit(1)

    strategy = sys.argv[1]
    print(f"\n开始测试 {strategy} 每日检查...\n")

    result = strategy_daily_check(strategy)

    if result['status'] == 'success':
        print(f"\n✅ 测试成功")
        sys.exit(0)
    else:
        print(f"\n❌ 测试失败: {result.get('error')}")
        sys.exit(1)

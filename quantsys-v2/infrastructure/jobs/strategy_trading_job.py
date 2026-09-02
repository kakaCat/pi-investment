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

from application.services.strategy_service import StrategyService

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

    构建 StrategyExecutor 并对当日执行所有启用策略（V13 + V14）。
    单一策略失败不会阻断其余策略，失败信息记录在该策略的结果条目中。

    Args:
        **params: 可选参数
            - date: 交易日期（YYYY-MM-DD，默认今天）
            - account_name: 账户名称（默认 'default'）

    Returns:
        dict: StrategyExecutor.execute_all 的合并结果
            - date: 交易日期
            - success: 全部策略成功才为 True
            - V13 / V14: 各策略的执行结果（或失败信息）
    """
    from application.strategies import StrategyExecutor
    from live_trading.simulation_trader import SimulationTrader
    from adapters.outbound.repositories.simulation_position_repository import (
        SimulationPositionRepository,
    )

    date = params.get('date')
    account_name = params.get('account_name', 'default')

    logger.info(f"{'='*70}")
    logger.info("全策略每日执行开始（StrategyExecutor.execute_all）")
    logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*70}")

    try:
        # SimulationTrader 同时充当 engine：其 .config 字典为 executor
        # 提供飞书通知配置（见 StrategyExecutor._create_notifier）
        trader = SimulationTrader(account_name=account_name)
        executor = StrategyExecutor(
            trader=trader,
            position_repo=SimulationPositionRepository(),
            engine=trader,
        )
        result = executor.execute_all(date)

        for version, entry in sorted(result.items()):
            if isinstance(entry, dict):
                status = 'success' if entry.get('success', True) else 'failed'
                logger.info(f"  {version}: {status}")
        logger.info(f"{'='*70}")
        logger.info(f"✅ 全策略每日执行完成（overall success={result['success']}）")
        logger.info(f"{'='*70}")

        return result

    except Exception as e:
        logger.error(f"❌ 全策略每日执行失败: {e}")

        import traceback
        traceback.print_exc()

        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


# ==================== 盘中风控任务（IntradayRiskService） ====================

class _PersistentSellAdapter:
    """将 SimulationTrader 适配为 IntradayRiskService 所需的
    ``trader.sell(symbol, quantity, price)`` 接口。

    broker.sell 只计算成交经济（滑点/佣金/印花税），不落库；本适配器
    补齐持久化副作用，与 SimulationTrader._execute_stop_loss 保持一致：
    现金更新 + 成交记录（add_trade）+ 持仓删除（delete_position）。
    """

    def __init__(self, trader, trade_date: str):
        self._trader = trader
        self._trade_date = trade_date

    def sell(self, symbol, quantity, price):
        t = self._trader
        trade = t.broker.sell(symbol, quantity, price)
        t.cash += trade['total_revenue']

        t.repo.add_trade(
            account_name=t.account_name,
            symbol=symbol,
            action='SELL',
            shares=quantity,
            price=price,
            filled_price=trade['filled_price'],
            amount=trade['amount'],
            commission=trade['commission'],
            stamp_duty=trade.get('stamp_duty', 0),
            total_revenue=trade['total_revenue'],
            trade_date=self._trade_date,
            reason='intraday_risk_stop_loss',
        )

        if symbol in t.portfolio:
            del t.portfolio[symbol]
        t.repo.delete_position(t.account_name, symbol)

        logger.warning(f"盘中风控止损卖出 {symbol}: {quantity}股 @ ¥{price:.2f}")
        return trade


def intraday_risk_check(**params):
    """
    盘中风控检查（每30分钟，交易时段 10:00-14:30）

    构建 IntradayRiskService 并对所有持仓执行止损/移动止损规则检查，
    触发时经由 _PersistentSellAdapter 卖出并落库（飞书告警由服务内部发送）。

    Args:
        **params: 可选参数
            - date: 交易日期（YYYY-MM-DD，默认今天）
            - account_name: 账户名称（默认 'default'，与 strategy_execute_all 一致）

    Returns:
        dict: IntradayRiskService.check_positions 的结果
            - date: 交易日期
            - checked: 检查的持仓数
            - actions: 触发的止损动作列表
            - success: 整体是否成功
    """
    from application.risk import IntradayRiskService
    from live_trading.simulation_trader import SimulationTrader
    from adapters.outbound.repositories.simulation_position_repository import (
        SimulationPositionRepository,
    )

    date = params.get('date') or datetime.now().strftime('%Y-%m-%d')
    account_name = params.get('account_name', 'default')

    logger.info(f"{'='*70}")
    logger.info("盘中风控检查开始（IntradayRiskService.check_positions）")
    logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"交易日期: {date}  账户: {account_name}")
    logger.info(f"{'='*70}")

    try:
        # SimulationTrader 同时充当 engine：其 .config 字典为服务提供
        # 飞书通知配置与 risk 阈值覆盖，.account_name 决定检查的账户
        trader = SimulationTrader(account_name=account_name)
        service = IntradayRiskService(
            position_repo=SimulationPositionRepository(),
            trader=_PersistentSellAdapter(trader, date),
            engine=trader,
        )
        result = service.check_positions(date)

        logger.info(f"{'='*70}")
        logger.info(
            f"✅ 盘中风控检查完成: 检查 {result['checked']} 只持仓, "
            f"触发 {len(result['actions'])} 个止损动作"
        )
        logger.info(f"{'='*70}")

        return result

    except Exception as e:
        logger.error(f"❌ 盘中风控检查失败: {e}")

        import traceback
        traceback.print_exc()

        return {
            'success': False,
            'error': str(e),
            'date': date,
            'checked': 0,
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

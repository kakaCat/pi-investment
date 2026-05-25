"""
熔断机制集成示例

演示如何在回测引擎中集成熔断机制和风险事件记录。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from quantsys.risk import CircuitBreaker, CircuitBreakerConfig, RiskEventLogger
from quantsys.backtest.engine import BacktestEngine
from quantsys.backtest.portfolio import Portfolio
from datetime import datetime


def example_basic_usage():
    """基础使用示例"""
    print("=" * 60)
    print("示例 1: 基础熔断机制")
    print("=" * 60)

    # 创建熔断器（使用默认配置）
    breaker = CircuitBreaker()

    # 创建风险事件记录器
    risk_logger = RiskEventLogger(log_dir='logs/risk_events', persist=True)

    # 模拟投资组合
    portfolio = Portfolio(initial_capital=1000000)
    portfolio.cash = 950000  # 亏损5万
    portfolio.total_equity = 950000

    # 模拟交易记录
    recent_trades = [
        {'pnl': -10000, 'strategy_id': 'ma_cross'},
        {'pnl': -8000, 'strategy_id': 'ma_cross'},
        {'pnl': -5000, 'strategy_id': 'ma_cross'},
    ]

    # 检查熔断条件
    should_halt, level, reason = breaker.check(
        portfolio=portfolio,
        recent_trades=recent_trades,
        current_date='2024-01-15'
    )

    print(f"\n熔断检查结果:")
    print(f"  是否熔断: {should_halt}")
    print(f"  级别: {level}")
    print(f"  原因: {reason}")

    # 如果触发熔断，记录事件
    if should_halt and level == 'HALT':
        risk_logger.record_circuit_break(
            strategy_id='ma_cross',
            reason=reason,
            trigger_type='consecutive_loss',
            trigger_value=3,
            threshold=3
        )

    # 查看熔断器状态
    status = breaker.get_status()
    print(f"\n熔断器状态:")
    for key, value in status.items():
        print(f"  {key}: {value}")


def example_custom_config():
    """自定义配置示例"""
    print("\n" + "=" * 60)
    print("示例 2: 自定义熔断配置")
    print("=" * 60)

    # 创建自定义配置
    config = CircuitBreakerConfig(
        daily_loss_limit=0.03,           # 单日亏损3%熔断
        daily_loss_warn=0.02,            # 单日亏损2%预警
        consecutive_loss_limit=2,        # 连续2次亏损熔断
        max_drawdown_limit=0.15,         # 最大回撤15%熔断
        auto_resume_enabled=True,        # 启用自动恢复
        auto_resume_delay_minutes=30,    # 30分钟后自动恢复
        reduce_position_on_warn=True,    # 预警时降仓
        reduce_position_pct=0.5          # 降至50%
    )

    breaker = CircuitBreaker(config=config)

    print(f"\n自定义配置:")
    print(f"  单日亏损限制: {config.daily_loss_limit:.1%}")
    print(f"  连续亏损限制: {config.consecutive_loss_limit}次")
    print(f"  最大回撤限制: {config.max_drawdown_limit:.1%}")
    print(f"  自动恢复: {config.auto_resume_enabled}")
    print(f"  预警降仓: {config.reduce_position_on_warn}")


def example_integration_with_backtest():
    """与回测引擎集成示例"""
    print("\n" + "=" * 60)
    print("示例 3: 集成到回测引擎")
    print("=" * 60)

    # 创建熔断器和风险记录器
    breaker = CircuitBreaker()
    risk_logger = RiskEventLogger()

    # 创建投资组合
    portfolio = Portfolio(initial_capital=1000000)

    # 模拟回测过程
    print("\n模拟回测过程:")

    for day in range(1, 11):
        date = f"2024-01-{day:02d}"

        # 模拟交易
        trade_pnl = -15000 if day <= 3 else 10000  # 前3天亏损，后面盈利

        # 更新投资组合
        portfolio.cash += trade_pnl
        portfolio.total_equity = portfolio.cash

        # 记录交易
        trade = {
            'date': date,
            'pnl': trade_pnl,
            'strategy_id': 'test_strategy'
        }

        # 更新熔断器
        breaker.update_trade_result(trade)

        # 检查熔断
        should_halt, level, reason = breaker.check(
            portfolio=portfolio,
            recent_trades=[trade],
            current_date=date
        )

        print(f"  Day {day}: PnL={trade_pnl:>7}, 权益={portfolio.total_equity:>9,.0f}, "
              f"连续亏损={breaker.consecutive_losses}, "
              f"状态={'🚨熔断' if should_halt else '✅正常' if level != 'WARN' else '⚠️预警'}")

        # 如果熔断，停止交易
        if should_halt:
            risk_logger.record_circuit_break(
                strategy_id='test_strategy',
                reason=reason,
                trigger_type='consecutive_loss',
                trigger_value=breaker.consecutive_losses,
                threshold=breaker.config.consecutive_loss_limit
            )
            print(f"\n  ⛔ 熔断触发: {reason}")
            print(f"  停止交易，等待恢复...")
            break

    # 显示统计
    print(f"\n熔断器统计:")
    stats = breaker.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")


def example_risk_logger():
    """风险事件记录器示例"""
    print("\n" + "=" * 60)
    print("示例 4: 风险事件记录")
    print("=" * 60)

    risk_logger = RiskEventLogger(persist=False)  # 不持久化，仅内存

    # 记录各种风险事件
    print("\n记录风险事件:")

    # 1. 风控拒绝
    class MockOrder:
        symbol = '600036.SH'
        action = 'buy'
        price = 50.0
        shares = 1000

    risk_logger.record_rejection(
        strategy_id='ma_cross',
        rule_id='R1',
        reason='单股仓位超限',
        order=MockOrder()
    )
    print("  ✓ 记录风控拒绝")

    # 2. 熔断事件
    risk_logger.record_circuit_break(
        strategy_id='ma_cross',
        reason='连续亏损3次',
        trigger_type='consecutive_loss',
        trigger_value=3,
        threshold=3
    )
    print("  ✓ 记录熔断事件")

    # 3. 预警事件
    risk_logger.record_warning(
        strategy_id='ma_cross',
        reason='单日亏损接近限制',
        warning_type='daily_loss',
        current_value=0.04,
        threshold=0.05
    )
    print("  ✓ 记录预警事件")

    # 4. 违规事件
    risk_logger.record_violation(
        strategy_id='rsi_reversal',
        reason='超出最大持仓数量',
        violation_type='position_limit',
        violation_details='持仓5只，限制3只'
    )
    print("  ✓ 记录违规事件")

    # 查询统计
    print(f"\n总体统计:")
    stats = risk_logger.get_overall_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # 查询策略摘要
    print(f"\n策略 'ma_cross' 风险摘要:")
    summary = risk_logger.get_strategy_summary('ma_cross')
    for key, value in summary.items():
        print(f"  {key}: {value}")

    # 查询规则统计
    print(f"\n规则触发统计:")
    rule_stats = risk_logger.get_rule_statistics()
    for rule_id, count in rule_stats.items():
        print(f"  {rule_id}: {count}次")


def example_complete_workflow():
    """完整工作流示例"""
    print("\n" + "=" * 60)
    print("示例 5: 完整风控工作流")
    print("=" * 60)

    # 初始化
    breaker = CircuitBreaker(CircuitBreakerConfig(
        daily_loss_limit=0.05,
        consecutive_loss_limit=3,
        reduce_position_on_warn=True
    ))
    risk_logger = RiskEventLogger(persist=False)

    portfolio = Portfolio(initial_capital=1000000)
    trades = []

    print("\n完整风控流程:")
    print("  1. 预交易检查")
    print("  2. 执行交易")
    print("  3. 更新熔断器")
    print("  4. 检查熔断条件")
    print("  5. 记录风险事件")

    # 模拟交易流程
    for i in range(5):
        print(f"\n--- 交易 {i+1} ---")

        # 1. 预交易检查（这里简化）
        print("  ✓ 预交易检查通过")

        # 2. 执行交易
        trade_pnl = -20000  # 模拟亏损
        portfolio.cash += trade_pnl
        portfolio.total_equity = portfolio.cash

        trade = {
            'date': f'2024-01-{i+1:02d}',
            'pnl': trade_pnl,
            'strategy_id': 'test_strategy'
        }
        trades.append(trade)
        print(f"  ✓ 交易执行: PnL={trade_pnl:,}")

        # 3. 更新熔断器
        breaker.update_trade_result(trade)

        # 4. 检查熔断条件
        should_halt, level, reason = breaker.check(
            portfolio=portfolio,
            recent_trades=trades,
            current_date=trade['date']
        )

        if level == 'WARN':
            print(f"  ⚠️  预警: {reason}")
            risk_logger.record_warning(
                strategy_id='test_strategy',
                reason=reason,
                warning_type='consecutive_loss',
                current_value=breaker.consecutive_losses,
                threshold=breaker.config.consecutive_loss_warn
            )

        if should_halt:
            print(f"  🚨 熔断: {reason}")
            risk_logger.record_circuit_break(
                strategy_id='test_strategy',
                reason=reason,
                trigger_type='consecutive_loss',
                trigger_value=breaker.consecutive_losses,
                threshold=breaker.config.consecutive_loss_limit
            )
            break

        print(f"  ✓ 风控检查通过")

    # 最终报告
    print(f"\n最终报告:")
    print(f"  总交易次数: {len(trades)}")
    print(f"  最终权益: {portfolio.total_equity:,.0f}")
    print(f"  总盈亏: {portfolio.total_equity - portfolio.initial_capital:,.0f}")
    print(f"  熔断次数: {risk_logger.circuit_break_count}")
    print(f"  预警次数: {risk_logger.warning_count}")


if __name__ == '__main__':
    # 运行所有示例
    example_basic_usage()
    example_custom_config()
    example_integration_with_backtest()
    example_risk_logger()
    example_complete_workflow()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)

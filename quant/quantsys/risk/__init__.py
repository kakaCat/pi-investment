"""
风控系统 - Risk Management System

量化交易的风险管理模块，包含:
1. 预交易风控 - 订单执行前的风险检查
2. 仓位管理 - 动态调整仓位大小
3. 止损机制 - 多种止损策略
4. 熔断机制 - 极端情况下自动暂停交易
5. 风险事件记录 - 记录所有风控相关事件

使用示例:
    from risk import PreTradeRiskCheck, PositionManager, StopLossManager
    from risk import CircuitBreaker, RiskEventLogger

    # 预交易风控
    risk_check = PreTradeRiskCheck()
    is_valid, error = risk_check.check(order, portfolio)

    # 仓位管理
    position_mgr = PositionManager()
    shares = position_mgr.calculate_position_size(symbol, price, total_equity)

    # 止损管理
    stop_mgr = StopLossManager()
    should_stop, reason = stop_mgr.should_stop_loss(...)

    # 熔断机制
    breaker = CircuitBreaker()
    should_halt, level, reason = breaker.check(portfolio, recent_trades)

    # 风险事件记录
    logger = RiskEventLogger()
    logger.record_rejection(strategy_id, rule_id, reason, order)
"""

from quantsys.risk.pre_trade import PreTradeRiskCheck, RiskConfig
from quantsys.risk.position_manager import PositionManager, PositionSizeConfig
from quantsys.risk.stop_loss import StopLossManager, StopLossConfig
from quantsys.risk.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, HaltEvent
from quantsys.risk.risk_logger import (
    RiskEventLogger,
    RiskEvent,
    RejectionEvent,
    CircuitBreakEvent,
    WarningEvent,
    ViolationEvent
)

__all__ = [
    # 预交易风控
    'PreTradeRiskCheck',
    'RiskConfig',
    # 仓位管理
    'PositionManager',
    'PositionSizeConfig',
    # 止损管理
    'StopLossManager',
    'StopLossConfig',
    # 熔断机制
    'CircuitBreaker',
    'CircuitBreakerConfig',
    'HaltEvent',
    # 风险事件记录
    'RiskEventLogger',
    'RiskEvent',
    'RejectionEvent',
    'CircuitBreakEvent',
    'WarningEvent',
    'ViolationEvent',
]

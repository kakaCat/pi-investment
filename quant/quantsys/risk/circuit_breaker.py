"""
熔断机制 - Circuit Breaker

在极端情况下自动暂停交易，保护资金安全。

熔断条件:
1. 单日亏损超过阈值 (默认5%)
2. 连续亏损次数超限 (默认3次)
3. 最大回撤超过阈值 (默认20%)
4. 单策略连续失败

使用示例:
    breaker = CircuitBreaker()

    # 每次交易后检查
    if breaker.should_halt(portfolio, recent_trades):
        print(f"触发熔断: {breaker.halt_reason}")
        # 停止所有交易
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerConfig:
    """熔断配置"""
    # 单日亏损限制
    daily_loss_limit: float = 0.05              # 5%
    daily_loss_warn: float = 0.03               # 3% 预警

    # 连续亏损限制
    consecutive_loss_limit: int = 3             # 连续3次亏损
    consecutive_loss_warn: int = 2              # 连续2次预警

    # 最大回撤限制
    max_drawdown_limit: float = 0.20            # 20%
    max_drawdown_warn: float = 0.15             # 15% 预警

    # 单策略连续失败限制
    strategy_consecutive_loss_limit: int = 5    # 单策略连续5次失败

    # 自动恢复
    auto_resume_enabled: bool = False           # 是否自动恢复
    auto_resume_delay_minutes: int = 60         # 自动恢复延迟（分钟）

    # 降仓模式
    reduce_position_on_warn: bool = True        # 预警时是否降仓
    reduce_position_pct: float = 0.5            # 降仓比例 50%


@dataclass
class HaltEvent:
    """熔断事件"""
    timestamp: datetime
    reason: str
    trigger_type: str  # 'daily_loss', 'consecutive_loss', 'max_drawdown', 'strategy_failure'
    trigger_value: float
    threshold: float
    strategy_id: Optional[str] = None
    auto_resume_at: Optional[datetime] = None


class CircuitBreaker:
    """
    熔断器

    监控交易风险，在触发条件时自动暂停交易。
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        """
        初始化熔断器

        Args:
            config: 熔断配置，如果为None则使用默认配置
        """
        self.config = config or CircuitBreakerConfig()

        # 熔断状态
        self.is_halted = False
        self.halt_reason = None
        self.halt_timestamp = None
        self.halt_events: List[HaltEvent] = []

        # 预警状态
        self.is_warned = False
        self.warn_reason = None

        # 统计数据
        self.daily_pnl: Dict[str, float] = {}  # {date: pnl}
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.strategy_consecutive_losses: Dict[str, int] = defaultdict(int)
        self.peak_equity = 0.0
        self.current_drawdown = 0.0

        # 降仓状态
        self.position_reduced = False
        self.original_position_size = 1.0

    def check(
        self,
        portfolio,
        recent_trades: Optional[List[Dict]] = None,
        current_date: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        检查是否应该触发熔断

        Args:
            portfolio: 投资组合对象
            recent_trades: 最近的交易记录
            current_date: 当前日期

        Returns:
            (should_halt, level, reason)
            - should_halt: True表示应该熔断
            - level: 'HALT' 或 'WARN' 或 None
            - reason: 触发原因
        """
        # 如果已经熔断，检查是否可以恢复
        if self.is_halted:
            if self._should_auto_resume():
                self.resume("自动恢复")
                return False, None, None
            return True, 'HALT', self.halt_reason

        current_date = current_date or datetime.now().strftime('%Y-%m-%d')

        # 1. 检查单日亏损
        halt, level, reason = self._check_daily_loss(portfolio, current_date)
        if halt:
            if level == 'HALT':
                self.halt(reason, 'daily_loss',
                         self.daily_pnl.get(current_date, 0) / portfolio.initial_capital,
                         self.config.daily_loss_limit)
                return True, 'HALT', reason
            elif level == 'WARN':
                self._warn(reason)
                return False, 'WARN', reason

        # 2. 检查连续亏损
        if recent_trades:
            halt, level, reason = self._check_consecutive_losses(recent_trades)
            if halt:
                if level == 'HALT':
                    self.halt(reason, 'consecutive_loss',
                             self.consecutive_losses,
                             self.config.consecutive_loss_limit)
                    return True, 'HALT', reason
                elif level == 'WARN':
                    self._warn(reason)
                    return False, 'WARN', reason

        # 3. 检查最大回撤
        halt, level, reason = self._check_max_drawdown(portfolio)
        if halt:
            if level == 'HALT':
                self.halt(reason, 'max_drawdown',
                         self.current_drawdown,
                         self.config.max_drawdown_limit)
                return True, 'HALT', reason
            elif level == 'WARN':
                self._warn(reason)
                return False, 'WARN', reason

        # 4. 检查单策略连续失败
        if recent_trades:
            halt, level, reason, strategy_id = self._check_strategy_failures(recent_trades)
            if halt:
                if level == 'HALT':
                    self.halt(reason, 'strategy_failure',
                             self.strategy_consecutive_losses[strategy_id],
                             self.config.strategy_consecutive_loss_limit,
                             strategy_id)
                    return True, 'HALT', reason

        # 清除预警状态
        if self.is_warned:
            self.is_warned = False
            self.warn_reason = None

        return False, None, None

    def _check_daily_loss(self, portfolio, current_date: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """检查单日亏损"""
        # 计算今日盈亏
        if not hasattr(portfolio, 'equity_curve') or len(portfolio.equity_curve) < 2:
            return False, None, None

        # 获取今日和昨日权益
        today_equity = portfolio.total_equity

        # 查找昨日权益
        yesterday_equity = portfolio.initial_capital
        for equity_record in reversed(portfolio.equity_curve[:-1]):
            if equity_record.date != current_date:
                yesterday_equity = equity_record.total_equity
                break

        daily_pnl = today_equity - yesterday_equity
        daily_return = daily_pnl / yesterday_equity if yesterday_equity > 0 else 0

        # 记录
        self.daily_pnl[current_date] = daily_pnl

        # 检查熔断
        if daily_return <= -self.config.daily_loss_limit:
            return True, 'HALT', f"单日亏损 {daily_return:.2%} 触发熔断 (限制: {self.config.daily_loss_limit:.2%})"

        # 检查预警
        if daily_return <= -self.config.daily_loss_warn:
            return True, 'WARN', f"单日亏损 {daily_return:.2%} 触发预警 (限制: {self.config.daily_loss_warn:.2%})"

        return False, None, None

    def _check_consecutive_losses(self, recent_trades: List[Dict]) -> Tuple[bool, Optional[str], Optional[str]]:
        """检查连续亏损"""
        if not recent_trades:
            return False, None, None

        # 统计连续亏损
        consecutive_losses = 0
        for trade in reversed(recent_trades):
            pnl = trade.get('pnl', 0) or trade.get('profit', 0)
            if pnl < 0:
                consecutive_losses += 1
            else:
                break

        self.consecutive_losses = consecutive_losses

        # 检查熔断
        if consecutive_losses >= self.config.consecutive_loss_limit:
            return True, 'HALT', f"连续亏损 {consecutive_losses} 次触发熔断 (限制: {self.config.consecutive_loss_limit}次)"

        # 检查预警
        if consecutive_losses >= self.config.consecutive_loss_warn:
            return True, 'WARN', f"连续亏损 {consecutive_losses} 次触发预警 (限制: {self.config.consecutive_loss_warn}次)"

        return False, None, None

    def _check_max_drawdown(self, portfolio) -> Tuple[bool, Optional[str], Optional[str]]:
        """检查最大回撤"""
        current_equity = portfolio.total_equity

        # 更新峰值
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        # 计算回撤
        if self.peak_equity > 0:
            self.current_drawdown = (self.peak_equity - current_equity) / self.peak_equity
        else:
            self.current_drawdown = 0

        # 检查熔断
        if self.current_drawdown >= self.config.max_drawdown_limit:
            return True, 'HALT', f"最大回撤 {self.current_drawdown:.2%} 触发熔断 (限制: {self.config.max_drawdown_limit:.2%})"

        # 检查预警
        if self.current_drawdown >= self.config.max_drawdown_warn:
            return True, 'WARN', f"最大回撤 {self.current_drawdown:.2%} 触发预警 (限制: {self.config.max_drawdown_warn:.2%})"

        return False, None, None

    def _check_strategy_failures(self, recent_trades: List[Dict]) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """检查单策略连续失败"""
        # 按策略统计连续亏损
        strategy_losses = defaultdict(int)

        for trade in reversed(recent_trades):
            strategy_id = trade.get('strategy_id')
            if not strategy_id:
                continue

            pnl = trade.get('pnl', 0) or trade.get('profit', 0)

            if pnl < 0:
                strategy_losses[strategy_id] += 1
            else:
                # 遇到盈利就停止统计该策略
                if strategy_id in strategy_losses:
                    del strategy_losses[strategy_id]

        self.strategy_consecutive_losses = strategy_losses

        # 检查是否有策略超限
        for strategy_id, losses in strategy_losses.items():
            if losses >= self.config.strategy_consecutive_loss_limit:
                return True, 'HALT', f"策略 {strategy_id} 连续失败 {losses} 次", strategy_id

        return False, None, None, None

    def halt(self, reason: str, trigger_type: str, trigger_value: float, threshold: float, strategy_id: Optional[str] = None):
        """触发熔断"""
        self.is_halted = True
        self.halt_reason = reason
        self.halt_timestamp = datetime.now()

        # 记录熔断事件
        event = HaltEvent(
            timestamp=self.halt_timestamp,
            reason=reason,
            trigger_type=trigger_type,
            trigger_value=trigger_value,
            threshold=threshold,
            strategy_id=strategy_id,
            auto_resume_at=self._calculate_auto_resume_time() if self.config.auto_resume_enabled else None
        )
        self.halt_events.append(event)

        logger.critical(f"🚨 熔断触发: {reason}")

    def _warn(self, reason: str):
        """触发预警"""
        self.is_warned = True
        self.warn_reason = reason

        logger.warning(f"⚠️  风控预警: {reason}")

        # 如果配置了预警降仓
        if self.config.reduce_position_on_warn and not self.position_reduced:
            self._reduce_position()

    def _reduce_position(self):
        """降低仓位"""
        self.position_reduced = True
        logger.warning(f"📉 触发降仓: 降至 {self.config.reduce_position_pct:.0%}")

    def resume(self, reason: str = "手动恢复"):
        """恢复交易"""
        if not self.is_halted:
            return

        self.is_halted = False
        self.halt_reason = None
        self.halt_timestamp = None
        self.position_reduced = False

        logger.info(f"✅ 熔断恢复: {reason}")

    def _should_auto_resume(self) -> bool:
        """检查是否应该自动恢复"""
        if not self.config.auto_resume_enabled or not self.halt_timestamp:
            return False

        elapsed_minutes = (datetime.now() - self.halt_timestamp).total_seconds() / 60
        return elapsed_minutes >= self.config.auto_resume_delay_minutes

    def _calculate_auto_resume_time(self) -> datetime:
        """计算自动恢复时间"""
        from datetime import timedelta
        return datetime.now() + timedelta(minutes=self.config.auto_resume_delay_minutes)

    def update_trade_result(self, trade: Dict):
        """
        更新交易结果（用于统计连续亏损）

        Args:
            trade: 交易记录，需包含 'pnl' 或 'profit' 字段
        """
        pnl = trade.get('pnl', 0) or trade.get('profit', 0)

        if pnl < 0:
            self.consecutive_losses += 1
            self.consecutive_wins = 0

            # 更新策略连续亏损
            strategy_id = trade.get('strategy_id')
            if strategy_id:
                self.strategy_consecutive_losses[strategy_id] += 1
        else:
            self.consecutive_losses = 0
            self.consecutive_wins += 1

            # 重置策略连续亏损
            strategy_id = trade.get('strategy_id')
            if strategy_id and strategy_id in self.strategy_consecutive_losses:
                self.strategy_consecutive_losses[strategy_id] = 0

    def get_status(self) -> Dict:
        """获取熔断器状态"""
        return {
            'is_halted': self.is_halted,
            'halt_reason': self.halt_reason,
            'halt_timestamp': self.halt_timestamp.isoformat() if self.halt_timestamp else None,
            'is_warned': self.is_warned,
            'warn_reason': self.warn_reason,
            'consecutive_losses': self.consecutive_losses,
            'consecutive_wins': self.consecutive_wins,
            'current_drawdown': self.current_drawdown,
            'peak_equity': self.peak_equity,
            'position_reduced': self.position_reduced,
            'total_halt_events': len(self.halt_events),
            'strategy_consecutive_losses': dict(self.strategy_consecutive_losses)
        }

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        if not self.halt_events:
            return {
                'total_halts': 0,
                'halt_by_type': {},
                'halt_by_strategy': {},
                'avg_halt_duration_minutes': 0
            }

        # 按类型统计
        halt_by_type = defaultdict(int)
        halt_by_strategy = defaultdict(int)

        for event in self.halt_events:
            halt_by_type[event.trigger_type] += 1
            if event.strategy_id:
                halt_by_strategy[event.strategy_id] += 1

        return {
            'total_halts': len(self.halt_events),
            'halt_by_type': dict(halt_by_type),
            'halt_by_strategy': dict(halt_by_strategy),
            'latest_halt': self.halt_events[-1].__dict__ if self.halt_events else None
        }

    def reset(self):
        """重置熔断器状态"""
        self.is_halted = False
        self.halt_reason = None
        self.halt_timestamp = None
        self.is_warned = False
        self.warn_reason = None
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.strategy_consecutive_losses.clear()
        self.peak_equity = 0.0
        self.current_drawdown = 0.0
        self.position_reduced = False
        self.daily_pnl.clear()

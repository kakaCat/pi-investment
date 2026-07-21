"""
策略熔断器服务

负责监控策略表现并自动触发熔断机制：
- ACTIVE: 正常运行
- WARNING: 连续亏损或低胜率，发出告警但继续运行
- SUSPENDED: 严重亏损，暂停实盘交易，仅允许纸面测试
"""

from enum import Enum
from typing import Dict, Optional, List
from datetime import datetime
import json
import structlog

from adapters.outbound.repositories import StrategyCircuitBreakerORMRepository
from application.services.circuit_breaker_alert_service import circuit_breaker_alert_service

logger = structlog.get_logger(__name__)


class CircuitBreakerState(str, Enum):
    """熔断器状态"""
    ACTIVE = 'active'
    WARNING = 'warning'
    SUSPENDED = 'suspended'


class StrategyCircuitBreaker:
    """策略熔断器"""

    # 默认配置
    DEFAULT_CONFIG = {
        'consecutive_loss_warning': 5,      # 连续亏损 5 次 → WARNING
        'consecutive_loss_suspended': 8,    # 连续亏损 8 次 → SUSPENDED
        'min_win_rate': 0.30,               # 滚动胜率 < 30% → WARNING
        'rolling_window': 20,               # 滚动窗口 20 笔交易
        'recovery_wins': 3,                 # 恢复需要连续 3 次盈利
    }

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化熔断器

        Args:
            config: 自定义配置（可选）
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.repo = StrategyCircuitBreakerORMRepository()

    def get_state(self, strategy_name: str) -> Dict:
        """
        获取策略熔断状态

        Args:
            strategy_name: 策略名称

        Returns:
            {
                'status': CircuitBreakerState,
                'consecutive_losses': int,
                'consecutive_wins': int,
                'rolling_win_rate': float,
                'reason': str,
                'updated_at': datetime
            }
        """
        state = self.repo.get_state(strategy_name)

        if not state:
            # 首次查询，创建初始状态
            state = {
                'strategy_name': strategy_name,
                'status': CircuitBreakerState.ACTIVE,
                'consecutive_losses': 0,
                'consecutive_wins': 0,
                'rolling_win_rate': None,
                'recent_trades': [],
                'reason': None,
                'updated_at': datetime.now()
            }
            self.repo.save_state(state)

        return state

    def record_trade(self, strategy_name: str, pnl_pct: float) -> Dict:
        """
        记录交易结果并更新熔断状态

        Args:
            strategy_name: 策略名称
            pnl_pct: 盈亏百分比（正数为盈利，负数为亏损）

        Returns:
            更新后的状态
        """
        state = self.get_state(strategy_name)

        # 更新连续盈亏计数
        if pnl_pct > 0:
            state['consecutive_wins'] += 1
            state['consecutive_losses'] = 0
        else:
            state['consecutive_losses'] += 1
            state['consecutive_wins'] = 0

        # 更新滚动窗口交易记录
        recent_trades = state.get('recent_trades', [])
        recent_trades.append(pnl_pct)
        if len(recent_trades) > self.config['rolling_window']:
            recent_trades = recent_trades[-self.config['rolling_window']:]
        state['recent_trades'] = recent_trades

        # 计算滚动胜率
        if len(recent_trades) >= self.config['rolling_window']:
            wins = sum(1 for pnl in recent_trades if pnl > 0)
            state['rolling_win_rate'] = wins / len(recent_trades)
        else:
            state['rolling_win_rate'] = None

        # 更新时间
        state['updated_at'] = datetime.now()

        # 检查状态转换
        new_status = self._check_state_transition(state)
        if new_status != state['status']:
            old_status = state['status']
            state['status'] = new_status
            state['reason'] = self._get_transition_reason(old_status, new_status, state)
            logger.info(f"策略 {strategy_name} 状态变更: {old_status} → {new_status}, 原因: {state['reason']}")

            # 发送告警通知
            self._send_alert(strategy_name, old_status, new_status, state)

        # 保存状态
        self.repo.save_state(state)

        return state

    def _check_state_transition(self, state: Dict) -> CircuitBreakerState:
        """
        检查状态转换

        Args:
            state: 当前状态

        Returns:
            新状态
        """
        current_status = state['status']
        consecutive_losses = state['consecutive_losses']
        consecutive_wins = state['consecutive_wins']
        rolling_win_rate = state['rolling_win_rate']

        # SUSPENDED → ACTIVE: 连续 3 次盈利
        if current_status == CircuitBreakerState.SUSPENDED:
            if consecutive_wins >= self.config['recovery_wins']:
                return CircuitBreakerState.ACTIVE
            return CircuitBreakerState.SUSPENDED

        # ACTIVE/WARNING → SUSPENDED: 连续亏损 ≥ 8 次
        if consecutive_losses >= self.config['consecutive_loss_suspended']:
            return CircuitBreakerState.SUSPENDED

        # ACTIVE → WARNING: 连续亏损 ≥ 5 次 或 滚动胜率 < 30%
        if current_status == CircuitBreakerState.ACTIVE:
            if consecutive_losses >= self.config['consecutive_loss_warning']:
                return CircuitBreakerState.WARNING
            if rolling_win_rate is not None and rolling_win_rate < self.config['min_win_rate']:
                return CircuitBreakerState.WARNING

        # WARNING → ACTIVE: 连续盈利或胜率恢复
        if current_status == CircuitBreakerState.WARNING:
            if consecutive_wins >= 2:  # 连续 2 次盈利恢复
                return CircuitBreakerState.ACTIVE
            if rolling_win_rate is not None and rolling_win_rate >= self.config['min_win_rate']:
                return CircuitBreakerState.ACTIVE

        return current_status

    def _get_transition_reason(self, old_status: CircuitBreakerState, new_status: CircuitBreakerState, state: Dict) -> str:
        """获取状态转换原因"""
        if new_status == CircuitBreakerState.WARNING:
            if state['consecutive_losses'] >= self.config['consecutive_loss_warning']:
                return f"连续亏损 {state['consecutive_losses']} 次"
            if state['rolling_win_rate'] is not None:
                return f"滚动胜率 {state['rolling_win_rate']:.1%} 低于阈值"
        elif new_status == CircuitBreakerState.SUSPENDED:
            return f"连续亏损 {state['consecutive_losses']} 次，触发熔断"
        elif new_status == CircuitBreakerState.ACTIVE:
            if old_status == CircuitBreakerState.SUSPENDED:
                return f"连续盈利 {state['consecutive_wins']} 次，恢复运行"
            return "表现恢复正常"
        return "状态变更"

    def is_allowed(self, strategy_name: str) -> bool:
        """
        检查策略是否允许实盘交易

        Args:
            strategy_name: 策略名称

        Returns:
            True: 允许实盘交易
            False: 仅允许纸面测试
        """
        state = self.get_state(strategy_name)
        return state['status'] != CircuitBreakerState.SUSPENDED

    def get_recommendation(self, strategy_name: str) -> str:
        """
        获取策略推荐等级

        Args:
            strategy_name: 策略名称

        Returns:
            'normal': 正常使用
            'cautious': 谨慎使用
            'avoid': 避免使用
        """
        state = self.get_state(strategy_name)

        if state['status'] == CircuitBreakerState.SUSPENDED:
            return 'avoid'
        elif state['status'] == CircuitBreakerState.WARNING:
            return 'cautious'
        else:
            return 'normal'

    def manual_suspend(self, strategy_name: str, reason: str) -> Dict:
        """
        手动暂停策略

        Args:
            strategy_name: 策略名称
            reason: 暂停原因

        Returns:
            更新后的状态
        """
        state = self.get_state(strategy_name)
        state['status'] = CircuitBreakerState.SUSPENDED
        state['reason'] = f"手动暂停: {reason}"
        state['updated_at'] = datetime.now()

        self.repo.save_state(state)
        logger.info(f"策略 {strategy_name} 手动暂停: {reason}")

        return state

    def manual_resume(self, strategy_name: str) -> Dict:
        """
        手动恢复策略

        Args:
            strategy_name: 策略名称

        Returns:
            更新后的状态
        """
        state = self.get_state(strategy_name)
        state['status'] = CircuitBreakerState.ACTIVE
        state['consecutive_losses'] = 0
        state['consecutive_wins'] = 0
        state['reason'] = "手动恢复"
        state['updated_at'] = datetime.now()

        self.repo.save_state(state)
        logger.info(f"策略 {strategy_name} 手动恢复")

        return state

    def get_all_states(self) -> List[Dict]:
        """获取所有策略的熔断状态"""
        return self.repo.get_all_states()

    def _send_alert(
        self,
        strategy_name: str,
        old_status: CircuitBreakerState,
        new_status: CircuitBreakerState,
        state: Dict
    ) -> None:
        """
        发送状态变更告警

        Args:
            strategy_name: 策略名称
            old_status: 旧状态
            new_status: 新状态
            state: 当前状态详情
        """
        try:
            circuit_breaker_alert_service.send_alert(
                strategy_name=strategy_name,
                old_status=old_status,
                new_status=new_status,
                reason=state.get('reason', '状态变更'),
                state=state
            )
        except Exception as e:
            logger.error(f"发送熔断告警失败: {e}")

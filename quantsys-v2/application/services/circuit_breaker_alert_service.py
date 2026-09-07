"""
策略熔断告警服务

负责在策略熔断状态变更时发送告警通知
"""
import structlog
from typing import Dict, Optional
from datetime import datetime

logger = structlog.get_logger(__name__)


class CircuitBreakerAlert:
    """熔断告警"""

    def __init__(
        self,
        strategy_name: str,
        old_status: str,
        new_status: str,
        reason: str,
        state: Dict
    ):
        self.strategy_name = strategy_name
        self.old_status = old_status
        self.new_status = new_status
        self.reason = reason
        self.state = state
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'strategy_name': self.strategy_name,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'reason': self.reason,
            'consecutive_losses': self.state.get('consecutive_losses', 0),
            'rolling_win_rate': self.state.get('rolling_win_rate'),
            'timestamp': self.timestamp.isoformat()
        }


class CircuitBreakerAlertService:
    """熔断告警服务"""

    def __init__(self):
        """初始化告警服务"""
        self.alert_handlers = []
        self._setup_default_handlers()

    def _setup_default_handlers(self):
        """设置默认告警处理器"""
        # 默认使用日志处理器
        self.alert_handlers.append(self._log_alert)

    def send_alert(
        self,
        strategy_name: str,
        old_status: str,
        new_status: str,
        reason: str,
        state: Dict
    ) -> None:
        """
        发送熔断告警

        Args:
            strategy_name: 策略名称
            old_status: 旧状态
            new_status: 新状态
            reason: 变更原因
            state: 当前状态详情
        """
        alert = CircuitBreakerAlert(
            strategy_name=strategy_name,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
            state=state
        )

        # 调用所有告警处理器
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"告警处理器执行失败: {e}")

    def _log_alert(self, alert: CircuitBreakerAlert) -> None:
        """日志告警处理器"""
        severity = self._get_alert_severity(alert.new_status)

        message = (
            f"【策略熔断告警】\n"
            f"策略名称: {alert.strategy_name}\n"
            f"状态变更: {alert.old_status} → {alert.new_status}\n"
            f"变更原因: {alert.reason}\n"
            f"连续亏损: {alert.state.get('consecutive_losses', 0)} 次\n"
        )

        if alert.state.get('rolling_win_rate') is not None:
            message += f"滚动胜率: {alert.state['rolling_win_rate']:.1%}\n"

        message += f"时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

        if severity == 'critical':
            logger.critical(message)
        elif severity == 'warning':
            logger.warning(message)
        else:
            logger.info(message)

    def _get_alert_severity(self, status: str) -> str:
        """获取告警级别"""
        if status == 'suspended':
            return 'critical'
        elif status == 'warning':
            return 'warning'
        else:
            return 'info'

    def add_handler(self, handler):
        """
        添加自定义告警处理器

        Args:
            handler: 处理器函数，接收 CircuitBreakerAlert 参数
        """
        self.alert_handlers.append(handler)

    def send_suspended_alert(self, strategy_name: str, state: Dict) -> None:
        """
        发送策略暂停告警（快捷方法）

        Args:
            strategy_name: 策略名称
            state: 状态详情
        """
        self.send_alert(
            strategy_name=strategy_name,
            old_status=state.get('previous_status', 'unknown'),
            new_status='suspended',
            reason=state.get('reason', '连续亏损触发熔断'),
            state=state
        )

    def send_warning_alert(self, strategy_name: str, state: Dict) -> None:
        """
        发送策略告警（快捷方法）

        Args:
            strategy_name: 策略名称
            state: 状态详情
        """
        self.send_alert(
            strategy_name=strategy_name,
            old_status=state.get('previous_status', 'active'),
            new_status='warning',
            reason=state.get('reason', '策略表现异常'),
            state=state
        )

    def send_recovery_alert(self, strategy_name: str, state: Dict) -> None:
        """
        发送策略恢复告警（快捷方法）

        Args:
            strategy_name: 策略名称
            state: 状态详情
        """
        self.send_alert(
            strategy_name=strategy_name,
            old_status='suspended',
            new_status='active',
            reason=state.get('reason', '策略表现恢复正常'),
            state=state
        )


# 全局告警服务实例
circuit_breaker_alert_service = CircuitBreakerAlertService()

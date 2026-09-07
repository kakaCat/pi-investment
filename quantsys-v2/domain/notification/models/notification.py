"""
通知聚合根

Notification 是通知领域的核心实体，封装：
1. 通知的业务属性（类型、优先级、内容、接收者）
2. 通知的生命周期（pending -> sending -> sent/failed）
3. 通知的状态转换逻辑

Author: System
Date: 2026-09-02
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import uuid


class NotificationPriority(Enum):
    """通知优先级"""
    LOW = "low"           # 普通通知（日报、周报）
    NORMAL = "normal"     # 常规通知（信号、提醒）
    HIGH = "high"         # 重要通知（风险预警）
    CRITICAL = "critical" # 紧急通知（止损触发、系统故障）


class NotificationStatus(Enum):
    """通知状态"""
    PENDING = "pending"       # 待发送
    SENDING = "sending"       # 发送中
    SENT = "sent"            # 已发送
    FAILED = "failed"        # 发送失败
    FALLBACK = "fallback"    # 降级发送


class NotificationType(Enum):
    """通知类型"""
    # 交易相关
    TRADE_SIGNAL = "trade_signal"           # 交易信号
    REBALANCE = "rebalance"                 # 调仓通知
    VERIFICATION = "verification"           # 验证报告

    # 风险相关
    STOP_LOSS = "stop_loss"                 # 止损触发
    TAKE_PROFIT = "take_profit"             # 止盈触发
    RISK_ALERT = "risk_alert"               # 风险预警

    # 报告相关
    DAILY_REPORT = "daily_report"           # 日报
    WEEKLY_REPORT = "weekly_report"         # 周报
    PREMARKET_REPORT = "premarket_report"   # 盘前报告

    # 系统相关
    SYSTEM_ALERT = "system_alert"           # 系统告警
    ML_TRAIN = "ml_train"                   # 模型训练
    WATCH_TRIGGERED = "watch_triggered"     # 盯盘触发

    # Agent 相关
    AGENT_REMINDER = "agent_reminder"       # Agent 提醒
    AGENT_REPORT = "agent_report"           # Agent 报告


@dataclass
class NotificationRecipient:
    """通知接收者

    Attributes:
        recipient_type: 接收者类型 'user' | 'group' | 'all'
        recipient_id: 接收者ID（可选）
        mention: 是否 @提及
    """
    recipient_type: str  # 'user' | 'group' | 'all'
    recipient_id: Optional[str] = None
    mention: bool = False


@dataclass
class Notification:
    """通知聚合根

    职责：
    1. 封装通知的完整上下文（类型、优先级、内容、接收者）
    2. 维护通知的状态机（pending -> sending -> sent/failed）
    3. 记录通知的生命周期（创建时间、发送时间、重试次数）

    不可变性：
    - 通知创建后，业务属性（类型、内容）不可修改
    - 只有状态转换方法可以修改状态字段

    Examples:
        >>> notif = Notification(
        ...     notification_type=NotificationType.STOP_LOSS,
        ...     title="止损触发",
        ...     content="000001 触发止损",
        ...     priority=NotificationPriority.CRITICAL
        ... )
        >>> notif.mark_sending()
        >>> notif.status
        <NotificationStatus.SENDING: 'sending'>
    """
    # 业务标识
    notification_id: str = field(
        default_factory=lambda: f"notif_{uuid.uuid4().hex[:16]}"
    )
    notification_type: NotificationType = NotificationType.SYSTEM_ALERT

    # 内容
    title: str = ""
    content: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)  # 模板变量

    # 接收者
    recipients: List[NotificationRecipient] = field(default_factory=list)

    # 优先级与状态
    priority: NotificationPriority = NotificationPriority.NORMAL
    status: NotificationStatus = NotificationStatus.PENDING

    # 生命周期
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3

    # 渠道控制
    preferred_channels: List[str] = field(default_factory=list)  # ['feishu', 'agent']
    fallback_enabled: bool = True

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def mark_sending(self) -> None:
        """标记为发送中

        状态转换: PENDING -> SENDING

        Raises:
            ValueError: 如果当前状态不是 PENDING
        """
        if self.status != NotificationStatus.PENDING:
            raise ValueError(f"Cannot mark sending from status {self.status}")
        self.status = NotificationStatus.SENDING

    def mark_sent(self) -> None:
        """标记为已发送

        状态转换: SENDING -> SENT
        更新: sent_at 时间戳
        """
        self.status = NotificationStatus.SENT
        self.sent_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        """标记为失败

        状态转换: SENDING -> FAILED
        更新: failed_at, error_message, retry_count

        Args:
            error: 错误信息
        """
        self.status = NotificationStatus.FAILED
        self.failed_at = datetime.now()
        self.error_message = error
        self.retry_count += 1

    def mark_fallback(self) -> None:
        """标记为降级发送

        状态转换: FAILED -> FALLBACK
        更新: sent_at 时间戳

        说明：
        主渠道失败后，通过降级渠道成功发送时使用
        """
        self.status = NotificationStatus.FALLBACK
        self.sent_at = datetime.now()

    def can_retry(self) -> bool:
        """是否可以重试

        Returns:
            bool: 重试次数未超过最大限制
        """
        return self.retry_count < self.max_retries

    def should_fallback(self) -> bool:
        """是否应该降级

        Returns:
            bool: 启用降级 且 不可重试
        """
        return self.fallback_enabled and not self.can_retry()

    def is_critical(self) -> bool:
        """是否为紧急通知

        Returns:
            bool: 优先级为 CRITICAL
        """
        return self.priority == NotificationPriority.CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化/持久化）

        Returns:
            Dict: 通知对象的字典表示
        """
        return {
            'notification_id': self.notification_id,
            'notification_type': self.notification_type.value,
            'title': self.title,
            'content': self.content,
            'variables': self.variables,
            'recipients': [
                {
                    'recipient_type': r.recipient_type,
                    'recipient_id': r.recipient_id,
                    'mention': r.mention
                }
                for r in self.recipients
            ],
            'priority': self.priority.value,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'preferred_channels': self.preferred_channels,
            'fallback_enabled': self.fallback_enabled,
            'metadata': self.metadata,
            'error_message': self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Notification':
        """从字典创建通知对象（反序列化）

        Args:
            data: 字典数据

        Returns:
            Notification: 通知对象
        """
        # 转换枚举类型
        notification_type = NotificationType(data['notification_type'])
        priority = NotificationPriority(data['priority'])
        status = NotificationStatus(data['status'])

        # 转换接收者列表
        recipients = [
            NotificationRecipient(**r) for r in data.get('recipients', [])
        ]

        # 转换时间戳
        created_at = datetime.fromisoformat(data['created_at'])
        sent_at = datetime.fromisoformat(data['sent_at']) if data.get('sent_at') else None
        failed_at = datetime.fromisoformat(data['failed_at']) if data.get('failed_at') else None

        return cls(
            notification_id=data['notification_id'],
            notification_type=notification_type,
            title=data['title'],
            content=data['content'],
            variables=data.get('variables', {}),
            recipients=recipients,
            priority=priority,
            status=status,
            created_at=created_at,
            sent_at=sent_at,
            failed_at=failed_at,
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3),
            preferred_channels=data.get('preferred_channels', []),
            fallback_enabled=data.get('fallback_enabled', True),
            metadata=data.get('metadata', {}),
            error_message=data.get('error_message'),
        )

    def __repr__(self) -> str:
        return (
            f"Notification(id={self.notification_id[:8]}..., "
            f"type={self.notification_type.value}, "
            f"priority={self.priority.value}, "
            f"status={self.status.value})"
        )

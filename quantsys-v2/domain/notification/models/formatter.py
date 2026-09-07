"""
通知格式化器接口

定义通知格式化的统一契约，将领域模型 Notification 转换为
渠道特定的载荷格式（如飞书卡片、邮件 HTML 等）。

Author: System
Date: 2026-09-02
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .notification import Notification, NotificationType


class NotificationFormatter(ABC):
    """通知格式化器接口

    职责：
    1. 将 Notification 转换为渠道特定的格式
    2. 声明支持的通知类型
    3. 实现业务逻辑到展示逻辑的转换

    设计原则：
    - 一个格式化器负责一种通知类型
    - 格式化器包含业务展示逻辑（如止损显示为红色卡片）
    - 格式化器不应访问外部资源（数据库、API）

    子类实现：
    - WatchTriggeredFormatter: 盯盘触发通知
    - StopLossFormatter: 止损触发通知
    - DailyReportFormatter: 每日报告
    - ... 更多业务格式化器
    """

    @abstractmethod
    def format(self, notification: 'Notification') -> Dict[str, Any]:
        """格式化通知

        Args:
            notification: 通知对象

        Returns:
            Dict: 渠道特定的载荷格式

        Examples:
            >>> formatter = FeishuCardFormatter()
            >>> notification = Notification(
            ...     notification_type=NotificationType.STOP_LOSS,
            ...     title="止损触发",
            ...     content="000001 触发止损"
            ... )
            >>> payload = formatter.format(notification)
            >>> payload['msg_type']
            'interactive'
            >>> payload['card']['header']['template']
            'red'

        Raises:
            ValueError: 如果通知类型不支持
        """
        pass

    @abstractmethod
    def supports_type(self, notification_type: 'NotificationType') -> bool:
        """是否支持该类型通知

        Args:
            notification_type: 通知类型

        Returns:
            bool: 是否支持

        Examples:
            >>> formatter = StopLossFormatter()
            >>> formatter.supports_type(NotificationType.STOP_LOSS)
            True
            >>> formatter.supports_type(NotificationType.DAILY_REPORT)
            False
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"

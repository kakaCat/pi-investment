"""
通知渠道接口

定义通知发送的统一契约，所有渠道实现（Feishu, Agent, Email, SMS）
必须遵循此接口。

Author: System
Date: 2026-09-02
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .notification import Notification, NotificationType


class ChannelResult:
    """渠道发送结果

    封装通知发送的结果信息，包括：
    - 是否成功
    - 消息描述
    - 是否确认送达（区分超时场景）
    - 元数据（如 message_id, trace_id 等）

    Examples:
        >>> result = ChannelResult.ok("发送成功")
        >>> result.success
        True
        >>> result.delivered
        True

        >>> result = ChannelResult.timeout("请求超时")
        >>> result.success
        True  # 超时但可能已送达，标记为成功
        >>> result.delivered
        False  # 无法确认是否送达
    """

    def __init__(
        self,
        success: bool,
        message: str = "",
        delivered: bool = True,
        metadata: Dict[str, Any] = None
    ):
        """初始化渠道结果

        Args:
            success: 是否成功（True=成功/可能成功, False=明确失败）
            message: 结果描述信息
            delivered: 是否确认送达（超时场景可能未知）
            metadata: 额外元数据
        """
        self.success = success
        self.message = message
        self.delivered = delivered
        self.metadata = metadata or {}

    @staticmethod
    def ok(message: str = "发送成功", metadata: Dict[str, Any] = None) -> 'ChannelResult':
        """创建成功结果

        Args:
            message: 成功描述
            metadata: 额外元数据（如 message_id）

        Returns:
            ChannelResult: 成功结果对象
        """
        return ChannelResult(
            success=True,
            message=message,
            delivered=True,
            metadata=metadata or {}
        )

    @staticmethod
    def timeout(message: str = "发送超时（可能已送达）") -> 'ChannelResult':
        """创建超时结果

        说明：
        超时场景下，请求可能已送达服务端但响应未返回，
        因此标记为 success=True（避免重复发送），但 delivered=False（无法确认）

        Args:
            message: 超时描述

        Returns:
            ChannelResult: 超时结果对象
        """
        return ChannelResult(
            success=True,
            message=message,
            delivered=False
        )

    @staticmethod
    def error(message: str, metadata: Dict[str, Any] = None) -> 'ChannelResult':
        """创建失败结果

        Args:
            message: 失败原因
            metadata: 额外元数据（如 error_code）

        Returns:
            ChannelResult: 失败结果对象
        """
        return ChannelResult(
            success=False,
            message=message,
            delivered=False,
            metadata=metadata or {}
        )

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        delivered_str = f", delivered={self.delivered}" if self.success else ""
        return f"ChannelResult({status}: {self.message}{delivered_str})"

    def __bool__(self) -> bool:
        """支持布尔转换

        Returns:
            bool: success 值
        """
        return self.success


class NotificationChannel(ABC):
    """通知渠道接口

    定义通知发送的统一契约，所有渠道实现必须遵循：
    1. send() - 发送通知
    2. supports() - 声明支持的通知类型
    3. get_name() - 返回渠道名称
    4. healthcheck() - 健康检查

    子类实现：
    - FeishuChannel: 飞书 Webhook 通知
    - AgentChannel: Agent 唤醒通知
    - EmailChannel: 邮件通知
    - SmsChannel: 短信通知
    """

    @abstractmethod
    def send(self, notification: 'Notification') -> ChannelResult:
        """发送通知

        Args:
            notification: 通知对象

        Returns:
            ChannelResult: 发送结果

        Raises:
            不应该抛出异常，所有错误应封装在 ChannelResult 中返回
        """
        pass

    @abstractmethod
    def supports(self, notification_type: 'NotificationType') -> bool:
        """是否支持该类型通知

        Args:
            notification_type: 通知类型

        Returns:
            bool: 是否支持

        Examples:
            >>> channel = FeishuChannel(...)
            >>> channel.supports(NotificationType.DAILY_REPORT)
            True
            >>> channel.supports(NotificationType.AGENT_REMINDER)
            False
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """获取渠道名称

        Returns:
            str: 渠道名称（如 'feishu', 'agent', 'email'）

        说明：
        渠道名称用于：
        1. 日志记录
        2. 渠道选择策略
        3. 配置管理
        """
        pass

    @abstractmethod
    def healthcheck(self) -> bool:
        """健康检查

        Returns:
            bool: 渠道是否可用

        说明：
        健康检查用于：
        1. 启动时验证配置
        2. 运行时检测渠道可用性
        3. 降级决策依据

        注意：
        健康检查应该是轻量级的，避免长时间阻塞
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.get_name()})"

"""
通知领域服务

协调通知发送的核心流程：
1. 渠道选择（根据策略）
2. 通知发送（调用渠道）
3. 重试与降级（失败处理）
4. 生命周期管理

Author: System
Date: 2026-09-02
"""

import structlog
from typing import List, Dict, Optional

from domain.notification.models.notification import Notification, NotificationStatus
from domain.notification.models.channel import NotificationChannel, ChannelResult
from domain.notification.policies.notification_policy import NotificationPolicy

logger = structlog.get_logger(__name__)


class NotificationService:
    """通知领域服务

    职责：
    1. 协调通知发送流程（选择渠道、格式化、重试、降级）
    2. 执行通知策略（优先级路由、渠道选择）
    3. 管理通知生命周期
    4. 记录发送历史（可选）

    不负责：
    - 具体渠道的发送实现（委托给 Channel）
    - 通知格式化（委托给 Formatter）
    - 业务逻辑（由应用层负责）
    """

    def __init__(
        self,
        channels: List[NotificationChannel],
        policy: NotificationPolicy,
        repository: Optional['NotificationRepository'] = None
    ):
        """初始化通知服务

        Args:
            channels: 通知渠道列表
            policy: 通知策略
            repository: 通知仓储（可选，用于持久化）
        """
        self.channels = {ch.get_name(): ch for ch in channels}
        self.policy = policy
        self.repository = repository

        logger.info(
            "NotificationService initialized",
            channels=list(self.channels.keys())
        )

    def send(self, notification: Notification) -> ChannelResult:
        """发送通知（标准流程）

        流程：
        1. 标记为发送中
        2. 根据策略选择渠道
        3. 按优先级尝试发送
        4. 失败时重试或降级
        5. 记录历史

        Args:
            notification: 通知对象

        Returns:
            ChannelResult: 最终发送结果

        Examples:
            >>> service = NotificationService(channels=[...], policy=...)
            >>> notification = Notification(
            ...     notification_type=NotificationType.STOP_LOSS,
            ...     title="止损触发",
            ...     content="000001 触发止损"
            ... )
            >>> result = service.send(notification)
            >>> result.success
            True
        """
        logger.info(
            "发送通知",
            notification_id=notification.notification_id,
            type=notification.notification_type.value,
            priority=notification.priority.value
        )

        # 1. 标记为发送中
        try:
            notification.mark_sending()
        except ValueError as e:
            logger.warning(
                "通知状态异常，跳过发送",
                notification_id=notification.notification_id,
                status=notification.status.value,
                error=str(e)
            )
            return ChannelResult.error(f"通知状态异常: {str(e)}")

        if self.repository:
            self.repository.save(notification)

        # 2. 选择渠道
        selected_channels = self.policy.select_channels(notification, self.channels)

        if not selected_channels:
            error_msg = "没有可用的通知渠道"
            logger.error(error_msg, notification_id=notification.notification_id)
            notification.mark_failed(error_msg)
            if self.repository:
                self.repository.save(notification)
            return ChannelResult.error(error_msg)

        logger.debug(
            "已选择渠道",
            notification_id=notification.notification_id,
            channels=selected_channels
        )

        # 3. 按优先级尝试发送
        for channel_name in selected_channels:
            channel = self.channels.get(channel_name)
            if not channel:
                continue

            result = self._send_via_channel(notification, channel)

            if result.success:
                notification.mark_sent()
                if self.repository:
                    self.repository.save(notification)

                logger.info(
                    "通知发送成功",
                    notification_id=notification.notification_id,
                    channel=channel_name,
                    delivered=result.delivered
                )
                return result

            # 失败：标记错误并继续下一个渠道
            logger.warning(
                "渠道发送失败，尝试下一个",
                notification_id=notification.notification_id,
                channel=channel_name,
                error=result.message
            )
            notification.mark_failed(result.message)

        # 4. 所有渠道都失败
        if self.repository:
            self.repository.save(notification)

        logger.error(
            "所有渠道发送失败",
            notification_id=notification.notification_id,
            error=notification.error_message
        )

        return ChannelResult.error(f"所有渠道发送失败: {notification.error_message}")

    def send_with_fallback(
        self,
        notification: Notification,
        primary_channel: str,
        fallback_channel: str
    ) -> ChannelResult:
        """带降级的发送

        Args:
            notification: 通知对象
            primary_channel: 主渠道（如 'agent'）
            fallback_channel: 降级渠道（如 'feishu'）

        Returns:
            ChannelResult: 最终发送结果

        Examples:
            >>> # Agent 模式：优先 Agent，失败降级飞书
            >>> result = service.send_with_fallback(
            ...     notification,
            ...     primary_channel='agent',
            ...     fallback_channel='feishu'
            ... )
        """
        logger.info(
            "发送通知（带降级）",
            notification_id=notification.notification_id,
            primary=primary_channel,
            fallback=fallback_channel
        )

        # 尝试主渠道
        primary = self.channels.get(primary_channel)
        if primary:
            result = self._send_via_channel(notification, primary)
            if result.success:
                notification.mark_sent()
                if self.repository:
                    self.repository.save(notification)

                logger.info(
                    "主渠道发送成功",
                    notification_id=notification.notification_id,
                    channel=primary_channel
                )
                return result
            else:
                logger.warning(
                    "主渠道发送失败，降级到备用渠道",
                    notification_id=notification.notification_id,
                    primary=primary_channel,
                    fallback=fallback_channel,
                    error=result.message
                )

        # 降级到备用渠道
        fallback = self.channels.get(fallback_channel)
        if fallback:
            notification.mark_fallback()
            result = self._send_via_channel(notification, fallback)

            if self.repository:
                self.repository.save(notification)

            if result.success:
                logger.info(
                    "降级渠道发送成功",
                    notification_id=notification.notification_id,
                    channel=fallback_channel
                )
            else:
                logger.error(
                    "降级渠道也失败",
                    notification_id=notification.notification_id,
                    channel=fallback_channel,
                    error=result.message
                )

            return result

        error_msg = "主渠道和降级渠道均不可用"
        logger.error(
            error_msg,
            notification_id=notification.notification_id,
            primary=primary_channel,
            fallback=fallback_channel
        )
        return ChannelResult.error(error_msg)

    def _send_via_channel(
        self,
        notification: Notification,
        channel: NotificationChannel
    ) -> ChannelResult:
        """通过指定渠道发送

        Args:
            notification: 通知对象
            channel: 通知渠道

        Returns:
            ChannelResult: 发送结果
        """
        try:
            logger.debug(
                "通过渠道发送通知",
                notification_id=notification.notification_id,
                channel=channel.get_name()
            )

            result = channel.send(notification)

            logger.debug(
                "渠道发送完成",
                notification_id=notification.notification_id,
                channel=channel.get_name(),
                success=result.success,
                message=result.message
            )

            return result

        except Exception as e:
            logger.error(
                "渠道发送异常",
                notification_id=notification.notification_id,
                channel=channel.get_name(),
                error=str(e),
                exc_info=True
            )
            return ChannelResult.error(f"渠道异常: {str(e)}")

    def get_available_channels(self) -> List[str]:
        """获取所有可用渠道名称

        Returns:
            List[str]: 渠道名称列表
        """
        return list(self.channels.keys())

    def healthcheck_all(self) -> Dict[str, bool]:
        """检查所有渠道健康状态

        Returns:
            Dict[str, bool]: {channel_name: is_healthy}
        """
        results = {}
        for name, channel in self.channels.items():
            try:
                results[name] = channel.healthcheck()
            except Exception as e:
                logger.error(
                    "渠道健康检查异常",
                    channel=name,
                    error=str(e)
                )
                results[name] = False

        logger.info("渠道健康检查完成", results=results)
        return results

"""
飞书通知渠道实现

通过飞书 Webhook API 发送通知消息，支持：
1. 文本消息
2. 富文本卡片
3. 交互式卡片

Author: System
Date: 2026-09-02
"""

import requests
import structlog
from typing import List, Optional

from domain.notification.models.notification import Notification, NotificationType
from domain.notification.models.channel import NotificationChannel, ChannelResult
from domain.notification.models.formatter import NotificationFormatter

logger = structlog.get_logger(__name__)


class FeishuChannel(NotificationChannel):
    """飞书通知渠道

    职责：
    1. 实现飞书 Webhook API 调用
    2. 处理飞书特定的错误码
    3. 管理格式化器注册表
    4. 提供健康检查

    配置：
    - webhook_url: 飞书机器人 Webhook 地址
    - timeout: 请求超时时间（秒）
    """

    def __init__(
        self,
        webhook_url: str,
        formatters: List[NotificationFormatter],
        timeout: int = 10
    ):
        """初始化飞书渠道

        Args:
            webhook_url: 飞书 Webhook URL
            formatters: 格式化器列表
            timeout: 请求超时时间（秒）
        """
        self.webhook_url = webhook_url
        self.timeout = timeout

        # 构建格式化器映射表
        self.formatters: dict[str, NotificationFormatter] = {}
        for formatter in formatters:
            # 使用类名作为 key（可扩展为按通知类型映射）
            self.formatters[formatter.__class__.__name__] = formatter

        logger.info(
            "FeishuChannel initialized",
            webhook_configured=bool(webhook_url),
            formatters_count=len(self.formatters)
        )

    def send(self, notification: Notification) -> ChannelResult:
        """发送到飞书

        Args:
            notification: 通知对象

        Returns:
            ChannelResult: 发送结果
        """
        if not self.webhook_url:
            return ChannelResult.error("飞书 webhook 未配置")

        # 1. 选择格式化器
        formatter = self._select_formatter(notification)
        if not formatter:
            error_msg = f"不支持的通知类型: {notification.notification_type.value}"
            logger.warning(
                error_msg,
                notification_id=notification.notification_id,
                type=notification.notification_type.value
            )
            return ChannelResult.error(error_msg)

        # 2. 格式化载荷
        try:
            payload = formatter.format(notification)
            logger.debug(
                "通知格式化完成",
                notification_id=notification.notification_id,
                formatter=formatter.__class__.__name__
            )
        except Exception as e:
            error_msg = f"格式化失败: {str(e)}"
            logger.error(
                error_msg,
                notification_id=notification.notification_id,
                error=str(e),
                exc_info=True
            )
            return ChannelResult.error(error_msg)

        # 3. 发送 HTTP 请求
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            )

            result = response.json()

            # 飞书 API 返回 code=0 或 StatusCode=0 表示成功
            if result.get('code') == 0 or result.get('StatusCode') == 0:
                logger.info(
                    "飞书发送成功",
                    notification_id=notification.notification_id
                )
                return ChannelResult.ok(
                    message="飞书发送成功",
                    metadata={'response': result}
                )
            else:
                error_msg = f"飞书 API 错误: {result}"
                logger.error(
                    error_msg,
                    notification_id=notification.notification_id,
                    response=result
                )
                return ChannelResult.error(error_msg)

        except requests.exceptions.Timeout:
            logger.warning(
                "飞书请求超时",
                notification_id=notification.notification_id,
                timeout=self.timeout
            )
            return ChannelResult.timeout("飞书请求超时（可能已送达）")

        except requests.exceptions.ConnectionError as e:
            error_msg = f"飞书连接失败: {str(e)}"
            logger.error(
                error_msg,
                notification_id=notification.notification_id,
                error=str(e)
            )
            return ChannelResult.error(error_msg)

        except Exception as e:
            error_msg = f"飞书发送异常: {str(e)}"
            logger.error(
                error_msg,
                notification_id=notification.notification_id,
                error=str(e),
                exc_info=True
            )
            return ChannelResult.error(error_msg)

    def supports(self, notification_type: NotificationType) -> bool:
        """检查是否有对应的格式化器

        Args:
            notification_type: 通知类型

        Returns:
            bool: 是否支持
        """
        return any(
            fmt.supports_type(notification_type)
            for fmt in self.formatters.values()
        )

    def get_name(self) -> str:
        """获取渠道名称

        Returns:
            str: 'feishu'
        """
        return "feishu"

    def healthcheck(self) -> bool:
        """健康检查：检查 webhook 是否配置

        Returns:
            bool: webhook 已配置
        """
        is_healthy = bool(self.webhook_url)
        logger.debug(
            "FeishuChannel healthcheck",
            is_healthy=is_healthy,
            webhook_configured=bool(self.webhook_url)
        )
        return is_healthy

    def _select_formatter(
        self,
        notification: Notification
    ) -> Optional[NotificationFormatter]:
        """选择合适的格式化器

        Args:
            notification: 通知对象

        Returns:
            NotificationFormatter: 格式化器（如果找到）
        """
        for formatter in self.formatters.values():
            if formatter.supports_type(notification.notification_type):
                return formatter

        return None

    def register_formatter(self, formatter: NotificationFormatter) -> None:
        """注册格式化器

        Args:
            formatter: 格式化器对象
        """
        self.formatters[formatter.__class__.__name__] = formatter
        logger.info(
            "格式化器已注册",
            formatter=formatter.__class__.__name__
        )

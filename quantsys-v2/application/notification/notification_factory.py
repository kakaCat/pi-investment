"""
通知系统工厂

负责组装完整的通知系统：
1. 创建所有格式化器
2. 创建所有通知渠道
3. 创建通知策略
4. 组装领域服务
5. 构建应用门面

Author: System
Date: 2026-09-02
"""

import structlog
from typing import Optional

from infrastructure.config.settings import get_settings

# Domain
from domain.notification.models.channel import NotificationChannel
from domain.notification.services.notification_service import NotificationService
from domain.notification.policies.notification_policy import NotificationPolicy

# Infrastructure
from infrastructure.notification.channels.feishu_channel import FeishuChannel
from infrastructure.notification.channels.agent_channel import AgentChannel
from infrastructure.notification.formatters.feishu_formatters import (
    WatchTriggeredFormatter,
    StopLossFormatter,
    TakeProfitFormatter,
    DailyReportFormatter,
    WeeklyReportFormatter,
    MLTrainFormatter,
    SystemAlertFormatter,
)

# Application
from application.notification.notification_facade import NotificationFacade

logger = structlog.get_logger(__name__)


class NotificationFactory:
    """通知系统工厂

    职责：
    1. 根据配置创建通知系统各组件
    2. 组装依赖关系
    3. 提供单例访问

    使用场景：
    - 应用启动时创建通知系统
    - 测试时创建 mock 系统
    """

    _instance: Optional[NotificationFacade] = None

    @classmethod
    def create_from_settings(cls) -> NotificationFacade:
        """从配置创建通知门面

        Returns:
            NotificationFacade: 通知门面实例

        Examples:
            >>> facade = NotificationFactory.create_from_settings()
            >>> result = facade.send_text("测试通知")
        """
        settings = get_settings()

        logger.info("开始创建通知系统")

        # 1. 创建格式化器
        formatters = cls._create_formatters()
        logger.info(f"创建格式化器完成，数量: {len(formatters)}")

        # 2. 创建渠道
        channels = cls._create_channels(settings, formatters)
        logger.info(f"创建渠道完成，数量: {len(channels)}")

        # 3. 创建策略
        policy = cls._create_policy()
        logger.info("创建策略完成")

        # 4. 创建仓储（可选）
        repository = None  # 暂不实现持久化

        # 5. 创建领域服务
        service = NotificationService(
            channels=channels,
            policy=policy,
            repository=repository
        )
        logger.info("创建领域服务完成")

        # 6. 创建门面
        facade = NotificationFacade(service)
        logger.info("通知系统创建完成")

        # 健康检查
        health = facade.healthcheck()
        logger.info("通知渠道健康检查", health=health)

        return facade

    @classmethod
    def get_instance(cls) -> NotificationFacade:
        """获取单例

        Returns:
            NotificationFacade: 通知门面单例

        Examples:
            >>> facade = NotificationFactory.get_instance()
        """
        if cls._instance is None:
            cls._instance = cls.create_from_settings()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（用于测试）"""
        cls._instance = None
        logger.info("通知系统单例已重置")

    @staticmethod
    def _create_formatters() -> list:
        """创建所有格式化器

        Returns:
            list: 格式化器列表
        """
        return [
            WatchTriggeredFormatter(),
            StopLossFormatter(),
            TakeProfitFormatter(),
            DailyReportFormatter(),
            WeeklyReportFormatter(),
            MLTrainFormatter(),
            SystemAlertFormatter(),
        ]

    @staticmethod
    def _create_channels(settings, formatters: list) -> list[NotificationChannel]:
        """创建所有渠道

        Args:
            settings: 配置对象
            formatters: 格式化器列表

        Returns:
            list: 渠道列表
        """
        channels = []

        # 飞书渠道
        feishu_webhook = settings.external.feishu_webhook_url
        if feishu_webhook:
            feishu_channel = FeishuChannel(
                webhook_url=feishu_webhook,
                formatters=formatters,
                timeout=10
            )
            channels.append(feishu_channel)
            logger.info("飞书渠道已启用")
        else:
            logger.warning("飞书 webhook 未配置，飞书渠道未启用")

        # Agent 渠道
        if settings.scheduler.agent_os_enabled:
            agent_channel = AgentChannel(
                agent_url=settings.scheduler.agent_os_url,
                timeout=30,
                token=None  # 可扩展为从配置读取
            )
            channels.append(agent_channel)
            logger.info(
                "Agent 渠道已启用",
                agent_url=settings.scheduler.agent_os_url
            )
        else:
            logger.warning("Agent 渠道未启用")

        return channels

    @staticmethod
    def _create_policy() -> NotificationPolicy:
        """创建通知策略

        Returns:
            NotificationPolicy: 通知策略
        """
        policy = NotificationPolicy()

        # 可以在这里自定义策略
        # policy.customize_priority(NotificationType.DAILY_REPORT, ['email', 'feishu'])

        return policy

    @staticmethod
    def create_for_testing(
        feishu_webhook: str = None,
        agent_url: str = None
    ) -> NotificationFacade:
        """创建测试用通知系统

        Args:
            feishu_webhook: 飞书 Webhook（可选）
            agent_url: Agent URL（可选）

        Returns:
            NotificationFacade: 通知门面实例
        """
        formatters = NotificationFactory._create_formatters()

        channels = []
        if feishu_webhook:
            channels.append(FeishuChannel(feishu_webhook, formatters))
        if agent_url:
            channels.append(AgentChannel(agent_url))

        policy = NotificationPolicy()
        service = NotificationService(channels, policy)
        facade = NotificationFacade(service)

        logger.info("测试用通知系统创建完成", channels=len(channels))

        return facade


# 全局便捷函数

def get_notification_facade() -> NotificationFacade:
    """获取通知门面单例

    Returns:
        NotificationFacade: 通知门面

    Examples:
        >>> from application.notification.notification_factory import get_notification_facade
        >>> facade = get_notification_facade()
        >>> facade.send_text("测试通知")
    """
    return NotificationFactory.get_instance()

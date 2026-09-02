"""
通知策略

定义通知路由规则：
1. 根据通知类型/优先级选择合适的渠道
2. 定义渠道优先级顺序
3. 定义降级规则

Author: System
Date: 2026-09-02
"""

from typing import Dict, List
from domain.notification.models.notification import NotificationType, Notification
from domain.notification.models.channel import NotificationChannel


class NotificationPolicy:
    """通知策略

    职责：
    1. 根据通知类型、优先级选择合适的渠道
    2. 定义渠道优先级顺序
    3. 定义降级规则

    设计原则：
    - 策略是无状态的（可复用）
    - 策略只做决策，不执行发送
    - 策略可配置化（通过构造函数或配置文件）
    """

    def __init__(self):
        """初始化通知策略

        渠道优先级规则：
        - agent-os 作为飞书网关：所有通知优先通过 agent-os 发送
        - feishu 作为降级：agent-os 不可用时，v2 直接发送飞书
        - Agent 内部事件：仅走 agent-os（agent 提醒等）

        设计理念：
        agent-os 是统一的消息网关，负责：
        1. 智能分析和决策（是否需要发送）
        2. 格式化和增强（添加上下文、建议等）
        3. 统一发送到飞书
        """
        # 渠道优先级配置（按通知类型）
        # agent = agent-os 网关, feishu = v2 直接发送（降级）
        self.channel_priority: Dict[NotificationType, List[str]] = {
            # 交易相关 - 优先 agent-os，降级 feishu
            NotificationType.TRADE_SIGNAL: ['agent', 'feishu'],
            NotificationType.REBALANCE: ['agent', 'feishu'],
            NotificationType.VERIFICATION: ['agent', 'feishu'],

            # 风险相关 - 优先 agent-os，降级 feishu
            NotificationType.STOP_LOSS: ['agent', 'feishu'],
            NotificationType.TAKE_PROFIT: ['agent', 'feishu'],
            NotificationType.RISK_ALERT: ['agent', 'feishu'],

            # 盯盘触发 - 优先 agent-os（智能分析）
            NotificationType.WATCH_TRIGGERED: ['agent', 'feishu'],

            # 报告相关 - 优先 agent-os，降级 feishu
            NotificationType.DAILY_REPORT: ['agent', 'feishu'],
            NotificationType.WEEKLY_REPORT: ['agent', 'feishu'],
            NotificationType.PREMARKET_REPORT: ['agent', 'feishu'],

            # 系统相关 - 优先 agent-os，降级 feishu
            NotificationType.SYSTEM_ALERT: ['agent', 'feishu'],
            NotificationType.ML_TRAIN: ['agent', 'feishu'],

            # Agent 内部事件 - 仅 agent-os（不降级）
            NotificationType.AGENT_REMINDER: ['agent'],
            NotificationType.AGENT_REPORT: ['agent'],
        }

        # 默认优先级（未配置的类型）- agent-os 优先
        self.default_priority = ['agent', 'feishu']

    def select_channels(
        self,
        notification: Notification,
        available_channels: Dict[str, NotificationChannel]
    ) -> List[str]:
        """选择渠道

        Args:
            notification: 通知对象
            available_channels: 可用渠道字典 {name: channel}

        Returns:
            List[str]: 按优先级排序的渠道名称列表

        Examples:
            >>> policy = NotificationPolicy()
            >>> notification = Notification(
            ...     notification_type=NotificationType.STOP_LOSS
            ... )
            >>> channels = {'feishu': ..., 'agent': ...}
            >>> policy.select_channels(notification, channels)
            ['feishu', 'agent']
        """
        # 1. 如果通知指定了首选渠道，优先使用
        if notification.preferred_channels:
            return [
                ch for ch in notification.preferred_channels
                if ch in available_channels
            ]

        # 2. 根据通知类型选择
        priority = self.channel_priority.get(
            notification.notification_type,
            self.default_priority
        )

        # 3. 过滤掉不可用的渠道
        available = [ch for ch in priority if ch in available_channels]

        # 4. 进一步过滤：检查渠道是否支持该通知类型
        supported = [
            ch for ch in available
            if available_channels[ch].supports(notification.notification_type)
        ]

        return supported if supported else available

    def should_use_fallback(
        self,
        notification: Notification,
        primary_channel: str
    ) -> bool:
        """是否应该使用降级策略

        Args:
            notification: 通知对象
            primary_channel: 主渠道名称

        Returns:
            bool: 是否应该降级

        说明：
        降级策略判断依据：
        1. 通知对象启用了 fallback_enabled
        2. 主渠道不是最后选择（有备用渠道）
        3. 通知重试次数已达上限
        """
        if not notification.fallback_enabled:
            return False

        if not notification.should_fallback():
            return False

        return True

    def get_fallback_channel(
        self,
        notification: Notification,
        primary_channel: str,
        available_channels: Dict[str, NotificationChannel]
    ) -> str:
        """获取降级渠道

        Args:
            notification: 通知对象
            primary_channel: 主渠道名称
            available_channels: 可用渠道字典

        Returns:
            str: 降级渠道名称（如果没有则返回空字符串）

        说明：
        降级渠道选择逻辑：
        1. 获取该通知类型的渠道优先级列表
        2. 找到主渠道在列表中的位置
        3. 返回下一个可用渠道
        """
        channels = self.select_channels(notification, available_channels)

        try:
            primary_index = channels.index(primary_channel)
            # 返回下一个渠道（如果存在）
            if primary_index + 1 < len(channels):
                return channels[primary_index + 1]
        except ValueError:
            # 主渠道不在列表中，返回第一个可用渠道
            if channels:
                return channels[0]

        return ""

    def customize_priority(
        self,
        notification_type: NotificationType,
        channels: List[str]
    ) -> None:
        """自定义通知类型的渠道优先级

        Args:
            notification_type: 通知类型
            channels: 渠道优先级列表

        Examples:
            >>> policy = NotificationPolicy()
            >>> policy.customize_priority(
            ...     NotificationType.DAILY_REPORT,
            ...     ['email', 'feishu']
            ... )
        """
        self.channel_priority[notification_type] = channels

    def set_default_priority(self, channels: List[str]) -> None:
        """设置默认渠道优先级

        Args:
            channels: 渠道优先级列表
        """
        self.default_priority = channels

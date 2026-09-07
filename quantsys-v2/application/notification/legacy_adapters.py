"""
旧版通知服务适配器

提供向后兼容的接口，将旧版 API 调用转发到新的 DDD 通知系统。

迁移策略：
1. 保留旧版接口签名
2. 内部调用新版 NotificationFacade
3. 逐步迁移调用方到新版 API
4. 最终删除此适配器

Author: System
Date: 2026-09-02
"""

import structlog
from typing import Dict, Any, Optional
from application.notification.notification_factory import get_notification_facade

logger = structlog.get_logger(__name__)


class LegacyFeishuNotificationServiceAdapter:
    """旧版 FeishuNotificationService 适配器

    兼容旧版接口：
    - send_text()
    - send_card()
    - send_alert()
    - send_daily_report()
    - send_weekly_report()
    """

    def __init__(self):
        """初始化适配器"""
        self.facade = get_notification_facade()
        logger.info("LegacyFeishuNotificationServiceAdapter initialized")

    def send_text(
        self,
        text: str,
        mention_all: bool = False,
        mention_users: list = None
    ) -> bool:
        """发送文本消息（兼容旧版）

        Args:
            text: 消息内容
            mention_all: 是否 @所有人
            mention_users: 要 @的用户ID列表

        Returns:
            bool: 是否发送成功
        """
        logger.debug("Legacy send_text called", mention_all=mention_all)
        return self.facade.send_text(text, mention_all=mention_all)

    def send_card(
        self,
        title: str,
        content: str,
        urgency: str = "normal",
        actions: list = None,
        extra_elements: list = None
    ) -> bool:
        """发送卡片消息（兼容旧版）

        Args:
            title: 卡片标题
            content: 卡片内容
            urgency: 紧急程度
            actions: 操作按钮
            extra_elements: 额外元素（暂不支持）

        Returns:
            bool: 是否发送成功
        """
        logger.debug("Legacy send_card called", title=title, urgency=urgency)
        return self.facade.send_card(title, content, urgency, actions)

    def send_alert(
        self,
        alert_type: str,
        symbol: str,
        message: str,
        data: Dict[str, Any] = None,
        actions: list = None,
        mention: bool = False
    ) -> bool:
        """发送告警通知（兼容旧版）

        Args:
            alert_type: 告警类型
            symbol: 股票代码
            message: 告警消息
            data: 额外数据
            actions: 操作按钮（暂不支持）
            mention: 是否 @用户

        Returns:
            bool: 是否发送成功
        """
        logger.debug(
            "Legacy send_alert called",
            alert_type=alert_type,
            symbol=symbol
        )
        return self.facade.send_alert(alert_type, symbol, message, data, mention)

    def send_daily_report(self, report_data: Dict[str, Any]) -> bool:
        """发送每日报告（兼容旧版）

        Args:
            report_data: 报告数据

        Returns:
            bool: 是否发送成功
        """
        logger.debug("Legacy send_daily_report called")
        result = self.facade.send_daily_report(report_data)
        return result.success

    def send_weekly_report(self, report_data: Dict[str, Any]) -> bool:
        """发送每周报告（兼容旧版）

        Args:
            report_data: 周报数据

        Returns:
            bool: 是否发送成功
        """
        logger.debug("Legacy send_weekly_report called")
        result = self.facade.send_weekly_report(report_data)
        return result.success


class LegacyAgentNotificationServiceAdapter:
    """旧版 AgentNotificationService 适配器

    兼容旧版接口：
    - notify_agent()
    - notify_agent_detailed()
    - send_reminder()
    """

    def __init__(self):
        """初始化适配器"""
        self.facade = get_notification_facade()
        logger.info("LegacyAgentNotificationServiceAdapter initialized")

    def notify_agent(self, event: str, data: Dict[str, Any]) -> bool:
        """通知 Agent 处理事件（兼容旧版）

        Args:
            event: 事件类型
            data: 事件数据

        Returns:
            bool: 是否成功通知
        """
        result = self.notify_agent_detailed(event, data)
        return result == 'ok'

    def notify_agent_detailed(self, event: str, data: Dict[str, Any]) -> str:
        """通知 Agent 并返回详细结果（兼容旧版）

        Args:
            event: 事件类型
            data: 事件数据

        Returns:
            str: 'ok' | 'timeout' | 'error' | 'disabled'
        """
        logger.debug("Legacy notify_agent_detailed called", event=event)

        # 检查 Agent 渠道是否可用
        channels = self.facade.get_available_channels()
        if 'agent' not in channels:
            logger.warning("Agent 渠道不可用")
            return 'disabled'

        # 使用新版 API 发送
        # 注意：这里简化处理，实际应该根据 event 映射到具体的通知类型
        result = self.facade.send_agent_reminder(
            agent_id='default',
            message=data.get('message', ''),
            remind_at=data.get('timestamp')
        )

        # 映射结果
        if result.success:
            if result.delivered:
                return 'ok'
            else:
                return 'timeout'
        else:
            return 'error'

    def send_reminder(
        self,
        agent_id: str,
        message: str,
        remind_at: Optional[str] = None
    ) -> bool:
        """发送提醒事件给 Agent（兼容旧版）

        Args:
            agent_id: Agent ID
            message: 提醒消息
            remind_at: 提醒时间

        Returns:
            bool: 是否成功通知
        """
        logger.debug("Legacy send_reminder called", agent_id=agent_id)
        result = self.facade.send_agent_reminder(agent_id, message, remind_at)
        return result.success


# 全局单例（用于替换旧版服务）

_feishu_service_instance: Optional[LegacyFeishuNotificationServiceAdapter] = None
_agent_service_instance: Optional[LegacyAgentNotificationServiceAdapter] = None


def get_legacy_feishu_service() -> LegacyFeishuNotificationServiceAdapter:
    """获取旧版飞书服务适配器单例

    Returns:
        LegacyFeishuNotificationServiceAdapter: 适配器实例
    """
    global _feishu_service_instance
    if _feishu_service_instance is None:
        _feishu_service_instance = LegacyFeishuNotificationServiceAdapter()
    return _feishu_service_instance


def get_legacy_agent_service() -> LegacyAgentNotificationServiceAdapter:
    """获取旧版 Agent 服务适配器单例

    Returns:
        LegacyAgentNotificationServiceAdapter: 适配器实例
    """
    global _agent_service_instance
    if _agent_service_instance is None:
        _agent_service_instance = LegacyAgentNotificationServiceAdapter()
    return _agent_service_instance

"""
通知门面（Facade）

提供简化的业务层 API，隐藏领域模型复杂性，提供常用通知场景的便捷方法。

Author: System
Date: 2026-09-02
"""

import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from domain.notification.models.notification import (
    Notification,
    NotificationType,
    NotificationPriority,
)
from domain.notification.models.channel import ChannelResult
from domain.notification.services.notification_service import NotificationService

logger = structlog.get_logger(__name__)


class NotificationFacade:
    """通知门面

    职责：
    1. 提供简化的业务层 API
    2. 隐藏领域模型复杂性
    3. 提供常用通知场景的便捷方法
    4. 向后兼容旧版接口

    使用场景：
    - 业务代码只需调用 facade 方法，无需了解领域模型细节
    - 统一的入口便于日志记录、监控、审计
    """

    def __init__(self, notification_service: NotificationService):
        """初始化通知门面

        Args:
            notification_service: 通知领域服务
        """
        self.service = notification_service
        logger.info("NotificationFacade initialized")

    # ==================== 盯盘相关 ====================

    def send_watch_triggered(
        self,
        symbol: str,
        name: str,
        price: float,
        condition: dict,
        message: str,
        context: str = None,
        notify_mode: str = 'direct',
        mode_tag: str = None,
        change_pct: float = None,
        pnl_pct: float = None
    ) -> ChannelResult:
        """发送盯盘触发通知

        Args:
            symbol: 股票代码
            name: 股票名称
            price: 触发价格
            condition: 触发条件
            message: 触发消息
            context: 操作预案（可选）
            notify_mode: 通知模式 'direct' | 'agent'
            mode_tag: 模式标签（可选，自动推断）
            change_pct: 涨跌幅（可选）
            pnl_pct: 盈亏比例（可选）

        Returns:
            ChannelResult: 发送结果
        """
        notification = Notification(
            notification_type=NotificationType.WATCH_TRIGGERED,
            title=f"盯盘触发 - {symbol}",
            content=message,
            variables={
                'symbol': symbol,
                'name': name,
                'price': price,
                'change_pct': change_pct,
                'pnl_pct': pnl_pct,
                'condition': condition,
                'context': context,
                'notify_mode': notify_mode,
                'mode_tag': mode_tag or (
                    'AI 分析版' if notify_mode == 'agent' else '直发提醒'
                ),
            },
            priority=NotificationPriority.HIGH
        )

        # 根据模式选择发送策略
        if notify_mode == 'agent':
            # Agent 模式：优先 Agent，失败降级飞书
            return self.service.send_with_fallback(notification, 'agent', 'feishu')
        else:
            # Direct 模式：直接飞书
            notification.preferred_channels = ['feishu']
            return self.service.send(notification)

    # ==================== 风险相关 ====================

    def send_stop_loss_alert(
        self,
        symbol: str,
        price: float,
        stop_loss_pct: float,
        loss_pct: float,
        message: str
    ) -> ChannelResult:
        """发送止损触发告警

        Args:
            symbol: 股票代码
            price: 触发价格
            stop_loss_pct: 止损阈值
            loss_pct: 当前亏损比例
            message: 告警消息

        Returns:
            ChannelResult: 发送结果
        """
        notification = Notification(
            notification_type=NotificationType.STOP_LOSS,
            title=f"止损触发 - {symbol}",
            content=message,
            variables={
                'symbol': symbol,
                'price': price,
                'stop_loss_pct': stop_loss_pct,
                'loss_pct': loss_pct,
            },
            priority=NotificationPriority.CRITICAL,
            preferred_channels=['feishu']  # 止损优先飞书
        )
        return self.service.send(notification)

    def send_take_profit_alert(
        self,
        symbol: str,
        price: float,
        take_profit_pct: float,
        profit_pct: float,
        message: str
    ) -> ChannelResult:
        """发送止盈触发告警

        Args:
            symbol: 股票代码
            price: 触发价格
            take_profit_pct: 止盈阈值
            profit_pct: 当前盈利比例
            message: 告警消息

        Returns:
            ChannelResult: 发送结果
        """
        notification = Notification(
            notification_type=NotificationType.TAKE_PROFIT,
            title=f"止盈触发 - {symbol}",
            content=message,
            variables={
                'symbol': symbol,
                'price': price,
                'take_profit_pct': take_profit_pct,
                'profit_pct': profit_pct,
            },
            priority=NotificationPriority.HIGH,
            preferred_channels=['feishu']
        )
        return self.service.send(notification)

    # ==================== 报告相关 ====================

    def send_daily_report(self, report_data: Dict[str, Any]) -> ChannelResult:
        """发送每日报告

        Args:
            report_data: 报告数据字典
                - date: 日期
                - sh_index_change: 上证指数涨跌
                - sz_index_change: 深证成指涨跌
                - north_flow: 北向资金
                - daily_pnl: 今日收益
                - total_return: 总收益率
                - position_count: 持仓数量
                - new_signals: 新增信号数
                - opportunities: 优质机会数
                - risk_alerts: 风险提示列表（可选）
                - detail_url: 详情链接（可选）

        Returns:
            ChannelResult: 发送结果
        """
        notification = Notification(
            notification_type=NotificationType.DAILY_REPORT,
            title=f"每日投资报告 - {report_data.get('date', '')}",
            content="",
            variables=report_data,
            priority=NotificationPriority.NORMAL,
            preferred_channels=['feishu']
        )
        return self.service.send(notification)

    def send_weekly_report(self, report_data: Dict[str, Any]) -> ChannelResult:
        """发送每周报告

        Args:
            report_data: 周报数据字典
                - week: 周数
                - weekly_return: 周收益率
                - max_drawdown: 最大回撤
                - win_rate: 交易胜率
                - cumulative_return: 累计收益
                - strategies: 策略表现列表
                - outlook: 展望字典
                - detail_url: 详情链接（可选）

        Returns:
            ChannelResult: 发送结果
        """
        notification = Notification(
            notification_type=NotificationType.WEEKLY_REPORT,
            title=f"投资周报 - 第{report_data.get('week', 'N/A')}周",
            content="",
            variables=report_data,
            priority=NotificationPriority.NORMAL,
            preferred_channels=['feishu']
        )
        return self.service.send(notification)

    # ==================== 模型训练相关 ====================

    def send_ml_train_notification(self, result: Dict[str, Any]) -> ChannelResult:
        """发送模型训练通知

        Args:
            result: 训练结果字典
                - status: 状态 'success' | 'failed' | 'skipped'
                - version: 模型版本（成功时）
                - train_accuracy: 训练准确率（成功时）
                - test_accuracy: 测试准确率（成功时）
                - symbols_trained: 训练样本数（成功时）
                - auto_switched: 是否自动切换（成功时）
                - error: 错误信息（失败时）
                - reason: 跳过原因（跳过时）
                - timestamp: 时间戳

        Returns:
            ChannelResult: 发送结果
        """
        status = result.get('status', 'unknown')

        if status == 'success':
            title = "✅ 模型训练成功"
            priority = NotificationPriority.NORMAL
        elif status == 'failed':
            title = "❌ 模型训练失败"
            priority = NotificationPriority.HIGH
        else:
            title = "⊙ 模型训练跳过"
            priority = NotificationPriority.LOW

        notification = Notification(
            notification_type=NotificationType.ML_TRAIN,
            title=title,
            content="",
            variables=result,
            priority=priority,
            preferred_channels=['feishu']
        )
        return self.service.send(notification)

    # ==================== Agent 相关 ====================

    def send_agent_reminder(
        self,
        agent_id: str,
        message: str,
        remind_at: str = None
    ) -> ChannelResult:
        """发送 Agent 提醒

        Args:
            agent_id: Agent ID
            message: 提醒消息
            remind_at: 提醒时间（可选）

        Returns:
            ChannelResult: 发送结果
        """
        notification = Notification(
            notification_type=NotificationType.AGENT_REMINDER,
            title="Agent 提醒",
            content=message,
            variables={
                'agent_id': agent_id,
                'remind_at': remind_at,
            },
            priority=NotificationPriority.NORMAL,
            preferred_channels=['agent']  # 仅发送到 Agent
        )
        return self.service.send(notification)

    # ==================== 通用方法（兼容旧版接口）====================

    def send_text(
        self,
        text: str,
        priority: str = 'normal',
        mention_all: bool = False
    ) -> bool:
        """发送纯文本通知（兼容旧版接口）

        Args:
            text: 文本内容
            priority: 优先级 'low' | 'normal' | 'high' | 'critical'
            mention_all: 是否 @所有人

        Returns:
            bool: 是否发送成功
        """
        try:
            priority_enum = NotificationPriority[priority.upper()]
        except KeyError:
            priority_enum = NotificationPriority.NORMAL

        notification = Notification(
            notification_type=NotificationType.SYSTEM_ALERT,
            title="系统通知",
            content=text,
            variables={'mention_all': mention_all},
            priority=priority_enum,
            preferred_channels=['feishu']
        )

        result = self.service.send(notification)
        return result.success

    def send_card(
        self,
        title: str,
        content: str,
        urgency: str = 'normal',
        actions: List[Dict] = None
    ) -> bool:
        """发送卡片通知（兼容旧版接口）

        Args:
            title: 卡片标题
            content: 卡片内容
            urgency: 紧急程度 'normal' | 'high' | 'critical'
            actions: 操作按钮列表

        Returns:
            bool: 是否发送成功
        """
        try:
            priority_enum = NotificationPriority[urgency.upper()]
        except KeyError:
            priority_enum = NotificationPriority.NORMAL

        notification = Notification(
            notification_type=NotificationType.SYSTEM_ALERT,
            title=title,
            content=content,
            variables={'actions': actions or []},
            priority=priority_enum,
            preferred_channels=['feishu']
        )

        result = self.service.send(notification)
        return result.success

    def send_alert(
        self,
        alert_type: str,
        symbol: str,
        message: str,
        data: Dict[str, Any] = None,
        mention: bool = False
    ) -> bool:
        """发送告警通知（兼容旧版接口）

        Args:
            alert_type: 告警类型 'stop_loss' | 'take_profit' | 'signal' | 'risk'
            symbol: 股票代码
            message: 告警消息
            data: 额外数据
            mention: 是否 @用户

        Returns:
            bool: 是否发送成功
        """
        # 映射告警类型到通知类型
        type_mapping = {
            'stop_loss': NotificationType.STOP_LOSS,
            'take_profit': NotificationType.TAKE_PROFIT,
            'signal': NotificationType.TRADE_SIGNAL,
            'risk': NotificationType.RISK_ALERT,
        }

        notification_type = type_mapping.get(
            alert_type,
            NotificationType.SYSTEM_ALERT
        )

        notification = Notification(
            notification_type=notification_type,
            title=f"{alert_type.upper()} - {symbol}",
            content=message,
            variables=data or {},
            priority=NotificationPriority.HIGH,
            preferred_channels=['feishu']
        )

        result = self.service.send(notification)
        return result.success

    # ==================== 诊断方法 ====================

    def get_available_channels(self) -> List[str]:
        """获取所有可用渠道

        Returns:
            List[str]: 渠道名称列表
        """
        return self.service.get_available_channels()

    def healthcheck(self) -> Dict[str, bool]:
        """检查所有渠道健康状态

        Returns:
            Dict[str, bool]: {channel_name: is_healthy}
        """
        return self.service.healthcheck_all()

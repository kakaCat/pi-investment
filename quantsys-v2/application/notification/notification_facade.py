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
        pnl_pct: float = None,
        trigger_level: str = None,      # ← 新增：L0/L1/L2
        action_hint: dict = None,       # ← 新增：行动指引
        escalation_reason: str = None,  # ← 新增：升级原因
        decision_audit_id: str = None,  # ← 新增：审计ID
        intent: str = None,             # ← REQ-f08def P8：规则意图（消息主体）
        lifecycle_stage: str = None,    # ← 阶段
        next_action_hint: str = None,   # ← 触发后该做什么
        account: str = None,            # ← 归属账户
        scope: str = None,              # ← market/sector/symbol/position（P8 路由）
        action_amount_yuan: float = None,   # ← 动作影响金额（P8：≥账户5% → 风控频道）
        target_agent: str = None,       # ← 处置该事件的 agent（按分类投递，见 WatchDeliveryPolicy）
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
        # P8：路由决策交给**通知域策略**（盯盘只声明语义，不关心发到哪个群）
        from domain.notification.policies.watch_channel_policy import WatchChannelPolicy
        watch_channel = WatchChannelPolicy().resolve(
            intent=intent, scope=scope,
            is_constitutional=(intent == 'exit_stop'),
            action_amount_yuan=action_amount_yuan,
        )
        # 处置 agent（谁接手）是**独立维度**：按账户归属解析，绝不从消息频道推导（2026-09-11 用户定调）
        from domain.notification.policies.watch_delivery_policy import WatchDeliveryPolicy
        target_agent = target_agent or WatchDeliveryPolicy().resolve(account=account)

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
                # 新增：分层相关
                'trigger_level': trigger_level,
                'action_hint': action_hint,
                'escalation_reason': escalation_reason,
                'decision_audit_id': decision_audit_id,
                # REQ-f08def P8：消息必须让用户一眼看清"主体是谁、为什么提醒"
                'intent': intent,
                'lifecycle_stage': lifecycle_stage,
                'next_action_hint': next_action_hint,
                'account': account,
                'scope': scope,
                'action_amount_yuan': action_amount_yuan,
                'watch_channel': watch_channel,
                # 处置 agent：投递层（AgentNotificationService）据此选择 wake 端点
                'target_agent': target_agent,
                # os_channel 是 agent 网关的既有覆盖点：逻辑频道码写入此处即完成路由
                'os_channel': watch_channel,
            },
            priority=NotificationPriority.HIGH if trigger_level == 'L2' else NotificationPriority.NORMAL
        )

        # 根据模式选择发送策略
        # L2 行动层：强制走 agent（即使 notify_mode=direct 也强制 agent）
        if trigger_level == 'L2' or notify_mode == 'agent':
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
            priority=NotificationPriority.CRITICAL
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
        )

        result = self.service.send(notification)
        return result.success

    # ============ 策略/风控（原 utils/feishu_notifier 直连实现的收敛点） ============

    def send_rebalance_notification(self, report_data: Dict[str, Any]) -> ChannelResult:
        """发送调仓通知（REBALANCE）

        2026-09-11（w-23c70356）：`utils/feishu_notifier.py`（自行 requests.post
        飞书 webhook 的旁路实现）已删除，策略层调仓通知统一收敛到门面。

        Args:
            report_data: {date, positions, top_stocks:[(symbol,score,weight,reason)],
                          buy_trades:[(symbol,qty,price)], sell_trades:[...]}
        """
        date = report_data.get('date') or ''
        lines = [
            f"**日期**：{date or '-'}",
            f"**持仓数**：{report_data.get('positions', '-')}",
        ]

        buy_trades = report_data.get('buy_trades') or []
        sell_trades = report_data.get('sell_trades') or []
        if buy_trades:
            lines.append('')
            lines.append('**买入**')
            lines.extend(f"- {s} {q}股 @ {p}" for s, q, p in buy_trades)
        if sell_trades:
            lines.append('')
            lines.append('**卖出**')
            lines.extend(f"- {s} {q}股 @ {p}" for s, q, p in sell_trades)

        top_stocks = report_data.get('top_stocks') or []
        if top_stocks:
            lines.append('')
            lines.append('**候选标的**')
            for item in top_stocks[:8]:
                try:
                    symbol, score, weight, reason = item
                    lines.append(f"- {symbol} 评分 {score} 权重 {weight} {reason or ''}".rstrip())
                except (TypeError, ValueError):
                    lines.append(f"- {item}")

        notification = Notification(
            notification_type=NotificationType.REBALANCE,
            title=f"🔁 调仓通知 {date}".rstrip(),
            content='\n'.join(lines),
            variables={'date': date},
            priority=NotificationPriority.NORMAL,
        )
        return self.service.send(notification)

    def send_risk_alert(self, report_data: Dict[str, Any]) -> ChannelResult:
        """发送盘中风险告警（RISK_ALERT）

        2026-09-11（w-23c70356）：同 send_rebalance_notification，原直连实现已收敛。

        Args:
            report_data: {trigger: 触发原因, losing_stocks: [symbol, ...]}
        """
        losing = report_data.get('losing_stocks') or []
        content = f"**触发原因**：{report_data.get('trigger', '-')}"
        if losing:
            content += '\n\n**涉及标的**：' + '、'.join(str(s) for s in losing)

        notification = Notification(
            notification_type=NotificationType.RISK_ALERT,
            title='🚨 盘中风控告警',
            content=content,
            variables={'trigger': report_data.get('trigger')},
            priority=NotificationPriority.HIGH,
        )
        return self.service.send(notification)

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

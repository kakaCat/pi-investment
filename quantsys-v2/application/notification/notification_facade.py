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
    NotificationStatus,
)
from domain.notification.models.channel import ChannelResult
from domain.notification.services.notification_service import NotificationService

logger = structlog.get_logger(__name__)


# ── target_agent 的传输能力（REQ-c9f899 t9 取证 + 返工项 A 复核，2026-09-18）────
# facade 按账户算出 target_agent（WatchDeliveryPolicy.resolve），而**通用通知渠道层没有
# per-agent 字段**，无法把消息投给指定 agent —— 取证：
#   · AgentChannel 只把 variables["os_channel"] 当 Agent OS 通知网关的 channel 字段
#     （infrastructure/notification/channels/agent_channel.py:100-105）；
#   · 网关请求体 SendRequest 只有 channel/title/content/color/urgency/metadata，无目标 agent
#     （agent-os/internal/domain/notification.go:48-55）；
#   · FeishuChannel 完全忽略 target_agent（目标只是发到某个飞书群）。
# 真实的目标 agent 路由存在于 AgentNotificationService.resolve_target_url
# （POST {url}/wake，application/services/agent_notification_service.py:121-130）。
# 处置（返工项 A）：L2 行动层改走该 wake 通道实现按 target 投递（见下方
# TARGET_AGENT_TRANSPORT_WAKE）；L0/L1 与 notify_mode=agent 的旧路径行为不变，
# 其 target_agent 仍只作文本/元数据承载，返回 metadata 里如实标 unsupported。
TARGET_AGENT_TRANSPORT = "unsupported_in_notification_channel"
TARGET_AGENT_TRANSPORT_REASON = (
    "通用通知渠道层仍不支持按 agent 路由（适用于 L0/L1 直发与 notify_mode=agent 的旧路径）："
    "AgentChannel 只认 variables[os_channel]，Agent OS 网关 SendRequest 无 per-agent 字段"
    "（agent-os/internal/domain/notification.go:48），FeishuChannel 忽略 target_agent。"
    "TODO：若要这两条路径也按 target 路由，需给 Agent OS 网关加 target 字段后在 AgentChannel 接线。"
    "（L2 行动层已改走 wake 通道，见下方 TARGET_AGENT_TRANSPORT_WAKE）"
)

# ── L2 行动层：target_agent 的真实路由通道（REQ-c9f899 返工项 A，2026-09-18）──────────
# 复核结论：通用通知渠道层确实无法按 agent 投递（见上），但 **wake 通道可以**——
# AgentNotificationService.resolve_target_url(target) 把 agent 键映射到落点，
# 再 POST {url}/wake（协议 {event,data,timestamp}；agent-dh :13080 的 /wake 已实现并投递到
# investor 窗口，见 agent-dh/packages/lifecycle/src/wake-webhook.ts；agent-ts :3002 同协议）。
# 因此 L2（行动层，需 agent 参与处置）优先走 wake；L0/L1 直发路径行为不变。
#
# 注入纪律：本方法**不直接创建 HTTP 客户端**——wake 实现由 NotificationFactory 注入的
# AgentNotificationService 单例提供（或单测注入假实现）。未注入 = 不做 wake（保持改造前
# 行为，同时保证测试进程绝不误唤真实 agent）。
WAKE_EVENT_WATCH_L2 = "watch_triggered"
TARGET_AGENT_TRANSPORT_WAKE = "agent_wake"
TARGET_AGENT_TRANSPORT_WAKE_FALLBACK = "feishu_fallback"
#: wake 送达判定：只有 'ok' 视为送达。'timeout' 的服务端语义是「大概率已送达但无法确认」，
#: 而盯盘告警「漏发比重复更严重」→ timeout 一律降级飞书（与 digest_service 把 timeout
#: 当失败、下轮重试的既有口径一致），并在响应 metadata 如实标注 wake_status。
WAKE_DELIVERED_STATUSES = ("ok",)


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

    def __init__(self, notification_service: NotificationService,
                 agent_notification_service=None):
        """初始化通知门面

        Args:
            notification_service: 通知领域服务
            agent_notification_service: AgentNotificationService（wake 通道，L2 目标路由用）。
                由 NotificationFactory 注入生产单例；**未注入 = L2 不做 wake**，退回既有
                agent→feishu 链路（保持改造前行为，同时保证测试进程绝不误唤真实 agent）。
        """
        self.service = notification_service
        self._agent_notification_service = agent_notification_service
        logger.info("NotificationFacade initialized")

    @property
    def agent_notification_service(self):
        """wake 通道实现（可为 None = 未装配；生产由 factory 注入）"""
        return self._agent_notification_service

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
        account_total_yuan: float = None,   # ← 账户总资产（金额门取数；缺失=门关闭，保持原行为）
        level: str = None,                  # ← 级别 P0..P3（REQ-c9f899 t12：渠道据此选按级别模板）
        rule_id: int = None,                # ← 规则号（REQ-ad0a FR-10：模板显示真实号；缺失=手工）
        todo_id: str = None,                # ← 关联待办 id（L2 wake 载荷上下文，可选）
        todo: dict = None,                  # ← 关联待办快照（L2 wake 载荷上下文，可选）
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
            account_total_yuan: 账户总资产（元，可选）。金额门（单笔动作影响金额 ≥ 5%）
                据此判定；**缺失时金额门关闭且不抛错**（保持修复前行为，不阻断路由）

        Returns:
            ChannelResult: 发送结果（metadata 内含 wake_target 与传输能力报告）
        """
        # P8：路由决策交给**通知域策略**（盯盘只声明语义，不关心发到哪个群）
        from domain.notification.policies.watch_channel_policy import WatchChannelPolicy
        # REQ-c9f899 t9 金额门死代码修复：此前用无参构造 → account_total_yuan 恒为 None，
        # 金额门从未生效。这里把调用方给的账户总资产注入策略（缺失=None=门关闭，行为不变）。
        watch_channel = WatchChannelPolicy(
            account_total_yuan=account_total_yuan,
        ).resolve(
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
                # REQ-c9f899 t12：级别随通知下发；有值 → FeishuChannel 走按级别模板
                # （watch_level_templates），无值 → 旧 WatchTriggeredFormatter（兼容，不破坏非分级通知）
                'watch_level': level,
                'rule_id': rule_id,
                'watch_channel': watch_channel,
                # 处置 agent：投递层（AgentNotificationService）据此选择 wake 端点
                'target_agent': target_agent,
                # os_channel 是 agent 网关的既有覆盖点：逻辑频道码写入此处即完成路由
                'os_channel': watch_channel,
            },
            priority=NotificationPriority.HIGH if trigger_level == 'L2' else NotificationPriority.NORMAL,
            # target_agent 的规范落点（渠道无关）：渠道层当前不支持它，见 _annotate_target_agent
            metadata={'wake_target': target_agent} if target_agent else {},
        )

        # 根据模式选择发送策略
        # L2 行动层（REQ-c9f899 返工项 A）：优先经 wake 通道投递到 target_agent；
        # 未装配或投递失败 → 降级飞书，并在响应 metadata 如实标注（不静默说成功）。
        # 注意：L2 与 notify_mode 解耦（即使 notify_mode=direct 也走 L2 分支）。
        if trigger_level == 'L2':
            return self._send_l2_via_target_agent(
                notification=notification,
                target_agent=target_agent,
                symbol=symbol,
                name=name,
                price=price,
                condition=condition,
                message=message,
                context=context,
                notify_mode=notify_mode,
                change_pct=change_pct,
                pnl_pct=pnl_pct,
                action_hint=action_hint,
                escalation_reason=escalation_reason,
                decision_audit_id=decision_audit_id,
                intent=intent,
                lifecycle_stage=lifecycle_stage,
                next_action_hint=next_action_hint,
                account=account,
                scope=scope,
                action_amount_yuan=action_amount_yuan,
                watch_channel=watch_channel,
                level=level,
                todo_id=todo_id,
                todo=todo,
            )

        # 非 L2：agent 优先、飞书降级（REQ-260924104605-ad0a FR-2 方案 A）。
        # direct 与 agent 两种 notify_mode 统一走「agent→feishu」：os_channel 逻辑频道码
        # 经 AgentChannel 路由到盯盘群（10 个盯盘频道 → 专用 webhook，FR-1 已配置）；
        # Agent OS 不可达时降级直飞书兜底（不丢消息），并在 metadata 如实标注降级。
        result = self.service.send_with_fallback(notification, 'agent', 'feishu')
        if notification.status == NotificationStatus.FALLBACK:
            result.metadata = {
                **(result.metadata or {}),
                'degraded': True,
                'degraded_reason': 'agent_os_unreachable',
                'delivery': 'feishu_fallback',
            }
        return self._annotate_target_agent(result, target_agent)

    def _send_l2_via_target_agent(self, notification, target_agent, *, symbol, name,
                                  price, condition, message, context, notify_mode,
                                  change_pct, pnl_pct, action_hint, escalation_reason,
                                  decision_audit_id, intent, lifecycle_stage,
                                  next_action_hint, account, scope, action_amount_yuan,
                                  watch_channel, level, todo_id, todo):
        """L2 行动层：经 wake 通道把触发投给 target_agent（REQ-c9f899 返工项 A）。

        成功（wake 返回 'ok'）→ 直接返回，不动通用渠道层；
        未装配 wake 通道 / 投递失败（error/timeout/disabled/skipped）→ 降级飞书，
        并在 ChannelResult.metadata 写明 wake_target_transport=feishu_fallback、wake_status、
        wake_degraded=True——**绝不在响应里假装 wake 成功**。
        """
        service = self._agent_notification_service
        if service is None:
            # wake 通道未装配：保持改造前行为（agent→feishu），并如实标注未配置
            logger.warning('L2 未装配 wake 通道，退回既有 agent→feishu 链路',
                           symbol=symbol, target_agent=target_agent)
            result = self.service.send_with_fallback(notification, 'agent', 'feishu')
            return self._annotate_wake_degraded(
                result, target_agent,
                transport=TARGET_AGENT_TRANSPORT,
                status='not_configured', detail=None, fallback='agent>feishu')

        wake_data = {
            'symbol': symbol,
            'name': name,
            'price': price,
            'condition': condition,
            'message': message,
            'context': context,
            'trigger_level': 'L2',
            'notify_mode': notify_mode,
            'change_pct': change_pct,
            'pnl_pct': pnl_pct,
            'action_hint': action_hint,
            'escalation_reason': escalation_reason,
            'decision_audit_id': decision_audit_id,
            'intent': intent,
            'lifecycle_stage': lifecycle_stage,
            'next_action_hint': next_action_hint,
            'account': account,
            'scope': scope,
            'action_amount_yuan': action_amount_yuan,
            'level': level,
            'watch_channel': watch_channel,
            # target 同时进 payload（可观测/可核验）与实际落点（resolve_target_url 决定 URL）
            'target_agent': target_agent,
            'instruction': (
                'L2 盯盘触发需处置（行动层）：按账户授权处置该标的触发'
                '（agent 自有账户可自决，用户账户只出建议）；'
                '下单遵守交易宪法与 R-001/R-002，动作留 decision 审计；'
                '若判不动，写明理由与下次触发的条件（NEXT）。'
            ),
        }
        if todo_id is not None:
            wake_data['todo_id'] = todo_id
        if todo is not None:
            wake_data['todo'] = todo

        status, detail = self._attempt_wake(service, target_agent, wake_data)

        if status in WAKE_DELIVERED_STATUSES:
            logger.info('L2 目标路由：已唤醒处置 agent',
                        target_agent=target_agent, symbol=symbol,
                        wake_event=WAKE_EVENT_WATCH_L2)
            result = ChannelResult.ok(
                message=f'L2 已唤醒 {target_agent}（wake 通道）',
                metadata={
                    'wake_target': target_agent,
                    'wake_target_transport': TARGET_AGENT_TRANSPORT_WAKE,
                    'wake_delivery': 'agent_wake',
                    'wake_event': WAKE_EVENT_WATCH_L2,
                    'wake_status': status,
                    'wake_degraded': False,
                    'wake_target_url': self._resolve_wake_url(service, target_agent),
                },
            )
            return self._annotate_target_agent(result, target_agent)

        logger.warning('L2 目标路由：wake 未送达，降级飞书',
                       target_agent=target_agent, symbol=symbol,
                       wake_status=status, detail=str(detail)[:200])
        notification.preferred_channels = ['feishu']
        result = self.service.send(notification)
        return self._annotate_wake_degraded(
            result, target_agent,
            transport=TARGET_AGENT_TRANSPORT_WAKE_FALLBACK,
            status=status, detail=detail, fallback='feishu')

    @staticmethod
    def _attempt_wake(service, target_agent: str, wake_data: dict):
        """调用注入的 wake 实现，返回 (status, detail)。

        优先 notify_agent_detailed（拿到 ok/timeout/error/disabled/skipped 细分状态）；
        旧实现只有 notify_agent(event,data) 时退化为布尔。不在此处创建任何 HTTP 客户端。
        异常一律收敛为 ('error', 原因)——投递失败不该打挂通知主流程。
        """
        event = WAKE_EVENT_WATCH_L2
        try:
            detailed = getattr(service, 'notify_agent_detailed', None)
            if callable(detailed):
                try:
                    status = detailed(event, wake_data, target=target_agent)
                except TypeError:
                    # 兼容无 target 形参的旧实现——不因签名差异丢掉唤醒
                    status = detailed(event, wake_data)
                if isinstance(status, bool):
                    return ('ok' if status else 'error'), None
                return str(status), None
            try:
                ok = service.notify_agent(event, wake_data, target=target_agent)
            except TypeError:
                ok = service.notify_agent(event, wake_data)
            return ('ok' if ok else 'error'), None
        except Exception as exc:  # noqa: BLE001 - 投递异常降级飞书，不打挂通知
            return 'error', str(exc)[:200]

    @staticmethod
    def _resolve_wake_url(service, target_agent: str):
        """best-effort 取实际落点（观测用）；实现缺失/异常返回 None，不影响投递。"""
        resolver = getattr(service, 'resolve_target_url', None)
        if not callable(resolver):
            return None
        try:
            return resolver(target_agent)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _annotate_wake_degraded(result, target_agent, *, transport, status, detail, fallback):
        """把「wake 未送达 → 已降级」如实写进响应 metadata（不许静默说成功）。"""
        if result is None:
            return result
        try:
            metadata = getattr(result, 'metadata', None)
            if isinstance(metadata, dict):
                metadata.setdefault('wake_target', target_agent)
                metadata.setdefault('wake_target_transport', transport)
                metadata.setdefault('wake_delivery', fallback)
                metadata.setdefault('wake_event', WAKE_EVENT_WATCH_L2)
                metadata.setdefault('wake_status', status)
                metadata.setdefault('wake_degraded', True)
                metadata.setdefault(
                    'wake_fallback_reason',
                    detail or f'wake 未送达（status={status}），降级 {fallback}')
        except Exception as exc:  # pragma: no cover - 注解失败绝不影响发送结果
            logger.warning("wake 降级注解失败", error=str(exc))
        return result

    @staticmethod
    def _annotate_target_agent(result, target_agent):
        """把 target_agent 的**真实传输能力**写进响应 metadata（REQ-c9f899 t9）。

        本方法不改投递行为：给 ChannelResult.metadata 补 wake_target / 传输能力 / 原因。
        依据见模块顶部的取证注释——渠道层没有 per-agent 字段，接不通就**显式报告**，
        绝不假装接通（对齐 R-013 数据来源标注与"不许静默跳过"纪律）。
        """
        if not target_agent or result is None:
            return result
        try:
            metadata = getattr(result, 'metadata', None)
            if isinstance(metadata, dict):
                metadata.setdefault('wake_target', target_agent)
                metadata.setdefault('wake_target_transport', TARGET_AGENT_TRANSPORT)
                metadata.setdefault('wake_target_transport_reason', TARGET_AGENT_TRANSPORT_REASON)
        except Exception as exc:  # pragma: no cover - 注解失败绝不影响发送结果
            logger.warning("target_agent 传输能力注解失败", error=str(exc))
        return result

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

    def send_watch_receipt(
        self,
        title: str,
        content: str,
        *,
        os_channel: str,
        urgency: str = 'normal'
    ) -> bool:
        """盯盘回执投递（REQ-260924104605-ad0a t3，FR-3）

        os_channel（逻辑频道码）写入 variables 直透 AgentChannel —— Agent OS 网关按
        notification_channels 表路由到盯盘群（timeout/P0 → risk_stop，其余 → watch_symbol）。
        Agent OS 不可达时降级直飞书兜底（落原群，不丢消息）；与触发路径同一条降级链。
        失败返回 False——调用方（watch_channels）据此抛错，ReceiptService 如实记
        delivery_status=failed，绝不假装送达。

        Args:
            title: 卡片标题
            content: 卡片内容
            os_channel: 逻辑频道码（risk_stop / watch_symbol 等，必填）
            urgency: 紧急程度 'normal' | 'high' | 'critical'

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
            variables={'os_channel': os_channel},
            priority=priority_enum,
        )

        result = self.service.send_with_fallback(notification, 'agent', 'feishu')
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

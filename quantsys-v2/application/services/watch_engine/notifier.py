"""WatchEngine 触发通知器：分层提醒 + 自动升级 + DDD 通知架构

触发层级（trigger_level）：
- L0_MESSAGE：纯信息通知，直接发飞书（不唤醒 Agent，不经 LLM）
- L1_OBSERVATION：观察提醒，直接发飞书（不唤醒 Agent，不经 LLM）
- L2_ACTION：关键操作，发给 Agent（经 LLM 分析后决策）

升级机制：
- L0/L1 触发满足 escalation_policy 条件时，自动升级为 L2
- 升级原因在飞书消息中标注

架构约束：
- 所有通知必须走 NotificationFacade（禁止直接调用飞书 SDK）
- 参考：pi-investment/CLAUDE.md 架构规范章节
"""
import time
from typing import Optional

import requests
import structlog

from application.notification.notification_factory import NotificationFactory
from application.services.watch_engine.dto import TriggerPayload
from domain.watch.models import TriggerLevel

logger = structlog.get_logger(__name__)


def _norm_symbol(symbol: str) -> str:
    """'002241.SZ' -> '002241'（stocks 表为纯 6 位代码）。"""
    return (symbol or '').split('.')[0].strip()


def _lookup_stock_name(symbol: str) -> Optional[str]:
    """兜底查股票名称（quant.stocks）。失败返回 None，不影响主流程。"""
    try:
        from infrastructure.persistence.orm import get_session
        from sqlalchemy import text
        session = get_session()
        row = session.execute(
            text("SELECT name FROM quant.stocks WHERE symbol = :s LIMIT 1"),
            {"s": _norm_symbol(symbol)},
        ).fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.debug('股票名称兜底查询失败', symbol=symbol, error=str(e))
        return None


def _direction_advice(condition: dict) -> str:
    """从 condition.direction 解读操作倾向（结合 price_break/pnl 等类型）。"""
    if not isinstance(condition, dict):
        return ''
    params = condition.get('params') or {}
    direction = params.get('direction')
    ctype = condition.get('type', '')
    if direction == 'above':
        return '📈 方向：上破（强势）——持仓参考止盈/锁利，空仓为买入候选'
    if direction == 'below':
        return '📉 方向：下破（弱势）——持仓警惕止损，空仓暂不介入'
    return f'类型：{ctype}' if ctype else ''


class WatchNotifier:
    """WatchEngine 通知器
    
    职责：
    1. 构建 TriggerPayload（含 trigger_level/action_hint）
    2. 根据 trigger_level 决定通知模式（direct/agent）
    3. 调用 NotificationFacade 发送通知（复用 DDD 通知架构）
    4. WebSocket 广播 + 触发记录落库
    
    架构约束：
    - 禁止直接调用 feishu_service.send_alert()
    - 禁止直接调用 agent_service.notify_agent_detailed()
    - 所有通知必须走 NotificationFacade
    """
    
    def __init__(
        self,
        trigger_repo=None,
        ws_url: Optional[str] = 'http://127.0.0.1:5003/broadcast/market_data',
        max_retries: int = 3,
        retry_interval: float = 1.0,
        notification_facade=None,  # 可选：注入 NotificationFacade 实例
    ):
        self.trigger_repo = trigger_repo
        self.ws_url = ws_url
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        
        # 注入或懒加载 NotificationFacade
        self._notification_facade = notification_facade
    
    @property
    def notification_facade(self):
        """获取 NotificationFacade 实例（懒加载）"""
        if self._notification_facade is None:
            self._notification_facade = NotificationFactory.get_instance()
        return self._notification_facade

    def notify(self, rule, condition: dict, quote, result, escalation_reason: str = None,
               disposition: str = None, disposition_reason: str = None,
               dup_of: int = None):
        """触发通知
        
        Args:
            rule: 触发规则（含 action_hint, escalation_policy）
            condition: 触发的条件
            quote: 实时行情
            result: 条件评估结果
            escalation_reason: 升级原因（如果是 L1→L2 自动升级）
        
        Returns:
            bool: 是否成功送达
        """
        # 0. 去重短路（REQ-f08def）：同标的同向在去重窗内已有触发 → 只落库不通知。
        # 实测噪声来源：同规则同向多阈值（0.46 秒内两条）、601600 六条规则语义重合（一次跌穿 4+ 条）。
        # 仍落库是为了保留审计（notified=False + disposition='deduped' + dup_of 溯源）。
        if disposition == 'deduped':
            logger.info('触发去重合并（不通知）', rule_id=getattr(rule, 'id', None),
                        symbol=getattr(rule, 'symbol', None), dup_of=dup_of)
            return self._record(rule, condition, quote, result, notified=False,
                                disposition=disposition, disposition_reason=disposition_reason,
                                dup_of=dup_of)

        # 1. 构建 TriggerPayload
        payload = self._build_payload(rule, condition, quote, result, escalation_reason)
        
        # 2. 确定通知模式
        trigger_level = payload.trigger_level
        notify_mode = 'agent' if trigger_level == 'L2' else 'direct'
        
        # 3. 调用 NotificationFacade 发送通知
        logger.info(
            '发送盯盘触发通知',
            rule_id=rule.id,
            symbol=rule.symbol,
            trigger_level=trigger_level,
            notify_mode=notify_mode,
            escalation_reason=escalation_reason,
        )
        
        try:
            # 构建 NotificationFacade 参数
            facade_result = self.notification_facade.send_watch_triggered(
                symbol=payload.symbol,
                name=payload.name or payload.symbol,
                price=payload.price,
                condition=payload.condition,
                message=payload.message,
                context=payload.context,
                notify_mode=notify_mode,
                change_pct=payload.change_pct,
                pnl_pct=payload.pnl_pct,
                trigger_level=trigger_level,
                action_hint=payload.to_notification_variables().get('action_hint'),
                escalation_reason=escalation_reason,
                decision_audit_id=payload.decision_audit_id,
            )
            notified = facade_result.success if hasattr(facade_result, 'success') else bool(facade_result)
        except Exception as e:
            logger.error('通知发送失败', symbol=payload.symbol, error=str(e))
            notified = False
        
        # 4. WebSocket 广播
        self._broadcast_ws(payload)
        
        # 5. 触发记录落库（含处置初态）
        trigger = self._record(rule, condition, quote, result, notified,
                               disposition=disposition, disposition_reason=disposition_reason)

        return trigger

    def _build_payload(self, rule, condition, quote, result, escalation_reason: str = None) -> TriggerPayload:
        """构建 TriggerPayload"""
        price = float(quote.price)
        
        # 计算涨跌幅
        change_pct = None
        if getattr(quote, 'prev_close', None):
            change_pct = round((price - float(quote.prev_close)) / float(quote.prev_close) * 100, 2)
        elif getattr(quote, 'change_pct', None) is not None:
            change_pct = float(quote.change_pct)
        
        # 计算盈亏比例
        pnl_pct = None
        cost = getattr(rule, 'cost_price', None)
        if cost:
            pnl_pct = round((price - float(cost)) / float(cost) * 100, 2)
        
        # 名称兜底
        name = getattr(quote, 'name', None) or _lookup_stock_name(rule.symbol)
        
        # 获取 trigger_level（从 action_hint 或 rule 属性）
        trigger_level = 'L1'  # 默认 L1
        action_hint = None
        
        # 尝试从 rule.action_hint 读取
        if hasattr(rule, 'action_hint') and rule.action_hint:
            import json
            try:
                if isinstance(rule.action_hint, str):
                    ah = json.loads(rule.action_hint)
                else:
                    ah = rule.action_hint
                trigger_level = ah.get('trigger_level', 'L1')
                from domain.watch.models import ActionHint, TriggerLevel
                action_hint = ActionHint(
                    trigger_level=TriggerLevel(trigger_level),
                    action_on_trigger=ah.get('action_on_trigger', 'observe'),
                    requires_agent=ah.get('requires_agent', False),
                    position_ref=ah.get('position_ref'),
                    confidence=ah.get('confidence'),
                    max_position_pct=ah.get('max_position_pct'),
                    stop_loss=ah.get('stop_loss'),
                    target_price=ah.get('target_price'),
                )
            except Exception as e:
                logger.warning('解析 action_hint 失败', rule_id=rule.id, error=str(e))
        
        # 如果是 L1→L2 升级，强制改为 L2
        if escalation_reason:
            trigger_level = 'L2'
        
        return TriggerPayload(
            rule_id=rule.id,
            symbol=rule.symbol,
            name=name,
            price=price,
            condition=condition,
            message=result.message,
            context=getattr(rule, 'context', None),
            trigger_level=trigger_level,
            action_hint=action_hint,
            escalation_reason=escalation_reason,
            change_pct=change_pct,
            pnl_pct=pnl_pct,
            volume_ratio=result.value if hasattr(result, 'value') else None,
        )

    def _broadcast_ws(self, payload: TriggerPayload):
        """WebSocket 广播"""
        if not self.ws_url:
            return
        try:
            requests.post(
                self.ws_url,
                json={'type': 'watch_triggered', 'data': payload.to_notification_variables()},
                timeout=3
            )
        except Exception as e:
            logger.debug('WS 广播失败（忽略）', error=str(e))

    def _record(self, rule, condition, quote, result, notified,
                disposition: str = None, disposition_reason: str = None, dup_of: int = None):
        """触发记录落库（含处置初态，返回落库后的触发对象供去重溯源）"""
        if self.trigger_repo is None:
            return None
        try:
            return self.trigger_repo.record(
                rule_id=rule.id,
                symbol=rule.symbol,
                condition=condition,
                trigger_price=float(quote.price),
                detail={'value': result.value, 'message': result.message},
                notified=notified,
                disposition=disposition or 'pending',
                disposition_reason=disposition_reason,
                dup_of=dup_of,
            )
        except Exception as e:
            logger.error('触发记录落库失败', error=str(e))
            return None

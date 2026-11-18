"""notify_agent —— agent 投递通道（REQ-261022235419-2299 / t7，FR-7/FR-9）

用户裁定：
- D-13：**发 agent 与发飞书是两个文件**，本文件只管 agent 通道
- D-10：按规则绑定账户路由到对应 agent（WATCH_ACCOUNT_AGENT_MAP）
- D-14：agent 处理 = 改写处理状态（process_state）

职责：
1. 取提示词（agent_prompts，按 持仓×判定类型）
2. 按账户映射找对应 agent
3. 调注入的发送器投递
4. 成功后可回写处理状态（由调用方/agent 侧完成；本模块只提供标记入口）

本文件**不 import** notify_feishu（两通道文件级分离，可单测断言）。
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, Optional

import structlog

from . import agent_prompts

logger = structlog.get_logger(__name__)

#: 默认兜底账户→agent 映射（生产从环境变量/env 配置注入覆盖）
DEFAULT_ACCOUNT_AGENT_MAP: Dict[str, str] = {}

#: 未映射账户的兜底 agent 名（不静默丢：留 warning + 投给默认 agent）。
#: 必须与 WatchDeliveryPolicy.DEFAULT_AGENT 一致：2026-10-27 实测 agent-ts:3002
#: 监听但不响应 /wake，30s 扫描每次固定等 10s 超时并判投递失败；agent-dh:13080
#: 是当前在线的唯一 wake 端点，且是通知域的既定兜底。
DEFAULT_AGENT = 'agent-dh'

#: 再次唤醒同一规则 agent 的最小绝对价格浮动阈值（%）。
MIN_AGENT_PRICE_CHANGE_PCT = 1.0
PRICE_GATE_SKIP = 'price_change_below_threshold'


@dataclass
class AgentDelivery:
    """一次 agent 投递的结果。

    ``skipped=True`` 表示被价格浮动门槛拦截：这是业务上的刻意跳过，
    不是投递失败；调用方不得计入 delivery_failed。
    """

    delivered: bool
    agent: str
    account: str
    prompt: str
    error: str = ''
    skipped: bool = False


def resolve_agent(account: Optional[str],
                  account_agent_map: Optional[Dict[str, str]] = None) -> str:
    """账户 → 对应 agent（D-10）。未映射时回落 DEFAULT_AGENT 并留 warning。"""
    mapping = account_agent_map if account_agent_map is not None else DEFAULT_ACCOUNT_AGENT_MAP
    acc = str(account or '').strip()
    if not acc:
        logger.warning('v2.agent_account_missing')
        return DEFAULT_AGENT
    agent = mapping.get(acc)
    if not agent:
        logger.warning('v2.agent_account_unmapped', account=acc)
        return DEFAULT_AGENT
    return agent


def _display(value):
    return '—' if value is None or value == '' else value


def _positive_price(value) -> Optional[Decimal]:
    """把行情价转成正的十进制数；Decimal(str(x)) 保证 1% 边界按十进制精确比较。"""
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not price.is_finite() or price <= 0:
        return None
    return price


def is_material_price_change(current_price, last_price) -> bool:
    """价格是否达到再次唤醒 agent 的最低浮动（缺价/脏价 fail-open 允许发送）。"""
    current = _positive_price(current_price)
    last = _positive_price(last_price)
    if current is None or last is None:
        return True
    change_pct = abs(current - last) / last * Decimal('100')
    return change_pct >= Decimal(str(MIN_AGENT_PRICE_CHANGE_PCT))


def tracker_key(rule) -> Any:
    """价格跟踪键：优先规则 id；测试对象缺 id 时回落账户+symbol，避免互相污染。"""
    rule_id = getattr(rule, 'id', None)
    if rule_id is not None:
        return rule_id
    return (str(getattr(rule, 'account', '') or ''), str(getattr(rule, 'symbol', '') or ''))


def build_prompt(rule, judgment, position_state: Optional[str]) -> str:
    """按 持仓状态 × 判定类型 取提示词并填充上下文。"""
    intent = str(getattr(judgment, 'intent', '') or getattr(rule, 'intent', '') or '').strip()
    template = agent_prompts.get(position_state, intent)

    hits = getattr(judgment, 'hit_conditions', None) or []
    hit_summary = '；'.join(str(h.get('message', '')) for h in hits) or '条件触发'

    price = getattr(getattr(judgment, 'quote', None), 'price', None)
    if price is None:
        price = getattr(rule, '_last_price', None) or '—'

    # 价格线（止损线用第一个 price_break 的价）
    stop_price = '—'
    for cond in (getattr(rule, 'conditions', None) or []):
        params = (cond.get('params') or {}) if isinstance(cond, dict) else {}
        if params.get('price'):
            stop_price = params['price']
            break

    action_params = getattr(rule, 'action_params', None) or {}
    try:
        return template.format(
            symbol=getattr(rule, 'symbol', ''),
            price=price,
            cost_price=_display(getattr(rule, 'cost_price', None)),
            pnl_pct=_display(getattr(judgment, 'pnl_pct', None)),
            sellable=_display(getattr(judgment, 'sellable', None)),
            stop_price=stop_price,
            invalidation_pct=getattr(rule, 'invalidation_threshold_pct', None) or '—',
            account=getattr(rule, 'account', None) or '—',
            hit_summary=hit_summary,
            judgment_type=intent,
            position_state=position_state or '—',
            t_trade_id=action_params.get('t_trade_id', '—'),
            t_trade_leg=action_params.get('leg', '—'),
            t_trade_mode=action_params.get('mode', '—'),
            quantity=action_params.get('quantity', '—'),
            reference_price=action_params.get('reference_price', '—'),
            buyback_price=action_params.get('buyback_price', '—'),
        )
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning('v2.agent_prompt_format_failed', error=str(exc))
        return f'{hit_summary}（提示词模板异常，已降级）'


def send(rule, judgment, position_state: Optional[str] = None,
         sender: Optional[Callable[[str, str, str, Dict[str, Any]], bool]] = None,
         account_agent_map: Optional[Dict[str, str]] = None,
         price_tracker: Optional[Dict[Any, Decimal]] = None,
         use_price_gate: bool = True) -> AgentDelivery:
    """投递到对应 agent（D-10 路由 + D-20 提示词 + D-23 价格浮动门槛）。

    参数：
        rule / judgment: 规则与判定结果
        position_state: 持仓状态（holding / none），决定提示词方案
        sender:         注入的发送器 ``sender(agent, account, prompt, context) -> bool``；
                        context 携带 rule_id/trigger_ids，供 agent 完成处置后回调；
                        生产实现走既有 agent 通知链路（qs_agenthub），缺失时
                        视为**未接线**（delivered=False，不伪造成功）
        account_agent_map: 账户→agent 映射（缺省 DEFAULT_ACCOUNT_AGENT_MAP）
        price_tracker:  rule_id → 上次成功发 agent 时价格；传入后才启用 1% 门槛。
                        成功投递才更新，失败不更新（不阻断既有补发语义）。
        use_price_gate: False 时只更新基线不拦截（失效裁决等必达通道用）。

    返回 AgentDelivery（含 agent/account/prompt，便于台账与单测断言）。
    """
    account = str(getattr(rule, 'account', '') or '').strip()
    agent = resolve_agent(account, account_agent_map)
    prompt = build_prompt(rule, judgment, position_state)
    trigger_ids = []
    for _, entry in getattr(judgment, '_v2_archive_entries', None) or []:
        trigger_id = getattr(entry, 'trigger_id', None)
        if trigger_id is not None and trigger_id not in trigger_ids:
            trigger_ids.append(trigger_id)
    action_params = getattr(rule, 'action_params', None) or {}
    context = {'rule_id': getattr(rule, 'id', None), 'trigger_ids': trigger_ids}
    intent = str(getattr(judgment, 'intent', '') or getattr(rule, 'intent', '') or '').strip()
    if intent == 't_trade' or action_params.get('t_trade_id') is not None:
        context.update({
            't_trade_id': action_params.get('t_trade_id'),
            't_trade_leg': action_params.get('leg'),
            't_trade_mode': action_params.get('mode'),
            'quantity': action_params.get('quantity'),
            'reference_price': action_params.get('reference_price'),
            'buyback_price': action_params.get('buyback_price'),
        })

    key = tracker_key(rule)
    current_price = _positive_price(
        getattr(getattr(judgment, 'quote', None), 'price', None))
    last_price = price_tracker.get(key) if price_tracker is not None else None
    if (price_tracker is not None and use_price_gate and last_price is not None
            and not is_material_price_change(current_price, last_price)):
        logger.info('v2.agent_send_skipped_price_change_below_threshold',
                    rule_id=getattr(rule, 'id', None), agent=agent,
                    current_price=current_price, last_price=last_price,
                    min_change_pct=MIN_AGENT_PRICE_CHANGE_PCT)
        return AgentDelivery(delivered=False, agent=agent, account=account,
                             prompt=prompt, error=PRICE_GATE_SKIP, skipped=True)

    if sender is None:
        logger.warning('v2.agent_sender_not_wired',
                       rule_id=getattr(rule, 'id', None), agent=agent)
        return AgentDelivery(delivered=False, agent=agent, account=account,
                             prompt=prompt, error='sender_not_wired')

    try:
        ok = bool(sender(agent, account, prompt, context))
    except Exception as exc:  # noqa: BLE001 - 投递失败留给调用方补发
        logger.error('v2.agent_send_failed',
                     rule_id=getattr(rule, 'id', None), agent=agent, error=str(exc))
        return AgentDelivery(delivered=False, agent=agent, account=account,
                             prompt=prompt, error=str(exc))

    if ok:
        if price_tracker is not None and current_price is not None:
            price_tracker[key] = current_price
        logger.info('v2.agent_delivered', rule_id=getattr(rule, 'id', None),
                    agent=agent, account=account)
    return AgentDelivery(delivered=ok, agent=agent, account=account, prompt=prompt,
                         error='' if ok else 'sender_returned_false')

"""notify_feishu —— 飞书盯盘群通道（REQ-261022235419-2299 / t8，FR-7/FR-10）

用户裁定（D-13）：发飞书与发 agent 是**两个文件**，本文件只管飞书群通道。

两个发群入口（D-14/16/18）：
1. agent 判断后 → agent 侧调本模块发群
2. 循环第 10 次 → 引擎直通发群（不经过 agent）

本文件**不 import** notify_agent（两通道文件级分离）。
发送动作走注入的 sender（生产 = qs_notification 的 NotificationFacade），
未接线时不伪造成功。
"""
from dataclasses import dataclass
from typing import Any, Callable, Optional

import structlog

from . import feishu_templates

logger = structlog.get_logger(__name__)

#: 发群入口标识（便于台账/对账区分来源）
ENTRY_AFTER_AGENT = 'after_agent'
ENTRY_DIRECT = 'direct'


@dataclass
class FeishuDelivery:
    """一次飞书投递结果。"""

    delivered: bool
    title: str
    body: str
    entry: str
    error: str = ''


def _display(value):
    return '—' if value is None or value == '' else value


def _with_agent_result(body: str, agent_result: Optional[dict]) -> str:
    if not agent_result:
        return body
    lines = [
        '**Agent 裁决**',
        f"动作：{agent_result['action']}",
        f"理由：{agent_result['reason']}",
    ]
    if agent_result.get('account'):
        lines.append(f"账户：{agent_result['account']}")
    if agent_result.get('qty') is not None:
        lines.append(f"数量：{agent_result['qty']}")
    return body + '\n\n' + '\n'.join(lines)


def render(rule, judgment, position_state: Optional[str] = None,
           agent_result: Optional[dict] = None) -> tuple[str, str]:
    """按 持仓状态 × 判定类型 渲染（标题, 正文），可附 agent 裁决。"""
    intent = str(getattr(judgment, 'intent', '') or getattr(rule, 'intent', '') or '').strip()
    title_tpl, body_tpl = feishu_templates.get(position_state, intent)

    hits = getattr(judgment, 'hit_conditions', None) or []
    hit_summary = '；'.join(str(h.get('message', '')) for h in hits) or '条件触发'

    price = getattr(getattr(judgment, 'quote', None), 'price', None) or '—'
    stop_price = '—'
    for cond in (getattr(rule, 'conditions', None) or []):
        params = (cond.get('params') or {}) if isinstance(cond, dict) else {}
        if params.get('price'):
            stop_price = params['price']
            break

    action_params = getattr(rule, 'action_params', None) or {}
    ctx = dict(
        symbol=getattr(rule, 'symbol', ''),
        # 公司名称：规则表不存名称，由 engine 注入 resolver 后回填到 rule.stock_name；
        # 缺名称时退化为空串（标题显示「(代码)」仍可定位）
        stock_name=getattr(rule, 'stock_name', '') or '',
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
    try:
        title = title_tpl.format(**ctx)
        if not ctx['stock_name']:
            title = title.replace('()', '').replace('()', '')
        return title, _with_agent_result(body_tpl.format(**ctx), agent_result)
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning('v2.feishu_template_format_failed', error=str(exc))
        return (f'🔔 盯盘触发 {ctx["symbol"]}',
                _with_agent_result(hit_summary, agent_result))


def make_facade_sender(facade):
    """构造生产用 sender：把 V2 渲染结果投到**盯盘群**（不是默认群）。

    必须走 ``send_watch_triggered``（经 notification_channels 路由到盯盘专用
    webhook，timeout/P0 → risk_stop、其余 → watch_symbol）；**不要**用
    ``send_card`` —— 那会落到默认群（2026-10-23 实测踩过）。

    用法（watch_bootstrap V2 分支）::

        sender = notify_feishu.make_facade_sender(get_notification_facade())
        create_engine_v2(..., feishu_sender=sender)
    """
    def _sender(title: str, body: str) -> bool:
        try:
            result = facade.send_watch_triggered(
                symbol=_extract_symbol(title),
                name='',
                price=0.0,
                condition={'type': 'v2_direct', 'params': {}},
                message=body,
                notify_mode='direct',
                scope='symbol',
            )
            return bool(getattr(result, 'success', getattr(result, 'delivered', False)))
        except Exception as exc:  # noqa: BLE001 - 发送失败交调用方补发
            logger.error('v2.feishu_facade_send_failed', error=str(exc))
            return False
    return _sender


def _extract_symbol(title: str) -> str:
    """从标题里取股票代码（模板标题格式「📈 增仓机会 300750.SZ」）。"""
    for token in str(title or '').split():
        if '.' in token and any(ch.isdigit() for ch in token):
            return token
    return ''


def build_card(rule, judgment, position_state: Optional[str] = None) -> dict:
    """构造飞书交互卡片 payload（header 颜色按判定类型区分）。

    卡片形态（飞书 v2 交互卡片）::

        {"msg_type": "interactive",
         "card": {"header": {"title": {"tag": "plain_text", "content": title},
                             "template": color},
                  "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": body}}]}}
    """
    intent = str(getattr(judgment, 'intent', '') or getattr(rule, 'intent', '') or '').strip()
    state = str(position_state or '').strip().lower() or None
    title, body = render(rule, judgment, state)
    color = feishu_templates.color_of(state, intent)
    return {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {'tag': 'plain_text', 'content': title},
                'template': color,
            },
            'elements': [
                {'tag': 'div', 'text': {'tag': 'lark_md', 'content': body}},
            ],
        },
    }


def send_card_direct(webhook_url: str, rule, judgment,
                     position_state: Optional[str] = None,
                     timeout: float = 8.0) -> dict:
    """直接 POST 盯盘群 webhook（完全自控 header 颜色）。

    与 ``send``（走注入 sender）的区别：本函数自带 HTTP 发送，用于需要
    精确控制卡片样式（颜色/结构）的场景。**只发盯盘群 webhook**，不要传原群。

    返回：{"success": bool, "status_code": int|None, "error": str}
    """
    payload = build_card(rule, judgment, position_state)
    if not webhook_url:
        logger.warning('v2.feishu_direct_no_webhook')
        return {'success': False, 'status_code': None, 'error': 'webhook_not_configured'}
    try:
        import requests
        resp = requests.post(webhook_url, json=payload,
                             headers={'Content-Type': 'application/json'},
                             timeout=timeout)
        data = resp.json() if resp.content else {}
        ok = bool(data.get('code') == 0 or data.get('StatusCode') == 0)
        if not ok:
            logger.warning('v2.feishu_direct_failed', status=resp.status_code, resp=data)
        return {'success': ok, 'status_code': resp.status_code,
                'error': '' if ok else str(data)}
    except Exception as exc:  # noqa: BLE001 - 发送失败交调用方处置
        logger.error('v2.feishu_direct_error', error=str(exc))
        return {'success': False, 'status_code': None, 'error': str(exc)}


def send_rendered(webhook_url: str, title: str, body: str,
                  template: str = 'blue', timeout: float = 8.0) -> bool:
    """发送**已渲染**的标题/正文到盯盘群（``send`` 注入 sender 用）。

    为什么单独有它：``send`` 的 sender 契约是 ``sender(title, body)``，而
    ``send_card_direct`` 的契约是 ``(rule, judgment, position_state)`` —— 宿主
    直接把后者当 sender 传入会拿到两个字符串、渲染出空标的（2026-10-24 实测）。
    本函数只吃渲染结果，不再碰 rule/judgment，避免两套契约混用。
    """
    if not webhook_url:
        logger.warning('v2.feishu_rendered_no_webhook')
        return False
    payload = {
        'msg_type': 'interactive',
        'card': {
            'header': {'title': {'tag': 'plain_text', 'content': str(title or '')},
                       'template': template or 'blue'},
            'elements': [{'tag': 'div',
                          'text': {'tag': 'lark_md', 'content': str(body or '')}}],
        },
    }
    try:
        import requests
        resp = requests.post(webhook_url, json=payload,
                             headers={'Content-Type': 'application/json'},
                             timeout=timeout)
        data = resp.json() if resp.content else {}
        ok = bool(data.get('code') == 0 or data.get('StatusCode') == 0)
        if not ok:
            logger.warning('v2.feishu_rendered_failed', status=resp.status_code, resp=data)
        return ok
    except Exception as exc:  # noqa: BLE001 - 发送失败交调用方处置
        logger.error('v2.feishu_rendered_error', error=str(exc))
        return False


def send(rule, judgment, position_state: Optional[str] = None,
         entry: str = ENTRY_AFTER_AGENT,
         sender: Optional[Callable[[str, str], bool]] = None,
         agent_result: Optional[dict] = None) -> FeishuDelivery:
    """发飞书盯盘群。

    参数：
        entry:  ENTRY_AFTER_AGENT（agent 判断后）/ ENTRY_DIRECT（循环第 10 次直通）
        sender: 注入发送器 ``sender(title, body) -> bool``（生产走
                NotificationFacade.send_watch_*）；缺失视为未接线。
        agent_result: after_agent 时附加的结构化裁决；direct 不传。
    """
    title, body = render(rule, judgment, position_state, agent_result=agent_result)

    if sender is None:
        logger.warning('v2.feishu_sender_not_wired',
                       rule_id=getattr(rule, 'id', None), entry=entry)
        return FeishuDelivery(delivered=False, title=title, body=body,
                              entry=entry, error='sender_not_wired')

    try:
        ok = bool(sender(title, body))
    except Exception as exc:  # noqa: BLE001 - 发送失败留给调用方补发
        logger.error('v2.feishu_send_failed',
                     rule_id=getattr(rule, 'id', None), entry=entry, error=str(exc))
        return FeishuDelivery(delivered=False, title=title, body=body,
                              entry=entry, error=str(exc))

    logger.info('v2.feishu_delivered', rule_id=getattr(rule, 'id', None),
                entry=entry, delivered=ok)
    return FeishuDelivery(delivered=ok, title=title, body=body, entry=entry,
                          error='' if ok else 'sender_returned_false')

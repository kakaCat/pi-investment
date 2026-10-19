"""统一盯盘消息渲染器（REQ-261016155500-4f2a，2026-10-16 · 设计 §3.3）

唯一出稿点：WatchMessage → (title, text, color, mention_all)。
- text 同时喂给 Notification.content（agent-os 网关裸转发路径）与飞书卡片 div——
  两条投递路径看到**同一份四段式正文**；
- 颜色只表达级别（P0 红/P1 橙/P2 蓝/P3 灰），方向只在正文文字表达；
- 🛑 仅用于 exit_stop 意图标签；🔔 仅用于"真的需要用户决策"（动作 ∈ 买/卖/减仓）。

灰度：WATCH_MSG_V2 环境变量（默认 true；'false' 关闭时调用方回退旧渲染链）。
"""
import os
from dataclasses import dataclass
from typing import Optional

from domain.watch.services.watch_message import WatchMessage, intent_meta

#: 灰度开关（默认开）。关闭时 facade/formatter 保持旧渲染路径，便于对比与回滚。
MSG_V2_ENABLED = os.environ.get('WATCH_MSG_V2', 'true').strip().lower() not in ('false', '0', 'off')

#: 级别 → 卡片颜色（唯一颜色语义：级别）。
LEVEL_COLORS = {'P0': 'red', 'P1': 'orange', 'P2': 'blue', 'P3': 'grey'}

#: 生命周期阶段 → 中文（对齐 feishu_formatters.STAGE_LABELS，收敛后的唯一副本）。
STAGE_LABELS = {
    'discovered': '刚发现', 'tracking': '跟踪中', 'entry_triggered': '买点已触发',
    'holding': '持仓中', 'exit_triggered': '卖点已触发', 'closed': '已收摊',
}

_NEEDS_DECISION_VERBS = ('buy', 'sell', 'reduce')


@dataclass(frozen=True)
class RenderedMessage:
    title: str
    text: str
    color: str = 'blue'
    mention_all: bool = False


def _fact_line(msg: WatchMessage) -> str:
    bits = []
    if msg.fact.condition_text:
        bits.append(msg.fact.condition_text)
    if msg.fact.price is not None:
        price = '现价 ¥%.2f' % msg.fact.price
        if msg.fact.change_pct is not None:
            price += ' (%+.2f%%)' % msg.fact.change_pct
        bits.append(price)
    if msg.fact.pnl_pct is not None:
        bits.append('盈亏 %+.2f%%' % msg.fact.pnl_pct)
    return '；'.join(bits) if bits else '-'


def _mode_tag(msg: WatchMessage) -> str:
    """首行模式标签：missing → ⚠️；需决策动作 → 🔔；其余直发/AI。"""
    if msg.action.verb == 'missing':
        return '`⚠️ 指引缺失`'
    if msg.action.verb in _NEEDS_DECISION_VERBS:
        return '`🔔 需决策`'
    if msg.mode == 'agent':
        return '`⚡ AI 分析版`'
    return '`📡 直发提醒`'


def render_watch_message(msg: WatchMessage) -> RenderedMessage:
    """WatchMessage → 渲染结果（text 为 Markdown，兼容 lark_md 与网关纯文本）。"""
    level = str(msg.level or 'P2').strip().upper()
    if level not in LEVEL_COLORS:
        level = 'P2'
    intent_label, default_purpose = intent_meta(msg.intent)
    display = msg.name + '（' + msg.symbol + '）' if msg.name else msg.symbol

    title = intent_label + ' · ' + display
    if msg.merged_from_rule:
        title += '（与规则#%s 同事件，合并展示）' % msg.merged_from_rule
    if level == 'P0':
        title = '🚨 ' + title

    meta_bits = []
    if msg.stage:
        meta_bits.append('阶段：' + STAGE_LABELS.get(msg.stage, msg.stage))
    meta_bits.append('账户：' + (msg.account or '通用观察'))
    meta_bits.append('级别：' + level)
    relation = str(msg.relation or '').strip()

    lines = [
        _mode_tag(msg),
        '**' + intent_label + '｜' + display + '**',
        ' · '.join(meta_bits),
        ('**与我何干**：' + relation) if relation else None,
        '**事实**：' + _fact_line(msg),
        '**意义**：' + (msg.purpose or default_purpose),
        '**建议动作**：' + (msg.action.text or '-'),
        '**重估条件**：' + (msg.reevaluate or '—'),
    ]
    lines = [ln for ln in lines if ln is not None]
    if msg.escalation_reason:
        lines.append('**升级**：' + msg.escalation_reason)
    if msg.plan:
        plan_lines = [ln for ln in msg.plan.splitlines() if ln.strip()]
        excerpt = '\n'.join(plan_lines[:6])
        if len(plan_lines) > 6:
            excerpt += '\n…（完整预案见盯盘规则 #%s）' % (msg.rule_id or '-')
        lines.append('**预案**：' + excerpt)

    trace = []
    if msg.rule_id is not None:
        trace.append('规则#%s' % msg.rule_id)
    if msg.trigger_ids:
        trace.append('触发' + '/'.join('#%s' % t for t in msg.trigger_ids))
    if msg.todo_id is not None:
        trace.append('待办#%s' % msg.todo_id)
    if trace:
        lines.append('—— ' + ' · '.join(trace))

    return RenderedMessage(
        title=title,
        text='\n'.join(lines),
        color=LEVEL_COLORS[level],
        mention_all=(level == 'P0'),
    )

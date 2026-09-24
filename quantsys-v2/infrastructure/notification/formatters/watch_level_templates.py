"""按级别的盯盘飞书消息模板（P0 红卡 / P1 橙卡 / P2 蓝卡 / P3 日终汇总）。

REQ-c9f899 R4「颜值」的落点（design/architecture.md §7：模板输入只认结构化字段，禁止拼接式消息）。

设计纪律（每条都可被 tests/notification/test_watch_templates.py 证伪）：

  · **纯函数 + 结构化输入**：模板只消费 WatchCardItem 的字段，不解析 message 文本、不读外部状态、
    不访问数据库——级别判定（domain/watch/services/level_resolver.py）与账户路由
    （domain/watch/services/owner_router.py）在调用前已完成，本模块只负责"长什么样"。
  · **首行一眼看到「标的 + 现价 + 该干什么」**（R4 共性纪律）——四类模板的首行都满足，
    且首行格式由级别固定，不由文案决定。
  · **级别决定颜色 / 是否 @ / 是否可静默 / 是否单独推送**，不由文案决定：
      P0 红卡 · 不可静默 · @ 用户；P1 橙卡 · 不可静默 · 合并成一张；P2 蓝卡 · 可静默 · 一行一条；
      P3 不单独推送，只进日终汇总（standalone_push=False）。
  · **未知级别默认走 P2 并显式标注**：resolve_level_template 返回 fallback=True 的模板，
    渲染结果里带 "⚠️ 未知级别…按 P2 处理" 一行，绝不静默降级。
  · 空输入响亮抛错（ValueError），不渲染空卡片——P0 静默比重复推送更危险。

落点说明：本模块只产飞书卡片载荷（msg_type=interactive），payload 形状复用既有
infrastructure/notification/formatters/feishu_base_formatter.py 的 format_card（既有渲染风格照抄）。
**渠道接线已由 t12 完成**：feishu_formatters.WatchTriggeredFormatter.format 在 payload 带级别
（watch_level/level）时改走本模块的 render_watch_variables；不带级别仍走旧渲染（兼容非分级通知）。
"""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from domain.notification.models.notification import NotificationType
from infrastructure.notification.formatters.feishu_base_formatter import FeishuFormatter
# INTENT_META/STAGE_LABELS 复用旧意图驱动格式化的同一份表（单一真相，不复制）；
# feishu_formatters 对本模块是 format() 内的延迟 import，此处模块级 import 无循环。
from infrastructure.notification.formatters.feishu_formatters import (
    WatchTriggeredFormatter as _LegacyWatchFormatter,
)

# ── 级别常量（与 domain/watch/services/level_resolver.py 的 P0..P3 同值）──────────
P0 = 'P0'
P1 = 'P1'
P2 = 'P2'
P3 = 'P3'

#: 全部级别（顺序 = 处置紧迫度）
LEVELS: Tuple[str, ...] = (P0, P1, P2, P3)

#: P0 的 @ 提及。系统未持有用户 open_id（既有基类只有 mention_all 一种形态，
#: 见 feishu_base_formatter.format_text），故用 lark_md 的 @所有人 保证强提醒；
#: 若未来接入 open_id，只改这一处常量。
MENTION_USER = '<at user_id="all">所有人</at>'

#: P1 处置入口文案（R4：带处置入口）
ACTION_ENTRY_TEXT = '处置入口：打开待办看板勾选，或在会话里回复「处置 #<待办号>」'

#: P0 的两条硬性提示（R4：不可静默；带处置结果回执位）
P0_NOT_SILENCEABLE_TEXT = '不可静默：宪法级消息不进静默与预算抑制'
P0_RECEIPT_TEXT = '回执位：处置后回写结论（动作，或「不动 + NEXT 条件」）'


# ── 结构化输入 ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class WatchCardItem:
    """一条盯盘触发的结构化字段（模板唯一输入，禁止直接塞已拼好的文案）。"""

    symbol: str                      # 6 位代码
    price: float                     # 现价
    action: str                      # 「该干什么」（动作/处置指引，一句话）
    name: str = ''                   # 股票名称
    account: str = ''                # 归属账户
    rule_id: Optional[int] = None    # 规则#
    level: str = P2                  # 级别（聚合器按它筛选 P2/P3）
    condition: str = ''              # 触发条件（人类可读）
    plan: str = ''                   # 预案
    todo_id: Optional[int] = None    # 待办#
    change_pct: Optional[float] = None
    pnl_pct: Optional[float] = None
    occurred_at: Optional[datetime] = None  # 触发时刻（聚合器分桶用）
    # ── REQ-260924104605-ad0a t1：意图驱动骨架扩展字段（可选；缺失=模板隐藏该行，绝不臆造）──
    intent: str = ''                     # 规则意图（entry/trend_observe/exit_stop/...）
    stage: str = ''                      # 生命周期阶段（tracking/holding/...）
    purpose: str = ''                    # 「这条提醒为了」（intent 驱动的目的句）
    plan_full: str = ''                  # 预案全文（含评分依据，P0/P1 完整卡用）
    stop_loss: Optional[float] = None    # 止损价
    take_profit: Optional[float] = None  # 止盈价
    validity_days: Optional[int] = None  # 有效期（天）
    source: str = ''                     # 来源（如 opportunity_scan 自动创建）

    @property
    def display(self) -> str:
        """「贵州茅台（600519）」名称在前（REQ-260924104605-ad0a FR-13）；
        无名称时如实降级为「600519（名称缺失）」——绝不臆造名称（R-013）。"""
        name = str(self.name or '').strip()
        return f'{name}（{self.symbol}）' if name else f'{self.symbol}（名称缺失）'

    @property
    def price_text(self) -> str:
        """现价文本（数值缺失时给 '-'，绝不臆造价格）。"""
        try:
            return '¥%.2f' % float(self.price)
        except (TypeError, ValueError):
            return '-'


# ── 卡片载荷构造（复用既有基类，不重复实现飞书卡片结构）──────────────────────
class _CardBuilder(FeishuFormatter):
    """仅用于复用 FeishuFormatter.format_card 构造飞书卡片载荷；不注册进任何渠道。"""

    def supports_type(self, notification_type) -> bool:  # pragma: no cover - 不用于渠道分发
        return notification_type == NotificationType.WATCH_TRIGGERED

    def format(self, notification) -> Dict[str, Any]:  # pragma: no cover - 不用于渠道分发
        return self.format_card(title=notification.title, content=notification.content)


_CARD_BUILDER = _CardBuilder()


# ── 渲染小工具 ────────────────────────────────────────────────────────────────
def _id_text(value) -> str:
    return '-' if value in (None, '') else str(value)


def _rows(items) -> List[WatchCardItem]:
    """归一输入为列表；空输入响亮抛错（静默空卡片比重复推送更危险）。"""
    if isinstance(items, WatchCardItem):
        rows = [items]
    else:
        rows = list(items or [])
    if not rows:
        raise ValueError('盯盘消息模板至少需要一条结构化触发项（WatchCardItem），拒绝渲染空卡片')
    return rows


def _fallback_line(fallback: bool, requested_level: Optional[str]) -> Optional[str]:
    if not fallback:
        return None
    return (f'⚠️ 未知级别「{requested_level or "(空)"}」：按 P2（知悉）处理'
            f'（resolve_level_template 兜底并显式标注，不静默降级）')


# ── 意图驱动骨架（REQ-260924104605-ad0a t2，FR-4~7/9/10/12/13）─────────────────
#: 骨架固定顺序：意图标签 → 触发 → 现价 → 目的 → 预案 → 风控 → 下一步。
INTENT_META = _LegacyWatchFormatter.INTENT_META
STAGE_LABELS = _LegacyWatchFormatter.STAGE_LABELS


def _intent_meta(item: WatchCardItem) -> Tuple[str, str]:
    """（意图标签, 目的句）：item.purpose 显式值优先，否则 INTENT_META 映射；
    未标注意图 → 显式「❓ 未标注意图」（无主规则=烂账，如实暴露不掩饰）。"""
    label, purpose = INTENT_META.get(
        (item.intent or '').strip(),
        ('❓ 未标注意图', '这条规则没有声明意图——建议补 intent（无主规则=烂账）'))
    return label, (str(item.purpose or '').strip() or purpose)


def _intent_emoji(item: WatchCardItem) -> str:
    """意图标签的 emoji 段（P2 行首用，FR-7）。"""
    return _intent_meta(item)[0].split(' ')[0]


def _rule_ref(item: WatchCardItem) -> str:
    """规则号引用：有规则显示真实号；无规则（手工创建）显示「手工」——
    拒绝「规则#-」外露（FR-10）。"""
    return f'规则#{item.rule_id}' if item.rule_id not in (None, '') else '手工'


def _meta_line(item: WatchCardItem) -> str:
    """阶段 · 归属 · 规则引用。归属缺失 = 「通用观察」（无账户预案，不臆造账户）。"""
    bits: List[str] = []
    stage = (item.stage or '').strip()
    if stage:
        bits.append(f'阶段：{STAGE_LABELS.get(stage, stage)}')
    bits.append(f'归属：{item.account or "通用观察"}')
    bits.append(_rule_ref(item))
    return ' · '.join(bits)


def _price_line(item: WatchCardItem) -> str:
    """现价行（附带涨跌幅/持仓盈亏；缺失字段不臆造）。"""
    line = f'**当前**：{item.price_text}'
    if item.change_pct is not None:
        line += ' (%+.2f%%)' % item.change_pct
    if item.pnl_pct is not None:
        line += '　盈亏 %+.2f%%' % item.pnl_pct
    return line


def _fmt_price_opt(value) -> Optional[str]:
    try:
        return '¥%.2f' % float(value)
    except (TypeError, ValueError):
        return None


def _risk_line(item: WatchCardItem) -> Optional[str]:
    """风控行：止损/止盈/有效期任一存在才渲染（全缺 = 隐藏该行，绝不臆造）。"""
    bits: List[str] = []
    stop = _fmt_price_opt(item.stop_loss)
    if stop:
        bits.append(f'止损 {stop}')
    take = _fmt_price_opt(item.take_profit)
    if take:
        bits.append(f'止盈 {take}')
    if item.validity_days not in (None, ''):
        bits.append(f'有效期 {item.validity_days} 天')
    return f"**风控**：{' ｜ '.join(bits)}" if bits else None


def _skeleton_lines(item: WatchCardItem, *, receipt_note: bool = True) -> List[str]:
    """完整卡的意图驱动骨架（P0/P1 首项用）。

    顺序固定（t2 验收锚点）：意图标签 → 触发 → 现价 → 目的 → 预案 → 风控 → 下一步。
    「该干什么」只在「下一步」出现一次（FR-9 判重：N=1 时 action 文本出现 1 次）。
    """
    label, purpose = _intent_meta(item)
    lines = [
        '`🔔 需决策`',
        f'**{label}｜{item.display}**',
        _meta_line(item),
        f'**触发**：{item.condition or "-"}',
        _price_line(item),
        f'**这条提醒为了**：{purpose}',
    ]
    plan = (item.plan_full or item.plan or '').strip()
    if plan:
        lines.append(f'**预案**：{plan}')
    risk = _risk_line(item)
    if risk:
        lines.append(risk)
    next_line = f'**下一步**：{item.action}'
    if item.todo_id not in (None, ''):
        next_line += f'（待办#{item.todo_id}）'
    if receipt_note:
        next_line += ' → 处置后必有回执'
    lines.append(next_line)
    return lines


def _summary_line(item: WatchCardItem) -> str:
    """P1 其余项的一行摘要：意图 emoji + 标的 + 动作 + 待办# + 归属（FR-6）。"""
    bits = [item.action]
    if item.todo_id not in (None, ''):
        bits.append(f'待办#{item.todo_id}')
    bits.append(f'归属 {item.account or "通用观察"}')
    return f'- {_intent_emoji(item)} {item.display} {" · ".join(bits)}'

# ── 四类模板 ──────────────────────────────────────────────────────────────────
def render_p0(items, *, fallback: bool = False,
              requested_level: Optional[str] = None) -> Dict[str, Any]:
    """P0 红卡：@所有人 首行 + 意图骨架 + 处置入口；不聚合（每条单独推送）。

    REQ-ad0a t2：骨架 = 意图标签→触发→现价→目的→预案→风控→下一步；
    风控行含止损/止盈（FR-5）；P0_RECEIPT/不可静默两条硬提示保留。
    """
    rows = _rows(items)
    lead = rows[0]
    lines = [MENTION_USER]                      # @所有人 首行（FR-5）
    lines += _skeleton_lines(lead, receipt_note=True)
    lines.append(f'**{ACTION_ENTRY_TEXT}**')    # 处置入口（FR-5）
    lines.append(f'**{P0_NOT_SILENCEABLE_TEXT}**')
    lines.append(f'**{P0_RECEIPT_TEXT}**')
    note = _fallback_line(fallback, requested_level)
    if note:
        lines.append(note)
    if len(rows) > 1:
        others = '、'.join(row.display for row in rows[1:4])
        lines.append(f'同批另有 {len(rows) - 1} 条 P0：{others}')
    return _CARD_BUILDER.format_card(
        title=f'🛑 P0 立即处置 · {lead.display}',
        content='\n'.join(lines),
        color='red',
    )


def render_p1(items, *, fallback: bool = False,
              requested_level: Optional[str] = None) -> Dict[str, Any]:
    """P1 橙卡：首项完整骨架 + 其余项一行摘要（意图 emoji/待办#/归属）。

    REQ-ad0a t2：N=1 判重——action 只在「下一步」出现一次（FR-9）；
    N>1 = 1 完整段 + (N-1) 摘要行（FR-6）；多账户分行不合并（FR-4）。
    """
    rows = _rows(items)
    lead = rows[0]
    total = len(rows)
    lines: List[str] = []
    if total > 1:
        lines.append(f'有 {total} 项等你拍板')
    lines += _skeleton_lines(lead, receipt_note=True)
    for row in rows[1:]:
        lines.append(_summary_line(row))
    lines.append(f'**{ACTION_ENTRY_TEXT}**')
    note = _fallback_line(fallback, requested_level)
    if note:
        lines.append(note)
    return _CARD_BUILDER.format_card(
        title=f'🟠 P1 待决策（{total} 项）· {lead.display}',
        content='\n'.join(lines),
        color='orange',
    )


def render_p2(items, *, fallback: bool = False,
              requested_level: Optional[str] = None) -> Dict[str, Any]:
    """P2 蓝卡：一行一条（支持聚合多条）；行首意图 emoji，行尾归属（FR-7）。"""
    rows = _rows(items)
    lines = [
        (f'{_intent_emoji(row)} [知悉] {row.display} {row.price_text} {row.action}'
         f' · 归属 {row.account or "通用观察"}')
        for row in rows
    ]
    note = _fallback_line(fallback, requested_level)
    if note:
        lines.append(note)
    title = (f'🔵 P2 知悉 · {rows[0].display}' if len(rows) == 1
             else f'🔵 P2 知悉（{len(rows)} 条）')
    return _CARD_BUILDER.format_card(title=title, content='\n'.join(lines), color='blue')


def render_p3_digest(items, *, fallback: bool = False, requested_level: Optional[str] = None,
                     day: Optional[str] = None, max_lines: int = 20) -> Dict[str, Any]:
    """P3 日终汇总：P3 **不单独推送**，多条合成一条清单（首个渲染函数即聚合出口）。"""
    rows = _rows(items)
    lead = rows[0]
    header = f'[日终汇总] 盯盘归档 {len(rows)} 条'
    if day:
        header = f'{header}（{day}）'
    # 首行也满足共性纪律「标的 + 现价 + 该干什么」（取清单第一条）
    lines = [f'{header} ｜ {lead.display} {lead.price_text} {lead.action}']
    for row in rows[:max_lines]:
        lines.append(
            f'- {row.display} {row.price_text} {row.action}'
            f' · 归属 {row.account or "通用观察"} · {_rule_ref(row)}'
        )
    if len(rows) > max_lines:
        lines.append(f'- …另有 {len(rows) - max_lines} 条')
    note = _fallback_line(fallback, requested_level)
    if note:
        lines.append(note)
    return _CARD_BUILDER.format_card(
        title=f'🗂 P3 日终归档（{len(rows)} 条）',
        content='\n'.join(lines),
        color='grey',
    )


# ── level → 模板解析 ──────────────────────────────────────────────────────────
@dataclass(frozen=True)
class LevelTemplate:
    """一个级别的模板元信息 + 渲染函数。

    fallback=True 表示**请求的级别未知**，已按 P2 兜底（requested_level 保留原值供显式标注）。
    """

    level: str
    label: str
    color: str
    mention_user: bool
    silenceable: bool
    standalone_push: bool
    renderer: Callable[..., Dict[str, Any]]
    fallback: bool = False
    requested_level: Optional[str] = None


LEVEL_TEMPLATES: Dict[str, LevelTemplate] = {
    P0: LevelTemplate(level=P0, label='P0 立即处置', color='red', mention_user=True,
                      silenceable=False, standalone_push=True, renderer=render_p0),
    P1: LevelTemplate(level=P1, label='P1 待决策', color='orange', mention_user=False,
                      silenceable=False, standalone_push=True, renderer=render_p1),
    P2: LevelTemplate(level=P2, label='P2 知悉', color='blue', mention_user=False,
                      silenceable=True, standalone_push=True, renderer=render_p2),
    # P3 不单独推送：renderer 指向日终汇总（聚合出口），standalone_push=False
    P3: LevelTemplate(level=P3, label='P3 归档', color='grey', mention_user=False,
                      silenceable=True, standalone_push=False, renderer=render_p3_digest),
}


def resolve_level_template(level) -> LevelTemplate:
    """级别 → 模板（**四类模板的统一解析入口**）。

    大小写/空白容错（' p1 ' → P1）；**未知级别默认走 P2 并显式标注**：
    返回 fallback=True 的 P2 副本，requested_level 保留原始输入，渲染时写进卡片。
    """
    key = str(level or '').strip().upper()
    template = LEVEL_TEMPLATES.get(key)
    if template is not None:
        return template
    return replace(LEVEL_TEMPLATES[P2], fallback=True, requested_level=key or '(空)')


def render_watch_message(level, items) -> Dict[str, Any]:
    """按级别渲染飞书卡片载荷（解析 + 渲染的唯一入口）。"""
    template = resolve_level_template(level)
    return template.renderer(items, fallback=template.fallback,
                             requested_level=template.requested_level)


# ── Notification.variables → 卡片（渠道接线，REQ-c9f899 t12 §6-项1）──────────
#: 意图 → 「该干什么」兜底文案（payload 未带 next_action_hint 时用；只映射已知 intent）
INTENT_ACTION_HINT = {
    'entry': '关注买点（进入买区则评估建仓）',
    'add_position': '评估是否加仓',
    't_trade': '区间高抛低吸（找卖点 / 回补点）',
    'exit_stop': '立即止损（宪法第 4 条）',
    'exit_take_profit': '减仓锁利或继续持有',
    'exit_reduce': '执行减仓',
    'trend_observe': '观察趋势 / 结构变化',
}


def _action_text(variables: Dict[str, Any]) -> str:
    """「该干什么」：next_action_hint 优先 → intent 映射 → action_hint 动作（只作事实兜底）。"""
    hint = str(variables.get('next_action_hint') or '').strip()
    if hint:
        return hint
    intent = str(variables.get('intent') or '').strip()
    if intent in INTENT_ACTION_HINT:
        return INTENT_ACTION_HINT[intent]
    action_hint = variables.get('action_hint')
    if isinstance(action_hint, dict):
        action = str(action_hint.get('action_on_trigger') or '').strip()
        if action:
            return action
    return '见触发条件'


def card_item_from_variables(variables: Dict[str, Any]) -> WatchCardItem:
    """Notification.variables → WatchCardItem（结构化字段直取，禁止解析已拼好的文案）。

    缺值时如实留空（price 缺失 → 模板渲染为 "-"，绝不臆造价格，R-013）。
    """
    data = variables or {}
    condition = data.get('condition')
    condition_text = str(data.get('message') or '').strip()
    if not condition_text and isinstance(condition, dict):
        condition_text = str(condition.get('type') or '')
    return WatchCardItem(
        symbol=str(data.get('symbol') or '').split('.')[0].strip(),
        name=str(data.get('name') or ''),
        price=data.get('price'),
        action=_action_text(data),
        account=str(data.get('account') or ''),
        rule_id=data.get('rule_id'),
        level=str(data.get('watch_level') or data.get('level') or P2),
        condition=condition_text,
        plan=str(data.get('context') or ''),
        todo_id=data.get('todo_id'),
        change_pct=data.get('change_pct'),
        pnl_pct=data.get('pnl_pct'),
        # REQ-ad0a t2：意图骨架字段直取（缺失如实留空/None，模板隐藏该行）
        intent=str(data.get('intent') or ''),
        stage=str(data.get('lifecycle_stage') or data.get('stage') or ''),
        purpose=str(data.get('purpose') or ''),
        plan_full=str(data.get('plan_full') or ''),
        stop_loss=data.get('stop_loss'),
        take_profit=data.get('take_profit'),
        validity_days=data.get('validity_days'),
        source=str(data.get('source') or ''),
    )


def render_watch_variables(variables: Dict[str, Any]) -> Dict[str, Any]:
    """按级别渲染一条通知（variables 来自 Notification.variables）。

    由 WatchTriggeredFormatter 在 payload 带级别时调用（渠道接线，t12）：
    level/watch_level 缺失时按 P2 兜底（render_watch_message 内部会显式标注未知级别）。
    """
    data = variables or {}
    level = data.get('watch_level') or data.get('level')
    return render_watch_message(level, [card_item_from_variables(data)])


# ── P2/P3 聚合器（纯函数：账户 × 标的 × 时段）────────────────────────────────
@dataclass(frozen=True)
class AggregatedGroup:
    """一个聚合桶：同一账户 × 同一标的 × 同一时间窗内的多条 P2/P3。"""

    account: str
    symbol: str
    bucket_start: datetime
    bucket_end: datetime
    count: int
    levels: Tuple[str, ...]
    first_at: datetime
    last_at: datetime
    latest: WatchCardItem
    items: Tuple[WatchCardItem, ...]

    @property
    def key(self) -> Tuple[str, str, datetime]:
        return (self.account, self.symbol, self.bucket_start)


def _bucket_start(when: datetime, window_minutes: int) -> datetime:
    """把时刻对齐到时间窗起点（按整分钟向下取整）。"""
    base = when.replace(second=0, microsecond=0)
    return base - timedelta(minutes=base.minute % window_minutes)


def aggregate_watch_items(
    items: Iterable[WatchCardItem],
    *,
    window_minutes: int = 30,
    limit: int = 20,
    levels: Sequence[str] = (P2, P3),
    max_items_per_group: int = 3,
    now: Optional[datetime] = None,
) -> List[AggregatedGroup]:
    """按 **账户 × 标的 × 时段** 聚合 P2/P3（窗口与上限可传参）。

    参数：
        window_minutes    时间窗长度（分钟，>0），超出窗口即拆桶
        limit             返回的聚合桶上限（按 last_at 倒序、count 倒序取前 N）
        levels            只聚合这些级别（默认 P2/P3；P0/P1 逐条必达，不聚合）
        max_items_per_group 每个桶保留的代表条目上限（0/None = 全留）
        now               缺 occurred_at 时的兜底时刻（默认 datetime.now()）

    返回：按最近发生时间倒序的 AggregatedGroup 列表。纯函数，无 I/O。
    """
    if int(window_minutes) <= 0:
        raise ValueError('window_minutes 必须为正整数（分钟）')
    if int(limit) <= 0:
        raise ValueError('limit 必须为正整数')

    wanted = {str(level).strip().upper() for level in levels}
    fallback_now = now or datetime.now()
    buckets: Dict[Tuple[str, str, datetime], List[Tuple[datetime, WatchCardItem]]] = {}

    for item in items or []:
        if str(getattr(item, 'level', '') or '').strip().upper() not in wanted:
            continue
        when = getattr(item, 'occurred_at', None) or fallback_now
        start = _bucket_start(when, int(window_minutes))
        key = (str(getattr(item, 'account', '') or '').strip(),
               str(getattr(item, 'symbol', '') or '').strip(),
               start)
        buckets.setdefault(key, []).append((when, item))

    groups: List[AggregatedGroup] = []
    for (account, symbol, start), rows in buckets.items():
        rows.sort(key=lambda pair: pair[0].isoformat())
        times = [pair[0] for pair in rows]
        members = tuple(pair[1] for pair in rows)
        groups.append(AggregatedGroup(
            account=account,
            symbol=symbol,
            bucket_start=start,
            bucket_end=start + timedelta(minutes=int(window_minutes)),
            count=len(rows),
            levels=tuple(sorted({str(getattr(m, 'level', '') or '').strip().upper()
                                 for m in members})),
            first_at=times[0],
            last_at=times[-1],
            latest=members[-1],
            items=(members[:int(max_items_per_group)] if max_items_per_group else members),
        ))

    # 时间用 isoformat 排序（naive/aware 混用时 datetime 直接比较会 TypeError）
    groups.sort(key=lambda group: (group.last_at.isoformat(), group.count), reverse=True)
    return groups[:int(limit)]

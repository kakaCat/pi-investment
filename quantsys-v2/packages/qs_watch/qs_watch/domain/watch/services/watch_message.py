"""统一盯盘消息模型（REQ-261016155500-4f2a，2026-10-16）

所有盯盘消息（触发/聚合/回执）先构造为 WatchMessage，再经唯一渲染器出稿——
agent-os 网关裸转发与飞书降级路径看到**同一份四段式正文**（设计 §3.3）。

四段骨架：事实 → 意义 → 建议动作 → 重估条件。第 3 段必出；
缺指引时如实标注（⚠️ 规则#N 未配置操作指引），**禁止**「由 agent 汇总时判断」类推责文案。

本模块为纯领域对象 + 纯函数（无 I/O）：意图标签、目的句、动作映射的**唯一权威副本**，
feishu_formatters / watch_level_templates 的同名映射是历史重复，messaging 阶段收敛到这里。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

#: 意图 → (标签, 目的句)。未知意图走 MISSING_INTENT。
INTENT_META = {
    'entry':            ('🎯 买入跟踪', '等买点：是否已进入买区、要不要建仓'),
    'add_position':     ('➕ 加仓跟踪', '是否该加仓、加多少'),
    't_trade':          ('🔁 做T跟踪', '区间高抛低吸：找卖出的高点 / 回补的低点'),
    'exit_stop':        ('🛑 止损盯盘', '浮亏触及止损线 —— 宪法要求必须执行，不得延后'),
    'exit_take_profit': ('💰 止盈盯盘', '达到目标位：减仓锁利，还是继续持有'),
    'exit_reduce':      ('📉 减仓盯盘', '触及减仓档：减多少、还是清仓'),
}
MISSING_INTENT = ('❓ 未标注意图', '这条规则没有声明意图——建议补 intent（无主规则=烂账）')

#: 意图 → 「该干什么」兜底动作句（仅在 action_params / next_action_hint 都缺时用）。
INTENT_ACTION_HINT = {
    'entry': '关注买点（进入买区则评估建仓）',
    'add_position': '评估是否加仓',
    't_trade': '区间高抛低吸（找卖点 / 回补点）',
    'exit_stop': '立即止损（宪法第 4 条）',
    'exit_take_profit': '减仓锁利或继续持有',
    'exit_reduce': '执行减仓',
    'trend_observe': '观察趋势 / 结构变化',
}

#: 动作动词 → 中文。observe / missing 不是交易动作。
VERB_ZH = {'buy': '买入', 'sell': '卖出', 'hold': '持有', 'reduce': '减仓',
           'observe': '观察', 'missing': ''}

ACTION_SOURCE_PARAMS = 'action_params'
ACTION_SOURCE_HINT = 'next_action_hint'
ACTION_SOURCE_INTENT = 'intent_map'
ACTION_SOURCE_MISSING = 'missing'


@dataclass(frozen=True)
class FactSection:
    """事实段：触发条件文案 + 现价 + 涨跌幅 + 盈亏。"""
    condition_text: str = ''
    price: Optional[float] = None
    change_pct: Optional[float] = None
    pnl_pct: Optional[float] = None


@dataclass(frozen=True)
class ActionSection:
    """建议动作段（必出）。verb ∈ buy/sell/hold/reduce/observe/missing。"""
    verb: str
    text: str
    source: str


@dataclass(frozen=True)
class WatchMessage:
    """统一盯盘消息（触发卡；聚合卡/回执卡复用同一渲染骨架）。"""
    level: str                                          # P0/P1/P2/P3
    symbol: str
    name: str = ''
    account: Optional[str] = None
    intent: Optional[str] = None
    stage: Optional[str] = None                         # lifecycle_stage
    fact: FactSection = field(default_factory=FactSection)
    purpose: str = ''                                   # 意义段
    plan: Optional[str] = None                          # 预案（评分依据/风控/来源，截断展示）
    action: ActionSection = field(default_factory=lambda: ActionSection('missing', '', 'missing'))
    reevaluate: Optional[str] = None                    # 重估/失效条件
    rule_id: Optional[int] = None
    trigger_ids: Tuple[int, ...] = ()
    todo_id: Optional[int] = None
    escalation_reason: Optional[str] = None
    merged_from_rule: Optional[int] = None              # dedup 合并展示标注
    mode: str = 'direct'                                # direct / agent（L2）


def intent_meta(intent: Optional[str]) -> Tuple[str, str]:
    """意图 → (标签, 目的句)；未知/缺失如实标注。"""
    return INTENT_META.get((intent or '').strip(), MISSING_INTENT)


def _params_of(action_params: Any) -> Dict[str, Any]:
    if isinstance(action_params, str):
        import json
        try:
            action_params = json.loads(action_params)
        except Exception:  # noqa: BLE001 - 解析失败按空处理
            return {}
    return action_params if isinstance(action_params, dict) else {}


def resolve_action(action_params: Any = None,
                   next_action_hint: Optional[str] = None,
                   intent: Optional[str] = None,
                   rule_id: Optional[int] = None) -> ActionSection:
    """建议动作解析（优先级：action_params > next_action_hint > intent 映射 > missing）。

    - action_params：结构化指引，附参考价/仓位/数量/观察判据细节；
    - observe 动作必须带 observation_criterion 才算有指引（校验器在写入时已强制）。
    """
    ap = _params_of(action_params)
    verb = str(ap.get('action') or '').strip().lower()
    if verb:
        parts = [VERB_ZH.get(verb, verb)]
        if ap.get('reference_price') is not None:
            parts.append('参考价 ¥%.2f' % float(ap['reference_price']))
        if ap.get('position_pct') is not None:
            parts.append('仓位 %.0f%%' % float(ap['position_pct']))
        if ap.get('quantity') is not None:
            parts.append('%d 股' % int(ap['quantity']))
        if verb == 'observe':
            crit = (ap.get('observation_criterion') or '').strip()
            parts.append('（判据：%s）' % crit if crit else '（缺变化判据）')
        return ActionSection(verb=verb, text='，'.join(parts),
                             source=ACTION_SOURCE_PARAMS)

    hint = (next_action_hint or '').strip()
    if hint:
        return ActionSection(verb='observe', text=hint, source=ACTION_SOURCE_HINT)

    mapped = INTENT_ACTION_HINT.get((intent or '').strip())
    if mapped:
        return ActionSection(verb='observe', text=mapped, source=ACTION_SOURCE_INTENT)

    return ActionSection(
        verb='missing',
        text='⚠️ 规则#%s 未配置操作指引，已派补全任务给 agent' % rule_id,
        source=ACTION_SOURCE_MISSING)

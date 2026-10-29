"""agent_prompts —— agent 提示词注册表（REQ-261022235419-2299 / t7，R-11/FR-10）

用户裁定（D-20/D-21）：**持仓和非持仓方案提示词不一样**，且提示词与模板
是**两个独立文件** —— 本文件只负责 agent 提示词（飞书模板在
``feishu_templates.py``，两者互不 import）。

键 = （持仓状态, 判定类型）：
- 持仓类：holding × (add_position / exit_take_profit / exit_stop / exit_reduce)
- 非持仓类：none × (entry / trend_observe)

未注册键 → 回落通用提示词（不中断投递，只留 warning）。
"""
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

#: 持仓状态取值（与 position_engine 同源）
POSITION_HOLDING = 'holding'
POSITION_NONE = 'none'


@dataclass(frozen=True)
class AgentPrompt:
    """一条 agent 提示词（判断任务 + 上下文结构 + 期望输出）。"""

    key: Tuple[str, str]
    template: str


_TEMPLATES: Dict[Tuple[str, str], AgentPrompt] = {}


def _register(position_state: str, judgment_type: str, template: str) -> None:
    _TEMPLATES[(position_state, judgment_type)] = AgentPrompt(
        key=(position_state, judgment_type), template=template,
    )


# ── 持仓类（holding）· 上下文含成本/浮亏/可卖量 ──────────────────────────
_register(POSITION_HOLDING, 'add_position', (
    '【持仓·增仓判断】{symbol} 现价 {price}，持仓成本 {cost_price}，'
    '浮盈亏 {pnl_pct}%，可卖 {sellable} 股。\n'
    '触发线已到（{hit_summary}）。请判断：是否加仓？加多少？用哪个账户？'
    '\n输出：{{action: 加仓|持有|观察, qty, account, reason}}'
))

_register(POSITION_HOLDING, 'exit_take_profit', (
    '【持仓·止盈判断】{symbol} 现价 {price}，成本 {cost_price}，'
    '浮盈 {pnl_pct}%，可卖 {sellable} 股。\n'
    '止盈线已触发（{hit_summary}）。请判断：是否止盈？全部还是部分？'
    '\n输出：{{action: 止盈|持有, qty, account, reason}}'
))

_register(POSITION_HOLDING, 'exit_stop', (
    '【持仓·止损判断｜最高优先】{symbol} 现价 {price} 已触及止损线 '
    '{stop_price}，成本 {cost_price}，浮亏 {pnl_pct}%，可卖 {sellable} 股。\n'
    '触发（{hit_summary}）。止损是保护线：请立即判断是否执行卖出，'
    '执行为优先动作；若判断为状态异常请给出证据。'
    '\n输出：{{action: 卖出|持有|核查, qty, account, reason}}'
))

_register(POSITION_HOLDING, 'exit_reduce', (
    '【持仓·减仓判断】{symbol} 现价 {price}，成本 {cost_price}，'
    '浮盈亏 {pnl_pct}%，可卖 {sellable} 股。\n'
    '减仓线已触发（{hit_summary}）。请判断：是否减仓？减多少？'
    '\n输出：{{action: 减仓|持有, qty, account, reason}}'
))

# ── 非持仓类（none）· 上下文含买点价/失效线/建议仓位 ────────────────────
_register(POSITION_NONE, 'entry', (
    '【未持仓·买入执行核验】{symbol} 现价 {price} 已到买入范围（{hit_summary}）。\n'
    '规则失效线 {invalidation_pct}%，账户 {account}。\n'
    '若规则关联已激活计划且账户有自主授权，触发后直接进入执行核验，不要重复选股或只回复'
    '“继续观察”：先用 watch_brief 核对计划与规则，再完成 R-001（实时价/资金/regime/仓位）、'
    'R-008（经验检索）、R-009（信号级别）与基本面排雷。全部通过则在合法交易时段按计划'
    '仓位与试单额度的较严值调用 portfolio_trade，并核对成交、止损和审计；任一不通过才观察，'
    '且必须逐项列出具体阻塞项，禁止用笼统的“再评估”结束。'
    '\n输出：{{action: 买入|观察, qty, account, reason, blockers}}'
))

_register(POSITION_NONE, 'trend_observe', (
    '【未持仓·观察留痕】{symbol} 现价 {price}（{hit_summary}）。\n'
    '观察类不产生交易动作，仅记录趋势；如需操作请说明依据。'
    '\n输出：{{action: 观察|建仓, reason}}'
))

#: 未注册键的通用提示词（不中断投递）
FALLBACK_PROMPT = (
    '【盯盘触发】{symbol} 现价 {price}，判定类型 {judgment_type}'
    '（持仓状态 {position_state}，{hit_summary}）。\n'
    '请判断：改规则 / 执行 / 哪个账户买？\n输出：{{action, reason}}'
)

#: 失效裁决专用提示词（intent='invalidation'；持仓/非持仓通用）
INVALIDATION_PROMPT = (
    '【规则失效·裁决】{symbol} 现价 {price}，已偏离规则价格线超过失效线 '
    '{invalidation_pct}%（{hit_summary}）。\n'
    '规则已退出盯盘（rule_state=invalid）。请裁决：调整阈值回 active，'
    '还是退役归档 archived？\n输出：{{action: 改阈值|退役, new_threshold?, reason}}'
)


def get(position_state: Optional[str], judgment_type: Optional[str]) -> str:
    """取提示词模板；未注册键回落通用模板（不抛异常）。"""
    key = (str(position_state or '').strip().lower(),
           str(judgment_type or '').strip())
    if key[1] == 'invalidation':
        return INVALIDATION_PROMPT
    prompt = _TEMPLATES.get(key)
    if prompt is None:
        logger.warning('v2.agent_prompt_missing', key=key)
        return FALLBACK_PROMPT
    return prompt.template


def registered_keys() -> Tuple[Tuple[str, str], ...]:
    """已注册键（供单测/看板逐类型核对）。"""
    return tuple(sorted(_TEMPLATES))

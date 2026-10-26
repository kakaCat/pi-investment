"""feishu_templates —— 飞书消息模板注册表（REQ-261022235419-2299 / t8，R-11/FR-10）

用户裁定（D-20/D-21）：
- 飞书模板与 agent 提示词是**两个独立文件**（本文件只负责飞书模板）
- **持仓和非持仓方案模板不一样**：持仓含成本/浮亏/可卖量，非持仓含买点价/失效线

键 = （持仓状态, 判定类型）；未注册 → 通用模板 + warning（不中断发送）。
"""
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

POSITION_HOLDING = 'holding'
POSITION_NONE = 'none'


@dataclass(frozen=True)
class FeishuTemplate:
    key: Tuple[str, str]
    title: str
    body: str


_TEMPLATES: Dict[Tuple[str, str], FeishuTemplate] = {}


def _register(position_state: str, judgment_type: str, title: str, body: str) -> None:
    _TEMPLATES[(position_state, judgment_type)] = FeishuTemplate(
        key=(position_state, judgment_type), title=title, body=body,
    )


# ── 持仓类 ────────────────────────────────────────────────────────────────
_register(POSITION_HOLDING, 'add_position', '【持仓】📈 增仓机会 {stock_name}({symbol})', (
    '现价 {price}｜成本 {cost_price}｜浮盈亏 {pnl_pct}%｜可卖 {sellable} 股\n'
    '触发：{hit_summary}\n建议动作：加仓（仓位与账户待 agent 确认）'
))

_register(POSITION_HOLDING, 'exit_take_profit', '【持仓】💰 止盈提醒 {stock_name}({symbol})', (
    '现价 {price}｜成本 {cost_price}｜浮盈 {pnl_pct}%｜可卖 {sellable} 股\n'
    '触发：{hit_summary}\n建议动作：止盈（全部或部分待定）'
))

_register(POSITION_HOLDING, 'exit_stop', '【持仓】🛑 止损提醒 {stock_name}({symbol})', (
    '现价 {price}｜止损线 {stop_price}｜成本 {cost_price}｜浮亏 {pnl_pct}%｜可卖 {sellable} 股\n'
    '触发：{hit_summary}\n建议动作：执行卖出（保护线，优先处理）'
))

_register(POSITION_HOLDING, 'exit_reduce', '【持仓】📉 减仓提醒 {stock_name}({symbol})', (
    '现价 {price}｜成本 {cost_price}｜浮盈亏 {pnl_pct}%｜可卖 {sellable} 股\n'
    '触发：{hit_summary}\n建议动作：减仓（数量待定）'
))

# ── 非持仓类 ──────────────────────────────────────────────────────────────
_register(POSITION_NONE, 'entry', '【未持仓】🎯 买入范围 {stock_name}({symbol})', (
    '现价 {price}｜失效线 {invalidation_pct}%｜账户 {account}\n'
    '触发：{hit_summary}\n建议动作：建仓（仓位待 agent 确认）'
))

_register(POSITION_NONE, 'trend_observe', '【未持仓】👀 观察 {stock_name}({symbol})', (
    '现价 {price}\n触发：{hit_summary}\n建议动作：观察（不产生交易动作）'
))

#: 判定类型 → 飞书卡片 header 颜色（D-21 持仓/非持仓分方案 + 颜色区分）
#: 飞书支持：blue / wathet / turquoise / green / yellow / orange / red / carmine
#:           / violet / purple / indigo / grey
COLORS = {
    ('holding', 'exit_stop'): 'red',            # 止损：最紧急（保护线）
    ('holding', 'exit_take_profit'): 'green',   # 止盈：盈利兑现
    ('holding', 'exit_reduce'): 'orange',       # 减仓：风险降低
    ('holding', 'add_position'): 'blue',        # 增仓：机会
    ('none', 'entry'): 'yellow',                # 买入范围：建仓机会
    ('none', 'trend_observe'): 'grey',          # 观察：只读
}
FALLBACK_COLOR = 'blue'


def color_of(position_state: Optional[str], judgment_type: Optional[str]) -> str:
    """取判定类型对应的卡片 header 颜色；未注册回落 FALLBACK_COLOR。"""
    key = (str(position_state or '').strip().lower(),
           str(judgment_type or '').strip())
    return COLORS.get(key, FALLBACK_COLOR)


FALLBACK_TITLE = '🔔 盯盘触发 {stock_name}({symbol})'
FALLBACK_BODY = (
    '现价 {price}｜判定 {judgment_type}｜持仓状态 {position_state}\n'
    '触发：{hit_summary}'
)


def get(position_state: Optional[str], judgment_type: Optional[str]
        ) -> Tuple[str, str]:
    """取（标题, 正文）模板；未注册键回落通用模板（不抛异常）。"""
    key = (str(position_state or '').strip().lower(),
           str(judgment_type or '').strip())
    tpl = _TEMPLATES.get(key)
    if tpl is None:
        logger.warning('v2.feishu_template_missing', key=key)
        return FALLBACK_TITLE, FALLBACK_BODY
    return tpl.title, tpl.body


def registered_keys() -> Tuple[Tuple[str, str], ...]:
    return tuple(sorted(_TEMPLATES))

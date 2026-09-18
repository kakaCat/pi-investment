"""盯盘级别判定（P0–P3）—— domain 纯函数，机器判定，不允许自由发挥。

REQ-c9f899 R1（级别体系）/ R7（SLA）的判据落点：级别决定飞书「颜值」、是否可静默、是否 @、
以及流转时效，因此必须**可单测、无 I/O、无外部状态**——调用方只喂输入，判定不接受 agent
自由裁量（设计架构 §2：级别判定/路由/终态校验/反复触发判定全部是 domain 纯函数）。

判定输入（R1：规则显式声明的意图 + 是否持仓 + 是否宪法级；本轮另接 trigger_level/scope/治理）：

  · intent            —— 规则意图。**调用方须传 disposition.intent_of(rule)**，与处置判据同源，
                         避免"声明 buy 却没写 intent"的规则绕过分级（重复 rule_guard 的教训）。
  · has_position      —— 该标的当前是否持仓。持仓的止盈/减仓 = 已到处置点 → P0。
  · is_constitutional —— 宪法级触发（止损/熔断/仓位超限/单笔超阈值），无条件下达。
  · action_on_trigger —— action_hint 的动作；**仅当 intent 为空时**用于归一意图，见 _effective_intent。
  · trigger_level     —— 规则分级（规则显式声明 L2 = 买卖节点 → 必须有人拍板）。
  · scope             —— 事件范围（market/sector = 市场/板块级 → 知悉）。
  · is_governance     —— 治理项（规则体检/自愈建议 → 归档汇总）。

判定优先级（自上而下，**先命中先返回**，不允许调换顺序）：

  1. is_constitutional 或 intent ∈ CONSTITUTIONAL_INTENTS      → P0（宪法级/止损：无条件下达）
  2. has_position 且 intent ∈ (exit_take_profit, exit_reduce)  → P0（持仓卖出类：已到处置点）
  3. intent ∈ (entry, add_position, t_trade)                   → P1（买卖节点：需有人拍板）
  4. trigger_level == 'L2'                                     → P1（规则显式声明行动层）
  5. is_governance                                             → P3（治理项：仅归档汇总）
  6. scope ∈ (market, sector)                                  → P2（市场/板块：知悉；先于纯观察）
  7. intent == 'trend_observe'                                 → P3（纯观察：无动作）
  8. 其余                                                      → P2（兜底知悉）

优先级冲突取**先命中**，不要凭直觉交换：
  · trigger_level='L2' 的 trend_observe → P1（第 4 条先于第 7 条，观察也不例外须拍板）；
  · scope=sector 的 trend_observe → P2（第 6 条先于第 7 条，板块异动属知悉而非归档）；
  · 无持仓的 exit_stop → P0（第 1 条不看持仓）；
  · 无持仓的 exit_take_profit → 不命中第 2 条，落到 P2（没有持仓就没有「已到处置点」）。
"""
from types import SimpleNamespace
from typing import Optional

from domain.watch.services.disposition import CONSTITUTIONAL_INTENTS, intent_of

P0 = 'P0'
P1 = 'P1'
P2 = 'P2'
P3 = 'P3'

#: 全部级别（顺序 = 处置紧迫度，供校验/遍历用）
LEVELS = (P0, P1, P2, P3)

#: 级别 → SLA 秒数（REQ-c9f899 R7）。
#: P0 = 5 分钟（300s）/ P1 = 30 分钟（1800s）；
#: P2 = **当日收盘前**——不是一个固定秒数（依赖交易日历与当日收盘时刻），故用 None 表示，
#: 由调用方按交易日收盘计算 due_at；P3 = 无 SLA（仅归档）。
LEVEL_SLA_SECONDS = {P0: 300, P1: 1800, P2: None, P3: None}

#: 意图分组。宪法级意图不在本模块另立常量——复用 disposition.CONSTITUTIONAL_INTENTS 单一事实源；
#: 以下三组是本模块的判定口径（entry 节点 vs 持仓卖出 vs 观察）。
POSITION_EXIT_INTENTS = ('exit_take_profit', 'exit_reduce')
ENTRY_INTENTS = ('entry', 'add_position', 't_trade')
OBSERVE_INTENT = 'trend_observe'
MARKET_SCOPES = ('market', 'sector')

_TRADE_ACTIONS = ('buy', 'sell')
_OBSERVE_ACTIONS = ('observe', 'message')


def sla_seconds_for(level: Optional[str]) -> Optional[int]:
    """级别 → SLA 秒数（R7）。

    P0=300 / P1=1800 为固定秒数；**P2=当日收盘前、P3=无 SLA 一律返回 None**——
    None 的含义由级别决定，调用方须区分：
      · P2：None = 「当日收盘前」，须按交易日收盘自行计算 due_at（不按秒计）；
      · P3：None = 无 SLA，仅归档，不应据此设到期晋升；
      · 未知级别：保守返回 None（调用方按「不按秒计」处理，绝不臆造时限）。
    大小写与空白容错（' p1 ' → 1800）。
    """
    return LEVEL_SLA_SECONDS.get(str(level or '').strip().upper())


def _effective_intent(intent, action_on_trigger) -> str:
    """意图归一：显式 intent 优先；为空时按 action_on_trigger 归一。

    存在价值：action_hint 声明了 buy/sell 却没写 intent 的规则，运行时（disposition.intent_of）
    照样会被当成交易意图——分级若只看空 intent 就会把它静默降成 P2/P3（正是 rule_guard 修过的坑）。
    故这里复用 disposition.intent_of 同一套推导规则（不新造第三份映射）：
      · buy  → entry
      · sell → 无 conditions 可辨止损/止盈，取最保守的 exit_reduce（持仓即 P0）
    无法识别或不涉及交易/观察的动作一律返回空串，让它落兜底档（不臆造级别）。
    """
    text = str(intent or '').strip()
    if text:
        return text
    act = str(action_on_trigger or '').strip().lower()
    if act in _TRADE_ACTIONS:
        return intent_of(SimpleNamespace(intent='', action_hint={'action_on_trigger': act},
                                        conditions=[]))
    if act in _OBSERVE_ACTIONS:
        return OBSERVE_INTENT
    return ''


def resolve_level(intent, has_position, is_constitutional: bool = False,
                  action_on_trigger=None, trigger_level=None, scope=None,
                  is_governance: bool = False) -> str:
    """级别判定（纯函数）：返回 P0/P1/P2/P3。优先级见模块 docstring（先命中先返回）。

    输入语义与边界（每条都能在 tests/domain/test_level_router.py 的真值表里找到对应行）：
      · is_constitutional=True 或 intent=exit_stop → P0（不看持仓、不看其他入参）；
      · 有持仓的止盈/减仓（exit_take_profit/exit_reduce）→ P0；
      · 买卖节点（entry/add_position/t_trade）→ P1；
      · trigger_level='L2' → P1（压过观察/治理/scope）；
      · 治理项 → P3；市场/板块 scope（含 trend_observe）→ P2；其余纯观察 → P3；兜底 P2。

    参数 action_on_trigger 仅用于 intent 为空的归一（见 _effective_intent），显式 intent 永远优先。
    """
    effective = _effective_intent(intent, action_on_trigger)

    # 1. 宪法级/止损：无条件下达
    if is_constitutional or effective in CONSTITUTIONAL_INTENTS:
        return P0

    # 2. 持仓的止盈/减仓：已到处置点
    if has_position and effective in POSITION_EXIT_INTENTS:
        return P0

    # 3. 买卖节点：需有人拍板
    if effective in ENTRY_INTENTS:
        return P1

    # 4. 规则显式声明行动层（先于观察/治理）
    if str(trigger_level or '').strip().upper() == 'L2':
        return P1

    # 5. 治理项（规则维护话题）：仅归档汇总
    if is_governance:
        return P3

    # 6. 市场/板块级：知悉（P2）
    #    ⚠️ 2026-09-18 修正：必须先于「纯观察 → P3」。市场级规则的意图通常是
    #    trend_observe 或空，若让观察兜底先行，「板块异动」将永远进不了 P2 知悉层，
    #    与需求 R1（P2 = 知悉，含板块异动）冲突——由主 agent 独立探针发现。
    if str(scope or '').strip().lower() in MARKET_SCOPES:
        return P2

    # 7. 纯观察：无动作、无需知悉 → 归档
    if effective == OBSERVE_INTENT:
        return P3

    # 8. 兜底：知悉（P2）
    return P2

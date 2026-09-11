"""盯盘触发处置决策 v2（REQ-f08def P3，RFC 014 v3 §3，2026-09-11，w-c8cae280）

「何时介入」的判据：价格触发五道门 + 元触发轻门 + 宪法豁免 + 每日预算。
纯函数 + 配置注入；数据由调用方（引擎 tick / 复核作业）注入。

判定优先级（自上而下，先命中先返回）：
  0. 宪法豁免：止损等无条件介入，且可突破预算
  1. 预算门：当日介入预算耗尽 → 非宪法动作进日终汇总
  2. 引擎升级（escalation_policy 命中）→ 摘要队列
  3. 规则分级 L2 → 摘要队列（L2 = 买卖节点，必须 agent 终判）
  4. 元触发轻门：仅增量门+经济门（不适用金额门/节点门）
  5. 价格触发五道门：意图 → 金额 → 增量 → 经济 → 节点

用户硬约束（2026-09-11）：不能所有触发都叫 agent——成本必须与利润一致。
所以默认宁归档不介入：判据不过就落 auto_observed（零 LLM），进日终汇总。
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

DEDUP_WINDOW_SEC = 60

DISPOSITION_PENDING = 'pending'
DISPOSITION_AUTO_OBSERVED = 'auto_observed'
DISPOSITION_DEDUPED = 'deduped'
DISPOSITION_ESCALATED = 'escalated'
DISPOSITION_HANDLED = 'handled'
DISPOSITION_IGNORED = 'ignored'
DISPOSITION_EXPIRED = 'expired'
DISPOSITION_LEGACY = 'legacy_unknown'
DISPOSITION_META_REVIEW = 'meta_review'   # 元触发：规则需复核（频次/静默/滞留/到期）

UNRESOLVED = (DISPOSITION_PENDING, DISPOSITION_ESCALATED, DISPOSITION_META_REVIEW)


@dataclass
class InterventionConfig:
    """介入判据配置（RFC 014 v3 §3.2/§3.3，默认值 = 用户尚未拍板时采用的口径）"""
    amount_threshold_pct: float = 0.01      # 金额门：动作影响 >= 账户 1%
    account_total_yuan: float = 100000.0    # 账户总资产（调用方注入/定期更新）
    same_topic_cooldown_sec: int = 14400    # 增量门：同标的同议题 4h 内只介入一次
    k_economic: float = 3.0                 # 经济门：期望收益 >= k × 介入成本
    wake_cost_yuan: float = 1.0             # 单次介入成本估算（token + 错误风险折价）
    daily_budget: int = 8                   # 每日介入预算（§3.3）
    anomaly_change_pct: float = 5.0         # 异常触发：|change_pct| 超此值视为异常
    meta_burst_per_day: int = 5             # 元触发：单日触发超此数需复核
    meta_idle_days: int = 14                # 元触发：超过此天数零触发需复核
    meta_stage_idle_days: int = 7           # 元触发：阶段滞留超此天数需复核


@dataclass
class GateContext:
    """decide() 的注入数据（缺省=信息不足→对应门跳过）。
    由调用方在 tick 时按规则填：intent/amount/last_intervention/expected_value。"""
    intent: Optional[str] = None
    amount_yuan: Optional[float] = None
    last_intervention_at: Optional[datetime] = None
    expected_value_yuan: Optional[float] = None
    trigger_kind: str = 'price'             # price | anomaly | meta
    daily_wake_count: int = 0
    change_pct: Optional[float] = None


CONSTITUTIONAL_INTENTS = ('exit_stop',)     # 止损铁律：无条件介入，可突破预算

#: 交易类意图（触发后会走到"下单/改单"）：**必须**有账户归属才能动作。
#: 用途：①规则创建/校验时判定"该规则必须带账户"；②agent 处置时判定"无账户则不得下单"。
#: ⚠️ 不作为投送判据——账户为空是**数据缺陷**，引擎照常唤醒 agent 去补归属，
#: 绝不因为"没账户不能交易"就不叫 agent（那等于把缺陷藏起来，用户 2026-09-11 纠正）。
TRADE_INTENTS = ('entry', 'add_position', 't_trade', 'exit_stop', 'exit_take_profit', 'exit_reduce')


#: 意图中文名（错误提示/消息用，避免各处重复硬编码）
TRADE_INTENT_LABELS = {
    'entry': '建仓买入',
    'add_position': '加仓',
    't_trade': '做T',
    'exit_stop': '止损卖出',
    'exit_take_profit': '止盈卖出',
    'exit_reduce': '减仓卖出',
}


def is_trade_intent(intent) -> bool:
    """交易类意图判定（会走到下单的那一类）"""
    return str(intent or '').strip() in TRADE_INTENTS


def intent_of(rule) -> str:
    """公开别名：规则意图推导（规则守卫与运行时必须同源）"""
    return _intent_of(rule)


def normalize_symbol(symbol) -> str:
    return str(symbol or '').split('.')[0].strip()


def direction_of(condition) -> str:
    params = (condition or {}).get('params') or {}
    d = params.get('direction')
    if d in ('above', 'below'):
        return d
    return str((condition or {}).get('type') or 'unknown')


def dedup_key(rule, condition):
    return (normalize_symbol(getattr(rule, 'symbol', '')), direction_of(condition))


def action_hint_of(rule) -> dict:
    ah = getattr(rule, 'action_hint', None)
    return ah if isinstance(ah, dict) else {}


def _intent_of(rule) -> str:
    """规则意图：优先读 intent 字段；缺省时按 action_on_trigger 推断，
    防止「声明了 buy/sell 但没写 intent」的规则被误归趋势观察而进不了五道门。"""
    intent = str(getattr(rule, 'intent', '') or '').strip()
    if intent:
        return intent
    ah = action_hint_of(rule)
    act = str(ah.get('action_on_trigger') or '').lower()
    if act == 'buy':
        return 'entry'
    if act == 'sell':
        for c in (getattr(rule, 'conditions', None) or []):
            if isinstance(c, dict) and c.get('type') == 'pnl_pct':
                d = (c.get('params') or {}).get('direction')
                if d == 'below':
                    return 'exit_stop'
                if d == 'above':
                    return 'exit_take_profit'
        return 'exit_reduce'
    return 'trend_observe'


def decide(rule, condition, escalated: bool = False,
           gate: Optional[GateContext] = None, cfg: Optional[InterventionConfig] = None):
    """介入判据（RFC 014 v3 §3.2）。返回 (disposition, reason)。"""
    cfg = cfg or InterventionConfig()
    gate = gate or GateContext()
    intent = _intent_of(rule)
    ah = action_hint_of(rule)
    act = str(ah.get('action_on_trigger') or '').lower()
    level = str(ah.get('trigger_level') or '').upper()

    # 0. 宪法豁免：无条件介入，可突破预算
    if intent in CONSTITUTIONAL_INTENTS:
        return DISPOSITION_ESCALATED, '宪法动作（' + intent + '）：无条件介入，不受经济性判断与预算豁免'

    # 1. 预算门：当日介入预算耗尽 → 非宪法动作进日终汇总
    if gate.daily_wake_count >= cfg.daily_budget:
        return DISPOSITION_AUTO_OBSERVED, '预算门：当日介入预算已耗尽（§3.3）→ 进日终汇总'

    # 2. 引擎升级（escalation_policy 命中）→ 摘要队列
    if escalated:
        return DISPOSITION_ESCALATED, '升级策略命中（L1→L2）→ 进 agent 摘要队列'

    # 3. 规则分级 L2 → 摘要队列（买卖节点必须 agent 终判）
    if level == 'L2':
        return DISPOSITION_ESCALATED, '规则分级 L2 行动层（买卖节点）→ 进 agent 摘要队列'

    # 4. 元触发轻门（不适用金额门/节点门）
    if gate.trigger_kind == 'meta':
        return _meta_gate(rule, gate, cfg)

    # 5. 价格触发五道门
    # ①意图门：趋势观察类不介入（只更新认识）
    if intent == 'trend_observe' or act in ('observe', 'message'):
        return DISPOSITION_AUTO_OBSERVED, '观察类（意图门）→ 归档记录，不唤醒 agent'

    # ②金额门：动作影响 < 账户 1% 不值得介入
    amount = gate.amount_yuan
    threshold = cfg.account_total_yuan * cfg.amount_threshold_pct
    if amount is not None and amount < threshold:
        return DISPOSITION_AUTO_OBSERVED, '金额门：动作影响 %.0f 元 < 阈值 %.0f 元 → 做对了也不值一次介入' % (amount, threshold)

    # ③增量门：同标的同议题冷却窗内不重复介入
    if gate.last_intervention_at is not None:
        if (datetime.now() - gate.last_intervention_at).total_seconds() < cfg.same_topic_cooldown_sec:
            return DISPOSITION_AUTO_OBSERVED, '增量门：同标的同议题 4h 内已介入过 → 不重复唤醒'

    # ⑤经济门：期望收益 < k × 介入成本 → 不介入
    if gate.expected_value_yuan is not None:
        if gate.expected_value_yuan < cfg.k_economic * cfg.wake_cost_yuan:
            return DISPOSITION_AUTO_OBSERVED, '经济门：期望收益 < %.1f × 介入成本 → 不介入' % cfg.k_economic

    # 全过 → 买卖动作进摘要队列，其余待处置
    if act in ('buy', 'sell'):
        return DISPOSITION_ESCALATED, '价格触发过五道门（' + act + '）→ 进 agent 摘要队列'
    return DISPOSITION_PENDING, '过五道门但未声明动作 → 待处置（人工/agent 复核）'


def _meta_gate(rule, gate: GateContext, cfg: InterventionConfig):
    """元触发轻门（§3.1 C 类）：只过增量门与经济门，不适用金额门/节点门。"""
    if gate.last_intervention_at is not None:
        if (datetime.now() - gate.last_intervention_at).total_seconds() < cfg.same_topic_cooldown_sec:
            return DISPOSITION_AUTO_OBSERVED, '元触发增量门：同标的 4h 内已复核过，跳过'
    return DISPOSITION_META_REVIEW, '元触发（频次/静默/滞留/到期）过轻门 → 进复核队列'


def evaluate_meta_trigger(kind: str, burst_count: int = 0, idle_days: float = 0,
                          stage_idle_days: float = 0, days_to_expiry: float = 0,
                          cfg: Optional[InterventionConfig] = None):
    """元触发判定（RFC 014 v3 §13）。返回 (need_review, reason)。

    kind: burst（一直响）/ idle（一直不响）/ stage（阶段滞留）/ expiry（快到期）
    """
    cfg = cfg or InterventionConfig()
    if kind == 'burst' and burst_count >= cfg.meta_burst_per_day:
        return True, '频次超限：单日触发 %d 次 ≥ %d → 规则需复核（阈值失真/该转阶段/该取消）' % (burst_count, cfg.meta_burst_per_day)
    if kind == 'idle' and idle_days >= cfg.meta_idle_days:
        return True, '静默超时：%.0f 天零触发 ≥ %d 天 → 复核（续期/调整/取消）' % (idle_days, cfg.meta_idle_days)
    if kind == 'stage' and stage_idle_days >= cfg.meta_stage_idle_days:
        return True, '阶段滞留：停留 %.0f 天 ≥ %d 天 → 复核（推进或回退）' % (stage_idle_days, cfg.meta_stage_idle_days)
    if kind == 'expiry' and days_to_expiry <= 2:
        return True, '规则到期：%.1f 天后过期 → 复核（续期/收摊）' % days_to_expiry
    return False, ''


def is_resolved(disposition: str) -> bool:
    """是否已收敛到终态（处置率统计）。meta_review 与 pending/escalated 一样未收敛。"""
    return disposition in (
        DISPOSITION_AUTO_OBSERVED, DISPOSITION_DEDUPED,
        DISPOSITION_HANDLED, DISPOSITION_IGNORED, DISPOSITION_EXPIRED,
    )

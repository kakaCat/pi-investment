"""盯盘触发处置决策 v2（REQ-f08def P3，RFC 014 v3 §3，2026-09-11，w-c8cae280）

「何时介入」的判据：价格触发五道门 + 元触发轻门 + 宪法豁免 + 每日预算。
纯函数 + 配置注入；数据由调用方（引擎 tick / 复核作业）注入。

**2026-10-07（REQ-261007133807-eda6 t5）**：判定顺序的**唯一事实源**已迁到
`domain/watch/services/escalation_verdict.py` 的 :func:`decide_escalation`
（宪法级 → 预算 → 三条可信路径 → L2 → 元触发 → 五道门 → 兜底）。本模块的 :func:`decide`
改为「Verdict → disposition 字符串」的**映射**，对外签名与文案逐字不变：

  0. 宪法豁免：止损等无条件介入，且可突破预算
  1. 预算门：当日介入预算耗尽 → 非宪法动作进日终汇总
  2. 引擎升级（escalation_policy 命中）→ 摘要队列
  3. 规则分级 L2 → 摘要队列（L2 = 买卖节点，必须 agent 终判）
  4. 元触发轻门：仅增量门+经济门（不适用金额门/节点门）
  5. 价格触发五道门：意图 → 金额 → 增量 → 经济 → 节点

消费侧契约：**理由码**（`EscalationCode`）由裁决出口产出并落 `watch_triggers.escalation_code`；
本模块只回答"落到哪个处置状态"（6 个取值的状态机），两把尺子刻意不合并。

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


def _disposition_map():
    """理由码 → 处置状态（**延迟构造**，见下方注释）。

    为什么不在模块顶层 import `EscalationCode`：`escalation_verdict` 在模块层依赖本模块
    （`GateContext` / `InterventionConfig` / `intent_of` / `CONSTITUTIONAL_INTENTS`），
    顶层互相 import 会成环（半初始化模块 → ImportError）。故第一次用到时再取，
    且**码名只从码表读**（不在本模块手写字符串，避免第二份词表）。
    """
    global _DISPOSITION_BY_CODE
    if _DISPOSITION_BY_CODE is None:
        from domain.watch.services.escalation_verdict import EscalationCode as C
        _DISPOSITION_BY_CODE = {
            C.CONSTITUTIONAL_INTENT: DISPOSITION_ESCALATED,
            C.RULE_EXPLICIT_ESCALATE: DISPOSITION_ESCALATED,
            C.ANOMALY_CHANGE_PCT: DISPOSITION_ESCALATED,
            C.RULE_LEVEL_L2: DISPOSITION_ESCALATED,
            C.GATES_PASSED_ACTION: DISPOSITION_ESCALATED,
            C.META_REVIEW: DISPOSITION_META_REVIEW,
            C.BUDGET_EXHAUSTED: DISPOSITION_AUTO_OBSERVED,
            C.OBSERVE_INTENT: DISPOSITION_AUTO_OBSERVED,
            C.AMOUNT_BELOW_THRESHOLD: DISPOSITION_AUTO_OBSERVED,
            C.SAME_TOPIC_COOLDOWN: DISPOSITION_AUTO_OBSERVED,
            C.ECONOMIC_BELOW_K: DISPOSITION_AUTO_OBSERVED,
            C.SUPPRESSED: DISPOSITION_AUTO_OBSERVED,
            C.PENDING_NO_ACTION: DISPOSITION_PENDING,
            C.DEDUPED: DISPOSITION_DEDUPED,
            C.UNKNOWN: DISPOSITION_PENDING,
        }
    return _DISPOSITION_BY_CODE


#: 理由码 → 处置状态（首次使用时由 _disposition_map() 填充；见其 docstring 说明为何延迟）
_DISPOSITION_BY_CODE = None


def decide(rule, condition, escalated: bool = False,
           gate: Optional[GateContext] = None, cfg: Optional[InterventionConfig] = None,
           escalation_reason: Optional[str] = None, verdict=None):
    """介入判据（RFC 014 v3 §3.2）。返回 (disposition, reason)。

    verdict（2026-10-07 · REQ-261007133807-eda6 t5 新增）：**裁决出口的结果**
    （`escalation_verdict.Verdict`）。给了它就只做映射；没给则内部调裁决出口——
    调用方（engine tick）给，旁路调用方（market_watch_service 等）不给也照常工作。

    escalation_reason（2026-09-14 新增）：引擎升级命中的原始原因。此前 decide()
    只收到 escalated 布尔，固定回一句「升级策略命中（L1→L2）」，使「究竟哪条
    升级路径命中」（频率/价格偏差/核心区域/量能/共振）在库里不可考。
    **兼容保留**：`escalated=True` 且未给 verdict 的调用方仍走该分支（文案逐字不变）。
    """
    cfg = cfg or InterventionConfig()
    gate = gate or GateContext()

    if verdict is None:
        # 判定顺序的唯一事实源（延迟导入避免环，见 _disposition_map）
        from domain.watch.services.escalation_verdict import (
            EscalationCode as C, decide_escalation,
        )
        # 旁路调用方没有 quote/result：异常波动路径自然不命中（与收敛前一致——
        # 收敛前的 decide() 也不评估异常波动，escalated 布尔由调用方给）。
        verdict = decide_escalation(rule, condition, None, None, gate=gate, cfg=cfg)
        # 兼容分支（收敛前顺序：宪法级 → 预算 → escalated → L2 → …）
        if escalated and verdict.code not in (C.CONSTITUTIONAL_INTENT, C.BUDGET_EXHAUSTED):
            detail = f'｜原始原因：{escalation_reason}' if escalation_reason else ''
            return DISPOSITION_ESCALATED, '升级策略命中（L1→L2）→ 进 agent 摘要队列' + detail

    return _disposition_map().get(getattr(verdict, 'code', None), DISPOSITION_PENDING), verdict.reason



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

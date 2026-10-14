"""升级裁决的**词表与结果契约**（REQ-261007133807-eda6 t1）

本模块是「这条盯盘触发为什么叫了 / 没叫 agent」这件事的**唯一事实源**：
卡面路径标签、`quant.watch_triggers.escalation_code` 的落库取值、
`docs/architecture/watch-notification-contract.md` 的判据表全部由这里的码表派生
（改一处必须改另一处 —— 文档判据表一致性由 tests/services/test_watch_contract_parity.py 锁住）。

为什么把码表与结果单独成文件、先于裁决逻辑落地（t1 范围）：
裁决逻辑（`decide_escalation`，t2）与卡面渲染（t9）、落库（t8）都要引用同一批码；
先落契约定死词表，后续卡才有稳定依赖面（本仓「契约定死再写实现」纪律）。

**历史五类升级路径已删除**（REQ-c9f899 t7：触发频率 / 量能异常 / 价格偏差 / 核心区域 /
多规则共振），本模块**不收录**它们 —— 收敛只做收敛与可见化，不复活既有实证不可信的路径。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from domain.watch.models import DEFAULT_ANOMALY_CHANGE_PCT, MetricKind
from domain.watch.services.disposition import (
    CONSTITUTIONAL_INTENTS,
    GateContext,
    InterventionConfig,
    action_hint_of,
    intent_of,
)
from domain.watch.services.metric_contract import require_metric

__all__ = ['EscalationCode', 'Verdict', 'decide_escalation', 'decide_escalation_paths',
           'explain_escalation', 'anomaly_threshold', 'trigger_level_of',
           'should_render_reason',
           'DEFAULT_ANOMALY_CHANGE_PCT']


class EscalationCode:
    """受控理由码（15 值：**叫** agent 的一侧与**没叫**的一侧都在表内）。

    两侧都在表内是刻意的：用户追问的是因果，只记录"叫"的理由等于把成本控制留成黑盒
    （预算门 / 五道门正是"为什么不叫"的答案）。
    """

    # ── 叫 agent 的一侧 ─────────────────────────────────────────
    CONSTITUTIONAL_INTENT = 'CONSTITUTIONAL_INTENT'   # 宪法级意图（exit_stop 止损铁律）
    RULE_EXPLICIT_ESCALATE = 'RULE_EXPLICIT_ESCALATE' # 规则显式声明 escalate=true
    ANOMALY_CHANGE_PCT = 'ANOMALY_CHANGE_PCT'         # 异常波动达阈值
    RULE_LEVEL_L2 = 'RULE_LEVEL_L2'                   # 规则分级 L2（买卖节点需拍板）
    META_REVIEW = 'META_REVIEW'                       # 元触发过轻门（进复核队列）
    GATES_PASSED_ACTION = 'GATES_PASSED_ACTION'       # 价格触发过五道门且声明买卖动作

    # ── 没叫 agent 的一侧（含四道门与预算）──────────────────────
    BUDGET_EXHAUSTED = 'BUDGET_EXHAUSTED'             # 当日介入预算已耗尽
    OBSERVE_INTENT = 'OBSERVE_INTENT'                 # 观察类（意图门）
    AMOUNT_BELOW_THRESHOLD = 'AMOUNT_BELOW_THRESHOLD' # 金额门未过
    SAME_TOPIC_COOLDOWN = 'SAME_TOPIC_COOLDOWN'       # 增量门（同标的同议题 4h 内）
    ECONOMIC_BELOW_K = 'ECONOMIC_BELOW_K'             # 经济门未过
    PENDING_NO_ACTION = 'PENDING_NO_ACTION'           # 过门但未声明动作（待处置）

    # ── 裁决之后的覆盖（去重 / 抑噪）────────────────────────────
    DEDUPED = 'DEDUPED'                               # 去重合并
    SUPPRESSED = 'SUPPRESSED'                         # 抑噪期归档

    # ── 未接入 ─────────────────────────────────────────────────
    UNKNOWN = 'UNKNOWN'                               # 未接入/输入缺省（禁止臆造理由）

    #: 码 → 命中路径标签（人读；**码的静态属性**，不落库 —— 单开一列必然两份漂移）
    PATH_LABEL = {
        CONSTITUTIONAL_INTENT: '宪法级动作',
        RULE_EXPLICIT_ESCALATE: '规则显式升级',
        ANOMALY_CHANGE_PCT: '异常波动',
        RULE_LEVEL_L2: '规则分级 L2',
        META_REVIEW: '元触发复核',
        GATES_PASSED_ACTION: '价格触发过门',
        BUDGET_EXHAUSTED: '预算门',
        OBSERVE_INTENT: '观察类',
        AMOUNT_BELOW_THRESHOLD: '金额门',
        SAME_TOPIC_COOLDOWN: '增量门',
        ECONOMIC_BELOW_K: '经济门',
        PENDING_NO_ACTION: '待处置',
        DEDUPED: '去重合并',
        SUPPRESSED: '抑噪归档',
        UNKNOWN: '未接入',
    }

    #: 全部码（顺序 = 词表定义顺序；`ALL` 由 PATH_LABEL 派生，不另行手写一份）
    ALL = tuple(PATH_LABEL)

    #: 会打断 agent 的码（`should_wake` 由它派生 —— 码与是否叫不许各说各话）
    WAKING = frozenset({
        CONSTITUTIONAL_INTENT,
        RULE_EXPLICIT_ESCALATE,
        ANOMALY_CHANGE_PCT,
        RULE_LEVEL_L2,
        META_REVIEW,
        GATES_PASSED_ACTION,
    })

    #: **三条可信路径**的码（REQ-c9f899 t7 收敛后仅存的三条）。
    #: 用途：卡面/落库要区分"因升级路径而叫"与"因 L2 分级或过门而叫"——
    #: 既有 `escalation_reason` 的语义就是前者（历史调用方据此选标签与是否简化预案），
    #: 故这里必须有一个单一事实源，而不是在引擎里再写一遍三个码名。
    PATHS = frozenset({
        RULE_EXPLICIT_ESCALATE,
        CONSTITUTIONAL_INTENT,
        ANOMALY_CHANGE_PCT,
    })

    @classmethod
    def is_valid(cls, code) -> bool:
        """是否受控码（空白/None/未收录一律 False，**不抛错**）。"""
        return str(code or '').strip().upper() in cls.PATH_LABEL

    @classmethod
    def normalize(cls, code) -> str:
        """归一为受控码；未收录一律回落 ``UNKNOWN``（原文由调用方留在 note 里）。"""
        raw = str(code or '').strip().upper()
        return raw if raw in cls.PATH_LABEL else cls.UNKNOWN

    @classmethod
    def label_of(cls, code) -> str:
        """码 → 路径标签；未收录时返回码本身（**不臆造**一句像理由的话）。"""
        raw = str(code or '').strip().upper()
        return cls.PATH_LABEL.get(raw, str(code or '').strip())

    @classmethod
    def wakes(cls, code) -> bool:
        """该码是否意味着打断 agent（与 `Verdict.should_wake` 同源）。"""
        return cls.normalize(code) in cls.WAKING


@dataclass(frozen=True)
class Verdict:
    """一次裁决的结果（不可变值对象）。

    字段：
      · ``should_wake`` —— 是否打断 agent。**由 code 派生**（构造时按码表强制归一），
        避免调用方"码说不叫、布尔说叫"这种自相矛盾的裁决。
      · ``code``        —— 受控理由码（未收录一律归一为 ``UNKNOWN``，原文留在 ``note``）。
      · ``reason``      —— 人话理由（进卡面与库；被覆盖时含「原判：…」段）。
      · ``path``        —— 命中路径标签（缺省按码表派生）。
      · ``note``        —— 附加说明（如"规则已关闭自动升级"/未受控码原文）；空则卡面不渲染。

    为什么 frozen：裁决一旦产生即事实；去重/抑噪覆盖必须经 :meth:`overridden` 产出**新实例**，
    使"本来会叫、被压掉了"这件事可追溯（原判保留在 reason 里）。
    """

    should_wake: bool
    code: str
    reason: str
    path: str = ''
    note: str = field(default='')

    def __post_init__(self):
        raw = self.code
        code = EscalationCode.normalize(raw)
        if code == EscalationCode.UNKNOWN and str(raw or '').strip():
            # 未受控码：如实留存原文，绝不静默丢弃（也绝不据此臆造理由）
            text = '未受控码原文：' + str(raw).strip()
            object.__setattr__(self, 'note', (self.note + '；' + text) if self.note else text)
        object.__setattr__(self, 'code', code)
        object.__setattr__(self, 'path', self.path or EscalationCode.label_of(code))
        object.__setattr__(self, 'should_wake', code in EscalationCode.WAKING)

    def overridden(self, code: str, reason: str) -> 'Verdict':
        """裁决之后的覆盖（去重 / 抑噪）：返回**新实例**，原判写进理由文本。

        为什么保留原判：被去重压掉的触发往往本来会被判成"叫 agent"（例如异常波动），
        只留一个 ``DEDUPED`` 会让"成本控制压掉了什么"再次不可见。
        """
        original = str(self.reason or '').strip()
        text = str(reason or '').strip()
        if original:
            text = (text + '；原判：' + original) if text else ('原判：' + original)
        return Verdict(
            should_wake=EscalationCode.wakes(code),
            code=code,
            reason=text,
            note=self.note,
        )


# ── 判据实现（顺序表见模块头；文案逐字沿用收敛前两处判定）──────────────────

# `DEFAULT_ANOMALY_CHANGE_PCT` 由 domain.watch.models 导入即在本模块可用（不再手写 5.0）：
# 定义落在 models 是为了避免「models ← checker/verdict」的循环导入，值仍只有一处。

#: 只有 L0/L1 走三条可信路径（L2 直接由分级判定，收敛前 EscalationCoordinator 同款短路）
_PATH_LEVELS = ('L0', 'L1')


def _action_hint(rule) -> dict:
    """action_hint 归一为 dict（容忍 JSONB 取回的字符串形态，与收敛前 checker 同款）。"""
    ah = getattr(rule, 'action_hint', None)
    if isinstance(ah, str):
        import json
        try:
            ah = json.loads(ah)
        except Exception:
            return {}
    return ah if isinstance(ah, dict) else {}


def _trigger_level(rule) -> str:
    """规则分级（缺省 L1，与收敛前 coordinator 一致）。"""
    return str(_action_hint(rule).get('trigger_level') or 'L1')


def trigger_level_of(rule) -> str:
    """公开别名：调用方（引擎/协调器）取规则分级用，避免各自再解析一次 action_hint。"""
    return _trigger_level(rule)


def _auto_escalate_off(policy) -> bool:
    """规则是否显式关闭自动升级（只关三条路径，不影响宪法级与 L2）。"""
    if isinstance(policy, dict):
        return bool(policy) and policy.get('auto_escalate', True) is False
    if policy is not None:
        return getattr(policy, 'auto_escalate', True) is False
    return False


def anomaly_threshold(policy, default_pct: Optional[float] = None) -> float:
    """生效的异常波动阈值：规则覆写优先 → 调用方给的缺省 → 全局缺省常量。"""
    value = None
    if isinstance(policy, dict):
        value = policy.get('anomaly_change_pct')
    elif policy is not None:
        value = getattr(policy, 'anomaly_change_pct', None)
    try:
        if value is not None:
            return float(value)
    except (TypeError, ValueError):
        pass
    if default_pct is not None:
        try:
            return float(default_pct)
        except (TypeError, ValueError):
            pass
    return DEFAULT_ANOMALY_CHANGE_PCT


def _change_pct(condition, quote, result) -> Optional[float]:
    """涨跌幅取数：``pct_change`` 条件走 metric 契约；其余用行情 change_pct（缺则按昨收算）。"""
    ctype = str((condition or {}).get('type') or '')
    if ctype == 'pct_change':
        require_metric(result, {MetricKind.PCT_CHANGE}, 'decide_escalation')
        return getattr(result, 'value', None)
    pct = getattr(quote, 'change_pct', None)
    if pct is not None:
        return pct
    prev = getattr(quote, 'prev_close', None)
    price = getattr(quote, 'price', None)
    try:
        if prev:
            return (float(price) - float(prev)) / float(prev) * 100
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return None


def decide_escalation_paths(rule, condition: dict, quote, result,
                            default_anomaly_pct: Optional[float] = None) -> Optional[Verdict]:
    """三条可信路径：规则显式 escalate / 宪法级 ``exit_stop`` / 异常波动达阈值。

    只对 ``L0/L1`` 生效（``L2`` 由分级判定接管）；规则显式 ``auto_escalate=false`` 时整段短路。
    无命中返回 ``None``（**不含预算门与五道门** —— 那属 :func:`decide_escalation` 的后续步骤）。

    ``default_anomaly_pct``：调用方实例级缺省阈值（兼容壳 ``EscalationChecker(anomaly_change_pct=…)``
    的既有语义——实例值优先于全局缺省，但**规则覆写仍然最高**）。
    """
    policy = getattr(rule, 'escalation_policy', None)
    if _auto_escalate_off(policy):
        return None
    if _trigger_level(rule) not in _PATH_LEVELS:
        return None

    if _action_hint(rule).get('escalate') is True:
        return Verdict(True, EscalationCode.RULE_EXPLICIT_ESCALATE,
                       '规则显式声明升级（action_hint.escalate=true）：命中即交 agent 处置')

    if intent_of(rule) in CONSTITUTIONAL_INTENTS:
        return Verdict(True, EscalationCode.CONSTITUTIONAL_INTENT,
                       '宪法级动作（exit_stop）：止损铁律，无条件交 agent 处置')

    pct = _change_pct(condition, quote, result)
    if pct is None:
        return None
    threshold = anomaly_threshold(policy, default_anomaly_pct)
    if abs(float(pct)) >= threshold:
        return Verdict(True, EscalationCode.ANOMALY_CHANGE_PCT,
                       '异常波动：涨跌幅 %.2f%% 达到阈值 %.1f%%' % (float(pct), threshold))
    return None


def decide_escalation(rule, condition: dict, quote, result,
                      gate: Optional[GateContext] = None,
                      cfg: Optional[InterventionConfig] = None) -> Verdict:
    """**唯一裁决出口**：这条触发要不要打断 agent（顺序见 design/architecture.md 裁决顺序表）。

    顺序自上而下、先命中先返回，与收敛前 ``EscalationChecker`` + ``disposition.decide``
    两处判定的**合成语义逐条等价**（顺序不得调换，调换即行为变更）：
    宪法级 → 预算 → 三条可信路径 → L2 → 元触发 → 意图门 → 金额门 → 增量门 → 经济门 → 动作。
    """
    cfg = cfg or InterventionConfig()
    gate = gate or GateContext()
    intent = intent_of(rule)
    level = _trigger_level(rule)

    # 1 宪法级：不看 auto_escalate、不看预算（收敛前 decide 规则 0）
    if intent in CONSTITUTIONAL_INTENTS:
        return Verdict(True, EscalationCode.CONSTITUTIONAL_INTENT,
                       '宪法动作（exit_stop）：无条件介入，不受经济性判断与预算豁免')

    # 2 预算门（收敛前 decide 规则 1）
    if gate.daily_wake_count >= cfg.daily_budget:
        return Verdict(False, EscalationCode.BUDGET_EXHAUSTED,
                       '预算门：当日介入预算已耗尽（§3.3）→ 进日终汇总')

    # 3/4 三条可信路径（规则显式 / 宪法级 / 异常波动）
    hit = decide_escalation_paths(rule, condition, quote, result)
    if hit is not None:
        return hit

    # 5 规则分级 L2（收敛前 decide 规则 3）
    if str(level).strip().upper() == 'L2':
        return Verdict(True, EscalationCode.RULE_LEVEL_L2,
                       '规则分级 L2 行动层（买卖节点）→ 进 agent 摘要队列')

    # 6 元触发轻门（收敛前 decide 规则 4 / _meta_gate）
    if gate.trigger_kind == 'meta':
        if gate.last_intervention_at is not None:
            delta = (datetime.now() - gate.last_intervention_at).total_seconds()
            if delta < cfg.same_topic_cooldown_sec:
                return Verdict(False, EscalationCode.SAME_TOPIC_COOLDOWN,
                               '元触发增量门：同标的 4h 内已复核过，跳过')
        return Verdict(True, EscalationCode.META_REVIEW,
                       '元触发（频次/静默/滞留/到期）过轻门 → 进复核队列')

    act = str(_action_hint(rule).get('action_on_trigger') or '').lower()

    # 7 意图门：观察类不介入（只更新认识）
    if intent == 'trend_observe' or act in ('observe', 'message'):
        return Verdict(False, EscalationCode.OBSERVE_INTENT,
                       '观察类（意图门）→ 归档记录，不唤醒 agent')

    # 8 金额门：动作影响 < 账户 × 阈值
    amount = gate.amount_yuan
    threshold = cfg.account_total_yuan * cfg.amount_threshold_pct
    if amount is not None and amount < threshold:
        return Verdict(False, EscalationCode.AMOUNT_BELOW_THRESHOLD,
                       '金额门：动作影响 %.0f 元 < 阈值 %.0f 元 → 做对了也不值一次介入' % (amount, threshold))

    # 9 增量门：同标的同议题冷却窗内不重复介入
    if gate.last_intervention_at is not None:
        delta = (datetime.now() - gate.last_intervention_at).total_seconds()
        if delta < cfg.same_topic_cooldown_sec:
            return Verdict(False, EscalationCode.SAME_TOPIC_COOLDOWN,
                           '增量门：同标的同议题 4h 内已介入过 → 不重复唤醒')

    # 10 经济门：期望收益 < k × 介入成本
    if gate.expected_value_yuan is not None:
        if gate.expected_value_yuan < cfg.k_economic * cfg.wake_cost_yuan:
            return Verdict(False, EscalationCode.ECONOMIC_BELOW_K,
                           '经济门：期望收益 < %.1f × 介入成本 → 不介入' % cfg.k_economic)

    # 11 全过 → 声明买卖动作的进摘要队列
    if act in ('buy', 'sell'):
        return Verdict(True, EscalationCode.GATES_PASSED_ACTION,
                       '价格触发过五道门（' + act + '）→ 进 agent 摘要队列')

    # 12 兜底：过门但未声明动作 → 待处置
    return Verdict(False, EscalationCode.PENDING_NO_ACTION,
                   '过五道门但未声明动作 → 待处置（人工/agent 复核）')


def should_render_reason(code, reason) -> bool:
    """卡面是否渲染「升级原因」行（**两条渲染路径共用的同一判据**，REQ-261007133807-eda6 t9/t13）。

    渲染：
      ① 有人话理由（升级路径命中，或被去重/抑噪覆盖时留下的「原判」）；
      ② 码本身意味着**叫了 agent**（`WAKING`）——例如规则本来就是 L2；
      ③ 码未收录（响亮：显示事实比隐藏更安全）。
    不渲染：已知的「没叫」码且无理由（观察类 / 预算门 / 四道门 …）。

    为什么：卡面是**打扰物**——把「为什么没叫你」写满卡片只会变成噪音；
    那些理由由 FR-2 落库（`escalation_code` / `escalation_reason`）负责可查。
    """
    text = str(reason or '').strip()
    if text:
        return True
    raw = str(code or '').strip()
    if not raw:
        return False
    if not EscalationCode.is_valid(raw):
        return True
    return EscalationCode.wakes(raw)


def explain_escalation(rule) -> str:
    """规则侧人话说明：**这条规则在什么条件下会叫我**（IF-2 / FR-4）。

    用途：`GET /api/watch/rules` 的 `escalation_explain` 字段——让"何时叫我"在规则上看得见，
    不必读代码、不必猜默认值。**如实**：策略未声明就写「未声明（按默认口径）」，不假装已显式声明。
    """
    policy = getattr(rule, 'escalation_policy', None)
    level = _trigger_level(rule)
    intent = intent_of(rule)
    declared = policy is not None and (not isinstance(policy, dict) or bool(policy))

    if str(level).strip().upper() == 'L2':
        sentence = '无条件叫我（买卖节点需拍板）'
    elif not declared:
        sentence = ('策略未声明（按默认口径：涨跌幅 ≥ %.1f%% 时会叫我）'
                    % DEFAULT_ANOMALY_CHANGE_PCT)
    elif _auto_escalate_off(policy):
        sentence = '已关闭自动升级：三条升级路径不生效，但止损与 L2 分级仍会叫我'
    elif _action_hint(rule).get('escalate') is True:
        sentence = '规则显式声明：命中即叫我（不看阈值）'
    else:
        threshold = anomaly_threshold(policy)
        # 「覆写」只在**真的偏离全局缺省**时才算：default() 写下的显式 5.0 与缺省同值，
        # 说成"规则覆写阈值"会让用户以为有人特意调过（如实优先于措辞漂亮）。
        value = (policy.get('anomaly_change_pct') if isinstance(policy, dict)
                 else getattr(policy, 'anomaly_change_pct', None))
        try:
            overridden = value is not None and float(value) != DEFAULT_ANOMALY_CHANGE_PCT
        except (TypeError, ValueError):
            overridden = False
        sentence = ('会自动叫我：涨跌幅 ≥ %.1f%%%s'
                    % (threshold, '（规则覆写阈值）' if overridden else '（按缺省阈值）'))

    text = '%s 规则｜%s' % (level, sentence)
    declared_intent = str(getattr(rule, 'intent', '') or '').strip()
    if declared_intent == 'trend_observe':
        text += '｜注：观察类规则仅知悉，不因动作门槛叫我'
    elif not declared_intent:
        # 未声明意图 ≠ 声明为观察类：引擎按 trend_observe 归一，说明必须如实区分这两件事
        text += '｜注：未声明意图（引擎按观察类归一，仅知悉）'
    return text

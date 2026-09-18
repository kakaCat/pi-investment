"""升级检查器领域服务（REQ-c9f899 t7 收敛，2026-09-18）

「什么时候把一条 L0/L1 触发交给 agent」——收敛后只剩三条**可信**路径：

  1) 规则显式声明：action_hint.escalate is True（规则作者说了算）
  2) 宪法级：intent == 'exit_stop'（止损铁律，无条件）
  3) 异常波动：|涨跌幅| ≥ 阈值（默认 5.0，按 metric 取数）

已删除（历史五类，均经实证不可信或无人维护）：
  · 触发频率 —— last_triggered 是覆盖写、无法累计；且「响得多」不是叫 agent 交易的理由。
    该语义**改写为规则自愈**（R6）：反复触发去修规则，不是去下单。
    计数能力保留在 StateManager（供自愈使用），本服务不再消费。
  · 量能异常 —— 不校验 metric，把 price_break 的现价当量比（线上 19 条假「量能异常」，
    且真放量反而判不出）。真放量应由 volume_surge 条件本身表达。
  · 价格偏差 —— 「预案位失效」属规则体检范畴（提请退役/调参），不该每触发一次就升级。
  · 核心区域 —— 需人工维护区间，线上无人填写。
  · 多规则共振 —— 统计口径脆弱且与去重合并语义重叠，价值未验证。

消费侧契约（t2）：本服务读 result.value 前必须先声明期望 metric（require_metric），
不符即响亮抛错——这是「现价当量比」不再复发的机制保证。
"""
from typing import Optional

# QuoteData / WatchRule 原先由本模块再导出（domain.watch.services.__init__ 与既有 importer 依赖），
# 本轮收敛保留再导出，避免破坏既有导入路径。
from domain.watch.models import MetricKind, QuoteData, WatchRule  # noqa: F401
from domain.watch.services.metric_contract import require_metric

__all__ = ['EscalationChecker', 'QuoteData', 'WatchRule',
           'DEFAULT_ANOMALY_CHANGE_PCT', 'CONSTITUTIONAL_INTENTS']

#: 异常波动阈值（%）：|涨跌幅| 达到即升级；可按规则覆写 escalation_policy.anomaly_change_pct
DEFAULT_ANOMALY_CHANGE_PCT = 5.0

#: 宪法级意图：无条件升级（预算豁免由 disposition 的宪法豁免承载）
CONSTITUTIONAL_INTENTS = ('exit_stop',)


class EscalationChecker:
    """升级检查器（三条可信路径；无可信路径命中即不打扰 agent）"""

    def __init__(self, anomaly_change_pct: Optional[float] = None):
        self.anomaly_change_pct = (
            float(anomaly_change_pct) if anomaly_change_pct is not None
            else DEFAULT_ANOMALY_CHANGE_PCT)

    def should_escalate(self, rule, condition: dict, quote, result,
                        recent_trigger_count: int = 0,
                        concurrent_trigger_count: int = 0) -> Optional[str]:
        """检查是否应升级，返回原因（None=不升级）

        recent_trigger_count / concurrent_trigger_count 为**兼容参数**，不参与判定
        （原频率/共振路径已删除；触发计数改供规则自愈 R6 使用）。
        """
        policy = getattr(rule, 'escalation_policy', None)
        if isinstance(policy, dict):
            if policy and policy.get('auto_escalate', True) is False:
                return None
        elif policy is not None and getattr(policy, 'auto_escalate', True) is False:
            return None

        reason = self._explicit_declaration(rule)
        if reason:
            return reason

        if self._intent_of(rule) in CONSTITUTIONAL_INTENTS:
            return '宪法级动作（exit_stop）：止损铁律，无条件交 agent 处置'

        return self._check_anomaly(rule, condition, quote, result)

    # ── 内部 ──────────────────────────────────────────────────
    @staticmethod
    def _action_hint(rule) -> dict:
        ah = getattr(rule, 'action_hint', None)
        if isinstance(ah, str):
            import json
            try:
                ah = json.loads(ah)
            except Exception:
                return {}
        return ah if isinstance(ah, dict) else {}

    def _explicit_declaration(self, rule) -> Optional[str]:
        if self._action_hint(rule).get('escalate') is True:
            return '规则显式声明升级（action_hint.escalate=true）：命中即交 agent 处置'
        return None

    @classmethod
    def _intent_of(cls, rule) -> str:
        intent = str(getattr(rule, 'intent', '') or '').strip()
        if intent:
            return intent
        return str(cls._action_hint(rule).get('action_on_trigger') or '').lower()

    def _threshold(self, policy) -> float:
        value = None
        if isinstance(policy, dict):
            value = policy.get('anomaly_change_pct')
        elif policy is not None:
            value = getattr(policy, 'anomaly_change_pct', None)
        try:
            return float(value) if value is not None else self.anomaly_change_pct
        except (TypeError, ValueError):
            return self.anomaly_change_pct

    def _check_anomaly(self, rule, condition, quote, result) -> Optional[str]:
        """异常波动判定（metric 契约：pct_change 条件的 value 必须是涨跌幅）"""
        ctype = str((condition or {}).get('type') or '')
        if ctype == 'pct_change':
            require_metric(result, {MetricKind.PCT_CHANGE}, '_check_anomaly')
            pct = getattr(result, 'value', None)
        else:
            pct = getattr(quote, 'change_pct', None)
            if pct is None:
                prev = getattr(quote, 'prev_close', None)
                price = getattr(quote, 'price', None)
                try:
                    if prev:
                        pct = (float(price) - float(prev)) / float(prev) * 100
                except (TypeError, ValueError, ZeroDivisionError):
                    pct = None

        if pct is None:
            return None
        threshold = self._threshold(getattr(rule, 'escalation_policy', None))
        if abs(float(pct)) >= threshold:
            return '异常波动：涨跌幅 %.2f%% 达到阈值 %.1f%%' % (float(pct), threshold)
        return None

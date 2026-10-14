"""处置决策引擎（RFC 014 v3 重构 P1，2026-09-14）

把「组装 GateContext + 调用 domain decide()」从 WatchEngine 剥出。

为何独立：金额门/增量门/经济门/预算门的输入来自外部（持仓市值、账户总资产
provider），此前与触发主流程混在引擎里，只能通过整体 tick 间接验证；提取后
可用 fake provider 直测。

分层：**判定规则本身仍在 domain/watch/services/disposition.decide()**（纯函数）。
本类只做上下文组装与依赖注入，不复制判定逻辑——避免出现第二份真相。
"""
from typing import Optional

from domain.watch.services.disposition import (
    GateContext, InterventionConfig, decide as decide_disposition, normalize_symbol,
)


class DispositionEngine:
    """介入判据的上下文组装与调用"""

    def __init__(self, state, position_value_provider=None,
                 account_total_provider=None, cfg: Optional[InterventionConfig] = None):
        self.state = state
        self._position_value_provider = position_value_provider
        self._account_total_provider = account_total_provider
        self.cfg = cfg or InterventionConfig()

    # ── 外部依赖取值（失败一律 None → 对应门跳过）──────────────
    def position_value(self, rule) -> Optional[float]:
        if self._position_value_provider is None:
            return None
        try:
            return self._position_value_provider(rule)
        except Exception:
            return None

    def account_total(self, rule=None) -> Optional[float]:
        # 2026-09-13（w-c8cae280）：透传规则，让金额门按规则归属账户取值。
        if self._account_total_provider is None:
            return None
        try:
            return self._account_total_provider(rule)
        except Exception:
            return None

    # ── GateContext 组装 ────────────────────────────────────
    def build_gate(self, rule, cond, quote) -> GateContext:
        '''构建介入判据上下文（RFC 014 v3 §3.2）。数据不足时留 None → 对应门跳过。'''
        ah = rule.action_hint if isinstance(getattr(rule, 'action_hint', None), dict) else {}
        intent = str(getattr(rule, 'intent', '') or ah.get('action_on_trigger') or '').strip()
        norm = normalize_symbol(rule.symbol)
        topic = intent or ah.get('action_on_trigger') or 'unknown'
        amount = None
        ev = None
        if intent in ('exit_stop', 'exit_take_profit', 'exit_reduce', 'add_position', 't_trade'):
            # 持仓级动作：金额 = 持仓市值
            amount = self.position_value(rule)
            if amount is not None:
                ev = amount * 0.05  # 粗估：一个 5% 动作的利害关系
        elif intent == 'entry':
            # 买入意向金额：action_hint.max_position_pct × 账户总资产（若有）
            mpp = ah.get('max_position_pct')
            total = self.account_total(rule)
            if mpp and total:
                amount = float(mpp) / 100.0 * float(total)
                ev = amount * 0.03
        return GateContext(
            intent=intent or None,
            amount_yuan=amount,
            last_intervention_at=self.state.last_intervention.get((norm, topic)),
            expected_value_yuan=ev,
            trigger_kind='price',
            daily_wake_count=self.state.interventions_today,
            change_pct=getattr(quote, 'change_pct', None),
        )

    # ── 判定 ────────────────────────────────────────────────
    def judge(self, rule, cond, quote, result):
        """**唯一裁决**（REQ-261007133807-eda6 t6）：返回 `(Verdict, GateContext)`。

        为什么把 gate 一起返回：裁决与处置必须吃**同一份**上下文（预算计数、金额、冷却窗）——
        各组装一次就可能给出不一致的结论（例如裁决时预算未满、处置时已满）。
        """
        from domain.watch.services.escalation_verdict import decide_escalation
        gate = self.build_gate(rule, cond, quote)
        verdict = decide_escalation(rule, cond, quote, result, gate=gate, cfg=self.cfg)
        return verdict, gate

    def decide(self, rule, cond, quote, escalated: bool = False,
               escalation_reason: Optional[str] = None,
               verdict=None, gate: Optional[GateContext] = None):
        """返回 (disposition, reason)；判定规则全部来自 domain 层。

        `verdict`（2026-10-07 · REQ-261007133807-eda6 t6 新增）：由 :meth:`judge` 产出的裁决；
        给了就只做映射（`gate` 可一并传入以免重复组装），没给则照旧走兼容分支
        （`escalated` + `escalation_reason`，旁路调用方不受影响）。
        """
        if gate is None:
            gate = self.build_gate(rule, cond, quote)
        return decide_disposition(rule, cond, escalated=escalated, gate=gate,
                                  cfg=self.cfg, escalation_reason=escalation_reason,
                                  verdict=verdict)

"""升级协调器（RFC 014 v3 重构 P2，2026-09-14）

把「升级检查」的编排逻辑从 tick 里提出来：
  - 判断规则触发层级（L0/L1/L2）
  - 收集频率与共振统计（委托 StateManager）
  - 调用 domain 的 EscalationChecker
  - 组装 QuoteData

为何独立：升级检查涉及多个数据源（规则属性、状态统计、行情数据），
此前散在 tick 的 20+ 行里；提取后编排清晰，domain 层判定逻辑不变。
"""
import json
from typing import Optional

from domain.watch.services.escalation_checker import EscalationChecker
from domain.watch.models import QuoteData


class EscalationCoordinator:
    """升级判定的数据收集与编排（domain 层判定逻辑不动）"""

    def __init__(self, state, now_fn, escalation_checker: Optional[EscalationChecker] = None):
        self.state = state
        self.now_fn = now_fn
        self.checker = escalation_checker or EscalationChecker()

    def check(self, rule, cond, quote, result, now) -> Optional[str]:
        """返回 escalation_reason（无则 None）。仅 L0/L1 规则会检查。"""
        level = self._get_trigger_level(rule)
        if level not in ('L0', 'L1'):
            return None

        recent_count = self.state.recent_trigger_count(now, rule.id, window_minutes=10)
        concurrent_count = self.state.concurrent_trigger_count(now, rule.symbol, rule.id, window_seconds=60)

        quote_data = QuoteData(
            symbol=rule.symbol,
            price=float(quote.price),
            change_pct=getattr(quote, 'change_pct', None),
            volume=getattr(quote, 'volume', None),
            prev_close=getattr(quote, 'prev_close', None),
        )

        return self.checker.should_escalate(
            rule=rule,
            condition=cond,
            quote=quote_data,
            result=result,
            recent_trigger_count=recent_count,
            concurrent_trigger_count=concurrent_count,
        )

    def _get_trigger_level(self, rule) -> str:
        """获取规则的触发层级（L0/L1/L2）"""
        action_hint = getattr(rule, 'action_hint', None)
        if not action_hint:
            return 'L1'  # 默认 L1
        
        try:
            if isinstance(action_hint, str):
                ah = json.loads(action_hint)
            else:
                ah = action_hint
            return ah.get('trigger_level', 'L1')
        except Exception:
            return 'L1'

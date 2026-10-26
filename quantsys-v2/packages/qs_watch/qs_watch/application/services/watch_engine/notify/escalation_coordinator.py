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

from qs_watch.domain.watch.services.escalation_checker import EscalationChecker
from qs_watch.domain.watch.models import QuoteData


class EscalationCoordinator:
    """升级判定的数据收集与编排（domain 层判定逻辑不动）"""

    def __init__(self, state, now_fn, escalation_checker: Optional[EscalationChecker] = None):
        self.state = state
        self.now_fn = now_fn
        self.checker = escalation_checker or EscalationChecker()

    def check(self, rule, cond, quote, result, now) -> Optional[str]:
        """返回 escalation_reason（无则 None）。

        2026-09-18（REQ-c9f899 t7）：不再收集「频率/共振」计数——那两条路径已删除
        （反复触发改由规则自愈 R6 处置）。触发计数仍由 StateManager 维护，供自愈消费。

        2026-10-22（trigger_level 退役）：原「仅 L0/L1 规则才检查升级」的门槛删除——
        trigger_level 整体退役后，所有规则统一走升级检查（EscalationChecker 内部按
        escalation_policy 判定，与 trigger_level 无关）。
        """
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
        )

    def _get_trigger_level(self, rule) -> str:
        """规则的 trigger_level（L0/L1/L2）——【已退役 2026-10-22】。

        不再有行为分支消费它（decide/resolve_level/escalation 门槛均已删除），
        仅 stages 事件流保留该字段做记录。统一返回 'L1'（原默认值），调用方
        后续可逐步去掉这个字段。
        """
        return 'L1'

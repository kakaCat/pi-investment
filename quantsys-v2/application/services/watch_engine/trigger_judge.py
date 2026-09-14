"""触发判据（RFC 014 v3 重构 P1，2026-09-14）

把「一个条件是否该产出事件」的三段判定从 tick 主循环里提出来：

  1) 未触发   -> 解除闩锁（重新武装，允许下次穿越再报）
  2) 持续成立 -> 电平保持，不重复推送（闩锁挡住）
  3) 冷却窗内 -> 跳过（cooldown_sec，默认 300s）

以及「产出后标记」：写 last_triggered（供冷却）、追加触发事件日志
（频率/共振统计的事实源）、置闩锁。

为何独立：这三段此前内联在 tick 的深层缩进里，既难单测也难阅读；
提取后 tick 只剩编排，判定可独立验证。

行为等价：判定顺序与语义不变。
"""
from datetime import datetime
from typing import Optional

from application.services.watch_engine.conditions import DEFAULT_COOLDOWN_SEC


class TriggerJudge:
    """闩锁 / 冷却 / 触发标记"""

    def __init__(self, state):
        self.state = state

    def should_emit(self, rule_id: int, cond_idx: int, triggered: bool,
                    cond: dict, now: datetime,
                    default_cooldown_sec: Optional[int] = None) -> bool:
        """是否应产出一次触发事件。未触发时会顺带解除闩锁。"""
        key = (rule_id, cond_idx)
        if not triggered:
            # 条件回到未触发状态 → 重新武装（允许下次穿越再报）
            self.state.latched.discard(key)
            return False
        if key in self.state.latched:
            # 条件持续成立（电平保持）→ 不重复推送，等重新武装
            return False
        return not self.in_cooldown(rule_id, cond_idx, cond, now, default_cooldown_sec)

    def in_cooldown(self, rule_id: int, cond_idx: int, cond: dict, now: datetime,
                    default_cooldown_sec: Optional[int] = None) -> bool:
        last = self.state.last_triggered.get((rule_id, cond_idx))
        if last is None:
            return False
        cooldown = cond.get('cooldown_sec', DEFAULT_COOLDOWN_SEC
                            if default_cooldown_sec is None else default_cooldown_sec)
        return (now - last).total_seconds() < cooldown

    def mark_emitted(self, rule_id: int, cond_idx: int, now: datetime,
                     symbol: str) -> None:
        """产出后标记：冷却基准 + 事件日志 + 闩锁"""
        self.state.last_triggered[(rule_id, cond_idx)] = now
        self.state.record_trigger_event(now, rule_id, symbol)
        self.state.latched.add((rule_id, cond_idx))

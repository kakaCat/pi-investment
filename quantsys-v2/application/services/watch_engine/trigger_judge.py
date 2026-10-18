"""触发判据（RFC 014 v3 重构 P1，2026-09-14）

把「一个条件是否该产出事件」的三段判定从 tick 主循环里提出来：

  1) 未触发   -> 解除闩锁（重新武装，允许下次穿越再报）
  2) 持续成立 -> 电平保持，不重复推送（闩锁挡住）
  3) 冷却窗内 -> 跳过（cooldown_sec，默认 300s）

以及「产出后标记」：写 last_triggered（供冷却）、追加触发事件日志
（频率/共振统计的事实源）、置闩锁。

2026-10-16（REQ-261016155500-4f2a wt:engine:1）：
  · 闩锁重新武装加**迟滞带**——price_break 触发后，价格回到阈值附近但未越过
    迟滞带（阈值 ± max(0.5%, 5 个报价单位)）时不重新武装，防阈值抖动复读；
  · 每规则每条件**每日通知上限**（默认 2 次，超限由引擎归档不通知）。

为何独立：这三段此前内联在 tick 的深层缩进里，既难单测也难阅读；
提取后 tick 只剩编排，判定可独立验证。
"""
from datetime import datetime
from typing import Optional

from application.services.watch_engine.conditions import (
    DEFAULT_COOLDOWN_SEC, DEFAULT_DAILY_EMIT_CAP, within_hysteresis_band,
)


class TriggerJudge:
    """闩锁 / 冷却 / 迟滞带 / 每日上限 / 触发标记"""

    def __init__(self, state):
        self.state = state

    def should_emit(self, rule_id: int, cond_idx: int, triggered: bool,
                    cond: dict, now: datetime,
                    default_cooldown_sec: Optional[int] = None,
                    value: Optional[float] = None) -> bool:
        """是否应产出一次触发事件。未触发时会顺带解除闩锁（迟滞带内除外）。"""
        key = (rule_id, cond_idx)
        if not triggered:
            if key in self.state.latched and within_hysteresis_band(cond, value):
                # 迟滞带内：条件回落但价格未真正离开阈值邻域——保持闩锁不重新武装，
                # 否则阈值附近每 300s 复读一张卡（price_break 电平触发的根因噪音）。
                return False
            # 条件回到未触发状态 → 重新武装（允许下次穿越再报）
            self.state.latched.discard(key)
            return False
        if key in self.state.latched:
            # 条件持续成立（电平保持）→ 不重复推送，等重新武装
            return False
        return not self.in_cooldown(rule_id, cond_idx, cond, now, default_cooldown_sec)

    # ── 每日通知上限 ────────────────────────────────────────

    def daily_emit_exceeded(self, rule_id: int, cond_idx: int, now: datetime,
                            cap: int = DEFAULT_DAILY_EMIT_CAP) -> bool:
        """该条件今日已通知次数是否达到上限（超限只归档不通知）。"""
        day, n = self.state.daily_emit_counts.get((rule_id, cond_idx), (None, 0))
        return day == now.date() and n >= cap

    def bump_daily_emit(self, rule_id: int, cond_idx: int, now: datetime) -> None:
        """通知成功后计数 +1（跨天自动归零重计）。"""
        key = (rule_id, cond_idx)
        day, n = self.state.daily_emit_counts.get(key, (None, 0))
        if day != now.date():
            day, n = now.date(), 0
        self.state.daily_emit_counts[key] = (day, n + 1)

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

"""WatchEngine 状态容器（RFC 014 v3 重构 P1，2026-09-14）

把原先散落在 WatchEngine.__init__ 里的 9 个状态字段收敛到一处：
  history / last_triggered / latched / recent_notified / overlap_reported /
  last_intervention / interventions_today / trigger_events / current_date

目的（按重要性）：
  1) **可观测**：snapshot() 给出当前状态规模，线上定位不必再猜；
  2) **可单测**：升级/去重逻辑的输入不再藏在引擎实例里；
  3) 为后续「状态可序列化 / 多实例恢复」留出单一改造面。

硬约束是**行为等价**：本类只搬迁状态与纯查询，不引入新语义；所有时间由
调用方注入（本类不持 now_fn），便于测试构造。
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class TriggerRecord:
    """一次触发的事实（内存态，事件日志的元素）"""
    rule_id: int
    symbol: str
    triggered_at: datetime


class StateManager:
    """盯盘引擎的触发/去重/介入状态。所有方法都是纯内存操作，无 I/O。"""

    def __init__(self, event_retention_min: int = 30, dedup_window_sec: int = 300):
        # 闩锁：条件持续成立时不重复推送，回落后重新武装
        self.latched: Set[Tuple[int, int]] = set()
        # 冷却与频率的「最近一次」：key=(rule_id, cond_idx) -> 时间（覆盖写语义）
        self.last_triggered: Dict[Tuple[int, int], datetime] = {}
        # 价格历史缓冲：symbol -> [(ts, price)]，供 velocity 条件
        self.history: Dict[str, List[Tuple[datetime, float]]] = {}
        # 去重窗：key=(归一化标的, 方向) -> (最近触发时间, 触发记录 id, 规则 id)
        # 带 rule_id 才能分辨「同一条规则多条件重复」（物理去重，保留）
        # 与「跨规则重叠」（业务问题，转治理）
        self.recent_notified: Dict[Tuple[str, str], Tuple[datetime, int, int]] = {}
        # 跨规则重叠已上报的规则对
        self.overlap_reported: Set[Tuple[int, int]] = set()
        # 增量门：key=(归一化标的, 意图) -> 最近介入时间
        self.last_intervention: Dict[Tuple[str, str], datetime] = {}
        # 当日介入计数
        self.interventions_today: int = 0
        # 触发事件日志：频率升级与多规则共振统计的**单一事实源**
        # （2026-09-14：原两条路径共用 last_triggered，而它是覆盖写、且不含 symbol）
        self.trigger_events: List[Tuple[datetime, int, str]] = []
        # 当前状态所属日期（跨天重置判定）
        self.current_date: Optional[date] = None

        # 事件日志保留窗口：需 ≥ 两个统计窗口（频率 10min / 共振 60s）的最大值
        self.event_retention_min = event_retention_min
        self.dedup_window_sec = dedup_window_sec

    # ── 触发事件日志：频率 / 共振统计的唯一事实源 ──────────────
    def record_trigger_event(self, now: datetime, rule_id: int, symbol: str) -> None:
        """记一条触发事件 + 按保留窗口裁剪（调用方保证 now 单调不减）"""
        self.trigger_events.append((now, rule_id, symbol))
        cutoff = now - timedelta(minutes=self.event_retention_min)
        self.trigger_events = [e for e in self.trigger_events if e[0] >= cutoff]

    def recent_trigger_count(self, now: datetime, rule_id: int,
                             window_minutes: int = 10) -> int:
        """该规则近 window_minutes 内的触发次数（含本次触达）"""
        cutoff = now - timedelta(minutes=window_minutes)
        history = sum(1 for t, rid, _ in self.trigger_events
                      if rid == rule_id and t >= cutoff)
        return history + 1  # +1 = 本次：本方法在本次事件写进日志之前被调用

    def concurrent_trigger_count(self, now: datetime, symbol: str, rule_id: int,
                                 window_seconds: int = 60) -> int:
        """同标的近 window_seconds 内触发过的不同规则数（含本次）"""
        cutoff = now - timedelta(seconds=window_seconds)
        rule_ids = {rid for t, rid, sym in self.trigger_events
                    if sym == symbol and t >= cutoff}
        rule_ids.add(rule_id)  # 含本次：共振 = 本条 + 同标的其他规则
        return len(rule_ids)

    # ── 跨天重置 ────────────────────────────────────────────
    def reset_daily(self, now: datetime, active_rule_ids=None, active_symbols=None) -> None:
        """跨天重置。active_* 为 None 时不做按规则/标的的裁剪（测试便利）。"""
        self.current_date = now.date()
        self.latched.clear()
        self.recent_notified.clear()
        self.overlap_reported.clear()
        self.last_intervention.clear()
        self.interventions_today = 0
        self.trigger_events = []
        if active_rule_ids is not None:
            self.last_triggered = {k: v for k, v in self.last_triggered.items()
                                   if k[0] in active_rule_ids}
        if active_symbols is not None:
            self.history = {s: b for s, b in self.history.items()
                            if s in active_symbols}

    # ── 去重窗裁剪 ──────────────────────────────────────────
    def prune_dedup(self, now: datetime, window_sec: Optional[int] = None) -> None:
        """清掉已过期的去重键，避免长跑进程内无界增长"""
        if not self.recent_notified:
            return
        window = self.dedup_window_sec if window_sec is None else window_sec
        cutoff = now.timestamp() - window
        self.recent_notified = {
            k: v for k, v in self.recent_notified.items()
            if v[0].timestamp() >= cutoff
        }

    # ── 可观测 ──────────────────────────────────────────────
    def snapshot(self) -> Dict[str, Any]:
        """状态规模快照（监控/排障用；不暴露内容，避免误读为业务数据）"""
        return {
            'latched': len(self.latched),
            'last_triggered': len(self.last_triggered),
            'history_symbols': len(self.history),
            'dedup_window': len(self.recent_notified),
            'overlap_reported': len(self.overlap_reported),
            'interventions_today': self.interventions_today,
            'trigger_events': len(self.trigger_events),
            'current_date': self.current_date.isoformat() if self.current_date else None,
        }

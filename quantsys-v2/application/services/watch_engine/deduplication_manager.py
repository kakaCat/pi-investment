"""去重管理（RFC 014 v3 重构 P2，2026-09-14）

把「同标的同向窗内合并」+「跨规则重叠转治理」从 tick 里提出来。

语义（不变）：
  - key = (归一化标的, 方向)：同一事件在窗内只通知一次；重复的**仍落库**
    （disposition='deduped' + dup_of），保证账不丢、人不扰；
  - 跨规则重叠（不同规则在同一 key 上重复表达）属**规则该重设**的业务问题：
    除合并通知外另落一条治理项交 agent，同一天同一对规则只报一次。

为何独立：这段含「物理去重（同规则多条件）」与「业务重叠（跨规则）」两种
不同处置，混在 tick 里既难区分也难单测；提取后判定与文案都可直测。
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from domain.watch.services.disposition import dedup_key


@dataclass
class DedupOutcome:
    """一次去重判定的结果"""
    is_duplicate: bool
    key: Tuple[str, str]
    dup_of: Optional[int] = None                    # 合并到的触发 id
    overlap_pair: Optional[Tuple[int, int]] = None  # 本次**首次**发现的跨规则重叠


class DeduplicationManager:
    """同标的同向去重 + 跨规则重叠检测"""

    def __init__(self, state, window_sec: int = 300):
        self.state = state
        self.window_sec = window_sec

    def check(self, rule, cond, now: datetime) -> DedupOutcome:
        """窗内是否已就同一 key 通知过；跨规则重叠顺带返回（每对每天只报一次）"""
        key = dedup_key(rule, cond)
        prev = self.state.recent_notified.get(key)
        if prev is None or (now - prev[0]).total_seconds() >= self.window_sec:
            return DedupOutcome(is_duplicate=False, key=key)
        overlap = None
        prev_rule_id = prev[2] if len(prev) > 2 else None
        if prev_rule_id is not None and prev_rule_id != rule.id:
            pair = tuple(sorted((int(prev_rule_id), int(rule.id))))
            if pair not in self.state.overlap_reported:
                self.state.overlap_reported.add(pair)
                overlap = pair
        return DedupOutcome(is_duplicate=True, key=key, dup_of=prev[1],
                            overlap_pair=overlap)

    def mark_notified(self, rule, cond, now: datetime, trigger_id: int) -> None:
        """记录一次已通知，供后续窗内去重"""
        key = dedup_key(rule, cond)
        self.state.recent_notified[key] = (
            now, trigger_id, int(getattr(rule, 'id', 0) or 0))

    def reason_text(self, outcome: DedupOutcome) -> str:
        """去重合并的处置文案（与原实现逐字一致）"""
        k = outcome.key
        return (f'同标的同向 {self.window_sec}s 内已触发（key={k[0]}/{k[1]}），'
                f'合并到触发 #{outcome.dup_of}，不再重复通知')

    @staticmethod
    def overlap_reason(pair: Tuple[int, int], key: Tuple[str, str]) -> str:
        return ('规则重叠：规则 #%s 与 #%s 在同一事件（%s/%s）上重复表达 → '
                '建议合并为一条多档规则、调阈值或退役其一'
                % (pair[0], pair[1], key[0], key[1]))

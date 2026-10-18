"""overlap_reported 持久化（REQ-261016155500-4f2a wt:engine:3，2026-10-16）

验收锚点：恢复把库里的已上报对灌回内存集合（重启不重复落治理项）；
flush 只在集合变化时写；跨天清空后落库同步清零。
"""
from datetime import datetime

from application.services.watch_engine.state_manager import StateManager

NOW = datetime(2026, 10, 16, 10, 0, 0)


def _store(pairs):
    saved = []

    class _S:
        def load_all(self):
            return []

        def load_dedup(self):
            return []

        def load_events(self, since=None):
            return []

        def load_price_history(self, symbols=None, since=None):
            return []

        def load_overlap_reported(self):
            return pairs

        def save_overlap_reported(self, p):
            saved.append([list(x) for x in p])

    return _S(), saved


def test_restore_loads_reported_pairs():
    store, saved = _store([[10, 20], [5, 6]])
    sm = StateManager(store=store)
    sm.restore_from_store(now=NOW)
    assert sm.overlap_reported == {(10, 20), (5, 6)}
    assert sm._persisted_overlap == {(10, 20), (5, 6)}
    # 恢复后无变化 → flush 不写（零 I/O 节流）
    assert sm._flush_overlap_reported() is None
    assert saved == []


def test_flush_writes_only_on_change():
    store, saved = _store([])
    sm = StateManager(store=store)
    sm.restore_from_store(now=NOW)
    sm.overlap_reported.add((1, 2))
    sm._flush_overlap_reported()
    assert saved == [[[1, 2]]]
    sm._flush_overlap_reported()                     # 无变化 → 不再写
    assert len(saved) == 1


def test_reset_daily_clears_and_flushes_empty():
    store, saved = _store([[1, 2]])
    sm = StateManager(store=store)
    sm.restore_from_store(now=NOW)
    sm.reset_daily(NOW)
    assert sm.overlap_reported == set()
    sm._flush_overlap_reported()
    assert saved == [[]]                             # 清零也落库（防重启回灌旧对）

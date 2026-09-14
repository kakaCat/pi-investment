"""DeduplicationManager 单测（RFC 014 v3 重构 P2，2026-09-14）

这段此前内联在 tick 里，还混着「物理去重（同规则多条件）」与
「业务重叠（跨规则）」两种不同处置；提取后分别直测。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from application.services.watch_engine.deduplication_manager import DeduplicationManager
from application.services.watch_engine.state_manager import StateManager

NOW = datetime(2026, 9, 14, 10, 30)


def _rule(rid=1, symbol='600519.SH'):
    return SimpleNamespace(id=rid, symbol=symbol)


def _cond(direction='below'):
    return {'type': 'price_break', 'params': {'direction': direction}}


def _mgr(window=300):
    s = StateManager()
    return DeduplicationManager(s, window), s


class TestWindowDedup:
    def test_first_check_is_not_duplicate(self):
        m, _ = _mgr()
        assert m.check(_rule(1), _cond(), NOW).is_duplicate is False

    def test_second_check_within_window_merges(self):
        m, _ = _mgr()
        m.mark_notified(_rule(1), _cond(), NOW, trigger_id=99)
        out = m.check(_rule(1), _cond(), NOW + timedelta(seconds=10))
        assert out.is_duplicate is True
        assert out.dup_of == 99

    def test_after_window_not_duplicate(self):
        m, _ = _mgr(window=300)
        m.mark_notified(_rule(1), _cond(), NOW, trigger_id=99)
        assert m.check(_rule(1), _cond(), NOW + timedelta(seconds=400)).is_duplicate is False

    def test_opposite_direction_not_deduped(self):
        m, _ = _mgr()
        m.mark_notified(_rule(1), _cond('below'), NOW, trigger_id=1)
        # 方向不同 = 不同 key（上破与下破是两件事）
        assert m.check(_rule(1), _cond('above'), NOW).is_duplicate is False


class TestCrossRuleOverlap:
    def test_overlap_reported_once_per_pair(self):
        m, _ = _mgr()
        m.mark_notified(_rule(1), _cond(), NOW, trigger_id=1)
        first = m.check(_rule(2), _cond(), NOW + timedelta(seconds=5))
        assert first.overlap_pair == (1, 2)
        # 同一对再命中：仍判重复，但不再重复上报治理
        second = m.check(_rule(2), _cond(), NOW + timedelta(seconds=6))
        assert second.is_duplicate is True
        assert second.overlap_pair is None

    def test_same_rule_repeat_is_not_overlap(self):
        """同一规则多条件重复属物理去重，不该被当成业务重叠上报"""
        m, _ = _mgr()
        m.mark_notified(_rule(1), _cond(), NOW, trigger_id=1)
        out = m.check(_rule(1), _cond(), NOW + timedelta(seconds=5))
        assert out.is_duplicate is True
        assert out.overlap_pair is None


def test_reason_text_points_to_merged_trigger():
    m, _ = _mgr()
    m.mark_notified(_rule(1), _cond(), NOW, trigger_id=42)
    out = m.check(_rule(1), _cond(), NOW + timedelta(seconds=5))
    assert '42' in m.reason_text(out)


def test_overlap_reason_mentions_pair():
    text = DeduplicationManager.overlap_reason((3, 7), ('600519', 'below'))
    assert '#3' in text and '#7' in text

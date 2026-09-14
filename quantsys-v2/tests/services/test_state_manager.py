"""StateManager 单测（RFC 014 v3 重构 P1，2026-09-14）

它是引擎「触发/去重/介入」状态与两条升级统计的唯一事实源，
直接测比通过 WatchEngine 间接测更精确（也更快）。
"""
from datetime import datetime, timedelta

from application.services.watch_engine.state_manager import StateManager, TriggerRecord

NOW = datetime(2026, 9, 14, 10, 30)


class TestTriggerEventLog:
    def test_record_and_count_within_window(self):
        s = StateManager()
        s.record_trigger_event(NOW - timedelta(minutes=2), 7, '600519.SH')
        s.record_trigger_event(NOW - timedelta(minutes=1), 7, '600519.SH')
        # 历史 2 次 + 本次 = 3
        assert s.recent_trigger_count(NOW, 7) == 3

    def test_count_excludes_out_of_window(self):
        s = StateManager()
        s.record_trigger_event(NOW - timedelta(minutes=30), 7, '600519.SH')
        assert s.recent_trigger_count(NOW, 7, window_minutes=10) == 1

    def test_retention_prunes_old_events(self):
        s = StateManager(event_retention_min=30)
        s.record_trigger_event(NOW - timedelta(minutes=90), 7, '600519.SH')
        # 记第 2 条时按保留窗口裁剪，90 分钟前那条应被清掉
        s.record_trigger_event(NOW, 7, '600519.SH')
        assert len(s.trigger_events) == 1


class TestConcurrentCount:
    def test_counts_distinct_rules_for_same_symbol(self):
        s = StateManager()
        s.record_trigger_event(NOW, 1, '600519.SH')
        assert s.concurrent_trigger_count(NOW, '600519.SH', 2) == 2

    def test_ignores_other_symbols(self):
        s = StateManager()
        s.record_trigger_event(NOW, 1, '000001.SZ')
        assert s.concurrent_trigger_count(NOW, '600519.SH', 2) == 1

    def test_same_rule_twice_counts_once(self):
        s = StateManager()
        s.record_trigger_event(NOW, 1, '600519.SH')
        s.record_trigger_event(NOW, 1, '600519.SH')
        assert s.concurrent_trigger_count(NOW, '600519.SH', 1) == 1

    def test_excludes_out_of_window(self):
        s = StateManager()
        s.record_trigger_event(NOW - timedelta(seconds=120), 1, '600519.SH')
        assert s.concurrent_trigger_count(NOW, '600519.SH', 2, window_seconds=60) == 1


class TestResetDaily:
    def test_clears_volatile_state(self):
        s = StateManager()
        s.latched.add((1, 0))
        s.recent_notified[('600519', 'up')] = (NOW, 1, 1)
        s.overlap_reported.add((1, 2))
        s.last_intervention[('600519', 'entry')] = NOW
        s.interventions_today = 5
        s.record_trigger_event(NOW, 1, '600519.SH')

        s.reset_daily(NOW)

        assert s.latched == set()
        assert s.recent_notified == {}
        assert s.overlap_reported == set()
        assert s.last_intervention == {}
        assert s.interventions_today == 0
        assert s.trigger_events == []
        assert s.current_date == NOW.date()

    def test_filters_inactive_rules_and_symbols(self):
        s = StateManager()
        s.last_triggered[(1, 0)] = NOW
        s.last_triggered[(2, 0)] = NOW
        s.history['600519.SH'] = [(NOW, 100.0)]
        s.history['000001.SZ'] = [(NOW, 10.0)]

        s.reset_daily(NOW, active_rule_ids={1}, active_symbols={'600519.SH'})

        assert set(s.last_triggered.keys()) == {(1, 0)}
        assert set(s.history.keys()) == {'600519.SH'}


class TestPruneDedup:
    def test_removes_expired_entries(self):
        s = StateManager(dedup_window_sec=300)
        s.recent_notified[('600519', 'up')] = (NOW - timedelta(seconds=400), 1, 1)
        s.recent_notified[('600519', 'down')] = (NOW - timedelta(seconds=100), 2, 1)

        s.prune_dedup(NOW)

        assert set(s.recent_notified.keys()) == {('600519', 'down')}

    def test_noop_when_empty(self):
        s = StateManager()
        s.prune_dedup(NOW)   # 不应抛错
        assert s.recent_notified == {}


def test_snapshot_reports_state_sizes():
    s = StateManager()
    s.latched.add((1, 0))
    s.interventions_today = 3
    s.record_trigger_event(NOW, 1, '600519.SH')
    s.current_date = NOW.date()

    snap = s.snapshot()

    assert snap['latched'] == 1
    assert snap['interventions_today'] == 3
    assert snap['trigger_events'] == 1
    assert snap['current_date'] == '2026-09-14'


def test_trigger_record_key():
    rec = TriggerRecord(rule_id=3, symbol='600519.SH', triggered_at=NOW)
    assert rec.rule_id == 3 and rec.symbol == '600519.SH'

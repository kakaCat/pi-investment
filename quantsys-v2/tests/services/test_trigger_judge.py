"""TriggerJudge 单测（RFC 014 v3 重构 P1，2026-09-14）

闩锁/冷却此前内联在 tick 深层缩进里，只能通过整体 tick 间接验证。
提取后直接测三段判定与标记语义。
"""
from datetime import datetime, timedelta

from application.services.watch_engine.state_manager import StateManager
from application.services.watch_engine.trigger_judge import TriggerJudge

NOW = datetime(2026, 9, 14, 10, 30)


def _judge():
    s = StateManager()
    return TriggerJudge(s), s


class TestLatch:
    def test_not_triggered_clears_latch_and_rearms(self):
        j, s = _judge()
        s.latched.add((1, 0))
        assert j.should_emit(1, 0, False, {}, NOW) is False
        assert (1, 0) not in s.latched      # 重新武装

    def test_latched_suppresses_repeat_while_holding(self):
        j, s = _judge()
        s.latched.add((1, 0))
        assert j.should_emit(1, 0, True, {}, NOW) is False

    def test_emits_when_triggered_and_unlatched(self):
        j, s = _judge()
        assert j.should_emit(1, 0, True, {}, NOW) is True


class TestCooldown:
    def test_within_cooldown_skipped(self):
        j, s = _judge()
        s.last_triggered[(1, 0)] = NOW - timedelta(seconds=60)
        assert j.should_emit(1, 0, True, {'cooldown_sec': 300}, NOW) is False

    def test_after_cooldown_emits(self):
        j, s = _judge()
        s.last_triggered[(1, 0)] = NOW - timedelta(seconds=400)
        assert j.should_emit(1, 0, True, {'cooldown_sec': 300}, NOW) is True

    def test_uses_default_cooldown_when_condition_silent(self):
        j, s = _judge()
        s.last_triggered[(1, 0)] = NOW - timedelta(seconds=100)
        assert j.in_cooldown(1, 0, {}, NOW) is True


class TestMarkEmitted:
    def test_marks_cooldown_latch_and_event_log(self):
        j, s = _judge()
        j.mark_emitted(1, 0, NOW, '600519.SH')
        assert s.last_triggered[(1, 0)] == NOW
        assert (1, 0) in s.latched
        assert s.trigger_events == [(NOW, 1, '600519.SH')]

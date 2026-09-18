"""心跳巡检测试（REQ-c9f899 t10）

覆盖：判定纯函数四态、只在「曾有心跳但过期」时告警、影子模式超期、
存储读失败不得误报 stale、告警通道抛错不得打挂巡检、引擎侧心跳节流与失败降级。
"""
import os
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from adapters.inbound.fastapi_app.watch_heartbeat_job import (
    SHADOW_SINCE_ENV,
    evaluate_heartbeat,
    evaluate_shadow_overdue,
    run_heartbeat_check,
)

NOW = datetime(2026, 9, 18, 10, 0, 0)


class FakeStore:
    def __init__(self, meta=None, boom=False):
        self.meta = meta or {}
        self.boom = boom

    def load_meta(self):
        if self.boom:
            raise RuntimeError('db down')
        return self.meta

    def save_meta(self, **fields):
        if getattr(self, 'save_boom', False):
            raise RuntimeError('write down')
        self.meta.update(fields)


# ── 判定纯函数 ──────────────────────────────────────────────
def test_heartbeat_ok():
    r = evaluate_heartbeat(NOW - timedelta(seconds=10), NOW)
    assert r['verdict'] == 'ok' and r['should_alert'] is False


def test_heartbeat_stale_alerts():
    r = evaluate_heartbeat(NOW - timedelta(seconds=400), NOW)
    assert r['verdict'] == 'stale' and r['should_alert'] is True
    assert '引擎线程可能已死' in r['reason']


def test_heartbeat_never_does_not_alert():
    r = evaluate_heartbeat(None, NOW)
    assert r['verdict'] == 'never' and r['should_alert'] is False


def test_heartbeat_disabled_does_not_alert():
    r = evaluate_heartbeat(NOW - timedelta(days=1), NOW, enabled=False)
    assert r['verdict'] == 'disabled' and r['should_alert'] is False


def test_aware_datetimes_do_not_crash_and_are_normalized():
    """真库回归：TIMESTAMPTZ 读回来是 aware，与 naive now 相减会 TypeError。

    2026-09-18 线上实测 /api/watch/metrics 因此 500——本用例用 aware 输入钉死这条路。
    """
    from datetime import timezone, timedelta as _td
    aware_now = NOW.replace(tzinfo=timezone(_td(hours=8)))
    aware_hb = (NOW - timedelta(seconds=30)).replace(tzinfo=timezone(_td(hours=8)))
    r = evaluate_heartbeat(aware_hb, aware_now)          # 不得抛 TypeError
    assert r['verdict'] == 'ok' and r['age_sec'] == 30.0

    st = evaluate_heartbeat((NOW - timedelta(seconds=600)).replace(tzinfo=timezone(_td(hours=8))), aware_now)
    assert st['verdict'] == 'stale'

    sh = evaluate_shadow_overdue(True, (NOW - timedelta(hours=72)).replace(tzinfo=timezone(_td(hours=8))), aware_now)
    assert sh['verdict'] == 'overdue'


def test_shadow_off_and_unknown_and_overdue():
    assert evaluate_shadow_overdue(False, None, NOW)['verdict'] == 'off'
    assert evaluate_shadow_overdue(True, None, NOW)['verdict'] == 'unknown'
    assert evaluate_shadow_overdue(True, None, NOW)['should_alert'] is False
    over = evaluate_shadow_overdue(True, NOW - timedelta(hours=72), NOW)
    assert over['verdict'] == 'overdue' and over['should_alert'] is True
    ok = evaluate_shadow_overdue(True, NOW - timedelta(hours=3), NOW)
    assert ok['verdict'] == 'ok'


# ── 巡检编排 ────────────────────────────────────────────────
def test_check_alerts_on_stale_and_calls_sender_once(monkeypatch):
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'true')
    monkeypatch.setenv(SHADOW_SINCE_ENV, NOW.isoformat())      # 影子未超期
    sent = []
    out = run_heartbeat_check(now=NOW,
                              store=FakeStore({'heartbeat_at': NOW - timedelta(seconds=600)}),
                              sender=sent.append)
    assert len(out['alerts']) == 1 and out['alerts'][0][0] == 'engine_heartbeat'
    assert out['sent'] == 1 and len(sent) == 1
    assert '心跳丢失' in sent[0]


def test_check_never_heartbeat_sends_nothing(monkeypatch):
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'true')
    sent = []
    out = run_heartbeat_check(now=NOW, store=FakeStore({}), sender=sent.append)
    assert out['heartbeat']['verdict'] == 'never'
    assert out['alerts'] == [] and sent == []


def test_check_shadow_overdue_alerts(monkeypatch):
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'true')
    monkeypatch.setenv(SHADOW_SINCE_ENV, (NOW - timedelta(hours=72)).isoformat())
    monkeypatch.setenv('WATCH_DIGEST_DRY_RUN', 'true')
    sent = []
    out = run_heartbeat_check(now=NOW, store=FakeStore({'heartbeat_at': NOW}), sender=sent.append)
    assert [a[0] for a in out['alerts']] == ['shadow_mode_overdue']
    assert '影子模式已挂' in sent[0]


def test_store_read_failure_does_not_fake_stale(monkeypatch):
    """读失败 → 按 never 处理，绝不误报 stale（否则 DB 抖动就会刷告警）"""
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'true')
    out = run_heartbeat_check(now=NOW, store=FakeStore(boom=True), sender=lambda m: None)
    assert out['heartbeat']['verdict'] == 'never'
    assert out['alerts'] == []


def test_sender_failure_does_not_crash_check(monkeypatch):
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'true')
    monkeypatch.setenv(SHADOW_SINCE_ENV, NOW.isoformat())

    def boom(_msg):
        raise RuntimeError('feishu down')

    out = run_heartbeat_check(now=NOW,
                              store=FakeStore({'heartbeat_at': NOW - timedelta(seconds=600)}),
                              sender=boom)
    assert out['sent'] == 0            # 发送失败如实计 0，不假装成功
    assert len(out['alerts']) == 1


# ── 引擎侧心跳 ──────────────────────────────────────────────
def _engine(store):
    from application.services.watch_engine.engine import WatchEngine
    eng = WatchEngine(rule_repo=SimpleNamespace(list_enabled=lambda: []),
                      quote_service=SimpleNamespace(get_realtime_quote=lambda s: None),
                      notifier=SimpleNamespace())
    eng._heartbeat_store = store
    return eng


def test_engine_heartbeat_writes_and_throttles(monkeypatch):
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'true')   # 密封：不依赖环境默认
    store = FakeStore({})
    eng = _engine(store)
    assert eng._write_heartbeat(NOW) is True
    assert store.meta['heartbeat_at'] == NOW
    # 节流：同一周期内第二次不写
    assert eng._write_heartbeat(NOW + timedelta(seconds=5)) is False
    assert eng._write_heartbeat(NOW + timedelta(seconds=61)) is True


def test_engine_heartbeat_write_failure_degrades_not_raises(monkeypatch):
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'true')
    store = FakeStore({})
    store.save_meta = lambda **f: (_ for _ in ()).throw(RuntimeError('write down'))
    eng = _engine(store)
    assert eng._write_heartbeat(NOW) is False
    assert eng._heartbeat_failures == 1
    assert eng._last_heartbeat_at is None


def test_engine_metrics_expose_heartbeat(monkeypatch):
    """排障入口：引擎状态快照必须能回答「心跳有没有在写、失败几次」"""
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'true')
    store = FakeStore({})
    eng = _engine(store)
    assert eng.get_metrics()['heartbeat_last_at'] is None
    eng._write_heartbeat(NOW)
    m = eng.get_metrics()
    assert m['heartbeat_last_at'].startswith('2026-09-18T10:00')
    assert m['heartbeat_failures'] == 0
    assert m['heartbeat_enabled'] is True


def test_engine_heartbeat_disabled(monkeypatch):
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'false')
    store = FakeStore({})
    eng = _engine(store)
    assert eng._write_heartbeat(NOW) is False
    assert store.meta == {}

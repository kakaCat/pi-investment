"""影子模式超期巡检测试。"""
from datetime import datetime, timedelta, timezone

from adapters.inbound.fastapi_app.watch_shadow_job import (
    SHADOW_SINCE_ENV,
    evaluate_shadow_overdue,
    run_shadow_check,
)

NOW = datetime(2026, 9, 18, 10, 0, 0)


def test_aware_datetimes_do_not_crash_and_are_normalized():
    aware_now = NOW.replace(tzinfo=timezone(timedelta(hours=8)))
    shadow_since = (NOW - timedelta(hours=72)).replace(
        tzinfo=timezone(timedelta(hours=8)))
    result = evaluate_shadow_overdue(True, shadow_since, aware_now)
    assert result['verdict'] == 'overdue'


def test_shadow_off_and_unknown_and_overdue():
    assert evaluate_shadow_overdue(False, None, NOW)['verdict'] == 'off'
    assert evaluate_shadow_overdue(True, None, NOW)['verdict'] == 'unknown'
    assert evaluate_shadow_overdue(True, None, NOW)['should_alert'] is False
    over = evaluate_shadow_overdue(True, NOW - timedelta(hours=72), NOW)
    assert over['verdict'] == 'overdue' and over['should_alert'] is True
    ok = evaluate_shadow_overdue(True, NOW - timedelta(hours=3), NOW)
    assert ok['verdict'] == 'ok'


def test_check_shadow_overdue_alerts(monkeypatch):
    monkeypatch.setenv(SHADOW_SINCE_ENV, (NOW - timedelta(hours=72)).isoformat())
    monkeypatch.setenv('WATCH_DIGEST_DRY_RUN', 'true')
    sent = []
    out = run_shadow_check(now=NOW, sender=sent.append)
    assert [a[0] for a in out['alerts']] == ['shadow_mode_overdue']
    assert out['sent'] == 1
    assert '影子模式已挂' in sent[0]


def test_sender_failure_does_not_crash_check(monkeypatch):
    monkeypatch.setenv(SHADOW_SINCE_ENV, (NOW - timedelta(hours=72)).isoformat())
    monkeypatch.setenv('WATCH_DIGEST_DRY_RUN', 'true')

    def boom(_msg):
        raise RuntimeError('feishu down')

    out = run_shadow_check(now=NOW, sender=boom)
    assert out['sent'] == 0
    assert len(out['alerts']) == 1

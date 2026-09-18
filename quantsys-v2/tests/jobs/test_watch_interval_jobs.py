"""进程外周期任务接线（REQ-c9f899 t12 §6-项4/5/6/10）。

可失败性：
  · 三个巡检任务的开关默认必须全关（总闸 WATCH_TODO_ENABLED=false）；
  · 翻转总闸后 SLA/心跳启用，自愈另需 WATCH_SELF_HEAL_ENABLED；
  · interval_due 的节流/在跑/关闭分支；
  · 自愈周期默认 10 分钟且下限=宿主 tick；
  · 真实通道 sender 失败必须抛错（不许把失败记成已送达）。
"""
from adapters.inbound.fastapi_app.daily_jobs_bootstrap import (
    DEFAULT_SELF_HEAL_INTERVAL_SEC,
    IntervalJobDef,
    _build_interval_jobs,
    _self_heal_interval_sec,
    _watch_heartbeat_job_enabled,
    _watch_loop_master_enabled,
    _watch_self_heal_job_enabled,
    interval_due,
)


def _job(enabled, interval=60):
    return IntervalJobDef("t", lambda: {}, interval, "d", lambda: enabled)


def test_interval_due_first_run_throttle_and_window():
    assert interval_due(_job(True), 1000.0, None, False) is True
    assert interval_due(_job(True), 1059.9, 1000.0, False) is False
    assert interval_due(_job(True), 1060.0, 1000.0, False) is True


def test_interval_due_disabled_or_running():
    assert interval_due(_job(False), 1000.0, None, False) is False
    assert interval_due(_job(True), 1000.0, None, True) is False


def test_all_interval_jobs_disabled_by_default(monkeypatch):
    for name in ("WATCH_TODO_ENABLED", "WATCH_SELF_HEAL_ENABLED", "WATCH_HEARTBEAT_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    assert _watch_loop_master_enabled() is False
    for job in _build_interval_jobs():
        assert job.enabled() is False, job.job_id


def test_master_switch_enables_sla_and_heartbeat(monkeypatch):
    monkeypatch.setenv("WATCH_TODO_ENABLED", "true")
    monkeypatch.setenv("WATCH_HEARTBEAT_ENABLED", "true")
    monkeypatch.setenv("WATCH_SELF_HEAL_ENABLED", "true")
    jobs = {job.job_id: job for job in _build_interval_jobs()}
    assert jobs["watch_sla_patrol"].enabled() is True
    assert jobs["watch_heartbeat_patrol"].enabled() is True
    assert jobs["watch_self_heal_scan"].enabled() is True


def test_heartbeat_requires_master_and_own_switch(monkeypatch):
    monkeypatch.setenv("WATCH_HEARTBEAT_ENABLED", "true")
    monkeypatch.delenv("WATCH_TODO_ENABLED", raising=False)
    assert _watch_heartbeat_job_enabled() is False      # 总闸关闭 → 不启用
    monkeypatch.setenv("WATCH_TODO_ENABLED", "true")
    assert _watch_heartbeat_job_enabled() is True
    monkeypatch.setenv("WATCH_HEARTBEAT_ENABLED", "false")
    assert _watch_heartbeat_job_enabled() is False


def test_self_heal_requires_both_switches(monkeypatch):
    monkeypatch.setenv("WATCH_SELF_HEAL_ENABLED", "true")
    monkeypatch.delenv("WATCH_TODO_ENABLED", raising=False)
    assert _watch_self_heal_job_enabled() is False
    monkeypatch.setenv("WATCH_TODO_ENABLED", "true")
    assert _watch_self_heal_job_enabled() is True


def test_self_heal_interval_default_and_floor(monkeypatch):
    monkeypatch.delenv("WATCH_SELF_HEAL_INTERVAL_SEC", raising=False)
    assert _self_heal_interval_sec() == float(DEFAULT_SELF_HEAL_INTERVAL_SEC) == 600.0
    monkeypatch.setenv("WATCH_SELF_HEAL_INTERVAL_SEC", "1")
    assert _self_heal_interval_sec() >= 60.0            # 下限=宿主 tick


class _FakeFacade:
    def __init__(self, ok):
        self.ok = ok
        self.calls = []

    def send_card(self, **kwargs):
        self.calls.append(kwargs)
        return self.ok


def test_send_watch_alert_uses_facade_and_raises_on_failure(monkeypatch):
    from application.services.watch_engine import watch_channels
    good = _FakeFacade(True)
    monkeypatch.setattr("application.notification.get_notification_facade", lambda: good)
    assert watch_channels.send_watch_alert("【盯盘引擎】心跳丢失 | 已过期 600s") is True
    assert good.calls[0]["urgency"] == "high"
    assert good.calls[0]["title"] == "【盯盘引擎】心跳丢失"
    assert "600s" in good.calls[0]["content"]

    bad = _FakeFacade(False)
    monkeypatch.setattr("application.notification.get_notification_facade", lambda: bad)
    import pytest
    with pytest.raises(RuntimeError):
        watch_channels.send_watch_alert("x | y")


def test_send_watch_receipt_channel_drives_urgency_and_raises(monkeypatch):
    from application.services.watch_engine import watch_channels
    import pytest
    good = _FakeFacade(True)
    monkeypatch.setattr("application.notification.get_notification_facade", lambda: good)
    watch_channels.send_watch_receipt({"kind": "timeout", "channel": "alerts",
                                       "message": "[超时] 待办#1"})
    assert good.calls[0]["urgency"] == "high"
    watch_channels.send_watch_receipt({"kind": "result", "channel": "reports",
                                       "message": "[处置后] 待办#1"})
    assert good.calls[1]["urgency"] == "normal"

    bad = _FakeFacade(False)
    monkeypatch.setattr("application.notification.get_notification_facade", lambda: bad)
    with pytest.raises(RuntimeError):
        watch_channels.send_watch_receipt({"kind": "result", "channel": "reports"})
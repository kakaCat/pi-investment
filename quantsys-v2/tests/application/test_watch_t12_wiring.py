"""引擎接线（REQ-c9f899 t12 §6-项2/3/7）。

可失败性：
  · 默认全关 → build_watch_loop_services 返回全 None（行为与改造前一致）；
  · 开关打开 → 按开关装配对应服务并注入引擎；装配失败降级为 None 不抛；
  · notifier 调用处必须把账户总资产与级别传给 facade（金额门/按级别渲染的接线）；
  · 引擎只在闭环开启（todo_service 注入）时产出级别，否则 None（旧渲染路径）。
"""
from types import SimpleNamespace

from application.services.watch_engine import watch_loop_wiring as wiring
from application.services.watch_engine.engine import WatchEngine
from application.services.watch_engine.factory import build_watch_loop_services


def _clear_switches(monkeypatch):
    for name in ("WATCH_TODO_ENABLED", "WATCH_SELF_HEAL_ENABLED",
                 "WATCH_RUNTIME_PERSIST_ENABLED"):
        monkeypatch.delenv(name, raising=False)


def test_build_watch_loop_services_all_off_by_default(monkeypatch):
    _clear_switches(monkeypatch)
    assert build_watch_loop_services() == (None, None, None, None, None)


def test_build_watch_loop_services_assembles_when_switches_on(monkeypatch):
    _clear_switches(monkeypatch)
    monkeypatch.setenv("WATCH_RUNTIME_PERSIST_ENABLED", "true")
    monkeypatch.setenv("WATCH_TODO_ENABLED", "true")
    monkeypatch.setenv("WATCH_SELF_HEAL_ENABLED", "true")
    monkeypatch.setattr(wiring, "build_runtime_store", lambda: "store")
    monkeypatch.setattr(wiring, "build_todo_service", lambda: "todo")
    monkeypatch.setattr(wiring, "build_receipt_service", lambda: "receipt")
    monkeypatch.setattr(wiring, "build_sla_job",
                        lambda receipt_service=None: ("sla", receipt_service))
    monkeypatch.setattr(wiring, "build_self_heal_service",
                        lambda todo_service=None: ("heal", todo_service))
    assert build_watch_loop_services() == ("store", "todo", "receipt",
                                           ("sla", "receipt"), ("heal", "todo"))


def test_build_watch_loop_services_degrades_on_failure(monkeypatch):
    _clear_switches(monkeypatch)
    monkeypatch.setenv("WATCH_TODO_ENABLED", "true")

    def _boom():
        raise RuntimeError("assembly down")

    monkeypatch.setattr(wiring, "build_todo_service", _boom)
    assert build_watch_loop_services() == (None, None, None, None, None)


def test_runtime_store_failure_does_not_raise(monkeypatch):
    _clear_switches(monkeypatch)
    monkeypatch.setenv("WATCH_RUNTIME_PERSIST_ENABLED", "true")

    def _boom():
        raise RuntimeError("store down")

    monkeypatch.setattr(wiring, "build_runtime_store", _boom)
    assert build_watch_loop_services()[0] is None


class _Result:
    success = True


class _Facade:
    def __init__(self):
        self.calls = []

    def send_watch_triggered(self, **kwargs):
        self.calls.append(kwargs)
        return _Result()


def _rule(**overrides):
    base = dict(id=1, symbol="600519", account="agent_brain", cost_price=None,
                context=None, action_hint=None, intent="entry", scope="symbol",
                lifecycle_stage=None, next_action_hint=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def _quote():
    return SimpleNamespace(price=10.0, prev_close=9.5, name="x", change_pct=None)


def _eval_result():
    return SimpleNamespace(value=None, message="m")


def test_notifier_passes_account_total_and_level():
    from application.services.watch_engine.notifier import WatchNotifier
    facade = _Facade()
    notifier = WatchNotifier(trigger_repo=None, ws_url=None,
                             notification_facade=facade,
                             account_total_provider=lambda rule: 200000.0)
    notifier.notify(_rule(), {"type": "price_break",
                              "params": {"direction": "above", "price": 10}},
                   _quote(), _eval_result(), disposition="pending", level="P1")
    assert facade.calls[0]["account_total_yuan"] == 200000.0
    assert facade.calls[0]["level"] == "P1"


def test_notifier_account_total_failure_is_none():
    from application.services.watch_engine.notifier import WatchNotifier
    facade = _Facade()

    def _boom(_rule):
        raise RuntimeError("account read down")

    notifier = WatchNotifier(trigger_repo=None, ws_url=None,
                             notification_facade=facade,
                             account_total_provider=_boom)
    notifier.notify(_rule(), {"type": "price_break",
                              "params": {"direction": "above", "price": 10}},
                   _quote(), _eval_result(), disposition="pending")
    assert facade.calls[0]["account_total_yuan"] is None
    assert facade.calls[0]["level"] is None


def _engine(todo_service=None):
    return WatchEngine(rule_repo=SimpleNamespace(list_enabled=lambda: []),
                       quote_service=SimpleNamespace(get_realtime_quote=lambda s: None),
                       notifier=SimpleNamespace(), todo_service=todo_service)


def test_notify_level_none_when_closed_loop_off():
    rule = SimpleNamespace(id=1, intent="exit_stop", action_hint=None, scope=None)
    assert _engine(None)._notify_level(rule, "pending") is None


def test_notify_level_computed_when_closed_loop_on():
    eng = _engine(object())
    stop = SimpleNamespace(id=1, intent="exit_stop", action_hint=None, scope=None)
    assert eng._notify_level(stop, "pending", has_position=False) == "P0"
    entry = SimpleNamespace(id=2, intent="entry", action_hint=None, scope=None)
    assert eng._notify_level(entry, "pending", has_position=False) == "P1"
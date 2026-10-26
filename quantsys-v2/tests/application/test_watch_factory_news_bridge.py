"""组合根装配：消息桥与规则变更联动的接线（REQ-261021194640-69b8，卡 t-e416b7）

判据：桥/联动被装配到服务上；未装配时保持 None（旧行为）；装配失败不阻断。
"""
from types import SimpleNamespace

from qs_watch.application.services.watch_engine import factory, watch_loop_wiring


def test_build_todo_service_wires_rule_change_linkage():
    svc = watch_loop_wiring.build_todo_service()
    assert svc._rule_change_linkage is not None, '规则联动必须默认装配'


def test_news_watch_service_accepts_bridge():
    bridge = SimpleNamespace(dispatch=lambda alerts: {'created': []})
    svc = factory._build_news_watch_service(bridge=bridge)
    assert svc._bridge is bridge
    assert factory._build_news_watch_service()._bridge is None


def test_policy_watch_service_accepts_bridge(monkeypatch):
    monkeypatch.setattr(factory, '_policy_watch_enabled', lambda: True)
    bridge = SimpleNamespace(dispatch=lambda alerts: {'created': []})
    svc = factory.build_policy_watch_service(news_service=object(), bridge=bridge)
    assert svc is not None and svc._bridge is bridge

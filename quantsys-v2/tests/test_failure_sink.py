"""FailureSink 测试（REQ-261004154902-a7cd · t1 / FR-2 / FR-9）。

覆盖验收标准第三条：report_failure 在 NotificationFacade 抛错时**不向外抛**，
且日志含 source/reason。

注意：本文件不得真实外发通知——测试期间由 tests/notify_guard.py 兜底，
但这里更进一步：所有用例都显式注入假 sink，绝不触碰真实通道。
"""
from __future__ import annotations

import logging

import pytest

from application.observability import failure_sink
from application.observability.failure_sink import (
    SEVERITY_HIGH,
    SEVERITY_NORMAL,
    install_failure_alert_sink,
    report_failure,
)


@pytest.fixture(autouse=True)
def _no_real_channels():
    """每个用例前后都把通道复位为「假 sink」，杜绝真实外发。"""
    install_failure_alert_sink(lambda title, content, urgency: True)
    yield
    install_failure_alert_sink(None)


def test_report_failure_logs_source_and_reason_and_delivers(caplog) -> None:
    captured = {}

    def fake_sink(title: str, content: str, urgency: str) -> bool:
        captured.update(title=title, content=content, urgency=urgency)
        return True

    install_failure_alert_sink(fake_sink)
    with caplog.at_level(logging.ERROR):
        delivered = report_failure(
            "strategy.rebalance",
            "rebalance_failed",
            "AttributeError: boom",
            severity=SEVERITY_HIGH,
            context={"account": "v13_simulation"},
        )

    assert delivered is True
    assert captured["urgency"] == SEVERITY_HIGH
    assert "strategy.rebalance" in captured["content"]
    assert "rebalance_failed" in captured["content"]
    assert "AttributeError: boom" in captured["content"]
    assert "v13_simulation" in captured["content"]

    # 日志必须含 source 与 reason（验收标准原文）
    assert "strategy.rebalance" in caplog.text
    assert "rebalance_failed" in caplog.text


def test_normal_severity_is_passed_through(caplog) -> None:
    captured = {}
    install_failure_alert_sink(
        lambda title, content, urgency: captured.update(urgency=urgency) or True
    )
    with caplog.at_level(logging.ERROR):
        assert report_failure("pending_orders.match", "pending_expired") is True
    assert captured["urgency"] == SEVERITY_NORMAL


def test_sink_exception_is_swallowed(caplog) -> None:
    def boom(title: str, content: str, urgency: str) -> bool:
        raise RuntimeError("channel exploded")

    install_failure_alert_sink(boom)
    with caplog.at_level(logging.ERROR):
        delivered = report_failure("scheduler.job", "rebalance_failed", "x")  # 不得抛
    assert delivered is False
    assert "channel exploded" in caplog.text


def test_not_delivered_is_itself_visible(caplog) -> None:
    install_failure_alert_sink(lambda title, content, urgency: False)
    with caplog.at_level(logging.ERROR):
        delivered = report_failure("scheduler.job", "factor_empty", "empty frame")
    assert delivered is False
    assert "外发未送达" in caplog.text


def test_default_sink_swallows_notification_failure(monkeypatch, caplog) -> None:
    """默认通道（NotificationFacade）抛错时：返回 False，绝不向外抛。"""

    def boom(*args, **kwargs):
        raise RuntimeError("8080 down and no feishu")

    monkeypatch.setattr(
        "application.notification.get_notification_facade", boom, raising=False
    )
    install_failure_alert_sink(None)  # 用默认通道
    with caplog.at_level(logging.ERROR):
        delivered = report_failure(
            "scheduler.job_executor", "rebalance_failed", "inner failed"
        )
    assert delivered is False
    assert "scheduler.job_executor" in caplog.text


def test_default_sink_uses_facade_send_card(monkeypatch) -> None:
    """默认通道走 NotificationFacade.send_card，并把 urgency 透传。"""
    seen = {}

    class FakeFacade:
        def send_card(self, title, content, urgency="normal"):
            seen.update(title=title, content=content, urgency=urgency)
            return True

    monkeypatch.setattr(
        "application.notification.get_notification_facade",
        lambda: FakeFacade(),
        raising=False,
    )
    install_failure_alert_sink(None)
    assert report_failure("strategy.daily_check", "factor_empty", "0 factors") is True
    assert seen["urgency"] == SEVERITY_NORMAL
    assert "strategy.daily_check" in seen["content"]

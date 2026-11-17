"""D-20/D-31：盯盘处置与待办闭环的审计、状态一致性回归。"""
from types import SimpleNamespace

import pytest

from adapters.inbound.fastapi_app.routes import watch_async
from adapters.outbound.repositories.watch_rule_repository import (
    WatchTrigger,
    WatchTriggerRepository,
)
from adapters.outbound.repositories.watch_todo_repository import WatchTodoRepository


def _trigger(response=None):
    return WatchTrigger(
        id=1,
        rule_id=2,
        symbol="600519.SH",
        condition={"type": "price_break"},
        trigger_price=1800,
        agent_response=response,
        disposition="pending",
    )


def test_disposition_and_response_commit_once_and_merge(monkeypatch):
    repo = WatchTriggerRepository.__new__(WatchTriggerRepository)
    trigger = _trigger({"notification_delivered": True, "action": "观察"})
    repo.get_by_id = lambda _id: trigger
    session = SimpleNamespace(commit=lambda: commits.append(1))
    commits = []
    session.commit = lambda: commits.append(1)
    monkeypatch.setattr(WatchTriggerRepository, "session", property(lambda _self: session))

    result = repo.update_disposition(
        1,
        "handled",
        reason="按预案复核",
        by="agent-dh",
        agent_response={"source": "watch_resolve", "reason": "按预案复核"},
    )

    assert result is trigger
    assert trigger.disposition == "handled"
    assert trigger.agent_response == {
        "notification_delivered": True,
        "action": "观察",
        "source": "watch_resolve",
        "reason": "按预案复核",
    }
    assert commits == [1]


def test_disposition_without_new_response_preserves_v2_payload(monkeypatch):
    repo = WatchTriggerRepository.__new__(WatchTriggerRepository)
    original = {"notification_delivered": True, "action": "卖出"}
    trigger = _trigger(original)
    repo.get_by_id = lambda _id: trigger
    monkeypatch.setattr(
        WatchTriggerRepository,
        "session",
        property(lambda _self: SimpleNamespace(commit=lambda: None)),
    )

    repo.update_disposition(1, "handled", reason="止损", by="agent-ts")

    assert trigger.agent_response == original


def test_patch_terminal_writes_response_but_pending_does_not(monkeypatch):
    calls = []

    class FakeRepo:
        def update_disposition(self, trigger_id, disposition, reason, by, agent_response):
            calls.append(agent_response)
            return _trigger(agent_response)

    monkeypatch.setattr(watch_async, "WatchTriggerRepository", FakeRepo)

    terminal = watch_async.update_trigger_disposition(
        1, {"disposition": "handled", "reason": "复核完成", "by": "agent-dh"}
    )
    pending = watch_async.update_trigger_disposition(
        1, {"disposition": "pending", "by": "agent-dh"}
    )

    assert terminal["success"] is True
    assert calls[0]["source"] == "watch_resolve"
    assert calls[0]["reason"] == "复核完成"
    assert calls[0]["completed_at"]
    assert calls[1] is None
    assert pending["data"]["trigger"]["agent_response"] is None


class _Result:
    def __init__(self, *, scalar=None, rowcount=1):
        self._scalar = scalar
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self._scalar


class _CloseSession:
    def __init__(self, fail_on_trigger=False):
        self.calls = []
        self.commits = 0
        self.fail_on_trigger = fail_on_trigger

    def execute(self, statement):
        self.calls.append(statement)
        if len(self.calls) == 1:
            return _Result(scalar=88)
        if len(self.calls) == 2:
            return _Result(rowcount=1)
        if self.fail_on_trigger:
            raise RuntimeError("injected trigger write failure")
        return _Result(rowcount=1)

    def commit(self):
        self.commits += 1


def _todo_repo(monkeypatch, session):
    repo = WatchTodoRepository.__new__(WatchTodoRepository)
    monkeypatch.setattr(WatchTodoRepository, "session", property(lambda _self: session))
    repo.get = lambda _id: SimpleNamespace(id=7, terminal="handled")
    return repo


def test_todo_close_synchronizes_trigger_in_same_transaction(monkeypatch):
    session = _CloseSession()
    repo = _todo_repo(monkeypatch, session)

    closed = repo.close(7, "handled", close_reason="规则已复核", closed_by="agent-dh")

    assert closed.terminal == "handled"
    assert len(session.calls) == 3  # 读 trigger_id、关 todo、对齐 trigger
    assert session.commits == 1


def test_todo_close_rolls_back_when_trigger_sync_fails(monkeypatch):
    session = _CloseSession(fail_on_trigger=True)
    repo = _todo_repo(monkeypatch, session)
    rolled_back = []
    repo._safe_rollback = lambda: rolled_back.append(True)

    with pytest.raises(RuntimeError, match="injected"):
        repo.close(7, "handled", close_reason="规则已复核")

    assert session.commits == 0
    assert rolled_back == [True]

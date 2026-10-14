"""裁决码落库与通知变量透传测试（REQ-261007133807-eda6 t8 · FR-2）

守三件事：
1) **"没叫"也要有码**：deduped 与 auto_observed 两种处置的行 `escalation_code` 非 NULL
   —— 只记录"叫"的理由等于把成本控制留成黑盒；
2) 码与理由从 notifier 一路透传到仓储（含去重短路分支，它不走通知但**必须落库**）；
3) **写库失败不阻断通知**：理由可见性不得反噬通知主链（失败只响亮留痕）。

真库读写用 pytest 下的测试库（conftest 负责切库），用例自清理。
"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from application.services.watch_engine.notifier import WatchNotifier
from domain.watch.services.escalation_verdict import EscalationCode

NOW = datetime(2026, 7, 21, 10, 30)


def _rule(rule_id=1, symbol='000001.SZ'):
    return SimpleNamespace(
        id=rule_id, symbol=symbol, intent='entry',
        conditions=[{'type': 'price_break', 'params': {'price': 100.0, 'direction': 'above'}}],
        action_hint={'trigger_level': 'L1', 'action_on_trigger': 'buy'},
        escalation_policy=None, context='t8 测试',
    )


class FakeTriggerRepo:
    def __init__(self, raise_on_record=False):
        self.recorded = []
        self._raise = raise_on_record

    def record(self, **kwargs):
        if self._raise:
            raise RuntimeError('模拟写库失败')
        self.recorded.append(kwargs)
        return SimpleNamespace(id=len(self.recorded))


class FakeFacade:
    def __init__(self):
        self.sent = 0
        self.kwargs = []

    def send_watch_triggered(self, **kwargs):
        self.sent += 1
        self.kwargs.append(kwargs)
        return SimpleNamespace(success=True)


def _quote():
    return SimpleNamespace(symbol='000001.SZ', price=101.0, prev_close=98.0,
                           volume=1_000_000, change_pct=None, name='平安银行')


def _result():
    return SimpleNamespace(value=101.0, message='现价 101.0 上破阈值 100.0', metric=None)


def test_code_and_reason_reach_repository_on_deduped():
    """去重短路分支：不发消息，但**必须落库带码**（账不能少、理由也不能少）。"""
    repo, facade = FakeTriggerRepo(), FakeFacade()
    notifier = WatchNotifier(trigger_repo=repo, notification_facade=facade, ws_url=None)
    rule = _rule()
    notifier.notify(rule, rule.conditions[0], _quote(), _result(),
                    disposition='deduped', disposition_reason='去重合并',
                    escalation_code=EscalationCode.DEDUPED,
                    escalation_reason='去重合并（同标的同向 60s 内）；原判：价格触发过五道门')
    assert facade.sent == 0
    assert len(repo.recorded) == 1
    assert repo.recorded[0]['escalation_code'] == EscalationCode.DEDUPED
    assert '原判' in repo.recorded[0]['escalation_reason']


def test_code_and_reason_reach_repository_and_notification_vars():
    """正常路径：落库带码 + 通知变量带码（卡面才可能显示"升级原因"）。"""
    repo, facade = FakeTriggerRepo(), FakeFacade()
    notifier = WatchNotifier(trigger_repo=repo, notification_facade=facade, ws_url=None)
    rule = _rule()
    notifier.notify(rule, rule.conditions[0], _quote(), _result(),
                    disposition='escalated', disposition_reason='过五道门',
                    escalation_code=EscalationCode.GATES_PASSED_ACTION,
                    escalation_reason='价格触发过五道门（buy）→ 进 agent 摘要队列')
    assert facade.sent == 1
    assert facade.kwargs[0].get('escalation_code') == EscalationCode.GATES_PASSED_ACTION
    assert repo.recorded[0]['escalation_code'] == EscalationCode.GATES_PASSED_ACTION


def test_record_failure_does_not_block_notification(capsys):
    """写库失败：通知照发，错误响亮留痕（理由可见性不得反噬主链）。

    留痕断言走 stdout 而非 caplog：本仓日志是 structlog（直接写 stdout），
    不经 stdlib logging —— 用 caplog 会"看起来没留痕"（实测踩过）。
    """
    repo, facade = FakeTriggerRepo(raise_on_record=True), FakeFacade()
    notifier = WatchNotifier(trigger_repo=repo, notification_facade=facade, ws_url=None)
    rule = _rule()
    trigger = notifier.notify(rule, rule.conditions[0], _quote(), _result(),
                              disposition='escalated',
                              escalation_code=EscalationCode.GATES_PASSED_ACTION)
    assert facade.sent == 1, '落库失败不得阻断通知'
    assert trigger is None, '落库失败返回 None（供调用方知悉），但通知已发出'
    out = capsys.readouterr().out
    assert '触发记录落库失败' in out and '模拟写库失败' in out


# ── 真库：两列确实落到行上（psql 等价）────────────────────────────────
@pytest.fixture
def cleanup_triggers():
    from sqlalchemy import text

    from infrastructure.persistence.database.engine import get_engine
    ids = []
    yield ids
    if ids:
        with get_engine().begin() as conn:
            conn.execute(text('delete from quant.watch_triggers where id = any(:ids)'), {'ids': ids})


@pytest.mark.parametrize('disposition,code', [
    ('deduped', EscalationCode.DEDUPED),
    ('auto_observed', EscalationCode.BUDGET_EXHAUSTED),
])
def test_not_waking_dispositions_still_carry_code_in_db(disposition, code, cleanup_triggers):
    """**"没叫"也有码**（FR-2 判据）：deduped 与 auto_observed 的行码非 NULL。"""
    from sqlalchemy import text

    from adapters.outbound.repositories.watch_rule_repository import WatchTriggerRepository
    from infrastructure.persistence.database.engine import get_engine

    t = WatchTriggerRepository().record(
        rule_id=None, symbol='T8TEST', condition={'type': 'price_break'},
        trigger_price=1.23, detail={'message': 't8'}, notified=False,
        disposition=disposition, disposition_reason='t8 判据',
        escalation_code=code, escalation_reason='没叫的理由：%s' % code)
    cleanup_triggers.append(t.id)

    with get_engine().connect() as conn:
        row = conn.execute(text('select escalation_code, escalation_reason from quant.watch_triggers '
                                'where id = :i'), {'i': t.id}).first()
    assert row is not None
    assert row[0] == code, row
    assert row[1] and code in row[1] or row[1]


def test_null_code_is_only_for_rows_that_never_reached_a_verdict(cleanup_triggers):
    """对照组：不传码时落 NULL（= 改造前/未接入裁决的历史行语义），不是空串。"""
    from sqlalchemy import text

    from adapters.outbound.repositories.watch_rule_repository import WatchTriggerRepository
    from infrastructure.persistence.database.engine import get_engine

    t = WatchTriggerRepository().record(
        rule_id=None, symbol='T8TEST', condition={'type': 'price_break'},
        trigger_price=1.23, detail={'message': 't8'}, notified=False,
        disposition='pending')
    cleanup_triggers.append(t.id)
    with get_engine().connect() as conn:
        row = conn.execute(text('select escalation_code from quant.watch_triggers where id = :i'),
                           {'i': t.id}).first()
    assert row[0] is None

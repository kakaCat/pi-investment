"""成交回执共享的执行指令模型与持仓读取。"""
from datetime import datetime
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.exec_directive import (
    ExecAction,
    ExecState,
    NotExecutableReason,
    PositionFacts,
    build_exec_directive,
    read_position_facts,
)

NOW = datetime(2026, 10, 23, 10, 0)


def _rule():
    return SimpleNamespace(
        id=1, symbol='600519.SH', intent='exit_stop', cost_price=28.0,
        account='agent_brain', linked_account='agent_brain', conditions=[])


def test_stop_uses_available_shares_not_total():
    directive = build_exec_directive(
        rule=_rule(), level='P0', now=NOW, trigger_price=26.5,
        position=PositionFacts(shares_total=2000, shares_available=300, avg_cost=28.0))
    assert directive.action is ExecAction.EXECUTE_STOP_LOSS
    assert directive.executable is True
    assert directive.qty == 300
    assert '余 1700 股' in directive.card_action_text()


def test_t1_locked_is_not_executable():
    directive = build_exec_directive(
        rule=_rule(), level='P0', now=NOW,
        position=PositionFacts(shares_total=1000, shares_available=0, avg_cost=28.0))
    assert directive.executable is False
    assert directive.not_executable_reason is NotExecutableReason.T1_LOCKED


def test_position_read_failure_stays_executable():
    directive = build_exec_directive(
        rule=_rule(), level='P0', now=NOW, position_read='degraded')
    assert directive.executable is True
    assert directive.evidence['position_read'] == 'degraded'


def test_missing_account_blocks_execution():
    rule = _rule()
    rule.account = None
    rule.linked_account = None
    directive = build_exec_directive(rule=rule, level='P0', now=NOW)
    assert directive.executable is False
    assert directive.not_executable_reason is NotExecutableReason.ACCOUNT_UNKNOWN


def test_non_exit_intent_has_no_execution_action():
    rule = _rule()
    rule.intent = 'entry'
    directive = build_exec_directive(rule=rule, level='P1', now=NOW)
    assert directive.action is ExecAction.NONE


def test_read_position_facts_ok_and_missing():
    class Repo:
        def get_position(self, account, symbol):
            if symbol == '000001':
                return None
            return SimpleNamespace(shares_total=100, shares_available=80, avg_cost=20.0)

    facts, state = read_position_facts('a', '600519', repo=Repo())
    assert state == 'ok'
    assert facts.shares_available == 80
    missing, state = read_position_facts('a', '000001', repo=Repo())
    assert missing is None and state == 'missing'


def test_read_position_failure_is_degraded_not_flat():
    class Repo:
        def get_position(self, account, symbol):
            raise RuntimeError('db down')

    facts, state = read_position_facts('a', '600519', repo=Repo())
    assert facts is None and state == 'degraded'


def test_action_items_include_hold_and_nonterminal_timeout():
    directive = build_exec_directive(rule=_rule(), level='P0', now=NOW)
    states = [item.state for item in directive.action_items]
    assert ExecState.HOLD in states
    timeout = next(item for item in directive.action_items if item.state is ExecState.TIMEOUT)
    assert timeout.terminal is None
    assert timeout.escalate is True

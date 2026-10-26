"""真实成交落库后发事件（REQ-261021194640-69b8 FR-1/FR-2，卡 t-a5fa64）

判据：
  1. 卖出成交投影成 FillEvent 后，监听方收到 action=sell 且 trade_id 非空；
  2. 监听方抛错时**不反噬成交**（不发异常、不改成交结果）；
  3. 未注册监听者时为空操作（旧行为）；
  4. `execute_trade` 在事务提交**之后**才发事件（成交不被回执绑架）。
"""
import inspect

import pytest

from qs_trading.application.ports.fill_listener import (
    FillEvent,
    get_fill_listener,
    register_fill_listener,
    unregister_fill_listener,
)
from qs_trading.application.services.account_trading_service import AccountTradingService


class Recording:
    def __init__(self):
        self.events = []

    def on_fill(self, event):
        self.events.append(event)


class Boom:
    def on_fill(self, event):
        raise RuntimeError('listener down')


@pytest.fixture(autouse=True)
def _clean_registry():
    unregister_fill_listener()
    yield
    unregister_fill_listener()


def test_sell_fill_emits_structured_event():
    rec = Recording()
    register_fill_listener(rec)

    AccountTradingService._emit_fill_notification(
        account_name='agent_virtual', symbol='000425.SZ', action='SELL',
        shares=1000, price=10.5, trade_id=1234, order_id=99, reason='止损')

    assert len(rec.events) == 1
    event = rec.events[0]
    assert isinstance(event, FillEvent)
    assert event.action == 'sell'
    assert event.trade_id == 1234
    assert event.account_name == 'agent_virtual'
    assert event.symbol == '000425.SZ'
    assert event.shares == 1000 and event.price == 10.5
    assert event.source == 'agent_trade'
    assert event.decision_audit_id is None


def test_listener_failure_does_not_raise():
    register_fill_listener(Boom())
    # 不抛异常 = 成交结果不受影响
    AccountTradingService._emit_fill_notification(
        account_name='agent_virtual', symbol='000425.SZ', action='sell',
        shares=100, price=10.0, trade_id=1)


def test_unregistered_listener_is_noop():
    assert get_fill_listener() is None
    AccountTradingService._emit_fill_notification(
        account_name='agent_virtual', symbol='000425.SZ', action='buy',
        shares=100, price=10.0, trade_id=2)


def test_execute_trade_emits_after_commit():
    """接线证据：execute_trade 源码里事件发送位于 `session.commit()` 之后。"""
    source = inspect.getsource(AccountTradingService.execute_trade)
    commit_at = source.index('self.repo.session.commit()')
    emit_at = source.index('_emit_fill_notification(')
    assert emit_at > commit_at, '成交回写必须在事务提交之后（不随回执回滚）'
    assert 'fill_notify_error' not in source  # 错误处理在 helper 内

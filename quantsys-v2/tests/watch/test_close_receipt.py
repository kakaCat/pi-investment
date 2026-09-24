"""REQ-260924104605-ad0a t5 验收测试（FR-14 处置结论回执）。

验收锚点（task t-72b739 acceptance）：
  · close 收敛后 sender 收到的卡片包含结论/原因/next_condition 三要素；
  · terminal=ignored 时文案包含 NEXT 条件原文；
  · 重复 close 返回 duplicate / 409，不重复发送；
  · receipt_service=None 时行为与改前一致。
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from application.services.watch_engine.receipt_service import ReceiptService
from application.services.watch_engine.todo_service import TodoService
from domain.watch.ports import WatchTodoAlreadyClosed

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _todo(id_=32, **over):
    base = dict(id=id_, symbol='601888', level='P1', flow_state='L3',
                account='agent_virtual', due_at=NOW - timedelta(hours=1),
                terminal=None)
    base.update(over)
    return SimpleNamespace(**base)


class FakeTodoRepo:
    """最小待办仓储：close 路径只用 get/close（并发语义 = 已终态返回 None）。"""

    def __init__(self, todos):
        self.rows = {t.id: t for t in todos}

    def get(self, todo_id):
        return self.rows.get(todo_id)

    def close(self, todo_id, terminal, close_reason=None, next_condition=None,
              action_kind=None, decision_audit_id=None, closed_by=None, now=None):
        todo = self.rows.get(todo_id)
        if todo is None or getattr(todo, 'terminal', None):
            return None
        todo.terminal = terminal
        todo.close_reason = close_reason
        todo.next_condition = next_condition
        todo.action_kind = action_kind
        todo.decision_audit_id = decision_audit_id
        todo.closed_by = closed_by
        todo.closed_at = now or NOW
        return todo


class FakeReceiptRepo:
    def __init__(self):
        self.rows = []

    def record(self, todo_id, kind, channel=None, delivery_status=None,
               message_id=None, payload_digest=''):
        row = dict(todo_id=todo_id, kind=kind, channel=channel,
                   delivery_status=delivery_status, message_id=message_id,
                   payload_digest=payload_digest)
        self.rows.append(row)
        return row

    def list_by_todo(self, todo_id):
        return [r for r in self.rows if r['todo_id'] == todo_id]

    def exists(self, todo_id, kind, payload_digest=''):
        return any(r['todo_id'] == todo_id and r['kind'] == kind
                   and r['payload_digest'] == payload_digest for r in self.rows)


def _service(todos, sent, names=None, with_receipt=True):
    receipt = (ReceiptService(FakeReceiptRepo(), sender=sent.append)
               if with_receipt else None)
    resolver = (SimpleNamespace(resolve_batch=lambda symbols: {
        str(s).split('.')[0].strip(): (names or {}).get(str(s).split('.')[0].strip())
        for s in symbols}) if names is not None else None)
    return TodoService(FakeTodoRepo(todos), receipt_service=receipt,
                       name_resolver=resolver), receipt


# ── 三要素卡片 ──────────────────────────────────────────────────────────────
def test_close_handled_sends_three_element_card():
    sent = []
    svc, _ = _service([_todo()], sent, names={'601888': '中国中免'})
    todo, outcome = svc.close_and_receipt(
        32, 'handled', close_reason='已按预案处置', action_kind='observe')

    assert outcome is not None and outcome['sent'] is True
    assert outcome['kind'] == 'result'
    assert len(sent) == 1                                  # 即时单条（不聚合）
    card = sent[0]['message']
    assert '结论：已处置（不动）' in card                    # 要素一：结论（终态+动作）
    assert '原因：已按预案处置' in card                      # 要素二：原因原文
    assert '后续意见：无' in card                            # 要素三：后续意见
    assert '中国中免（601888）' in card                      # 名称（代码），FR-13
    assert '归属 agent_virtual' in card


def test_close_ignored_card_contains_next_condition_verbatim():
    sent = []
    svc, _ = _service([_todo()], sent, names={'601888': '中国中免'})
    _, outcome = svc.close_and_receipt(
        32, 'ignored', close_reason='破位放弃',
        next_condition='价格重新站回 20 日线')

    assert outcome['sent'] is True
    card = sent[0]['message']
    assert '结论：忽略（不动）' in card
    assert '后续意见：NEXT 价格重新站回 20 日线' in card     # NEXT 条件原文


def test_close_trade_action_shown_in_conclusion():
    sent = []
    svc, _ = _service([_todo()], sent, names={'601888': '中国中免'})
    svc.close_and_receipt(32, 'handled', close_reason='触发止损',
                          action_kind='trade', decision_audit_id='DA-1')
    assert '结论：已处置（已执行交易）' in sent[0]['message']


# ── 重复处置不重复发送 ──────────────────────────────────────────────────────
def test_duplicate_close_raises_and_never_resends():
    sent = []
    svc, receipt = _service([_todo()], sent, names={'601888': '中国中免'})
    svc.close_and_receipt(32, 'handled', close_reason='已按预案处置')
    assert len(sent) == 1

    with pytest.raises(WatchTodoAlreadyClosed):            # 重复 close → 409
        svc.close_and_receipt(32, 'handled', close_reason='再点一次')
    assert len(sent) == 1                                  # 没有第二次发送

    # 回执层兜底：同一 (todo, kind, digest) 重试 → duplicate，不重发
    closed = svc.close.__self__._repo.get(32)
    again = receipt.result(closed, terminal='handled', name='中国中免',
                           close_reason='已按预案处置')
    assert again['duplicate'] is True and again['sent'] is False
    assert len(sent) == 1


# ── 未注入回执 = 行为与改前一致 ─────────────────────────────────────────────
def test_without_receipt_service_behaves_as_before():
    sent = []
    svc, receipt = _service([_todo()], sent, with_receipt=False)
    assert receipt is None
    todo, outcome = svc.close_and_receipt(32, 'handled', close_reason='已处置')
    assert todo.terminal == 'handled'                      # 收敛照常
    assert outcome is None                                 # 无回执，与改前一致
    assert sent == []


# ── 诚实降级 ────────────────────────────────────────────────────────────────
def test_name_missing_marks_name_missing():
    sent = []
    svc, _ = _service([_todo()], sent, names={'601888': None})
    svc.close_and_receipt(32, 'handled', close_reason='已处置')
    assert '601888（名称缺失）' in sent[0]['message']        # R-013 不臆造


def test_receipt_failure_does_not_break_close():
    """回执落库异常：收敛已生效、outcome=None、不抛（响亮记日志）。"""
    class BoomRepo(FakeReceiptRepo):
        def exists(self, todo_id, kind, payload_digest=''):
            raise RuntimeError('receipt db down')

    sent = []
    receipt = ReceiptService(BoomRepo(), sender=sent.append)
    svc = TodoService(FakeTodoRepo([_todo()]), receipt_service=receipt)
    todo, outcome = svc.close_and_receipt(32, 'handled', close_reason='已处置')
    assert todo.terminal == 'handled'                      # 收敛主线不受影响
    assert outcome is None

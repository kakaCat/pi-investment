"""result 回执即时投递（2026-10-26 修复跨请求内存缓冲丢失）。

验收锚点：
  · close 收敛后同一服务调用内立即发送，不依赖外部 flush；
  · 多次收敛各自独立发送，不进入进程内存聚合；
  · 幂等：同一待办同一终态重复 result → duplicate，不重复发送；
  · 通道失败如实记 failed，仓储落库失败向上抛（由 TodoService 兜底为收敛成功、回执丢失）。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.receipt_service import ReceiptService

NOW = datetime(2026, 10, 26, 10, 0, 0)
DUE = NOW - timedelta(hours=1)


def _todo(tid, level='P2'):
    return SimpleNamespace(id=tid, symbol='601888', level=level, flow_state='L3',
                           account='agent_brain', due_at=DUE, escalate_count=0,
                           created_at=NOW - timedelta(hours=2), claimed_at=None,
                           closed_at=NOW)


class _Repo:
    def __init__(self):
        self.rows = []

    def exists(self, todo_id, kind, payload_digest=''):
        return any(r['todo_id'] == todo_id and r['kind'] == kind
                   and r['payload_digest'] == payload_digest for r in self.rows)

    def record(self, todo_id, kind, channel=None, delivery_status=None,
               message_id=None, payload_digest=''):
        self.rows.append(dict(todo_id=todo_id, kind=kind, channel=channel,
                              delivery_status=delivery_status,
                              payload_digest=payload_digest))
        return self.rows[-1]


_UNSET = object()


def _svc(sender=_UNSET):
    sent = []
    repo = _Repo()
    svc = ReceiptService(repo, sender=sent.append if sender is _UNSET else sender)
    return svc, repo, sent


def test_single_close_sends_immediately():
    svc, repo, sent = _svc()
    out = svc.result(_todo(1), terminal='ignored', close_reason='不动',
                     next_condition='回升 10 元以上')
    assert out['issued'] is True and out['sent'] is True
    assert len(sent) == 1
    assert sent[0]['kind'] == 'result'
    assert '结论：忽略（不动）' in sent[0]['message']
    assert 'NEXT 回升 10 元以上' in sent[0]['message']
    assert len(repo.rows) == 1
    assert repo.rows[0]['delivery_status'] == 'sent'


def test_multiple_closes_send_independently():
    svc, repo, sent = _svc()
    for tid in (1, 2, 3):
        svc.result(_todo(tid), terminal='handled', close_reason='已处置')
    assert len(sent) == 3
    assert len({row['payload_digest'] for row in repo.rows}) == 3


def test_duplicate_close_never_resends():
    svc, repo, sent = _svc()
    first = svc.result(_todo(1), terminal='handled')
    second = svc.result(_todo(1), terminal='handled')
    assert first['issued'] is True
    assert second['duplicate'] is True and second['sent'] is False
    assert len(sent) == 1
    assert sent[0]['message'].count('待办#') == 1


def test_sender_failure_records_failed():
    def _boom(payload):
        raise RuntimeError('channel down')

    svc, repo, _ = _svc(sender=_boom)
    out = svc.result(_todo(1), terminal='handled', close_reason='已处置')
    assert out['sent'] is False and out['delivery_status'] == 'failed'
    assert repo.rows[0]['delivery_status'] == 'failed'


def test_missing_sender_is_honest_log_only():
    svc, repo, _ = _svc(sender=None)
    out = svc.result(_todo(1), terminal='handled')
    assert out['sent'] is False and out['delivery_status'] == 'log_only'
    assert repo.rows[0]['delivery_status'] == 'log_only'

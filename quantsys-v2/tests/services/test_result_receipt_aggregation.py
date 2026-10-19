"""result 回执聚合（2026-10-19：批量处置一次 41 张卡的修复）

验收锚点：
  · 稳态单条：缓冲→窗口兜底 flush 一张卡（结论不丢，延迟 ≤ 窗口+巡检周期）
  · 批量：窗口内 3 条收敛 → 1 张卡 3 行，逐条落库
  · 到量立即 flush（8 条上限）
  · 幂等：同一待办同一终态重复 result → duplicate，不重复进行
  · 巡检收尾兜底 flush_result_buffer
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.receipt_service import (
    RESULT_AGG_CAP, ReceiptService,
)

NOW = datetime(2026, 10, 19, 14, 0, 0)
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


def _svc():
    sent = []
    repo = _Repo()
    svc = ReceiptService(repo, sender=sent.append)
    return svc, repo, sent


def test_batch_three_closes_one_card():
    svc, repo, sent = _svc()
    for tid in (1, 2, 3):
        svc.result(_todo(tid), terminal='handled', close_reason='已处置')
    assert sent == []                              # 窗口未满不自动发（投递层聚合）
    svc.flush_result_buffer()
    assert len(sent) == 1                          # 3 条 → 1 张卡
    card = sent[0]
    assert card['kind'] == 'result'
    assert '3 项待办已收敛' in card['message']
    assert card['message'].count('待办#') == 3     # 逐条溯源
    assert len(repo.rows) == 3                     # 逐条落库
    assert all(r['delivery_status'] == 'sent' for r in repo.rows)


def test_cap_flushes_immediately():
    svc, repo, sent = _svc()
    for tid in range(1, RESULT_AGG_CAP + 1):
        svc.result(_todo(tid), terminal='handled', close_reason='x')
    assert len(sent) == 1                          # 到量即 flush
    assert '8 项待办已收敛' in sent[0]['message']
    assert svc._result_buffer == []


def test_duplicate_close_not_buffered_twice():
    svc, repo, sent = _svc()
    first = svc.result(_todo(1), terminal='handled')
    second = svc.result(_todo(1), terminal='handled')
    assert first['issued'] is True
    assert second['duplicate'] is True
    svc.flush_result_buffer()
    assert len(sent) == 1
    assert sent[0]['message'].count('待办#') == 1  # 同一待办只出现一次


def test_empty_flush_is_noop():
    svc, repo, sent = _svc()
    out = svc.flush_result_buffer()
    assert out['count'] == 0 and sent == []


def test_single_close_delayed_until_window_flush():
    svc, repo, sent = _svc()
    svc.result(_todo(1), terminal='ignored', close_reason='不动',
               next_condition='回升 10 元以上')
    assert sent == []                              # 稳态：先入缓冲（≤90s+巡检内必达）
    out = svc.flush_result_buffer()
    assert out['count'] == 1 and len(sent) == 1
    assert '1 项待办已收敛' in sent[0]['message']
    assert 'NEXT 回升 10 元以上' in sent[0]['message']

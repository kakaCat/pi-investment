"""REQ-260924104605-ad0a t4 验收测试（FR-8 聚合 / FR-11 文案 / FR-13 名称解析）。

验收锚点（task t-01322d acceptance）：
  · 同周期 3 条超时 → sender 调用 1 次、卡片包含 3 行且每行含归属账户；
  · 重跑同周期全部 duplicate、sender 调用 0 次；
  · 空组 flush 返回 no-op；
  · 回执文案不包含微秒与「| 周期 |」、due 只出现 1 次；
  · 名称未命中时返回纯代码+「名称缺失」标注。
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from adapters.inbound.fastapi_app.watch_sla_job import WatchSlaJob
from application.services.watch_engine.receipt_service import (
    DELIVERY_LOG_ONLY,
    DELIVERY_SENT,
    ReceiptService,
    render_receipt,
)

NOW = datetime(2026, 9, 24, 12, 14, tzinfo=timezone.utc)
DUE = NOW - timedelta(hours=2, minutes=14)      # 已超时 2h14m


def _todo(id_, flow='L3', **over):
    base = dict(id=id_, symbol='601888', level='P1', flow_state=flow,
                account='agent_virtual', due_at=DUE, escalate_count=0)
    base.update(over)
    return SimpleNamespace(**base)


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


class FakeTodoRepo:
    """最小待办仓储：list_overdue + promote（支持 L3 计数累加语义）。"""

    def __init__(self, todos):
        self.rows = {t.id: t for t in todos}

    def list_overdue(self, now=None, limit=100):
        return list(self.rows.values())

    def promote(self, todo_id, to_state, now=None, escalate_count=None):
        todo = self.rows.get(todo_id)
        if todo is None:
            return None
        todo.flow_state = to_state
        if escalate_count is not None:
            todo.escalate_count = escalate_count
        return todo


class FakeNameResolver:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def resolve_batch(self, symbols):
        self.calls.append(list(symbols))
        return {str(s).split('.')[0].strip(): self.mapping.get(str(s).split('.')[0].strip())
                for s in symbols}


def _job(todos, sent, resolver=None):
    receipts = FakeReceiptRepo()
    service = ReceiptService(receipts, sender=sent.append)
    job = WatchSlaJob(FakeTodoRepo(todos), service, name_resolver=resolver)
    return job, receipts


# ── FR-8：一周期一卡 ────────────────────────────────────────────────────────
def test_three_timeouts_same_cycle_one_card_three_lines():
    sent = []
    todos = [_todo(31, symbol='601888', account='agent_virtual'),
             _todo(32, symbol='002916', account='user_main_simulation'),
             _todo(33, symbol='600150', account='agent_brain')]
    job, receipts = _job(todos, sent)

    stats = job.run_once(NOW)

    assert stats['timeout'] == 3 and stats['group_cards'] == 1
    assert len(sent) == 1                                  # sender 只调 1 次
    card = sent[0]['message']
    lines = [l for l in card.split(chr(10)) if l.startswith('- ')]
    assert len(lines) == 3                                 # 卡片 3 行
    assert '⏰ 超时回执 ｜ 3 项待办超时未处置' in card
    for account in ('agent_virtual', 'user_main_simulation', 'agent_brain'):
        assert f'归属 {account}' in card                   # 每行含归属账户
    assert len(receipts.rows) == 3                         # 逐条落库（不重不漏）
    assert all(r['delivery_status'] == DELIVERY_SENT for r in receipts.rows)
    assert sent[0]['os_channel'] == 'risk_stop'            # timeout → 高优频道
    assert all(r['message_id'] == receipts.rows[0]['message_id'] for r in receipts.rows)


def test_rerun_same_cycle_all_duplicate_zero_sender_calls():
    sent = []
    job, receipts = _job([_todo(34)], sent)
    job.run_once(NOW)
    assert len(sent) == 1

    stats2 = job.run_once(NOW)                             # 重跑同周期
    assert stats2['duplicates'] == 1 and stats2['timeout'] == 0
    assert len(sent) == 1                                  # sender 0 次新调用
    assert stats2['group_cards'] == 0                      # 空组不发
    assert len(receipts.rows) == 1                         # 不重复落库


def test_empty_group_flush_is_noop():
    sent = []
    receipts = FakeReceiptRepo()
    service = ReceiptService(receipts, sender=sent.append)
    service.begin_group()
    summary = service.flush_grouped()
    assert summary == {} and sent == [] and receipts.rows == []


def test_log_only_when_sender_missing():
    receipts = FakeReceiptRepo()
    service = ReceiptService(receipts, sender=None)
    service.begin_group()
    service.timeout(_todo(35))
    summary = service.flush_grouped()
    assert summary['timeout']['delivery_status'] == DELIVERY_LOG_ONLY
    assert summary['timeout']['sent'] is False
    assert receipts.rows[0]['delivery_status'] == DELIVERY_LOG_ONLY


def test_escalate_group_routes_watch_symbol():
    sent = []
    job, _ = _job([_todo(36, flow='L1', level='P2')], sent)
    job.run_once(NOW)
    assert len(sent) == 1
    assert sent[0]['kind'] == 'escalate'
    assert sent[0]['os_channel'] == 'watch_symbol'         # 非 timeout/P0 → 普通位
    assert '🔺 升级即回执' in sent[0]['message']


# ── FR-13：名称一轮一次批量解析 + 缺失降级 ──────────────────────────────────
def test_names_resolved_once_per_cycle_and_rendered():
    sent = []
    resolver = FakeNameResolver({'601888': '中国中免', '002916': '深南电路'})
    todos = [_todo(41, symbol='601888'), _todo(42, symbol='002916'),
             _todo(43, symbol='601138')]                   # 601138 未命中
    job, _ = _job(todos, sent, resolver=resolver)

    job.run_once(NOW)

    assert len(resolver.calls) == 1                        # 一轮一次联查（无 N+1）
    assert set(resolver.calls[0]) == {'601888', '002916', '601138'}
    card = sent[0]['message']
    assert '中国中免（601888）' in card
    assert '深南电路（002916）' in card
    assert '601138（名称缺失）' in card                    # 未命中如实降级（R-013）


def test_no_resolver_marks_name_missing():
    sent = []
    job, _ = _job([_todo(44)], sent, resolver=None)
    job.run_once(NOW)
    assert '601888（名称缺失）' in sent[0]['message']


# ── FR-11：文案卫生 ─────────────────────────────────────────────────────────
def test_receipt_text_has_no_micros_no_period_tag_due_once():
    text = render_receipt(_todo(45), kind='timeout', period='|<iso-due>', now=NOW)
    assert '已超时 2h14m' in text
    assert '截止 09-24 10:00' in text
    assert text.count('10:00') == 1                        # due 只出现 1 次
    assert '.000000' not in text and '微秒' not in text
    assert '| 周期 |' not in text and '周期' not in text   # period 不外露
    import re
    assert not re.search(r'\d{2}:\d{2}:\d{2}\.\d+', text)   # 无 ISO 微秒尾巴


def test_result_not_grouped_sends_immediately():
    """FR-14 前置：处置结论不参与聚合，即使聚合轮开启也即时投递。"""
    sent = []
    receipts = FakeReceiptRepo()
    service = ReceiptService(receipts, sender=sent.append)
    todo = _todo(46)
    todo.close_reason = '破位放弃'
    service.begin_group()
    outcome = service.result(todo, terminal='ignored')
    assert outcome['sent'] is True
    assert len(sent) == 1                                  # 即时单条，不等 flush
    assert service.flush_grouped() == {}                   # 组里没残留

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

    def promote(self, todo_id, to_state, now=None, escalate_count=None,
                extend_due_minutes=30):
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


# ── agent 自有待办：私信唤醒，不占用户卡（2026-10-16）────────────────────────
def test_agent_owned_all_woken_sends_no_user_card():
    """一轮内 agent 自有条目全部唤醒成功 → 0 张用户卡，但仍逐条落库（可追溯）"""
    sent = []
    receipts = FakeReceiptRepo()
    woken = []
    service = ReceiptService(receipts, sender=sent.append,
                             agent_waker=lambda t, ctx: woken.append(t.id) or True)
    service.begin_group()
    for todo in (_todo(41, owner_kind='agent', owner_ref='agent-dh'),
                 _todo(42, owner_kind='agent', owner_ref='agent-dh')):
        service.timeout(todo)
    summary = service.flush_grouped()

    assert sent == []                                  # 私信占满一轮 = 用户一张卡都不发
    assert woken == [41, 42]
    assert summary['timeout'] == {'count': 2, 'card_count': 0, 'sent': True,
                                  'delivery_status': DELIVERY_SENT, 'batch_id': None}
    assert [r['delivery_status'] for r in receipts.rows] == [DELIVERY_SENT, DELIVERY_SENT]
    assert [r['message_id'] for r in receipts.rows] == ['wake', 'wake']


def test_agent_owned_wake_failure_folds_into_same_card():
    """agent 自有 P1 唤醒失败 → 折进本轮同一张卡（一行一条，不按条炸卡）"""
    sent = []
    receipts = FakeReceiptRepo()
    service = ReceiptService(receipts, sender=sent.append, agent_waker=lambda t, ctx: False)
    service.begin_group()
    service.timeout(_todo(43, level='P1', owner_kind='agent', owner_ref='agent-dh'))
    service.timeout(_todo(44, level='P1', owner_kind='agent', owner_ref='agent-dh'))
    summary = service.flush_grouped()

    assert len(sent) == 1                              # 一张卡
    assert sent[0]['message'].count('- 待办#') == 2    # 两行
    assert summary['timeout']['card_count'] == 1 and summary['timeout']['count'] == 2
    assert all(r['delivery_status'] == DELIVERY_SENT for r in receipts.rows)


def test_agent_owned_p2_wake_failure_stays_ledger_only():
    """P2 agent 自有唤醒失败：只记 failed，不折进用户卡（级别策略：不打扰用户）"""
    sent = []
    receipts = FakeReceiptRepo()
    service = ReceiptService(receipts, sender=sent.append, agent_waker=lambda t, ctx: False)
    service.begin_group()
    service.timeout(_todo(45, level='P2', owner_kind='agent', owner_ref='agent-dh'))
    summary = service.flush_grouped()

    assert sent == []
    assert summary['timeout']['card_count'] == 0 and summary['timeout']['sent'] is True
    assert receipts.rows[0]['delivery_status'] == 'failed'


def test_log_only_when_sender_missing():
    receipts = FakeReceiptRepo()
    service = ReceiptService(receipts, sender=None)
    service.begin_group()
    service.timeout(_todo(35))
    summary = service.flush_grouped()
    assert summary['timeout']['delivery_status'] == DELIVERY_LOG_ONLY
    assert summary['timeout']['sent'] is False
    assert receipts.rows[0]['delivery_status'] == DELIVERY_LOG_ONLY


def test_promotion_sends_no_group_card():
    """REQ-261016155500-4f2a：升级回执下线——晋升不产生任何聚合卡/回执。"""
    sent = []
    job, receipts = _job([_todo(36, flow='L1', level='P2')], sent)
    stats = job.run_once(NOW)
    assert stats['promoted'] == 1 and stats['escalated'] == 0
    assert sent == [] and receipts.rows == []


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

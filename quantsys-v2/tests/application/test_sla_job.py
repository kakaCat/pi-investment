"""到期待办巡检单测（REQ-c9f899 t6）

覆盖 t6 验收：L1→L2、L2→L3、L3 超时升级给用户、幂等不重发、单条异常继续、
仓储抛错降级不崩、sender 抛错不影响、upgrade 计数，以及端口/适配器签名防漂移。

为什么用内存 fake 而不是真库：本任务的核心是**编排与幂等**（谁在什么状态下该发哪段回执、
同一 due 周期只发一次），fake 才能精确断言"该跳过时有没有误发/误写"；真库路径由
tests/application/test_todo_service.py 与 tests/api/* 走真实适配器覆盖。适配器的写库前校验
（空 digest/非法 kind）不碰 DB，故在本文件直接对真适配器断言。

⚠️ 诚实边界：sender 缺省为 None（log-only，真实通道接线归 t12）——所有"已送达"断言都
显式注入 sender，不把 log-only 当成功。
"""
import inspect
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from adapters.inbound.fastapi_app.watch_sla_job import WatchSlaJob
from adapters.outbound.repositories.watch_receipt_repository import WatchReceiptRepository
from application.services.watch_engine.receipt_service import (
    CHANNEL_ALERTS,
    CHANNEL_REPORTS,
    DELIVERY_FAILED,
    DELIVERY_LOG_ONLY,
    DELIVERY_SENT,
    ReceiptService,
    payload_digest,
    resolve_channel,
)
from domain.watch.ports import IWatchReceiptRepository, RECEIPT_KINDS

NOW = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)
DUE_PAST = NOW - timedelta(minutes=5)


# ── fakes ────────────────────────────────────────────────────

@dataclass
class FakeTodo:
    """待办记录（属性与 quant.watch_todos 对齐，供 duck-typed 访问）"""
    id: int
    symbol: str = '600150'
    level: str = 'P2'
    flow_state: str = 'L1'
    account: str = 'agent_brain'
    due_at: datetime = None
    escalate_count: int = 0
    terminal: str = None


class FakeTodoRepo:
    """IWatchTodoRepository 的内存子集（list_overdue / promote，行为对齐适配器契约）"""

    def __init__(self, rows=()):
        self.rows = {t.id: t for t in rows}
        self.list_calls = []
        self.promote_calls = []
        self.list_boom = False
        self.promote_none_ids = set()
        self.promote_boom_ids = set()

    def list_overdue(self, now=None, limit=100):
        self.list_calls.append({'now': now, 'limit': limit})
        if self.list_boom:
            raise RuntimeError('db down')
        cutoff = now or NOW
        rows = [t for t in self.rows.values()
                if t.terminal is None and t.due_at is not None and t.due_at < cutoff]
        rows.sort(key=lambda t: t.due_at)
        return rows[:limit]

    def promote(self, todo_id, to_state, *, escalate_count=None, now=None):
        self.promote_calls.append({'todo_id': todo_id, 'to_state': to_state,
                                   'escalate_count': escalate_count})
        if todo_id in self.promote_boom_ids:
            raise RuntimeError('promote down')
        todo = self.rows.get(todo_id)
        if todo is None or todo.terminal is not None or todo_id in self.promote_none_ids:
            return None
        todo.flow_state = to_state
        todo.escalate_count = (todo.escalate_count + 1 if escalate_count is None
                               else escalate_count)
        return todo


class FakeReceiptRepo:
    """IWatchReceiptRepository 的内存实现（method 签名须与端口一致，见签名比对测试）"""

    def __init__(self):
        self.rows = []
        self._seq = 0
        self.record_calls = []
        self.exists_calls = []
        self.exists_boom = False
        self.record_boom = False

    def record(self, todo_id, kind, channel=None, delivery_status=None, message_id=None,
               payload_digest=''):
        self.record_calls.append({'todo_id': todo_id, 'kind': kind, 'channel': channel,
                                  'delivery_status': delivery_status,
                                  'payload_digest': payload_digest})
        if self.record_boom:
            raise RuntimeError('receipt db down')
        self._seq += 1
        row = {'id': self._seq, 'todo_id': todo_id, 'kind': kind, 'channel': channel,
               'delivery_status': delivery_status, 'message_id': message_id,
               'payload_digest': payload_digest}
        self.rows.append(row)
        return row

    def list_by_todo(self, todo_id):
        return [r for r in self.rows if r['todo_id'] == todo_id]

    def exists(self, todo_id, kind, payload_digest=''):
        self.exists_calls.append((todo_id, kind, payload_digest))
        if self.exists_boom:
            raise RuntimeError('exists down')
        return any(r['todo_id'] == todo_id and r['kind'] == kind
                   and r['payload_digest'] == payload_digest for r in self.rows)


def build_job(todo_repo, receipts=None, sender=None, limit=100):
    """组装巡检 job：默认 log-only（sender=None），需要"已送达"时显式注入 sender。"""
    receipts = receipts if receipts is not None else FakeReceiptRepo()
    job = WatchSlaJob(todo_repo, ReceiptService(receipts, sender=sender), limit=limit)
    return job, receipts


def overdue(id_=1, flow='L1', **over):
    """造一条已到期未收敛待办"""
    kwargs = dict(id=id_, symbol='600150', level='P2', flow_state=flow, due_at=DUE_PAST)
    kwargs.update(over)
    return FakeTodo(**kwargs)


# ── 端口 / 签名防漂移 ────────────────────────────────────────

def test_port_method_set_is_stable():
    """端口方法集固定为 interfaces/data-model 约定的 3 个（增删/改名必须显式面对本测试）"""
    assert IWatchReceiptRepository.__abstractmethods__ == frozenset(
        {'record', 'list_by_todo', 'exists'})
    assert RECEIPT_KINDS == ('escalate', 'result', 'timeout', 'suppressed')


def _param_names(func):
    return list(inspect.signature(func).parameters)


def test_adapter_and_fake_signatures_match_port():
    """适配器与 fake 的参数名必须与端口逐一相同

    本仓适配器是结构化实现（不显式继承端口 ABC），签名漂移（端口加参数忘改实现）
    是静默 TypeError 的温床，必须在这里红。
    """
    for name in IWatchReceiptRepository.__abstractmethods__:
        expected = _param_names(getattr(IWatchReceiptRepository, name))
        assert _param_names(getattr(WatchReceiptRepository, name)) == expected, f'适配器签名 {name}'
        assert _param_names(getattr(FakeReceiptRepo, name)) == expected, f'fake 签名 {name}'


# ── 适配器写库前校验（不碰 DB）──────────────────────────────

def test_adapter_rejects_empty_digest_without_touching_db():
    """空 digest 让幂等失效：必须在触碰 session 之前响亮拒绝"""
    with pytest.raises(ValueError):
        WatchReceiptRepository().record(1, 'escalate', payload_digest='')
    with pytest.raises(ValueError):
        WatchReceiptRepository().exists(1, 'escalate', '')


def test_adapter_rejects_unknown_kind_and_overlong_digest():
    repo = WatchReceiptRepository()
    with pytest.raises(ValueError):
        repo.record(1, 'nope', payload_digest='x' * 8)
    with pytest.raises(ValueError):
        repo.record(1, 'escalate', payload_digest='x' * 65)


# ── 纯函数 ──────────────────────────────────────────────────

def test_payload_digest_is_stable_and_period_sensitive():
    a = payload_digest('escalate', 7, 'L2|2026-09-18T10:00:00')
    assert a == payload_digest('escalate', 7, 'L2|2026-09-18T10:00:00')  # 确定性
    assert a != payload_digest('escalate', 7, 'L3|2026-09-18T10:00:00')  # 段不同
    assert a != payload_digest('timeout', 7, 'L2|2026-09-18T10:00:00')   # 类型不同
    assert a != payload_digest('escalate', 8, 'L2|2026-09-18T10:00:00')  # 待办不同


def test_resolve_channel_by_level_and_kind():
    assert resolve_channel('P0', 'escalate') == CHANNEL_ALERTS
    assert resolve_channel('P1', 'escalate') == CHANNEL_REPORTS
    assert resolve_channel('P3', 'result') == CHANNEL_REPORTS
    assert resolve_channel('P2', 'timeout') == CHANNEL_ALERTS   # 超时=升级给你本人


# ── 机械晋升：L1→L2 / L2→L3 ─────────────────────────────────

def test_l1_promoted_to_l2_and_writes_escalate_receipt():
    todo = overdue(1, flow='L1')
    repo = FakeTodoRepo([todo])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    stats = job.run_once(NOW)

    assert repo.rows[1].flow_state == 'L2'
    assert repo.rows[1].escalate_count == 1
    assert (stats['scanned'], stats['promoted'], stats['escalated']) == (1, 1, 1)
    assert [r['kind'] for r in receipts.rows] == ['escalate']
    assert receipts.rows[0]['delivery_status'] == DELIVERY_SENT
    assert len(sent) == 1 and stats['alerts'] == 1
    assert '升级即' in sent[0]['message']


def test_l2_promoted_to_l3_with_distinct_digest():
    repo = FakeTodoRepo([overdue(2, flow='L2')])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    stats = job.run_once(NOW)

    assert repo.rows[2].flow_state == 'L3'
    assert (stats['promoted'], stats['escalated']) == (1, 1)
    l2_digest = payload_digest('escalate', 2, 'L2|' + DUE_PAST.isoformat())
    l3_digest = payload_digest('escalate', 2, 'L3|' + DUE_PAST.isoformat())
    assert receipts.rows[0]['payload_digest'] == l3_digest != l2_digest


def test_chain_advances_one_step_per_round():
    """机械保证：同一待办连续三轮 → L1→L2→L3→超时升级，不存在滞留"""
    repo = FakeTodoRepo([overdue(3, flow='L1')])
    seen = []
    job, receipts = build_job(repo, sender=seen.append)

    first = job.run_once(NOW)
    second = job.run_once(NOW)
    third = job.run_once(NOW)

    assert repo.rows[3].flow_state == 'L3'
    assert [(s['promoted'], s['escalated'], s['timeout']) for s in (first, second, third)] == [
        (1, 1, 0), (1, 1, 0), (0, 0, 1)]
    assert [r['kind'] for r in receipts.rows] == ['escalate', 'escalate', 'timeout']
    assert repo.rows[3].escalate_count == 3   # 两次晋升 + 一次超时升级


# ── L3 超时升级给用户 ───────────────────────────────────────

def test_l3_overdue_writes_timeout_and_bumps_escalate_count():
    todo = overdue(4, flow='L3', level='P1', escalate_count=2)
    repo = FakeTodoRepo([todo])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    stats = job.run_once(NOW)

    assert (stats['promoted'], stats['timeout'], stats['escalated']) == (0, 1, 0)
    assert repo.rows[4].flow_state == 'L3'          # 不改变终态/流转态
    assert repo.rows[4].escalate_count == 3         # upgrade 计数 +1
    assert receipts.rows[0]['kind'] == 'timeout'
    assert receipts.rows[0]['channel'] == CHANNEL_ALERTS
    assert stats['alerts'] == 1 and '超时' in sent[0]['message']


def test_l3_timeout_is_idempotent_within_same_due_period():
    """同一待办同一 due 周期：第二轮不重发、不重复累加 escalate_count"""
    repo = FakeTodoRepo([overdue(5, flow='L3')])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    first = job.run_once(NOW)
    second = job.run_once(NOW)

    assert (first['timeout'], first['alerts']) == (1, 1)
    assert (second['timeout'], second['alerts']) == (0, 0)
    assert second['duplicates'] == 1
    assert len(receipts.rows) == 1 and len(sent) == 1
    assert repo.rows[5].escalate_count == 1


def test_escalate_receipt_idempotent_when_already_recorded():
    """升级即回执已存在（例如上一轮落库后进程被杀重跑）→ 晋升照做，回执不重发"""
    todo = overdue(6, flow='L1')
    repo = FakeTodoRepo([todo])
    sent = []
    receipts = FakeReceiptRepo()
    service = ReceiptService(receipts, sender=sent.append)
    service.escalate(todo, to_state='L2')            # 预置同 digest 回执
    assert len(sent) == 1
    job = WatchSlaJob(repo, service)

    stats = job.run_once(NOW)

    assert repo.rows[6].flow_state == 'L2'           # 晋升仍然发生（机械保证）
    assert stats['promoted'] == 1
    assert stats['escalated'] == 0 and stats['duplicates'] == 1
    assert len(sent) == 1 and len(receipts.rows) == 1


# ── 健壮性：异常与降级 ──────────────────────────────────────

def test_single_item_failure_does_not_stop_round():
    repo = FakeTodoRepo([overdue(7, flow='L1'), overdue(8, flow='L1')])
    repo.promote_boom_ids = {7}
    job, receipts = build_job(repo)

    stats = job.run_once(NOW)

    assert stats['errors'] == 1
    assert stats['promoted'] == 1
    assert repo.rows[8].flow_state == 'L2'           # 后一条照常处理
    assert [r['todo_id'] for r in receipts.rows] == [8]


def test_repo_scan_failure_returns_degraded_without_raising():
    repo = FakeTodoRepo([overdue(9, flow='L1')])
    repo.list_boom = True
    job, receipts = build_job(repo)

    stats = job.run_once(NOW)

    assert stats['degraded'] is True
    assert 'db down' in stats['degraded_reason']
    assert stats['scanned'] == 0 and stats['promoted'] == 0
    assert receipts.rows == []                        # 不假装处理过


def test_receipt_repo_failure_is_counted_not_crashing():
    """回执仓储抛错：单条计入 errors，整轮继续（且不得谎报已发）"""
    repo = FakeTodoRepo([overdue(10, flow='L1'), overdue(11, flow='L1')])
    receipts = FakeReceiptRepo()
    receipts.exists_boom = True
    job, _ = build_job(repo, receipts=receipts)

    stats = job.run_once(NOW)

    assert stats['errors'] == 2                       # 两条都在发回执时失败
    assert stats['promoted'] == 2                     # 晋升已发生（状态推进不受回执影响）
    assert stats['escalated'] == 0


def test_sender_failure_records_failed_and_does_not_crash():
    repo = FakeTodoRepo([overdue(12, flow='L1')])

    def boom(_payload):
        raise RuntimeError('feishu down')

    job, receipts = build_job(repo, sender=boom)

    stats = job.run_once(NOW)

    assert stats['escalated'] == 1 and stats['alerts'] == 0
    assert receipts.rows[0]['delivery_status'] == DELIVERY_FAILED
    assert repo.rows[12].flow_state == 'L2'


def test_default_sender_is_log_only_and_never_claims_sent():
    repo = FakeTodoRepo([overdue(13, flow='L3')])
    job, receipts = build_job(repo, sender=None)      # 缺省 log-only（t12 才接线）

    stats = job.run_once(NOW)

    assert stats['timeout'] == 1
    assert stats['alerts'] == 0                       # 未送达就不许计成功
    assert receipts.rows[0]['delivery_status'] == DELIVERY_LOG_ONLY


def test_promote_returning_none_is_skipped_without_receipt():
    """并发抢先/已收敛 → 仓储 promote 返回 None：不改状态、不发回执、如实 skipped"""
    repo = FakeTodoRepo([overdue(14, flow='L1')])
    repo.promote_none_ids = {14}
    job, receipts = build_job(repo)

    stats = job.run_once(NOW)

    assert stats['skipped'] == 1
    assert (stats['promoted'], stats['escalated']) == (0, 0)
    assert receipts.rows == []


def test_unknown_flow_state_is_skipped_not_guessed():
    repo = FakeTodoRepo([overdue(15, flow='L9')])
    job, receipts = build_job(repo)

    stats = job.run_once(NOW)

    assert stats['skipped'] == 1 and stats['promoted'] == 0
    assert repo.rows[15].flow_state == 'L9'           # 不臆造晋升
    assert receipts.rows == []


# ── 计数与参数传递 ──────────────────────────────────────────

def test_counts_aggregate_multiple_todos():
    repo = FakeTodoRepo([overdue(16, flow='L1'), overdue(17, flow='L2'),
                         overdue(18, flow='L3')])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    stats = job.run_once(NOW)

    assert stats['scanned'] == 3
    assert stats['promoted'] == 2        # L1→L2、L2→L3
    assert stats['escalated'] == 2
    assert stats['timeout'] == 1         # L3 升级给用户
    assert stats['alerts'] == 3
    assert len(sent) == 3


def test_job_passes_now_and_limit_to_repo():
    repo = FakeTodoRepo([overdue(19, flow='L1')])
    job, _ = build_job(repo, limit=7)

    job.run_once(NOW)

    assert repo.list_calls == [{'now': NOW, 'limit': 7}]


def test_terminal_todo_is_not_processed():
    """已收敛待办不在巡检口径内（仓储只回未终态），即便误传也不得动它"""
    todo = overdue(20, flow='L3', terminal='handled')
    repo = FakeTodoRepo([todo])
    job, receipts = build_job(repo)

    stats = job.run_once(NOW)

    assert stats['scanned'] == 0 and receipts.rows == []
    assert repo.rows[20].terminal == 'handled'


# ── 处置后回执（result 段）──────────────────────────────────

def test_result_receipt_records_once_and_is_idempotent():
    todo = overdue(21, flow='L3')
    receipts = FakeReceiptRepo()
    sent = []
    service = ReceiptService(receipts, sender=sent.append)

    first = service.result(todo, terminal='handled')
    second = service.result(todo, terminal='handled')

    assert first['issued'] is True and first['sent'] is True
    assert second['issued'] is False and second['duplicate'] is True
    assert [r['kind'] for r in receipts.rows] == ['result']
    assert len(sent) == 1


def test_result_and_timeout_have_distinct_digests():
    todo = overdue(22, flow='L3')
    receipts = FakeReceiptRepo()
    service = ReceiptService(receipts)

    service.timeout(todo)
    service.result(todo, terminal='handled')

    assert len({r['payload_digest'] for r in receipts.rows}) == 2

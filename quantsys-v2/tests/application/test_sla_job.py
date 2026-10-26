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
from qs_watch.application.services.watch_engine.receipt_service import (
    CHANNEL_ALERTS,
    CHANNEL_REPORTS,
    DELIVERY_FAILED,
    DELIVERY_LOG_ONLY,
    DELIVERY_SENT,
    ReceiptService,
    payload_digest,
    resolve_channel,
)
from qs_watch.domain.watch.ports import IWatchReceiptRepository, RECEIPT_KINDS

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
    created_at: datetime = None
    claimed_at: datetime = None
    closed_at: datetime = None
    #: 归属（route_owner 的结果）：缺省 None = 走用户路径（与改前的所有断言一致）
    owner_kind: str = None
    owner_ref: str = None
    #: 动作类型（FR-6 执行期限判定用：P0 + trade = 执行类待办）
    action_kind: str = None


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

    def promote(self, todo_id, to_state, *, escalate_count=None, now=None,
                extend_due_minutes=30):
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
        # 对齐适配器契约：晋升顺延 due_at（REQ-261016155500-4f2a 防收盘三连升）
        if extend_due_minutes and todo.due_at is not None:
            todo.due_at = todo.due_at + timedelta(minutes=extend_due_minutes)
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


def build_job(todo_repo, receipts=None, sender=None, limit=100, agent_waker=None):
    """组装巡检 job：默认 log-only（sender=None），需要"已送达"时显式注入 sender。

    agent_waker：agent 自有待办的升级通道（2026-10-16）。缺省 None = 超时一律走卡片
    （与改前一致），要验证"催 agent 而不是用户"的用例显式注入。
    """
    receipts = receipts if receipts is not None else FakeReceiptRepo()
    job = WatchSlaJob(todo_repo,
                      ReceiptService(receipts, sender=sender, agent_waker=agent_waker),
                      limit=limit)
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

def test_l1_promoted_to_l2_without_receipt():
    """REQ-261016155500-4f2a 回执收敛：晋升不发卡（升级回执下线），历史在
    flow_state/escalate_count 与结果回执时间线。"""
    todo = overdue(1, flow='L1')
    repo = FakeTodoRepo([todo])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    stats = job.run_once(NOW)

    assert repo.rows[1].flow_state == 'L2'
    assert repo.rows[1].escalate_count == 1
    assert (stats['scanned'], stats['promoted'], stats['escalated']) == (1, 1, 0)
    assert receipts.rows == [] and sent == [] and stats['alerts'] == 0


def test_l2_promoted_to_l3_without_receipt():
    repo = FakeTodoRepo([overdue(2, flow='L2')])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    stats = job.run_once(NOW)

    assert repo.rows[2].flow_state == 'L3'
    assert (stats['promoted'], stats['escalated']) == (1, 0)
    assert receipts.rows == [] and sent == []


def test_promotion_extends_due_30min_to_prevent_close_cascade():
    """REQ-261016155500-4f2a：晋升顺延 due_at 30min——P2 收盘不再三连升。"""
    repo = FakeTodoRepo([overdue(23, flow='L1')])
    job, _ = build_job(repo)

    job.run_once(NOW)

    assert repo.rows[23].due_at == DUE_PAST + timedelta(minutes=30)


def test_chain_advances_one_step_per_round():
    """机械保证：同一待办逐轮推进 → L1→L2→L3→超时；每步 due 顺延 30min，
    故每轮时钟需推进 31min 才会命中下一轮（这正是防收盘三连升的语义）。"""
    repo = FakeTodoRepo([overdue(3, flow='L1')])
    seen = []
    job, receipts = build_job(repo, sender=seen.append)

    first = job.run_once(NOW)
    second = job.run_once(NOW + timedelta(minutes=31))
    third = job.run_once(NOW + timedelta(minutes=62))

    assert repo.rows[3].flow_state == 'L3'
    assert [(s['promoted'], s['escalated'], s['timeout']) for s in (first, second, third)] == [
        (1, 0, 0), (1, 0, 0), (0, 0, 1)]
    # 升级回执下线：只有 timeout 一条台账（P2 默认级别 → 只落台账不发送）
    assert [r['kind'] for r in receipts.rows] == ['timeout']
    assert receipts.rows[0]['delivery_status'] == DELIVERY_LOG_ONLY
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
    # REQ-ad0a t7：落库标签 = 真实投递路由（timeout → risk_stop 盯盘频道），
    # 不再是 FR-1 分群前与 alerts 群挂钩的旧标签
    assert receipts.rows[0]['channel'] == 'risk_stop'
    assert stats['alerts'] == 1 and '超时' in sent[0]['message']


def test_l3_timeout_is_idempotent_within_same_due_period():
    """P1 超时：只发一次；第二轮仍命中 overdue 但幂等跳过（duplicates=1，不重发不重复计数）

    2026-10-16 修正：超时 bump **不再顺延 due_at**（见下一条回归），所以第二轮**会**
    命中并走到 exists 分支——这正是"同一 due 周期只发一次"的实现方式；此前的断言
    ("第二轮不再命中") 恰好把缺陷当成了契约。
    """
    repo = FakeTodoRepo([overdue(5, flow='L3', level='P1')])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    first = job.run_once(NOW)
    second = job.run_once(NOW)

    assert (first['timeout'], first['alerts']) == (1, 1)
    assert (second['timeout'], second['alerts']) == (0, 0)
    assert second['duplicates'] == 1                # 命中但已存在 → 整段跳过
    assert len(receipts.rows) == 1 and len(sent) == 1
    assert repo.rows[5].escalate_count == 1


def test_l3_timeout_does_not_rotate_due_at_no_repeat_every_30min():
    """① 回归（2026-10-16 生产缺陷）：超时 bump **不得**顺延 due_at。

    病根：due_at 是回执幂等键（payload_digest 的 period）的一部分，而 bump 复用了
    promote()，其缺省会 due_at +30min → 每 30 分钟换一个新 digest → 同一待办无限复读
    （实测 13 条 P1 待办 3 小时刷 78 条卡）。本用例把时钟推到 +31min：
    若有人把 extend_due_minutes 改回缺省（或删掉显式 0），这张卡就会再发一次 → 红。
    """
    repo = FakeTodoRepo([overdue(41, flow='L3', level='P1')])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    first = job.run_once(NOW)
    later = job.run_once(NOW + timedelta(minutes=31))

    assert first['timeout'] == 1
    assert later['timeout'] == 0 and later['duplicates'] == 1
    assert repo.rows[41].due_at == DUE_PAST          # due_at 原地不动（幂等键稳定）
    assert len(receipts.rows) == 1 and len(sent) == 1
    assert repo.rows[41].escalate_count == 1         # 幂等跳过时不再累加计数


def test_l3_timeout_of_agent_owned_todo_wakes_owner_not_user():
    """② agent 自有待办的超时升级 → 唤醒 owner agent，不占用户卡片（2026-10-16）"""
    todo = overdue(42, flow='L3', level='P1', owner_kind='agent', owner_ref='agent-dh')
    repo = FakeTodoRepo([todo])
    sent, wakes = [], []
    job, receipts = build_job(repo, sender=sent.append,
                              agent_waker=lambda t, ctx: wakes.append((t.id, ctx)) or True)

    stats = job.run_once(NOW)

    assert [w[0] for w in wakes] == [42]              # 唤醒 owner
    assert wakes[0][1]['kind'] == 'timeout'
    assert sent == []                                 # 用户一张卡都不发
    assert stats['timeout'] == 1 and stats['agent_wakes'] == 1
    assert stats['alerts'] == 1 and stats['timeout_suppressed'] == 0
    assert receipts.rows[0]['delivery_status'] == DELIVERY_SENT
    assert repo.rows[42].escalate_count == 1


def test_l3_timeout_agent_owned_p2_wakes_owner_without_user_card():
    """agent 自有 P2 超时：照常催 owner（私信），但不发用户卡（级别门只管用户路径）"""
    todo = overdue(43, flow='L3', level='P2', owner_kind='agent', owner_ref='agent-dh')
    repo = FakeTodoRepo([todo])
    sent, wakes = [], []
    job, receipts = build_job(repo, sender=sent.append,
                              agent_waker=lambda t, ctx: wakes.append(t.id) or True)

    stats = job.run_once(NOW)

    assert wakes == [43] and sent == []
    assert stats['agent_wakes'] == 1 and stats['timeout_suppressed'] == 0
    assert receipts.rows[0]['delivery_status'] == DELIVERY_SENT


def test_l3_timeout_agent_wake_failure_is_folded_into_one_card():
    """唤醒 owner 失败：P1 折进本轮**同一张**卡（绝不静默丢，也不按条炸卡）"""
    todo = overdue(44, flow='L3', level='P1', owner_kind='agent', owner_ref='agent-dh')
    repo = FakeTodoRepo([todo])
    sent = []

    def _boom(t, ctx):
        raise RuntimeError('wake down')

    job, receipts = build_job(repo, sender=sent.append, agent_waker=_boom)
    stats = job.run_once(NOW)

    assert stats['timeout'] == 1 and stats['agent_wakes'] == 1
    assert stats['group_cards'] == 1 and len(sent) == 1      # 一张卡，不是每个待办一张
    assert '待办#44' in sent[0]['message']
    assert receipts.rows[0]['delivery_status'] == DELIVERY_SENT


def test_l3_timeout_many_agent_owned_failures_still_one_card():
    """炸卡回归（2026-10-16 生产实测一轮 10 张）：N 条唤醒失败 → 仍只有 1 张卡"""
    todos = [overdue(50 + i, flow='L3', level='P1', owner_kind='agent',
                     owner_ref='agent-dh') for i in range(10)]
    repo = FakeTodoRepo(todos)
    sent = []
    job, receipts = build_job(repo, sender=sent.append,
                              agent_waker=lambda t, ctx: False)   # 全部未送达

    stats = job.run_once(NOW)

    assert stats['timeout'] == 10 and stats['group_cards'] == 1
    assert len(sent) == 1
    assert sent[0]['message'].count('- 待办#') == 10          # 10 行折进同一张卡
    assert len(receipts.rows) == 10


def test_l3_timeout_agent_owned_without_waker_falls_back_to_card():
    """未接线 agent_waker（缺省）：P0/P1 仍退回用户卡（行为与改前一致，绝不静默丢）"""
    todo = overdue(45, flow='L3', level='P1', owner_kind='agent', owner_ref='agent-dh')
    repo = FakeTodoRepo([todo])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)     # agent_waker=None

    stats = job.run_once(NOW)

    assert stats['timeout'] == 1 and stats['agent_wakes'] == 1
    assert stats['alerts'] == 1 and len(sent) == 1
    assert receipts.rows[0]['delivery_status'] == DELIVERY_SENT


def test_l3_p2_timeout_suppressed_ledger_only():
    """REQ-261016155500-4f2a：P2 超时不发卡——只落台账（log_only），日终汇总点名"""
    repo = FakeTodoRepo([overdue(24, flow='L3', level='P2')])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    stats = job.run_once(NOW)

    assert stats['timeout'] == 1 and stats['timeout_suppressed'] == 1
    assert stats['alerts'] == 0 and sent == []
    assert len(receipts.rows) == 1
    assert receipts.rows[0]['kind'] == 'timeout'
    assert receipts.rows[0]['delivery_status'] == DELIVERY_LOG_ONLY
    assert repo.rows[24].escalate_count == 1


def test_l3_p0_timeout_still_delivers():
    """P0 超时仍发送（收敛只压 P2/P3）"""
    repo = FakeTodoRepo([overdue(25, flow='L3', level='P0')])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    stats = job.run_once(NOW)

    assert stats['timeout'] == 1 and stats['timeout_suppressed'] == 0
    assert stats['alerts'] == 1 and len(sent) == 1
    assert receipts.rows[0]['delivery_status'] == DELIVERY_SENT


def test_promotion_never_writes_escalate_receipt():
    """升级回执下线后，重复巡检/预置 digest 场景不再存在 escalate 回执；
    晋升是纯状态推进，任何情况下不为它落回执。"""
    todo = overdue(6, flow='L1')
    repo = FakeTodoRepo([todo])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    stats = job.run_once(NOW)

    assert repo.rows[6].flow_state == 'L2'           # 晋升仍然发生（机械保证）
    assert stats['promoted'] == 1
    assert stats['escalated'] == 0 and stats['duplicates'] == 0
    assert len(sent) == 0 and len(receipts.rows) == 0


# ── 健壮性：异常与降级 ──────────────────────────────────────

def test_single_item_failure_does_not_stop_round():
    repo = FakeTodoRepo([overdue(7, flow='L1'), overdue(8, flow='L1')])
    repo.promote_boom_ids = {7}
    job, receipts = build_job(repo)

    stats = job.run_once(NOW)

    assert stats['errors'] == 1
    assert stats['promoted'] == 1
    assert repo.rows[8].flow_state == 'L2'           # 后一条照常处理
    assert receipts.rows == []                       # 晋升不发卡


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
    """回执仓储抛错只在真正发回执时（L3 超时）发生；晋升不再触回执仓储。

    本用例：L1 待办晋升，回执仓储坏了也不影响——不报错、不回执、状态照推进。"""
    repo = FakeTodoRepo([overdue(10, flow='L1'), overdue(11, flow='L1')])
    receipts = FakeReceiptRepo()
    receipts.exists_boom = True
    job, _ = build_job(repo, receipts=receipts)

    stats = job.run_once(NOW)

    assert stats['errors'] == 0                       # 晋升路径不触回执仓储
    assert stats['promoted'] == 2
    assert receipts.record_calls == []


def test_sender_failure_records_failed_and_does_not_crash():
    repo = FakeTodoRepo([overdue(12, flow='L3', level='P1')])

    def boom(_payload):
        raise RuntimeError('feishu down')

    job, receipts = build_job(repo, sender=boom)

    stats = job.run_once(NOW)

    assert stats['timeout'] == 1 and stats['alerts'] == 0
    assert stats['timeout_suppressed'] == 0
    assert receipts.rows[0]['delivery_status'] == DELIVERY_FAILED
    assert repo.rows[12].flow_state == 'L3'


def test_default_sender_is_log_only_and_never_claims_sent():
    repo = FakeTodoRepo([overdue(13, flow='L3', level='P1')])
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
                         overdue(18, flow='L3', level='P1')])
    sent = []
    job, receipts = build_job(repo, sender=sent.append)

    stats = job.run_once(NOW)

    assert stats['scanned'] == 3
    assert stats['promoted'] == 2        # L1→L2、L2→L3（不发卡）
    assert stats['escalated'] == 0
    assert stats['timeout'] == 1         # L3/P1 升级给用户
    assert stats['alerts'] == 1
    # REQ-261016155500-4f2a：只有 timeout 一张聚合卡（升级回执已下线）
    assert len(sent) == 1 and sent[0]['kind'] == 'timeout'
    assert stats['group_cards'] == 1


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

    # 2026-10-26 即时投递：close 同一调用内发送；重复 result 只走幂等短路
    assert first['issued'] is True
    assert first['sent'] is True
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


def test_result_receipt_carries_full_timeline():
    """REQ-261016155500-4f2a：结果回执附全过程时间线（升级回执下线后晋升历史只在结果卡可见）"""
    todo = overdue(26, flow='L3', escalate_count=2)
    todo.created_at = NOW - timedelta(hours=3)
    todo.claimed_at = NOW - timedelta(hours=2)
    todo.closed_at = NOW - timedelta(minutes=5)
    receipts = FakeReceiptRepo()
    sent = []
    service = ReceiptService(receipts, sender=sent.append)

    service.result(todo, terminal='handled', close_reason='已按预案减仓',
                   action_kind='trade')

    message = sent[0]['message']
    assert '时间线：' in message
    assert '创建' in message and '认领' in message and '关闭' in message
    assert '晋升 2 次' in message


# ── 执行期限（REQ-261021194640-69b8 FR-6）────────────────────

class TestExecDeadline:
    """P0 执行待办按「创建 + WATCH_EXEC_SLA_MIN」判超时，不按提醒 due_at 判。"""

    def _exec_todo(self, created_at, **over):
        return overdue(1, flow='L3', level='P0', action_kind='trade',
                       created_at=created_at, **over)

    def test_before_deadline_no_receipt(self):
        todo = self._exec_todo(NOW - timedelta(minutes=29))
        job, receipts = build_job(FakeTodoRepo([todo]))
        stats = job.run_once(now=NOW)
        assert stats['exec_waiting'] == 1
        assert stats['timeout'] == 0
        assert receipts.rows == []

    def test_after_deadline_one_receipt(self):
        todo = self._exec_todo(NOW - timedelta(minutes=31))
        job, receipts = build_job(FakeTodoRepo([todo]))
        stats = job.run_once(now=NOW)
        assert stats['timeout'] == 1
        assert [r['kind'] for r in receipts.rows] == ['timeout']

    def test_repeated_tick_stays_one_receipt(self):
        todo = self._exec_todo(NOW - timedelta(minutes=31))
        job, receipts = build_job(FakeTodoRepo([todo]))
        first = job.run_once(now=NOW)
        second = job.run_once(now=NOW)
        assert first['timeout'] == 1 and second['timeout'] == 0
        assert len([r for r in receipts.rows if r['kind'] == 'timeout']) == 1

    @pytest.mark.parametrize('created_at', [
        NOW - timedelta(minutes=31),                        # 带时区
        (NOW - timedelta(minutes=31)).replace(tzinfo=None),  # 裸时间
        NOW - timedelta(days=1),                             # 跨日
    ])
    def test_timezone_matrix(self, created_at):
        todo = self._exec_todo(created_at)
        job, _receipts = build_job(FakeTodoRepo([todo]))
        stats = job.run_once(now=NOW)
        assert stats['errors'] == 0
        assert stats['timeout'] == 1

    def test_not_written_expired_at_deadline(self):
        todo = self._exec_todo(NOW - timedelta(minutes=31))
        job, _receipts = build_job(FakeTodoRepo([todo]))
        job.run_once(now=NOW)
        assert todo.terminal is None, '执行期限到只催办，绝不写 expired'

    def test_non_exec_todo_timeout_unchanged(self):
        todo = overdue(2, flow='L3', level='P0')  # action_kind=None：非执行类
        job, _receipts = build_job(FakeTodoRepo([todo]))
        stats = job.run_once(now=NOW)
        assert stats['timeout'] == 1
        assert stats['exec_waiting'] == 0

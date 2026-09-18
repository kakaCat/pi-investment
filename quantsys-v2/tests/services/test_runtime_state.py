"""盯盘运行态持久化与启动恢复单测（REQ-c9f899 t3，2026-09-18）

为什么加：闩锁/冷却基准原先只存进程内存，重启即丢——实测单日触发 23 次 >
1800s 冷却理论上限 16 次，冷却形同虚设（需求 R10）。本文件守住四件事：

  1) 恢复：库里的 latched / last_triggered_at 能灌回内存，重启后冷却仍生效；
  2) 写失败：store 抛异常时 flush 返回 False + degraded=True，**绝不抛错**（tick 不许崩）；
  3) 节流：无脏键时 flush 不调用 store（0 次 I/O），只写真正变化的键；
  4) 默认关闭：不注入 store 且 WATCH_RUNTIME_PERSIST_ENABLED 未设时，行为与改造前一致。

这些用例会红：把 store 参数/恢复逻辑/flush 摘掉、或让它吞掉写失败返回 True 时全部失败。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from application.services.watch_engine.engine import (
    RUNTIME_PERSIST_ENV, WatchEngine, _runtime_persist_enabled,
)
from application.services.watch_engine.state_manager import StateManager
from application.services.watch_engine.trigger_judge import TriggerJudge

# 状态层测试用（naive，与引擎 datetime.now 口径一致）
NOW = datetime(2026, 9, 18, 10, 0, 0)
COOLDOWN_1800 = {'cooldown_sec': 1800}

# 引擎整链路测试用（2026-07-21 周二，交易时段内，与 test_watch_engine.py 同口径）
ENGINE_NOW = datetime(2026, 7, 21, 10, 30)


class FakeRuntimeStore:
    """内存版 IWatchRuntimeStateStore；可注入读/写失败与调用计数"""

    def __init__(self, rows=None, fail_load=False, fail_upsert=False):
        self.rows = [dict(r) for r in (rows or [])]
        self.fail_load = fail_load
        self.fail_upsert = fail_upsert
        self.upsert_calls = []          # 每次 upsert_many 的深拷贝入参
        self.meta = {}

    def load_all(self):
        if self.fail_load:
            raise RuntimeError('load boom')
        return [dict(r) for r in self.rows]

    def upsert_many(self, rows):
        if self.fail_upsert:
            raise RuntimeError('write boom')
        self.upsert_calls.append([dict(r) for r in rows])

    def load_meta(self):
        return dict(self.meta)

    def save_meta(self, **fields):
        self.meta.update(fields)


def _row(rule_id=1, cond_idx=0, latched=False, last=None, cooldown_effective=None):
    return {'rule_id': rule_id, 'cond_idx': cond_idx, 'latched': latched,
            'last_triggered_at': last, 'cooldown_effective_sec': cooldown_effective}


# ══════════════ 1) 启动恢复 ══════════════

class TestRestore:
    def test_restored_latch_suppresses_repeat(self):
        """重启后闩锁仍在：条件持续成立时不重复推送"""
        store = FakeRuntimeStore([_row(latched=True, last=NOW)])
        s = StateManager(store=store)
        assert s.restore_from_store() == 1
        j = TriggerJudge(s)
        # 已过冷却期，但闩锁未回落 → 不推送
        assert j.should_emit(1, 0, True, COOLDOWN_1800,
                             NOW + timedelta(seconds=3600)) is False

    def test_restored_cooldown_still_applies_after_restart(self):
        """核心用例（R10）：冷却是真的——重启后同一规则仍受冷却约束。

        未恢复时（等价改造前）冷却基准为 0，同条件会立刻再推一次 → 断言 False 的
        这一行就是"单日 23 次 > 理论上限 16 次"的病根回归。
        """
        store = FakeRuntimeStore([_row(latched=False, last=NOW)])
        j0 = TriggerJudge(StateManager(store=store))
        assert j0.should_emit(1, 0, True, COOLDOWN_1800,
                              NOW + timedelta(seconds=600)) is True   # 未恢复：冷却丢了

        s = StateManager(store=store)
        assert s.restore_from_store() == 1
        j = TriggerJudge(s)
        assert j.should_emit(1, 0, True, COOLDOWN_1800,
                             NOW + timedelta(seconds=600)) is False  # 恢复后：冷却生效
        assert j.in_cooldown(1, 0, COOLDOWN_1800, NOW + timedelta(seconds=1799)) is True
        assert j.in_cooldown(1, 0, COOLDOWN_1800, NOW + timedelta(seconds=1801)) is False

    def test_restore_normalizes_tz_aware_to_engine_clock(self):
        """库列是 TIMESTAMPTZ（读出来 aware），引擎时钟 naive——混用会抛 TypeError。

        这里用"本机本地时区的 aware 时刻"，保证断言与运行环境时区无关。
        """
        aware = datetime.now().astimezone()
        naive_equiv = aware.replace(tzinfo=None)
        store = FakeRuntimeStore([_row(latched=False, last=aware)])
        s = StateManager(store=store)
        s.restore_from_store()

        assert s.last_triggered[(1, 0)].tzinfo is None
        assert s.last_triggered[(1, 0)] == naive_equiv
        # 关键：不抛 TypeError，且冷却判定正确
        assert TriggerJudge(s).in_cooldown(
            1, 0, COOLDOWN_1800, naive_equiv + timedelta(seconds=60)) is True
        assert TriggerJudge(s).in_cooldown(
            1, 0, COOLDOWN_1800, naive_equiv + timedelta(seconds=1801)) is False

    def test_restore_keeps_cooldown_effective_for_passthrough(self):
        """自愈延长后的有效冷却必须原样接住（判定不消费，但 flush 不能把它冲成 NULL）"""
        store = FakeRuntimeStore([_row(latched=True, last=NOW, cooldown_effective=900)])
        s = StateManager(store=store)
        s.restore_from_store()
        assert s.cooldown_effective[(1, 0)] == 900
        s.mark_dirty((1, 0))
        assert s.flush() is True
        assert store.upsert_calls[-1][0]['cooldown_effective_sec'] == 900

    def test_restore_without_store_is_noop(self):
        s = StateManager()
        assert s.restore_from_store() == 0
        assert s.degraded is False

    def test_restore_failure_degrades_but_does_not_raise(self):
        s = StateManager(store=FakeRuntimeStore(fail_load=True))
        assert s.restore_from_store() == 0        # 不抛错
        assert s.degraded is True

    def test_restore_skips_malformed_rows(self):
        store = FakeRuntimeStore([_row(), {'rule_id': 9}])   # 第二行缺 cond_idx
        s = StateManager(store=store)
        assert s.restore_from_store() == 1                  # 只收下合法那行
        assert (1, 0) in s._persisted
        assert (9, 0) not in s._persisted
        assert s.degraded is False


# ══════════════ 2) 脏键 flush 与节流 ══════════════

class TestFlush:
    def test_flush_without_dirty_keys_does_not_call_store(self):
        """节流：无脏键 → store 调用次数 0"""
        store = FakeRuntimeStore([_row(latched=True, last=NOW)])
        s = StateManager(store=store)
        s.restore_from_store()
        assert s.flush() is True
        assert len(store.upsert_calls) == 0
        assert s.flush() is True
        assert len(store.upsert_calls) == 0

    def test_flush_writes_only_dirty_keys(self):
        """只写变化的键：只改 (2,0)，(1,0) 不应出现在本批 upsert 里"""
        store = FakeRuntimeStore([_row(rule_id=1, latched=True, last=NOW)])
        s = StateManager(store=store)
        s.restore_from_store()
        TriggerJudge(s).mark_emitted(2, 0, NOW, '601888.SH')   # 只动 (2,0)

        assert s.flush() is True
        assert len(store.upsert_calls) == 1
        keys = {(r['rule_id'], r['cond_idx']) for r in store.upsert_calls[0]}
        assert keys == {(2, 0)}
        row = store.upsert_calls[0][0]
        assert row['latched'] is True and row['last_triggered_at'] == NOW

    def test_unlatch_is_written_even_when_last_triggered_unchanged(self):
        """闩锁回落的删除也要落库（否则重启后闩锁复活，永不重新武装）"""
        store = FakeRuntimeStore([_row(latched=True, last=NOW)])
        s = StateManager(store=store)
        s.restore_from_store()
        s.latched.discard((1, 0))                 # 条件回落 → 重新武装
        assert s.flush() is True
        assert store.upsert_calls[0][0]['latched'] is False

    def test_flush_without_store_returns_false_and_does_nothing(self):
        s = StateManager()
        s.latched.add((1, 0))
        assert s.flush() is False                 # 未启用持久化
        assert s.degraded is False

    def test_second_flush_is_noop_after_success(self):
        store = FakeRuntimeStore()
        s = StateManager(store=store)
        TriggerJudge(s).mark_emitted(1, 0, NOW, '600519.SH')
        assert s.flush() is True
        assert len(store.upsert_calls) == 1
        assert s.flush() is True
        assert len(store.upsert_calls) == 1       # 无新变化 → 不再写


# ══════════════ 3) 写失败：响亮但不致命 ══════════════

class TestWriteFailure:
    def test_upsert_failure_returns_false_degrades_and_does_not_raise(self):
        store = FakeRuntimeStore(fail_upsert=True)
        s = StateManager(store=store)
        TriggerJudge(s).mark_emitted(1, 0, NOW, '600519.SH')

        assert s.flush() is False                 # 绝不静默当成成功
        assert s.degraded is True
        assert len(store.upsert_calls) == 0

    def test_dirty_key_retained_for_retry_after_failure(self):
        """写失败后脏键不能丢：下次 flush 仍应重试（at-least-once）"""
        store = FakeRuntimeStore(fail_upsert=True)
        s = StateManager(store=store)
        TriggerJudge(s).mark_emitted(1, 0, NOW, '600519.SH')
        assert s.flush() is False

        store.fail_upsert = False
        assert s.flush() is True
        assert len(store.upsert_calls) == 1
        assert s.degraded is False                # 成功后恢复

    def test_engine_tick_survives_store_failure(self):
        """整链路回归：store 写失败时 tick 不抛异常、事件照常产出、状态置 degraded"""
        store = FakeRuntimeStore(fail_upsert=True)
        eng = _engine([_rule()], {'600519.SH': 101.0}, runtime_state_store=store)
        events = eng.tick()                      # 不抛异常即为通过
        assert len(events) == 1
        assert eng.state.degraded is True
        assert store.upsert_calls == []


# ══════════════ 4) 引擎接线与开关 ══════════════

def _rule(rule_id=1, symbol='600519.SH'):
    # 与 tests/services/test_watch_engine.py 同款最小规则；intent=exit_stop 保证
    # 触发能走到"通知"（观察类意图会被处置门压成 auto_observed）
    return SimpleNamespace(
        id=rule_id, symbol=symbol,
        conditions=[{'type': 'price_break',
                     'params': {'direction': 'above', 'price': 100.0}}],
        cost_price=None, active_window=None,
        intent='exit_stop', action_hint={'trigger_level': 'L2', 'action_on_trigger': 'sell'},
        escalation_policy=None,
        scope='symbol', linked_account=None, lifecycle_stage='watching',
        created_from=None, next_action_hint=None, target=None,
        review_interval_days=None, review_due_at=None, enabled=True,
    )


class _Repo:
    def __init__(self, rules):
        self._rules = rules

    def list_enabled(self):
        return list(self._rules)


class _Quotes:
    def __init__(self, prices):
        self.prices = prices

    def get_realtime_quote(self, symbol):
        price = self.prices.get(symbol)
        if price is None:
            return None
        return SimpleNamespace(symbol=symbol, price=price, prev_close=98.0,
                               volume=1_000_000, change_pct=None)


class _Notifier:
    def __init__(self):
        self.notifications = []

    def notify(self, rule, condition, quote, result, **kwargs):
        self.notifications.append((rule.id, quote.price))
        return SimpleNamespace(id=len(self.notifications))


def _engine(rules, prices, **kw):
    return WatchEngine(
        rule_repo=_Repo(rules),
        quote_service=_Quotes(prices),
        notifier=_Notifier(),
        now_fn=lambda: ENGINE_NOW,
        **kw,
    )


class TestEngineWiring:
    def test_disabled_by_default_keeps_memory_only(self, monkeypatch):
        monkeypatch.delenv(RUNTIME_PERSIST_ENV, raising=False)
        eng = _engine([_rule()], {'600519.SH': 101.0})
        assert eng.state.store is None
        assert _runtime_persist_enabled() is False
        assert eng._flush_runtime_state() is False   # no-op，不碰库

    def test_env_switch_enables_adapter(self, monkeypatch):
        monkeypatch.setenv(RUNTIME_PERSIST_ENV, 'true')
        assert _runtime_persist_enabled() is True
        eng = _engine([_rule()], {'600519.SH': 101.0})
        assert eng.state.store is not None
        from adapters.outbound.repositories.watch_runtime_state_repository import (
            WatchRuntimeStateRepository,
        )
        assert isinstance(eng.state.store, WatchRuntimeStateRepository)

    def test_injected_store_is_used_and_restored_once(self):
        store = FakeRuntimeStore([_row(latched=True, last=NOW)])
        eng = _engine([_rule()], {'600519.SH': 101.0}, runtime_state_store=store)
        assert eng.state.store is store
        assert eng._restore_runtime_state() == 1
        assert (1, 0) in eng.state.latched
        assert eng._restore_runtime_state() == 0     # 幂等：只恢复一次

    def test_tick_flushes_trigger_state_to_store(self):
        store = FakeRuntimeStore()
        eng = _engine([_rule()], {'600519.SH': 101.0}, runtime_state_store=store)
        assert len(eng.tick()) == 1
        assert len(store.upsert_calls) == 1
        row = store.upsert_calls[0][0]
        assert (row['rule_id'], row['cond_idx'], row['latched']) == (1, 0, True)

    def test_tick_without_store_does_not_touch_any_store(self, monkeypatch):
        monkeypatch.delenv(RUNTIME_PERSIST_ENV, raising=False)
        eng = _engine([_rule()], {'600519.SH': 101.0})
        assert len(eng.tick()) == 1                 # 触发照常
        assert eng.state.store is None              # 但无持久化路径


# ══════════════ 5) 适配器契约（SQL 只在适配器层，ADR-001）══════════════

def test_repository_exposes_port_surface():
    from adapters.outbound.repositories.watch_runtime_state_repository import (
        WatchRuntimeStateRepository,
    )
    repo = WatchRuntimeStateRepository()
    for name in ('load_all', 'upsert_many', 'load_meta', 'save_meta'):
        assert callable(getattr(repo, name))


def test_repository_rejects_unknown_meta_field():
    """meta 字段名拼错必须响亮失败——静默丢弃会把"心跳已更新"变成假象"""
    from adapters.outbound.repositories.watch_runtime_state_repository import (
        WatchRuntimeStateRepository,
    )
    with pytest.raises(ValueError):
        WatchRuntimeStateRepository().save_meta(bogus_field=1)


def test_repository_roundtrip_on_test_db():
    """真实 ORM 往返（quant_test）：insert → ON CONFLICT update → 单行 meta 部分更新。

    数据库不可用时 skip（不伪造通过）；可用而适配器坏掉时必须红。
    """
    import psycopg2
    from infrastructure.persistence.database.engine import _resolve_db_dsn

    dsn = _resolve_db_dsn()
    if not dsn:
        pytest.skip('no database dsn configured')
    try:
        psycopg2.connect(dsn).close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f'test database unavailable: {e}')

    from infrastructure.persistence.orm import Base, close_session, get_session
    from infrastructure.persistence.orm.models.watch_todo import (
        WatchRuntimeMeta, WatchRuntimeState,
    )
    from adapters.outbound.repositories.watch_runtime_state_repository import (
        WatchRuntimeStateRepository,
    )

    Base.metadata.create_all(get_session().get_bind(),
                             tables=[WatchRuntimeState.__table__,
                                     WatchRuntimeMeta.__table__])
    get_session().commit()

    rid = 990002          # 测试库哨兵 id，远离真实规则
    repo = WatchRuntimeStateRepository()
    try:
        repo.upsert_many([
            {'rule_id': rid, 'cond_idx': 0, 'latched': True,
             'last_triggered_at': datetime(2026, 9, 18, 10, 0),
             'cooldown_effective_sec': None},
            {'rule_id': rid, 'cond_idx': 1, 'latched': False,
             'last_triggered_at': None, 'cooldown_effective_sec': 900},
        ])
        rows = sorted((r for r in repo.load_all() if r['rule_id'] == rid),
                      key=lambda r: r['cond_idx'])
        assert len(rows) == 2
        assert rows[0]['latched'] is True
        assert rows[1]['cooldown_effective_sec'] == 900

        # 冲突键更新（不是插出第三行）
        repo.upsert_many([{'rule_id': rid, 'cond_idx': 0, 'latched': False,
                           'last_triggered_at': datetime(2026, 9, 18, 11, 0),
                           'cooldown_effective_sec': 1800}])
        rows = [r for r in repo.load_all() if r['rule_id'] == rid]
        assert len(rows) == 2
        row0 = next(r for r in rows if r['cond_idx'] == 0)
        assert row0['latched'] is False
        assert row0['cooldown_effective_sec'] == 1800

        # TIMESTAMPTZ 读回是 aware —— StateManager._naive 归一化的前提
        assert row0['last_triggered_at'].tzinfo is not None

        repo.save_meta(heartbeat_at=datetime(2026, 9, 18, 12, 0))
        assert repo.load_meta()['heartbeat_at'] is not None
        repo.save_meta(state_date=datetime(2026, 9, 18).date())
        meta = repo.load_meta()
        assert meta['state_date'] is not None
        assert meta['heartbeat_at'] is not None      # 部分更新不冲掉其它字段
    finally:
        session = get_session()
        session.query(WatchRuntimeState).filter(
            WatchRuntimeState.rule_id == rid).delete()
        session.query(WatchRuntimeMeta).filter(
            WatchRuntimeMeta.id == 1).delete()
        session.commit()
        close_session()

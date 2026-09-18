"""运行态补完单测：去重窗 / 事件窗 / 价格历史 / 迁移幂等（REQ-c9f899 返工 B+C）

为什么加：t3 只持久化了闩锁 + 冷却基准；去重窗、触发事件窗口、velocity 价格历史
仍在进程内存。重启后：
  · 去重窗清零 → 同标的同向在窗内被重复通知；
  · 事件窗口清零 → 频率/共振统计从 0 起算（冷启动）；
  · 价格历史清零 → velocity 命中「窗口内无历史价格（冷启动）」不判定。
本文件守住四件事：

  1) 落库 → 重启（新 StateManager 恢复）→ 行为连续（去重生效 / 频率连续 / velocity 不再冷启动）；
  2) 增量落库：只写变化的去重键、只写新增事件、只写新价格点，并节流；
  3) 三类扩展按窗口裁剪（有界）+ 写失败只降级不致命（degraded + 返回 False + 下轮重试）；
  4) 迁移 additive 且幂等（假 cursor 跑两遍，第二遍 0 变更）。

这些用例会红：把 restore/flush 中某一类扩展摘掉、让写失败静默返回 True、
或去掉迁移的存在性判断时全部失败（已做变异验证，见实现汇报）。
"""
import importlib.util
import re
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from application.services.watch_engine.conditions import EvalContext, evaluate
from application.services.watch_engine.deduplication_manager import DeduplicationManager
from application.services.watch_engine.engine import WatchEngine
from application.services.watch_engine.state_manager import StateManager

# 状态层测试用（naive，与引擎 datetime.now 口径一致）
NOW = datetime(2026, 9, 18, 10, 30, 0)


# ── 测试替身 ────────────────────────────────────────────────

def _cond():
    return {'type': 'price_break', 'params': {'direction': 'above', 'price': 100.0}}


def _velocity_cond():
    return {'type': 'velocity', 'params': {'pct': 5.0, 'window_min': 30}}


def _rule(rule_id=1, symbol='600519.SH'):
    return SimpleNamespace(
        id=rule_id, symbol=symbol,
        conditions=[_cond()], intent='exit_stop',
        action_hint={'trigger_level': 'L2', 'action_on_trigger': 'sell'},
    )


def _quote(price):
    return SimpleNamespace(symbol='600519.SH', price=price)


class FakeCompleteStore:
    """内存版 IWatchRuntimeStateStore（含返工 B+C 的扩展方法）；可注入各类写失败"""

    def __init__(self, runtime=None, dedup=None, events=None, history=None,
                 shadow_since=None, fail=None):
        self.runtime_rows = [dict(r) for r in (runtime or [])]
        self.dedup_rows = {(r['symbol'], r['direction']): dict(r) for r in (dedup or [])}
        self.event_rows = [dict(r) for r in (events or [])]
        self.history_rows = [dict(r) for r in (history or [])]
        self.shadow_since = shadow_since
        self.fail = set(fail or ())
        self.upsert_calls = []
        self.dedup_calls = []
        self.event_calls = []
        self.history_calls = []
        self.prune_calls = []
        self.price_history_args = []
        self.meta = {}

    def _check(self, name):
        if name in self.fail:
            raise RuntimeError(name + ' boom')

    # 运行态行 / meta
    def load_all(self):
        self._check('load_all')
        return [dict(r) for r in self.runtime_rows]

    def upsert_many(self, rows):
        self._check('upsert_many')
        self.upsert_calls.append([dict(r) for r in rows])

    def load_meta(self):
        return dict(self.meta)

    def save_meta(self, **fields):
        self.meta.update(fields)

    # 去重窗
    def load_dedup(self):
        self._check('load_dedup')
        return [dict(v) for v in self.dedup_rows.values()]

    def upsert_dedup(self, rows):
        self._check('upsert_dedup')
        self.dedup_calls.append([dict(r) for r in rows])
        for r in rows:
            self.dedup_rows[(r['symbol'], r['direction'])] = dict(r)

    def prune_dedup(self, cutoff):
        self._check('prune_dedup')
        self.prune_calls.append(('dedup', cutoff))

    # 事件窗
    def load_events(self, since=None):
        self._check('load_events')
        return [dict(r) for r in self.event_rows
                if since is None or r['triggered_at'] >= since]

    def append_events(self, rows):
        self._check('append_events')
        self.event_calls.append([dict(r) for r in rows])
        keys = {(r['triggered_at'], r['rule_id'], r['symbol']) for r in self.event_rows}
        for r in rows:
            key = (r['triggered_at'], r['rule_id'], r['symbol'])
            if key not in keys:
                self.event_rows.append(dict(r))
                keys.add(key)

    def prune_events(self, cutoff):
        self._check('prune_events')
        self.prune_calls.append(('events', cutoff))

    # 价格历史
    def load_price_history(self, symbols=None, since=None):
        self._check('load_price_history')
        self.price_history_args.append((symbols, since))
        return [dict(r) for r in self.history_rows
                if (not symbols or r['symbol'] in symbols)
                and (since is None or r['ts'] >= since)]

    def upsert_price_history(self, rows):
        self._check('upsert_price_history')
        self.history_calls.append([dict(r) for r in rows])

    def prune_price_history(self, cutoff):
        self._check('prune_price_history')
        self.prune_calls.append(('history', cutoff))


# ══════════════ 1) 去重窗：恢复后窗内不再重复通知 ══════════════

class TestWatchDedupWindowPersistence:
    def test_restore_makes_dedup_window_effective(self):
        """重启恢复后，同标的同向在窗内仍判为重复（不再重复通知）"""
        store = FakeCompleteStore(dedup=[
            {'symbol': '600519', 'direction': 'above',
             'notified_at': NOW - timedelta(seconds=30), 'trigger_id': 7, 'rule_id': 1},
        ])
        s = StateManager(dedup_window_sec=60, store=store)
        s.restore_from_store(now=NOW)
        assert ('600519', 'above') in s.recent_notified

        out = DeduplicationManager(s, 60).check(_rule(), _cond(), NOW)
        assert out.is_duplicate is True
        assert out.dup_of == 7

    def test_restore_drops_expired_dedup_keys(self):
        store = FakeCompleteStore(dedup=[
            {'symbol': '600519', 'direction': 'above',
             'notified_at': NOW - timedelta(seconds=300), 'trigger_id': 7, 'rule_id': 1},
        ])
        s = StateManager(dedup_window_sec=60, store=store)
        s.restore_from_store(now=NOW)
        assert s.recent_notified == {}
        assert DeduplicationManager(s, 60).check(_rule(), _cond(), NOW).is_duplicate is False

    def test_flush_writes_only_changed_dedup_keys(self):
        store = FakeCompleteStore()
        s = StateManager(dedup_window_sec=60, store=store)
        DeduplicationManager(s, 60).mark_notified(_rule(), _cond(), NOW, 5)

        assert s.flush(now=NOW) is True
        assert len(store.dedup_calls) == 1
        row = store.dedup_calls[0][0]
        assert (row['symbol'], row['direction'], row['trigger_id']) == ('600519', 'above', 5)

        assert s.flush(now=NOW) is True
        assert len(store.dedup_calls) == 1        # 无变化不重写（节流）


# ══════════════ 2) 事件窗：恢复后频率统计连续 ══════════════

class TestWatchTriggerEventPersistence:
    def test_restored_events_keep_frequency_continuous(self):
        store = FakeCompleteStore(events=[
            {'triggered_at': NOW - timedelta(minutes=5), 'rule_id': 1, 'symbol': '600519.SH'},
            {'triggered_at': NOW - timedelta(minutes=3), 'rule_id': 1, 'symbol': '600519.SH'},
        ])
        # 冷启动（未恢复）只有「本次」——正是频率被误判时的口径
        assert StateManager().recent_trigger_count(NOW, 1, 10) == 1

        s = StateManager(store=store)
        s.restore_from_store(now=NOW)
        assert s.recent_trigger_count(NOW, 1, 10) == 3     # 2 历史 + 本次
        s.record_trigger_event(NOW, 1, '600519.SH')
        assert s.recent_trigger_count(NOW, 1, 10) == 4

    def test_restore_drops_events_outside_retention(self):
        store = FakeCompleteStore(events=[
            {'triggered_at': NOW - timedelta(minutes=90), 'rule_id': 1, 'symbol': '600519.SH'},
            {'triggered_at': NOW - timedelta(minutes=2), 'rule_id': 1, 'symbol': '600519.SH'},
        ])
        s = StateManager(event_retention_min=30, store=store)
        s.restore_from_store(now=NOW)
        assert len(s.trigger_events) == 1

    def test_flush_appends_new_events_only(self):
        store = FakeCompleteStore()
        s = StateManager(store=store)
        s.record_trigger_event(NOW, 1, '600519.SH')
        s.record_trigger_event(NOW, 2, '000001.SZ')
        assert s.flush(now=NOW) is True
        assert len(store.event_calls) == 1
        assert len(store.event_calls[0]) == 2
        assert s.flush(now=NOW) is True
        assert len(store.event_calls) == 1         # 无新事件不重写


# ══════════════ 3) 价格历史：恢复后 velocity 不再冷启动 ══════════════

class TestWatchPriceHistoryPersistence:
    def test_restored_history_removes_velocity_cold_start(self):
        store = FakeCompleteStore(history=[
            {'symbol': '600519.SH', 'ts': NOW - timedelta(minutes=20), 'price': 100.0},
            {'symbol': '600519.SH', 'ts': NOW - timedelta(minutes=10), 'price': 101.0},
        ])
        # 冷启动：窗口内无历史 → 明确报「冷启动」且不判定
        cold = evaluate(_velocity_cond(), _quote(110.0), EvalContext(), now=NOW)
        assert cold.triggered is False
        assert '冷启动' in cold.message

        s = StateManager(store=store)
        s.restore_from_store(now=NOW, symbols={'600519.SH'})
        ctx = EvalContext(price_history=tuple(s.history['600519.SH']))
        res = evaluate(_velocity_cond(), _quote(110.0), ctx, now=NOW)
        assert res.triggered is True
        assert res.value == pytest.approx(10.0)

    def test_history_restore_is_bounded_by_symbols_and_capped(self):
        rows = [{'symbol': '600519.SH', 'ts': NOW - timedelta(seconds=i),
                 'price': 100.0 + i * 0.01} for i in range(300)]
        rows.append({'symbol': '000001.SZ', 'ts': NOW - timedelta(seconds=10), 'price': 9.0})
        store = FakeCompleteStore(history=rows)

        s = StateManager(store=store, history_max_points=240)
        s.restore_from_store(now=NOW, symbols={'600519.SH'})

        assert len(s.history['600519.SH']) == 240     # 单 symbol 硬上限
        assert '000001.SZ' not in s.history           # symbols 之外的标的不恢复
        symbols_arg, since_arg = store.price_history_args[-1]
        assert symbols_arg == {'600519.SH'}
        assert since_arg == NOW - timedelta(minutes=30)

    def test_flush_writes_only_new_price_points(self):
        store = FakeCompleteStore()
        s = StateManager(store=store, history_flush_sec=0)
        s.push_history('600519.SH', NOW - timedelta(minutes=1), 100.0)
        s.push_history('600519.SH', NOW, 101.0)

        assert s.flush(now=NOW) is True
        assert [r['price'] for r in store.history_calls[0]] == [100.0, 101.0]

        s.push_history('600519.SH', NOW + timedelta(seconds=10), 102.0)
        assert s.flush(now=NOW) is True
        assert [r['price'] for r in store.history_calls[1]] == [102.0]   # 只写新点

    def test_history_flush_is_throttled_per_symbol(self):
        store = FakeCompleteStore()
        s = StateManager(store=store, history_flush_sec=60)
        s.push_history('600519.SH', NOW, 100.0)
        assert s.flush(now=NOW) is True                # 首次：无 last → 立即写
        assert len(store.history_calls) == 1

        s.push_history('600519.SH', NOW + timedelta(seconds=10), 101.0)
        assert s.flush(now=NOW + timedelta(seconds=10)) is True
        assert len(store.history_calls) == 1           # 10s < 60s → 节流

        s.push_history('600519.SH', NOW + timedelta(seconds=70), 102.0)
        assert s.flush(now=NOW + timedelta(seconds=70)) is True
        assert len(store.history_calls) == 2


# ══════════════ 4) 有界裁剪 + 写失败降级 ══════════════

class TestWatchBoundedPruneAndFailure:
    def test_prune_called_with_window_cutoffs(self):
        store = FakeCompleteStore()
        s = StateManager(event_retention_min=30, dedup_window_sec=60, store=store,
                         history_retention_min=30, extras_prune_sec=0)
        s.record_trigger_event(NOW, 1, '600519.SH')
        assert s.flush(now=NOW) is True

        calls = dict(store.prune_calls)
        assert calls['dedup'] == NOW - timedelta(seconds=60)
        assert calls['events'] == NOW - timedelta(minutes=30)
        assert calls['history'] == NOW - timedelta(minutes=30)

    def test_prune_is_throttled(self):
        store = FakeCompleteStore()
        s = StateManager(store=store, extras_prune_sec=60)
        s.push_history('600519.SH', NOW, 100.0)
        s.flush(now=NOW)
        n1 = len(store.prune_calls)

        s.push_history('600519.SH', NOW + timedelta(seconds=5), 101.0)
        s.flush(now=NOW + timedelta(seconds=5))
        assert len(store.prune_calls) == n1            # 未到 60s 不再裁剪

        s.push_history('600519.SH', NOW + timedelta(seconds=65), 102.0)
        s.flush(now=NOW + timedelta(seconds=65))
        assert len(store.prune_calls) > n1

    def test_dedup_write_failure_degrades_and_retries(self):
        store = FakeCompleteStore(fail={'upsert_dedup'})
        s = StateManager(dedup_window_sec=60, store=store)
        DeduplicationManager(s, 60).mark_notified(_rule(), _cond(), NOW, 5)

        assert s.flush(now=NOW) is False               # 不抛错，但也不假装成功
        assert s.degraded is True
        assert store.dedup_calls == []

        store.fail.discard('upsert_dedup')
        assert s.flush(now=NOW) is True                # 下轮重试
        assert len(store.dedup_calls) == 1
        assert s.degraded is False

    def test_event_write_failure_degrades_and_retries(self):
        store = FakeCompleteStore(fail={'append_events'})
        s = StateManager(store=store)
        s.record_trigger_event(NOW, 1, '600519.SH')

        assert s.flush(now=NOW) is False
        assert s.degraded is True
        assert store.event_calls == []

        store.fail.discard('append_events')
        assert s.flush(now=NOW) is True
        assert len(store.event_calls) == 1
        assert s.degraded is False

    def test_history_write_failure_degrades_and_retries(self):
        store = FakeCompleteStore(fail={'upsert_price_history'})
        s = StateManager(store=store, history_flush_sec=0)
        s.push_history('600519.SH', NOW, 100.0)

        assert s.flush(now=NOW) is False
        assert s.degraded is True
        assert store.history_calls == []

        store.fail.discard('upsert_price_history')
        assert s.flush(now=NOW) is True
        assert len(store.history_calls) == 1

    def test_restore_failure_in_one_extension_does_not_block_others(self):
        store = FakeCompleteStore(
            dedup=[{'symbol': '600519', 'direction': 'above',
                    'notified_at': NOW - timedelta(seconds=10), 'trigger_id': 5, 'rule_id': 1}],
            history=[{'symbol': '600519.SH', 'ts': NOW - timedelta(minutes=5), 'price': 100.0}],
            fail={'load_events'},
        )
        s = StateManager(store=store)
        s.restore_from_store(now=NOW)
        assert ('600519', 'above') in s.recent_notified     # 去重仍恢复
        assert s.history['600519.SH']                       # 价格历史仍恢复
        assert s.degraded is True                           # 事件失败被显式标记


# ══════════════ 5) 向后兼容 + 引擎接线 ══════════════

class TestWatchBackwardCompatAndEngineWiring:
    def test_store_without_extras_is_behavior_equivalent(self):
        class MinimalStore:
            def __init__(self):
                self.calls = []
            def load_all(self):
                return []
            def upsert_many(self, rows):
                self.calls.append(rows)
            def load_meta(self):
                return {}
            def save_meta(self, **fields):
                pass

        s = StateManager(store=MinimalStore())
        s.record_trigger_event(NOW, 1, '600519.SH')
        assert s.flush(now=NOW) is True            # 无扩展方法：跳过而非报错
        assert s._pending_events == []             # 缓冲不无界增长
        assert s.degraded is False

    def test_without_store_extras_are_noop(self):
        s = StateManager()
        s.record_trigger_event(NOW, 1, '600519.SH')
        assert s._pending_events == []
        assert s.restore_from_store(now=NOW) == 0
        assert s.flush(now=NOW) is False

    def test_engine_restore_passes_active_symbols(self):
        store = FakeCompleteStore(history=[
            {'symbol': '600519.SH', 'ts': NOW - timedelta(minutes=5), 'price': 100.0},
        ])

        class _Repo:
            def list_enabled(self):
                return [_rule()]

        eng = WatchEngine(rule_repo=_Repo(), quote_service=None, notifier=None,
                          now_fn=lambda: NOW, runtime_state_store=store)
        assert eng._restore_runtime_state() == 0
        assert store.price_history_args[-1][0] == {'600519.SH'}    # symbols 有界
        assert eng.state.history['600519.SH']
        assert eng._restore_runtime_state() == 0                   # 幂等：只恢复一次


# ══════════════ 6) 迁移 additive 且幂等（假 cursor，不碰真库）══════════════

class _FakeCursor:
    """模拟 information_schema 查询 + DDL 记录，用来验证迁移幂等（无需数据库）"""

    def __init__(self):
        self.tables = set()
        self.columns = set()
        self.indexes = set()
        self.ddl = []
        self._last = None

    def execute(self, sql, params=None):
        s = ' '.join(str(sql).split())
        if s.startswith('SELECT 1 FROM information_schema.tables'):
            self._last = (1,) if params[1] in self.tables else None
            return
        if s.startswith('SELECT 1 FROM information_schema.columns'):
            self._last = (1,) if (params[1], params[2]) in self.columns else None
            return
        if s.startswith('SELECT 1 FROM pg_indexes'):
            self._last = (1,) if params[1] in self.indexes else None
            return
        m = re.match(r'CREATE TABLE IF NOT EXISTS quant\.(\w+)', s)
        if m:
            self.tables.add(m.group(1))
            self.ddl.append(s)
            return
        m = re.match(r'ALTER TABLE quant\.(\w+) ADD COLUMN IF NOT EXISTS (\w+)', s)
        if m:
            self.columns.add((m.group(1), m.group(2)))
            self.ddl.append(s)
            return
        m = re.match(r'CREATE INDEX IF NOT EXISTS (\w+)', s)
        if m:
            self.indexes.add(m.group(1))
            self.ddl.append(s)
            return
        # INSERT ... ON CONFLICT (id) DO NOTHING：幂等单行兜底，假 cursor 忽略

    def fetchone(self):
        return self._last


def _load_migration():
    path = (Path(__file__).resolve().parents[2]
            / 'infrastructure/persistence/migrations/20260918b_watch_runtime_complete.py')
    spec = importlib.util.spec_from_file_location('mig_20260918b', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_watch_migration_declares_shadow_column_and_light_tables():
    mig = _load_migration()
    assert ('watch_runtime_meta', 'digest_shadow_since') in [(t, c) for t, c, _ in mig.COLUMNS]
    assert {'watch_runtime_dedup', 'watch_trigger_events',
            'watch_price_history'} <= {n for n, _ in mig.TABLES}


def test_watch_migration_is_additive_and_idempotent():
    mig = _load_migration()
    cursor = _FakeCursor()
    cursor.tables.add('watch_runtime_meta')     # 前置迁移 20260918 已建此表

    first = mig.upgrade(cursor)
    assert first == len(mig.TABLES) + len(mig.COLUMNS) + len(mig.INDEXES)
    assert not any('DROP' in d.upper() for d in cursor.ddl)   # additive：无 DROP

    second = mig.upgrade(cursor)
    assert second == 0                                        # 幂等：第二遍 0 变更


def test_watch_migration_requires_prerequisite_table():
    """前置迁移未执行时必须响亮失败，不得静默跳过加列"""
    mig = _load_migration()
    with pytest.raises(RuntimeError):
        mig.upgrade(_FakeCursor())

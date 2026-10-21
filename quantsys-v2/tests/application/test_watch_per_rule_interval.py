"""规则级盯盘频率 `interval_sec`（RFC 017 §2.3 · `per-rule-interval` 卡）。

## 本文件钉住的口径（与交卷判据逐条对应）

| 判据 | 用例 |
|------|------|
| 0 到期/未到期 | `TestDueGate`：到期才取价；未到期**不取价、不评估**（价格历史不增点） |
| 0 临期提速 | `TestNearThresholdSpeedup`：本拍 distance_ratio ≤ buffer → 下一拍 `min(interval, fast)` |
| 0 下限 5s | `TestFloor`：`interval_sec=1/4` 引擎按 5s 执行（并只 warn 一次） |
| 0 重启恢复 | `TestRestartRecovery`：调度缓存是进程内存 → 新进程首拍全部求值（不漏拍） |
| 1 场景矩阵/bootstrap | 本文件不改它们的行为：`interval_sec=NULL`（存量规则）仍逐拍求值 |
| 2 路由透传 | `TestRuleRoutePassthrough`：POST 创建即带频率/持仓态；PATCH 可改（含清空） |
| 3 未到期不产生外呼 | `TestSymbolMerge`：同 symbol 只取一次价；未到期规则不额外外呼 |
| 迁移白名单 | `TestSchemaSyncWhitelist`：新迁移已纳入 `tests/_db_schema_sync.py` 且列真的建出来 |

## 为什么这样测

调度是**时间行为**：mock 掉"到没到期"只会测到自己的假设。这里全部用真实
`WatchEngine.tick()` + 可控时钟（`_Clock`），只替换出口（行情源 / 通知 / 仓储），
再用**行情外呼次数**与**价格历史点数**作为"到底有没有取价/评估"的客观证据——
不是靠断言内部字段来自证。

`interval_sec=NULL` 的存量规则**不做规则级门**（跟随循环档 = 逐拍求值，RFC 017
"存量规则节奏一秒都不该被改变"）：`test_null_interval_rules_still_evaluate_every_beat`
把这条兼容口径钉死，防止后续为了"统一调度"把存量规则也挡在门外（那会让止损
在循环为更短 interval 早醒时**推迟**判定）。
"""
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.watch_async import router
from qs_watch.application.services.watch_engine.engine import (
    RULE_INTERVAL_FLOOR_SEC, WatchEngine, _rule_interval_sec,
)
from tests.services.test_watch_engine import FakeNotifier, FakeQuoteService, make_rule

NOW = datetime(2026, 7, 21, 10, 30)   # 周二，交易时段内（与场景矩阵同一基准）
SYMBOL = '600519.SH'
VALID_CONDITIONS = [
    {'type': 'price_break', 'params': {'direction': 'above', 'price': 100.0}},
]
FAR = 70.0      # 距 100 有 30% → 不临期（distance_ratio 0.30 > buffer 0.2）
NEAR = 99.0     # 距 100 只有 1% → 临期（0.01 ≤ 0.2）


class _Clock:
    """可控引擎时钟（now_fn 无参可调用）。"""

    def __init__(self, at: datetime = NOW):
        self.at = at

    def __call__(self) -> datetime:
        return self.at

    def advance(self, seconds: float) -> datetime:
        self.at = self.at + timedelta(seconds=seconds)
        return self.at


class _Repo:
    def __init__(self, rules):
        self.rules = rules

    def list_enabled(self):
        return list(self.rules)


def _rule(id: int = 1, interval_sec=None, symbol: str = SYMBOL, **attrs):
    rule = make_rule(id=id, symbol=symbol)
    # RFC 017 新列：老库缺列时读出的就是 None（fail-open 跟随全局档），这里显式区分。
    rule.interval_sec = interval_sec
    rule.position_state = 'none'
    for key, value in attrs.items():     # scope 等 make_rule 未覆盖的字段
        setattr(rule, key, value)
    return rule


def _engine(rules, prices=None, clock=None, **kw):
    clock = clock or _Clock()
    return WatchEngine(
        rule_repo=_Repo(rules),
        quote_service=FakeQuoteService(prices or {SYMBOL: FAR}),
        notifier=FakeNotifier(),
        now_fn=clock,
        **kw,
    )


# ── 到期门 ────────────────────────────────────────────────────────
class TestDueGate:

    def test_due_tick_fetches_quote_and_next_beat_waits_interval(self):
        clock = _Clock()
        engine = _engine([_rule(interval_sec=30)], clock=clock)

        assert engine.tick() == []
        assert engine.quote_service.calls == [SYMBOL]

        clock.advance(10)                      # 30s 未到
        assert engine.tick() == []
        assert engine.quote_service.calls == [SYMBOL], '未到期规则不得取价'

        clock.advance(20)                      # 累计 30s → 到期
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL, SYMBOL]

    def test_not_due_tick_does_not_push_price_history(self):
        """不取价的客观证据：同 symbol 的价格历史不新增点（历史只在取价后推）。"""
        clock = _Clock()
        engine = _engine([_rule(interval_sec=30)], clock=clock)
        engine.tick()
        assert engine.state.history[SYMBOL] == [(NOW, FAR)]

        clock.advance(5)
        engine.tick()
        assert engine.state.history[SYMBOL] == [(NOW, FAR)], '未到期不得评估/推点'
        assert engine.state.schedule.last_eval_at[1] == NOW

    def test_null_interval_rules_still_evaluate_every_beat(self):
        """存量规则（interval_sec=NULL）跟随循环档：逐拍求值，节奏一秒不改。

        这也是场景矩阵/e2e 能在冻结时钟下连拍 tick 的前提（首拍之后不能把
        NULL 规则挡在门外）。
        """
        rule = _rule(interval_sec=None)
        assert _rule_interval_sec(rule) is None
        engine = _engine([rule])
        assert engine.tick() == []
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL, SYMBOL]
        assert engine.effective_rule_interval(rule) is None

    def test_market_scope_rules_do_not_enter_rule_schedule(self):
        """市场级规则（scope=market/sector）不参与规则级频率（RFC §2.3 排除项）。"""
        rule = _rule(interval_sec=30, scope='market')
        engine = _engine([rule])
        engine.tick()
        assert engine.quote_service.calls == []
        assert engine.state.schedule.last_eval_at == {}

    def test_interval_change_takes_effect_on_next_beat(self):
        """规则 CRUD 改 interval_sec → 下一拍按新间隔重算（无需重启/热重载）。

        用同一批 rule 对象模拟"库里已改、下一拍 list_enabled 重新读出"。
        """
        clock = _Clock()
        rule = _rule(interval_sec=60)
        engine = _engine([rule], clock=clock)
        engine.tick()
        assert engine.get_metrics()['rule_schedule'][0]['interval_sec'] == 60

        clock.advance(5)
        rule.interval_sec = 5                 # 模拟 PATCH interval_sec=5
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL, SYMBOL], '5s 新间隔立即生效'
        assert engine.get_metrics()['rule_schedule'][0]['interval_sec'] == 5


# ── 临期提速 min(interval, fast) ─────────────────────────────────
class TestNearThresholdSpeedup:

    def test_near_threshold_speeds_next_beat_to_fast_interval(self):
        clock = _Clock()
        rule = _rule(interval_sec=60)
        engine = _engine([rule], {SYMBOL: NEAR}, clock=clock)

        engine.tick()
        assert engine.state.schedule.is_near(1) is True
        assert engine.effective_rule_interval(rule) == 10.0, '临期 → min(60, fast=10)'

        clock.advance(10)
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL, SYMBOL], '10s 就该轮询到（而非 60s）'

    def test_far_from_threshold_keeps_declared_interval(self):
        clock = _Clock()
        rule = _rule(interval_sec=60)
        engine = _engine([rule], {SYMBOL: FAR}, clock=clock)

        engine.tick()
        assert engine.state.schedule.is_near(1) is False
        assert engine.effective_rule_interval(rule) == 60.0

        clock.advance(10)
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL], '未临期 → 不提前求值'

        clock.advance(50)
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL, SYMBOL]

    def test_speedup_never_goes_below_declared_interval(self):
        """min(interval, fast)：interval 比 fast 还短时取自己的 interval（不反向变慢）。"""
        rule = _rule(interval_sec=5)
        engine = _engine([rule], {SYMBOL: NEAR})
        engine.tick()
        assert engine.effective_rule_interval(rule) == 5.0


# ── 下限 5s ─────────────────────────────────────────────────────
class TestFloor:

    def test_below_floor_runs_at_five_seconds(self):
        clock = _Clock()
        rule = _rule(interval_sec=1)
        engine = _engine([rule], clock=clock)

        assert RULE_INTERVAL_FLOOR_SEC == 5
        assert engine.effective_rule_interval(rule) == 5.0, '1s 配置按 5s 执行'

        engine.tick()
        clock.advance(4)
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL], '4s 未到下限'

        clock.advance(1)
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL, SYMBOL]

    def test_floor_warns_only_once_per_rule(self):
        """写入 1–4s 是"可落库但不可执行"的配置：按 5s 执行且**只** warn 一次。"""
        rule = _rule(interval_sec=3)
        engine = _engine([rule])
        engine.tick()
        assert engine._interval_floor_warned == {1}


# ── 重启恢复 ─────────────────────────────────────────────────────
class TestRestartRecovery:

    def test_fresh_process_evaluates_every_rule_on_first_beat(self):
        """调度缓存是进程内存：新进程首拍全部求值（早一拍，不漏拍）。

        RFC 017 §2.3 的订正——不为一份可丢的调度缓存加运行态列；「重启后多久
        轮到这条规则」不是业务事实，「重启后规则还在判定」才是。
        """
        clock = _Clock()
        first = _engine([_rule(interval_sec=60)], clock=clock)
        first.tick()
        assert first.quote_service.calls == [SYMBOL]

        clock.advance(5)                        # 距上一代最后一拍只过了 5s
        restarted = _engine([_rule(interval_sec=60)], clock=clock)
        assert restarted.state.schedule.last_eval_at == {}
        restarted.tick()
        assert restarted.quote_service.calls == [SYMBOL], '首拍到期，不继承上一代的 last_eval_at'
        assert restarted.state.schedule.last_eval_at == {1: clock.at}

    def test_restore_keeps_latch_but_frequency_cache_starts_empty(self):
        """重启恢复的分层口径：闩锁从运行态 store 灌回（不重复推送），
        调度缓存是进程内存（首拍照常求值）——两者互不冒充。"""
        from tests.services.test_runtime_state import FakeRuntimeStore, _row

        clock = _Clock()
        store = FakeRuntimeStore([
            _row(rule_id=1, cond_idx=0, latched=True, last=NOW - timedelta(seconds=60)),
        ])
        engine = _engine([_rule(interval_sec=60)], {SYMBOL: 101.0}, clock=clock,
                         runtime_state_store=store)

        assert engine._restore_runtime_state() == 1
        assert engine.state.schedule.last_eval_at == {}, '调度缓存不落库、不恢复'

        events = engine.tick()
        assert engine.quote_service.calls == [SYMBOL], '首拍照常求值（早一拍，不漏拍）'
        assert events == [], '闩锁已从 store 恢复 → 重启不重复推送'


# ── 同 symbol 合并取价 ───────────────────────────────────────────
class TestSymbolMerge:

    def test_two_rules_same_symbol_share_one_quote_per_beat(self):
        clock = _Clock()
        rules = [_rule(id=1, interval_sec=60), _rule(id=2, interval_sec=60)]
        engine = _engine(rules, clock=clock)

        engine.tick()
        assert engine.quote_service.calls == [SYMBOL], '同 tick 同 symbol 只取一次价'

        clock.advance(10)
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL], '两条规则都未到期 → 本 tick 不外呼'

        clock.advance(50)
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL, SYMBOL]

    def test_one_due_rule_still_single_quote_for_symbol(self):
        """只要还有一条到期，该 symbol 仍只取一次价给到期的规则共享。"""
        clock = _Clock()
        rules = [_rule(id=1, interval_sec=10), _rule(id=2, interval_sec=60)]
        engine = _engine(rules, clock=clock)

        engine.tick()
        assert engine.quote_service.calls == [SYMBOL]

        clock.advance(10)                       # 只有 id=1 到期
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL, SYMBOL]


# ── 主循环 sleep：取最早到期 ─────────────────────────────────────
class TestLoopSleep:

    def test_sleep_is_bounded_by_earliest_due(self):
        clock = _Clock()
        engine = _engine([_rule(interval_sec=30)], clock=clock)
        engine.tick()

        assert engine.seconds_until_next_due() == 30.0
        assert engine.next_sleep_interval(60) == 30.0, 'interval=30 不能被 60s 档位饿死'
        assert engine.next_sleep_interval(10) == 10.0, '档位更短时以档位为准'

    def test_sleep_uses_band_when_no_rule_interval(self):
        engine = _engine([_rule(interval_sec=None)])
        engine.tick()
        assert engine.seconds_until_next_due() is None
        assert engine.next_sleep_interval(60) == 60.0

    def test_sleep_never_below_one_second(self):
        clock = _Clock()
        engine = _engine([_rule(interval_sec=5)], clock=clock)
        engine.tick()
        clock.advance(10)                       # 已过期
        assert engine.next_sleep_interval(60) == 1.0


# ── 可观察性 ────────────────────────────────────────────────────
class TestMetrics:

    def test_metrics_report_rule_schedule(self):
        clock = _Clock()
        engine = _engine([_rule(interval_sec=30)], clock=clock)
        engine.tick()

        metrics = engine.get_metrics()
        assert metrics['rule_schedule_tracked'] == 1
        assert metrics['rule_schedule'] == [
            {'rule_id': 1, 'interval_sec': 30,
             'last_eval_at': NOW.isoformat(), 'next_due_in_sec': 30.0},
        ]
        assert metrics['rule_next_due_in_sec'] == 30.0
        assert metrics['rule_deferred'] == 0

    def test_metrics_count_deferred_rules(self):
        clock = _Clock()
        engine = _engine([_rule(interval_sec=30)], clock=clock)
        engine.tick()
        clock.advance(1)
        engine.tick()
        assert engine.get_metrics()['rule_deferred'] == 1


# ── 路由透传：POST 创建即带频率/持仓态，PATCH 可改 ────────────────
@pytest.fixture()
def client(db_schema_synced):
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture()
def created_rule(client):
    def _create(**payload):
        body = {'symbol': '000001.SZ', 'conditions': VALID_CONDITIONS,
                'context': 'per-rule-interval 测试'}
        body.update(payload)
        resp = client.post('/api/watch/rules', json=body)
        assert resp.status_code == 200, resp.json()
        rule_id = resp.json()['data']['rule']['id']
        return rule_id, resp.json()['data']['rule']

    created = []

    def factory(**payload):
        rule_id, rule = _create(**payload)
        created.append(rule_id)
        return rule_id, rule

    yield factory
    for rule_id in created:
        client.delete('/api/watch/rules/%s' % rule_id)


class TestRuleRoutePassthrough:

    def test_post_persists_interval_and_position_state(self, client, created_rule):
        rule_id, rule = created_rule(interval_sec=30, position_state='holding')
        assert rule['interval_sec'] == 30
        assert rule['position_state'] == 'holding'

        # 读回也是同一份（不是只在创建响应里贴了一层）
        listed = client.get('/api/watch/rules?symbol=000001.SZ').json()['data']['rules']
        persisted = next(r for r in listed if r['id'] == rule_id)
        assert persisted['interval_sec'] == 30
        assert persisted['position_state'] == 'holding'

    def test_post_defaults_keep_backward_compatible(self, created_rule):
        _, rule = created_rule()
        assert rule['interval_sec'] is None, 'NULL = 跟随全局档'
        assert rule['position_state'] == 'none', 'DB 默认 none'

    def test_patch_updates_interval_and_position_state(self, client, created_rule):
        rule_id, _ = created_rule(interval_sec=30, position_state='none')

        resp = client.patch('/api/watch/rules/%s' % rule_id,
                            json={'interval_sec': 15, 'position_state': 'holding'})
        assert resp.status_code == 200, resp.json()
        data = resp.json()['data']
        assert data['rule']['interval_sec'] == 15
        assert data['rule']['position_state'] == 'holding'
        assert set(data['changed_fields']) == {'interval_sec', 'position_state'}

        # 清空回到"跟随全局档"
        resp = client.patch('/api/watch/rules/%s' % rule_id, json={'interval_sec': None})
        assert resp.status_code == 200
        assert resp.json()['data']['rule']['interval_sec'] is None

    @pytest.mark.parametrize('payload', [
        {'interval_sec': 0},
        {'interval_sec': -5},
        {'interval_sec': 'abc'},
        {'interval_sec': True},
        {'position_state': 'maybe'},
    ])
    def test_post_invalid_new_fields_rejected_400(self, client, payload):
        body = {'symbol': '000001.SZ', 'conditions': VALID_CONDITIONS}
        body.update(payload)
        resp = client.post('/api/watch/rules', json=body)
        assert resp.status_code == 400, resp.json()
        assert resp.json()['success'] is False

    def test_patch_invalid_interval_rejected_400(self, client, created_rule):
        rule_id, _ = created_rule()
        resp = client.patch('/api/watch/rules/%s' % rule_id, json={'interval_sec': 0})
        assert resp.status_code == 400


# ── 迁移白名单（tests/_db_schema_sync.py）────────────────────────
class TestSchemaSyncWhitelist:

    def test_new_migration_is_discovered_and_required(self):
        from tests import _db_schema_sync

        modules = [Path(m.__file__).name for m in _db_schema_sync._load_migration_modules()]
        assert '20261021_watch_rules_position_interval.py' in modules, \
            'RFC 017 迁移必须在同步白名单的 glob 里'
        assert ('watch_rules', 'position_state') in _db_schema_sync.REQUIRED_COLUMNS
        assert ('watch_rules', 'interval_sec') in _db_schema_sync.REQUIRED_COLUMNS

    def test_sync_report_has_no_missing_columns(self, db_schema_synced):
        from sqlalchemy import text

        from qs_kernel.infrastructure.persistence.database.engine import get_engine

        with get_engine().connect() as conn:
            names = {row[0] for row in conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'quant' AND table_name = 'watch_rules'"))}
        assert {'position_state', 'interval_sec'} <= names

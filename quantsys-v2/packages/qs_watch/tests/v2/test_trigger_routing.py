"""t6 验收用例：触发路由 router（FR-7/FR-11，architecture.md IF-6）

循环语义（D-14/16/19）：
- 每循环第 1 次 → agent
- 第 2~9 次 → skip（零投递）
- 第 10 次 → direct 并归零
- 每规则独立计数（A 的进度不影响 B）
- 每日重置：**仅活跃规则**归零（2026-10-23 用户裁定：非活跃规则不进判定，不重置）
"""
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.v2 import router


class MemoryCycleStore:
    """内存版计数存储（生产实现 = watch_rules.cycle_count / process_state）。

    ``active_ids`` 模拟「活跃规则集合」——每日重置只清活跃规则的计数；
    非活跃规则（invalid/archived/停用/过期）不参与判定，不重置。
    """

    def __init__(self, active_ids=None):
        self.counts = {}
        self.states = {}
        self.active_ids = set(active_ids) if active_ids is not None else None
        self.reset_calls = 0

    def get_cycle_count(self, rule_id):
        return self.counts.get(rule_id, 0)

    def set_cycle_count(self, rule_id, count):
        self.counts[rule_id] = count

    def set_process_state(self, rule_id, state):
        self.states[rule_id] = state

    def reset_active_cycles(self):
        self.reset_calls += 1
        if self.active_ids is None:
            targets = list(self.counts)
        else:
            targets = [k for k in self.counts if k in self.active_ids]
        for k in targets:
            self.counts[k] = 0
            self.states[k] = 'pending'
        return len(targets)


def _rule(rid):
    return SimpleNamespace(id=rid, symbol='300750.SZ')


class TestCycleRoute:
    def test_first_trigger_routes_to_agent(self):
        store = MemoryCycleStore()
        d = router.route_trigger(_rule(1), store)
        assert d.route == router.ROUTE_AGENT
        assert d.cycle_count == 1
        assert store.counts[1] == 1

    def test_second_to_ninth_skips(self):
        store = MemoryCycleStore()
        router.route_trigger(_rule(1), store)          # 1 → agent
        for expected in range(2, 10):                  # 2..9 → skip
            d = router.route_trigger(_rule(1), store)
            assert d.route == router.ROUTE_SKIP, f'cycle {expected} should skip'
            assert d.cycle_count == expected
        assert store.counts[1] == 9

    def test_tenth_goes_direct_and_resets(self):
        store = MemoryCycleStore()
        for _ in range(9):
            router.route_trigger(_rule(1), store)
        d = router.route_trigger(_rule(1), store)       # 第 10 次
        assert d.route == router.ROUTE_DIRECT
        assert d.cycle_count == 10
        assert store.counts[1] == 0, '第 10 次后必须归零'

    def test_eleventh_starts_new_cycle_with_agent(self):
        store = MemoryCycleStore()
        for _ in range(10):
            router.route_trigger(_rule(1), store)
        d = router.route_trigger(_rule(1), store)       # 新循环第 1 次
        assert d.route == router.ROUTE_AGENT
        assert d.cycle_count == 1


class TestPerRuleIndependence:
    def test_two_rules_count_independently(self):
        """D-19：A 循环到第 5 次不影响 B 的计数。"""
        store = MemoryCycleStore()
        for _ in range(4):
            router.route_trigger(_rule('A'), store)     # A → 第 5 次
        assert store.counts['A'] == 4
        d_b = router.route_trigger(_rule('B'), store)   # B 第一次
        assert d_b.route == router.ROUTE_AGENT
        assert store.counts['B'] == 1
        assert store.counts['A'] == 4


class TestFailOpen:
    def test_read_failure_treated_as_first(self):
        class BrokenStore:
            def get_cycle_count(self, rule_id):
                raise RuntimeError('db down')

            def set_cycle_count(self, rule_id, count):
                pass

        d = router.route_trigger(_rule(1), BrokenStore())
        assert d.route == router.ROUTE_AGENT, '读失败按首发处理（宁可多发不漏）'


class TestDailyReset:
    def test_reset_only_active_cycles(self):
        """2026-10-23 用户裁定：活跃的才重置，非活跃的不需要重置。"""
        store = MemoryCycleStore(active_ids={'A'})
        router.route_trigger(_rule('A'), store)     # A 活跃：当天走了 1 次循环
        router.route_trigger(_rule('B'), store)     # B 非活跃（invalid/停用/过期）
        store.set_process_state('A', 'processed')
        store.set_process_state('B', 'processed')

        n = router.reset_daily_cycles(store)

        assert n == 1, '只重置活跃规则'
        assert store.counts['A'] == 0 and store.states['A'] == 'pending'
        assert store.counts['B'] == 1, '非活跃规则不参与判定，计数保持原样'
        assert store.states['B'] == 'processed', '非活跃规则的处理状态也不该被抹掉'
        assert store.reset_calls == 1

    def test_reset_legacy_store_still_supported(self):
        """旧实现只有 reset_all_cycles()：仍可重置（该名语义已收窄为活跃规则）。"""
        class LegacyStore:
            def __init__(self):
                self.calls = 0

            def reset_all_cycles(self):
                self.calls += 1
                return 3

        store = LegacyStore()
        assert router.reset_daily_cycles(store) == 3
        assert store.calls == 1

    def test_reset_failure_returns_zero(self):
        class BrokenStore:
            def reset_active_cycles(self):
                raise RuntimeError('db down')

        assert router.reset_daily_cycles(BrokenStore()) == 0

    def test_store_without_reset_returns_zero(self):
        class EmptyStore:
            pass

        assert router.reset_daily_cycles(EmptyStore()) == 0

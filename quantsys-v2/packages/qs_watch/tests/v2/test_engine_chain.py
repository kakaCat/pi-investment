"""t9/t10 验收用例：判定链接入 engine.tick（端到端）与每日重置

覆盖：
- tick 判定链：失效 → 分类 → 判定 → 路由 → 投递（用 Fake 全链，不碰 DB）
- 止损空仓 fail-open 在链路中生效
- 10 次循环第 10 次走直通群（notify_feishu）
- 影子模式（无 cycle_store / 无 sender）：只判定不投递
"""
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.v2 import engine as v2_engine
from qs_watch.application.services.watch_engine.v2 import router


class FakeRuleRepo:
    def __init__(self, rules):
        self._rules = rules

    def list_by_state(self, state):
        return list(self._rules)


class FakeQuoteService:
    def __init__(self, prices):
        self.prices = prices
        self.calls = []

    def get_realtime_quote(self, symbol):
        self.calls.append(symbol)
        if symbol not in self.prices:
            raise RuntimeError(f'no quote {symbol}')
        return SimpleNamespace(symbol=symbol, price=self.prices[symbol])


class MemCycleStore:
    def __init__(self):
        self.counts = {}

    def get_cycle_count(self, rule_id):
        return self.counts.get(rule_id, 0)

    def set_cycle_count(self, rule_id, count):
        self.counts[rule_id] = count

    def reset_active_cycles(self):
        # 本 fake 的计数都属于活跃规则（非活跃规则不进引擎判定，也不计数）
        n = len(self.counts)
        for k in list(self.counts):
            self.counts[k] = 0
        return n


def _rule(rid, intent, price, direction, state, symbol='300750.SZ'):
    return SimpleNamespace(
        id=rid,
        symbol=symbol,
        intent=intent,
        conditions=[{'type': 'price_break', 'params': {'price': price, 'direction': direction}}],
        position_state=state,
        account='acct_A',
        cost_price=10.0,
        invalidation_threshold_pct=50.0,
    )


def _engine(rules, prices, **kwargs):
    return v2_engine.WatchEngineV2(
        rule_repo=FakeRuleRepo(rules),
        quote_service=FakeQuoteService(prices),
        **kwargs,
    )


class TestChainEndToEnd:
    def test_holding_stop_triggers_agent_first(self):
        rule = _rule(260, 'exit_stop', 9.0, 'below', 'holding')
        agent_calls, feishu_calls = [], []
        eng = _engine(
            [rule], {'300750.SZ': 8.8},
            cycle_store=MemCycleStore(),
            agent_sender=lambda a, acc, p: agent_calls.append((a, acc)) or True,
            feishu_sender=lambda t, b: feishu_calls.append(t) or True,
            account_agent_map={'acct_A': 'agent-A'},
        )
        result = eng.tick()
        assert len(result.judgments) == 1
        kind, r, judgment, route, delivery = result.judgments[0]
        assert kind == 'trigger'
        assert route.route == router.ROUTE_AGENT
        assert agent_calls == [('agent-A', 'acct_A')]
        assert feishu_calls == []

    def test_tenth_cycle_goes_direct_to_feishu(self):
        rule = _rule(260, 'exit_stop', 9.0, 'below', 'holding')
        store = MemCycleStore()
        store.counts[260] = 9  # 下一次触发即第 10 次
        feishu_calls = []
        eng = _engine(
            [rule], {'300750.SZ': 8.8},
            cycle_store=store,
            agent_sender=lambda a, acc, p: True,
            feishu_sender=lambda t, b: feishu_calls.append(t) or True,
        )
        result = eng.tick()
        kind, r, judgment, route, delivery = result.judgments[0]
        assert route.route == router.ROUTE_DIRECT
        assert len(feishu_calls) == 1
        assert store.counts[260] == 0, '第 10 次后归零'

    def test_unpositioned_entry_triggers_agent(self):
        rule = _rule(127, 'entry', 30.0, 'above', 'none', symbol='000999.SZ')
        agent_calls = []
        eng = _engine(
            [rule], {'000999.SZ': 30.5},
            cycle_store=MemCycleStore(),
            agent_sender=lambda a, acc, p: agent_calls.append(p) or True,
        )
        result = eng.tick()
        kind, r, judgment, route, delivery = result.judgments[0]
        assert judgment.intent == 'entry'
        assert route.route == router.ROUTE_AGENT

    def test_invalidation_short_circuits(self):
        """失效（偏离超线）→ 只产 invalidation 事件，不再判触发。"""
        rule = _rule(306, 'exit_take_profit', 250.0, 'above', 'holding')
        rule.invalidation_threshold_pct = 10.0
        eng = _engine([rule], {'300750.SZ': 320.0}, cycle_store=MemCycleStore())
        result = eng.tick()
        assert len(result.judgments) == 1
        kind, r, event, delivery = result.judgments[0]
        assert kind == 'invalidation'
        assert event.deviation_pct > 10.0
        assert delivery is None  # FakeRepo 无 update_fields → 落库失败不投递

    def test_invalidation_marks_rule_and_dispatches_agent(self):
        """失效闭环：落 rule_state=invalid + 投递对应 agent（2026-10-24 上线补齐）。"""
        class UpdatableRepo(FakeRuleRepo):
            def __init__(self, rules):
                super().__init__(rules)
                self.updated = []

            def update_fields(self, rule_id, **fields):
                self.updated.append((rule_id, fields))
                return True

        rule = _rule(306, 'exit_take_profit', 250.0, 'above', 'holding')
        rule.invalidation_threshold_pct = 10.0
        repo = UpdatableRepo([rule])
        agent_calls = []
        eng = v2_engine.WatchEngineV2(
            rule_repo=repo,
            quote_service=FakeQuoteService({'300750.SZ': 320.0}),
            agent_sender=lambda a, acc, p: agent_calls.append((a, acc, p)) or True,
            account_agent_map={'acct_A': 'agent-A'},
        )
        result = eng.tick()
        kind, r, event, delivery = result.judgments[0]
        assert kind == 'invalidation' and delivery.delivered is True
        assert repo.updated[0][0] == 306
        assert repo.updated[0][1]['rule_state'] == 'invalid'
        assert 'invalid_reason' in repo.updated[0][1]
        assert agent_calls and agent_calls[0][0] == 'agent-A'
        assert '规则失效' in agent_calls[0][2]

    def test_observe_only_archives_without_delivery(self):
        """观察类只留痕：返回 trigger outcome 供归档，但不路由、不唤醒 agent。"""
        rule = _rule(313, 'trend_observe', 10.0, 'above', 'none', symbol='300418')
        agent_calls = []
        eng = _engine(
            [rule], {'300418': 10.5},
            cycle_store=MemCycleStore(),
            agent_sender=lambda a, acc, p: agent_calls.append(p) or True,
        )
        result = eng.tick()
        kind, r, judgment, route, delivery = result.judgments[0]
        assert kind == 'trigger' and judgment.observe_only is True
        assert route is None and delivery is None
        assert agent_calls == []

    def test_shadow_mode_no_delivery(self):
        """无 cycle_store / 无 sender：判定仍留痕（judgments 有），但不路由不投递。"""
        rule = _rule(260, 'exit_stop', 9.0, 'below', 'holding')
        eng = _engine([rule], {'300750.SZ': 8.8})
        result = eng.tick()
        assert len(result.judgments) == 1
        kind, r, judgment, route, delivery = result.judgments[0]
        assert kind == 'trigger'
        assert judgment.triggered is True
        assert route is None, '影子期无 store 不路由'
        assert delivery is None, '影子期不投递'

    def test_single_symbol_failure_does_not_break_tick(self):
        rules = [
            _rule(1, 'exit_stop', 9.0, 'below', 'holding', symbol='AAA'),
            _rule(2, 'exit_stop', 9.0, 'below', 'holding', symbol='BBB'),
        ]
        eng = _engine(rules, {'AAA': 8.8})  # BBB 取价失败
        result = eng.tick()
        assert 'AAA' in result.quotes and result.quotes['AAA'] is not None
        assert result.quotes.get('BBB') is None

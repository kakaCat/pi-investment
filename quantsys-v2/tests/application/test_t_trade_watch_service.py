from types import SimpleNamespace

from qs_watch.application.services.watch_engine.lifecycle.t_trade_watch_service import (
    TTradeWatchService,
)


class FakeRuleRepo:
    def __init__(self):
        self.rules = {99: SimpleNamespace(id=99, enabled=True, rule_state="active")}
        self.updates = []

    def get_by_id(self, rule_id):
        return self.rules.get(rule_id)

    def create_rule(self, **kwargs):
        rule_id = max(self.rules) + 1
        rule = SimpleNamespace(id=rule_id, enabled=True, rule_state="active", **kwargs)
        self.rules[rule_id] = rule
        return rule

    def update_fields(self, rule_id, **fields):
        self.updates.append((rule_id, fields))
        rule = self.rules[rule_id]
        for key, value in fields.items():
            setattr(rule, key, value)
        return rule


class FakeCycleRepo:
    def __init__(self, cycle):
        self.cycle = cycle
        self.commits = 0

    def get(self, cycle_id):
        assert cycle_id == self.cycle.id
        return self.cycle

    def commit(self):
        self.commits += 1


def cycle(status="waiting_sell"):
    return SimpleNamespace(
        id=7, account="agent_brain", symbol="002007", mode="auto_sim", status=status,
        upper_price=13.55, lower_price=12.19, shares=100,
        invalidation="止损优先", sell_rule_id=None, buyback_rule_id=None, rule_sync=None,
    )


def test_reconcile_switches_only_cycle_rules_and_preserves_stop_rule():
    rules = FakeRuleRepo()
    item = cycle()
    service = TTradeWatchService(rule_repo=rules, cycle_repo=FakeCycleRepo(item))
    service.reconcile(item)
    sell_rule_id = item.sell_rule_id
    sell_rule = rules.rules[sell_rule_id]
    assert sell_rule.conditions[0]["params"]["direction"] == "above"
    assert sell_rule.action_params["t_trade_id"] == 7
    assert rules.rules[99].enabled is True

    item.status = "waiting_buyback"
    service.on_fill({"t_trade_id": 7})
    assert rules.rules[sell_rule_id].rule_state == "archived"
    buyback_rule = rules.rules[item.buyback_rule_id]
    assert buyback_rule.conditions[0]["params"]["direction"] == "below"
    assert buyback_rule.action_params["leg"] == "buyback"
    assert rules.rules[99].enabled is True


def test_reconcile_is_idempotent_and_terminal_retires_rules():
    rules = FakeRuleRepo()
    item = cycle()
    service = TTradeWatchService(rule_repo=rules, cycle_repo=FakeCycleRepo(item))
    service.reconcile(item)
    first_id = item.sell_rule_id
    service.reconcile(item)
    assert item.sell_rule_id == first_id
    assert len(rules.rules) == 2
    item.status = "cancelled"
    service.reconcile(item)
    assert rules.rules[first_id].rule_state == "archived"
    assert rules.rules[99].rule_state == "active"

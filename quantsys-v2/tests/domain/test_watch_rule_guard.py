"""规则守卫单测：没有账户的规则不能进入买卖（2026-09-11，w-aebfddcd）"""
import pytest

from domain.watch.services.disposition import TRADE_INTENTS
from domain.watch.services.rule_guard import (
    TradeRuleWithoutAccount, effective_account, guard_new_rule, guard_rule_change,
)


@pytest.mark.parametrize("intent", TRADE_INTENTS)
def test_trade_intent_requires_account(intent):
    with pytest.raises(TradeRuleWithoutAccount) as e:
        guard_new_rule(intent=intent)
    assert "不能进入买卖" in str(e.value)
    guard_new_rule(intent=intent, account="agent_virtual")  # 有账户即通过


def test_observe_intent_without_account_is_allowed():
    guard_new_rule(intent="trend_observe")
    guard_new_rule(intent="")
    guard_new_rule()


def test_intent_derived_from_action_hint_buy():
    """声明 buy 但没写 intent 的规则同样受管（推导与运行时同源）"""
    with pytest.raises(TradeRuleWithoutAccount):
        guard_new_rule(action_hint={"action_on_trigger": "buy"})
    guard_new_rule(action_hint={"action_on_trigger": "buy"}, account="agent_brain")


def test_intent_derived_from_action_hint_sell_stop_loss():
    conds = [{"type": "pnl_pct", "params": {"pct": -8, "direction": "below"}}]
    with pytest.raises(TradeRuleWithoutAccount):
        guard_new_rule(action_hint={"action_on_trigger": "sell"}, conditions=conds)
    guard_new_rule(action_hint={"action_on_trigger": "sell"}, conditions=conds,
                   account="user_main_simulation")


def test_blank_account_is_not_an_account():
    for blank in ("", "   ", None):
        with pytest.raises(TradeRuleWithoutAccount):
            guard_new_rule(intent="entry", account=blank)


class _Rule:
    def __init__(self, intent="trend_observe", account=None, linked_account=None):
        self.symbol = "600519"
        self.intent = intent
        self.account = account
        self.linked_account = linked_account
        self.action_hint = {}
        self.conditions = []


def test_change_to_trade_without_account_rejected():
    with pytest.raises(TradeRuleWithoutAccount):
        guard_rule_change(_Rule(intent="trend_observe"), {"intent": "entry"})


def test_clearing_account_on_trade_rule_rejected():
    rule = _Rule(intent="exit_stop", linked_account="agent_virtual")
    with pytest.raises(TradeRuleWithoutAccount):
        guard_rule_change(rule, {"linked_account": None})
    # 只是改别的字段不受影响
    guard_rule_change(rule, {"context": "改预案"})


def test_effective_account_prefers_linked_account():
    assert effective_account({"account": "a", "linked_account": "b"}) == "b"
    assert effective_account(_Rule(account="a")) == "a"
    assert effective_account(_Rule()) is None

"""账户级计划项领域校验（REQ-261026140857-c192）"""

from datetime import datetime, timedelta, timezone

from qs_plan.domain.plan import (
    ItemConditionDraft,
    PlanItemDraft,
    validate_item_decision,
    validate_items_unique_open,
)

NOW = datetime(2026, 10, 26, 9, tzinfo=timezone.utc)


def _item(**overrides):
    base = {
        "item_id": 1,
        "symbol": "600519.SH",
        "action": "buy",
        "horizon": "swing",
        "target_weight": 0.1,
        "thesis": "质量与估值匹配",
        "invalidation": "基本面恶化",
    }
    base.update(overrides)
    return PlanItemDraft(**base)


def _condition(role="entry", **overrides):
    base = {
        "item_id": 1,
        "role": role,
        "condition_type": "price_break",
        "params": {"price": 1500, "direction": "above"},
        "batch": 0,
        "sequence": 0,
    }
    base.update(overrides)
    return ItemConditionDraft(**base)


def test_valid_buy_with_entry_conditions_passes_activation():
    item = _item(entry_valid_until=NOW + timedelta(days=1))
    problems = validate_item_decision(item, [_condition()], activation=True, now=NOW)
    assert problems == []


def test_activation_requires_buy_entry_conditions():
    item = _item()
    problems = validate_item_decision(item, [], activation=True, now=NOW)
    assert "buy 计划项必须补全入场条件" in problems


def test_sell_and_hold_require_at_least_one_exit_rule():
    for action in ("sell", "hold"):
        item = _item(action=action, target_weight=0.05, target_qty=100)
        problems = validate_item_decision(item, [], activation=True, now=NOW)
        assert "sell/hold 计划项至少要有 stop_loss/reduce/exit_reduce 之一" in problems
        ok = validate_item_decision(item, [_condition(role="stop_loss")], activation=True, now=NOW)
        assert ok == []


def test_avoid_rejects_execution_conditions():
    item = _item(action="avoid", target_weight=None, target_qty=None)
    problems = validate_item_decision(item, [_condition()], activation=True, now=NOW)
    assert "avoid 计划项不得配置执行条件" in problems


def test_invalid_action_horizon_weight_and_required_text():
    item = _item(
        action="bad_action",
        horizon="week",
        target_weight=1.2,
        max_weight=-0.1,
        target_qty=-1,
        thesis="",
        invalidation="",
    )
    problems = validate_item_decision(item, [_condition()])
    assert "action 必须是 buy/add/observe/sell/reduce_risk/hold/avoid 之一" in problems
    assert "horizon 必须是 day/swing" in problems
    assert "target_weight 必须在 0～1" in problems
    assert "max_weight 必须在 0～1" in problems
    assert "target_qty 必须是 >=0 的整数" in problems
    assert "thesis 必填" in problems
    assert "invalidation 必填" in problems


def test_condition_role_batch_sequence_and_params_are_validated():
    item = _item()
    problems = validate_item_decision(
        item,
        [
            _condition(role="watch"),
            _condition(role="entry", condition_type="", sequence=-1),
            _condition(role="entry", condition_type="price_break", params=[]),
            _condition(role="entry", condition_type="price_break", batch=-1),
            _condition(role="entry", condition_type="price_break", item_id=99),
        ],
    )
    assert (
        "条件角色必须是 entry/add_position/trend_observe/stop_loss/reduce/exit_reduce" in problems
    )
    assert "条件 type 必填" in problems
    assert "条件 params 必须是对象" in problems
    assert "条件 batch/sequence 必须非负" in problems
    assert "条件 item_id 与计划项不一致" in problems


def test_expired_entry_valid_until_is_rejected_on_activation():
    item = _item(entry_valid_until=NOW - timedelta(seconds=1))
    problems = validate_item_decision(item, [_condition()], activation=True, now=NOW)
    assert "entry_valid_until 已过期" in problems


def test_same_symbol_cannot_have_multiple_items_in_one_decision():
    first = _item(item_id=1, symbol="600519.SH")
    second = _item(item_id=2, symbol="600519.SH")
    assert validate_items_unique_open([first, second]) == ["同一标的存在多个计划项：600519.SH"]


def test_add_observe_and_reduce_risk_require_matching_conditions():
    add = _item(action="add")
    assert "add 计划项必须补全加仓条件" in validate_item_decision(add, [], activation=True)
    assert validate_item_decision(add, [_condition(role="add_position")], activation=True) == []

    observe = _item(action="observe", target_weight=None, target_qty=None)
    assert "observe 计划项必须补全观察条件" in validate_item_decision(observe, [], activation=True)
    assert (
        validate_item_decision(observe, [_condition(role="trend_observe")], activation=True) == []
    )

    reduce_risk = _item(action="reduce_risk")
    assert "reduce_risk 计划项必须补全风控减仓条件" in validate_item_decision(
        reduce_risk, [], activation=True
    )
    assert (
        validate_item_decision(reduce_risk, [_condition(role="exit_reduce")], activation=True) == []
    )


def test_invalidation_threshold_must_be_positive_percentage():
    item = _item()
    assert "invalidation_threshold_pct 必须在 (0,100]" in validate_item_decision(
        item,
        [_condition(invalidation_threshold_pct=0)],
        activation=True,
        now=NOW,
    )
    assert (
        validate_item_decision(
            item,
            [_condition(invalidation_threshold_pct=8)],
            activation=True,
            now=NOW,
        )
        == []
    )


def test_decimal_weight_from_orm_is_accepted():
    """回归（2026-11-11，w-191eb58c）：ORM 读 NUMERIC 列得 Decimal，
    旧 _weight_ok 用 isinstance(int/float) 把它误判非法，导致
    trading_plan_generate_daily 连续两日全盘失败。"""
    from decimal import Decimal

    item = _item(target_weight=Decimal("0.006483"), max_weight=Decimal("0.15"))
    problems = validate_item_decision(item, [_condition()])
    assert "target_weight 必须在 0～1" not in problems
    assert "max_weight 必须在 0～1" not in problems

    # 越界 Decimal 仍须拒绝
    bad = _item(target_weight=Decimal("1.2"))
    assert "target_weight 必须在 0～1" in validate_item_decision(bad, [_condition()])

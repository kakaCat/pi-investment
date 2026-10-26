"""单标的 spec 收口测试：多 symbol / pool 显式拒绝，防止进入不完整多标的语义。"""

from qs_plan.domain.plan.spec import validate_plan_spec


def _base():
    return {
        "targets": [{"symbol": "600519.SH", "budget_pct": 5, "role": "core"}],
        "entry": {
            "conditions": [{"type": "price_break", "params": {"price": 10}}],
            "combinator": "all_of",
        },
        "exit": {"stop_loss": {"type": "pct", "value": 8}},
        "monitoring": {},
        "schedule": {},
    }


def test_single_symbol_is_valid():
    assert validate_plan_spec(_base()) == []


def test_multiple_symbols_rejected():
    spec = _base()
    spec["targets"].append({"symbol": "000001.SZ", "budget_pct": 5})
    problems = validate_plan_spec(spec)
    assert any("单标的" in p for p in problems)


def test_pool_target_rejected():
    spec = _base()
    spec["targets"] = [{"pool": "core_pool", "budget_pct": 5}]
    problems = validate_plan_spec(spec)
    assert any("明确 symbol" in p for p in problems)


def test_empty_targets_rejected():
    spec = _base()
    spec["targets"] = []
    problems = validate_plan_spec(spec)
    assert any("非空数组" in p for p in problems)

"""计划入场触发必须进入执行核验，而不是泛泛地继续观察。"""
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.v2 import notify_agent


def test_entry_prompt_requires_guarded_execution_or_explicit_blockers():
    rule = SimpleNamespace(
        id=260,
        symbol="601668.SH",
        intent="entry",
        account="agent_brain",
        cost_price=None,
        invalidation_threshold_pct=8.0,
        conditions=[{
            "type": "price_break",
            "params": {"price": 4.62, "direction": "above"},
        }],
        plan_id=42,
        plan_version=3,
        action_params={"action": "buy", "position_pct": 2.0},
    )
    judgment = SimpleNamespace(
        intent="entry",
        hit_conditions=[{"condition": {}, "value": 4.63, "message": "上破 4.62"}],
        quote=SimpleNamespace(symbol="601668.SH", price=4.63),
        pnl_pct=None,
        sellable=None,
    )

    prompt = notify_agent.build_prompt(rule, judgment, "none")

    assert "买入执行核验" in prompt
    assert "R-001" in prompt and "R-008" in prompt and "R-009" in prompt
    assert "portfolio_trade" in prompt
    assert "合法交易时段" in prompt
    assert "具体阻塞项" in prompt
    assert "成交、止损和审计" in prompt

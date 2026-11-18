from types import SimpleNamespace

from qs_watch.application.services.watch_engine.lifecycle.fill_sync_service import (
    FillSyncService,
)
from qs_watch.application.services.watch_engine.v2 import notify_agent, notify_feishu
from qs_watch.domain.watch.models import validate_action_params


def rule(mode="auto_sim"):
    return SimpleNamespace(
        id=31, symbol="002007", account="agent_brain", intent="t_trade",
        conditions=[{"type": "price_break", "params": {"price": 13.55}}],
        action_params={
            "t_trade_id": 7, "leg": "sell", "mode": mode, "quantity": 100,
            "reference_price": 13.55, "buyback_price": 12.19,
        },
        stock_name="华兰生物", cost_price=12.5, invalidation_threshold_pct=20,
    )


def judgment():
    return SimpleNamespace(
        intent="t_trade", hit_conditions=[{"message": "上沿触发"}],
        quote=SimpleNamespace(price=13.60), pnl_pct=8.8, sellable=300,
        _v2_archive_entries=[("x", SimpleNamespace(trigger_id=88))],
    )


def test_agent_prompt_and_context_carry_full_cycle():
    prompt = notify_agent.build_prompt(rule(), judgment(), "holding")
    assert "周期 7" in prompt
    assert "100 股" in prompt
    assert "t_trade 工具" in prompt
    captured = {}
    delivery = notify_agent.send(
        rule(), judgment(), "holding", use_price_gate=False,
        sender=lambda agent, account, text, context: captured.update(context) or True,
    )
    assert delivery.delivered is True
    assert captured["t_trade_id"] == 7
    assert captured["trigger_ids"] == [88]
    assert captured["buyback_price"] == 12.19


def test_remind_prompt_forbids_execution_and_feishu_renders_cycle():
    item = rule("remind_only")
    prompt = notify_agent.build_prompt(item, judgment(), "holding")
    assert "禁止下单" in prompt
    title, body = notify_feishu.render(item, judgment(), "holding")
    assert "区间T" in title
    assert "周期 7" in body
    assert "remind_only" in body
    assert validate_action_params(item.action_params) is None


def test_fill_sync_calls_t_trade_progress_without_affecting_fill():
    calls = []
    position_repo = SimpleNamespace(
        get_position=lambda account, symbol: SimpleNamespace(
            shares_total=100, shares_available=100, avg_cost=12.5,
        )
    )
    service = FillSyncService(
        rule_repo=SimpleNamespace(list_rules=lambda: []),
        position_repo=position_repo,
        t_trade_progress=lambda event: calls.append(event) or {"status": "ok"},
    )
    result = service.on_fill({
        "account_name": "agent_brain", "symbol": "002007", "action": "buy",
        "shares": 100, "price": 12.19, "trade_id": 2, "t_trade_id": 7,
    })
    assert result["t_trade_progress"] == {"status": "ok"}
    assert calls[0]["t_trade_id"] == 7
    assert result["errors"] == []

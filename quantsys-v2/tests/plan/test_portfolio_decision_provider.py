"""组合决策 provider 无文件化适配（REQ-261026140857-c192）"""

from datetime import date

from adapters.outbound.repositories.portfolio_decision_provider import (
    PortfolioDecisionProviderAdapter,
)


def test_provider_calls_core_algorithm_without_file_write(monkeypatch):
    calls = []

    def fake_generate(**kwargs):
        calls.append(kwargs)
        return {
            "account": kwargs["account"],
            "generated_at": "2026-10-26T09:05:00+00:00",
            "data_date": "2026-10-24",
            "mode": "PLAN_ONLY（不下单）",
            "exposure": {"target_pct": 0.2, "first_phase_cap_pct": 0.25},
            "growth_sleeve": {
                "meta": {"exposure_pct_of_total": 0.05},
                "holdings": [{"symbol": "000002", "weight_pct_of_sleeve": 50, "lots": 3}],
            },
            "holdings": [
                {"symbol": "600519", "weight_pct_of_core": 60, "role": "core", "lots": 1},
                {"symbol": "000001", "weight_pct_of_core": 40, "role": "core", "lots": 2},
            ],
            "execution_plan": {
                "batches": [
                    {"batch": 1, "detail": [{"symbol": "600519"}, {"symbol": "000002"}]},
                    {"batch": 2, "detail": [{"symbol": "000001"}]},
                ]
            },
            "market_style": {"style": "balanced"},
            "risk_lens": {"ann_vol": 0.12},
        }

    monkeypatch.setattr("application.services.portfolio_decision_service.generate", fake_generate)

    decision = PortfolioDecisionProviderAdapter().build(
        account="agent_brain", trade_date=date(2026, 10, 26)
    )

    assert calls == [{"account": "agent_brain", "_write": False}]
    assert decision.account == "agent_brain"
    assert decision.trade_date == date(2026, 10, 26)
    assert decision.data_as_of.date().isoformat() == "2026-10-24"
    assert [(target.symbol, target.target_weight) for target in decision.targets] == [
        ("600519", 0.12),
        ("000001", 0.08),
        ("000002", 0.025),
    ]
    assert [target.target_qty for target in decision.targets] == [100, 200, 300]
    assert [target.execution_batch for target in decision.targets] == [1, 2, 1]
    assert all(target.stop_loss == {"type": "pct", "value": 8} for target in decision.targets)
    assert decision.risk_budget["max_total_exposure"] == 0.25
    assert decision.market_gate["style"] == "balanced"

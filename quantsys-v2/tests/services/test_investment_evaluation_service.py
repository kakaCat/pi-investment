"""A 项投资评价纯计算测试：不连库、不触发任何写操作。"""
from datetime import date

import pytest

from application.services.investment_evaluation_service import (
    InvestmentEvaluationService,
    build_trade_episodes,
    calculate_account_economy,
    classify_trade,
    summarize_episodes,
    summarize_signals,
)


def trade(
    trade_id, symbol, action, shares, day, pnl=None, reason="R-009 投资信号", price=10.0,
):
    return {
        "id": trade_id,
        "account_name": "test_account",
        "symbol": symbol,
        "action": action,
        "shares": shares,
        "filled_price": price,
        "price": price,
        "amount": shares * price,
        "commission": 0,
        "stamp_duty": 0,
        "transfer_fee": 0,
        "realized_pnl": pnl,
        "reason": reason,
        "trade_date": day,
        "trade_time": f"{day}T09:31:00",
        "order_id": trade_id + 1000,
    }


def test_partial_sells_form_one_episode_and_engineering_is_separate():
    trades = [
        trade(1, "002007", "BUY", 1100, "2026-08-26", price=13.27),
        trade(2, "002007", "SELL", 500, "2026-10-23", pnl=-248.26),
        trade(3, "002007", "SELL", 600, "2026-10-28", pnl=-620.75),
        trade(4, "601600", "BUY", 1000, "2026-09-10"),
        trade(5, "601600", "SELL", 1000, "2026-09-11", pnl=-559.78),
        trade(6, "600519", "BUY", 100, "2026-09-24", reason="测试 submitted_by 字段 - 盘前挂单"),
        trade(7, "600519", "SELL", 100, "2026-09-28", pnl=-1394.95, reason="工程测试单污染仓，退出"),
        trade(8, "600000", "BUY", 100, "2026-09-24", reason="最终验证 submitted_by 字段功能"),
    ]
    episodes, unmatched = build_trade_episodes(trades)
    assert unmatched == []
    assert len([row for row in episodes if row["symbol"] == "002007"]) == 1
    summary = summarize_episodes(episodes)
    assert summary["economic"]["count"] == 3
    assert summary["economic"]["total_realized_pnl"] == pytest.approx(-2823.74)
    assert summary["investment"]["count"] == 2
    assert summary["investment"]["wins"] == 0
    assert summary["investment"]["losses"] == 2
    assert summary["investment"]["win_rate"] == 0
    assert summary["investment"]["expectancy"] == pytest.approx(-714.395)
    assert summary["open_count"] == 1
    assert summary["excluded_count"] == 1


def test_engineering_classifier_does_not_reject_normal_strategy_validation():
    assert classify_trade({"reason": "策略验证通过，按 A 级信号建仓"})[0] == "investment"
    assert classify_trade({"reason": "回测验证后首次试单"})[0] == "investment"
    assert classify_trade({"reason": "测试 submitted_by 字段"})[0] == "engineering_test"
    assert classify_trade({"submitted_by": "engineering_test", "reason": "字段隔离验证"})[0] == "engineering_test"
    assert classify_trade({"strategy_name": "test_only"})[0] == "engineering_test"
    assert classify_trade({"submitted_by": "strategy_validation", "reason": "策略验证"})[0] == "investment"


def test_no_closed_episode_is_null_not_zero_or_hundred_percent():
    summary = summarize_episodes([])
    assert summary["investment"]["sample_status"] == "insufficient_sample"
    assert summary["investment"]["win_rate"] is None
    assert summary["investment"]["expectancy"] is None


def test_twr_removes_external_deposit_and_accrues_funding_cost():
    snapshots = [
        {"snapshot_date": date(2026, 1, 1), "total_value": 100000, "is_synthetic": False},
        {"snapshot_date": date(2026, 1, 11), "total_value": 510000, "is_synthetic": False},
    ]
    flows = [{"created_at": "2026-01-05T09:00:00", "amount": 400000, "flow_type": "deposit"}]
    result = calculate_account_economy(snapshots, flows, None, date(2026, 1, 11), 0.02)
    assert result["time_weighted_return"] == pytest.approx(0.10)
    assert result["external_net_flow"] == 400000
    assert result["funding_cost_to_nav_date"] == pytest.approx(305000 * 0.02 * 10 / 365)
    assert result["economic_pnl_after_funding_cost"] == pytest.approx(
        10000 - 305000 * 0.02 * 10 / 365
    )


def test_backfilled_deposit_is_aligned_to_cash_balance_not_late_ledger_date():
    snapshots = [
        {"snapshot_date": date(2026, 7, 21), "total_value": 100000, "cash": 100000, "is_synthetic": False},
        {"snapshot_date": date(2026, 8, 25), "total_value": 100000, "cash": 100000, "is_synthetic": False},
        {"snapshot_date": date(2026, 9, 10), "total_value": 99868.75, "cash": 75472.75, "is_synthetic": False},
        {"snapshot_date": date(2026, 9, 11), "total_value": 500396, "cash": 485920, "is_synthetic": False},
    ]
    flows = [
        {"id": 1, "flow_type": "deposit", "created_at": "2026-08-25T21:50:49", "amount": 100000, "balance_after": 100000},
        {"id": 2, "flow_type": "deposit", "created_at": "2026-09-13T15:12:54", "amount": 401077.03, "balance_after": 485920},
    ]
    result = calculate_account_economy(snapshots, flows, None, date(2026, 9, 11), 0.02)
    assert result["external_net_flow"] == pytest.approx(401077.03)
    assert result["external_flow_alignment"][0]["included_in_period"] is False
    assert result["external_flow_alignment"][1]["effective_date"] == "2026-09-11"
    assert result["time_weighted_return"] is not None
    assert result["time_weighted_return"] > -0.03
    assert result["intervals"][-1]["external_flow"] == pytest.approx(401077.03)


def test_global_signals_are_not_account_evidence_and_episode_dedup_is_explicit():
    signals = [
        {"id": 1, "signal_date": date(2026, 1, 1), "symbol": "600000", "source": "manual", "grade": "B", "return_5d": 0.02},
        {"id": 2, "signal_date": date(2026, 1, 10), "symbol": "600000", "source": "manual", "grade": "B", "return_5d": -0.03},
        {"id": 3, "signal_date": date(2026, 2, 1), "symbol": "600000", "source": "manual", "grade": "B", "return_5d": -0.01},
    ]
    result = summarize_signals(signals)
    assert result["scope"] == "global_unassigned"
    assert result["not_account_evidence"] is True
    assert result["independence_status"] == "estimated"
    assert result["total_records"] == 3
    assert result["estimated_independent_episodes"] == 2
    assert result["by_grade"]["B"]["count"] == 2
    assert result["by_grade"]["B"]["window_5d"]["average_return"] == pytest.approx(0.005)


class FakeRepository:
    def get_trades(self, account_name, start_date, end_date):
        return [
            trade(6, "600519", "BUY", 100, "2026-09-24", reason="测试 submitted_by 字段"),
            trade(7, "600519", "SELL", 100, "2026-09-28", pnl=-1394.95, reason="工程测试单污染仓"),
        ]

    def get_snapshots(self, account_name, end_date):
        return [
            {"snapshot_date": date(2026, 9, 24), "total_value": 500000, "is_synthetic": False},
            {"snapshot_date": date(2026, 9, 28), "total_value": 498605.05, "is_synthetic": False},
        ]

    def get_external_flows(self, account_name, start_date, end_date):
        return []

    def get_positions(self, account_name):
        return []

    def get_signals(self, start_date, end_date):
        return []

    def get_decision_summary(self, account_name):
        return {"decision_count": 2, "scored_count": 0, "trade_decision_count": 2, "latest_decision_at": None}

    def get_account(self, account_name):
        return {"account_name": account_name, "total_value": 498605.05, "updated_at": None}


def test_report_keeps_engineering_loss_in_economy_but_excludes_it_from_ability():
    report = InvestmentEvaluationService(FakeRepository()).build_report(
        "test_account", end_date="2026-09-28"
    )
    assert report["read_only"] is True
    assert report["trade_economy"]["realized_pnl_all_sells"] == -1394.95
    assert report["trade_economy"]["engineering_realized_pnl"] == -1394.95
    assert report["investment_ability"]["count"] == 0
    assert report["investment_ability"]["win_rate"] is None
    assert report["data_quality"]["excluded_engineering_trade_ids"] == [6, 7]
    assert report["signal_evaluation"]["not_account_evidence"] is True

"""日检结果契约测试（REQ-261004154902-a7cd · t2 / FR-1 / FR-2）。

覆盖验收标准：
① 因子返回空 → ``ok=False`` 且 ``reason='factor_empty'``；
② 模型预测抛错 → ``ok=False``、``reason='rebalance_failed'``；
③ ``hasattr(SimulationTrader, '_send_rebalance_notification')`` 为真（方法必须真在类上）；
④ 通知抛错/未送达时，成功的调仓仍是成功，但 ``detail['notify_error']`` 非空；
⑤ 非交易日与未到调仓周期 → ``status='skipped'``，**不是** success。

全部用例零数据库写入、零真实通知：实例用 ``__new__`` 构造，失败出口被替换成记录器，
交易/落库方法被替换成桩。
"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

import live_trading.simulation_trader as st
from live_trading.simulation_trader import SimulationTrader


@pytest.fixture()
def failures(monkeypatch):
    """替换失败出口，记录每次外发（不触碰真实通道）。"""
    recorded = []

    def fake_report_failure(source, reason, error=None, severity="normal", context=None):
        recorded.append(
            {"source": source, "reason": reason, "error": error, "severity": severity, "context": context}
        )
        return True

    monkeypatch.setattr(st, "report_failure", fake_report_failure)
    return recorded


def _bare_trader(*, model=object(), trading_day=True, rebalance_due=True):
    """不打 DB、不建连接的最小实例（只具备 run_daily_check 需要的属性）。"""
    trader = SimulationTrader.__new__(SimulationTrader)
    trader.account_name = "v13_simulation"
    trader.model_path = "live_trading/models/v13_model.json"
    trader.config = {"strategy": {"rebalance_days": 5}, "initial_capital": 100000}
    trader.model = model
    trader.portfolio = {}
    trader.cash = 100000.0
    trader.last_rebalance_date = "2026-08-31"
    trader._last_notify_error = None
    trader.risk_controller = SimpleNamespace(check_single_stock_stop_loss=lambda *a, **k: [])
    trader._is_trading_day = lambda _date: trading_day
    trader._is_rebalance_due = lambda _date: rebalance_due
    return trader


# -- ① 因子为空 --------------------------------------------------------------
def test_factor_empty_is_failed_with_specific_reason(failures, monkeypatch):
    trader = _bare_trader()
    monkeypatch.setattr(trader, "_validate_data_consistency", lambda: None)
    monkeypatch.setattr(trader, "_get_stock_pool", lambda limit=200: [{"symbol": "300109"}])
    trader.factor_calc = SimpleNamespace(get_latest_factors=lambda stocks: pd.DataFrame())

    outcome = trader.run_daily_check()

    assert outcome["ok"] is False
    assert outcome["status"] == "failed"
    assert outcome["reason"] == "factor_empty"
    assert outcome["error"]
    assert failures and failures[0]["reason"] == "factor_empty"


# -- ② 调仓抛错 --------------------------------------------------------------
def test_rebalance_failure_is_reported_as_failed(failures, monkeypatch):
    trader = _bare_trader()
    monkeypatch.setattr(trader, "rebalance", lambda _date: {"success": False, "error": "predict exploded"})

    outcome = trader.run_daily_check()

    assert outcome["executed"] is False
    assert outcome["ok"] is False
    assert outcome["status"] == "failed"
    assert outcome["reason"] == "rebalance_failed"
    assert "predict exploded" in outcome["error"]
    assert failures and failures[0]["source"] == "strategy.daily_check"


def test_old_behaviour_would_have_lied(failures, monkeypatch):
    """回归锁：调仓失败**绝不**能再返回 executed=True + action='rebalance'。"""
    trader = _bare_trader()
    monkeypatch.setattr(trader, "rebalance", lambda _date: {"success": False, "error": "boom"})

    outcome = trader.run_daily_check()

    assert not (outcome["executed"] is True and outcome["action"] == "rebalance")
    assert outcome["status"] != "success"


# -- ③ 通知方法必须在类上 ----------------------------------------------------
def test_notification_methods_are_real_class_methods():
    assert hasattr(SimulationTrader, "_send_rebalance_notification") is True
    assert hasattr(SimulationTrader, "_format_rebalance_content") is True
    # 曾经它们被缩进在 if __name__ == '__main__' 块里 → 调用点必抛 AttributeError
    import inspect

    assert inspect.isfunction(SimulationTrader.__dict__["_send_rebalance_notification"])


# -- ④ 通知失败不影响成败判定 ------------------------------------------------
def test_notification_failure_does_not_flip_success(failures, monkeypatch):
    trader = _bare_trader()
    monkeypatch.setattr(
        trader,
        "rebalance",
        lambda _date: {
            "success": True,
            "position_count": 5,
            "total_value": 123456.0,
            "notify_ok": False,
            "notify_error": "send_card 返回 False",
        },
    )

    outcome = trader.run_daily_check()

    assert outcome["ok"] is True
    assert outcome["status"] == "success"
    assert outcome["reason"] == "ok"
    assert outcome["notify_ok"] is False
    assert outcome["notify_error"] == "send_card 返回 False"


# -- ⑤ 跳过不许算成功 --------------------------------------------------------
def test_not_trading_day_is_skipped_not_success(failures):
    trader = _bare_trader(trading_day=False)

    outcome = trader.run_daily_check()

    assert outcome["status"] == "skipped"
    assert outcome["reason"] == "not_trading_day"
    assert outcome["ok"] is False


def test_not_due_is_skipped_not_success(failures):
    trader = _bare_trader(rebalance_due=False)

    outcome = trader.run_daily_check()

    assert outcome["status"] == "skipped"
    assert outcome["reason"] == "not_due"
    assert outcome["ok"] is False
    assert "days_to_next" in outcome


def test_model_not_loaded_is_failed_not_skipped(failures):
    trader = _bare_trader(model=None)

    outcome = trader.run_daily_check()

    assert outcome["status"] == "failed"
    assert outcome["reason"] == "model_not_loaded"
    assert outcome["executed"] is False


# -- 空转的真实后果：先前的 not_due 会被记 success ---------------------------
def test_not_due_payload_no_longer_says_success(failures):
    trader = _bare_trader(rebalance_due=False)
    payload = trader.run_daily_check()
    # 兼容字段仍在（既有调用方读它们）
    assert "executed" in payload and "reason" in payload and "action" in payload
    # 但新增的 status 必须说实话
    assert payload["status"] == "skipped"

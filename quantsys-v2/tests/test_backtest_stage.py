"""
BacktestStage unit tests
"""
import pytest
from domain.quantlib.stages.backtest_stage import (
    BacktestStage, Position, Trade, DailyEquity
)


def make_klines(n: int = 100, trend: float = 0.5) -> list:
    """Generate synthetic klines with a mild upward trend."""
    import numpy as np
    np.random.seed(42)
    base = 100.0
    klines = []
    for i in range(n):
        drift = trend * (i / n)
        change = np.random.randn() * 2
        close = base + drift + change
        high = close + abs(np.random.randn() * 0.5)
        low = close - abs(np.random.randn() * 0.5)
        open_p = low + np.random.random() * (high - low)
        volume = np.random.randint(10000, 1000000)
        klines.append({
            "date": f"2024-{(i // 20) + 1:02d}-{(i % 20) + 1:02d}",
            "open": round(open_p, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": volume,
        })
        base = close
    return klines


def make_buy_signals(klines: list) -> list:
    """Generate buy/sell signal pairs."""
    dates = [k["date"] for k in klines]
    return [
        {"date": dates[10], "action": "buy", "symbol": "TEST", "reason": "ma_cross"},
        {"date": dates[50], "action": "sell", "symbol": "TEST", "reason": "take_profit"},
    ]


class TestBacktestStageValidation:
    def test_missing_symbol(self):
        stage = BacktestStage()
        with pytest.raises(ValueError, match="symbol"):
            stage.validate_input({"klines": make_klines()})

    def test_missing_klines(self):
        stage = BacktestStage()
        with pytest.raises(ValueError, match="klines"):
            stage.validate_input({"symbol": "TEST"})

    def test_insufficient_klines(self):
        stage = BacktestStage()
        with pytest.raises(ValueError, match="at least 2"):
            stage.validate_input({"symbol": "TEST", "klines": [{"close": 100}]})

    def test_valid_input(self):
        stage = BacktestStage()
        assert stage.validate_input({
            "symbol": "TEST", "klines": make_klines()
        }) is True


class TestBacktestStageRun:
    def test_no_signals_buy_and_hold(self):
        """Without signals, engine holds cash — no trades."""
        klines = make_klines(50, trend=2.0)
        stage = BacktestStage(initial_capital=100000)
        result = stage.process({
            "symbol": "TEST",
            "klines": klines,
            "signals": [],
        })

        bt = result["backtest"]
        assert "metrics" in bt
        assert "equity_curve" in bt
        assert "trades" in bt
        assert len(bt["equity_curve"]) == 50
        # No signals → no trades
        assert bt["metrics"]["total_trades"] == 0

    def test_buy_then_sell(self):
        klines = make_klines(100, trend=5.0)
        signals = make_buy_signals(klines)
        stage = BacktestStage(initial_capital=100000)
        result = stage.process({
            "symbol": "TEST",
            "klines": klines,
            "signals": signals,
        })

        bt = result["backtest"]
        metrics = bt["metrics"]
        assert metrics["total_trades"] == 1
        assert metrics["initial_capital"] == 100000
        assert "final_capital" in metrics
        assert "total_return" in metrics
        assert "sharpe_ratio" in metrics
        assert len(bt["trades"]) == 1

    def test_buy_no_money(self):
        """Cannot buy if capital is insufficient."""
        klines = make_klines(50)
        stage = BacktestStage(initial_capital=100)  # Very little money
        result = stage.process({
            "symbol": "TEST",
            "klines": klines,
            "signals": [{"date": klines[10]["date"], "action": "buy", "symbol": "TEST"}],
        })
        assert result["backtest"]["metrics"]["total_trades"] == 0

    def test_sell_without_position(self):
        """Sell signal when no position held — ignored."""
        klines = make_klines(50)
        stage = BacktestStage()
        result = stage.process({
            "symbol": "TEST",
            "klines": klines,
            "signals": [{"date": klines[10]["date"], "action": "sell", "symbol": "TEST"}],
        })
        assert result["backtest"]["metrics"]["total_trades"] == 0

    def test_preserves_input_data(self):
        klines = make_klines(30)
        stage = BacktestStage()
        data = {"symbol": "TEST", "klines": klines, "signals": [], "extra": "keep"}
        result = stage.process(data)
        assert result["symbol"] == "TEST"
        assert result["klines"] == klines
        assert result["extra"] == "keep"

    def test_override_parameters_from_input(self):
        klines = make_klines(30)
        stage = BacktestStage(initial_capital=100000)
        result = stage.process({
            "symbol": "TEST",
            "klines": klines,
            "signals": [],
            "initial_capital": 50000,
            "commission_rate": 0.001,
        })
        metrics = result["backtest"]["metrics"]
        assert metrics["initial_capital"] == 50000

    def test_multiple_buy_signals_only_first_executes(self):
        """Only first buy executes when already in position."""
        klines = make_klines(80, trend=3.0)
        signals = [
            {"date": klines[10]["date"], "action": "buy", "symbol": "TEST"},
            {"date": klines[20]["date"], "action": "buy", "symbol": "TEST"},
            {"date": klines[50]["date"], "action": "sell", "symbol": "TEST"},
        ]
        stage = BacktestStage(initial_capital=100000)
        result = stage.process({
            "symbol": "TEST",
            "klines": klines,
            "signals": signals,
        })
        assert result["backtest"]["metrics"]["total_trades"] == 1

    def test_metrics_structure(self):
        klines = make_klines(50)
        stage = BacktestStage()
        result = stage.process({
            "symbol": "TEST", "klines": klines, "signals": []
        })
        m = result["backtest"]["metrics"]
        for key in [
            "total_return", "annual_return", "max_drawdown", "sharpe_ratio",
            "total_trades", "win_rate", "profit_loss_ratio", "avg_holding_days",
            "initial_capital", "final_capital", "winning_trades", "losing_trades"
        ]:
            assert key in m, f"Missing metric: {key}"

    def test_equity_curve_structure(self):
        klines = make_klines(30)
        stage = BacktestStage()
        result = stage.process({
            "symbol": "TEST", "klines": klines, "signals": []
        })
        for eq in result["backtest"]["equity_curve"]:
            for key in ["date", "cash", "position_value", "total_equity", "return_pct", "drawdown"]:
                assert key in eq


class TestBacktestStageEdgeCases:
    def test_upward_trend_profitable(self):
        """Strong uptrend should produce positive returns."""
        klines = make_klines(100, trend=10.0)
        signals = make_buy_signals(klines)
        stage = BacktestStage(initial_capital=100000)
        result = stage.process({
            "symbol": "TEST", "klines": klines, "signals": signals,
        })
        # In strong uptrend buy-hold-sell should be profitable
        trade = result["backtest"]["trades"][0]
        assert trade["profit"] > 0

    def test_downward_trend_unprofitable(self):
        """Strong downtrend with buy-sell should produce loss."""
        klines = make_klines(100, trend=-10.0)
        signals = make_buy_signals(klines)
        stage = BacktestStage(initial_capital=100000)
        result = stage.process({
            "symbol": "TEST", "klines": klines, "signals": signals,
        })
        trade = result["backtest"]["trades"][0]
        assert trade["profit"] < 0

    def test_hold_across_full_period(self):
        """Buy at start, sell at end — entire period."""
        klines = make_klines(80, trend=3.0)
        signals = [
            {"date": klines[5]["date"], "action": "buy", "symbol": "TEST"},
            {"date": klines[70]["date"], "action": "sell", "symbol": "TEST"},
        ]
        stage = BacktestStage(initial_capital=100000)
        result = stage.process({
            "symbol": "TEST", "klines": klines, "signals": signals,
        })
        trade = result["backtest"]["trades"][0]
        assert trade["holding_days"] > 0

    def test_custom_slippage_commission(self):
        klines = make_klines(80, trend=3.0)
        signals = make_buy_signals(klines)
        stage = BacktestStage(
            initial_capital=100000,
            commission_rate=0.001,
            slippage_rate=0.002,
            stamp_tax_rate=0.002,
        )
        result = stage.process({
            "symbol": "TEST", "klines": klines, "signals": signals,
        })
        assert result["backtest"]["metrics"]["total_trades"] == 1

    def test_drawdown_calculated(self):
        klines = make_klines(50)
        stage = BacktestStage()
        result = stage.process({
            "symbol": "TEST", "klines": klines, "signals": []
        })
        # Equity stays flat (all cash), drawdown should be near 0
        for eq in result["backtest"]["equity_curve"]:
            assert eq["drawdown"] <= 0.0  # drawdown is non-positive


class TestMetricsCalculation:
    def test_no_trades_metrics(self):
        from domain.quantlib.stages.backtest_stage import BacktestStage as BS
        metrics = BS._calculate_metrics([], [], 100000, "", "")
        assert metrics["total_trades"] == 0
        assert metrics["sharpe_ratio"] == 0.0

    def test_with_equity_curve_no_trades(self):
        from domain.quantlib.stages.backtest_stage import DailyEquity, BacktestStage as BS
        eq = [DailyEquity("2024-01-01", 100000, 0, 100000, 0, 0)]
        metrics = BS._calculate_metrics(eq, [], 100000, "2024-01-01", "2024-01-01")
        assert metrics["total_return"] == 0.0
        assert metrics["max_drawdown"] == 0.0

"""
RiskAssessmentStage unit tests
"""
import pytest
import numpy as np
import pandas as pd
from domain.quantlib.stages.risk_stage import RiskAssessmentStage


def make_klines(n: int = 100, volatility: float = 2.0) -> list:
    """Generate synthetic klines with random walk."""
    np.random.seed(42)
    base = 100.0
    klines = []
    for i in range(n):
        change = np.random.randn() * volatility
        close = base + change
        high = close + abs(np.random.randn())
        low = close - abs(np.random.randn())
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


def make_uptrend_klines(n: int = 100) -> list:
    """Generate klines with clear uptrend."""
    np.random.seed(42)
    base = 100.0
    klines = []
    for i in range(n):
        drift = 0.1 * i  # steady uptrend
        noise = np.random.randn() * 1.5
        close = base + drift + noise
        high = close + abs(np.random.randn())
        low = close - abs(np.random.randn() * 0.5)
        volume = np.random.randint(10000, 1000000)
        klines.append({
            "date": f"2024-{(i // 20) + 1:02d}-{(i % 20) + 1:02d}",
            "close": round(close, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "open": round(low + np.random.random() * (high - low), 2),
            "volume": volume,
        })
        base = close
    return klines


class TestRiskAssessmentStageValidation:
    def test_missing_symbol(self):
        stage = RiskAssessmentStage()
        with pytest.raises(ValueError, match="symbol"):
            stage.validate_input({"klines": make_klines()})

    def test_missing_klines(self):
        stage = RiskAssessmentStage()
        with pytest.raises(ValueError, match="klines"):
            stage.validate_input({"symbol": "TEST"})

    def test_insufficient_klines(self):
        stage = RiskAssessmentStage()
        with pytest.raises(ValueError, match="at least 5"):
            stage.validate_input({
                "symbol": "TEST",
                "klines": [{"close": 100} for _ in range(3)]
            })

    def test_valid_input(self):
        stage = RiskAssessmentStage()
        assert stage.validate_input({
            "symbol": "TEST", "klines": make_klines(10)
        }) is True


class TestRiskAssessmentStageRun:
    def test_basic_risk_metrics(self):
        klines = make_klines(100)
        stage = RiskAssessmentStage()
        result = stage.process({
            "symbol": "000001.SZ",
            "klines": klines,
        })

        ra = result["risk_assessment"]
        assert ra["symbol"] == "000001.SZ"
        assert "var_95" in ra
        assert "cvar_95" in ra
        assert "volatility" in ra
        assert "sharpe_ratio" in ra
        assert "max_drawdown" in ra
        assert ra["data_points"] > 0

    def test_preserves_input_data(self):
        klines = make_klines(50)
        stage = RiskAssessmentStage()
        data = {"symbol": "TEST", "klines": klines, "extra": "keep"}
        result = stage.process(data)
        assert result["symbol"] == "TEST"
        assert result["klines"] == klines
        assert result["extra"] == "keep"

    def test_var_95_is_negative(self):
        """VaR at 95% confidence should be negative (loss)."""
        klines = make_klines(200, volatility=3.0)
        stage = RiskAssessmentStage(confidence_level=0.95)
        result = stage.process({"symbol": "TEST", "klines": klines})
        assert result["risk_assessment"]["var_95"] < 0

    def test_var_99_worse_than_var_95(self):
        """VaR at 99% should be worse (more negative) than VaR at 95%."""
        klines = make_klines(200, volatility=3.0)
        stage = RiskAssessmentStage()
        result = stage.process({"symbol": "TEST", "klines": klines})
        assert result["risk_assessment"]["var_99"] <= result["risk_assessment"]["var_95"]

    def test_cvar_worse_than_var(self):
        """CVaR should be worse than VaR."""
        klines = make_klines(200, volatility=3.0)
        stage = RiskAssessmentStage()
        result = stage.process({"symbol": "TEST", "klines": klines})
        assert result["risk_assessment"]["cvar_95"] <= result["risk_assessment"]["var_95"]

    def test_max_drawdown_in_uptrend(self):
        """In uptrend, max drawdown should be small."""
        klines = make_uptrend_klines(100)
        stage = RiskAssessmentStage()
        result = stage.process({"symbol": "TEST", "klines": klines})
        # Uptrend, but there's noise — drawdown exists but limited
        assert result["risk_assessment"]["max_drawdown"] > -0.5

    def test_no_close_data_returns_error(self):
        stage = RiskAssessmentStage()
        result = stage.process({
            "symbol": "TEST",
            "klines": [{"date": f"2024-01-{(i+1):02d}"} for i in range(10)],
        })
        assert "error" in result["risk_assessment"]

    def test_all_metrics_present(self):
        klines = make_klines(100)
        stage = RiskAssessmentStage()
        result = stage.process({"symbol": "TEST", "klines": klines})
        ra = result["risk_assessment"]
        expected_keys = [
            "symbol", "data_points", "latest_price", "mean_return",
            "volatility", "var_95", "var_99", "cvar_95", "cvar_99",
            "parametric_var_95", "max_drawdown", "max_drawdown_days",
            "sharpe_ratio", "sortino_ratio", "calmar_ratio",
            "win_rate_daily", "avg_win", "avg_loss", "skewness", "kurtosis",
        ]
        for key in expected_keys:
            assert key in ra, f"Missing: {key}"

    def test_custom_parameters(self):
        klines = make_klines(50)
        stage = RiskAssessmentStage(confidence_level=0.99, risk_free_rate=0.03)
        result = stage.process({
            "symbol": "TEST", "klines": klines,
            "confidence_level": 0.90,
            "risk_free_rate": 0.01,
        })
        ra = result["risk_assessment"]
        assert ra["symbol"] == "TEST"
        assert ra["var_95"] < 0  # standard metric always present
        assert ra["var_99"] < 0  # standard metric always present

    def test_stage_name_default(self):
        stage = RiskAssessmentStage()
        assert stage.name == "risk"

    def test_stage_name_custom(self):
        stage = RiskAssessmentStage(name="risk_analysis")
        assert stage.name == "risk_analysis"


class TestPositionRisk:
    def test_with_positions(self):
        klines = make_klines(50)
        positions = [
            {"symbol": "000001.SZ", "shares": 1000, "entry_price": 95.0},
            {"symbol": "000002.SZ", "shares": 500, "entry_price": 50.0},
        ]
        stage = RiskAssessmentStage()
        result = stage.process({
            "symbol": "PORTFOLIO",
            "klines": klines,
            "positions": positions,
        })
        ra = result["risk_assessment"]
        assert "position_risk" in ra
        pr = ra["position_risk"]
        assert pr["position_count"] == 2
        assert pr["total_value"] > 0
        assert len(pr["positions"]) == 2
        for p in pr["positions"]:
            assert "weight" in p
            assert "pnl" in p
            assert "pnl_pct" in p

    def test_position_weights_sum_to_one(self):
        klines = make_klines(50)
        positions = [
            {"symbol": "A", "shares": 100, "entry_price": 50.0},
            {"symbol": "B", "shares": 200, "entry_price": 25.0},
        ]
        stage = RiskAssessmentStage()
        result = stage.process({
            "symbol": "PORTFOLIO",
            "klines": klines,
            "positions": positions,
        })
        weights = [p["weight"] for p in result["risk_assessment"]["position_risk"]["positions"]]
        assert sum(weights) == pytest.approx(1.0, 0.01)

    def test_empty_positions(self):
        klines = make_klines(30)
        stage = RiskAssessmentStage()
        result = stage.process({
            "symbol": "TEST",
            "klines": klines,
            "positions": [],
        })
        assert "position_risk" not in result["risk_assessment"]

    def test_position_with_avg_cost_fallback(self):
        klines = make_klines(30)
        positions = [{"symbol": "A", "shares": 100, "avg_cost": 95.0}]
        stage = RiskAssessmentStage()
        result = stage.process({
            "symbol": "PORTFOLIO",
            "klines": klines,
            "positions": positions,
        })
        p = result["risk_assessment"]["position_risk"]["positions"][0]
        assert p["entry_price"] == 95.0


class TestHelperMethods:
    def test_historical_var(self):
        returns = pd.Series(np.random.randn(1000) * 0.02)
        var = RiskAssessmentStage._historical_var(returns, 0.95)
        assert var < 0

    def test_historical_cvar(self):
        returns = pd.Series(np.random.randn(1000) * 0.02)
        var = RiskAssessmentStage._historical_var(returns, 0.95)
        cvar = RiskAssessmentStage._historical_cvar(returns, 0.95)
        assert cvar <= var

    def test_parametic_var(self):
        returns = pd.Series(np.random.randn(1000) * 0.02)
        pvar = RiskAssessmentStage._parametric_var(returns, 0.95)
        assert pvar < 0

    def test_max_drawdown_uptrend(self):
        prices = pd.Series(np.linspace(100, 200, 100) + np.random.randn(100) * 2)
        dd, days = RiskAssessmentStage._max_drawdown(prices)
        assert dd > -0.3  # Limited drawdown in uptrend

    def test_max_drawdown_downtrend(self):
        prices = pd.Series(np.linspace(200, 100, 100) + np.random.randn(100) * 2)
        dd, days = RiskAssessmentStage._max_drawdown(prices)
        assert dd < -0.3  # Significant drawdown in downtrend

    def test_max_drawdown_flat(self):
        prices = pd.Series([100.0] * 50)
        dd, days = RiskAssessmentStage._max_drawdown(prices)
        assert dd == 0.0
        assert days == 0

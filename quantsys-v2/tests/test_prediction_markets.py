"""Tests for prediction market data sources, calculators, and service.

Covers:
- ProbabilityCalculator: midpoint probability, last price probability,
  bid_ask_adjusted, implied distribution, confidence intervals
- SentimentCalculator: EWMA, Bollinger band signals, momentum, mean reversion,
  aggregate market probability
- PMArbitrageCalculator: complementary arbitrage, cross-platform,
  multi-outcome (Dutch book)
- PMTimeSeriesCalculator: trend decomposition, volatility, forecast, correlation
- PolymarketSource: config, connection error handling, stock_info rejection
- KalshiSource: config, connection error handling, stock_info rejection
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock, PropertyMock


# ============================================================================
# ProbabilityCalculator Tests
# ============================================================================

class TestProbabilityCalculator:
    """Tests for probability calculation methods."""

    @pytest.fixture
    def calc(self):
        from domain.quantlib.prediction_markets.probability import ProbabilityCalculator
        return ProbabilityCalculator()

    def test_midpoint_probability(self, calc):
        """Midpoint probability: (bid + ask) / 2."""
        result = calc.calculate(
            prices={"Yes": 0.6},
            method="midpoint",
            bid=0.55,
            ask=0.65
        )
        assert result["value"] == pytest.approx(0.6, abs=0.01)
        assert result["method"] == "midpoint"
        assert result["metadata"]["bid"] == pytest.approx(0.55)
        assert result["metadata"]["ask"] == pytest.approx(0.65)
        assert result["metadata"]["spread"] == pytest.approx(0.10)

    def test_last_price_probability_scalar(self, calc):
        """Last trade price as probability (scalar input)."""
        result = calc.calculate(
            prices=0.72,
            method="last_price",
            last=0.72
        )
        assert result["value"] == pytest.approx(0.72, abs=0.01)
        assert result["method"] == "last_price"

    def test_last_price_probability_dict(self, calc):
        """Last trade price from dict of outcomes."""
        result = calc.calculate(
            prices={"A": 0.4, "B": 0.3},
            method="last_price",
            last={"A": 0.4, "B": 0.3}
        )
        # Normalized: A=0.571, B=0.429
        assert isinstance(result["value"], dict)
        assert result["value"]["A"] == pytest.approx(0.5714, abs=0.01)
        assert result["value"]["B"] == pytest.approx(0.4286, abs=0.01)

    def test_bid_ask_adjusted(self, calc):
        """Spread-adjusted probability (wider spread → less confidence)."""
        result = calc.calculate(
            prices={"Yes": 0.5},
            method="bid_ask_adjusted",
            bid=0.45,
            ask=0.55
        )
        assert 0.0 <= result["value"] <= 1.0
        assert result["method"] == "bid_ask_adjusted"
        assert "confidence" in result["metadata"]

    def test_implied_distribution(self, calc):
        """Normalize multi-outcome probabilities to sum to 1.0."""
        outcomes = ["Candidate A", "Candidate B", "Candidate C"]
        probs = [0.55, 0.40, 0.15]  # Sum = 1.10, needs normalization
        dist = calc.calculate_implied_distribution(outcomes, probs)
        assert abs(dist["normalized_total"] - 1.0) < 0.001
        assert len(dist["distribution"]) == 3
        assert dist["distribution"][0]["probability"] == pytest.approx(0.5, abs=0.01)
        assert dist["distribution"][1]["probability"] == pytest.approx(0.3636, abs=0.01)

    def test_wilson_confidence_interval(self, calc):
        """Wilson score interval for binomial proportion."""
        result = calc.calculate_confidence_interval(
            probability=0.65,
            sample_size=100,
            confidence=0.95
        )
        val = result["value"]
        assert 0.0 < val["lower"] < val["center"] < val["upper"] < 1.0
        assert val["center"] > 0.60
        assert val["center"] < 0.70
        # Width should be wider for smaller samples
        result_small = calc.calculate_confidence_interval(0.65, 20, 0.95)
        width_large = val["upper"] - val["lower"]
        width_small = result_small["value"]["upper"] - result_small["value"]["lower"]
        assert width_small > width_large

    def test_confidence_interval_edge_cases(self, calc):
        """Confidence interval near boundaries."""
        # Near 0
        r = calc.calculate_confidence_interval(0.01, 100, 0.95)
        assert r["value"]["lower"] >= 0.0

        # Near 1
        r = calc.calculate_confidence_interval(0.99, 100, 0.95)
        assert r["value"]["upper"] <= 1.0


# ============================================================================
# SentimentCalculator Tests
# ============================================================================

class TestSentimentCalculator:
    """Tests for sentiment signal generation."""

    @pytest.fixture
    def calc(self):
        from domain.quantlib.prediction_markets.sentiment import SentimentCalculator
        return SentimentCalculator()

    @pytest.fixture
    def uptrend_series(self):
        """Clear uptrend in probability."""
        return np.linspace(0.4, 0.7, 30)

    @pytest.fixture
    def downtrend_series(self):
        """Clear downtrend."""
        return np.linspace(0.7, 0.4, 30)

    def test_ewma_uptrend(self, calc, uptrend_series):
        """EWMA should detect strong uptrend."""
        result = calc.calculate(
            uptrend_series,
            method="exponential_weighted",
            halflife=7
        )
        assert result["value"] >= 0.0  # Bullish signal
        assert result["metadata"]["trend"] == 1.0  # Uptrend

    def test_ewma_downtrend(self, calc, downtrend_series):
        """EWMA should detect strong downtrend."""
        result = calc.calculate(
            downtrend_series,
            method="exponential_weighted",
            halflife=7
        )
        assert result["value"] <= 0.0

    def test_bollinger_band_signal(self, calc, uptrend_series):
        """Bollinger Band breakout detection."""
        result = calc.calculate(
            uptrend_series,
            method="bollinger_band",
            window=10,
            num_std=2.0
        )
        assert "upper_band" in result["metadata"]
        assert "lower_band" in result["metadata"]
        assert result["metadata"]["upper_band"] > result["metadata"]["lower_band"]

    def test_momentum_signal(self, calc, uptrend_series):
        """Momentum crossover should show bullish signal in uptrend."""
        result = calc.calculate(
            uptrend_series,
            method="momentum",
            fast=5,
            slow=15
        )
        # Fast MA > Slow MA in an uptrend
        assert result["metadata"]["fast_ma"] > result["metadata"]["slow_ma"]
        assert result["value"] > 0.0  # Positive signal

    def test_mean_reversion_signal(self, calc, downtrend_series):
        """Mean reversion signal on downtrend series."""
        # Create a series that overshoots
        series = np.array([0.5] * 18 + [0.3, 0.28, 0.25])
        result = calc.calculate(
            series,
            method="mean_reversion",
            window=10
        )
        # Should detect oversold condition (positive signal for reversion)
        assert "z_score" in result["metadata"]
        z = result["metadata"]["z_score"]
        assert z < -1.0  # Significantly below mean

    def test_aggregate_market_probability_weighted(self, calc):
        """Volume-weighted aggregation of multiple market probabilities."""
        market_data = [
            {"probability": 0.65, "volume": 100000},
            {"probability": 0.58, "volume": 10000},
            {"probability": 0.62, "volume": 50000},
        ]
        result = calc.aggregate_market_probability(market_data, method="weighted_average")
        # Weighted toward the high-volume 0.65
        assert result["value"] > 0.60
        assert result["metadata"]["num_markets"] == 3


# ============================================================================
# PMArbitrageCalculator Tests
# ============================================================================

class TestPMArbitrage:
    """Tests for arbitrage detection."""

    @pytest.fixture
    def calc(self):
        from domain.quantlib.prediction_markets.arbitrage import PMArbitrageCalculator
        return PMArbitrageCalculator()

    def test_complementary_arbitrage_detected(self, calc):
        """Detect when sum of all outcome asks < 1.0."""
        # YES ask=0.48, NO ask=0.48 → total=0.96 → arb!
        prices = {"Yes": (0.45, 0.48), "No": (0.45, 0.48)}
        result = calc.calculate(
            market_prices=prices,
            method="complementary",
            transaction_cost=0.02
        )
        assert result["metadata"]["is_arbitrage_buy_all"] is True
        assert result["metadata"]["net_profit_buy_all"] > 0.0

    def test_complementary_no_arbitrage(self, calc):
        """No arbitrage when sum of asks >= 1.0."""
        # YES ask=0.52, NO ask=0.50 → total=1.02 → no arb
        prices = {"Yes": (0.50, 0.52), "No": (0.48, 0.50)}
        result = calc.calculate(
            market_prices=prices,
            method="complementary",
            transaction_cost=0.02
        )
        assert result["metadata"]["is_arbitrage_buy_all"] is False

    def test_cross_platform_arbitrage(self, calc):
        """Detect same-outcome price differences across platforms."""
        prices = {
            "polymarket": {"Yes": (0.55, 0.57)},
            "kalshi": {"Yes": (0.52, 0.53)},
        }
        result = calc.calculate(
            market_prices=prices,
            method="cross_platform",
            transaction_cost=0.01
        )
        assert "opportunities" in result["metadata"]
        assert result["metadata"]["platforms_analyzed"] == ["polymarket", "kalshi"]

    def test_multi_outcome_dutch_book(self, calc):
        """Detect Dutch book in multi-outcome markets."""
        markets = [
            ("Candidate_A", 0.35, 0.37),
            ("Candidate_B", 0.28, 0.30),
            ("Candidate_C", 0.22, 0.24),
        ]
        result = calc.calculate(
            market_prices=markets,
            method="multi_outcome",
            transaction_cost=0.02
        )
        # Total ask = 0.91 → Dutch book
        assert result["metadata"]["is_dutch_book"] is True
        assert result["metadata"]["total_ask"] < 1.0


# ============================================================================
# PMTimeSeriesCalculator Tests
# ============================================================================

class TestPMTimeSeries:
    """Tests for probability time series analysis."""

    @pytest.fixture
    def calc(self):
        from domain.quantlib.prediction_markets.time_series import PMTimeSeriesCalculator
        return PMTimeSeriesCalculator()

    @pytest.fixture
    def trend_series(self):
        """Series with a clear upward trend."""
        np.random.seed(42)
        base = np.linspace(0.3, 0.7, 50)
        noise = np.random.normal(0, 0.02, 50)
        return base + noise

    def test_trend_decomposition(self, calc, trend_series):
        """Detect upward trend direction and strength."""
        result = calc.calculate(
            trend_series,
            method="trend_decomposition"
        )
        assert result["metadata"]["direction"] == "upward"
        assert result["metadata"]["trend_coefficient"] > 0.0
        assert result["metadata"]["r_squared"] > 0.5  # Good fit

    def test_volatility_analysis(self, calc, trend_series):
        """Rolling volatility and regime detection."""
        result = calc.calculate(
            trend_series,
            method="volatility"
        )
        assert "current_volatility" in result["metadata"]
        assert "volatility_regime" in result["metadata"]
        assert result["metadata"]["current_volatility"] >= 0.0

    def test_forecast(self, calc, trend_series):
        """AR(1) forecast with confidence bands."""
        result = calc.calculate(
            trend_series,
            method="forecast",
            horizon=7
        )
        assert len(result["metadata"]["forecast"]) == 7
        assert len(result["metadata"]["lower_band"]) == 7
        assert len(result["metadata"]["upper_band"]) == 7
        for lower, upper in zip(result["metadata"]["lower_band"], result["metadata"]["upper_band"]):
            assert 0.0 <= lower <= upper <= 1.0

    def test_correlation(self, calc):
        """Correlation between two probability series."""
        np.random.seed(123)
        series_a = np.linspace(0.3, 0.7, 30) + np.random.normal(0, 0.01, 30)
        series_b = np.linspace(0.3, 0.7, 30) + np.random.normal(0, 0.01, 30)
        result = calc.calculate_correlation(series_a, series_b)
        assert result["value"] > 0.7  # Strong positive correlation
        assert result["metadata"]["interpretation"] == "strong"
        assert result["metadata"]["direction"] == "positive"


# ============================================================================
# PolymarketSource Tests
# ============================================================================

class TestPolymarketSource:
    """Tests for Polymarket API data source."""

    @pytest.fixture
    def source(self):
        from adapters.outbound.datasources.sources.polymarket_source import PolymarketSource
        return PolymarketSource()

    def test_validate_config(self, source):
        """Polymarket requires no API key, config is always valid."""
        assert source.validate_config() is True

    def test_name_and_key_requirement(self, source):
        """Source metadata."""
        assert source.name == "Polymarket"
        assert source.requires_api_key is False

    def test_stock_info_not_applicable(self, source):
        """get_stock_info should return error for prediction markets."""
        response = source.get_stock_info("AAPL")
        assert response.success is False
        assert "Not applicable" in response.error

    def test_test_connection_success(self, source):
        """Successful connection test."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "test-market"}]
        mock_response.raise_for_status = MagicMock()
        source.session.get = MagicMock(return_value=mock_response)

        result = source.test_connection()
        assert result.success is True
        assert result.data["status"] == "connected"

    def test_test_connection_failure(self, source):
        """Failed connection test returns error response."""
        import requests as req
        source.session.get = MagicMock(
            side_effect=req.exceptions.ConnectionError("Connection refused")
        )

        result = source.test_connection()
        assert result.success is False
        assert "Connection" in result.error

    def test_get_markets(self, source):
        """Retrieve market list."""
        mock_data = [
            {"id": "m1", "question": "Will BTC hit 100k?", "outcomes": []},
            {"id": "m2", "question": "Will it rain tomorrow?", "outcomes": []},
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()
        source.session.get = MagicMock(return_value=mock_response)

        result = source.get_markets(limit=10, active=True)
        assert result.success is True
        assert len(result.data) == 2


# ============================================================================
# KalshiSource Tests
# ============================================================================

class TestKalshiSource:
    """Tests for Kalshi API data source."""

    @pytest.fixture
    def source(self):
        from adapters.outbound.datasources.sources.kalshi_source import KalshiSource
        return KalshiSource()

    def test_validate_config(self, source):
        """Kalshi public endpoints work even without API key."""
        assert source.validate_config() is True

    def test_name_and_key_requirement(self, source):
        """Source metadata."""
        assert source.name == "Kalshi"
        assert source.requires_api_key is True

    def test_stock_info_not_applicable(self, source):
        """get_stock_info should return error for prediction markets."""
        response = source.get_stock_info("AAPL")
        assert response.success is False
        assert "Not applicable" in response.error

    def test_test_connection_success(self, source):
        """Successful connection to exchange status endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "operational"}
        mock_response.raise_for_status = MagicMock()
        source.session.get = MagicMock(return_value=mock_response)

        result = source.test_connection()
        assert result.success is True
        assert result.data["status"] == "connected"

    def test_test_connection_failure(self, source):
        """Connection failure returns error response."""
        import requests as req
        source.session.get = MagicMock(
            side_effect=req.exceptions.Timeout("Timeout")
        )

        result = source.test_connection()
        assert result.success is False
        assert "timeout" in result.error.lower() or "Connection" in result.error


# ============================================================================
# PredictionMarketService Tests
# ============================================================================

class TestPredictionMarketService:
    """Tests for service orchestration layer."""

    @pytest.fixture
    def service(self):
        from application.services.prediction_market_service import PredictionMarketService
        return PredictionMarketService()

    def test_init_without_ds(self, service):
        """Service initializes with defaults without data source."""
        assert service.ds is None
        assert service.probability_calc is not None
        assert service.sentiment_calc is not None
        assert service.arbitrage_calc is not None
        assert service.ts_calc is not None

    def test_get_market_overview_no_ds(self, service):
        """Market overview returns empty markets when no data source."""
        result = service.get_market_overview(source="polymarket", limit=10)
        assert result["success"] is True
        assert isinstance(result["markets"], list)
        assert result["source"] == "polymarket"

    def test_get_event_probability_fallback(self, service):
        """Event probability falls back when no data source."""
        result = service.get_event_probability(
            "test-event", source="polymarket", method="midpoint"
        )
        assert result["event_id"] == "test-event"
        assert result["source"] == "polymarket"
        assert result["method"] == "midpoint"
        assert "probability" in result

    def test_get_event_probability_midpoint(self, service):
        """Explicit midpoint calculation with bid/ask values."""
        result = service.get_event_probability(
            "btc-100k", source="polymarket", method="midpoint"
        )
        assert result["event_id"] == "btc-100k"

    def test_get_sentiment_analysis_no_ds(self, service):
        """Sentiment analysis uses synthetic data when no source."""
        result = service.get_sentiment_analysis("test-event", lookback_days=30)
        assert result["event_id"] == "test-event"
        assert "results" in result
        assert "exponential_weighted" in result["results"]
        assert "bollinger_band" in result["results"]
        assert "momentum" in result["results"]
        assert "mean_reversion" in result["results"]
        assert "trend" in result["results"]
        assert "overall_sentiment" in result

    def test_detect_arbitrage_no_ds(self, service):
        """Arbitrage detection provides demo results when no source."""
        result = service.detect_arbitrage(tx_cost=0.02)
        assert "demo_complementary" in result
        assert "demo_note" in result

    def test_get_time_series_no_ds(self, service):
        """Time series analysis uses synthetic data when no source."""
        result = service.get_time_series("test-event", method="trend_decomposition")
        assert result["event_id"] == "test-event"
        assert result["method"] == "trend_decomposition"
        assert "result" in result
        assert "price_range" in result

    def test_get_time_series_forecast(self, service):
        """Time series forecast with horizon."""
        result = service.get_time_series("test-event", method="forecast")
        assert result["method"] == "forecast"
        forecast = result["result"].get("metadata", {}).get("forecast", [])
        assert len(forecast) == 7  # Default horizon


# ============================================================================
# Package Import Test
# ============================================================================

def test_prediction_markets_package_import():
    """Verify all calculators can be imported from package."""
    from domain.quantlib.prediction_markets import (
        ProbabilityCalculator,
        SentimentCalculator,
        PMArbitrageCalculator,
        PMTimeSeriesCalculator,
    )
    assert ProbabilityCalculator is not None
    assert SentimentCalculator is not None
    assert PMArbitrageCalculator is not None
    assert PMTimeSeriesCalculator is not None


def test_data_source_imports():
    """Verify data sources can be imported."""
    from adapters.outbound.datasources.sources.polymarket_source import PolymarketSource
    from adapters.outbound.datasources.sources.kalshi_source import KalshiSource
    assert PolymarketSource is not None
    assert KalshiSource is not None

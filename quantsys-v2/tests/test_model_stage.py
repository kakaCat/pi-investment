"""
ModelStage unit tests
"""
import pytest
import numpy as np
import pandas as pd
from domain.quantlib.stages.model_stage import (
    ModelStage, FEATURE_NAMES, DEFAULT_MODEL_PATH
)


def make_klines(n: int = 60) -> list:
    """Generate synthetic klines for testing."""
    np.random.seed(42)
    base = 100.0
    klines = []
    for i in range(n):
        change = np.random.randn() * 2
        close = base + change
        high = close + abs(np.random.randn())
        low = close - abs(np.random.randn())
        open_p = low + np.random.random() * (high - low)
        volume = np.random.randint(10000, 1000000)
        amount = close * volume
        klines.append({
            "date": f"2024-{(i // 20) + 1:02d}-{(i % 20) + 1:02d}",
            "open": round(open_p, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": volume,
            "amount": round(amount, 2),
        })
        base = close
    return klines


def make_factors() -> dict:
    return {
        "ma5": 98.5, "ma10": 97.2, "ma20": 95.8,
        "rsi": 55.0, "macd": 1.2, "macd_signal": 0.8,
        "macd_hist": 0.4, "boll_upper": 105.0,
        "boll_middle": 100.0, "boll_lower": 95.0,
        "atr": 2.5, "volume_ma5": 500000, "volume_ratio": 1.2,
    }


class TestModelStageValidation:
    def test_missing_symbol(self):
        stage = ModelStage()
        with pytest.raises(ValueError, match="symbol"):
            stage.validate_input({"factors": {}, "klines": [{}]})

    def test_missing_factors(self):
        stage = ModelStage()
        with pytest.raises(ValueError, match="factors"):
            stage.validate_input({"symbol": "TEST", "klines": [{}]})

    def test_missing_klines(self):
        stage = ModelStage()
        with pytest.raises(ValueError, match="klines"):
            stage.validate_input({"symbol": "TEST", "factors": {}})

    def test_empty_klines(self):
        stage = ModelStage()
        with pytest.raises(ValueError, match="non-empty"):
            stage.validate_input({"symbol": "TEST", "factors": {}, "klines": []})

    def test_valid_input(self):
        stage = ModelStage()
        assert stage.validate_input({
            "symbol": "TEST", "factors": {}, "klines": make_klines()
        }) is True


class TestModelStagePrediction:
    def test_graceful_degradation_when_no_model(self):
        """Without a real model file, should return hold with model=none."""
        stage = ModelStage(model_path="/nonexistent/path/model.pkl")
        result = stage.process({
            "symbol": "000001.SZ",
            "factors": make_factors(),
            "klines": make_klines(60),
        })

        assert "prediction" in result
        pred = result["prediction"]
        assert pred["action"] == "hold"
        assert pred["model"] == "none"
        assert "message" in pred

    def test_preserves_input_data(self):
        stage = ModelStage(model_path="/nonexistent/path/model.pkl")
        data = {
            "symbol": "000001.SZ",
            "factors": make_factors(),
            "klines": make_klines(60),
            "extra_field": "keep_me",
        }
        result = stage.process(data)
        assert result["symbol"] == "000001.SZ"
        assert result["factors"] == data["factors"]
        assert result["klines"] == data["klines"]
        assert result["extra_field"] == "keep_me"

    def test_custom_threshold(self):
        stage = ModelStage(
            model_path="/nonexistent/path/model.pkl",
            confidence_threshold=0.7,
        )
        assert stage.confidence_threshold == 0.7

    def test_model_load_failure_handled(self):
        stage = ModelStage(model_path="/tmp/__nonexistent_model__.pkl")
        stage._load_model()
        assert stage._model is None
        assert stage._model_loaded is True

    def test_stage_name_default(self):
        stage = ModelStage()
        assert stage.name == "prediction"

    def test_stage_name_custom(self):
        stage = ModelStage(name="ml_predict")
        assert stage.name == "ml_predict"


class TestFeatureEngineering:
    def test_feature_vector_shape(self):
        klines = make_klines(60)
        factors = make_factors()
        stage = ModelStage(model_path="/nonexistent/path/model.pkl")
        vec = stage._build_feature_vector(factors, klines)
        assert vec.shape == (1, 38)
        assert vec.dtype == np.float64

    def test_feature_vector_no_nan(self):
        klines = make_klines(60)
        factors = make_factors()
        stage = ModelStage(model_path="/nonexistent/path/model.pkl")
        vec = stage._build_feature_vector(factors, klines)
        assert not np.any(np.isnan(vec))
        assert not np.any(np.isinf(vec))

    def test_all_feature_names_present(self):
        assert len(FEATURE_NAMES) == 38

    def test_insufficient_data_uses_mean(self):
        """With < period data, should use mean instead of NaN."""
        klines = make_klines(5)
        factors = make_factors()
        stage = ModelStage(model_path="/nonexistent/path/model.pkl")
        vec = stage._build_feature_vector(factors, klines)
        assert not np.any(np.isnan(vec))

    def test_missing_columns_raises(self):
        stage = ModelStage(model_path="/nonexistent/path/model.pkl")
        with pytest.raises(ValueError, match="Missing required column"):
            stage._build_feature_vector(make_factors(), [{"date": "2024-01-01"}])


class TestHelperMethods:
    def test_calc_sma(self):
        s = pd.Series([10, 20, 30, 40, 50])
        result = ModelStage._calc_sma(s, 3)
        assert result == 40.0

    def test_calc_ema(self):
        s = pd.Series([10, 20, 30, 40, 50])
        result = ModelStage._calc_ema(s, 3)
        assert result > 0

    def test_calc_momentum(self):
        s = pd.Series([10, 20, 30])
        result = ModelStage._calc_momentum(s, 2)
        assert result == 10.0

    def test_calc_roc(self):
        s = pd.Series([100, 110])
        result = ModelStage._calc_roc(s, 1)
        assert result == pytest.approx(10.0, 0.1)

    def test_calc_rsi_n(self):
        np.random.seed(42)
        s = pd.Series(np.random.randn(30).cumsum() + 100)
        result = ModelStage._calc_rsi_n(s, 14)
        assert 0 <= result <= 100

    def test_calc_williams_r(self):
        klines = make_klines(20)
        df = pd.DataFrame(klines)
        result = ModelStage._calc_williams_r(df, 10)
        assert -100 <= result <= 0

    def test_calc_sma_short_series(self):
        s = pd.Series([10, 20])
        result = ModelStage._calc_sma(s, 10)
        assert result == 15.0  # mean

    def test_calc_momentum_short_series(self):
        s = pd.Series([10])
        result = ModelStage._calc_momentum(s, 2)
        assert result == 0.0

    def test_calc_roc_zero_division(self):
        s = pd.Series([0, 10])
        result = ModelStage._calc_roc(s, 1)
        assert result == 0.0

    def test_calc_rsi_all_gains(self):
        s = pd.Series(range(1, 30))
        result = ModelStage._calc_rsi_n(s, 14)
        assert result == 100.0  # all gains → RSI=100

    def test_calc_williams_r_flat(self):
        df = pd.DataFrame({"high": [10]*10, "low": [10]*10, "close": [10]*10})
        result = ModelStage._calc_williams_r(df, 5)
        assert result == 0.0

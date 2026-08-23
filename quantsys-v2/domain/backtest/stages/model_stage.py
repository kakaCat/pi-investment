"""
Model Prediction Stage

Loads trained XGBoost model and predicts signal confidence from factors.
Graceful degradation when model is unavailable.
"""
import os
import pickle
import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from infrastructure.quantlib.core.pipeline import PipelineStage

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = ".pi-invest/ml/models/xgboost_latest.pkl"

FEATURE_NAMES = [
    "open", "high", "low", "close", "volume", "amount", "turnover_rate",
    "ATR14", "BOLL_bb_lower", "BOLL_bb_middle", "BOLL_bb_percent",
    "BOLL_bb_upper", "BOLL_bb_width", "CCI14", "EMA12", "EMA26",
    "EMV14", "KDJ_d", "KDJ_j", "KDJ_k", "MA10", "MA20", "MA5", "MA60",
    "MACD_macd_dea", "MACD_macd_dif", "MACD_macd_histogram",
    "MFI14", "MOM12", "MOM6", "OBV", "ROC12", "RSI12", "RSI24", "RSI6",
    "VR", "WR10", "WR6"
]


class ModelStage(PipelineStage):
    """
    Model prediction stage.

    Input:
    - symbol: stock code
    - factors: calculated factor values (dict)
    - klines: K-line data (list of dict), used for raw price features

    Output:
    - prediction: {confidence, action, model_info}
    """

    def __init__(
        self,
        name: str = "prediction",
        model_path: str = None,
        confidence_threshold: float = 0.5
    ):
        super().__init__(name)
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._model_loaded = False

    def validate_input(self, data: Dict[str, Any]) -> bool:
        if "symbol" not in data:
            raise ValueError("Missing required field: symbol")
        if "factors" not in data:
            raise ValueError("Missing required field: factors")
        if "klines" not in data:
            raise ValueError("Missing required field: klines")
        if not isinstance(data["klines"], list) or len(data["klines"]) == 0:
            raise ValueError("klines must be a non-empty list")
        return True

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        symbol = data["symbol"]
        factors = data["factors"]
        klines = data["klines"]

        logger.info(f"Predicting signal confidence for {symbol}")

        prediction = self._predict(factors, klines)

        result = data.copy()
        result["prediction"] = prediction

        conf = prediction['confidence']
        conf_str = f"{conf:.3f}" if conf is not None else "N/A"
        logger.info(
            f"Prediction for {symbol}: confidence={conf_str}, "
            f"action={prediction['action']}"
        )
        return result

    def _predict(self, factors: Dict[str, float], klines: List[Dict]) -> Dict:
        if not self._model_loaded:
            self._load_model()

        if self._model is None:
            return {
                "confidence": None,
                "action": "hold",
                "model": "none",
                "message": "Model not available"
            }

        try:
            features = self._build_feature_vector(factors, klines)
            proba = self._model.predict_proba(features)[0]
            confidence = float(proba[1]) if len(proba) > 1 else float(proba[0])

            action = "buy" if confidence >= self.confidence_threshold else "sell"

            return {
                "confidence": confidence,
                "action": action,
                "model": "xgboost",
                "threshold": self.confidence_threshold
            }
        except Exception as e:
            logger.error(f"Prediction failed for: {e}")
            return {
                "confidence": None,
                "action": "hold",
                "model": "xgboost",
                "error": str(e)
            }

    def _load_model(self):
        self._model_loaded = True
        resolved = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            self.model_path
        )
        if os.path.exists(self.model_path):
            resolved = self.model_path
        elif not os.path.exists(resolved):
            logger.warning(f"Model file not found: {resolved}")
            return

        try:
            with open(resolved, 'rb') as f:
                self._model = pickle.load(f)
            logger.info(f"Model loaded from {resolved}")
        except Exception as e:
            logger.warning(f"Failed to load model: {e}")
            self._model = None

    def _build_feature_vector(
        self,
        factors: Dict[str, float],
        klines: List[Dict]
    ) -> np.ndarray:
        df = pd.DataFrame(klines)

        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        feature_map = {
            "open": latest.get("open", 0),
            "high": latest.get("high", 0),
            "low": latest.get("low", 0),
            "close": latest.get("close", 0),
            "volume": latest.get("volume", 0),
            "amount": latest.get("amount", latest.get("close", 0) * latest.get("volume", 0)),
            "turnover_rate": latest.get("turnover_rate", 0),
            "ATR14": factors.get("atr", 0),
            "BOLL_bb_lower": factors.get("boll_lower", 0),
            "BOLL_bb_middle": factors.get("boll_middle", 0),
            "BOLL_bb_width": (factors.get("boll_upper", 0) - factors.get("boll_lower", 0)),
            "BOLL_bb_upper": factors.get("boll_upper", 0),
            "BOLL_bb_percent": (
                (latest.get("close", 0) - factors.get("boll_lower", 0)) /
                (factors.get("boll_upper", 0) - factors.get("boll_lower", 0) + 1e-10)
            ),
            "CCI14": 0.0,
            "EMA12": self._calc_ema(df["close"], 12) or 0.0,
            "EMA26": self._calc_ema(df["close"], 26) or 0.0,
            "EMV14": 0.0,
            "KDJ_d": 0.0, "KDJ_j": 0.0, "KDJ_k": 0.0,
            "MA10": factors.get("ma10", 0),
            "MA20": factors.get("ma20", 0),
            "MA5": factors.get("ma5", 0),
            "MA60": self._calc_sma(df["close"], 60),
            "MACD_macd_dea": factors.get("macd_signal", 0),
            "MACD_macd_dif": factors.get("macd", 0),
            "MACD_macd_histogram": factors.get("macd_hist", 0),
            "MFI14": 0.0,
            "MOM12": self._calc_momentum(df["close"], 12),
            "MOM6": self._calc_momentum(df["close"], 6),
            "OBV": 0.0,
            "ROC12": self._calc_roc(df["close"], 12),
            "RSI12": self._calc_rsi_n(df["close"], 12),
            "RSI24": self._calc_rsi_n(df["close"], 24),
            "RSI6": factors.get("rsi", 0),
            "VR": 0.0,
            "WR10": self._calc_williams_r(df, 10),
            "WR6": self._calc_williams_r(df, 6),
        }

        values = [feature_map.get(name, 0.0) for name in FEATURE_NAMES]
        return np.array(values, dtype=np.float64).reshape(1, -1)

    @staticmethod
    def _calc_sma(series: pd.Series, period: int) -> float:
        if len(series) < period:
            return float(series.mean()) if len(series) > 0 else 0.0
        return float(series.rolling(window=period).mean().iloc[-1])

    @staticmethod
    def _calc_ema(series: pd.Series, period: int) -> float:
        if len(series) < period:
            return float(series.mean()) if len(series) > 0 else 0.0
        return float(series.ewm(span=period, adjust=False).mean().iloc[-1])

    @staticmethod
    def _calc_momentum(series: pd.Series, period: int) -> float:
        if len(series) < period:
            return 0.0
        return float(series.iloc[-1] - series.iloc[-period])

    @staticmethod
    def _calc_roc(series: pd.Series, period: int) -> float:
        if len(series) <= period or series.iloc[-period - 1] == 0:
            return 0.0
        return float((series.iloc[-1] - series.iloc[-period - 1]) / series.iloc[-period - 1] * 100)

    @staticmethod
    def _calc_rsi_n(series: pd.Series, period: int) -> float:
        if len(series) < period + 1:
            return 50.0
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        if loss.iloc[-1] == 0:
            return 100.0
        rs = gain.iloc[-1] / loss.iloc[-1]
        return float(100 - (100 / (1 + rs)))

    @staticmethod
    def _calc_williams_r(df: pd.DataFrame, period: int) -> float:
        if len(df) < period:
            return 0.0
        high_n = df["high"].rolling(window=period).max().iloc[-1]
        low_n = df["low"].rolling(window=period).min().iloc[-1]
        close = df["close"].iloc[-1]
        if high_n == low_n:
            return 0.0
        return float((high_n - close) / (high_n - low_n) * -100)

"""
Machine Learning Integration Module
====================================

AI-driven quantitative strategy tools for QuantSys V2.

Modules:
    - feature_engineering: Automatic feature generation and selection
    - factor_mining: Factor discovery with genetic algorithms and ML selection
    - return_prediction: Multi-model return prediction (XGBoost, LightGBM, LSTM, Ensemble)
    - risk_prediction: Volatility, correlation, and tail risk prediction (GARCH+ML)
    - anomaly_detection: Market/trade/data-quality anomaly detection
    - lstm_predictor: PyTorch LSTM-based prediction (from quant)
    - transformer_predictor: PyTorch Transformer-based prediction (from quant)
    - mlflow_manager: MLflow experiment tracking (from quant)

Usage:
    from qs_quantlib.ml import FeatureEngineeringCalculator
    from qs_quantlib.ml import FactorMiningCalculator
    from qs_quantlib.ml import ReturnPredictionCalculator
    from qs_quantlib.ml import RiskPredictionCalculator
    from qs_quantlib.ml import AnomalyDetectionCalculator
    from qs_quantlib.ml import LSTMPredictor
    from qs_quantlib.ml import TransformerPredictor
    from qs_quantlib.ml import MLflowManager
"""
from .feature_engineering import FeatureEngineeringCalculator
from .factor_mining import FactorMiningCalculator
from .return_prediction import ReturnPredictionCalculator
from .risk_prediction import RiskPredictionCalculator
from .anomaly_detection import AnomalyDetectionCalculator
from .lstm_predictor import LSTMPredictor
from .transformer_predictor import TransformerPredictor
from .mlflow_manager import MLflowManager

__all__ = [
    'FeatureEngineeringCalculator',
    'FactorMiningCalculator',
    'ReturnPredictionCalculator',
    'RiskPredictionCalculator',
    'AnomalyDetectionCalculator',
    'LSTMPredictor',
    'TransformerPredictor',
    'MLflowManager',
]

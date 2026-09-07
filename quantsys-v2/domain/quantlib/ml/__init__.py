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
    from domain.quantlib.ml import FeatureEngineeringCalculator
    from domain.quantlib.ml import FactorMiningCalculator
    from domain.quantlib.ml import ReturnPredictionCalculator
    from domain.quantlib.ml import RiskPredictionCalculator
    from domain.quantlib.ml import AnomalyDetectionCalculator
    from domain.quantlib.ml import LSTMPredictor
    from domain.quantlib.ml import TransformerPredictor
    from domain.quantlib.ml import MLflowManager
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

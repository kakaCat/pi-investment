"""
Advanced feature engineering for stock prediction.

Generates 50+ features from price, volume, and technical indicators.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Feature engineering pipeline for stock signals.

    Generates comprehensive features including:
    - Price-based features (returns, volatility)
    - Technical indicators (RSI, MACD, Bollinger)
    - Statistical features (skewness, kurtosis)
    - Time-based features (day of week, month)
    - Cross features (interaction terms)
    """

    def __init__(self):
        self.feature_names = []

    def extract_features(self, signal: dict, historical_data: Optional[pd.DataFrame] = None) -> dict:
        """
        Extract comprehensive features from a signal.

        Args:
            signal: Signal dictionary with indicators
            historical_data: Optional DataFrame with historical price data for advanced features

        Returns:
            Dictionary of features
        """
        features = {}

        # 1. Basic indicator features (8 features)
        features.update(self._extract_basic_features(signal))

        # 2. Price return features (6 features)
        features.update(self._extract_return_features(signal))

        # 3. Volatility features (4 features)
        features.update(self._extract_volatility_features(signal))

        # 4. Technical indicator features (12 features)
        features.update(self._extract_technical_features(signal))

        # 5. Volume features (4 features)
        features.update(self._extract_volume_features(signal))

        # 6. Time-based features (6 features)
        features.update(self._extract_time_features(signal))

        # 7. Statistical features (6 features)
        if historical_data is not None:
            features.update(self._extract_statistical_features(historical_data))

        # 8. Cross features (10 features)
        features.update(self._extract_cross_features(features))

        # Store feature names for later use
        self.feature_names = sorted(features.keys())

        return features

    def _extract_basic_features(self, signal: dict) -> dict:
        """Extract basic features from signal indicators."""
        indicators = signal.get('indicators', {})

        return {
            'rsi': indicators.get('rsi', 50),
            'macd_histogram': indicators.get('macd_histogram', 0),
            'volume_ratio': indicators.get('volume_ratio', 1),
            'close_price': indicators.get('close', signal.get('price', 0)),
            'ma5': indicators.get('ma5', 0),
            'ma20': indicators.get('ma20', 0),
            'ma60': indicators.get('ma60', 0),
            'action_encoded': 0 if signal.get('action') == 'buy' else 1
        }

    def _extract_return_features(self, signal: dict) -> dict:
        """Extract price return features."""
        indicators = signal.get('indicators', {})
        close = indicators.get('close', 0)

        # Calculate returns from moving averages as proxies
        ma5 = indicators.get('ma5', close)
        ma20 = indicators.get('ma20', close)
        ma60 = indicators.get('ma60', close)

        return {
            'return_1d': (close - ma5) / ma5 if ma5 > 0 else 0,
            'return_5d': (close - ma20) / ma20 if ma20 > 0 else 0,
            'return_20d': (close - ma60) / ma60 if ma60 > 0 else 0,
            'return_ma5_ma20': (ma5 - ma20) / ma20 if ma20 > 0 else 0,
            'return_ma20_ma60': (ma20 - ma60) / ma60 if ma60 > 0 else 0,
            'return_ma5_ma60': (ma5 - ma60) / ma60 if ma60 > 0 else 0
        }

    def _extract_volatility_features(self, signal: dict) -> dict:
        """Extract volatility features."""
        indicators = signal.get('indicators', {})

        bb_upper = indicators.get('bollinger_upper', 0)
        bb_lower = indicators.get('bollinger_lower', 0)
        bb_middle = indicators.get('bollinger_middle', indicators.get('ma20', 0))
        close = indicators.get('close', 0)

        # Bollinger Band width as volatility proxy
        bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
        bb_position = (close - bb_lower) / (bb_upper - bb_lower) if bb_upper > bb_lower else 0.5

        # Distance from bands
        distance_to_upper = (bb_upper - close) / close if close > 0 else 0
        distance_to_lower = (close - bb_lower) / close if close > 0 else 0

        return {
            'bb_width': bb_width,
            'bb_position': bb_position,
            'distance_to_upper_band': distance_to_upper,
            'distance_to_lower_band': distance_to_lower
        }

    def _extract_technical_features(self, signal: dict) -> dict:
        """Extract technical indicator features."""
        indicators = signal.get('indicators', {})

        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)
        macd_hist = indicators.get('macd_histogram', 0)

        return {
            'rsi_overbought': 1 if rsi > 70 else 0,
            'rsi_oversold': 1 if rsi < 30 else 0,
            'rsi_neutral': 1 if 40 <= rsi <= 60 else 0,
            'rsi_distance_50': abs(rsi - 50),
            'macd': macd,
            'macd_signal': macd_signal,
            'macd_cross': 1 if macd > macd_signal else 0,
            'macd_hist_positive': 1 if macd_hist > 0 else 0,
            'macd_hist_abs': abs(macd_hist),
            'macd_divergence': abs(macd - macd_signal),
            'trend_strength': abs(macd_hist) * (1 if macd > macd_signal else -1),
            'momentum': rsi / 100 * macd_hist
        }

    def _extract_volume_features(self, signal: dict) -> dict:
        """Extract volume-based features."""
        indicators = signal.get('indicators', {})

        volume_ratio = indicators.get('volume_ratio', 1)

        return {
            'volume_ratio': volume_ratio,
            'volume_surge': 1 if volume_ratio > 2 else 0,
            'volume_low': 1 if volume_ratio < 0.5 else 0,
            'volume_log': np.log1p(volume_ratio)
        }

    def _extract_time_features(self, signal: dict) -> dict:
        """Extract time-based features."""
        date_str = signal.get('date', datetime.now().strftime('%Y-%m-%d'))

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
        except:
            date = datetime.now()

        return {
            'day_of_week': date.weekday(),
            'is_monday': 1 if date.weekday() == 0 else 0,
            'is_friday': 1 if date.weekday() == 4 else 0,
            'month': date.month,
            'is_quarter_end': 1 if date.month in [3, 6, 9, 12] else 0,
            'is_year_end': 1 if date.month == 12 else 0
        }

    def _extract_statistical_features(self, df: pd.DataFrame) -> dict:
        """Extract statistical features from historical data."""
        if df is None or len(df) < 20:
            return {
                'price_skewness': 0,
                'price_kurtosis': 0,
                'return_skewness': 0,
                'return_kurtosis': 0,
                'price_percentile': 0.5,
                'volume_percentile': 0.5
            }

        # Calculate returns
        returns = df['close'].pct_change().dropna()

        return {
            'price_skewness': float(df['close'].skew()) if len(df) > 2 else 0,
            'price_kurtosis': float(df['close'].kurtosis()) if len(df) > 3 else 0,
            'return_skewness': float(returns.skew()) if len(returns) > 2 else 0,
            'return_kurtosis': float(returns.kurtosis()) if len(returns) > 3 else 0,
            'price_percentile': float(df['close'].iloc[-1] / df['close'].max()) if len(df) > 0 else 0.5,
            'volume_percentile': float(df['volume'].iloc[-1] / df['volume'].max()) if len(df) > 0 and 'volume' in df else 0.5
        }

    def _extract_cross_features(self, features: dict) -> dict:
        """Extract interaction/cross features."""
        cross_features = {}

        # RSI * MA ratio
        if 'rsi' in features and 'return_ma5_ma20' in features:
            cross_features['rsi_x_ma_ratio'] = features['rsi'] / 100 * features['return_ma5_ma20']

        # Volume * Momentum
        if 'volume_ratio' in features and 'momentum' in features:
            cross_features['volume_x_momentum'] = features['volume_ratio'] * features['momentum']

        # BB position * RSI
        if 'bb_position' in features and 'rsi' in features:
            cross_features['bb_x_rsi'] = features['bb_position'] * features['rsi'] / 100

        # MACD * Volume
        if 'macd_histogram' in features and 'volume_ratio' in features:
            cross_features['macd_x_volume'] = features['macd_histogram'] * features['volume_ratio']

        # Trend strength * Volume
        if 'trend_strength' in features and 'volume_ratio' in features:
            cross_features['trend_x_volume'] = features['trend_strength'] * features['volume_ratio']

        # RSI deviation * Volatility
        if 'rsi_distance_50' in features and 'bb_width' in features:
            cross_features['rsi_dev_x_volatility'] = features['rsi_distance_50'] * features['bb_width']

        # Price momentum * Time
        if 'return_5d' in features and 'day_of_week' in features:
            cross_features['return_x_weekday'] = features['return_5d'] * features['day_of_week']

        # Bollinger squeeze indicator
        if 'bb_width' in features and 'volume_ratio' in features:
            cross_features['bb_squeeze'] = (1 / (features['bb_width'] + 0.01)) * features['volume_ratio']

        # Overbought/oversold with volume
        if 'rsi' in features and 'volume_ratio' in features:
            rsi = features['rsi']
            vol = features['volume_ratio']
            cross_features['extreme_rsi_volume'] = (1 if rsi > 70 or rsi < 30 else 0) * vol

        # MA alignment score
        if all(k in features for k in ['return_ma5_ma20', 'return_ma20_ma60']):
            ma5_20 = features['return_ma5_ma20']
            ma20_60 = features['return_ma20_ma60']
            cross_features['ma_alignment'] = 1 if (ma5_20 > 0 and ma20_60 > 0) else (-1 if (ma5_20 < 0 and ma20_60 < 0) else 0)

        return cross_features

    def features_to_array(self, features: dict) -> np.ndarray:
        """Convert feature dictionary to ordered array."""
        if not self.feature_names:
            self.feature_names = sorted(features.keys())

        return np.array([features.get(name, 0) for name in self.feature_names])

    def get_feature_names(self) -> List[str]:
        """Get ordered list of feature names."""
        return self.feature_names

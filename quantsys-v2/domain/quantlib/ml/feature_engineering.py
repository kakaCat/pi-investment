"""
Feature Engineering Calculator
==============================

Automatic feature generation for quantitative machine learning.

Features:
    - Technical indicators (RSI, MACD, Bollinger Bands, etc.)
    - Statistical features (rolling moments, skewness, kurtosis)
    - Time-based features (lagged values, differences, returns)
    - Cross-feature interactions
    - Feature importance ranking

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Union, List, Tuple, Set
from itertools import combinations

from domain.quantlib import BaseCalculator, validate_inputs, timing_decorator
from domain.quantlib.exceptions import (
    DataValidationError,
    InsufficientDataError,
    CalculationError,
    ConfigurationError
)


class FeatureEngineeringCalculator(BaseCalculator):
    """
    Automatic feature generation for quantitative ML models.

    Generates a comprehensive set of technical, statistical, time-based,
    and cross features from raw price/volume data.

    Example:
        calc = FeatureEngineeringCalculator()
        result = calc.calculate(
            data=price_df,
            feature_types=['technical', 'statistical', 'time'],
            window_sizes=[5, 10, 20]
        )
        features = result['features']
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)
        self._feature_functions = {
            'technical': self._generate_technical_features,
            'statistical': self._generate_statistical_features,
            'time': self._generate_time_features,
            'cross': self._generate_cross_features
        }

    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        return self.generate_features(*args, **kwargs)

    def get_supported_methods(self) -> List[str]:
        return ['technical', 'statistical', 'time', 'cross', 'all']

    @validate_inputs
    @timing_decorator
    def generate_features(self,
                          data: pd.DataFrame,
                          feature_types: Optional[List[str]] = None,
                          window_sizes: Optional[List[int]] = None,
                          cross_features: Optional[List[Tuple[str, str]]] = None,
                          include_raw: bool = True) -> Dict[str, Any]:
        """
        Generate a comprehensive feature set from input data.

        Args:
            data: DataFrame with columns like 'close', 'high', 'low', 'open', 'volume'
            feature_types: List of feature types to generate.
                           Options: 'technical', 'statistical', 'time', 'cross'
            window_sizes: Rolling window sizes for feature computation
            cross_features: List of (col1, col2) pairs for cross features
            include_raw: Whether to include raw data as features

        Returns:
            Dictionary with:
                - features: DataFrame of generated features
                - feature_names: List of feature column names
                - feature_importance: Dict mapping feature name to importance score
                - feature_types: Dict mapping feature name to its type
        """
        if data is None or (isinstance(data, pd.DataFrame) and data.empty):
            raise DataValidationError("Input data is empty", field_name="data")

        if feature_types is None:
            feature_types = ['technical', 'statistical', 'time']

        if window_sizes is None:
            window_sizes = [5, 10, 20, 60]

        if not isinstance(data, pd.DataFrame):
            raise DataValidationError("data must be a pandas DataFrame", field_name="data")

        if 'close' not in data.columns:
            raise DataValidationError(
                "DataFrame must contain a 'close' column",
                field_name="data"
            )

        # Validate feature types
        valid_types = set(self.get_supported_methods())
        valid_types.discard('all')
        for ft in feature_types:
            if ft not in valid_types:
                raise ConfigurationError(
                    f"Unsupported feature type: {ft}",
                    parameter="feature_types"
                )
            if ft not in self._feature_functions:
                raise ConfigurationError(
                    f"Feature type '{ft}' has no registered generator",
                    parameter="feature_types"
                )

        # Ensure window sizes are positive integers
        window_sizes = [int(w) for w in window_sizes if int(w) > 1]

        features_list = []
        feature_names = []
        feature_type_map = {}
        feature_importance = {}

        # Generate features by type
        for ft in feature_types:
            gen_func = self._feature_functions[ft]

            if ft == 'cross':
                generated = gen_func(data, cross_features)
            else:
                generated = gen_func(data, window_sizes)

            if generated is not None and not generated.empty:
                # Ensure we don't add duplicate column names
                for col in generated.columns:
                    if col not in feature_names:
                        feature_names.append(col)
                        feature_type_map[col] = ft
                        features_list.append(generated[col])

        if not features_list:
            if include_raw:
                # Fall back to raw data if no features generated
                for col in data.columns:
                    if col not in feature_names:
                        feature_names.append(col)
                        feature_type_map[col] = 'raw'
                        features_list.append(data[col].copy())

            if not features_list:
                raise CalculationError(
                    "No features could be generated from the input data",
                    calculation_type="feature_engineering"
                )

        # Combine all features
        result_df = pd.concat(features_list, axis=1)
        result_df.columns = feature_names

        # Add raw data if requested
        if include_raw:
            raw_feature_names = []
            for col in data.columns:
                raw_col_name = f"raw_{col}"
                if raw_col_name not in feature_names:
                    result_df[raw_col_name] = data[col].values
                    feature_type_map[raw_col_name] = 'raw'
                    raw_feature_names.append(raw_col_name)
            feature_names.extend(raw_feature_names)

        # Calculate feature importance
        feature_importance = self._calculate_feature_importance(result_df)

        # Drop rows with NaN
        result_df = result_df.dropna()

        feature_params = {
            'feature_types': feature_types,
            'window_sizes': window_sizes,
            'include_raw': include_raw
        }

        return self._create_result_dict(
            value=result_df.to_dict(orient='list'),
            method='feature_engineering',
            parameters=feature_params,
            metadata={
                'n_features': len(feature_names),
                'feature_names': feature_names,
                'feature_importance': feature_importance,
                'feature_types': feature_type_map,
                'n_samples': len(result_df)
            }
        )

    def _generate_technical_features(self,
                                     data: pd.DataFrame,
                                     window_sizes: List[int]) -> pd.DataFrame:
        """Generate technical indicator features."""
        features = pd.DataFrame(index=data.index)

        close = data['close'].astype(float)
        high = data.get('high', data['close']).astype(float)
        low = data.get('low', data['close']).astype(float)
        volume = data.get('volume', pd.Series(1.0, index=data.index)).astype(float)

        for w in window_sizes:
            if w > len(data):
                continue

            # RSI
            features[f'rsi_{w}'] = self._compute_rsi(close, w)

            # MACD (use standard periods but vary signal line)
            if w >= 12:
                ema_fast = close.ewm(span=12, adjust=False).mean()
                ema_slow = close.ewm(span=26, adjust=False).mean()
                macd = ema_fast - ema_slow
                signal = macd.ewm(span=w, adjust=False).mean()
                features[f'macd_{w}'] = macd - signal
                features[f'macd_line_{w}'] = macd

            # Bollinger Bands
            ma = close.rolling(window=w).mean()
            std = close.rolling(window=w).std()
            features[f'bb_position_{w}'] = (close - ma) / (2 * std + 1e-10)
            features[f'bb_width_{w}'] = 2 * std / (ma + 1e-10)

            # Rate of Change (ROC)
            features[f'roc_{w}'] = close.pct_change(w)

            # Volume Ratio
            vol_ma = volume.rolling(window=w).mean()
            features[f'volume_ratio_{w}'] = volume / (vol_ma + 1e-10)

            # ATR (Average True Range)
            tr = pd.concat([
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs()
            ], axis=1).max(axis=1)
            features[f'atr_{w}'] = tr.rolling(window=w).mean() / (close + 1e-10)

            # MA Crossover
            if w >= 10:
                ma_short = close.rolling(window=int(w / 2)).mean()
                ma_long = close.rolling(window=w).mean()
                features[f'ma_cross_{w}'] = (ma_short - ma_long) / (close + 1e-10)

            # Price position relative to MA
            if w > 1:
                features[f'price_vs_ma_{w}'] = (close - ma) / (std + 1e-10)

        return features

    def _generate_statistical_features(self,
                                       data: pd.DataFrame,
                                       window_sizes: List[int]) -> pd.DataFrame:
        """Generate statistical moment features."""
        features = pd.DataFrame(index=data.index)

        cols = [c for c in ['close', 'high', 'low', 'open', 'volume']
                if c in data.columns]
        returns = data['close'].pct_change()

        for w in window_sizes:
            if w > len(data):
                continue

            # Rolling moments for returns
            roll = returns.rolling(window=w)
            features[f'ret_mean_{w}'] = roll.mean()
            features[f'ret_std_{w}'] = roll.std()
            features[f'ret_skew_{w}'] = roll.skew()
            features[f'ret_kurt_{w}'] = roll.kurt()

            # Rolling moments for close price
            roll_c = data['close'].rolling(window=w)
            features[f'price_mean_{w}'] = roll_c.mean()
            features[f'price_std_{w}'] = roll_c.std()

            # Max drawdown over window
            roll_max = data['close'].rolling(window=w).max()
            features[f'drawdown_{w}'] = data['close'] / roll_max - 1

            # Historical volatility
            features[f'hist_vol_{w}'] = returns.rolling(window=w).std() * np.sqrt(252)

            # Rolling Sharpe (simple, rf=0)
            features[f'rolling_sharpe_{w}'] = (roll.mean() / (roll.std() + 1e-10)) * np.sqrt(252)

        return features

    def _generate_time_features(self,
                                data: pd.DataFrame,
                                window_sizes: List[int]) -> pd.DataFrame:
        """Generate time-based features (lags and differences)."""
        features = pd.DataFrame(index=data.index)

        cols = [c for c in ['close', 'volume'] if c in data.columns]

        for col in cols:
            series = data[col].astype(float)

            for w in window_sizes:
                if w > len(data):
                    continue

                # Lagged values
                features[f'{col}_lag_{w}'] = series.shift(w)

                # Simple differences
                features[f'{col}_diff_{w}'] = series.diff(w)

                # Percentage changes
                features[f'{col}_pct_{w}'] = series.pct_change(w)

                # Exponential moving average
                features[f'{col}_ema_{w}'] = series.ewm(span=w, adjust=False).mean()

            # Higher-order lags (1, 2, 3)
            for lag in [1, 2, 3]:
                features[f'{col}_lag{lag}'] = series.shift(lag)
                features[f'{col}_ret{lag}'] = series.pct_change(lag)

        return features

    def _generate_cross_features(self,
                                 data: pd.DataFrame,
                                 cross_features: Optional[List[Tuple[str, str]]] = None) -> pd.DataFrame:
        """Generate cross-feature interactions."""
        features = pd.DataFrame(index=data.index)

        numeric_cols = [c for c in data.columns
                        if pd.api.types.is_numeric_dtype(data[c])]

        if cross_features is None:
            if len(numeric_cols) >= 2:
                cross_features = list(combinations(numeric_cols[:5], 2))
            else:
                return features

        for col1, col2 in cross_features:
            if col1 in data.columns and col2 in data.columns:
                s1 = data[col1].astype(float)
                s2 = data[col2].astype(float)

                name = f'{col1}_x_{col2}'
                features[f'{name}_mul'] = s1 * s2
                features[f'{name}_div'] = s1 / (s2 + 1e-10)
                features[f'{name}_ratio'] = (s1 - s2) / (s1 + s2 + 1e-10)

        return features

    def _calculate_feature_importance(self,
                                      features: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate feature importance based on:
        1. Variance (higher variance = potentially more informative)
        2. Correlation with target-agnostic information content
        """
        importance = {}
        numeric_cols = features.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            col_data = features[col].dropna()
            if len(col_data) < 2:
                importance[col] = 0.0
                continue

            # Normalized variance as importance proxy
            var_score = np.var(col_data.values) / (np.mean(np.abs(col_data.values)) + 1e-10)
            importance[col] = float(np.clip(var_score, 0, 10))

        # Normalize importances
        if importance:
            max_imp = max(importance.values())
            if max_imp > 0:
                importance = {k: v / max_imp for k, v in importance.items()}

        return importance

    @staticmethod
    def _compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Compute the Relative Strength Index."""
        if len(prices) < period + 1:
            return pd.Series(np.nan, index=prices.index)

        delta = prices.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)

        avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def get_feature_names_by_type(self,
                                  feature_types: Dict[str, str],
                                  target_type: str) -> List[str]:
        """Filter feature names by type."""
        return [name for name, ftype in feature_types.items() if ftype == target_type]

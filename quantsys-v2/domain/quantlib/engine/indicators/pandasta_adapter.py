"""pandas-ta indicator adapter."""
from __future__ import annotations

from typing import Any

import pandas as pd

from domain.quantlib.engine.indicators.base import IndicatorAdapter


class PandasTAAdapter(IndicatorAdapter):
    """Adapter for the pandas-ta library (130+ indicators, pure Python).

    Requires the ``_numba_compat`` module to be imported first on
    Python 3.14+ where numba is incompatible.
    """

    _NAME_MAP: dict[str, str] = {
        'SMA': 'SMA', 'EMA': 'EMA', 'RSI': 'RSI', 'ADX': 'ADX',
        'CCI': 'CCI', 'MACD': 'MACD', 'BBANDS': 'BBANDS', 'ATR': 'ATR',
        'STOCH': 'STOCH', 'WILLR': 'WILLR', 'MFI': 'MFI', 'ROC': 'ROC',
        'OBV': 'OBV', 'PLUS_DI': 'PLUS_DI', 'MINUS_DI': 'MINUS_DI',
    }

    def is_available(self) -> bool:
        try:
            import domain.quantlib.engine.indicators._numba_compat  # noqa: F401
            import pandas_ta  # noqa: F401
            return True
        except ImportError:
            return False

    def list_indicators(self) -> list[str]:
        try:
            import pandas_ta as ta
            return list(ta.Strategy('All').ta.names())
        except Exception:
            return list(self._NAME_MAP.keys())

    def calculate(
        self, klines: list[dict], indicator: str, **params
    ) -> Any:
        if not self.is_available():
            return None

        import pandas_ta as ta

        df = self._klines_to_df(klines)
        ta_name = indicator.upper()

        func = getattr(ta, ta_name.lower(), None)
        if func is None:
            return None

        # Handle derived indicators from ADX DataFrame
        if ta_name in ('PLUS_DI', 'MINUS_DI'):
            adx_df = self.calculate(klines, 'ADX', **params)
            if adx_df is None and hasattr(adx_df, '__iter__'):
                return None
            # Use the ADX function directly for sub-columns
            try:
                kwargs = self._build_kwargs(df, params)
                adx_result = ta.adx(**kwargs)
                col = 'DMP_14' if ta_name == 'PLUS_DI' else 'DMN_14'
                if col in adx_result.columns:
                    return adx_result[col].tolist()
            except Exception:
                return None
            return None

        try:
            kwargs = self._build_kwargs(df, params)
            result = func(**kwargs)
            # Handle DataFrame results (e.g. ADX returns multi-column DF)
            if isinstance(result, pd.DataFrame):
                # Find the first numeric-like column matching the indicator name
                cols = [c for c in result.columns
                        if ta_name.upper() in c.upper()
                        and result[c].dtype in ('float64', 'float32', 'int64')]
                if cols:
                    return result[cols[0]].tolist()
                # Fallback: return first numeric column
                for c in result.columns:
                    if result[c].dtype in ('float64', 'float32', 'int64'):
                        return result[c].tolist()
                return result.iloc[:, 0].tolist()
            if isinstance(result, pd.Series):
                return result.tolist()
            return result
        except Exception:
            return None

    def _klines_to_df(self, klines: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(klines)
        for col in ('close', 'high', 'low', 'open', 'volume'):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 处理NULL volume：使用0填充，避免计算异常
        if 'volume' in df.columns:
            df['volume'] = df['volume'].fillna(0)

        return df

    def _build_kwargs(self, df: pd.DataFrame, params: dict) -> dict:
        kwargs = {
            'close': df['close'], 'high': df['high'],
            'low': df['low'], 'open': df['open'], 'volume': df['volume'],
        }
        if 'length' in params:
            kwargs['length'] = params['length']
        if 'fast' in params:
            kwargs['fast'] = params['fast']
        if 'slow' in params:
            kwargs['slow'] = params['slow']
        if 'signal' in params:
            kwargs['signal'] = params['signal']
        if 'std' in params:
            kwargs['std'] = params['std']
        return kwargs

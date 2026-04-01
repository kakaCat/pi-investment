"""均值回归策略"""

from __future__ import annotations

import pandas as pd

from strategies.base import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    name = 'mean_reversion'
    required_columns = ('date', 'close', 'ma20', 'rsi', 'bb_lower')

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        self.validate_columns(df)
        signals = (
            (df['close'] < df['bb_lower'])
            & (df['close'] < df['ma20'])
            & (df['rsi'] < 35)
        ).astype(int)
        return pd.Series(signals.to_numpy(), index=pd.Index(df['date'], name='date'))

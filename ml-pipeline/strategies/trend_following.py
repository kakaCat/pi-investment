"""趋势跟随策略"""

from __future__ import annotations

import pandas as pd

from strategies.base import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    name = 'trend_following'
    required_columns = ('date', 'close', 'ma20', 'ma60', 'macd_hist')

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        self.validate_columns(df)
        signals = (
            (df['close'] > df['ma20'])
            & (df['ma20'] > df['ma60'])
            & (df['macd_hist'] > 0)
        ).astype(int)
        return pd.Series(signals.to_numpy(), index=pd.Index(df['date'], name='date'))

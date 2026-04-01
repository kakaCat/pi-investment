"""动量策略"""

from __future__ import annotations

import pandas as pd

from strategies.base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    name = 'momentum'
    required_columns = ('date', 'close', 'ma20', 'macd', 'macd_signal', 'volume_change')

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        self.validate_columns(df)
        signals = (
            (df['close'] > df['ma20'])
            & (df['macd'] > df['macd_signal'])
            & (df['volume_change'] > 0)
        ).astype(int)
        return pd.Series(signals.to_numpy(), index=pd.Index(df['date'], name='date'))

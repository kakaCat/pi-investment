"""回测策略基类"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    name = 'base'
    required_columns: tuple[str, ...] = ('date', 'close')

    def validate_columns(self, df: pd.DataFrame) -> None:
        missing_columns = [column for column in self.required_columns if column not in df.columns]
        if missing_columns:
            missing = ', '.join(missing_columns)
            raise ValueError(f'Strategy {self.name} missing required columns: {missing}')

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        raise NotImplementedError

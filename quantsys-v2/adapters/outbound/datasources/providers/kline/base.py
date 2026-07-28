"""Base class for kline data providers"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class KlineData:
    """Kline data point

    volume 单位统一为股（providers 负责把手的原始单位 ×100 归一），
    amount 为成交额（元），无原始数据时 provider 按 volume×close 估算。
    """
    symbol: str
    date: str  # YYYY-MM-DD or YYYY-MM-DD HH:MM:SS
    open: float
    high: float
    low: float
    close: float
    volume: int
    change_pct: float = 0.0
    amount: float = 0.0
    source: str = ""
    timestamp: str = ""  # ISO format

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class KlineProvider(ABC):
    """Abstract base class for kline data providers"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and source attribution"""
        pass

    @abstractmethod
    def get_klines(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str
    ) -> Optional[List[KlineData]]:
        """Get kline data

        Args:
            symbol: Stock symbol
            period: Period (daily, weekly, monthly, 1m, 5m, 15m, 30m, 60m)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of KlineData if successful, None if failed
        """
        pass

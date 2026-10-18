# domain/trading/ports/IMinuteKlineRepository.py
"""分钟线仓储端口（RFC 015 §4.1）

存储为既有表 quant.minute_klines（主键 (symbol, trade_datetime)，无 period 列）。
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from domain.models.market_data import MinuteKline


class IMinuteKlineRepository(ABC):
    """分钟K线仓储接口"""

    @abstractmethod
    def get_minute_klines(
        self,
        symbol: str,
        start_datetime: str,
        end_datetime: str,
    ) -> List[MinuteKline]:
        """按时间区间查询分钟K线（升序）

        Args:
            start_datetime: 'YYYY-MM-DD HH:MM:SS'
            end_datetime: 'YYYY-MM-DD HH:MM:SS'

        Returns:
            List[MinuteKline]（无数据返回空列表，不返回 None）
        """
        pass

    @abstractmethod
    def save_minute_klines(self, klines: List[MinuteKline]) -> bool:
        """批量落库（主键冲突由实现方处理/上报）"""
        pass

    @abstractmethod
    def get_latest_minute_kline(self, symbol: str) -> Optional[MinuteKline]:
        """最新一根分钟K线（无数据返回 None）"""
        pass

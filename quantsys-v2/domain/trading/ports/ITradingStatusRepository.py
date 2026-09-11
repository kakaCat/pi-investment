# domain/trading/ports/ITradingStatusRepository.py
"""交易状态基础数据端口（RFC 015 §4.3）

职责边界：只提供**基础状态事实**（stocks 表静态字段 + 最近日线昨收），
不做任何判定——ST/停牌/涨跌停的裁决属于领域服务 TradingStatusPolicy。
"""
from abc import ABC, abstractmethod
from typing import Optional


class ITradingStatusRepository(ABC):
    """交易状态基础数据仓储接口"""

    @abstractmethod
    def get_stock_status(self, symbol: str) -> Optional[dict]:
        """获取标的基础状态

        Returns:
            dict（至少包含以下键）或 None（标的不在 stocks 表 / 未上市）：
                symbol: str
                name: str
                market: str            # A/HK
                is_st: bool
                is_suspended: bool
                is_delisted: bool
                prev_close: Optional[float]   # 最近一根日线收盘价
                prev_close_date: Optional[str]
                source: str            # 'stocks_table'
        """
        pass

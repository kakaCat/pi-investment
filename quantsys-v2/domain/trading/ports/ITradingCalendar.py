"""
交易日历端口 (Trading Calendar Port)

定义交易日历的抽象接口，遵循依赖倒置原则。
domain 层定义接口，application/infrastructure 层实现。
"""
from abc import ABC, abstractmethod
from typing import List


class ITradingCalendar(ABC):
    """交易日历接口"""

    @abstractmethod
    def is_trading_day(self, day_str: str) -> bool:
        """
        判断指定日期是否为交易日

        Args:
            day_str: 日期字符串 (YYYY-MM-DD)

        Returns:
            bool: 是否为交易日
        """
        pass

    @abstractmethod
    def get_trading_days(
        self,
        start_date: str,
        end_date: str,
        exchange: str = 'SSE'
    ) -> List[str]:
        """
        获取指定日期范围内的所有交易日

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            exchange: 交易所代码 ('SSE', 'SZSE', 'ALL')

        Returns:
            List[str]: 交易日列表
        """
        pass

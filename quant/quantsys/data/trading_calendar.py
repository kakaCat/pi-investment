"""交易日历管理类

提供A股交易日历查询功能，支持缓存机制以减少API调用。
"""
from datetime import date, timedelta
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class TradingCalendar:
    """A股交易日历管理类

    使用akshare获取交易日历数据，并实现内存缓存以提高性能。
    """

    def __init__(self):
        """初始化交易日历"""
        self._cache: List[date] = []
        self._cache_start: Optional[date] = None
        self._cache_end: Optional[date] = None

        # 尝试导入akshare
        try:
            import akshare as ak
            self._ak = ak
        except ImportError:
            logger.warning("akshare not available, TradingCalendar will not work")
            self._ak = None

    def get_trading_days(self, start_date: date, end_date: date) -> List[date]:
        """获取指定日期范围内的交易日

        Args:
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            交易日列表，按日期升序排列
        """
        if self._ak is None:
            raise RuntimeError("akshare is not available")

        # 检查缓存是否覆盖请求范围
        if self._is_cache_valid(start_date, end_date):
            return self._filter_cache(start_date, end_date)

        # 扩展缓存范围以覆盖请求
        new_start = min(start_date, self._cache_start) if self._cache_start else start_date
        new_end = max(end_date, self._cache_end) if self._cache_end else end_date

        # 从API获取数据
        try:
            df = self._ak.tool_trade_date_hist_sina()

            # 转换为date对象列表
            trading_days = []
            for date_value in df['trade_date']:
                # akshare返回的可能是date对象或字符串
                if isinstance(date_value, date):
                    trading_days.append(date_value)
                elif isinstance(date_value, str):
                    # 格式: "2024-01-02" 或 "20240102"
                    if '-' in date_value:
                        parts = date_value.split('-')
                        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                    else:
                        year = int(date_value[:4])
                        month = int(date_value[4:6])
                        day = int(date_value[6:8])
                    trading_days.append(date(year, month, day))

            # 排序并更新缓存
            trading_days.sort()
            self._cache = trading_days
            self._cache_start = trading_days[0] if trading_days else None
            self._cache_end = trading_days[-1] if trading_days else None

            logger.info(f"Loaded {len(trading_days)} trading days from {self._cache_start} to {self._cache_end}")

            return self._filter_cache(start_date, end_date)

        except Exception as e:
            logger.error(f"Failed to fetch trading calendar: {e}")
            raise

    def is_trading_day(self, check_date: date) -> bool:
        """判断指定日期是否为交易日

        Args:
            check_date: 要检查的日期

        Returns:
            True表示是交易日，False表示不是
        """
        # 确保缓存覆盖该日期
        if not self._is_cache_valid(check_date, check_date):
            # 获取包含该日期的年份的所有交易日
            year_start = date(check_date.year, 1, 1)
            year_end = date(check_date.year, 12, 31)
            self.get_trading_days(year_start, year_end)

        return check_date in self._cache

    def _is_cache_valid(self, start_date: date, end_date: date) -> bool:
        """检查缓存是否覆盖指定日期范围

        Args:
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            True表示缓存有效，False表示需要重新加载
        """
        if not self._cache or self._cache_start is None or self._cache_end is None:
            return False

        return self._cache_start <= start_date and self._cache_end >= end_date

    def _filter_cache(self, start_date: date, end_date: date) -> List[date]:
        """从缓存中筛选指定日期范围的交易日

        Args:
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            交易日列表
        """
        return [d for d in self._cache if start_date <= d <= end_date]

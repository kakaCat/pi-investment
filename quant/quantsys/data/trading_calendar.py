"""交易日历管理类

提供A股交易日历查询功能，支持缓存机制以减少API调用。
"""
from datetime import date
from typing import List, Set
import logging

logger = logging.getLogger(__name__)


class TradingCalendar:
    """A股交易日历管理类

    使用akshare获取交易日历数据，并实现内存缓存以提高性能。
    由于交易日历数据量小（~8797天），采用一次性加载全部数据的策略。
    """

    def __init__(self):
        """初始化交易日历"""
        self._cache: List[date] = []
        self._cache_set: Set[date] = set()
        self._cache_loaded: bool = False

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

        Raises:
            RuntimeError: akshare不可用
            ValueError: 日期范围无效
        """
        if self._ak is None:
            raise RuntimeError("akshare is not available")

        # 验证日期范围
        if start_date > end_date:
            raise ValueError(f"start_date ({start_date}) must be <= end_date ({end_date})")

        # 如果缓存未加载，加载全部交易日历
        if not self._cache_loaded:
            self._load_full_calendar()

        # 从缓存中筛选日期范围
        return [d for d in self._cache if start_date <= d <= end_date]

    def is_trading_day(self, check_date: date) -> bool:
        """判断指定日期是否为交易日

        Args:
            check_date: 要检查的日期

        Returns:
            True表示是交易日，False表示不是

        Raises:
            RuntimeError: akshare不可用
        """
        if self._ak is None:
            raise RuntimeError("akshare is not available")

        # 如果缓存未加载，加载全部交易日历
        if not self._cache_loaded:
            self._load_full_calendar()

        # O(1) 查找
        return check_date in self._cache_set

    def _load_full_calendar(self) -> None:
        """从akshare加载完整的交易日历

        Raises:
            RuntimeError: 加载失败
        """
        try:
            df = self._ak.tool_trade_date_hist_sina()

            # 转换为date对象列表
            trading_days = []
            for date_value in df['trade_date']:
                try:
                    # akshare返回的可能是date对象或字符串
                    if isinstance(date_value, date):
                        trading_days.append(date_value)
                    elif isinstance(date_value, str):
                        # 格式: "2024-01-02" 或 "20240102"
                        if '-' in date_value:
                            parts = date_value.split('-')
                            if len(parts) != 3:
                                logger.warning(f"Invalid date format: {date_value}")
                                continue
                            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                        else:
                            if len(date_value) != 8:
                                logger.warning(f"Invalid date format: {date_value}")
                                continue
                            year = int(date_value[:4])
                            month = int(date_value[4:6])
                            day = int(date_value[6:8])
                        trading_days.append(date(year, month, day))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse date value {date_value}: {e}")
                    continue

            # 排序并更新缓存
            trading_days.sort()
            self._cache = trading_days
            self._cache_set = set(trading_days)
            self._cache_loaded = True

            cache_start = trading_days[0] if trading_days else None
            cache_end = trading_days[-1] if trading_days else None

            logger.info(f"Loaded {len(trading_days)} trading days from {cache_start} to {cache_end}")

        except Exception as e:
            logger.error(f"Failed to fetch trading calendar: {e}")
            raise RuntimeError(f"Failed to load trading calendar: {e}") from e

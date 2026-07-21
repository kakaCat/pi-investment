"""
交易日历服务

提供交易日历查询功能，支持多种数据源和缓存策略。
"""
import structlog
from typing import List, Optional
from datetime import datetime, timedelta, date
import json

logger = structlog.get_logger(__name__)


class TradingCalendarService:
    """交易日历服务

    提供交易日历查询，数据源优先级：
    1. Redis 缓存（TTL 1天）- 最快
    2. 数据库 daily_klines（DISTINCT trade_date）- 次快
    3. AkShare API（tool_trade_date_hist_sina）- Fallback
    """

    def __init__(self, kline_repo=None, redis_client=None):
        """初始化交易日历服务

        Args:
            kline_repo: K线数据仓库实例
            redis_client: Redis客户端实例（可选）
        """
        from adapters.outbound.repositories import KlineORMRepository

        self.kline_repo = kline_repo or KlineORMRepository()
        self.redis = redis_client
        self._cache = {}  # 内存缓存作为 Redis 的 fallback

    def get_trading_days(
        self,
        start_date: str,
        end_date: str,
        exchange: str = 'SSE'
    ) -> List[str]:
        """获取指定日期范围内的所有交易日

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            exchange: 交易所代码 ('SSE', 'SZSE', 'ALL')

        Returns:
            交易日列表（YYYY-MM-DD格式），按日期升序
        """
        cache_key = f"trading_days:{exchange}:{start_date}:{end_date}"

        # 1. 尝试 Redis 缓存
        if self.redis:
            try:
                cached = self.redis.get(cache_key)
                if cached:
                    logger.debug(f"从 Redis 缓存获取交易日历: {start_date} ~ {end_date}")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis 缓存读取失败: {e}")

        # 2. 尝试内存缓存
        if cache_key in self._cache:
            cache_entry = self._cache[cache_key]
            if datetime.now() < cache_entry['expires_at']:
                logger.debug(f"从内存缓存获取交易日历: {start_date} ~ {end_date}")
                return cache_entry['data']

        # 3. 优先使用工作日fallback（最可靠）
        # 这样可以避免循环依赖：如果数据库没有某天的数据，就不会认为那天是交易日
        logger.info(f"使用工作日规则生成交易日历: {start_date} ~ {end_date}")
        weekdays = self._generate_weekdays(start_date, end_date)

        # 尝试从 AkShare 获取精确的交易日历（用于排除节假日）
        try:
            import akshare as ak
            logger.debug(f"尝试从 AkShare 获取精确交易日历")
            df = ak.tool_trade_date_hist_sina()
            df['trade_date'] = df['trade_date'].astype(str)
            filtered = df[
                (df['trade_date'] >= start_date) &
                (df['trade_date'] <= end_date)
            ]
            akshare_days = filtered['trade_date'].tolist()

            if akshare_days and len(akshare_days) > 0:
                logger.info(f"从 AkShare 获取到 {len(akshare_days)} 个交易日")
                self._cache_trading_days(cache_key, akshare_days)
                return akshare_days
        except Exception as e:
            logger.warning(f"从 AkShare 获取交易日历失败，使用工作日: {e}")

        # 如果 AkShare 失败，使用工作日作为结果
        logger.info(f"使用工作日规则: {len(weekdays)} 天")
        self._cache_trading_days(cache_key, weekdays)
        return weekdays

    def _cache_trading_days(self, cache_key: str, days: List[str]):
        """缓存交易日历数据

        Args:
            cache_key: 缓存键
            days: 交易日列表
        """
        # Redis 缓存（TTL 1天）
        if self.redis:
            try:
                self.redis.setex(cache_key, 86400, json.dumps(days))
            except Exception as e:
                logger.warning(f"Redis 缓存写入失败: {e}")

        # 内存缓存
        self._cache[cache_key] = {
            'data': days,
            'expires_at': datetime.now() + timedelta(days=1)
        }

    def _generate_weekdays(self, start_date: str, end_date: str) -> List[str]:
        """生成工作日列表（排除周末）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            工作日列表
        """
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        weekdays = []
        current = start
        while current <= end:
            # 排除周六(5)和周日(6)
            if current.weekday() < 5:
                weekdays.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)

        return weekdays

    def is_trading_day(self, check_date: str, exchange: str = 'SSE') -> bool:
        """判断指定日期是否为交易日

        Args:
            check_date: 日期 (YYYY-MM-DD)
            exchange: 交易所代码

        Returns:
            True if 交易日，否则 False
        """
        # 获取前后一周的交易日历
        check_dt = datetime.strptime(check_date, '%Y-%m-%d').date()
        start_date = (check_dt - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = (check_dt + timedelta(days=7)).strftime('%Y-%m-%d')

        trading_days = self.get_trading_days(start_date, end_date, exchange)
        return check_date in trading_days

    def get_next_trading_day(
        self,
        from_date: str,
        exchange: str = 'SSE'
    ) -> Optional[str]:
        """获取下一个交易日

        Args:
            from_date: 起始日期 (YYYY-MM-DD)
            exchange: 交易所代码

        Returns:
            下一个交易日，如果没有返回 None
        """
        from_dt = datetime.strptime(from_date, '%Y-%m-%d').date()
        end_date = (from_dt + timedelta(days=30)).strftime('%Y-%m-%d')

        trading_days = self.get_trading_days(from_date, end_date, exchange)

        # 找到第一个大于 from_date 的交易日
        for day in trading_days:
            if day > from_date:
                return day

        return None

    def get_prev_trading_day(
        self,
        from_date: str,
        exchange: str = 'SSE'
    ) -> Optional[str]:
        """获取上一个交易日

        Args:
            from_date: 起始日期 (YYYY-MM-DD)
            exchange: 交易所代码

        Returns:
            上一个交易日，如果没有返回 None
        """
        from_dt = datetime.strptime(from_date, '%Y-%m-%d').date()
        start_date = (from_dt - timedelta(days=30)).strftime('%Y-%m-%d')

        trading_days = self.get_trading_days(start_date, from_date, exchange)

        # 找到最后一个小于 from_date 的交易日
        for day in reversed(trading_days):
            if day < from_date:
                return day

        return None

    def get_trading_days_count(
        self,
        start_date: str,
        end_date: str,
        exchange: str = 'SSE'
    ) -> int:
        """获取指定日期范围内的交易日数量

        Args:
            start_date: 开始日期
            end_date: 结束日期
            exchange: 交易所代码

        Returns:
            交易日数量
        """
        trading_days = self.get_trading_days(start_date, end_date, exchange)
        return len(trading_days)

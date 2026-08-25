"""
数据缺失检测器

检测股票K线数据的缺失情况，与交易日历比对找出缺失的交易日。
"""
import structlog
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = structlog.get_logger(__name__)


class DataGapDetector:
    """数据缺失检测器

    通过比对交易日历和实际K线数据，检测缺失的交易日。
    支持单个股票检测和批量检测。
    """

    def __init__(self, kline_repo=None, calendar_service=None):
        """初始化缺失检测器

        Args:
            kline_repo: K线数据仓库实例
            calendar_service: 交易日历服务实例
        """
        from domain.ports import IKlineRepository
        from application.services.trading_calendar_service import TradingCalendarService

        self.kline_repo = kline_repo
        self.calendar = calendar_service or TradingCalendarService(self.kline_repo)

    def detect_gaps(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        exchange: str = 'SSE'
    ) -> Dict:
        """检测单个股票的数据缺失

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            exchange: 交易所代码

        Returns:
            缺失信息字典:
            {
                'symbol': '600000.SH',
                'total_trading_days': 250,
                'actual_days': 245,
                'missing_days_count': 5,
                'missing_days': ['2026-02-15', '2026-02-16', ...],
                'missing_segments': [
                    {'start': '2026-02-15', 'end': '2026-02-20', 'days': 4},
                    {'start': '2026-03-10', 'end': '2026-03-10', 'days': 1}
                ],
                'coverage_rate': 98.0
            }
        """
        logger.info(f"检测股票 {symbol} 的数据缺失: {start_date} ~ {end_date}")

        # 1. 获取交易日历
        trading_days = set(self.calendar.get_trading_days(start_date, end_date, exchange))

        # 2. 获取实际数据的交易日
        try:
            actual_days_list = self.kline_repo.get_trading_days(start_date, end_date, symbol)
            actual_days = set(actual_days_list)
        except Exception as e:
            logger.error(f"获取股票 {symbol} 的实际数据失败: {e}")
            actual_days = set()

        # 3. 计算缺失的交易日
        missing_days = sorted(trading_days - actual_days)

        # 4. 合并连续缺失的日期段
        missing_segments = self._merge_consecutive_days(missing_days)

        # 5. 计算覆盖率
        total_days = len(trading_days)
        actual_count = len(actual_days)
        coverage_rate = (actual_count / total_days * 100) if total_days > 0 else 0.0

        return {
            'symbol': symbol,
            'total_trading_days': total_days,
            'actual_days': actual_count,
            'missing_days_count': len(missing_days),
            'missing_days': missing_days,
            'missing_segments': missing_segments,
            'coverage_rate': round(coverage_rate, 2)
        }

    def detect_gaps_batch(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        exchange: str = 'SSE',
        max_workers: int = 8,
        only_with_gaps: bool = True
    ) -> Dict[str, Dict]:
        """批量检测多个股票的数据缺失

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            exchange: 交易所代码
            max_workers: 并行工作线程数
            only_with_gaps: 仅返回有缺失的股票

        Returns:
            字典，key为股票代码，value为缺失信息
        """
        logger.info(f"批量检测 {len(symbols)} 只股票的数据缺失")

        # 1. 获取交易日历（所有股票共享）
        trading_days = set(self.calendar.get_trading_days(start_date, end_date, exchange))
        total_trading_days = len(trading_days)

        logger.info(f"交易日历: {start_date} ~ {end_date}, 共 {total_trading_days} 个交易日")

        # 2. 批量查询所有股票的实际数据（优化：一次SQL查询）
        actual_days_map = self._batch_get_actual_days(symbols, start_date, end_date)

        # 3. 并行计算每个股票的缺失情况
        gaps = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self._calculate_gaps_for_symbol,
                    symbol,
                    trading_days,
                    actual_days_map.get(symbol, set())
                ): symbol
                for symbol in symbols
            }

            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    gap_info = future.result()

                    # 仅返回有缺失的股票
                    if only_with_gaps:
                        if gap_info['missing_days_count'] > 0:
                            gaps[symbol] = gap_info
                    else:
                        gaps[symbol] = gap_info

                except Exception as e:
                    logger.error(f"计算股票 {symbol} 缺失信息失败: {e}")

        logger.info(f"检测完成: {len(gaps)} 只股票有数据缺失")
        return gaps

    def _batch_get_actual_days(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, set]:
        """批量查询多个股票的实际交易日（优化：一次SQL）

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            字典，key为股票代码，value为交易日集合
        """
        if not symbols:
            return {}

        try:
            # 使用 PostgreSQL 的 array_agg 聚合函数，一次查询获取所有股票的交易日
            query = """
                SELECT symbol, array_agg(trade_date::text ORDER BY trade_date) as dates
                FROM quant.daily_klines
                WHERE symbol = ANY(%s)
                  AND trade_date >= %s
                  AND trade_date <= %s
                GROUP BY symbol
            """

            cursor = None
            try:
                cursor = self.kline_repo._get_cursor()
                cursor.execute(query, (symbols, start_date, end_date))
                results = cursor.fetchall()
            finally:
                if cursor:
                    cursor.close()

            # 转换为字典
            actual_days_map = {}
            for row in results:
                if isinstance(row, dict):
                    symbol = row['symbol']
                    dates = row['dates']
                else:
                    symbol = row[0]
                    dates = row[1]
                actual_days_map[symbol] = set(dates) if dates else set()

            # 补充没有数据的股票（空集合）
            for symbol in symbols:
                if symbol not in actual_days_map:
                    actual_days_map[symbol] = set()

            return actual_days_map

        except Exception as e:
            logger.error(f"批量查询实际交易日失败: {e}")
            # Fallback：逐个查询（使用正确的方法签名）
            actual_days_map = {}
            for symbol in symbols:
                try:
                    query = """
                        SELECT trade_date
                        FROM quant.daily_klines
                        WHERE symbol = %s
                          AND trade_date >= %s
                          AND trade_date <= %s
                        ORDER BY trade_date ASC
                    """
                    cursor = None
                    try:
                        cursor = self.kline_repo._get_cursor()
                        cursor.execute(query, (symbol, start_date, end_date))
                        results = cursor.fetchall()
                        # Handle both dict and tuple results
                        if results and isinstance(results[0], dict):
                            actual_days_map[symbol] = set(str(row['trade_date']) for row in results)
                        elif results:
                            actual_days_map[symbol] = set(str(row[0]) for row in results)
                        else:
                            actual_days_map[symbol] = set()
                    finally:
                        if cursor:
                            cursor.close()
                except Exception as e2:
                    logger.error(f"查询股票 {symbol} 实际交易日失败: {e2}")
                    actual_days_map[symbol] = set()

            return actual_days_map

    def _calculate_gaps_for_symbol(
        self,
        symbol: str,
        trading_days: set,
        actual_days: set
    ) -> Dict:
        """计算单个股票的缺失信息

        Args:
            symbol: 股票代码
            trading_days: 交易日历集合
            actual_days: 实际交易日集合

        Returns:
            缺失信息字典
        """
        missing_days = sorted(trading_days - actual_days)
        missing_segments = self._merge_consecutive_days(missing_days)

        total_days = len(trading_days)
        actual_count = len(actual_days)
        coverage_rate = (actual_count / total_days * 100) if total_days > 0 else 0.0

        return {
            'symbol': symbol,
            'total_trading_days': total_days,
            'actual_days': actual_count,
            'missing_days_count': len(missing_days),
            'missing_days': missing_days,
            'missing_segments': missing_segments,
            'coverage_rate': round(coverage_rate, 2)
        }

    def _merge_consecutive_days(self, days: List[str]) -> List[Dict]:
        """合并连续的日期为日期段

        Args:
            days: 日期列表（已排序）

        Returns:
            日期段列表，每个段包含 start, end, days 字段
        """
        if not days:
            return []

        segments = []
        segment_start = days[0]
        segment_end = days[0]
        segment_count = 1

        for i in range(1, len(days)):
            current = datetime.strptime(days[i], '%Y-%m-%d').date()
            prev = datetime.strptime(days[i-1], '%Y-%m-%d').date()

            # 如果是连续日期（考虑周末和节假日，这里简单判断相差 <= 3天）
            if (current - prev).days <= 3:
                segment_end = days[i]
                segment_count += 1
            else:
                # 保存当前段
                segments.append({
                    'start': segment_start,
                    'end': segment_end,
                    'days': segment_count
                })
                # 开始新段
                segment_start = days[i]
                segment_end = days[i]
                segment_count = 1

        # 保存最后一段
        segments.append({
            'start': segment_start,
            'end': segment_end,
            'days': segment_count
        })

        return segments

    def get_gap_summary(self, gaps: Dict[str, Dict]) -> Dict:
        """获取缺失汇总统计

        Args:
            gaps: 缺失信息字典（来自 detect_gaps_batch）

        Returns:
            汇总统计:
            {
                'total_stocks': 100,
                'stocks_with_gaps': 15,
                'total_missing_days': 450,
                'avg_coverage_rate': 98.5,
                'worst_stocks': [
                    {'symbol': '600000.SH', 'coverage_rate': 85.0, 'missing_days': 30},
                    ...
                ]
            }
        """
        if not gaps:
            return {
                'total_stocks': 0,
                'stocks_with_gaps': 0,
                'total_missing_days': 0,
                'avg_coverage_rate': 100.0,
                'worst_stocks': []
            }

        total_missing = sum(g['missing_days_count'] for g in gaps.values())
        avg_coverage = sum(g['coverage_rate'] for g in gaps.values()) / len(gaps)

        # 找出覆盖率最低的前10只股票
        worst_stocks = sorted(
            [
                {
                    'symbol': symbol,
                    'coverage_rate': gap['coverage_rate'],
                    'missing_days': gap['missing_days_count']
                }
                for symbol, gap in gaps.items()
            ],
            key=lambda x: x['coverage_rate']
        )[:10]

        return {
            'total_stocks': len(gaps),
            'stocks_with_gaps': len([g for g in gaps.values() if g['missing_days_count'] > 0]),
            'total_missing_days': total_missing,
            'avg_coverage_rate': round(avg_coverage, 2),
            'worst_stocks': worst_stocks
        }

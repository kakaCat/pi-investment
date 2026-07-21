"""
K线数据ORM Repository

使用SQLAlchemy ORM重构的K线数据访问层

支持：
1. 日K线查询（单只/批量）
2. 分钟K线查询
3. 最新K线查询
4. Polars DataFrame返回（保持兼容性）

迁移状态：✅ 已完成ORM迁移

DDD架构：
- 实现 domain.ports.IKlineRepository 接口
- 符合依赖倒置原则
"""
from typing import List, Dict, Optional
from datetime import date, datetime
import polars as pl
import structlog

from sqlalchemy import desc, and_, func
from infrastructure.persistence.orm import BaseORMRepository, get_session
from infrastructure.persistence.orm.models import DailyKline, MinuteKline
from domain.ports import IKlineRepository

logger = structlog.get_logger(__name__)

__all__ = ['KlineORMRepository']


class KlineORMRepository(BaseORMRepository[DailyKline], IKlineRepository):
    """K线ORM Repository

    示例用法：
        repo = KlineORMRepository()

        # 查询日K线（返回Polars DataFrame）
        df = repo.get_daily_klines('000001', '2026-01-01', '2026-06-30')

        # 查询最新K线
        latest = repo.get_latest_daily_kline('000001')

        # 批量查询
        batch = repo.get_latest_daily_klines_batch(['000001', '600000'])
    """

    model = DailyKline

    # ==================== IKlineRepository接口实现 ====================

    def get_kline_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = 'daily'
    ) -> pl.DataFrame:
        """获取K线数据（IKlineRepository接口实现）

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)，None表示从最早开始
            end_date: 结束日期 (YYYY-MM-DD)，None表示到最新
            period: K线周期，支持 'daily', 'minute'

        Returns:
            polars DataFrame
        """
        if period == 'minute':
            if not start_date or not end_date:
                # 分钟K线必须指定日期范围
                return pl.DataFrame()
            return self.get_minute_klines(symbol, start_date, end_date)

        # 默认返回日K线
        if not start_date:
            start_date = '1990-01-01'
        if not end_date:
            from datetime import date
            end_date = date.today().isoformat()

        return self.get_daily_klines(symbol, start_date, end_date)

    def get_range(self, symbol: str, start_date: str, end_date: str) -> pl.DataFrame:
        """获取指定日期范围内的K线数据（兼容别名）

        多个服务文件（strategy_executor、strategy_execution_service 等）调用此方法。
        委托给 get_kline_data()，返回 polars DataFrame（按日期升序）。

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            polars DataFrame
        """
        return self.get_kline_data(symbol, start_date, end_date)

    def save_kline_data(self, symbol: str, kline_data: pl.DataFrame, period: str = 'daily') -> bool:
        """保存K线数据（IKlineRepository接口实现）

        Args:
            symbol: 股票代码
            kline_data: K线数据DataFrame
            period: K线周期

        Returns:
            成功返回True
        """
        try:
            if kline_data.is_empty():
                return True

            if period == 'daily':
                # 转换为DailyKline对象
                klines = []
                for row in kline_data.iter_rows(named=True):
                    kline = DailyKline(
                        symbol=self._normalize_symbol(symbol),
                        trade_date=row.get('trade_date'),
                        open=row.get('open'),
                        high=row.get('high'),
                        low=row.get('low'),
                        close=row.get('close'),
                        volume=row.get('volume'),
                        amount=row.get('amount'),
                        turnover_rate=row.get('turnover_rate'),
                    )
                    klines.append(kline)
                return self.batch_insert_daily_klines(klines)

            return False

        except Exception as e:
            logger.error(f"Error saving kline data for {symbol}: {e}")
            return False

    def save_klines(self, klines: List[Dict]) -> int:
        """保存K线数据（字典列表格式）

        Args:
            klines: K线数据字典列表

        Returns:
            成功保存的记录数
        """
        if not klines:
            return 0

        try:
            # 转换为DailyKline对象
            kline_objs = []
            for kline_dict in klines:
                kline = DailyKline(
                    symbol=self._normalize_symbol(kline_dict['symbol']),
                    trade_date=kline_dict['trade_date'],
                    open=kline_dict['open'],
                    high=kline_dict['high'],
                    low=kline_dict['low'],
                    close=kline_dict['close'],
                    volume=kline_dict['volume'],
                    amount=kline_dict.get('amount', 0),
                    turnover_rate=kline_dict.get('turnover_rate', 0),
                )
                kline_objs.append(kline)

            # 使用batch_insert_daily_klines保存
            result = self.batch_insert_daily_klines(kline_objs)
            return len(klines) if result else 0

        except Exception as e:
            logger.error(f"Error in save_klines: {e}")
            return 0

    def batch_get_kline(self, symbols: List[str], start_date: str, end_date: str) -> Dict[str, pl.DataFrame]:
        """批量获取K线数据（IKlineRepository接口实现）

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            字典 {symbol: DataFrame}
        """
        try:
            batch_data = self.get_daily_klines_batch(symbols, start_date, end_date)
            result = {}
            for symbol, klines in batch_data.items():
                if klines:
                    result[symbol] = pl.DataFrame(klines)
                else:
                    result[symbol] = pl.DataFrame()
            return result
        except Exception as e:
            logger.error(f"Error batch getting klines: {e}")
            return {symbol: pl.DataFrame() for symbol in symbols}

    # ==================== 原有方法 ====================

    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码（去除后缀）

        数据库已统一使用无后缀格式
        """
        if '.' in symbol:
            return symbol.split('.')[0]
        return symbol

    # ==================== 日K线查询 ====================

    def get_daily_klines(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        fields: List[str] = None
    ) -> pl.DataFrame:
        """查询日K线数据

        Args:
            symbol: 股票代码（可带或不带交易所后缀）
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            fields: 需要返回的字段列表，None表示返回所有字段

        Returns:
            polars DataFrame，按日期升序排列
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)

            # 构建查询
            query = self.session.query(DailyKline).filter(
                DailyKline.symbol == normalized_symbol,
                DailyKline.trade_date >= start_date,
                DailyKline.trade_date <= end_date
            ).order_by(DailyKline.trade_date.asc())

            # 执行查询
            klines = query.all()

            if not klines:
                # 返回空DataFrame with schema
                return pl.DataFrame(schema={
                    'symbol': pl.Utf8,
                    'trade_date': pl.Date,
                    'open': pl.Float64,
                    'high': pl.Float64,
                    'low': pl.Float64,
                    'close': pl.Float64,
                    'volume': pl.Float64,
                    'amount': pl.Float64,
                    'turnover_rate': pl.Float64,
                })

            # 转换为字典列表
            rows = []
            for kline in klines:
                row = kline.to_dict()
                if fields:
                    row = {k: v for k, v in row.items() if k in fields}
                rows.append(row)

            return pl.DataFrame(rows)

        except Exception as e:
            logger.error(f"Error getting daily klines for {symbol}: {e}")
            return pl.DataFrame()

    def get_latest_daily_kline(self, symbol: str) -> Optional[pl.DataFrame]:
        """获取最新的日K线数据

        Args:
            symbol: 股票代码

        Returns:
            polars DataFrame (单行)，不存在返回None
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)

            kline = self.session.query(DailyKline).filter(
                DailyKline.symbol == normalized_symbol
            ).order_by(DailyKline.trade_date.desc()).first()

            if kline:
                return pl.DataFrame([kline.to_dict()])
            return None

        except Exception as e:
            logger.error(f"Error getting latest daily kline for {symbol}: {e}")
            return None

    def get_latest(self, symbol: str, limit: int = 100) -> pl.DataFrame:
        """获取最近N条日K线数据（兼容方法）

        Args:
            symbol: 股票代码
            limit: 返回最近N条记录

        Returns:
            polars DataFrame，按日期升序排列
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)

            klines = self.session.query(DailyKline).filter(
                DailyKline.symbol == normalized_symbol
            ).order_by(DailyKline.trade_date.desc()).limit(limit).all()

            if not klines:
                return pl.DataFrame(schema={
                    'symbol': pl.Utf8,
                    'trade_date': pl.Date,
                    'open': pl.Float64,
                    'high': pl.Float64,
                    'low': pl.Float64,
                    'close': pl.Float64,
                    'volume': pl.Int64,
                    'amount': pl.Float64,
                    'turnover_rate': pl.Float64
                })

            # 转换为DataFrame并按日期升序排列
            df = pl.DataFrame([k.to_dict() for k in reversed(klines)])
            return df

        except Exception as e:
            logger.error(f"Error getting latest {limit} klines for {symbol}: {e}")
            return pl.DataFrame()

    def get_latest_daily_klines_batch(
        self,
        symbols: List[str]
    ) -> Dict[str, Optional[Dict]]:
        """批量查询多只股票的最新日K线数据

        Args:
            symbols: 股票代码列表

        Returns:
            字典 {symbol: kline_data}，保持输入symbol格式
        """
        if not symbols:
            return {}

        try:
            # 标准化股票代码
            symbol_mapping = {}  # normalized -> original
            normalized_symbols = []

            for symbol in symbols:
                normalized = self._normalize_symbol(symbol)
                normalized_symbols.append(normalized)
                symbol_mapping[normalized] = symbol

            # 使用子查询获取每只股票的最新日期
            # SELECT DISTINCT ON (symbol) * FROM ... ORDER BY symbol, trade_date DESC
            from sqlalchemy.sql import text

            subquery = self.session.query(
                DailyKline.symbol,
                func.max(DailyKline.trade_date).label('max_date')
            ).filter(
                DailyKline.symbol.in_(normalized_symbols)
            ).group_by(DailyKline.symbol).subquery()

            # JOIN获取完整K线数据
            klines = self.session.query(DailyKline).join(
                subquery,
                and_(
                    DailyKline.symbol == subquery.c.symbol,
                    DailyKline.trade_date == subquery.c.max_date
                )
            ).all()

            # 构建结果字典
            db_results = {kline.symbol: kline.to_dict() for kline in klines}

            result = {}
            for normalized, original in symbol_mapping.items():
                result[original] = db_results.get(normalized)

            return result

        except Exception as e:
            logger.error(f"Error getting batch latest daily klines: {e}")
            return {symbol: None for symbol in symbols}

    def get_daily_klines_batch(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, List[Dict]]:
        """批量查询多只股票的日K线数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            字典 {symbol: [kline_data, ...]}, 按日期升序
        """
        if not symbols:
            return {}

        try:
            # 标准化股票代码
            normalized_symbols = [self._normalize_symbol(s) for s in symbols]

            # 批量查询
            klines = self.session.query(DailyKline).filter(
                DailyKline.symbol.in_(normalized_symbols),
                DailyKline.trade_date >= start_date,
                DailyKline.trade_date <= end_date
            ).order_by(DailyKline.symbol, DailyKline.trade_date.asc()).all()

            # 按symbol分组
            result = {symbol: [] for symbol in symbols}

            # 反向映射：normalized -> original
            symbol_mapping = {}
            for original in symbols:
                normalized = self._normalize_symbol(original)
                symbol_mapping[normalized] = original

            for kline in klines:
                original_symbol = symbol_mapping.get(kline.symbol)
                if original_symbol:
                    result[original_symbol].append(kline.to_dict())

            return result

        except Exception as e:
            logger.error(f"Error getting batch daily klines: {e}")
            return {symbol: [] for symbol in symbols}

    def count_daily_klines(self, symbol: str) -> int:
        """统计某只股票的日K线数量

        Args:
            symbol: 股票代码

        Returns:
            K线数量
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            return self.session.query(DailyKline).filter(
                DailyKline.symbol == normalized_symbol
            ).count()
        except Exception as e:
            logger.error(f"Error counting daily klines for {symbol}: {e}")
            return 0

    def count_klines(self, symbol: str) -> int:
        """统计某只股票的日K线数量（count_daily_klines 的别名）

        data_service.py 等调用方依赖此接口名，保留以保证向后兼容。

        Args:
            symbol: 股票代码

        Returns:
            K线数量
        """
        return self.count_daily_klines(symbol)

    def get_date_range(self, symbol: str) -> Optional[tuple]:
        """获取某只股票的K线日期范围

        Args:
            symbol: 股票代码

        Returns:
            (最早日期, 最晚日期) 或 None
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)

            result = self.session.query(
                func.min(DailyKline.trade_date),
                func.max(DailyKline.trade_date)
            ).filter(
                DailyKline.symbol == normalized_symbol
            ).first()

            if result and result[0]:
                return (result[0], result[1])
            return None

        except Exception as e:
            logger.error(f"Error getting date range for {symbol}: {e}")
            return None

    # ==================== 分钟K线查询 ====================

    def get_minute_klines(
        self,
        symbol: str,
        start_datetime: str,
        end_datetime: str
    ) -> pl.DataFrame:
        """查询分钟K线数据

        Args:
            symbol: 股票代码
            start_datetime: 开始时间 (YYYY-MM-DD HH:MM:SS)
            end_datetime: 结束时间 (YYYY-MM-DD HH:MM:SS)

        Returns:
            polars DataFrame
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)

            klines = self.session.query(MinuteKline).filter(
                MinuteKline.symbol == normalized_symbol,
                MinuteKline.trade_datetime >= start_datetime,
                MinuteKline.trade_datetime <= end_datetime
            ).order_by(MinuteKline.trade_datetime.asc()).all()

            if not klines:
                return pl.DataFrame(schema={
                    'symbol': pl.Utf8,
                    'trade_datetime': pl.Datetime,
                    'open': pl.Float64,
                    'high': pl.Float64,
                    'low': pl.Float64,
                    'close': pl.Float64,
                    'volume': pl.Float64,
                    'amount': pl.Float64,
                })

            rows = [kline.to_dict() for kline in klines]
            return pl.DataFrame(rows)

        except Exception as e:
            logger.error(f"Error getting minute klines for {symbol}: {e}")
            return pl.DataFrame()

    def get_latest_minute_kline(self, symbol: str) -> Optional[Dict]:
        """获取最新的分钟K线

        Args:
            symbol: 股票代码

        Returns:
            K线数据字典
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)

            kline = self.session.query(MinuteKline).filter(
                MinuteKline.symbol == normalized_symbol
            ).order_by(MinuteKline.trade_datetime.desc()).first()

            if kline:
                return kline.to_dict()
            return None

        except Exception as e:
            logger.error(f"Error getting latest minute kline for {symbol}: {e}")
            return None

    # ==================== 批量写入 ====================

    def batch_insert_daily_klines(self, klines: List[DailyKline]) -> bool:
        """批量插入日K线数据（使用 upsert 避免重复键冲突）

        Args:
            klines: DailyKline对象列表

        Returns:
            成功返回True
        """
        if not klines:
            return True

        try:
            from sqlalchemy.dialects.postgresql import insert

            # 转换为字典列表
            data_list = []
            for kline in klines:
                data_list.append({
                    'symbol': kline.symbol,
                    'trade_date': kline.trade_date,
                    'open': kline.open,
                    'high': kline.high,
                    'low': kline.low,
                    'close': kline.close,
                    'volume': kline.volume,
                    'amount': kline.amount,
                    'turnover_rate': kline.turnover_rate,
                    'remark': getattr(kline, 'remark', None),
                })

            # 使用 PostgreSQL 的 ON CONFLICT DO UPDATE
            stmt = insert(DailyKline).values(data_list)
            stmt = stmt.on_conflict_do_update(
                index_elements=['symbol', 'trade_date'],
                set_={
                    'open': stmt.excluded.open,
                    'high': stmt.excluded.high,
                    'low': stmt.excluded.low,
                    'close': stmt.excluded.close,
                    'volume': stmt.excluded.volume,
                    'amount': stmt.excluded.amount,
                    'turnover_rate': stmt.excluded.turnover_rate,
                }
            )

            self.session.execute(stmt)
            self.session.commit()

            logger.info(f"Successfully upserted {len(klines)} daily klines")
            return True

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error batch upserting daily klines: {e}")
            return False

    def batch_insert_minute_klines(self, klines: List[MinuteKline]) -> bool:
        """批量插入分钟K线数据

        Args:
            klines: MinuteKline对象列表

        Returns:
            成功返回True
        """
        try:
            self.session.add_all(klines)
            self.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error batch inserting minute klines: {e}")
            self.session.rollback()
            return False

    def batch_get_recent_klines(
        self,
        symbols: List[str],
        days: int = 120
    ) -> Dict[str, List[Dict]]:
        """批量查询多只股票最近N天的K线数据

        Args:
            symbols: 股票代码列表
            days: 查询最近N天的数据

        Returns:
            字典 {symbol: [kline_dict, ...]}, 按日期升序
        """
        if not symbols:
            return {}

        try:
            # 构建标准化映射
            symbol_mapping = {}  # normalized -> original
            normalized_symbols = []
            for original in symbols:
                normalized = self._normalize_symbol(original)
                normalized_symbols.append(normalized)
                symbol_mapping[normalized] = original

            # 使用子查询获取每只股票的最新N条记录
            # 方案：为每只股票分别获取，但合并到一个查询中
            from sqlalchemy import literal_column
            from sqlalchemy.sql import union_all

            # 由于需要每只股票的最近N条，使用循环是必要的
            # 但我们可以优化为使用窗口函数（如果数据库支持）
            result = {}

            for normalized in set(normalized_symbols):  # 去重
                klines = self.session.query(DailyKline).filter(
                    DailyKline.symbol == normalized
                ).order_by(DailyKline.trade_date.desc()).limit(days).all()

                # 转换为字典列表，按日期升序排列
                original_symbol = symbol_mapping[normalized]
                if klines:
                    result[original_symbol] = [k.to_dict() for k in reversed(klines)]
                else:
                    result[original_symbol] = []

            return result

        except Exception as e:
            logger.error(f"Error batch getting recent klines: {e}")
            return {symbol: [] for symbol in symbols}

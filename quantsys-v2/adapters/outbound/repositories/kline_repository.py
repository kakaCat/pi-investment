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


# to_dict() 输出的显式 schema。
# 不用 pl.DataFrame(rows) 默认推断：infer_schema_length=100 只采样前 100 行，
# 某列前 100 行全 NULL 被判 Null 类型，第 101+ 行非空值 append 直接 ComputeError
# （2026-08-04 事故：turnover_rate 老数据 NULL 近期回填 0.0 / remark 被回填任务写入错误字符串）
_DAILY_KLINE_SCHEMA = {
    'symbol': pl.Utf8,
    'trade_date': pl.Utf8,
    'open': pl.Float64,
    'high': pl.Float64,
    'low': pl.Float64,
    'close': pl.Float64,
    'volume': pl.Float64,
    'amount': pl.Float64,
    'turnover_rate': pl.Float64,
    'remark': pl.Utf8,
    'source': pl.Utf8,
}

_MINUTE_KLINE_SCHEMA = {
    'symbol': pl.Utf8,
    'trade_datetime': pl.Utf8,
    'open': pl.Float64,
    'high': pl.Float64,
    'low': pl.Float64,
    'close': pl.Float64,
    'volume': pl.Float64,
    'amount': pl.Float64,
}


def _rows_to_df(rows: list, schema: dict) -> pl.DataFrame:
    """to_dict rows → polars DataFrame（显式 schema，按 rows 实际键取子集）"""
    if not rows:
        return pl.DataFrame(schema=schema)
    sub_schema = {k: v for k, v in schema.items() if k in rows[0]}
    return pl.DataFrame(rows, schema=sub_schema)


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
            self._safe_rollback()
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
                    source=kline_dict.get('source'),
                )
                kline_objs.append(kline)

            # 使用batch_insert_daily_klines保存
            result = self.batch_insert_daily_klines(kline_objs)
            return len(klines) if result else 0

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in save_klines: {e}")
            return 0

    def save_daily_klines(self, klines: List[Dict]) -> int:
        """批量保存日K线数据（UPSERT，dict 列表契约）

        旧 BaseRepository 时代契约，ORM 重构（8f06ae1）时丢失，
        2026-08-06 恢复——storage_stage._write_daily_klines 与
        data_backfiller 仍在调用，缺失即 AttributeError。

        与 save_klines 的差异（保持旧契约语义）:
        - 按 (symbol, trade_date) 入参内去重（旧实现行为）
        - 失败抛异常而非静默返回 0（调用方 data_backfiller 依赖异常重试）

        Args:
            klines: K线数据列表，每个元素包含 symbol, trade_date,
                open, high, low, close, volume，可选 amount, turnover_rate

        Returns:
            成功写入（去重后）的记录数

        Raises:
            Exception: 数据库写入失败
        """
        if not klines:
            return 0

        # 标准化 + 按 (symbol, trade_date) 去重（对齐旧 execute_batch 实现）
        seen_keys = set()
        kline_objs = []
        for kline in klines:
            symbol = self._normalize_symbol(str(kline['symbol']))
            trade_date = kline['trade_date']
            unique_key = (symbol, str(trade_date))
            if unique_key in seen_keys:
                continue
            seen_keys.add(unique_key)
            kline_objs.append(DailyKline(
                symbol=symbol,
                trade_date=trade_date,
                open=kline.get('open'),
                high=kline.get('high'),
                low=kline.get('low'),
                close=kline.get('close'),
                volume=kline.get('volume'),
                amount=kline.get('amount', 0),
                turnover_rate=kline.get('turnover_rate', 0),
                source=kline.get('source'),
            ))

        if not kline_objs:
            return 0

        if not self.batch_insert_daily_klines(kline_objs):
            raise Exception("保存日K线数据失败: batch upsert 返回 False（详见上方日志）")

        return len(kline_objs)

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
                    result[symbol] = _rows_to_df(klines, _DAILY_KLINE_SCHEMA)
                else:
                    result[symbol] = pl.DataFrame()
            return result
        except Exception as e:
            self._safe_rollback()
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

            return _rows_to_df(rows, _DAILY_KLINE_SCHEMA)

        except Exception as e:
            self._safe_rollback()
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
                return _rows_to_df([kline.to_dict()], _DAILY_KLINE_SCHEMA)
            return None

        except Exception as e:
            self._safe_rollback()
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
            df = _rows_to_df([k.to_dict() for k in reversed(klines)], _DAILY_KLINE_SCHEMA)
            return df

        except Exception as e:
            self._safe_rollback()
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
            self._safe_rollback()
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
            self._safe_rollback()
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
            self._safe_rollback()
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
            self._safe_rollback()
            logger.error(f"Error getting date range for {symbol}: {e}")
            return None

    def get_kline_stats(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """获取K线统计信息

        旧 BaseRepository 时代契约（归档 8f06ae1^），ORM 重构（8f06ae1）时丢失，
        2026-08-06 恢复——FastAPI routes/stock_async.py:54 与 Flask routes/stock.py:119
        经 ds.kline.get_kline_stats 调用（ds.kline = KlineORMRepository），
        缺失即 AttributeError（个股详情接口 klineDays 恒为 0）。

        Args:
            symbol: 股票代码（可带或不带交易所后缀）
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            统计信息字典: count, max_high, min_low, avg_close,
            total_volume, total_amount；无数据返回 {}
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)

            result = self.session.query(
                func.count().label('count'),
                func.max(DailyKline.high).label('max_high'),
                func.min(DailyKline.low).label('min_low'),
                func.avg(DailyKline.close).label('avg_close'),
                func.sum(DailyKline.volume).label('total_volume'),
                func.sum(DailyKline.amount).label('total_amount'),
            ).filter(
                DailyKline.symbol == normalized_symbol,
                DailyKline.trade_date >= start_date,
                DailyKline.trade_date <= end_date,
            ).first()

            if not result or not result[0]:
                return {}
            return dict(result._mapping)

        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting kline stats for {symbol}: {e}")
            return {}

    def get_trading_days(
        self,
        start_date: str,
        end_date: str,
        symbol: Optional[str] = None
    ) -> List[str]:
        """获取指定日期范围内 daily_klines 有数据的交易日

        旧 BaseRepository 时代契约（归档 8f06ae1^），ORM 重构（8f06ae1）时丢失，
        2026-08-06 恢复——data_gap_detector 需要"实际有数据的交易日"比对交易日历算缺失。
        丢失期间 data_gap_detector.py 以 (symbol, start, end) 位置参数调用不存在的方法，
        AttributeError 被其 except 吞掉，缺口检测静默退化为"全部交易日缺失"。
        恢复时顺带修正调用方参数顺序，并新增可选 symbol 过滤（归档语义为全市场去重日期）。

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            symbol: 可选；传入时只统计该股票有数据的交易日

        Returns:
            交易日列表（YYYY-MM-DD 字符串，升序）
        """
        try:
            query = self.session.query(DailyKline.trade_date).filter(
                DailyKline.trade_date >= start_date,
                DailyKline.trade_date <= end_date,
            )
            if symbol:
                query = query.filter(
                    DailyKline.symbol == self._normalize_symbol(symbol)
                )
            rows = query.distinct().order_by(DailyKline.trade_date.asc()).all()
            return [str(row[0]) for row in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting trading days: {e}")
            return []

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
            return _rows_to_df(rows, _MINUTE_KLINE_SCHEMA)

        except Exception as e:
            self._safe_rollback()
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
            self._safe_rollback()
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
                    'source': getattr(kline, 'source', None),
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
                    'source': stmt.excluded.source,
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
            self._safe_rollback()
            logger.error(f"Error batch getting recent klines: {e}")
            return {symbol: [] for symbol in symbols}

    # ==================== 全市场聚合查询（市场情绪分析用） ====================
    # 注意：daily_klines 中指数代码与股票代码冲突（如 '000001' 是平安银行
    # 而非上证指数），因此市场维度指标一律用全市场聚合计算，不读指数代码。

    def get_market_breadth(self, lookback_days: int = 10) -> Optional[Dict]:
        """全市场涨跌家数（最新交易日，与其前一交易日比较）

        Returns:
            {data_date, up_count, down_count, flat_count, total,
             up_percentage, ratio}；无数据返回 None
        """
        from sqlalchemy import text
        try:
            rows = self.session.execute(text("""
                WITH recent AS (
                    SELECT symbol, trade_date, close,
                           ROW_NUMBER() OVER (PARTITION BY symbol
                                              ORDER BY trade_date DESC) AS rn
                    FROM quant.daily_klines
                    WHERE trade_date >= CURRENT_DATE - (:days || ' days')::interval
                )
                SELECT a.trade_date AS data_date,
                       COUNT(*) FILTER (WHERE a.close > b.close) AS up_count,
                       COUNT(*) FILTER (WHERE a.close < b.close) AS down_count,
                       COUNT(*) FILTER (WHERE a.close = b.close) AS flat_count
                FROM recent a
                JOIN recent b ON a.symbol = b.symbol AND b.rn = 2
                WHERE a.rn = 1
                GROUP BY a.trade_date
                ORDER BY a.trade_date DESC
                LIMIT 1
            """), {'days': lookback_days}).fetchone()

            if not rows or rows[1] is None:
                return None

            data_date, up, down, flat = rows[0], int(rows[1]), int(rows[2]), int(rows[3])
            total = up + down + flat
            if total == 0:
                return None
            return {
                'data_date': data_date.isoformat() if data_date else None,
                'up_count': up,
                'down_count': down,
                'flat_count': flat,
                'total': total,
                'up_percentage': round(up / total * 100, 2),
                'ratio': round(up / down, 2) if down > 0 else 999,
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_market_breadth: {e}")
            return None

    def get_market_turnover_by_day(self, days: int = 30) -> List[Dict]:
        """全市场成交量按日汇总（倒序）

        注：用 volume（股数）而非 amount——腾讯 K 线源不写 amount 字段，
        2026-07 起 daily_klines 近期数据的 amount 全为 0。

        Returns:
            [{trade_date, total_volume}]，最新在前
        """
        from sqlalchemy import text
        try:
            rows = self.session.execute(text("""
                SELECT trade_date, SUM(volume) AS total_volume
                FROM quant.daily_klines
                WHERE trade_date >= CURRENT_DATE - (:days || ' days')::interval
                GROUP BY trade_date
                ORDER BY trade_date DESC
                LIMIT :days
            """), {'days': days}).fetchall()
            return [{'trade_date': r[0].isoformat() if r[0] else None,
                     'total_volume': float(r[1] or 0)} for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_market_turnover_by_day: {e}")
            return []

    def get_market_daily_returns(self, days: int = 40) -> List[Dict]:
        """全市场等权日收益序列（倒序），用于波动率与趋势计算

        Returns:
            [{trade_date, avg_return}]（小数，非百分比），最新在前
        """
        from sqlalchemy import text
        try:
            rows = self.session.execute(text("""
                WITH k AS (
                    SELECT symbol, trade_date, close,
                           LAG(close) OVER (PARTITION BY symbol
                                            ORDER BY trade_date) AS prev_close
                    FROM quant.daily_klines
                    WHERE trade_date >= CURRENT_DATE - (:days || ' days')::interval
                )
                SELECT trade_date, AVG((close - prev_close) / NULLIF(prev_close, 0)) AS avg_return
                FROM k
                WHERE prev_close IS NOT NULL AND prev_close > 0
                GROUP BY trade_date
                ORDER BY trade_date DESC
                LIMIT :days
            """), {'days': days}).fetchall()
            return [{'trade_date': r[0].isoformat() if r[0] else None,
                     'avg_return': float(r[1]) if r[1] is not None else None}
                    for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_market_daily_returns: {e}")
            return []

    def get_new_high_low_counts(self, window_days: int = 365) -> Optional[Dict]:
        """创 window 期内新高/新低的股票家数（最新交易日收盘价判定）

        Returns:
            {data_date, new_high_count, new_low_count}；无数据返回 None
        """
        from sqlalchemy import text
        try:
            row = self.session.execute(text("""
                WITH recent AS (
                    SELECT symbol, trade_date, close,
                           MAX(close) OVER (PARTITION BY symbol) AS max_close,
                           MIN(close) OVER (PARTITION BY symbol) AS min_close,
                           ROW_NUMBER() OVER (PARTITION BY symbol
                                              ORDER BY trade_date DESC) AS rn
                    FROM quant.daily_klines
                    WHERE trade_date >= CURRENT_DATE - (:days || ' days')::interval
                )
                SELECT trade_date AS data_date,
                       COUNT(*) FILTER (WHERE close >= max_close) AS new_high_count,
                       COUNT(*) FILTER (WHERE close <= min_close) AS new_low_count
                FROM recent
                WHERE rn = 1
                GROUP BY trade_date
                ORDER BY trade_date DESC
                LIMIT 1
            """), {'days': window_days}).fetchone()

            if not row:
                return None
            return {
                'data_date': row[0].isoformat() if row[0] else None,
                'new_high_count': int(row[1] or 0),
                'new_low_count': int(row[2] or 0),
            }
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_new_high_low_counts: {e}")
            return None

    def get_active_symbols(self, days: int = 15, min_days: int = 3,
                           limit: int = 500) -> List[str]:
        """近期有 K 线且成交活跃的股票（按成交量降序）

        用途：index_constituents 为空时，机会扫描热门池的 fallback。
        """
        from sqlalchemy import text
        try:
            rows = self.session.execute(text("""
                SELECT symbol, SUM(volume) AS tv
                FROM quant.daily_klines
                WHERE trade_date >= CURRENT_DATE - (:days || ' days')::interval
                GROUP BY symbol
                HAVING COUNT(*) >= :min_days
                ORDER BY tv DESC
                LIMIT :limit
            """), {'days': days, 'min_days': min_days, 'limit': limit}).fetchall()
            return [r[0] for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_active_symbols: {e}")
            return []

    def get_market_breadth_history(self, days: int = 120) -> List[Dict]:
        """全市场历史 breadth + 量能比序列（M1 regime 回填用，RFC 007）

        逐日聚合：涨跌平家数（close vs 前收）+ 总量 + 量能比（近5日均量/近20日均量）。
        注：用 volume（股数）而非 amount——腾讯 K 线源近期数据 amount 为 0。

        Returns:
            [{trade_date, up, down, flat, total_volume, volume_ratio}]，最新在前；
            无数据返回 []
        """
        from sqlalchemy import text
        try:
            rows = self.session.execute(text("""
                WITH px AS (
                    SELECT symbol, trade_date, close,
                           LAG(close) OVER (PARTITION BY symbol
                                            ORDER BY trade_date) AS prev_close,
                           volume
                    FROM quant.daily_klines
                    WHERE trade_date > CURRENT_DATE - (:days * 2 || ' days')::interval
                ),
                daily AS (
                    SELECT trade_date,
                           COUNT(*) FILTER (WHERE prev_close IS NOT NULL
                                            AND close > prev_close) AS up,
                           COUNT(*) FILTER (WHERE prev_close IS NOT NULL
                                            AND close < prev_close) AS down,
                           COUNT(*) FILTER (WHERE prev_close IS NOT NULL
                                            AND close = prev_close) AS flat,
                           SUM(volume) AS total_volume
                    FROM px GROUP BY trade_date
                )
                SELECT trade_date, up, down, flat, total_volume,
                       AVG(total_volume) OVER (ORDER BY trade_date
                           ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)
                       / NULLIF(AVG(total_volume) OVER (ORDER BY trade_date
                           ROWS BETWEEN 24 PRECEDING AND 5 PRECEDING), 0) AS vr
                FROM daily
                ORDER BY trade_date DESC LIMIT :days
            """), {'days': days}).fetchall()
            return [{
                'trade_date': r[0],
                'up': int(r[1] or 0), 'down': int(r[2] or 0), 'flat': int(r[3] or 0),
                'total_volume': float(r[4] or 0),
                'volume_ratio': float(r[5]) if r[5] is not None else None,
            } for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_market_breadth_history: {e}")
            return []

    def get_latest_trade_date(self) -> Optional[str]:
        """最新交易日（daily_klines 最大 trade_date）。

        用途：M1 市场感知快照的默认交易日判定。
        Returns: 'YYYY-MM-DD' 或 None
        """
        from sqlalchemy import func
        try:
            d = self.session.query(func.max(DailyKline.trade_date)).scalar()
            return d.isoformat() if d else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_latest_trade_date: {e}")
            return None

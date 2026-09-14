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
from typing import Any, List, Dict, Optional, Set
from datetime import date, datetime, timedelta
import polars as pl
import structlog

from sqlalchemy import desc, and_, func, select
from infrastructure.persistence.orm import BaseORMRepository, get_session
from infrastructure.persistence.orm.models import DailyKline, IndexDaily, MinuteKline, Stock
# 指数与个股分表（2026-09-11 w-f4aa1f6a）：指数键带市场后缀，解析统一走 symbol_classifier，
# 绝不在调用方手写后缀（399xxx 恒 .SZ，其余白名单 .SH，歧义码由 stocks 表定夺）。
# 该模块只依赖标准库 + 惰性 DB 访问，无循环导入。
from utils.symbol_classifier import resolve_index_symbol
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


def filter_index_rows(klines: List[DailyKline]) -> 'tuple[List[DailyKline], List[str]]':
    """剔除指数行 —— daily_klines 有约束 chk_daily_klines_no_indexrows。

    约束定义：symbol !~ '^399' AND symbol <> ALL(ARRAY['000300','399300'])。
    指数价格按 2026-09-11 分表设计存 quant.index_daily（键带市场后缀，如 399001.SZ），
    本表只放个股。任何调用方漏过滤指数码时，upsert 都会撞约束 → CheckViolation →
    整批回滚 + 日志刷 error（实证：2026-09-11 18:40 与 2026-09-12 00:25-00:26 共 11 次，
    看板事件 bc64397b / d0f549d1 / bbb56df6 / 585f5a3f / f1b3a7f8）。

    收口放在本模块，是为了让所有写入路径（save_kline_data / save_klines /
    save_daily_klines / batch_insert_daily_klines 的直接调用方）都拿到同一道闸门。

    Args:
        klines: DailyKline 对象列表

    Returns:
        (保留的行, 被剔除的指数代码去重列表)
    """
    if not klines:
        return [], []
    from utils.symbol_classifier import is_index_symbol
    # 先取唯一代码再判定：is_index_symbol 对白名单码要查 stocks 表，按行判会放大查询次数
    unique_symbols = {str(getattr(k, 'symbol', '') or '').strip() for k in klines}
    index_symbols = {s for s in unique_symbols if s and is_index_symbol(s)}
    if not index_symbols:
        return list(klines), []
    kept = [k for k in klines if str(getattr(k, 'symbol', '') or '').strip() not in index_symbols]
    return kept, sorted(index_symbols)

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

    # ==================== 指数日线（独立表） ====================

    def get_index_daily_klines(
        self,
        index_symbol: str,
        start_date: str,
        end_date: str,
        fields: List[str] = None
    ) -> List[Dict[str, Any]]:
        """读取指数日线（quant.index_daily，键为带市场后缀的指数代码，如 000300.SH）。

        2026-09-11（w-f4aa1f6a）指数与个股**分表**的原因：
          ① 语义不同——指数 volume 是成分股聚合（量纲与个股不同）、无复权/停牌/涨跌停，
             混表曾导致「amount = volume × close」把深证成指估成 949.86 万亿元（w-23c70356 清理过）；
          ② 命名空间——daily_klines 全是裸 6 位码，指数与深市股票同码冲突
             （000001 平安银行 / 000016 *ST康佳A / 000905 厦门港务 …），指数价格实际无处安放。
        调用方应先经 utils.symbol_classifier.resolve_index_symbol 规范化，非指数不要走本方法。

        2026-09-14（w-32314d00，REQ-24e15d B4-c3-b）：由 f-string 拼 SQL + text() 改为
        Core select()。顺带修一个静默缺陷——旧实现的默认列序取自 **set**（allowed），
        集合迭代序随进程哈希种子变化，fields 不传时返回的 dict 键序每次运行都可能不同；
        现固定为确定性元组序。
        """
        _DEFAULT_COLS = ('symbol', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'amount')
        allowed = set(_DEFAULT_COLS)
        cols = [c for c in (fields or _DEFAULT_COLS) if c in allowed] or list(_DEFAULT_COLS)
        try:
            stmt = (
                select(*(getattr(IndexDaily, c) for c in cols))
                .where(
                    IndexDaily.symbol == index_symbol,
                    IndexDaily.trade_date >= start_date,
                    IndexDaily.trade_date <= end_date,
                )
                .order_by(IndexDaily.trade_date.asc())
            )
            rows = self.session.execute(stmt).mappings().all()
            out: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                if d.get('trade_date') is not None and hasattr(d['trade_date'], 'isoformat'):
                    d['trade_date'] = d['trade_date'].isoformat()
                out.append(d)
            return out
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting index daily klines for {index_symbol}: {e}")
            return []

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

            # 构建查询（2026-09-11 修复 w-f4aa1f6a）：start/end 为 None 时不能作为
            # 比较值使用——SQLAlchemy 会抛 "Only '=', '!=', 'is_()', ... can be used
            # with None/True/False"，整条 K 线查询随之失败
            #（实证：error_event 39510d03，2026-09-11 01:17:05，300677 日线获取失败）。
            # 只在实际提供了边界时才加过滤条件。
            query = self.session.query(DailyKline).filter(
                DailyKline.symbol == normalized_symbol
            )
            if start_date:
                query = query.filter(DailyKline.trade_date >= start_date)
            if end_date:
                query = query.filter(DailyKline.trade_date <= end_date)
            query = query.order_by(DailyKline.trade_date.asc())

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
        经 kline_repo.get_kline_stats 调用（kline_repo = KlineORMRepository），
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

    def get_recent_trading_days(self, days: int = 120) -> List[str]:
        """最近 N 个**自然日**内有数据的交易日（升序字符串列表）。

        2026-09-14（w-32314d00，REQ-24e15d B2）：原实现在
        adapters/inbound/fastapi_app/routes/data_quality_async.py 的因子新鲜度门禁里，
        是 session.execute(text("SELECT DISTINCT trade_date FROM quant.daily_klines
        WHERE trade_date > CURRENT_DATE - INTERVAL '120 days' ORDER BY trade_date"))。
        注意边界语义是 **严格大于** today-N 天（不是 >=），故这里照搬 ">"，
        不复用 get_trading_days（那个是闭区间 >= / <=），以免安静地多算一天、
        进而让 stale_days 差 1。
        """
        from datetime import date as _date, timedelta as _timedelta
        cutoff = _date.today() - _timedelta(days=days)
        try:
            rows = (
                self.session.query(DailyKline.trade_date)
                .filter(DailyKline.trade_date > cutoff)
                .distinct()
                .order_by(DailyKline.trade_date.asc())
                .all()
            )
            return [str(r[0]) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting recent trading days: {e}")
            return []

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

    def get_first_close_on_or_after(self, symbol: str, start_date) -> Optional[float]:
        """返回 >= start_date 的**第一个交易日**收盘价；无数据返回 None。

        2026-09-13（w-32314d00，REQ-24e15d t4）：`infrastructure/jobs/verification_job.py` 与
        `weekly_report_job.py` 原先各自手写 `SELECT close FROM quant.daily_klines … LIMIT 1`，
        且是"先拿仓储的 session 再写裸 SQL"的半迁移写法 —— 这里把该查询收进仓储。
        """
        try:
            row = (
                self.session.query(DailyKline.close)
                .filter(DailyKline.symbol == self._normalize_symbol(symbol))
                .filter(DailyKline.trade_date >= start_date)
                .order_by(DailyKline.trade_date.asc())
                .limit(1)
                .first()
            )
            return float(row[0]) if row and row[0] is not None else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting first close for {symbol}: {e}")
            return None

    # ==================== 指数收盘价（quant.index_daily） ====================
    # 2026-09-13（w-32314d00，REQ-24e15d t4）：verification_job / weekly_report_job /
    # risk_check_job 三处都在读"创业板指 399006 的区间收益"，写法清一色是
    #   SELECT close FROM quant.daily_klines WHERE symbol='399006' ...
    # 而 daily_klines 里 **399 族一行都没有**（实测 0 行；指数在 quant.index_daily，
    # 399006.SZ 有 268 行）→ 三处**全部静默返回 0.0**：周报/验证的"基准收益"长期是 0，
    # 超额收益归因因此失真。收敛成本方法后，此类错误不会再各写一遍。

    def _resolve_index_key(self, index_symbol: str) -> Optional[str]:
        """把指数标识解析为 index_daily 的键；非指数/无法解析返回 None。"""
        key = resolve_index_symbol(index_symbol)
        if not key:
            logger.warning("resolve_index_failed", given=index_symbol,
                           hint="非指数代码或与深市个股同码；指数请传 399006 / 000300.SH")
        return key

    def get_first_index_close_on_or_after(self, index_symbol: str, start_date) -> Optional[float]:
        """返回 >= start_date 的**第一个交易日**指数收盘价（quant.index_daily）。

        非指数代码或无数据 → None（**不静默返回 0.0**，调用方须自行区分"未取到"与"收益为 0"）。
        """
        key = self._resolve_index_key(index_symbol)
        if not key:
            return None
        try:
            row = (
                self.session.query(IndexDaily.close)
                .filter(IndexDaily.symbol == key)
                .filter(IndexDaily.trade_date >= start_date)
                .order_by(IndexDaily.trade_date.asc())
                .limit(1)
                .first()
            )
            return float(row[0]) if row and row[0] is not None else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting first index close for {index_symbol}: {e}")
            return None

    def get_last_index_close_on_or_before(self, index_symbol: str, end_date) -> Optional[float]:
        """返回 <= end_date 的**最后一个交易日**指数收盘价；非指数或无数据 → None。"""
        key = self._resolve_index_key(index_symbol)
        if not key:
            return None
        try:
            row = (
                self.session.query(IndexDaily.close)
                .filter(IndexDaily.symbol == key)
                .filter(IndexDaily.trade_date <= end_date)
                .order_by(IndexDaily.trade_date.desc())
                .limit(1)
                .first()
            )
            return float(row[0]) if row and row[0] is not None else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting last index close for {index_symbol}: {e}")
            return None

    def get_index_return(self, index_symbol: str, start_date, end_date) -> Optional[float]:
        """区间收益（小数）= 末值/首值 - 1；任一端取不到返回 None。

        口径：首值 = >= start_date 的第一个交易日收盘；末值 = <= end_date 的最后一个交易日收盘。
        """
        first = self.get_first_index_close_on_or_after(index_symbol, start_date)
        if not first:
            return None
        last = self.get_last_index_close_on_or_before(index_symbol, end_date)
        if not last:
            return None
        return (last - first) / first

    def get_latest_index_close(self, index_symbol: str) -> Optional[float]:
        """最新一个交易日的指数收盘价；非指数或无数据 → None。"""
        return self.get_last_index_close_on_or_before(index_symbol, date.today().isoformat())

    def get_last_close_on_or_before(self, symbol: str, end_date) -> Optional[float]:
        """返回 <= end_date 的**最后一个交易日**收盘价；无数据返回 None。"""
        try:
            row = (
                self.session.query(DailyKline.close)
                .filter(DailyKline.symbol == self._normalize_symbol(symbol))
                .filter(DailyKline.trade_date <= end_date)
                .order_by(DailyKline.trade_date.desc())
                .limit(1)
                .first()
            )
            return float(row[0]) if row and row[0] is not None else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting last close for {symbol}: {e}")
            return None

    def get_latest_close(self, symbol: str) -> Optional[float]:
        """最新一个交易日的收盘价（按 trade_date 倒序第一条）；无数据/收盘为 NULL → None。

        2026-09-14（w-32314d00，REQ-24e15d）：原实现是
        application/services/opportunity_to_watch_rule_service.py 的
        `_latest_close_from_db`（裸 SQL：SELECT close FROM quant.daily_klines
        WHERE symbol=:s ORDER BY trade_date DESC LIMIT 1）。

        与 get_last_close_on_or_before 的差异（勿合并）：本方法
          · **不加 trade_date <= end_date 过滤**；
          · **不做后缀归一化**（原 SQL 的 symbol 原样匹配，调用方传的就是 6 位码）。
        返回值口径与原实现逐值一致：`float(row[0]) if row and row[0] is not None else None`。

        异常策略：**回滚后上抛**——调用方的 `except → logger.warning('读取最新收盘价失败')
        → return None` 是既有容错路径，仓储吞异常会让该留痕静默消失。
        """
        try:
            row = (
                self.session.query(DailyKline.close)
                .filter(DailyKline.symbol == symbol)
                .order_by(DailyKline.trade_date.desc())
                .limit(1)
                .first()
            )
        except Exception:
            self._safe_rollback()
            raise
        return float(row[0]) if row and row[0] is not None else None

    def list_distinct_trade_dates_since(self, start_date) -> Set[date]:
        """`trade_date >= start_date` 的全部交易日（DISTINCT，去重集合）。

        2026-09-14（w-32314d00，REQ-24e15d）：原实现是
        application/services/data_pipeline_service.py 的 `load_trading_calendar_from_db`
        在 quant.trading_calendar 为空时的回退路径（裸 SQL：SELECT DISTINCT trade_date
        FROM quant.daily_klines WHERE trade_date >= %s ORDER BY trade_date）。

        语义对齐：返回 **set[datetime.date]**（原实现 `_rows_to_set` 的结果类型），
        边界是闭区间 `>=`；ORDER BY 对 set 无影响，保留以对齐 SQL 文本。

        异常策略：**回滚后上抛**——调用方有外层 `except Exception → set()` 与
        `logger.warning('trading_calendar_unavailable')`，吞异常会让"日历不可用"
        失去留痕、并把故障伪装成"空日历"（正是 2026-09-11 那类静默降级）。
        """
        try:
            rows = (
                self.session.query(DailyKline.trade_date)
                .filter(DailyKline.trade_date >= start_date)
                .distinct()
                .order_by(DailyKline.trade_date.asc())
                .all()
            )
        except Exception:
            self._safe_rollback()
            raise
        return {r[0] for r in rows}

    def batch_insert_daily_klines(self, klines: List[DailyKline]) -> bool:
        """批量插入日K线数据（使用 upsert 避免重复键冲突）

        Args:
            klines: DailyKline对象列表

        Returns:
            成功返回True
        """
        if not klines:
            return True

        # 统一收口：指数行不入 daily_klines（约束 chk_daily_klines_no_indexrows）。
        # 必须在下方 auto-create stocks 元数据之前剔除——指数不是股票，
        # 提前放行会为指数造出假个股行，再撞约束整批回滚。
        klines, skipped_index = filter_index_rows(klines)
        if skipped_index:
            logger.warning(
                f"Skip index rows for daily_klines (约束 chk_daily_klines_no_indexrows): "
                f"{skipped_index} —— 指数价格请写 quant.index_daily")
        if not klines:
            # 全部都是指数行：无事可做，不是失败（调用方不必因此重试）
            return True

        try:
            from sqlalchemy.dialects.postgresql import insert

            # 1. 确保所有股票元数据存在（去重）
            from adapters.shared.market_helpers import infer_market
            symbols = list(set(kline.symbol for kline in klines))
            uncreatable = []
            for symbol in symbols:
                stock = self.session.query(Stock).filter(Stock.symbol == symbol).first()
                if not stock:
                    # 自动创建股票元数据（最小字段集）；market 必须可从代码推断，
                    # 否则跳过该标的（禁止用 'unknown' 占位触发 chk_stocks_market）
                    market = infer_market(symbol)
                    if market is None:
                        uncreatable.append(symbol)
                        continue
                    stock = Stock(
                        symbol=symbol,
                        name=symbol,  # 临时使用代码作为名称
                        market=market
                    )
                    self.session.add(stock)
                    logger.warning(f"Auto-created stock metadata for {symbol} (K线插入时缺失, market={market})")
            if uncreatable:
                logger.warning(
                    f"Skip klines for symbols without inferable market: {uncreatable}")
                klines = [k for k in klines if k.symbol not in set(uncreatable)]
            self.session.flush()  # 提交股票元数据

            # 2. 转换为字典列表
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

            if not data_list:
                # 全部标的都因 market 不可推断被跳过：不能带空列表进 insert().values([])
                logger.warning("No insertable klines after market inference filter")
                return True

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
                    # source 是"数据来源"的溯源字段：调用方没带来源时（如每日同步的
                    # KlineData 不带 source）不能把既有来源**抹成 NULL** —— 那会让
                    # source 逐日流失，最终无法回答"这行是谁写的"。改用 coalesce：
                    # 有新值才覆盖。2026-09-13（w-32314d00，REQ-24e15d t4）。
                    'source': func.coalesce(stmt.excluded.source, DailyKline.source),
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

        2026-09-14（B4-c3-b）：原 text() CTE 迁为 Core select()。窗口起点仍用
        **服务端** CURRENT_DATE（不退化为客户端日期），只把 interval 换成绑定参数。
        """
        try:
            cutoff = func.current_date() - timedelta(days=lookback_days)
            recent = (
                select(
                    DailyKline.symbol.label('symbol'),
                    DailyKline.trade_date.label('trade_date'),
                    DailyKline.close.label('close'),
                    func.row_number().over(
                        partition_by=DailyKline.symbol,
                        order_by=DailyKline.trade_date.desc(),
                    ).label('rn'),
                )
                .where(DailyKline.trade_date >= cutoff)
                .subquery('recent')
            )
            a = recent.alias('a')
            b = recent.alias('b')

            row = self.session.execute(
                select(
                    a.c.trade_date,
                    func.count().filter(a.c.close > b.c.close).label('up_count'),
                    func.count().filter(a.c.close < b.c.close).label('down_count'),
                    func.count().filter(a.c.close == b.c.close).label('flat_count'),
                )
                .join(b, and_(a.c.symbol == b.c.symbol, b.c.rn == 2))
                .where(a.c.rn == 1)
                .group_by(a.c.trade_date)
                .order_by(a.c.trade_date.desc())
                .limit(1)
            ).fetchone()

            if not row or row[1] is None:
                return None

            data_date, up, down, flat = row[0], int(row[1]), int(row[2]), int(row[3])
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
        try:
            rows = self.session.execute(
                select(
                    DailyKline.trade_date,
                    func.sum(DailyKline.volume).label('total_volume'),
                )
                .where(DailyKline.trade_date >= func.current_date() - timedelta(days=days))
                .group_by(DailyKline.trade_date)
                .order_by(DailyKline.trade_date.desc())
                .limit(days)
            ).fetchall()
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
        try:
            k = (
                select(
                    DailyKline.symbol.label('symbol'),
                    DailyKline.trade_date.label('trade_date'),
                    DailyKline.close.label('close'),
                    func.lag(DailyKline.close).over(
                        partition_by=DailyKline.symbol,
                        order_by=DailyKline.trade_date,
                    ).label('prev_close'),
                )
                .where(DailyKline.trade_date >= func.current_date() - timedelta(days=days))
                .subquery('k')
            )
            rows = self.session.execute(
                select(
                    k.c.trade_date,
                    func.avg(
                        (k.c.close - k.c.prev_close) / func.nullif(k.c.prev_close, 0)
                    ).label('avg_return'),
                )
                .where(k.c.prev_close.isnot(None), k.c.prev_close > 0)
                .group_by(k.c.trade_date)
                .order_by(k.c.trade_date.desc())
                .limit(days)
            ).fetchall()
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
        try:
            recent = (
                select(
                    DailyKline.symbol.label('symbol'),
                    DailyKline.trade_date.label('trade_date'),
                    DailyKline.close.label('close'),
                    func.max(DailyKline.close).over(
                        partition_by=DailyKline.symbol
                    ).label('max_close'),
                    func.min(DailyKline.close).over(
                        partition_by=DailyKline.symbol
                    ).label('min_close'),
                    func.row_number().over(
                        partition_by=DailyKline.symbol,
                        order_by=DailyKline.trade_date.desc(),
                    ).label('rn'),
                )
                .where(DailyKline.trade_date >= func.current_date() - timedelta(days=window_days))
                .subquery('recent')
            )
            row = self.session.execute(
                select(
                    recent.c.trade_date.label('data_date'),
                    func.count().filter(recent.c.close >= recent.c.max_close).label('new_high_count'),
                    func.count().filter(recent.c.close <= recent.c.min_close).label('new_low_count'),
                )
                .where(recent.c.rn == 1)
                .group_by(recent.c.trade_date)
                .order_by(recent.c.trade_date.desc())
                .limit(1)
            ).fetchone()

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
        try:
            total_volume = func.sum(DailyKline.volume).label('tv')
            rows = self.session.execute(
                select(DailyKline.symbol, total_volume)
                .where(DailyKline.trade_date >= func.current_date() - timedelta(days=days))
                .group_by(DailyKline.symbol)
                .having(func.count() >= min_days)
                .order_by(total_volume.desc())
                .limit(limit)
            ).fetchall()
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
        try:
            px = (
                select(
                    DailyKline.symbol.label('symbol'),
                    DailyKline.trade_date.label('trade_date'),
                    DailyKline.close.label('close'),
                    func.lag(DailyKline.close).over(
                        partition_by=DailyKline.symbol,
                        order_by=DailyKline.trade_date,
                    ).label('prev_close'),
                    DailyKline.volume.label('volume'),
                )
                .where(DailyKline.trade_date > func.current_date() - timedelta(days=days * 2))
                .subquery('px')
            )
            daily = (
                select(
                    px.c.trade_date.label('trade_date'),
                    func.count().filter(
                        px.c.prev_close.isnot(None), px.c.close > px.c.prev_close
                    ).label('up'),
                    func.count().filter(
                        px.c.prev_close.isnot(None), px.c.close < px.c.prev_close
                    ).label('down'),
                    func.count().filter(
                        px.c.prev_close.isnot(None), px.c.close == px.c.prev_close
                    ).label('flat'),
                    func.sum(px.c.volume).label('total_volume'),
                )
                .group_by(px.c.trade_date)
                .subquery('daily')
            )
            # SQLAlchemy 的 rows 元组语义：负=PRECEDING、0=CURRENT ROW、正=FOLLOWING
            # （写成正数会渲染成 "4 FOLLOWING AND CURRENT ROW"，PG 直接报 WindowingError）
            ma5 = func.avg(daily.c.total_volume).over(
                order_by=daily.c.trade_date, rows=(-4, 0)
            ).label('ma5')
            ma20 = func.avg(daily.c.total_volume).over(
                order_by=daily.c.trade_date, rows=(-24, -5)
            ).label('ma20')
            rows = self.session.execute(
                select(
                    daily.c.trade_date,
                    daily.c.up,
                    daily.c.down,
                    daily.c.flat,
                    daily.c.total_volume,
                    ma5,
                    ma20,
                )
                .order_by(daily.c.trade_date.desc())
                .limit(days)
            ).fetchall()

            out: List[Dict] = []
            for r in rows:
                # NULLIF(ma20, 0) 的语义放在 Python 侧实现：SQLAlchemy 对 nullif()
                # 硬编码返回类型 Numeric()，会把除法渲染成 numeric 运算，
                # 末位精度与旧 raw SQL 的 double precision 除法不一致
                #（实测 0.9767216403301303 vs 0.9767216403301268）。
                m5, m20 = r[5], r[6]
                ratio = float(m5) / float(m20) if (m5 is not None and m20 not in (None, 0)) else None
                out.append({
                    'trade_date': r[0],
                    'up': int(r[1] or 0), 'down': int(r[2] or 0), 'flat': int(r[3] or 0),
                    'total_volume': float(r[4] or 0),
                    'volume_ratio': ratio,
                })
            return out
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_market_breadth_history: {e}")
            return []

    def has_bar_on_date(self, day) -> bool:
        """某自然日是否已有日K数据（TradingDayGuard 的"是否已收盘并落库"判据）。

        2026-09-14（w-32314d00，REQ-24e15d B3）：原实现在
        application/services/trading_day_guard.py 里用 db_cursor 执行
        "SELECT EXISTS(SELECT 1 FROM quant.daily_klines WHERE trade_date = %s)"，
        与"(SELECT max(trade_date) …)"合并成一次往返。这里拆成两个仓储方法
        （可读性优先；两者都走 daily_klines 的索引，实测各 ~0.1ms）。
        """
        from datetime import date as _date
        d = day
        if isinstance(day, str):
            try:
                d = _date.fromisoformat(day[:10])
            except ValueError:
                return False
        try:
            return self.session.query(DailyKline.trade_date).filter(
                DailyKline.trade_date == d
            ).first() is not None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error checking bar on {day}: {e}")
            return False

    def get_trade_dates_map(self, symbols: List[str], start_date, end_date) -> Dict[str, set]:
        """批量取多只股票在区间内**实际有数据**的交易日集合。

        2026-09-14（w-32314d00，REQ-24e15d B3）：原实现在
        application/services/data_gap_detector.py 里用 array_agg 的裸 SQL 一次查全部，
        失败再逐只回退。这里用一次 ORM 查询 + Python 侧分组（等价语义，
        且不再需要"两种结果形态"的兼容分支）。**没有数据的股票会得到空集合**，
        与调用方原有的"补充空集合"行为一致。
        """
        out: Dict[str, set] = {str(s): set() for s in symbols}
        if not symbols:
            return out
        try:
            rows = (
                self.session.query(DailyKline.symbol, DailyKline.trade_date)
                .filter(DailyKline.symbol.in_([str(s) for s in symbols]))
                .filter(DailyKline.trade_date >= start_date)
                .filter(DailyKline.trade_date <= end_date)
                .order_by(DailyKline.symbol.asc(), DailyKline.trade_date.asc())
                .all()
            )
            for sym, d in rows:
                out.setdefault(str(sym), set()).add(str(d))
            return out
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error getting trade dates map: {e}")
            return out

    def find_duplicate_trade_dates(self, symbol: str, start_date, end_date) -> List[str]:
        """区间内出现重复行的交易日（数据完整性校验用）。

        2026-09-14（w-32314d00，REQ-24e15d B3）：原实现在
        application/services/data_validator.py 里用裸 SQL
        GROUP BY trade_date HAVING COUNT(*) > 1。
        注意：daily_klines 主键是 (symbol, trade_date)，正常不可能重复——
        本方法用于校验历史遗留/异常写入，保留其原语义。
        """
        try:
            rows = (
                self.session.query(
                    DailyKline.trade_date, func.count().label('cnt')
                )
                .filter(DailyKline.symbol == self._normalize_symbol(symbol))
                .filter(DailyKline.trade_date >= start_date)
                .filter(DailyKline.trade_date <= end_date)
                .group_by(DailyKline.trade_date)
                .having(func.count() > 1)
                .order_by(DailyKline.trade_date.asc())
                .all()
            )
            return [str(r[0]) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error finding duplicate trade dates for {symbol}: {e}")
            return []

    def get_kline_coverage(self, expected: str) -> Dict[str, Any]:
        """按标的统计日K线覆盖度（迁移自 daily_jobs_bootstrap._kline_coverage）。

        2026-09-10 的原始修复背景：原判定用全局 max(trade_date)，只要有一只票有当日
        数据就认定"全市场新鲜" → evening_pipeline 直接跳过同步；实测 2026-09-10 时
        5150/5542 只（93%）停在 09-02，缺口被固化近 8 个交易日无人发现。故改为
        按标的覆盖度 + 最陈旧标的日期。

        口径（与原 SQL 逐值一致，已在真实库上比对）：
          · 宇宙 = quant.stocks 中 NOT is_delisted 且 name 不含 退/ST 的标的；
          · covered = 该宇宙中"存在 trade_date >= expected 的日K线"的标的数；
          · oldest_stale = 每只票的 max(trade_date) 中，为 NULL 或 < expected 的**最小值**
            （即"最陈旧的那只票停在哪天"）；全市场都新鲜时为 None；
          · 注意 NOT is_delisted / NOT (name LIKE ...) 遇 NULL 时为 NULL 会被过滤掉 ——
            这是 PG 的三值逻辑，与本方法 .is_(False)/notlike 的语义一致。

        Returns:
            {total, covered, stale, coverage, oldest_stale}
            —— coverage 在 total=0 时取 1.0（无标的口径下不算"不新鲜"）。
        """
        uni_filters = (
            Stock.is_delisted.is_(False),
            Stock.name.notlike('%退%'),
            Stock.name.notlike('%ST%'),
        )
        try:
            universe = (
                select(Stock.symbol.label('symbol'))
                .where(*uni_filters)
                .subquery()
            )
            total_q = select(func.count()).select_from(universe)
            covered_q = (
                select(func.count())
                .select_from(universe)
                .where(
                    select(1)
                    .select_from(DailyKline)
                    .where(DailyKline.symbol == universe.c.symbol,
                           DailyKline.trade_date >= expected)
                    .exists()
                )
            )
            per_symbol_max = (
                select(Stock.symbol.label('symbol'),
                       func.max(DailyKline.trade_date).label('mx'))
                .select_from(Stock)
                .outerjoin(DailyKline, DailyKline.symbol == Stock.symbol)
                .where(*uni_filters)
                .group_by(Stock.symbol)
                .subquery()
            )
            oldest_q = (
                select(func.min(per_symbol_max.c.mx))
                .where((per_symbol_max.c.mx.is_(None))
                       | (per_symbol_max.c.mx < expected))
            )
            row = self.session.execute(
                select(total_q.scalar_subquery().label('total'),
                       covered_q.scalar_subquery().label('covered'),
                       oldest_q.scalar_subquery().label('oldest_stale'))
            ).mappings().first()
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_kline_coverage: {e}")
            raise

        total = int(row['total'] or 0)
        covered = int(row['covered'] or 0)
        oldest = row['oldest_stale']
        return {
            'total': total,
            'covered': covered,
            'stale': total - covered,
            'coverage': (covered / total) if total else 1.0,
            'oldest_stale': str(oldest) if oldest else None,
        }

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

    def get_latest_trade_date_strict(self) -> Optional[str]:
        """最新交易日（daily_klines 最大 trade_date），'YYYY-MM-DD'；无数据返回 None。

        **与 get_latest_trade_date 的唯一差异 = 异常策略**：读失败时回滚并**上抛**，不吞。

        2026-09-14（REQ-24e15d B4-c5）：application/services/scheduler_tasks.py 的
        handle_data_update 原先自己拼裸 SQL（缩进块，非 SQL 字面量，仅供阅读）：

            SELECT max(trade_date) FROM quant.daily_klines

        该查询失败时走它自己的 except 分支，返回 {"status": "error"}。若改用会吞异常的
        get_latest_trade_date，读失败会被静默降级成 {"status": "stale"} —— 把"读不到"
        伪装成"数据滞后"，与本仓反复踩过的静默失效同类。

        返回值口径与原 .scalar() 逐值一致：None（表空/全 NULL）或 'YYYY-MM-DD'。
        """
        try:
            d = self.session.query(func.max(DailyKline.trade_date)).scalar()
            return d.isoformat() if d else None
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_latest_trade_date_strict: {e}")
            raise

    def count_bars_by_symbol(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """按标的统计 [start_date, end_date] 内的日K线根数（stocks LEFT JOIN daily_klines）。

        2026-09-14（REQ-24e15d B4-c5）：application/services/scheduler_tasks.py 的
        _filter_factor_universe（因子计算前的标的预筛）原为裸 SQL，等价形态：

            SELECT s.symbol, s.name, s.is_delisted, s.is_st, count(k.trade_date) AS bars
              FROM quant.stocks s
              LEFT JOIN quant.daily_klines k
                     ON k.symbol = s.symbol
                    AND k.trade_date BETWEEN :start AND :end
             WHERE s.symbol = ANY(:syms)
             GROUP BY s.symbol, s.name, s.is_delisted, s.is_st

        口径逐字保留：
          · LEFT JOIN ⇒ 区间内无 K 线的标的**仍出一行**、bars = 0（0 与"缺行"必须可区分）；
          · 日期条件留在 **ON** 子句里（放进 WHERE 会把 LEFT JOIN 退化成 INNER JOIN）；
          · 只回主表中存在的 symbol；不在主表的代码不出现在结果里（调用方据此判 unknown）；
          · 分组键 = symbol, name, is_delisted, is_st。

        symbol 过滤走绑定参数（expanding IN，与原来的 = ANY(:syms) 同义）；空列表在入口短路
        返回 []，既不产生空的 IN 列表这种非法 SQL，语义也与"没有任何标的命中"一致。

        异常策略：回滚后**上抛** —— 调用方 handle_factor_compute 的 except 会把它记成任务失败；
        吞异常会把"读不到标的池"变成"预筛后 0 只入选"的假成功。

        Returns:
            [{'symbol','name','is_delisted','is_st','bars'}]（bars 为 int，恒非 None）
        """
        if not symbols:
            return []
        try:
            rows = self.session.execute(
                select(
                    Stock.symbol.label('symbol'),
                    Stock.name.label('name'),
                    Stock.is_delisted.label('is_delisted'),
                    Stock.is_st.label('is_st'),
                    func.count(DailyKline.trade_date).label('bars'),
                )
                .select_from(Stock)
                .outerjoin(
                    DailyKline,
                    and_(
                        DailyKline.symbol == Stock.symbol,
                        DailyKline.trade_date.between(start_date, end_date),
                    ),
                )
                .where(Stock.symbol.in_(list(symbols)))
                .group_by(
                    Stock.symbol, Stock.name, Stock.is_delisted, Stock.is_st,
                )
            ).mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in count_bars_by_symbol: {e}")
            raise

    def get_latest_index_quotes(
        self,
        index_symbol: str,
        limit: int = 2,
    ) -> List[tuple]:
        """最近 N 个交易日的指数 (trade_date, close)，按 trade_date **倒序**；无数据返回 []。

        2026-09-14（REQ-24e15d B4-c5）：adapters/outbound/datasources/market_state_provider.py
        的 _indices 原为裸 SQL：

            SELECT trade_date, close FROM quant.index_daily
             WHERE symbol = :s ORDER BY trade_date DESC LIMIT 2

        口径逐字保留：
          · symbol **原样匹配**，不经 resolve_index_symbol / _resolve_index_key 归一化 ——
            调用方传的就是 index_daily 的键（带市场后缀）；而归一化会去查 stocks 表做
            歧义裁决（000001.SH 上证指数 vs 000001 平安银行），既多一次 DB 往返，
            又可能把命中行判成"非指数"（= 静默少一行），与迁移前的命中集合不一致；
          · close 为 NULL 时原样返回 None（调用方自己判 None，不用 0 冒充）；
          · 返回 (trade_date, close) 元组列表，保持原来的位置访问语义。

        异常策略：回滚后**上抛** —— 调用方 except 会把 index_daily 记进 MarketState.degraded；
        仓储吞异常会让该降级信号静默消失。
        """
        try:
            rows = self.session.execute(
                select(IndexDaily.trade_date, IndexDaily.close)
                .where(IndexDaily.symbol == index_symbol)
                .order_by(IndexDaily.trade_date.desc())
                .limit(limit)
            ).all()
            return [(r[0], r[1]) for r in rows]
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_latest_index_quotes for {index_symbol}: {e}")
            raise

    def get_closes_on_date(
        self,
        symbols: List[str],
        trade_date: str,
    ) -> Dict[str, float]:
        """指定交易日、指定标的的收盘价映射 {symbol: close}（只含 close 非 NULL 的行）。

        2026-09-14（REQ-24e15d B4-c5）：infrastructure/jobs/fund_flow_update_job.py 的
        _load_reference_closes 原为裸 SQL：

            SELECT symbol, close FROM quant.daily_klines
             WHERE trade_date = :d AND symbol = ANY(:syms) AND close IS NOT NULL

        口径逐字保留：等值日期 + expanding IN（保留 ANY(:syms) 的语义）+ close IS NOT NULL；
        symbol **原样匹配**（不做后缀归一化）；值为 float(close)。

        空 symbols 恒返回 {}（入口短路，与调用方的 if not symbols: return {} 一致，
        也避免生成空的 IN 列表）。

        异常策略：回滚后**上抛** —— 调用方有自己的 except（记 warning、本次跳过一致性校验）；
        仓储吞异常会让那条留痕消失。
        """
        if not symbols:
            return {}
        try:
            rows = self.session.execute(
                select(DailyKline.symbol, DailyKline.close).where(
                    DailyKline.trade_date == trade_date,
                    DailyKline.symbol.in_(list(symbols)),
                    DailyKline.close.isnot(None),
                )
            ).all()
            return {str(r[0]): float(r[1]) for r in rows}
        except Exception as e:
            self._safe_rollback()
            logger.error(f"Error in get_closes_on_date({trade_date}): {e}")
            raise

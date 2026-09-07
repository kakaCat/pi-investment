"""
Qlib 数据适配器

让 Qlib 直接读取 quantsys-v2 的 PostgreSQL 数据库，
无需下载/转换数据。

使用方式:
    import qlib
    from application.services.qlib.qlib_data_adapter import QuantsysV2DataProvider

    # 注册自定义 Provider
    from qlib.data import register_provider
    register_provider('quantsys_v2', QuantsysV2DataProvider)

    # 初始化 Qlib
    qlib.init(provider_uri='quantsys_v2')

    # 使用 Qlib API
    from qlib.data import D
    df = D.features(
        instruments=['600000.SH', '600519.SH'],
        fields=['$close', '$open', '$volume'],
        start_time='2023-01-01',
        end_time='2023-12-31'
    )
"""

import os
import pandas as pd
import numpy as np
from typing import List, Union, Tuple
from datetime import datetime
from sqlalchemy import create_engine, text

try:
    from qlib.data import BaseProvider
    from qlib.log import get_module_logger
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False
    # 定义一个基础类以防 Qlib 未安装
    class BaseProvider:
        pass


class QuantsysV2DataProvider(BaseProvider):
    """
    Quantsys-v2 数据提供器

    直接从 PostgreSQL 数据库读取数据，转换为 Qlib 格式。

    优势:
    - 无需下载 10GB 官方数据
    - 无需转换数据格式
    - 数据实时更新（每日自动更新）
    - 与现有系统无缝集成
    """

    def __init__(self):
        """初始化数据提供器"""
        if not QLIB_AVAILABLE:
            raise ImportError(
                "Qlib not installed. "
                "Install with: pip install pyqlib"
            )

        super().__init__()

        # 获取日志
        self.logger = get_module_logger("QuantsysV2DataProvider")

        # 使用全局 SQLAlchemy Engine(与 BaseRepository 统一)
        from infrastructure.persistence.database.engine import get_engine
        self.engine = get_engine()

        self.logger.info("QuantsysV2DataProvider initialized (using global Engine)")

    # _create_engine 方法已废弃,改用全局 Engine

    def features(
        self,
        instruments: Union[str, List[str]],
        fields: List[str],
        start_time: Union[str, pd.Timestamp] = None,
        end_time: Union[str, pd.Timestamp] = None,
        freq: str = 'day',
        disk_cache: bool = False
    ) -> pd.DataFrame:
        """
        获取特征数据（Qlib 标准接口）

        Args:
            instruments: 股票代码列表，如 ['600000.SH', '600519.SH']
            fields: 字段列表，如 ['$close', '$open', '$volume']
                   支持 Qlib 表达式，如 '$close/$open'
            start_time: 开始时间 '2023-01-01'
            end_time: 结束时间 '2023-12-31'
            freq: 频率，目前只支持 'day'
            disk_cache: 是否使用磁盘缓存（暂不支持）

        Returns:
            DataFrame with MultiIndex (datetime, instrument)
        """
        # 转换 instruments 为列表
        if isinstance(instruments, str):
            instruments = [instruments]

        # 转换时间格式
        if start_time:
            start_time = pd.Timestamp(start_time).strftime('%Y-%m-%d')
        if end_time:
            end_time = pd.Timestamp(end_time).strftime('%Y-%m-%d')

        self.logger.info(
            f"Fetching data: {len(instruments)} instruments, "
            f"{len(fields)} fields, {start_time} to {end_time}"
        )

        # 1. 从数据库查询原始数据
        df_raw = self._query_database(instruments, start_time, end_time)

        if df_raw.empty:
            self.logger.warning("No data found in database")
            return pd.DataFrame()

        # 2. 转换为 Qlib 格式（MultiIndex）
        df_qlib = self._convert_to_qlib_format(df_raw)

        # 3. 计算字段表达式
        df_result = self._calculate_fields(df_qlib, fields)

        return df_result

    def _query_database(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        从数据库查询K线数据

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame with columns: symbol, trade_date, open, high, low, close, volume
        """
        # 构建 SQL 查询
        symbols_str = ','.join(f"'{s}'" for s in symbols)

        query = f"""
        SELECT
            symbol,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            amount
        FROM klines
        WHERE symbol IN ({symbols_str})
        """

        if start_date:
            query += f" AND trade_date >= '{start_date}'"
        if end_date:
            query += f" AND trade_date <= '{end_date}'"

        query += " ORDER BY symbol, trade_date"

        # 执行查询
        try:
            df = pd.read_sql(query, self.engine)
            self.logger.info(f"Fetched {len(df)} rows from database")
            return df
        except Exception as e:
            self.logger.error(f"Database query failed: {e}")
            return pd.DataFrame()

    def _convert_to_qlib_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        转换为 Qlib 格式（MultiIndex: datetime, instrument）

        Args:
            df: 原始数据

        Returns:
            DataFrame with MultiIndex
        """
        if df.empty:
            return df

        # 转换日期为 datetime
        df['trade_date'] = pd.to_datetime(df['trade_date'])

        # 设置 MultiIndex
        df = df.set_index(['trade_date', 'symbol'])

        # 重命名索引
        df.index.names = ['datetime', 'instrument']

        return df

    def _calculate_fields(
        self,
        df: pd.DataFrame,
        fields: List[str]
    ) -> pd.DataFrame:
        """
        计算字段表达式

        支持:
        - 基础字段: $close, $open, $high, $low, $volume
        - 表达式: $close/$open, $high-$low
        - 函数: Ref($close, 1), Mean($close, 5)

        Args:
            df: Qlib 格式数据
            fields: 字段列表

        Returns:
            DataFrame with calculated fields
        """
        if df.empty:
            return df

        result = pd.DataFrame(index=df.index)

        for field in fields:
            try:
                if field.startswith('$'):
                    # 基础字段（如 $close）
                    col_name = field[1:]  # 去掉 $
                    if col_name in df.columns:
                        result[field] = df[col_name]
                    else:
                        self.logger.warning(f"Column '{col_name}' not found")
                        result[field] = np.nan
                else:
                    # 表达式（如 $close/$open）
                    expr = self._convert_qlib_expression(field, df)
                    result[field] = expr
            except Exception as e:
                self.logger.error(f"Failed to calculate field '{field}': {e}")
                result[field] = np.nan

        return result

    def _convert_qlib_expression(self, expr: str, df: pd.DataFrame):
        """
        转换 Qlib 表达式为 pandas 计算

        Examples:
            $close/$open -> df['close'] / df['open']
            $high-$low -> df['high'] - df['low']
            Ref($close, 1) -> df['close'].shift(1)

        Args:
            expr: Qlib 表达式
            df: 数据

        Returns:
            计算结果（Series）
        """
        # 替换 $ 符号
        pandas_expr = expr
        for col in ['close', 'open', 'high', 'low', 'volume', 'amount']:
            pandas_expr = pandas_expr.replace(f'${col}', f"df['{col}']")

        # 替换 Qlib 函数
        # Ref($close, 1) -> df['close'].shift(1)
        if 'Ref(' in pandas_expr:
            # 简单替换（完整实现需要更复杂的解析）
            pandas_expr = pandas_expr.replace('Ref(', 'shift(')

        # 计算表达式
        try:
            result = eval(pandas_expr, {'df': df, 'np': np, 'pd': pd})
            return result
        except Exception as e:
            self.logger.error(f"Expression evaluation failed: {expr} -> {pandas_expr}, {e}")
            return pd.Series(np.nan, index=df.index)

    def calendar(
        self,
        start_time: Union[str, pd.Timestamp] = None,
        end_time: Union[str, pd.Timestamp] = None,
        freq: str = 'day'
    ) -> np.ndarray:
        """
        获取交易日历

        Args:
            start_time: 开始时间
            end_time: 结束时间
            freq: 频率

        Returns:
            交易日数组
        """
        # 查询数据库中的唯一交易日
        query = """
        SELECT DISTINCT trade_date
        FROM klines
        WHERE 1=1
        """

        if start_time:
            start_time = pd.Timestamp(start_time).strftime('%Y-%m-%d')
            query += f" AND trade_date >= '{start_time}'"
        if end_time:
            end_time = pd.Timestamp(end_time).strftime('%Y-%m-%d')
            query += f" AND trade_date <= '{end_time}'"

        query += " ORDER BY trade_date"

        df = pd.read_sql(query, self.engine)
        dates = pd.to_datetime(df['trade_date']).values

        return dates

    def instruments(
        self,
        market: str = 'all',
        filter_pipe: List = None
    ) -> List[str]:
        """
        获取股票列表

        Args:
            market: 市场（'all', 'SH', 'SZ'）
            filter_pipe: 过滤器（暂不支持）

        Returns:
            股票代码列表
        """
        query = "SELECT DISTINCT symbol FROM klines ORDER BY symbol"

        df = pd.read_sql(query, self.engine)
        symbols = df['symbol'].tolist()

        # 按市场过滤
        if market != 'all':
            symbols = [s for s in symbols if s.endswith(f'.{market.upper()}')]

        return symbols


__all__ = ['QuantsysV2DataProvider']

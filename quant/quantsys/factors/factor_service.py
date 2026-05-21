"""
因子计算服务

功能：
1. 从 PostgreSQL 读取最新K线数据
2. 计算42个技术因子
3. 保存因子值到 PostgreSQL
"""

import logging
import re
from datetime import datetime
from typing import List, Optional, Dict
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

from quantsys.factors import (
    MA, EMA, RSI, MACD, KDJ, BollingerBands, ATR, OBV,
    CCI, WilliamsR, ROC, MFI, EMV, VolumeRatio, MOM
)

logger = logging.getLogger(__name__)


# 定义所有因子
FACTORS = [
    # 趋势类因子
    ('MA5', MA(5)),
    ('MA10', MA(10)),
    ('MA20', MA(20)),
    ('MA60', MA(60)),
    ('EMA12', EMA(12)),
    ('EMA26', EMA(26)),

    # 动量类因子
    ('RSI6', RSI(6)),
    ('RSI12', RSI(12)),
    ('RSI24', RSI(24)),
    ('ROC12', ROC(12)),
    ('MOM6', MOM(6)),
    ('MOM12', MOM(12)),

    # 波动率因子
    ('ATR14', ATR(14)),
    ('BOLL', BollingerBands(20, 2)),

    # 成交量因子
    ('OBV', OBV()),
    ('VR', VolumeRatio(26)),
    ('MFI14', MFI(14)),
    ('EMV14', EMV(14)),

    # 超买超卖因子
    ('KDJ', KDJ(9, 3, 3)),
    ('WR10', WilliamsR(10)),
    ('WR6', WilliamsR(6)),
    ('CCI14', CCI(14)),

    # 趋势强度因子
    ('MACD', MACD(12, 26, 9)),
]


class FactorService:
    """因子计算服务"""

    def __init__(self, pg_config: dict):
        """
        初始化因子服务

        Args:
            pg_config: PostgreSQL 连接配置
        """
        self.pg_config = pg_config

    def _connect(self):
        """创建数据库连接"""
        return psycopg2.connect(**self.pg_config)

    def get_latest_kline_date(self) -> Optional[str]:
        """获取最新K线日期"""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(trade_date) FROM quant.daily_klines")
                result = cur.fetchone()
                return result[0] if result and result[0] else None
        finally:
            conn.close()

    def get_stock_data(self, symbol: str, days: int = 100) -> Optional[pd.DataFrame]:
        """
        获取股票K线数据

        Args:
            symbol: 股票代码
            days: 获取天数

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        conn = self._connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT trade_date as date, open, high, low, close, volume
                    FROM quant.daily_klines
                    WHERE symbol = %s
                    ORDER BY trade_date DESC
                    LIMIT %s
                """, (symbol, days))

                rows = cur.fetchall()
                if not rows:
                    return None

                df = pd.DataFrame(rows)
                # 按日期升序排列
                df = df.sort_values('date').reset_index(drop=True)
                return df
        finally:
            conn.close()

    def get_all_symbols(self, market: str = 'A') -> List[str]:
        """
        获取所有股票代码

        Args:
            market: 市场类型 ('A' for A股)

        Returns:
            股票代码列表
        """
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                if market == 'A':
                    cur.execute("""
                        SELECT DISTINCT symbol
                        FROM quant.stocks
                        WHERE market = 'A'
                        ORDER BY symbol
                    """)
                else:
                    cur.execute("""
                        SELECT DISTINCT symbol
                        FROM quant.stocks
                        ORDER BY symbol
                    """)

                return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def calculate_factors_for_stock(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        计算单只股票的所有因子

        Args:
            symbol: 股票代码

        Returns:
            因子字典 {factor_name: factor_value}
        """
        # 获取数据（需要足够的历史数据来计算因子）
        data = self.get_stock_data(symbol, days=100)

        if data is None or len(data) < 60:
            return None

        # 计算所有因子
        factor_results = {}

        for factor_name, factor_obj in FACTORS:
            try:
                result = factor_obj.calculate(data)

                # 处理不同类型的返回值
                if isinstance(result, pd.DataFrame):
                    # 多列因子（如 MACD, KDJ, BOLL）
                    for col in result.columns:
                        col_name = f"{factor_name}_{col}"
                        factor_results[col_name] = result[col].iloc[-1]
                elif isinstance(result, pd.Series):
                    # 单列因子
                    factor_results[factor_name] = result.iloc[-1]
                else:
                    # 标量值
                    factor_results[factor_name] = result

            except Exception as e:
                logger.warning(f"  ⚠️  {symbol} 计算因子 {factor_name} 失败: {e}")
                continue

        return factor_results

    def save_factors(self, symbol: str, date: str, factors: Dict[str, float]):
        """
        保存因子值到 PostgreSQL

        Args:
            symbol: 股票代码
            date: 日期
            factors: 因子字典
        """
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                # 删除该股票该日期的旧因子数据
                cur.execute("""
                    DELETE FROM quant.factor_values
                    WHERE symbol = %s AND factor_date = %s
                """, (symbol, date))

                # 插入新因子数据
                for factor_name, factor_value in factors.items():
                    if pd.notna(factor_value):
                        cur.execute("""
                            INSERT INTO quant.factor_values (symbol, factor_date, factor_name, factor_value)
                            VALUES (%s, %s, %s, %s)
                        """, (symbol, date, factor_name, float(factor_value)))

                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_factor_stats(self, date: str) -> Dict[str, int]:
        """
        获取因子统计信息

        Args:
            date: 日期

        Returns:
            统计信息字典
        """
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(DISTINCT symbol) as stocks,
                        COUNT(DISTINCT factor_name) as factors,
                        COUNT(*) as records
                    FROM quant.factor_values
                    WHERE factor_date = %s
                """, (date,))

                row = cur.fetchone()
                return {
                    'stocks': row[0] or 0,
                    'factors': row[1] or 0,
                    'records': row[2] or 0
                }
        finally:
            conn.close()

    def check_factors_exist(self, symbol: str, date: str) -> bool:
        """
        检查因子是否已存在

        Args:
            symbol: 股票代码
            date: 日期

        Returns:
            True 表示已存在，False 表示不存在
        """
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM quant.factor_values
                    WHERE symbol = %s AND factor_date = %s
                """, (symbol, date))
                count = cur.fetchone()[0]
                return count > 0
        finally:
            conn.close()

    def calculate_factors(self, symbols: Optional[List[str]] = None, force: bool = False) -> Dict:
        """
        计算因子（主入口）

        Args:
            symbols: 股票代码列表，None 表示计算全部A股
            force: 是否强制重新计算（默认 False，只计算缺失的）

        Returns:
            计算结果统计
        """
        logger.info("=" * 60)
        logger.info("因子计算任务开始")
        logger.info(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"增量模式: {'否（强制重算）' if force else '是（跳过已有）'}")
        logger.info("=" * 60)

        # 获取股票范围
        if symbols is None:
            symbols = self.get_all_symbols(market='A')

        logger.info(f"共 {len(symbols)} 只股票需要计算因子")

        # 获取最新日期
        latest_date = self.get_latest_kline_date()
        logger.info(f"最新数据日期: {latest_date}")
        logger.info("")

        if not latest_date:
            raise ValueError("没有找到K线数据")

        # 计算因子
        success_count = 0
        fail_count = 0
        skip_count = 0

        for i, symbol in enumerate(symbols, 1):
            try:
                # 增量计算：检查是否已存在
                if not force and self.check_factors_exist(symbol, latest_date):
                    logger.info(f"[{i}/{len(symbols)}] ⏭️  {symbol} 因子已存在，跳过")
                    skip_count += 1
                    continue

                # 计算因子
                factors = self.calculate_factors_for_stock(symbol)

                if factors is None:
                    logger.warning(f"[{i}/{len(symbols)}] ⚠️  {symbol} 数据不足，跳过")
                    fail_count += 1
                    continue

                # 保存因子
                self.save_factors(symbol, latest_date, factors)

                logger.info(f"[{i}/{len(symbols)}] ✅ {symbol} 计算完成，{len(factors)} 个因子")
                success_count += 1

            except Exception as e:
                logger.error(f"[{i}/{len(symbols)}] ❌ {symbol} 计算失败: {e}")
                fail_count += 1
                continue

        logger.info("")
        logger.info("=" * 60)
        logger.info("因子计算任务完成")
        logger.info(f"成功: {success_count} | 跳过: {skip_count} | 失败: {fail_count}")
        logger.info("=" * 60)

        # 统计信息
        stats = self.get_factor_stats(latest_date)
        logger.info(f"\n📊 因子统计:")
        logger.info(f"  日期: {latest_date}")
        logger.info(f"  股票数: {stats['stocks']}")
        logger.info(f"  因子数: {stats['factors']}")
        logger.info(f"  记录数: {stats['records']}")

        return {
            'success': True,
            'date': latest_date,
            'total': len(symbols),
            'success_count': success_count,
            'fail_count': fail_count,
            'stats': stats
        }

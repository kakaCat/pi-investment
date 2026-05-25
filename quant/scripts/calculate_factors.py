#!/usr/bin/env python3
"""
因子计算脚本

功能：
1. 从数据库读取最新K线数据
2. 计算42个技术因子
3. 保存因子值到数据库
"""

import os
import sys
import logging
import argparse
import re
from datetime import datetime
import pandas as pd

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.data.db import Database
from quantsys.factors import (
    MA, EMA, RSI, MACD, KDJ, BollingerBands, ATR, OBV,
    CCI, WilliamsR, ROC, MFI, EMV, VolumeRatio, MOM
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# 定义所有因子（使用实际存在的因子）
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


def normalize_symbol(symbol: str) -> str:
    """Normalize common exchange prefixes/suffixes."""
    value = str(symbol).strip()
    value = re.sub(r'^(sh|sz|bj)', '', value, flags=re.IGNORECASE)
    value = re.sub(r'\.(SH|SZ|BJ|HK)$', '', value, flags=re.IGNORECASE)
    return value


def parse_symbols(raw_symbols: str = None):
    """Parse comma/whitespace separated symbols."""
    if not raw_symbols:
        return None
    symbols = [
        normalize_symbol(symbol)
        for symbol in re.split(r'[\s,，]+', raw_symbols)
        if symbol.strip()
    ]
    return list(dict.fromkeys(symbols))


def create_factor_table(db: Database):
    """创建因子表"""
    db._migrate()
    logger.info("✅ 因子表创建完成")


def get_stock_data(db: Database, symbol: str, days: int = 100) -> pd.DataFrame:
    """获取股票数据"""
    latest_date = db.get_latest_kline_date()
    if not latest_date:
        return None
    df = db.get_stock_klines_until_date(symbol, latest_date, days)

    if len(df) == 0:
        return None

    # 按日期升序排列
    df = df.sort_values('date').reset_index(drop=True)

    return df


def calculate_factors_for_stock(db: Database, symbol: str) -> dict:
    """计算单只股票的所有因子"""
    # 获取数据（需要足够的历史数据来计算因子）
    data = get_stock_data(db, symbol, days=100)

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


def save_factors(db: Database, symbol: str, date: str, factors: dict):
    """保存因子值到数据库"""
    records = [
        (symbol, date, factor_name, float(factor_value))
        for factor_name, factor_value in factors.items()
        if pd.notna(factor_value)
    ]
    db.replace_factor_values_for_dates(records)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='因子计算脚本')
    parser.add_argument('--symbols', type=str, help='股票代码列表，逗号分隔；不传则计算全部A股')
    parser.add_argument('--job-id', type=str, help='后端异步任务ID，用于兼容API任务调度')
    return parser


def main():
    """主函数"""
    args = build_arg_parser().parse_args()

    logger.info("=" * 60)
    logger.info("因子计算任务开始")
    if args.job_id:
        logger.info(f"任务ID: {args.job_id}")
    logger.info(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 数据库路径
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.pi-invest', 'stock-db', 'stocks.db'
    )

    db = Database(db_path)

    # 创建因子表
    create_factor_table(db)

    # 获取股票范围
    symbols = parse_symbols(args.symbols) or db.get_all_symbols(market='A')
    logger.info(f"共 {len(symbols)} 只股票需要计算因子")
    logger.info("")

    # 获取最新日期
    latest_date = db.get_latest_kline_date()
    logger.info(f"最新数据日期: {latest_date}")
    logger.info("")

    # 计算因子
    success_count = 0
    fail_count = 0

    for i, symbol in enumerate(symbols, 1):
        try:
            # 计算因子
            factors = calculate_factors_for_stock(db, symbol)

            if factors is None:
                logger.warning(f"[{i}/{len(symbols)}] ⚠️  {symbol} 数据不足，跳过")
                fail_count += 1
                continue

            # 保存因子
            save_factors(db, symbol, latest_date, factors)

            logger.info(f"[{i}/{len(symbols)}] ✅ {symbol} 计算完成，{len(factors)} 个因子")
            success_count += 1

        except Exception as e:
            logger.error(f"[{i}/{len(symbols)}] ❌ {symbol} 计算失败: {e}")
            fail_count += 1
            continue

    logger.info("")
    logger.info("=" * 60)
    logger.info("因子计算任务完成")
    logger.info(f"成功: {success_count} | 失败: {fail_count}")
    logger.info("=" * 60)

    # 统计信息
    stats = db.get_factor_stats(latest_date)
    logger.info(f"\n📊 因子统计:")
    logger.info(f"  日期: {latest_date}")
    logger.info(f"  股票数: {stats['stocks']}")
    logger.info(f"  因子数: {stats['factors']}")
    logger.info(f"  记录数: {stats['records']}")


if __name__ == '__main__':
    main()

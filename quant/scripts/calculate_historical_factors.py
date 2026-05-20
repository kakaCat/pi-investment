#!/usr/bin/env python3
"""
历史因子计算脚本

功能：
1. 从数据库读取历史K线数据
2. 计算每一天的42个技术因子
3. 保存因子值到数据库
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from tqdm import tqdm

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


def create_factor_table(db: Database):
    """创建因子表"""
    db._migrate()


def get_stock_data_until_date(db: Database, symbol: str, end_date: str, lookback: int = 100) -> pd.DataFrame:
    """获取截止到某日期的股票数据"""
    df = db.get_stock_klines_until_date(symbol, end_date, lookback)

    if len(df) == 0:
        return None

    # 按日期升序排列
    df = df.sort_values('date').reset_index(drop=True)

    return df


def calculate_factors_for_date(db: Database, symbol: str, date: str) -> dict:
    """计算单只股票在某日期的所有因子"""
    # 获取截止到该日期的历史数据
    data = get_stock_data_until_date(db, symbol, date, lookback=100)

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
            # 静默失败，避免日志过多
            continue

    return factor_results


def save_factors_batch(db: Database, records: list):
    """批量保存因子值"""
    db.upsert_factor_values(records)


def get_trading_dates(db: Database, days: int) -> list:
    """获取最近N个交易日"""
    return db.get_trading_dates(days)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='计算历史因子数据')
    parser.add_argument('--days', type=int, default=180, help='计算最近N天的因子（默认180天）')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("历史因子计算任务")
    logger.info("=" * 60)
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"计算天数: {args.days}")
    logger.info("")

    # 数据库路径 - 使用项目根目录的数据库
    project_root = Path(__file__).parent.parent.parent
    db_path = project_root / '.pi-invest' / 'stock-db' / 'stocks.db'

    db = Database(str(db_path))

    # 创建因子表
    create_factor_table(db)

    # 获取有K线数据的股票
    symbols = db.get_symbols_with_kline_count(1)
    logger.info(f"股票数量: {len(symbols)}")

    # 获取交易日期
    trading_dates = get_trading_dates(db, args.days)
    logger.info(f"交易日数: {len(trading_dates)}")
    logger.info(f"日期范围: {trading_dates[0]} ~ {trading_dates[-1]}")
    logger.info("")

    # 计算因子
    total_tasks = len(symbols) * len(trading_dates)
    logger.info(f"总任务数: {total_tasks}")
    logger.info("")

    success_count = 0
    fail_count = 0
    batch_records = []
    batch_size = 1000

    with tqdm(total=total_tasks, desc="计算因子") as pbar:
        for symbol in symbols:
            for date in trading_dates:
                try:
                    # 计算因子
                    factors = calculate_factors_for_date(db, symbol, date)

                    if factors is None:
                        fail_count += 1
                        pbar.update(1)
                        continue

                    # 添加到批量记录
                    for factor_name, factor_value in factors.items():
                        if pd.notna(factor_value):
                            batch_records.append((symbol, date, factor_name, float(factor_value)))

                    success_count += 1

                    # 批量保存
                    if len(batch_records) >= batch_size:
                        save_factors_batch(db, batch_records)
                        batch_records = []

                except Exception as e:
                    fail_count += 1

                pbar.update(1)

    # 保存剩余记录
    if batch_records:
        save_factors_batch(db, batch_records)

    logger.info("")
    logger.info("=" * 60)
    logger.info("历史因子计算完成")
    logger.info("=" * 60)
    logger.info(f"成功: {success_count}")
    logger.info(f"失败: {fail_count}")
    logger.info("")

    # 统计信息
    stats = db.get_factor_stats()
    logger.info("📊 数据库统计:")
    logger.info(f"  股票数: {stats['stocks']}")
    logger.info(f"  因子数: {stats['factors']}")
    logger.info(f"  记录数: {stats['records']}")
    logger.info(f"  日期范围: {stats['min_date']} ~ {stats['max_date']}")


if __name__ == '__main__':
    main()

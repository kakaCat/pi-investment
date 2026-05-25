#!/usr/bin/env python3
"""
因子计算脚本 - 多进程并行优化版本

优化点：
1. 多进程并行处理（4进程）
2. 批量INSERT（100行/批次）
3. 事务批处理（减少commit次数）
4. 预先筛选有效股票（数据量>=60天）

预期性能提升：5-10倍
"""

import os
import sys
import logging
from datetime import datetime
import pandas as pd
from multiprocessing import Pool, cpu_count
import time

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

# 全局变量（用于子进程）
_db_path = None
_latest_date = None


def init_worker(db_path, latest_date):
    """初始化工作进程"""
    global _db_path, _latest_date
    _db_path = db_path
    _latest_date = latest_date


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


def calculate_factors_for_stock(symbol: str) -> tuple:
    """
    计算单只股票的所有因子

    Returns:
        (symbol, date, factors_dict) 或 None
    """
    try:
        db = Database(_db_path)

        # 获取数据
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
                # 静默失败，不打印警告（减少日志输出）
                continue

        return (symbol, _latest_date, factor_results)

    except Exception as e:
        return None


def save_factors_batch(db: Database, results: list):
    """
    批量保存因子值到数据库

    Args:
        results: [(symbol, date, factors_dict), ...]
    """
    if not results:
        return 0

    try:
        insert_data = []
        for symbol, date, factors in results:
            for factor_name, factor_value in factors.items():
                if pd.notna(factor_value):  # 跳过 NaN 值
                    insert_data.append((symbol, date, factor_name, float(factor_value)))

        if insert_data:
            db.replace_factor_values_for_dates(insert_data)

        return len(results)

    except Exception as e:
        logger.error(f"批量保存失败: {e}")
        return 0


def get_valid_symbols(db: Database) -> list:
    """
    预先筛选有足够数据的股票（>=60天K线）

    Returns:
        符合条件的股票代码列表
    """
    return db.get_symbols_with_kline_count(60)


def main():
    """主函数"""
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("因子计算任务开始（多进程并行版本）")
    logger.info(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 数据库路径
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.pi-invest', 'stock-db', 'stocks.db'
    )

    db = Database(db_path)

    # 创建因子表
    db._migrate()
    logger.info("✅ 因子表创建完成")

    # 获取最新日期
    latest_date = db.get_latest_kline_date()

    if not latest_date:
        logger.error("❌ 数据库中没有K线数据")
        return

    logger.info(f"最新数据日期: {latest_date}")

    # 预先筛选有效股票
    logger.info("正在筛选有效股票（数据量>=60天）...")
    symbols = get_valid_symbols(db)
    logger.info(f"共 {len(symbols)} 只股票符合条件")
    logger.info("")

    if len(symbols) == 0:
        logger.warning("⚠️  没有符合条件的股票")
        return

    # 确定进程数（最多使用CPU核心数-1，最少2个）
    num_workers = max(2, min(cpu_count() - 1, 8))
    logger.info(f"使用 {num_workers} 个进程并行计算")
    logger.info("")

    # 多进程并行计算
    batch_size = 100  # 每批处理100只股票
    total_batches = (len(symbols) + batch_size - 1) // batch_size

    success_count = 0
    fail_count = 0

    with Pool(processes=num_workers, initializer=init_worker, initargs=(db_path, latest_date)) as pool:
        for batch_idx in range(total_batches):
            batch_start = batch_idx * batch_size
            batch_end = min(batch_start + batch_size, len(symbols))
            batch_symbols = symbols[batch_start:batch_end]

            logger.info(f"处理批次 {batch_idx + 1}/{total_batches} ({len(batch_symbols)} 只股票)...")

            # 并行计算因子
            batch_start_time = time.time()
            results = pool.map(calculate_factors_for_stock, batch_symbols)

            # 过滤掉失败的结果
            valid_results = [r for r in results if r is not None]

            # 批量保存
            saved = save_factors_batch(db, valid_results)

            batch_elapsed = time.time() - batch_start_time
            success_count += saved
            fail_count += len(batch_symbols) - saved

            logger.info(f"  ✅ 批次完成: 成功 {saved}/{len(batch_symbols)}, 耗时 {batch_elapsed:.2f}s")
            logger.info("")

    total_elapsed = time.time() - start_time

    logger.info("=" * 60)
    logger.info("因子计算任务完成")
    logger.info(f"成功: {success_count} | 失败: {fail_count}")
    logger.info(f"总耗时: {total_elapsed:.2f}秒 ({total_elapsed/60:.2f}分钟)")
    logger.info(f"平均速度: {success_count/total_elapsed:.1f} 只/秒")
    logger.info("=" * 60)

    # 统计信息
    stats = db.get_factor_stats(latest_date)
    logger.info("")
    logger.info("数据库统计:")
    logger.info(f"  - 股票数: {stats['stocks']}")
    logger.info(f"  - 因子种类: {stats['factors']}")
    logger.info(f"  - 因子记录: {stats['records']}")


if __name__ == '__main__':
    main()

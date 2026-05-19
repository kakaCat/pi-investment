#!/usr/bin/env python3
"""
下载5年历史数据

为所有股票下载过去5年的K线数据
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging

# 添加路径
QUANT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(QUANT_ROOT))

from quantsys.data.db import Database
from quantsys.data.fetchers.klines import KlineFetcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def main():
    """主函数"""
    # 计算日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5*365)  # 5年前

    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    logging.info("=" * 60)
    logging.info("下载5年历史数据")
    logging.info("=" * 60)
    logging.info(f"开始日期: {start_str}")
    logging.info(f"结束日期: {end_str}")
    logging.info(f"总天数: {(end_date - start_date).days} 天")
    logging.info("")

    # 连接数据库
    db_path = Path.home() / '.pi-invest' / 'stock-db' / 'stocks.db'
    db = Database(str(db_path))

    # 获取所有股票
    conn = db._get_connection()
    cursor = conn.cursor()

    # 只更新已有K线数据的股票（持仓+关注列表）
    cursor.execute("""
        SELECT DISTINCT s.symbol, s.name, s.market
        FROM stocks s
        INNER JOIN daily_klines k ON s.symbol = k.symbol
        WHERE s.market = 'A'
        ORDER BY s.symbol
    """)

    stocks = cursor.fetchall()
    total = len(stocks)

    logging.info(f"共 {total} 只股票需要更新")
    logging.info("")

    # 创建 KlineFetcher
    fetcher = KlineFetcher(db)

    # 计算需要下载的天数
    days = (end_date - start_date).days

    # 批量更新
    success_count = 0
    failed_count = 0

    for i, row in enumerate(stocks, 1):
        symbol = row[0]
        name = row[1]

        logging.info(f"[{i}/{total}] 处理: {symbol} {name}")

        try:
            # 更新K线数据（下载指定天数）
            fetcher.run(symbols=[symbol], days=days)
            success_count += 1
            logging.info(f"  ✅ 成功")

        except Exception as e:
            failed_count += 1
            logging.error(f"  ❌ 错误: {e}")

    # 统计结果
    logging.info("")
    logging.info("=" * 60)
    logging.info("下载完成")
    logging.info("=" * 60)
    logging.info(f"成功: {success_count} 只")
    logging.info(f"失败: {failed_count} 只")
    logging.info("")

    # 查看数据统计
    cursor.execute("""
        SELECT
            COUNT(DISTINCT symbol) as stock_count,
            COUNT(*) as kline_count,
            MIN(date) as earliest_date,
            MAX(date) as latest_date
        FROM daily_klines
    """)

    row = cursor.fetchone()
    if row:
        logging.info("数据库统计:")
        logging.info(f"  股票数: {row[0]}")
        logging.info(f"  K线数: {row[1]}")
        logging.info(f"  最早日期: {row[2]}")
        logging.info(f"  最新日期: {row[3]}")

    db.close()

if __name__ == '__main__':
    main()

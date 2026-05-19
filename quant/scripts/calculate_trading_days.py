#!/usr/bin/env python3
"""
计算实际交易日天数

计算从2021-05-19到各股票最新日期之间的实际交易日天数
排除周末和节假日
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# 添加路径
QUANT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(QUANT_ROOT))

from quantsys.data.db import Database

def calculate_trading_days(start_date: str, end_date: str) -> int:
    """
    计算两个日期之间的交易日天数

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)

    Returns:
        交易日天数
    """
    # 使用pandas生成工作日序列（排除周末）
    date_range = pd.date_range(start=start_date, end=end_date, freq='B')

    # 可选：使用chinese_calendar库排除中国节假日
    try:
        import chinese_calendar as cc
        # 过滤掉节假日
        trading_days = [d for d in date_range if not cc.is_holiday(d)]
        return len(trading_days)
    except ImportError:
        # 如果没有chinese_calendar，只排除周末
        return len(date_range)

def main():
    """主函数"""
    print("=" * 80)
    print("计算实际交易日天数")
    print("=" * 80)
    print()

    # 连接数据库
    db_path = QUANT_ROOT / '.pi-invest' / 'stock-db' / 'stocks.db'
    db = Database(str(db_path))
    conn = db._get_connection()
    cursor = conn.cursor()

    # 基准开始日期
    base_start_date = '2021-05-19'

    # 查询每只股票的数据范围
    cursor.execute("""
        SELECT
            s.symbol,
            s.name,
            COUNT(k.date) as actual_days,
            MIN(k.date) as start_date,
            MAX(k.date) as end_date,
            ROUND(JULIANDAY(MAX(k.date)) - JULIANDAY(MIN(k.date))) as total_days
        FROM stocks s
        INNER JOIN daily_klines k ON s.symbol = k.symbol
        WHERE s.market = 'A'
        GROUP BY s.symbol, s.name
        ORDER BY actual_days DESC
    """)

    results = cursor.fetchall()

    print(f"{'股票代码':<10} {'股票名称':<12} {'实际天数':<10} {'开始日期':<12} {'结束日期':<12} {'总天数':<10} {'交易日':<10}")
    print("-" * 80)

    for row in results:
        symbol = row[0]
        name = row[1]
        actual_days = row[2]
        start_date = row[3]
        end_date = row[4]
        total_days = int(row[5]) if row[5] else 0

        # 计算从基准日期到结束日期的交易日天数
        if start_date and end_date:
            # 使用实际开始日期或基准日期（取较晚的）
            calc_start = max(base_start_date, start_date)
            trading_days = calculate_trading_days(calc_start, end_date)
        else:
            trading_days = 0

        print(f"{symbol:<10} {name:<12} {actual_days:<10} {start_date:<12} {end_date:<12} {total_days:<10} {trading_days:<10}")

    print()
    print("=" * 80)

    # 统计总体信息
    if results:
        cursor.execute("""
            SELECT
                COUNT(DISTINCT symbol) as stock_count,
                COUNT(*) as total_klines,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM daily_klines
        """)

        summary = cursor.fetchone()
        if summary:
            stock_count = summary[0]
            total_klines = summary[1]
            earliest_date = summary[2]
            latest_date = summary[3]

            # 计算从基准日期到最新日期的交易日
            if earliest_date and latest_date:
                calc_start = max(base_start_date, earliest_date)
                total_trading_days = calculate_trading_days(calc_start, latest_date)
                total_calendar_days = (pd.to_datetime(latest_date) - pd.to_datetime(calc_start)).days
            else:
                total_trading_days = 0
                total_calendar_days = 0

            print(f"股票总数: {stock_count}")
            print(f"K线总数: {total_klines}")
            print(f"最早日期: {earliest_date}")
            print(f"最新日期: {latest_date}")
            print(f"基准日期: {base_start_date}")
            print(f"日历天数: {total_calendar_days}")
            print(f"交易日数: {total_trading_days}")
            print()

            # 计算完整5年的交易日
            full_5year_trading_days = calculate_trading_days(base_start_date, datetime.now().strftime('%Y-%m-%d'))
            print(f"从 {base_start_date} 到今天的交易日数: {full_5year_trading_days}")

    db.close()

if __name__ == '__main__':
    main()

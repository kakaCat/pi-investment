#!/usr/bin/env python3
"""
每日数据更新脚本

用途：每天自动更新沪深300成分股的最新K线数据
建议运行时间：每天晚上18:00（交易日收盘后）
"""

import os
import sys

# 禁用代理
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.data.db import Database
from quantsys.data.fetchers.klines import KlineFetcher
from datetime import datetime


def main():
    """每日更新主函数"""
    print("=" * 60)
    print("沪深300成分股 - 每日数据更新")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    # 数据库路径
    db_path = os.path.join(
        os.path.expanduser('~'),
        '.pi-invest', 'stock-db', 'stocks.db'
    )

    db = Database(db_path)
    fetcher = KlineFetcher(db)

    # 获取所有A股股票
    symbols = db.get_all_symbols(market='A')
    print(f"共 {len(symbols)} 只股票需要更新")
    print()

    # 只更新最近5天的数据（包含今天）
    fetcher.run(symbols=symbols, days=5, market='A')

    print("\n" + "=" * 60)
    print("✅ 每日更新完成！")
    print("=" * 60)

    # 显示最新数据
    conn = db._get_connection()
    cursor = conn.execute("""
        SELECT MAX(date) as latest_date, COUNT(DISTINCT symbol) as updated_stocks
        FROM daily_klines
        WHERE date = (SELECT MAX(date) FROM daily_klines)
    """)
    stats = cursor.fetchone()

    print(f"\n📊 更新统计:")
    print(f"  最新日期: {stats[0]}")
    print(f"  更新股票: {stats[1]} 只")
    print()


if __name__ == '__main__':
    main()

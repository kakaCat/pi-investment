#!/usr/bin/env python3
"""
获取沪深300成分股数据

用途：
1. 首次运行：获取沪深300成分股的2年历史数据
2. 定时运行：每天更新最新数据
"""

import os
import sys

# 禁用代理（如果akshare无法连接，取消注释下面几行）
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.data.db import Database
from quantsys.data.fetchers.stock_list import StockListFetcher
from quantsys.data.fetchers.klines import KlineFetcher
import akshare as ak
from datetime import datetime


def fetch_hs300_stocks(db: Database):
    """获取沪深300成分股列表并保存到数据库"""
    print("=" * 60)
    print("步骤1: 获取沪深300成分股列表")
    print("=" * 60)

    try:
        # 获取沪深300成分股
        df = ak.index_stock_cons_csindex(symbol="000300")
        print(f"✅ 成功获取 {len(df)} 只沪深300成分股")

        # 保存到数据库
        conn = db._get_connection()
        saved_count = 0

        for _, row in df.iterrows():
            symbol = row['成分券代码']
            name = row['成分券名称']

            try:
                conn.execute(
                    "INSERT OR REPLACE INTO stocks (symbol, name, market) VALUES (?, ?, ?)",
                    (symbol, name, 'A')
                )
                saved_count += 1
            except Exception as e:
                print(f"  ⚠️  保存 {symbol} {name} 失败: {e}")

        conn.commit()
        print(f"✅ 成功保存 {saved_count} 只股票到数据库")
        return saved_count

    except Exception as e:
        print(f"❌ 获取沪深300成分股失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


def fetch_klines_data(db: Database, days: int = 730):
    """获取K线数据"""
    print("\n" + "=" * 60)
    print(f"步骤2: 获取K线数据（最近{days}天）")
    print("=" * 60)

    fetcher = KlineFetcher(db)

    # 获取所有A股股票
    symbols = db.get_all_symbols(market='A')
    print(f"共 {len(symbols)} 只股票需要更新")

    # 批量更新
    fetcher.run(symbols=symbols, days=days, market='A')


def main():
    """主函数"""
    print("=" * 60)
    print("沪深300成分股数据获取工具")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    # 数据库路径
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.pi-invest', 'stock-db', 'stocks.db'
    )

    db = Database(db_path)

    # 步骤1: 获取股票列表
    stock_count = fetch_hs300_stocks(db)

    if stock_count == 0:
        print("\n❌ 未能获取股票列表，退出")
        return

    # 步骤2: 获取K线数据（2年 = 730天）
    fetch_klines_data(db, days=730)

    print("\n" + "=" * 60)
    print("✅ 数据获取完成！")
    print("=" * 60)

    # 显示统计信息
    conn = db._get_connection()
    cursor = conn.execute("""
        SELECT
            COUNT(DISTINCT symbol) as stocks,
            COUNT(*) as records,
            MIN(date) as earliest,
            MAX(date) as latest
        FROM daily_klines
    """)
    stats = cursor.fetchone()

    print(f"\n📊 数据库统计:")
    print(f"  股票数量: {stats[0]}")
    print(f"  K线记录: {stats[1]}")
    print(f"  日期范围: {stats[2]} 至 {stats[3]}")
    print()


if __name__ == '__main__':
    main()

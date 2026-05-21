#!/usr/bin/env python3
"""
刷新 stock_data_summary 表

这个脚本应该在以下情况运行：
1. 每次更新股票数据后
2. 每次计算因子后
3. 定期维护（每天一次）
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def refresh_summary(db_path: str):
    """刷新股票数据汇总表"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始刷新 stock_data_summary...")

    conn = sqlite3.connect(db_path)

    try:
        # 创建表（如果不存在）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_data_summary (
                symbol TEXT PRIMARY KEY,
                factor_days INTEGER,
                factor_count INTEGER,
                kline_days INTEGER,
                earliest_date TEXT,
                latest_date TEXT,
                last_updated TEXT
            )
        """)

        # 第一步：更新因子统计
        print("  - 更新因子统计...")
        conn.execute("""
            INSERT OR REPLACE INTO stock_data_summary (symbol, factor_days, factor_count, last_updated)
            SELECT
                symbol,
                COUNT(DISTINCT date) as factor_days,
                COUNT(DISTINCT factor_name) as factor_count,
                datetime('now') as last_updated
            FROM factor_values
            GROUP BY symbol
        """)

        # 第二步：更新K线统计
        print("  - 更新K线统计...")
        conn.execute("""
            UPDATE stock_data_summary
            SET
                kline_days = (SELECT COUNT(DISTINCT date) FROM daily_klines WHERE daily_klines.symbol = stock_data_summary.symbol),
                earliest_date = (SELECT MIN(date) FROM daily_klines WHERE daily_klines.symbol = stock_data_summary.symbol),
                latest_date = (SELECT MAX(date) FROM daily_klines WHERE daily_klines.symbol = stock_data_summary.symbol)
        """)

        conn.commit()

        # 统计
        cursor = conn.execute("SELECT COUNT(*) FROM stock_data_summary")
        total = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM stock_data_summary WHERE factor_count >= 30")
        complete = cursor.fetchone()[0]

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 刷新完成")
        print(f"  - 总股票数: {total}")
        print(f"  - 因子完整: {complete}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    # 查找数据库路径
    project_root = Path(__file__).parent.parent.parent
    project_db = project_root / '.pi-invest' / 'stock-db' / 'stocks.db'
    home_db = Path.home() / '.pi-invest' / 'stock-db' / 'stocks.db'

    db_path = project_db if project_db.exists() else home_db

    if not db_path.exists():
        print(f"❌ 数据库不存在: {db_path}")
        sys.exit(1)

    print(f"使用数据库: {db_path}")
    refresh_summary(str(db_path))

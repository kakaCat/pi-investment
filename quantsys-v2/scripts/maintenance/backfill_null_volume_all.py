#!/usr/bin/env python3
"""
修复数据库中volume为NULL的历史数据

策略：
1. 查询所有volume为NULL的股票
2. 按股票分批重新下载数据（从最早的NULL日期开始）
3. 使用UPSERT更新数据库
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

# 设置环境变量使用PostgreSQL
os.environ['QUANT_DB_PROVIDER'] = 'postgres'
os.environ['QUANT_DATABASE_URL'] = 'postgresql://mac@127.0.0.1:5432/quant_investment'
os.environ['QUANT_PG_SCHEMA'] = 'quant'

# 添加旧版 quant 包路径（quantsys-v2 的同级目录）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_QUANT_ROOT = PROJECT_ROOT.parent / 'quant'
sys.path.insert(0, str(LEGACY_QUANT_ROOT))

from quantsys.data.db import Database
from quantsys.data.fetchers.klines import KlineFetcher

def get_symbols_with_null_volume(conn):
    """获取所有有NULL volume的股票及其最早的NULL日期"""
    query = """
        SELECT
            symbol,
            MIN(trade_date) as earliest_null_date,
            MAX(trade_date) as latest_null_date,
            COUNT(*) as null_count
        FROM quant.daily_klines
        WHERE volume IS NULL
        GROUP BY symbol
        ORDER BY symbol
    """

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(query)
    results = cur.fetchall()
    cur.close()

    return [dict(row) for row in results]

def fix_symbol_volume(db: Database, fetcher: KlineFetcher, symbol: str, earliest_date: datetime):
    """修复单个股票的volume数据"""
    # 计算需要下载的天数（从最早的NULL日期到今天）
    # 将date转换为datetime以便计算
    if isinstance(earliest_date, datetime):
        earliest_dt = earliest_date
    else:
        earliest_dt = datetime.combine(earliest_date, datetime.min.time())

    days = (datetime.now() - earliest_dt).days + 10  # 多下载10天确保覆盖

    try:
        # 重新下载数据
        count = fetcher._update_symbol(symbol, days=days, period='daily')
        return True, count
    except Exception as e:
        return False, str(e)

def main():
    print("=" * 80)
    print("修复volume数据")
    print("=" * 80)

    # 连接PostgreSQL数据库
    conn = psycopg2.connect(
        host='127.0.0.1',
        port=5432,
        database='quant_investment',
        user='mac'
    )

    # 连接Database用于KlineFetcher
    db = Database()
    fetcher = KlineFetcher(db)

    # 获取需要修复的股票列表
    print("\n正在查询需要修复的股票...")
    symbols_to_fix = get_symbols_with_null_volume(conn)

    total = len(symbols_to_fix)
    print(f"找到 {total} 只股票需要修复volume数据")

    if total == 0:
        print("没有需要修复的数据")
        return

    # 统计信息
    total_null_records = sum(s['null_count'] for s in symbols_to_fix)
    print(f"总计 {total_null_records:,} 条记录需要修复")

    # 询问确认
    print(f"\n这将重新下载 {total} 只股票的历史数据")
    print("预计耗时: 约 {} 分钟".format(int(total * 0.5)))  # 假设每只股票0.5秒

    response = input("\n是否继续? (y/n): ")
    if response.lower() != 'y':
        print("已取消")
        return

    # 开始修复
    print("\n" + "=" * 80)
    print("开始修复")
    print("=" * 80)

    success_count = 0
    failed_count = 0
    failed_symbols = []

    start_time = time.time()

    for index, item in enumerate(symbols_to_fix, 1):
        symbol = item['symbol']
        earliest_date = item['earliest_null_date']
        null_count = item['null_count']

        # 修复数据
        success, result = fix_symbol_volume(db, fetcher, symbol, earliest_date)

        if success:
            success_count += 1
            print(f"[{index}/{total}] ✓ {symbol} - 更新 {result} 条记录 (原有 {null_count} 条NULL)")
        else:
            failed_count += 1
            failed_symbols.append({'symbol': symbol, 'error': result})
            print(f"[{index}/{total}] ✗ {symbol} - 失败: {result}")

        # 每100只股票显示进度
        if index % 100 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / index
            remaining = (total - index) * avg_time
            print(f"\n进度: {index}/{total} ({index/total*100:.1f}%)")
            print(f"已用时间: {elapsed/60:.1f} 分钟")
            print(f"预计剩余: {remaining/60:.1f} 分钟\n")

    # 完成统计
    elapsed = time.time() - start_time

    print("\n" + "=" * 80)
    print("修复完成")
    print("=" * 80)
    print(f"总计: {total} 只股票")
    print(f"成功: {success_count} 只")
    print(f"失败: {failed_count} 只")
    print(f"耗时: {elapsed/60:.1f} 分钟")

    if failed_symbols:
        print(f"\n失败的股票:")
        for item in failed_symbols[:20]:  # 只显示前20个
            print(f"  {item['symbol']}: {item['error']}")
        if len(failed_symbols) > 20:
            print(f"  ... 还有 {len(failed_symbols) - 20} 只")

    # 验证修复结果
    print("\n" + "=" * 80)
    print("验证修复结果")
    print("=" * 80)

    query = """
        SELECT
            COUNT(*) as null_volume_count,
            COUNT(DISTINCT symbol) as affected_symbols
        FROM quant.daily_klines
        WHERE volume IS NULL
    """

    cur = conn.cursor()
    cur.execute(query)
    result = cur.fetchone()
    cur.close()

    remaining_null = result[0]
    remaining_symbols = result[1]

    print(f"修复前: {total_null_records:,} 条NULL记录")
    print(f"修复后: {remaining_null:,} 条NULL记录")
    print(f"已修复: {total_null_records - remaining_null:,} 条记录")
    print(f"修复率: {(total_null_records - remaining_null) / total_null_records * 100:.1f}%")

    if remaining_null > 0:
        print(f"\n⚠️  仍有 {remaining_symbols} 只股票的 {remaining_null:,} 条记录volume为NULL")
        print("这些可能是退市股票或数据源不再提供的股票")

    # 关闭连接
    conn.close()

if __name__ == '__main__':
    main()

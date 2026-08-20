#!/usr/bin/env python3
"""
智能修复volume数据 - 只修复活跃股票

策略：
1. 只修复最近30天有交易的股票（活跃股票）
2. 使用并行下载加速
3. 跳过退市/停牌股票
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from concurrent.futures import ThreadPoolExecutor, as_completed

# 设置环境变量使用PostgreSQL
os.environ['QUANT_DB_PROVIDER'] = 'postgres'
os.environ['QUANT_DATABASE_URL'] = 'postgresql://mac@127.0.0.1:5432/quant_investment'
os.environ['QUANT_PG_SCHEMA'] = 'quant'

# 添加旧版 quant 包路径（quantsys-v2 的同级目录）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_QUANT_ROOT = PROJECT_ROOT.parent / 'quant'

from quantsys.data.db import Database
from quantsys.data.fetchers.klines import KlineFetcher

def get_active_symbols_with_null_volume(conn):
    """获取最近30天有交易且volume为NULL的活跃股票"""
    query = """
        WITH recent_trades AS (
            SELECT DISTINCT symbol
            FROM quant.daily_klines
            WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days'
              AND close IS NOT NULL
        ),
        null_volume_symbols AS (
            SELECT
                symbol,
                MIN(trade_date) as earliest_null_date,
                MAX(trade_date) as latest_null_date,
                COUNT(*) as null_count
            FROM quant.daily_klines
            WHERE volume IS NULL
            GROUP BY symbol
        )
        SELECT
            n.symbol,
            n.earliest_null_date,
            n.latest_null_date,
            n.null_count
        FROM null_volume_symbols n
        INNER JOIN recent_trades r ON n.symbol = r.symbol
        ORDER BY n.symbol
    """

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(query)
    results = cur.fetchall()
    cur.close()

    return [dict(row) for row in results]

def fix_symbol_volume(db: Database, fetcher: KlineFetcher, symbol: str, earliest_date):
    """修复单个股票的volume数据"""
    try:
        # 将date转换为datetime以便计算
        if isinstance(earliest_date, datetime):
            earliest_dt = earliest_date
        else:
            earliest_dt = datetime.combine(earliest_date, datetime.min.time())

        days = (datetime.now() - earliest_dt).days + 10

        # 重新下载数据
        count = fetcher._update_symbol(symbol, days=days, period='daily')
        return symbol, True, count
    except Exception as e:
        return symbol, False, str(e)

def main():
    print("=" * 80)
    print("智能修复volume数据（仅活跃股票）")
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

    # 获取需要修复的活跃股票列表
    print("\n正在查询需要修复的活跃股票（最近30天有交易）...")
    symbols_to_fix = get_active_symbols_with_null_volume(conn)

    if not symbols_to_fix:
        print("没有需要修复的活跃股票")
        conn.close()
        return

    total_symbols = len(symbols_to_fix)
    total_null_records = sum(s['null_count'] for s in symbols_to_fix)

    print(f"找到 {total_symbols} 只活跃股票需要修复volume数据")
    print(f"总计 {total_null_records:,} 条记录需要修复")
    print(f"\n使用4个并行线程下载")
    print(f"预计耗时: 约 {total_symbols * 0.5:.0f} 分钟")

    response = input("\n是否继续? (y/n): ")
    if response.lower() != 'y':
        print("已取消")
        conn.close()
        return

    # 并行修复
    print("\n" + "=" * 80)
    print("开始修复（并行下载）")
    print("=" * 80)

    success_count = 0
    fail_count = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=4) as executor:
        # 提交所有任务
        futures = {
            executor.submit(
                fix_symbol_volume,
                db,
                fetcher,
                s['symbol'],
                s['earliest_null_date']
            ): s for s in symbols_to_fix
        }

        # 处理完成的任务
        for i, future in enumerate(as_completed(futures), 1):
            symbol_info = futures[future]
            symbol, success, result = future.result()

            if success:
                success_count += 1
                print(f"[{i}/{total_symbols}] ✓ {symbol} - 成功更新 {result} 条记录")
            else:
                fail_count += 1
                print(f"[{i}/{total_symbols}] ✗ {symbol} - 失败: {result}")

            # 每10个股票显示进度
            if i % 10 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                remaining = (total_symbols - i) / rate if rate > 0 else 0
                print(f"    进度: {i}/{total_symbols} ({i/total_symbols*100:.1f}%) | "
                      f"速度: {rate:.1f} 股票/秒 | 剩余时间: {remaining/60:.1f} 分钟")

    elapsed_time = time.time() - start_time

    # 显示统计
    print("\n" + "=" * 80)
    print("修复完成")
    print("=" * 80)
    print(f"总耗时: {elapsed_time/60:.1f} 分钟")
    print(f"成功: {success_count} 只股票")
    print(f"失败: {fail_count} 只股票")
    print(f"成功率: {success_count/total_symbols*100:.1f}%")

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

    print(f"修复前: {total_null_records:,} 条NULL记录（活跃股票）")
    print(f"修复后: {remaining_null:,} 条NULL记录（全部股票）")

    # 关闭连接
    conn.close()
    print("\n✓ 完成")

if __name__ == '__main__':
    main()

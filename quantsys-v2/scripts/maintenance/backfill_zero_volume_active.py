#!/usr/bin/env python3
"""
重新下载真实的成交量数据

策略：
1. 只处理最近有交易的活跃股票（最近30天有成交记录）
2. 只重新下载volume=0的日期范围
3. 使用并行下载加速（8线程）
4. 显示详细进度
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
sys.path.insert(0, str(LEGACY_QUANT_ROOT))

from quantsys.data.db import Database
from quantsys.data.fetchers.klines import KlineFetcher

def get_active_symbols_with_zero_volume(conn):
    """获取最近30天有交易且有volume=0记录的活跃股票"""
    query = """
        WITH recent_trades AS (
            -- 最近30天有正常成交量的股票（说明是活跃股票）
            SELECT DISTINCT symbol
            FROM quant.daily_klines
            WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days'
              AND volume > 0
        ),
        zero_volume_symbols AS (
            -- 有volume=0记录的股票
            SELECT
                symbol,
                MIN(trade_date) as earliest_zero_date,
                MAX(trade_date) as latest_zero_date,
                COUNT(*) as zero_count
            FROM quant.daily_klines
            WHERE volume = 0
            GROUP BY symbol
        )
        SELECT
            z.symbol,
            s.name,
            z.earliest_zero_date,
            z.latest_zero_date,
            z.zero_count
        FROM zero_volume_symbols z
        INNER JOIN recent_trades r ON z.symbol = r.symbol
        INNER JOIN quant.stocks s ON z.symbol = s.symbol
        ORDER BY z.zero_count DESC
        LIMIT 500  -- 限制最多处理500只股票
    """

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(query)
    results = cur.fetchall()
    cur.close()

    return [dict(row) for row in results]

def fix_symbol_volume(db: Database, fetcher: KlineFetcher, symbol: str, name: str, earliest_date, latest_date):
    """重新下载单个股票的volume数据"""
    try:
        # 计算需要下载的天数
        if isinstance(earliest_date, datetime):
            earliest_dt = earliest_date
        else:
            earliest_dt = datetime.combine(earliest_date, datetime.min.time())

        # 从最早的zero日期开始下载到现在
        days = (datetime.now() - earliest_dt).days + 10

        # 重新下载数据
        count = fetcher._update_symbol(symbol, days=days, period='daily')

        return {
            'symbol': symbol,
            'name': name,
            'success': True,
            'count': count,
            'error': None
        }
    except Exception as e:
        return {
            'symbol': symbol,
            'name': name,
            'success': False,
            'count': 0,
            'error': str(e)
        }

def main():
    print("=" * 80)
    print("重新下载真实成交量数据（仅活跃股票）")
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
    symbols_to_fix = get_active_symbols_with_zero_volume(conn)

    if not symbols_to_fix:
        print("没有需要修复的活跃股票")
        conn.close()
        return

    total_symbols = len(symbols_to_fix)
    total_zero_records = sum(s['zero_count'] for s in symbols_to_fix)

    print(f"\n找到 {total_symbols} 只活跃股票需要重新下载volume数据")
    print(f"总计 {total_zero_records:,} 条volume=0的记录需要修复")
    print(f"\n使用8个并行线程下载")
    print(f"预计耗时: 约 {total_symbols * 0.3:.0f} 分钟")

    # 显示前10只股票
    print("\n前10只需要修复的股票：")
    print(f"{'代码':<10} {'名称':<15} {'Zero记录数':<12} {'日期范围'}")
    print("-" * 80)
    for s in symbols_to_fix[:10]:
        date_range = f"{s['earliest_zero_date']} ~ {s['latest_zero_date']}"
        print(f"{s['symbol']:<10} {s['name']:<15} {s['zero_count']:<12} {date_range}")

    if total_symbols > 10:
        print(f"... 还有 {total_symbols - 10} 只股票")

    # 检查是否有命令行参数 --yes 或 -y
    import sys
    auto_confirm = '--yes' in sys.argv or '-y' in sys.argv

    if not auto_confirm:
        response = input("\n是否继续? (y/n): ")
        if response.lower() != 'y':
            print("已取消")
            conn.close()
            return
    else:
        print("\n自动确认，开始下载...")

    # 并行修复
    print("\n" + "=" * 80)
    print("开始重新下载（并行8线程）")
    print("=" * 80)

    success_count = 0
    fail_count = 0
    total_updated = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=8) as executor:
        # 提交所有任务
        futures = {
            executor.submit(
                fix_symbol_volume,
                db,
                fetcher,
                s['symbol'],
                s['name'],
                s['earliest_zero_date'],
                s['latest_zero_date']
            ): s for s in symbols_to_fix
        }

        # 处理完成的任务
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()

            if result['success']:
                success_count += 1
                total_updated += result['count']
                print(f"[{i}/{total_symbols}] ✓ {result['symbol']} {result['name']:<10} - 更新 {result['count']} 条记录")
            else:
                fail_count += 1
                error_msg = result['error'][:50] if result['error'] else 'Unknown'
                print(f"[{i}/{total_symbols}] ✗ {result['symbol']} {result['name']:<10} - 失败: {error_msg}")

            # 每20个股票显示进度
            if i % 20 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                remaining = (total_symbols - i) / rate if rate > 0 else 0
                print(f"    进度: {i}/{total_symbols} ({i/total_symbols*100:.1f}%) | "
                      f"速度: {rate:.2f} 股票/秒 | 剩余时间: {remaining/60:.1f} 分钟")

    elapsed_time = time.time() - start_time

    # 显示统计
    print("\n" + "=" * 80)
    print("下载完成")
    print("=" * 80)
    print(f"总耗时: {elapsed_time/60:.1f} 分钟")
    print(f"成功: {success_count} 只股票")
    print(f"失败: {fail_count} 只股票")
    print(f"成功率: {success_count/total_symbols*100:.1f}%")
    print(f"更新记录数: {total_updated:,} 条")

    # 验证修复结果
    print("\n" + "=" * 80)
    print("验证修复结果")
    print("=" * 80)

    # 检查volume=0的记录数变化
    query = """
        SELECT
            COUNT(*) as zero_volume_count,
            COUNT(DISTINCT symbol) as affected_symbols
        FROM quant.daily_klines
        WHERE volume = 0
    """

    cur = conn.cursor()
    cur.execute(query)
    result = cur.fetchone()
    cur.close()

    remaining_zero = result[0]
    remaining_symbols = result[1]

    print(f"修复前: {total_zero_records:,} 条volume=0记录（活跃股票）")
    print(f"修复后: {remaining_zero:,} 条volume=0记录（全部股票）")
    print(f"已修复: {total_zero_records - remaining_zero:,} 条记录")

    if remaining_zero > 0:
        print(f"\n⚠️  仍有 {remaining_symbols} 只股票的 {remaining_zero:,} 条记录volume=0")
        print("这些可能是：")
        print("  1. 非活跃股票（最近30天无交易）")
        print("  2. 真实停牌日期（成交量确实为0）")
        print("  3. 数据源不再提供的退市股票")

    # 关闭连接
    conn.close()
    print("\n✓ 完成")

if __name__ == '__main__':
    main()

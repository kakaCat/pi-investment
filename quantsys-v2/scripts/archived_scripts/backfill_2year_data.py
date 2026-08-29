#!/usr/bin/env python3
"""
补充2年数据不足的股票
- 针对2年内K线数据 < 384条的股票
- 使用多数据源自动切换
- 补充从2年前到今天的完整数据
"""

import sys
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# 添加项目根目录到路径

from adapters.outbound.repositories import KlineORMRepository
from adapters.outbound.datasources.manager import get_data_source_manager

def fetch_2year_klines(symbol: str) -> tuple:
    """
    获取指定股票2年的K线数据

    Args:
        symbol: 股票代码（纯数字）

    Returns:
        (symbol, success, data, source, error)
    """
    try:
        manager = get_data_source_manager()

        # 2年前到今天
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=730)).strftime('%Y%m%d')

        response = manager.get_klines(
            symbol=symbol,
            period='daily',
            start_date=start_date,
            end_date=end_date
        )

        if response.success and response.data:
            source = response.metadata.get('source', 'unknown') if response.metadata else 'unknown'
            return (symbol, True, response.data, source, None)
        else:
            return (symbol, False, None, None, response.error or "Unknown error")

    except Exception as e:
        return (symbol, False, None, None, str(e))

def main():
    print("=" * 80)
    print("补充2年数据不足的股票")
    print("=" * 80)

    # 查询需要补充的股票（2年内数据 < 384条）
    import psycopg2

    conn = psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=os.environ.get('PGPORT', '5432'),
        database=os.environ.get('PGDATABASE', 'quant_investment'),
        user=os.environ.get('PGUSER', os.environ.get('USER', 'postgres'))
    )
    cur = conn.cursor()

    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

    cur.execute(f"""
        WITH two_year_data AS (
            SELECT
                symbol,
                COUNT(*) as kline_count,
                MAX(trade_date) as latest_date
            FROM quant.daily_klines
            WHERE trade_date >= '{two_years_ago}'
            GROUP BY symbol
        )
        SELECT
            symbol,
            kline_count,
            latest_date
        FROM two_year_data
        WHERE kline_count < 384
        ORDER BY kline_count DESC, symbol
    """)

    stocks_to_update = []
    for row in cur.fetchall():
        symbol, kline_count, latest_date = row
        stocks_to_update.append({
            'symbol': symbol,
            'current_count': kline_count,
            'latest_date': latest_date.strftime('%Y-%m-%d') if latest_date else 'N/A'
        })

    cur.close()
    conn.close()

    total = len(stocks_to_update)
    print(f"待补充股票数: {total}")
    print(f"数据源策略: 多源自动切换（AkShare → 东方财富 → 新浪财经）")
    print(f"时间范围: {two_years_ago} ~ {datetime.now().strftime('%Y-%m-%d')}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if total == 0:
        print("✅ 所有股票2年数据都是完整的！")
        return

    # 初始化repository
    repo = KlineORMRepository()

    # 并发补充（使用2个worker）
    success_count = 0
    fail_count = 0
    total_new_records = 0
    source_stats = {}

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {}

        for stock in stocks_to_update:
            future = executor.submit(
                fetch_2year_klines,
                stock['symbol']
            )
            futures[future] = stock
            time.sleep(0.5)  # 请求间隔

        for i, future in enumerate(as_completed(futures), 1):
            stock = futures[future]
            symbol = stock['symbol']
            current_count = stock['current_count']

            try:
                symbol_ret, success, data, source, error = future.result()

                if success and data:
                    # 保存到数据库（会自动去重）
                    new_records = repo.save_daily_klines(symbol_ret, data)
                    success_count += 1
                    total_new_records += new_records

                    # 统计数据源
                    if source:
                        source_stats[source] = source_stats.get(source, 0) + 1

                    elapsed = time.time() - start_time
                    speed = i / elapsed if elapsed > 0 else 0
                    eta = (total - i) / speed if speed > 0 else 0

                    print(f"[{i}/{total}] {symbol} ✓ {len(data)}条 (已有{current_count}, +{new_records}新增) | "
                          f"{success_count}✓ {fail_count}✗ | {speed:.1f}/s ETA {int(eta)}s")
                else:
                    fail_count += 1
                    error_msg = error[:60] if error else 'Unknown'
                    print(f"[{i}/{total}] {symbol} ❌ {error_msg}")

            except Exception as e:
                fail_count += 1
                print(f"[{i}/{total}] {symbol} ❌ Exception: {str(e)[:60]}")

            # 每50个显示进度
            if i % 50 == 0:
                print()
                print(f"进度: {i}/{total} ({i*100/total:.1f}%)")
                print(f"成功: {success_count}, 失败: {fail_count}, 新增记录: {total_new_records}")
                print()

    elapsed = time.time() - start_time

    print()
    print("=" * 80)
    print("补充完成")
    print("=" * 80)
    print(f"处理股票数: {total}")
    print(f"成功: {success_count} ({success_count*100/total:.1f}%)")
    print(f"失败: {fail_count} ({fail_count*100/total:.1f}%)")
    print(f"新增K线记录: {total_new_records}")
    print(f"总耗时: {elapsed:.1f}秒 ({elapsed/60:.1f}分钟)")
    print(f"平均速度: {total/elapsed:.2f} 股/秒")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if source_stats:
        print()
        print("数据源统计:")
        for source, count in sorted(source_stats.items(), key=lambda x: -x[1]):
            print(f"  {source}: {count} ({count*100/success_count:.1f}%)")

if __name__ == '__main__':
    main()

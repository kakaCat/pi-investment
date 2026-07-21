#!/usr/bin/env python3
"""
补充最近数据缺失的股票K线数据
- 针对最新日期 <= 2026-05-29 的股票
- 补充从最后日期到今天的数据
- 使用多数据源自动切换
"""

import sys
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from adapters.outbound.repositories import KlineORMRepository
from adapters.outbound.datasources.manager import get_data_provider_manager

def fetch_recent_klines(symbol: str, start_date: str) -> tuple:
    """
    获取指定股票从 start_date 到今天的K线数据

    Args:
        symbol: 股票代码（纯数字，如 "600519"）
        start_date: 起始日期 (YYYY-MM-DD)

    Returns:
        (symbol, success, data, error)
    """
    try:
        manager = get_data_provider_manager()
        end_date = datetime.now().strftime('%Y%m%d')
        start_date_str = start_date.replace('-', '')

        response = manager.get_klines(
            symbol=symbol,
            period='daily',
            start_date=start_date_str,
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
    print("补充最近数据缺失的股票K线")
    print("=" * 80)

    # 读取数据库中需要更新的股票
    repo = KlineORMRepository()

    # 查询需要更新的股票（最新日期 <= 2026-05-29）
    stocks_to_update = []

    # 使用 psycopg2 直接查询
    import psycopg2

    # 直接使用数据库连接参数
    conn = psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=os.environ.get('PGPORT', '5432'),
        database=os.environ.get('PGDATABASE', 'quant_investment'),
        user=os.environ.get('PGUSER', os.environ.get('USER', 'postgres'))
    )
    cur = conn.cursor()

    cur.execute("""
        SELECT
            symbol,
            MAX(trade_date) as latest_date,
            COUNT(*) as total_records
        FROM quant.daily_klines
        GROUP BY symbol
        HAVING MAX(trade_date) <= '2026-05-29'
        ORDER BY MAX(trade_date) DESC, symbol
    """)

    for row in cur.fetchall():
        symbol, latest_date, total_records = row
        # 从最后日期的下一天开始补充
        next_day = (latest_date + timedelta(days=1)).strftime('%Y-%m-%d')
        stocks_to_update.append({
            'symbol': symbol,
            'latest_date': latest_date.strftime('%Y-%m-%d'),
            'start_date': next_day,
            'total_records': total_records
        })

    cur.close()
    conn.close()

    total = len(stocks_to_update)
    print(f"待更新股票数: {total}")
    print(f"更新策略: 多数据源自动切换（AkShare → 东方财富 → 新浪财经）")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if total == 0:
        print("✅ 所有股票数据都是最新的！")
        return

    # 并发更新（使用2个worker，避免限流）
    success_count = 0
    fail_count = 0
    total_new_records = 0
    source_stats = {}

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {}

        for stock in stocks_to_update:
            future = executor.submit(
                fetch_recent_klines,
                stock['symbol'],
                stock['start_date']
            )
            futures[future] = stock
            time.sleep(0.3)  # 请求间隔

        for i, future in enumerate(as_completed(futures), 1):
            stock = futures[future]
            symbol = stock['symbol']
            latest_date = stock['latest_date']

            try:
                symbol_ret, success, data, source, error = future.result()

                if success and data:
                    # 保存到数据库
                    new_records = repo.save_daily_klines(symbol_ret, data)
                    success_count += 1
                    total_new_records += new_records

                    # 统计数据源
                    source_stats[source] = source_stats.get(source, 0) + 1

                    elapsed = time.time() - start_time
                    speed = i / elapsed if elapsed > 0 else 0
                    eta = (total - i) / speed if speed > 0 else 0

                    print(f"[{i}/{total}] {symbol} ✓ +{new_records}条 (从{latest_date}) | "
                          f"{success_count}✓ {fail_count}✗ | {speed:.1f}/s ETA {int(eta)}s")
                else:
                    fail_count += 1
                    print(f"[{i}/{total}] {symbol} ❌ {error[:60] if error else 'Unknown'}")

            except Exception as e:
                fail_count += 1
                print(f"[{i}/{total}] {symbol} ❌ Exception: {str(e)[:60]}")

            # 每100个显示进度
            if i % 100 == 0:
                print()
                print(f"进度: {i}/{total} ({i*100/total:.1f}%)")
                print(f"成功: {success_count}, 失败: {fail_count}, 新增记录: {total_new_records}")
                print()

    elapsed = time.time() - start_time

    print()
    print("=" * 80)
    print("更新完成")
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

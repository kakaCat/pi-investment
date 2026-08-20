#!/usr/bin/env python3
"""
直接使用AkShare补充最近数据缺失的股票K线数据
- 针对最新日期 <= 2026-05-29 的股票
- 排除北交所退市股票（920xxx）
- 直接调用akshare，不通过DataSourceManager
"""

import sys
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import pandas as pd

# 添加项目根目录到路径

from adapters.outbound.repositories import KlineORMRepository

def fetch_recent_klines_direct(symbol: str, start_date: str) -> tuple:
    """
    直接使用AkShare获取K线数据

    Args:
        symbol: 股票代码（纯数字）
        start_date: 起始日期 (YYYY-MM-DD)

    Returns:
        (symbol, success, data_list, error)
    """
    try:
        import akshare as ak

        end_date = datetime.now().strftime('%Y%m%d')
        start_date_str = start_date.replace('-', '')

        # 调用akshare获取前复权日线数据
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date_str,
            end_date=end_date,
            adjust="qfq"
        )

        if df is None or df.empty:
            return (symbol, False, None, "No data returned")

        # 转换为标准格式
        data_list = []
        for _, row in df.iterrows():
            data_list.append({
                'trade_date': pd.to_datetime(row['日期']).strftime('%Y-%m-%d'),
                'open': float(row['开盘']),
                'high': float(row['最高']),
                'low': float(row['最低']),
                'close': float(row['收盘']),
                'volume': float(row['成交量']),
                'amount': float(row['成交额']),
                'turnover_rate': float(row['换手率']) if '换手率' in row and pd.notna(row['换手率']) else 0.0
            })

        return (symbol, True, data_list, None)

    except Exception as e:
        return (symbol, False, None, str(e))

def main():
    print("=" * 80)
    print("补充最近数据缺失的股票K线（直接AkShare方法）")
    print("=" * 80)

    # 查询需要更新的股票（排除北交所退市股票）
    import psycopg2

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
        WHERE symbol NOT LIKE '920%'  -- 排除北交所退市股票
        GROUP BY symbol
        HAVING MAX(trade_date) <= '2026-05-29'
        ORDER BY MAX(trade_date) DESC, symbol
    """)

    stocks_to_update = []
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
    print(f"待更新股票数: {total} (已排除北交所退市股票)")
    print(f"数据源: AkShare (直接调用)")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if total == 0:
        print("✅ 所有股票数据都是最新的！")
        return

    # 初始化repository
    repo = KlineORMRepository()

    # 并发更新（使用1个worker，避免AkShare限流）
    success_count = 0
    fail_count = 0
    total_new_records = 0

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = {}

        for stock in stocks_to_update:
            future = executor.submit(
                fetch_recent_klines_direct,
                stock['symbol'],
                stock['start_date']
            )
            futures[future] = stock
            time.sleep(0.5)  # 请求间隔0.5秒

        for i, future in enumerate(as_completed(futures), 1):
            stock = futures[future]
            symbol = stock['symbol']
            latest_date = stock['latest_date']

            try:
                symbol_ret, success, data, error = future.result()

                if success and data:
                    # 保存到数据库
                    new_records = repo.save_daily_klines(symbol_ret, data)
                    success_count += 1
                    total_new_records += new_records

                    elapsed = time.time() - start_time
                    speed = i / elapsed if elapsed > 0 else 0
                    eta = (total - i) / speed if speed > 0 else 0

                    print(f"[{i}/{total}] {symbol} ✓ +{new_records}条 (从{latest_date}) | "
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
    print("更新完成")
    print("=" * 80)
    print(f"处理股票数: {total}")
    print(f"成功: {success_count} ({success_count*100/total:.1f}%)")
    print(f"失败: {fail_count} ({fail_count*100/total:.1f}%)")
    print(f"新增K线记录: {total_new_records}")
    print(f"总耗时: {elapsed:.1f}秒 ({elapsed/60:.1f}分钟)")
    print(f"平均速度: {total/elapsed:.2f} 股/秒")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    main()

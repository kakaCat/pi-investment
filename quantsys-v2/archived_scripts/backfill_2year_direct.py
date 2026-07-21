#!/usr/bin/env python3
"""
补充2年数据不足的股票（直接AkShare方法）
- 针对2年内K线数据 < 384条的股票
- 直接调用akshare，不通过DataSourceManager
- 补充从2年前到今天的完整数据
"""

import sys
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from adapters.outbound.repositories import KlineORMRepository

def fetch_2year_klines_direct(symbol: str) -> tuple:
    """
    直接使用AkShare获取2年K线数据

    Args:
        symbol: 股票代码（纯数字）

    Returns:
        (symbol, success, data_list, error)
    """
    try:
        import akshare as ak

        # 2年前到今天
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=730)).strftime('%Y%m%d')

        # 调用akshare获取前复权日线数据
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )

        if df is None or df.empty:
            return (symbol, False, None, "No data returned")

        # 转换为标准格式（包含symbol）
        data_list = []
        for _, row in df.iterrows():
            data_list.append({
                'symbol': symbol,
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
    print("补充2年数据不足的股票（直接AkShare方法）")
    print("=" * 80)

    # 数据库连接
    import psycopg2
    from psycopg2.extras import execute_batch

    conn = psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=os.environ.get('PGPORT', '5432'),
        database=os.environ.get('PGDATABASE', 'quant_investment'),
        user=os.environ.get('PGUSER', os.environ.get('USER', 'postgres'))
    )

    two_years_ago = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

    # 查询需要补充的股票
    cur = conn.cursor()
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
            AND symbol NOT LIKE '920%'  -- 排除北交所退市股票
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

    total = len(stocks_to_update)
    print(f"待补充股票数: {total} (已排除北交所退市股票)")
    print(f"数据源: AkShare (直接调用)")
    print(f"时间范围: {two_years_ago} ~ {datetime.now().strftime('%Y-%m-%d')}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if total == 0:
        print("✅ 所有股票2年数据都是完整的！")
        cur.close()
        conn.close()
        return

    # UPSERT SQL
    upsert_sql = """
        INSERT INTO quant.daily_klines (symbol, trade_date, open, high, low, close, volume, amount, turnover_rate)
        VALUES (%(symbol)s, %(trade_date)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(amount)s, %(turnover_rate)s)
        ON CONFLICT (symbol, trade_date)
        DO UPDATE SET
            open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
            close = EXCLUDED.close, volume = EXCLUDED.volume,
            amount = EXCLUDED.amount, turnover_rate = EXCLUDED.turnover_rate
    """

    # 单线程补充（避免AkShare限流）
    success_count = 0
    fail_count = 0
    total_new_records = 0

    start_time = time.time()

    for i, stock in enumerate(stocks_to_update, 1):
        symbol = stock['symbol']
        current_count = stock['current_count']

        symbol_ret, success, data, error = fetch_2year_klines_direct(symbol)

        if success and data:
            # 保存到数据库
            try:
                execute_batch(cur, upsert_sql, data, page_size=100)
                conn.commit()
                new_records = len(data)
                success_count += 1
                total_new_records += new_records

                elapsed = time.time() - start_time
                speed = i / elapsed if elapsed > 0 else 0
                eta = (total - i) / speed if speed > 0 else 0

                print(f"[{i}/{total}] {symbol} ✓ {len(data)}条 (已有{current_count}, +{new_records}新增) | "
                      f"{success_count}✓ {fail_count}✗ | {speed:.2f}/s ETA {int(eta)}s")
            except Exception as e:
                conn.rollback()
                fail_count += 1
                print(f"[{i}/{total}] {symbol} ❌ DB Error: {str(e)[:60]}")
        else:
            fail_count += 1
            error_msg = error[:60] if error else 'Unknown'
            print(f"[{i}/{total}] {symbol} ❌ {error_msg}")

        # 每50个显示进度
        if i % 50 == 0:
            print()
            print(f"进度: {i}/{total} ({i*100/total:.1f}%)")
            print(f"成功: {success_count}, 失败: {fail_count}, 新增记录: {total_new_records}")
            print()

        # 请求间隔（避免限流）
        time.sleep(0.5)

    cur.close()
    conn.close()

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

if __name__ == '__main__':
    main()

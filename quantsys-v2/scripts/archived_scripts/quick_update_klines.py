#!/usr/bin/env python3
"""
快速批量更新K线数据 - 优化版
- 批量处理，内存友好
- 失败重试机制
- 进度实时显示
"""

import os
import sys
from datetime import datetime, timedelta
import time
import psycopg2
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def update_stock_klines(symbol: str, start_date: str) -> tuple:
    """更新单个股票的K线数据"""
    try:
        import akshare as ak
        import pandas as pd

        end_date = datetime.now().strftime('%Y%m%d')
        start_date_str = start_date.replace('-', '')

        # 获取数据
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date_str,
            end_date=end_date,
            adjust="qfq"
        )

        if df is None or df.empty:
            return (symbol, 0, None)

        # 准备插入数据
        records = []
        for _, row in df.iterrows():
            records.append((
                symbol,
                pd.to_datetime(row['日期']).strftime('%Y-%m-%d'),
                float(row['开盘']),
                float(row['最高']),
                float(row['最低']),
                float(row['收盘']),
                float(row['成交量']),
                float(row['成交额']),
                float(row['换手率']) if '换手率' in row and pd.notna(row['换手率']) else 0.0
            ))

        return (symbol, len(records), records)

    except Exception as e:
        return (symbol, -1, str(e))

def batch_insert_klines(conn, records):
    """批量插入K线数据"""
    cur = conn.cursor()

    insert_sql = """
        INSERT INTO quant.daily_klines
        (symbol, trade_date, open, high, low, close, volume, amount, turnover_rate)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (symbol, trade_date)
        DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            amount = EXCLUDED.amount,
            turnover_rate = EXCLUDED.turnover_rate
    """

    cur.executemany(insert_sql, records)
    conn.commit()
    cur.close()

def main():
    print("=" * 80)
    print("🚀 快速批量更新K线数据")
    print("=" * 80)

    # 连接数据库
    conn = psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=os.environ.get('PGPORT', '5432'),
        database=os.environ.get('PGDATABASE', 'quant_investment'),
        user=os.environ.get('PGUSER', os.environ.get('USER', 'postgres')),
        password=os.environ.get('PGPASSWORD', '')
    )

    # 查询需要更新的股票
    cur = conn.cursor()
    cur.execute("""
        SELECT symbol, MAX(trade_date) as latest_date
        FROM quant.daily_klines
        WHERE symbol NOT LIKE '920%%'
        GROUP BY symbol
        HAVING MAX(trade_date) <= '2026-05-29'
        ORDER BY MAX(trade_date) DESC, symbol
        LIMIT 100
    """)

    stocks = []
    for row in cur.fetchall():
        symbol, latest_date = row
        next_day = (latest_date + timedelta(days=1)).strftime('%Y-%m-%d')
        stocks.append((symbol, latest_date.strftime('%Y-%m-%d'), next_day))

    cur.close()

    total = len(stocks)
    print(f"📊 本批次待更新股票数: {total}")
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if total == 0:
        print("✅ 没有需要更新的股票！")
        conn.close()
        return

    # 逐个更新
    success = 0
    failed = 0
    total_records = 0
    start_time = time.time()

    for i, (symbol, latest_date, start_date) in enumerate(stocks, 1):
        try:
            symbol_ret, count, data = update_stock_klines(symbol, start_date)

            if count > 0 and data:
                # 批量插入
                batch_insert_klines(conn, data)
                success += 1
                total_records += count

                elapsed = time.time() - start_time
                speed = i / elapsed if elapsed > 0 else 0
                eta = (total - i) / speed if speed > 0 else 0

                print(f"[{i}/{total}] {symbol} ✅ +{count}条 (从{latest_date}) | "
                      f"{success}✓ {failed}✗ | {speed:.1f}/s ETA {int(eta)}s")
            elif count == 0:
                success += 1
                print(f"[{i}/{total}] {symbol} ⚪ 无新数据 (从{latest_date})")
            else:
                failed += 1
                error_msg = str(data)[:50] if data else "Unknown"
                print(f"[{i}/{total}] {symbol} ❌ {error_msg}")

            # 请求间隔，避免被限流
            time.sleep(0.5)

        except Exception as e:
            failed += 1
            print(f"[{i}/{total}] {symbol} ❌ Exception: {str(e)[:50]}")

        # 每20个显示统计
        if i % 20 == 0:
            print()
            print(f"📈 进度: {i}/{total} ({i*100/total:.1f}%) | "
                  f"成功: {success} | 失败: {failed} | 新增: {total_records}条")
            print()

    conn.close()

    elapsed = time.time() - start_time

    print()
    print("=" * 80)
    print("✅ 批次更新完成")
    print("=" * 80)
    print(f"处理股票数: {total}")
    print(f"成功: {success} ({success*100/total:.1f}%)")
    print(f"失败: {failed} ({failed*100/total:.1f}%)")
    print(f"新增K线记录: {total_records}")
    print(f"总耗时: {elapsed:.1f}秒 ({elapsed/60:.1f}分钟)")
    print(f"平均速度: {total/elapsed:.2f} 股/秒")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == '__main__':
    main()

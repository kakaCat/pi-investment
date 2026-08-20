"""Import 6-year K-line data for 沪深300 stocks from Sina Finance to PostgreSQL.
Includes auto-registration of missing stocks before import.
Usage: python scripts/import_hs300_klines.py [--datalen 1500] [--delay 0.8]
"""
import json, sys, os, ssl, time, argparse
from urllib.request import Request, urlopen
from urllib.error import URLError
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_batch
import akshare as ak

SINA_KLINES_URL = (
    'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
    'CN_MarketData.getKLineData'
)


def sina_symbol(sym: str) -> str:
    sym = sym.strip().upper().replace('.SH', '').replace('.SZ', '')
    if sym.startswith('6') or sym.startswith('5') or sym.startswith('51'):
        return f'sh{sym}'
    return f'sz{sym}'


def fetch_klines_sina(symbol: str, datalen: int = 1500) -> list:
    if datalen == 0:
        return []
    url = f'{SINA_KLINES_URL}?symbol={symbol}&scale=240&ma=no&datalen={datalen}'
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
    try:
        with urlopen(req, context=ctx, timeout=30) as resp:
            raw = resp.read()
            for enc in ('gbk', 'gb2312', 'utf-8'):
                try:
                    return json.loads(raw.decode(enc))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            return []
    except URLError as e:
        sys.stderr.write(f"[{symbol}] ERROR: {e}\n")
        return []


def get_hs300_symbols() -> dict:
    """Returns {'pure_code': 'stock name'} for HS300 components (no suffix)."""
    df = ak.index_stock_cons(symbol='000300')
    symbols = {}
    for _, row in df.iterrows():
        code = row['品种代码']
        name = row['品种名称']
        symbols[code] = name
    return symbols


def register_missing_stocks(cursor, hs300: dict):
    """Insert HS300 stocks that don't exist in quant.stocks yet."""
    cursor.execute('SELECT symbol FROM quant.stocks')
    existing = set(row[0] for row in cursor.fetchall())

    missing = {s: n for s, n in hs300.items() if s not in existing}
    if not missing:
        return 0

    insert_sql = '''
        INSERT INTO quant.stocks (symbol, name, market, is_st, is_suspended) 
        VALUES (%s, %s, %s, false, false)
        ON CONFLICT (symbol) DO NOTHING
    '''
    for sym, name in missing.items():
        # 使用纯数字代码，通过前缀判断市场（6开头=SH，其他=SZ）
        market = 'SH' if sym.startswith(('6', '5')) else 'SZ'
        cursor.execute(insert_sql, (sym, name, market))
    cursor.connection.commit()
    return len(missing)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--datalen', type=int, default=1500, help='Number of daily bars to fetch')
    parser.add_argument('--delay', type=float, default=0.8, help='Delay between requests (seconds)')
    parser.add_argument('--limit', type=int, default=0, help='Limit to first N stocks (0=all)')
    args = parser.parse_args()

    print(f"🚀 沪深300 K线数据导入")
    print(f"   datalen: {args.datalen} bars (~{args.datalen//250} yrs)")
    print(f"   delay:   {args.delay}s")
    print(f"   started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Get HS300 symbols
    print("📋 获取沪深300成分股列表...")
    hs300 = get_hs300_symbols()
    symbols_pg = list(hs300.keys())
    if args.limit > 0:
        symbols_pg = symbols_pg[:args.limit]
    print(f"   共 {len(symbols_pg)} 只股票")
    print()

    # DB connection
    pg_host = os.environ.get('PGHOST', '127.0.0.1')
    pg_port = os.environ.get('PGPORT', '5432')
    pg_db = os.environ.get('PGDATABASE', 'quant_investment')
    pg_user = os.environ.get('PGUSER', '')
    pg_pass = os.environ.get('PGPASSWORD', '')

    conn = psycopg2.connect(
        host=pg_host, port=pg_port, dbname=pg_db,
        user=pg_user, password=pg_pass
    )
    cursor = conn.cursor()

    # Register missing stocks
    print("📝 注册未入库的沪深300股票...")
    registered = register_missing_stocks(cursor, hs300)
    print(f"   新增 {registered} 只股票到 stocks 表")
    print()

    upsert_sql = """
        INSERT INTO quant.daily_klines (symbol, trade_date, open, high, low, close, volume, amount, turnover_rate)
        VALUES (%(symbol)s, %(trade_date)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(amount)s, %(turnover_rate)s)
        ON CONFLICT (symbol, trade_date)
        DO UPDATE SET
            open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
            close = EXCLUDED.close, volume = EXCLUDED.volume,
            amount = EXCLUDED.amount, turnover_rate = EXCLUDED.turnover_rate
    """

    total_rows = 0
    success = 0
    failed = []

    start_ts = time.time()

    for i, sym_pg in enumerate(symbols_pg):
        code = sym_pg.replace('.SH', '').replace('.SZ', '')
        sina_sym = sina_symbol(sym_pg)
        name = hs300.get(sym_pg, '')

        pct = (i + 1) / len(symbols_pg) * 100
        elapsed = time.time() - start_ts
        eta = (elapsed / (i + 1) * len(symbols_pg) - elapsed) if i > 0 else 0
        print(f"[{i+1:3d}/{len(symbols_pg)} {pct:5.1f}% ETA {eta:.0f}s] "
              f"{sym_pg:12s} {name:8s} ", end='', flush=True)

        klines_raw = fetch_klines_sina(sina_sym, args.datalen)

        if not klines_raw:
            print("❌ NO DATA")
            failed.append(sym_pg)
            time.sleep(args.delay)
            continue

        rows = []
        for k in klines_raw:
            try:
                rows.append({
                    'symbol': sym_pg,
                    'trade_date': k['day'],
                    'open': float(k['open']),
                    'high': float(k['high']),
                    'low': float(k['low']),
                    'close': float(k['close']),
                    'volume': float(k['volume']),
                    'amount': float(k.get('amount', 0) or 0),
                    'turnover_rate': float(k.get('turnover_rate', 0) or 0),
                })
            except (ValueError, KeyError):
                continue

        try:
            execute_batch(cursor, upsert_sql, rows, page_size=1000)
            conn.commit()
            total_rows += len(rows)
            success += 1
            dr = rows[-1]['trade_date'] if rows[-1]['trade_date'] < rows[0]['trade_date'] else rows[0]['trade_date']
            d0 = rows[-1]['trade_date'] if rows[-1]['trade_date'] > rows[0]['trade_date'] else rows[0]['trade_date']
            print(f"✅ {len(rows):5d} [{dr} ~ {d0}]")
        except Exception as e:
            conn.rollback()
            print(f"❌ DB: {str(e)[:60]}")
            failed.append(sym_pg)

        time.sleep(args.delay)

    cursor.close()
    conn.close()

    elapsed = time.time() - start_ts
    print()
    print("=" * 60)
    print(f"✅ {success}/{len(symbols_pg)} 成功, {total_rows:,} bars, 耗时 {elapsed:.0f}s")
    if failed:
        print(f"❌ 失败 {len(failed)}: {', '.join(failed[:15])}")
        if len(failed) > 15:
            print(f"   ... 及其他 {len(failed) - 15} 只")


if __name__ == '__main__':
    main()

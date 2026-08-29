"""Import 6-year K-line data for all stocks in quant.stocks that need it, from Sina Finance.
Skips stocks that already have full data. Uses a saved symbol list to avoid akshare timeout.
Usage: python scripts/bulk_import_klines.py [--datalen 1500] [--delay 0.8] [--limit N]
"""
import json, sys, os, ssl, time, argparse
from urllib.request import Request, urlopen
from urllib.error import URLError
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_batch

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
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urlopen(req, context=ctx, timeout=30) as resp:
            raw = resp.read()
            for enc in ('gbk', 'gb2312', 'utf-8'):
                try:
                    return json.loads(raw.decode(enc))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            return []
    except Exception as e:
        sys.stderr.write(f"[{symbol}] {e}\n")
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--datalen', type=int, default=1500)
    parser.add_argument('--delay', type=float, default=0.8)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--symbols-file', help='File with one symbol per line')
    args = parser.parse_args()

    print(f"🚀 批量K线数据导入")
    print(f"   datalen: {args.datalen} bars (~{args.datalen//250} yrs)")
    print(f"   delay:   {args.delay}s")
    print(f"   started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # DB connect
    pg_host = os.environ.get('PGHOST', '127.0.0.1')
    pg_port = os.environ.get('PGPORT', '5432')
    pg_db = os.environ.get('PGDATABASE', 'quant_investment')
    pg_user = os.environ.get('PGUSER', '')
    pg_pass = os.environ.get('PGPASSWORD', '')

    conn = psycopg2.connect(host=pg_host, port=pg_port, dbname=pg_db, user=pg_user, password=pg_pass)
    cursor = conn.cursor()

    if args.symbols_file:
        with open(args.symbols_file) as f:
            symbols_pg = [l.strip() for l in f if l.strip()]
        print(f"📋 从文件读取: {len(symbols_pg)} symbols")
    else:
        # Get all symbols from stocks table
        cursor.execute('SELECT symbol, name FROM quant.stocks ORDER BY symbol')
        all_stocks = cursor.fetchall()
        symbols_pg = [s for s, _ in all_stocks]

    if args.limit:
        symbols_pg = symbols_pg[:args.limit]

    # Check existing data coverage per symbol
    cursor.execute('''
        SELECT symbol, COUNT(*) as cnt, MIN(trade_date), MAX(trade_date) 
        FROM quant.daily_klines GROUP BY symbol
    ''')
    existing = {row[0]: row[1] for row in cursor.fetchall()}

    # Sort: stocks with fewer klines first
    symbols_pg.sort(key=lambda s: existing.get(s, 0))

    print(f"📊 待处理: {len(symbols_pg)} 只股票")

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
        sina_sym = sina_symbol(sym_pg)
        existing_count = existing.get(sym_pg, 0)

        pct = (i + 1) / len(symbols_pg) * 100
        elapsed = time.time() - start_ts
        eta = (elapsed / (i + 1) * len(symbols_pg) - elapsed) if i > 0 else 0

        # Skip stocks that already have full data
        if existing_count >= args.datalen * 0.9:
            continue

        print(f"[{i+1:4d}/{len(symbols_pg)} {pct:5.1f}% ETA {eta:.0f}s] "
              f"{sym_pg:12s} (have {existing_count:5d}) ", end='', flush=True)

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
            new_cnt = max(existing_count, len(rows))
            dr = min(r['trade_date'] for r in rows)
            d0 = max(r['trade_date'] for r in rows)
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
    print(f"✅ {success}/{len(symbols_pg)} 成功, {total_rows:,} bars, {elapsed:.0f}s")
    if failed:
        print(f"❌ 失败 {len(failed)}: {', '.join(failed[:15])}")


if __name__ == '__main__':
    main()

"""Robust batch K-line importer — handles timeouts, retries, reconnects.
Usage: python scripts/robust_import_klines.py --symbols-file /tmp/hs300_symbols.txt --datalen 1500
"""
import json, sys, os, ssl, time, argparse, signal
from urllib.request import Request, urlopen
from urllib.error import URLError
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_batch

SINA_KLINES_URL = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'

# Track whether we should stop
_stop = False

def handle_sigterm(signum, frame):
    global _stop
    _stop = True
    print("\n⚠️  SIGTERM received, finishing current stock...")

signal.signal(signal.SIGTERM, handle_sigterm)


def sina_symbol(sym: str) -> str:
    sym = sym.strip().upper().replace('.SH', '').replace('.SZ', '')
    if sym.startswith('6') or sym.startswith('5') or sym.startswith('51'):
        return f'sh{sym}'
    return f'sz{sym}'


def fetch_one(sym_pg, datalen, max_retries=2):
    """Fetch K-lines with retries. Returns (sym_pg, rows, error)."""
    sina = sina_symbol(sym_pg)
    url = f'{SINA_KLINES_URL}?symbol={sina}&scale=240&ma=no&datalen={datalen}'
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    for attempt in range(max_retries + 1):
        try:
            with urlopen(req, context=ctx, timeout=20) as resp:
                raw = resp.read()
                for enc in ('gbk', 'gb2312', 'utf-8'):
                    try:
                        data = json.loads(raw.decode(enc))
                        rows = []
                        for k in data:
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
                                pass
                        return (sym_pg, rows, None)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                return (sym_pg, [], 'decode error')
        except Exception as e:
            err = str(e)[:80]
            if attempt < max_retries:
                time.sleep(2)
                continue
            return (sym_pg, [], err)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols-file', required=True)
    parser.add_argument('--datalen', type=int, default=1500)
    parser.add_argument('--workers', type=int, default=4, help='Concurrent fetches')
    parser.add_argument('--skip-existing', action='store_true', default=True)
    args = parser.parse_args()

    with open(args.symbols_file) as f:
        symbols = sorted([l.strip() for l in f if l.strip()])

    print(f"🚀 批量K线导入 (并行{args.workers}workers)")
    print(f"   symbols: {len(symbols)}")
    print(f"   datalen: {args.datalen}")
    print(f"   started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # DB
    pg_host = os.environ.get('PGHOST', '127.0.0.1')
    pg_port = os.environ.get('PGPORT', '5432')
    pg_db = os.environ.get('PGDATABASE', 'quant_investment')
    pg_user = os.environ.get('PGUSER', '')
    pg_pass = os.environ.get('PGPASSWORD', '')

    conn = psycopg2.connect(host=pg_host, port=pg_port, dbname=pg_db, user=pg_user, password=pg_pass)
    cur = conn.cursor()

    # Check existing
    cur.execute('SELECT symbol, COUNT(*) FROM quant.daily_klines GROUP BY symbol')
    existing = {row[0]: row[1] for row in cur.fetchall()}

    upsert_sql = """
        INSERT INTO quant.daily_klines (symbol, trade_date, open, high, low, close, volume, amount, turnover_rate)
        VALUES (%(symbol)s, %(trade_date)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(amount)s, %(turnover_rate)s)
        ON CONFLICT (symbol, trade_date) DO UPDATE SET
            open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
            close = EXCLUDED.close, volume = EXCLUDED.volume,
            amount = EXCLUDED.amount, turnover_rate = EXCLUDED.turnover_rate
    """

    total_rows = 0
    success = 0
    failed = 0
    start_ts = time.time()

    # Process in batches to avoid overwhelming memory
    batch_size = 20
    for batch_start in range(0, len(symbols), batch_size):
        if _stop:
            break
        batch = symbols[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (len(symbols) + batch_size - 1) // batch_size

        # Parallel fetch
        results = {}
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(fetch_one, s, args.datalen): s for s in batch}
            for future in as_completed(futures):
                sym, rows, err = future.result()
                results[sym] = (rows, err)

        # Write to DB
        for sym in batch:
            if sym not in results:
                continue
            rows, err = results[sym]
            if err:
                failed += 1
                continue
            if not rows:
                failed += 1
                continue

            try:
                execute_batch(cur, upsert_sql, rows, page_size=1000)
                conn.commit()
                total_rows += len(rows)
                success += 1
                dr, d0 = rows[-1]['trade_date'], rows[0]['trade_date']
                print(f"[{batch_start+1:3d}/{len(symbols)}] {sym:12s} ✅ {len(rows):5d} [{dr} ~ {d0}]")
            except Exception as e:
                conn.rollback()
                failed += 1
                print(f"[{batch_start+1:3d}/{len(symbols)}] {sym:12s} ❌ DB: {str(e)[:60]}")

        elapsed = time.time() - start_ts
        pct = batch_start / len(symbols) * 100
        eta = (elapsed / batch_start * len(symbols) - elapsed) if batch_start > 0 else 0
        print(f"   ── batch {batch_num}/{total_batches} done, {success} ok {failed} fail, ETA {eta:.0f}s")

    cur.close()
    conn.close()
    elapsed = time.time() - start_ts
    print(f"\n{'='*60}")
    print(f"✅ {success} success, {failed} failed, {total_rows:,} bars, {elapsed:.0f}s")


if __name__ == '__main__':
    main()

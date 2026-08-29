"""
Sina K-line backfill — batched approach to avoid rate limiting.
Processes 100 stocks, pauses 15s, repeats.
"""
import json, sys, os, ssl, time, argparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_values

SINA_URL = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'


def sina_sym(s):
    s = str(s).strip().upper().replace('.SH', '').replace('.SZ', '')
    return f'sh{s}' if s.startswith(('6', '5')) else f'sz{s}'


def fetch(sym_pg, datalen):
    url = f'{SINA_URL}?symbol={sina_sym(sym_pg)}&scale=240&ma=no&datalen={datalen}'
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'})
    for attempt in range(2):
        try:
            with urlopen(req, context=ctx, timeout=15) as resp:
                raw = resp.read()
                for enc in ('gbk', 'gb2312', 'utf-8'):
                    try:
                        data = json.loads(raw.decode(enc))
                        rows = []
                        for k in data:
                            try:
                                o, h, l_, c, v = [float(k[x]) for x in ('open', 'high', 'low', 'close', 'volume')]
                                amt_s = str(k.get('amount', '')).strip()
                                amt = float(amt_s) if amt_s else v * c
                                rows.append((sym_pg, k['day'], o, h, l_, c, v, amt, 0.0))
                            except (ValueError, KeyError):
                                continue
                        return rows
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                return []
        except Exception:
            if attempt == 1:
                return None
            time.sleep(1)
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--datalen', type=int, default=40)
    p.add_argument('--batch-size', type=int, default=100)
    p.add_argument('--pause', type=int, default=15, help='Seconds to pause between batches')
    p.add_argument('--limit', type=int, default=0)
    args = p.parse_args()

    pg = psycopg2.connect(
        host=os.environ.get('PGHOST', '127.0.0.1'),
        port=os.environ.get('PGPORT', '5432'),
        dbname=os.environ.get('PGDATABASE', 'quant_investment'),
        user=os.environ.get('PGUSER', ''),
        password=os.environ.get('PGPASSWORD', ''),
    )
    cur = pg.cursor()

    cur.execute("""
        SELECT symbol FROM quant.daily_klines
        GROUP BY symbol HAVING MAX(trade_date) < '2026-05-29'
        ORDER BY symbol
    """)
    to_update = [r[0] for r in cur.fetchall()]
    if args.limit:
        to_update = to_update[:args.limit]
    total_stocks = len(to_update)
    print(f"📊 {total_stocks} stocks to process, batch_size={args.batch_size}, pause={args.pause}s")

    upsert_sql = """
        INSERT INTO quant.daily_klines (symbol, trade_date, open, high, low, close, volume, amount, turnover_rate)
        VALUES %s
        ON CONFLICT (symbol, trade_date) DO UPDATE SET
            open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
            close = EXCLUDED.close, volume = EXCLUDED.volume,
            amount = EXCLUDED.amount, turnover_rate = EXCLUDED.turnover_rate
    """

    total_r = ok = fail = 0
    start = time.time()

    for batch_start in range(0, total_stocks, args.batch_size):
        batch_syms = to_update[batch_start:batch_start + args.batch_size]
        batch_rows = []
        batch_ok = batch_fail = 0

        for sym in batch_syms:
            rows = fetch(sym, args.datalen)
            if rows is None:
                batch_fail += 1
                fail += 1
            elif not rows:
                batch_fail += 1
                fail += 1
            else:
                batch_ok += 1
                ok += 1
                batch_rows.extend(rows)

        # Flush batch to DB
        if batch_rows:
            try:
                execute_values(cur, upsert_sql, batch_rows, page_size=500)
                pg.commit()
                total_r += len(batch_rows)
            except Exception as e:
                pg.rollback()
                print(f"\n❌ DB error: {e}")

        done = min(batch_start + args.batch_size, total_stocks)
        elapsed = time.time() - start
        rate = done / max(elapsed, 1)
        eta = (total_stocks - done) / max(rate, 0.01)
        batches_done = batch_start // args.batch_size + 1
        total_batches = (total_stocks + args.batch_size - 1) // args.batch_size
        print(f"[{done}/{total_stocks}] batch {batches_done}/{total_batches} {batch_ok}✓ {batch_fail}✗ | {rate:.1f}/s | ETA {eta/60:.0f}min", flush=True)

        if batch_start + args.batch_size < total_stocks:
            print(f"  ⏸  Pausing {args.pause}s...", flush=True)
            time.sleep(args.pause)

    elapsed = time.time() - start
    print(f"\n✅ {total_r:,} rows, {ok}✓ {fail}✗, {elapsed/60:.1f}min")
    cur.close()
    pg.close()


if __name__ == '__main__':
    main()

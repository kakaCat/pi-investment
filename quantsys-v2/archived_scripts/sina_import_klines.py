"""
Download K-line data from Sina Finance and import to PostgreSQL.
Usage: python scripts/sina_import_klines.py [--symbols 600519,000858,...] [--days 365]
"""
import json, sys, os, ssl, time, argparse
from urllib.request import Request, urlopen
from urllib.error import URLError

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import execute_batch

SINA_KLINES_URL = (
    'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
    'CN_MarketData.getKLineData'
)

def sina_symbol(sym: str) -> str:
    """Convert symbol to Sina format: sh600519 / sz000858 / sh512010"""
    sym = sym.strip().upper().replace('.SH', '').replace('.SZ', '')
    if sym.startswith('6') or sym.startswith('5'):
        return f'sh{sym}'
    # 0开头（深主板）、3开头（创业板）、159开头（深市ETF）
    return f'sz{sym}'

def fetch_klines_sina(symbol: str, datalen: int = 1023) -> list:
    """Fetch daily K-line data from Sina Finance."""
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
            # Try multiple encodings
            for enc in ('gbk', 'gb2312', 'utf-8'):
                try:
                    data = json.loads(raw.decode(enc))
                    break
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            else:
                print(f"  WARNING: Could not decode response for {symbol}", file=sys.stderr)
                return []
            return data
    except URLError as e:
        print(f"  ERROR fetching {symbol}: {e}", file=sys.stderr)
        return []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols', default='600519,000858,300750,601012,600036,002142,601899,002594',
                        help='Comma-separated stock codes')
    parser.add_argument('--days', type=int, default=365, help='Days of data to fetch')
    parser.add_argument('--suffix', choices=('SH','SZ'), help='Exchange suffix to append')
    args = parser.parse_args()

    symbols_raw = [s.strip() for s in args.symbols.split(',') if s.strip()]

    # Add exchange suffix if needed
    symbols_pg = []
    for sym in symbols_raw:
        s = sym.strip().upper()
        if '.' in s:
            symbols_pg.append(s)
        elif args.suffix:
            symbols_pg.append(f'{s}.{args.suffix}')
        else:
            if s.startswith('6'):
                symbols_pg.append(f'{s}.SH')
            elif s.startswith('0') or s.startswith('3') or s.startswith('159'):
                symbols_pg.append(f'{s}.SZ')
            else:
                symbols_pg.append(f'{s}.SH')

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

    upsert_sql = """
        INSERT INTO quant.daily_klines (symbol, trade_date, open, high, low, close, volume, amount, turnover_rate)
        VALUES (%(symbol)s, %(trade_date)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(amount)s, %(turnover_rate)s)
        ON CONFLICT (symbol, trade_date)
        DO UPDATE SET
            open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
            close = EXCLUDED.close, volume = EXCLUDED.volume,
            amount = EXCLUDED.amount, turnover_rate = EXCLUDED.turnover_rate
    """

    datalen = min(args.days * 2, 1023)  # Fetch enough to cover all trading days
    total = 0

    for i, (sym_raw, sym_pg) in enumerate(zip(symbols_raw, symbols_pg)):
        sina_sym = sina_symbol(sym_raw)
        print(f"[{i+1}/{len(symbols_raw)}] Fetching {sym_pg} ...", end=' ', flush=True)
        klines_raw = fetch_klines_sina(sina_sym, datalen)

        if not klines_raw:
            print("NO DATA")
            continue

        # Get most recent <days> worth of data
        klines_raw = klines_raw[-args.days * 2:] if len(klines_raw) > args.days * 2 else klines_raw

        rows = []
        for k in klines_raw:
            rows.append({
                'symbol': sym_pg,
                'trade_date': k['day'],
                'open': k['open'],
                'high': k['high'],
                'low': k['low'],
                'close': k['close'],
                'volume': k['volume'],
                'amount': 0,
                'turnover_rate': 0,
            })

        try:
            execute_batch(cursor, upsert_sql, rows, page_size=1000)
            conn.commit()
            total += len(rows)
            print(f"{len(rows)} rows ✓")
        except Exception as e:
            conn.rollback()
            print(f"ERROR: {e}", file=sys.stderr)

        if i < len(symbols_raw) - 1:
            time.sleep(0.5)  # Rate limit

    cursor.close()
    conn.close()
    print(f"\n✅ Done: {total} klines for {len(symbols_raw)} stocks")

if __name__ == '__main__':
    main()

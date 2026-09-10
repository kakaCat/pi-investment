"""指数日线入库/刷新（2026-09-11，w-f4aa1f6a）

背景：quant.index_daily 新建后，指数数据需有稳定的采集通道。实测：
- akshare 的 index_zh_a_hist 走 80.push2.eastmoney.com，本机经代理时好时坏（ProxyError）；
- akshare 的 stock_zh_index_daily 走新浪，实测稳定可用且量级正确
  （上证50 2904 / 上证指数 3934 / 中证500 7717，与同码深市个股的 2.46/11.85/9.46 完全区分开）。

用法：
  python tools/backfill_index_daily.py                # 默认窗口 400 天，全部指数
  python tools/backfill_index_daily.py --days 60
  python tools/backfill_index_daily.py --dry-run
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

# 指数 → 新浪代码（带市场前缀）
INDEX_SINA = {
    '000001.SH': 'sh000001',  # 上证指数
    '000016.SH': 'sh000016',  # 上证50（歧义码：*ST康佳A）
    '000300.SH': 'sh000300',  # 沪深300
    '000852.SH': 'sh000852',  # 中证1000（歧义码：石化机械）
    '000905.SH': 'sh000905',  # 中证500（歧义码：厦门港务）
    '000906.SH': 'sh000906',  # 中证800
    '399001.SZ': 'sz399001',  # 深证成指
    '399006.SZ': 'sz399006',  # 创业板指
}

UPSERT = """
INSERT INTO quant.index_daily (symbol, trade_date, open, high, low, close, volume, amount, source, updated_at)
VALUES (:symbol, :trade_date, :open, :high, :low, :close, :volume, :amount, :source, now())
ON CONFLICT (symbol, trade_date) DO UPDATE
   SET open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close,
       volume = EXCLUDED.volume, amount = EXCLUDED.amount, source = EXCLUDED.source, updated_at = now()
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=400)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--dsn', default=None)
    args = ap.parse_args()

    import akshare as ak

    engine = create_engine(args.dsn) if args.dsn else create_engine('postgresql+psycopg2:///quant_investment')
    cutoff = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')

    total = 0
    with engine.begin() as conn:
        for symbol, sina_code in INDEX_SINA.items():
            try:
                df = ak.stock_zh_index_daily(symbol=sina_code)
            except Exception as e:  # noqa: BLE001
                print(f"[index] {symbol} 拉取失败: {type(e).__name__}: {str(e)[:80]}")
                continue
            if df is None or df.empty:
                print(f"[index] {symbol} 无数据")
                continue
            rows = df[df['date'].astype(str) >= cutoff]
            n = 0
            for _, r in rows.iterrows():
                params = {
                    'symbol': symbol,
                    'trade_date': str(r['date'])[:10],
                    'open': float(r['open']), 'high': float(r['high']),
                    'low': float(r['low']), 'close': float(r['close']),
                    'volume': float(r.get('volume') or 0), 'amount': float(r.get('amount') or 0),
                    'source': 'sina:stock_zh_index_daily',
                }
                if not args.dry_run:
                    conn.execute(text(UPSERT), params)
                n += 1
            total += n
            last = str(rows.iloc[-1]['date'])[:10] if n else '-'
            print(f"[index] {symbol:10s} ({sina_code}) 写入 {n:4d} 行，最新 {last}")
    mode = 'dry-run' if args.dry_run else '已写入'
    print(f"[index] {mode}：合计 {total} 行")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

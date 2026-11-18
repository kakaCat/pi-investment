#!/usr/bin/env python
"""交易日历表刷新（2026-11-03 改造：交易所发布日历为主，K线派生为兜底）

## 数据源（两路并集，INSERT-only）
1. **交易所发布日历（主）**：akshare `tool_trade_date_hist_sina`（上交所），
   提前发布全年交易日（实测覆盖到 2026-12-31）。2026-11-03 前的旧实现是
   "从 quant.daily_klines DISTINCT trade_date 派生"——只能覆盖**已有K线**的
   过去日期，当天盘中/清晨守卫拿不到"今天是否交易日"，节假日全靠
   TradingDayGuard 的"近 7 日有K线"启发式硬猜：
     · 2026-10-01（国庆周四）被猜成交易日 → orchestrator 给全账户写假净值快照；
     · 2026-10-08（节后首日）被猜成非交易日（上根K线已 8 天）→ 整天跳过。
   改用交易所日历后，未来日期也有行，guard 从清晨起即可精确判定。
2. **K线派生（兜底）**：daily_klines DISTINCT trade_date 并入，
   兜住 sina 漏掉的已交易历史日（两源并集，幂等）。

## 调度
launchd 每日 **06:00（盘前，PRE_MARKET 之前）+ 23:10（盘后复核）**。
06:00 失败时当天 guard 自动回退 K 线启发式（旧行为，不击穿）；23:10 再补。

## 幂等
PK 为 (trade_date, exchange)，插入用 ON CONFLICT DO NOTHING，可反复运行。

用法：
    ./venv/bin/python tools/refresh_trading_calendar.py                # 刷新
    ./venv/bin/python tools/refresh_trading_calendar.py --dry-run      # 只看会写多少
"""
import argparse
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

DEFAULT_EXCHANGES = ('SSE', 'SZSE', 'ALL')


def _ensure_composite_pk(conn, dry_run: bool) -> str:
    """把 PK 从 (trade_date) 改为 (trade_date, exchange)（仅空表时）。"""
    row = conn.execute(text("""
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'quant.trading_calendar'::regclass AND contype = 'p'
    """)).fetchone()
    current = row[0] if row else ''
    if 'trade_date,exchange' in current.replace(' ', ''):
        return 'already-composite'
    n = conn.execute(text('SELECT count(*) FROM quant.trading_calendar')).scalar()
    if n:
        return f'skipped-nonempty({n})'
    if dry_run:
        return 'would-alter(dry-run)'
    conn.execute(text('ALTER TABLE quant.trading_calendar DROP CONSTRAINT IF EXISTS trading_calendar_pkey'))
    conn.execute(text('ALTER TABLE quant.trading_calendar ADD PRIMARY KEY (trade_date, exchange)'))
    return 'altered'


def _fetch_exchange_calendar_days() -> tuple:
    """交易所发布日历（主源）。返回 (days, source_note)；网络失败返回 ([], 说明)。"""
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        days = sorted({str(d)[:10] for d in df['trade_date'].tolist()})
        return days, f'sina交易所日历 {len(days)} 天（{days[0]} ~ {days[-1]}）'
    except Exception as e:  # noqa: BLE001 - 主源失败不许打断兜底源
        print(f'[calendar] ⚠️ 交易所日历获取失败（降级为仅K线兜底）: {type(e).__name__}: {e}')
        return [], 'sina不可用'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--dsn', default=None)
    args = ap.parse_args()

    exchanges = list(DEFAULT_EXCHANGES)
    engine = create_engine(args.dsn) if args.dsn else create_engine('postgresql+psycopg2:///quant_investment')

    sina_days, sina_note = _fetch_exchange_calendar_days()
    print(f'[calendar] 主源: {sina_note}')

    with engine.begin() as conn:
        pk_state = _ensure_composite_pk(conn, args.dry_run)
        print(f'[calendar] PK 状态: {pk_state}')

        written = {}
        if sina_days:
            if args.dry_run:
                print(f'[calendar] --dry-run：主源将为 {exchanges} 各写至多 {len(sina_days)} 行')
            else:
                for ex in exchanges:
                    res = conn.execute(text("""
                        INSERT INTO quant.trading_calendar (trade_date, exchange, is_trading_day)
                        SELECT d::date, :ex, TRUE FROM unnest(CAST(:days AS text[])) AS t(d)
                        ON CONFLICT (trade_date, exchange) DO NOTHING
                    """), {'ex': ex, 'days': sina_days})
                    written[f'{ex}(sina)'] = res.rowcount

        # K 线派生兜底：并集语义，兜住主源漏掉的已交易历史日
        src = conn.execute(text(
            'SELECT count(DISTINCT trade_date), min(trade_date), max(trade_date) FROM quant.daily_klines'
        )).fetchone()
        print(f'[calendar] 兜底源 daily_klines: {src[0]} 个交易日（{src[1]} ~ {src[2]}）')
        if args.dry_run:
            print(f'[calendar] --dry-run：兜底源将为 {exchanges} 各写至多 {src[0]} 行')
            return 0
        for ex in exchanges:
            res = conn.execute(text("""
                INSERT INTO quant.trading_calendar (trade_date, exchange, is_trading_day)
                SELECT DISTINCT trade_date, :ex, TRUE FROM quant.daily_klines
                ON CONFLICT (trade_date, exchange) DO NOTHING
            """), {'ex': ex})
            written[f'{ex}(klines)'] = res.rowcount

        total = conn.execute(text('SELECT count(*) FROM quant.trading_calendar')).scalar()
        cov = conn.execute(text('SELECT min(trade_date), max(trade_date) FROM quant.trading_calendar')).fetchone()
        for k, n in written.items():
            print(f'[calendar] {k}: 新增 {n} 行')
        print(f'[calendar] 表内总行数: {total}，覆盖 {cov[0]} ~ {cov[1]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

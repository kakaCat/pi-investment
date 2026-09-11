#!/usr/bin/env python
"""交易日历表刷新（步2，2026-09-11，w-f4aa1f6a）

## 为什么需要
`quant.trading_calendar` 长期**0 行**（建表后无人写入），而
`application/services/data_pipeline_service.py:load_trading_calendar_from_db` 是
`TimeAlignmentStage` 的 calendar_loader——管道一直在用**空日历**做时间对齐，
且原实现静默返回 set()（已加空表回退 + 报警，见该函数 2026-09-11 注释）。

本脚本把唯一真源（`quant.daily_klines` 的 DISTINCT trade_date）灌进该表：
- 管道拿到真实交易日集合；
- 数据契约「quant.trading_calendar 行数下限」有真实基线；
- 外部只读查询不再看到一张空表。

## 幂等
PK 为 (trade_date, exchange)，插入用 ON CONFLICT DO NOTHING，可反复运行。
原表 PK 只有 trade_date（exchange 名存实亡），本脚本在其为空时自动改为复合 PK
（有数据时跳过并告警，避免破坏既有数据）。

用法：
    ./venv/bin/python tools/refresh_trading_calendar.py                # 刷新
    ./venv/bin/python tools/refresh_trading_calendar.py --dry-run      # 只看会写多少
    ./venv/bin/python tools/refresh_trading_calendar.py --exchanges SSE
"""
import argparse
import sys
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
    if 'trade_date, exchange' in current.replace(' ', '') or 'exchange, trade_date' in current.replace(' ', ''):
        return 'already-composite'

    n = conn.execute(text('SELECT count(*) FROM quant.trading_calendar')).scalar()
    if n:
        return f'skipped-nonempty({n})'
    if dry_run:
        return 'would-alter(dry-run)'

    conn.execute(text('ALTER TABLE quant.trading_calendar DROP CONSTRAINT IF EXISTS trading_calendar_pkey'))
    conn.execute(text('ALTER TABLE quant.trading_calendar ADD PRIMARY KEY (trade_date, exchange)'))
    return 'altered'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--exchanges', default=','.join(DEFAULT_EXCHANGES),
                    help='逗号分隔的交易所代码，默认 SSE,SZSE,ALL')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--dsn', default=None)
    args = ap.parse_args()

    exchanges = [e.strip() for e in args.exchanges.split(',') if e.strip()]
    engine = create_engine(args.dsn) if args.dsn else create_engine('postgresql+psycopg2:///quant_investment')

    with engine.begin() as conn:
        pk_state = _ensure_composite_pk(conn, args.dry_run)

        src = conn.execute(text(
            'SELECT count(DISTINCT trade_date), min(trade_date), max(trade_date) FROM quant.daily_klines'
        )).fetchone()
        distinct_days, dmin, dmax = src[0], src[1], src[2]
        print(f'[calendar] 真源 daily_klines: {distinct_days} 个交易日（{dmin} ~ {dmax}）')
        print(f'[calendar] PK 状态: {pk_state}')

        if args.dry_run:
            print(f'[calendar] --dry-run：将为 {exchanges} 各写入 {distinct_days} 行')
            return 0

        written = {}
        for ex in exchanges:
            res = conn.execute(text("""
                INSERT INTO quant.trading_calendar (trade_date, exchange, is_trading_day)
                SELECT DISTINCT trade_date, :ex, TRUE FROM quant.daily_klines
                ON CONFLICT (trade_date, exchange) DO NOTHING
            """), {'ex': ex})
            written[ex] = res.rowcount

        total = conn.execute(text('SELECT count(*) FROM quant.trading_calendar')).scalar()
        for ex, n in written.items():
            print(f'[calendar] {ex}: 新增 {n} 行')
        print(f'[calendar] 表内总行数: {total}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

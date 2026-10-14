"""交易日历表刷新（步2，2026-09-11，w-f4aa1f6a；2026-10-04 扩源 REQ-261004102115-d3de）

## 为什么需要
`quant.trading_calendar` 长期**0 行**（建表后无人写入），而
`application/services/data_pipeline_service.py:load_trading_calendar_from_db` 是
`TimeAlignmentStage` 的 calendar_loader——管道一直在用**空日历**做时间对齐，
且原实现静默返回 set()（已加空表回退 + 报警，见该函数 2026-09-11 注释）。

本脚本把交易日灌进该表：
- 管道拿到真实交易日集合；
- 数据契约「quant.trading_calendar 行数下限」有真实基线；
- 外部只读查询不再看到一张空表。

## 2026-10-04：真源扩为「K 线 ∪ 官方日历」（REQ-261004102115-d3de · FR-1）

只用 `daily_klines` 的 DISTINCT trade_date 有一个**结构性缺陷**：K 线里**天然没有未来交易日**，
于是表刚填好就已经过期；探针的"最近已收盘交易日"查表查不到 → 每次都退回 provider。
现在并上 AKShare 官方日历（经 `DataProviderManager.get_trading_calendar`，含未来日期），
表可以覆盖到年底甚至更远，快路径才真正快。K 线源作为历史深水区的兜底**保留**。

## 幂等
PK 为 (trade_date, exchange)，插入用 ON CONFLICT DO NOTHING，可反复运行。
原表 PK 只有 trade_date（exchange 名存实亡），本脚本在其为空时自动改为复合 PK
（有数据时跳过并告警，避免破坏既有数据）。

用法：
    ./venv/bin/python tools/refresh_trading_calendar.py                # 刷新（K线 ∪ 官方日历）
    ./venv/bin/python tools/refresh_trading_calendar.py --dry-run      # 只看会写多少
    ./venv/bin/python tools/refresh_trading_calendar.py --exchanges SSE
    ./venv/bin/python tools/refresh_trading_calendar.py --skip-provider  # 只用 K 线源（离线时）
"""
import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

DEFAULT_EXCHANGES = ('SSE', 'SZSE', 'ALL')

#: 官方日历的覆盖窗口：过去 5 年（历史深水区）~ 未来 400 天（跨年提前量）
PROVIDER_LOOKBACK_DAYS = 365 * 5
PROVIDER_AHEAD_DAYS = 400


def _provider_days(start: date, end: date):
    """AKShare 官方交易日历（经既有 DataProviderManager 入口，不直连外部库）。

    这是**唯一能给出未来交易日**的真源；不可用时返回空集并打印原因，
    由调用方退化为"只用 K 线源"（不静默：会有明确一行输出）。
    """
    try:
        from infrastructure.services.service_factory import ServiceFactory

        manager = ServiceFactory.get_data_provider_manager()
        result = manager.get_trading_calendar(start.isoformat(), end.isoformat())
    except Exception as exc:  # noqa: BLE001 —— 扩源失败不该让整条刷新失败
        print(f'[calendar] provider 取数失败：{type(exc).__name__}: {exc}（本次只用 K 线源）')
        return set()

    if not isinstance(result, dict) or not result.get('success'):
        print(f'[calendar] provider 不可用：{str(result)[:160]}（本次只用 K 线源）')
        return set()

    rows = result.get('data')
    rows = getattr(rows, 'data', rows)
    days = set()
    for row in rows or []:
        raw = row.get('trade_date') if isinstance(row, dict) else row
        if not raw:
            continue
        try:
            days.add(datetime.strptime(str(raw)[:10], '%Y-%m-%d').date())
        except ValueError:
            continue
    return days


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
    ap.add_argument('--skip-provider', action='store_true',
                    help='只用 K 线真源（离线/外部不可用时用）')
    args = ap.parse_args()

    exchanges = [e.strip() for e in args.exchanges.split(',') if e.strip()]
    engine = create_engine(args.dsn) if args.dsn else create_engine('postgresql+psycopg2:///quant_investment')

    # 官方日历（含**未来**交易日）——K 线真源给不出这个，见模块 docstring。
    today = date.today()
    prov_days = set() if args.skip_provider else _provider_days(
        today - timedelta(days=PROVIDER_LOOKBACK_DAYS),
        today + timedelta(days=PROVIDER_AHEAD_DAYS),
    )
    if not args.skip_provider:
        print(f'[calendar] 官方日历（AKShare）: {len(prov_days)} 个交易日'
              + (f'（{min(prov_days)} ~ {max(prov_days)}）' if prov_days else ''))

    with engine.begin() as conn:
        pk_state = _ensure_composite_pk(conn, args.dry_run)

        src = conn.execute(text(
            'SELECT count(DISTINCT trade_date), min(trade_date), max(trade_date) FROM quant.daily_klines'
        )).fetchone()
        distinct_days, dmin, dmax = src[0], src[1], src[2]
        print(f'[calendar] 真源 daily_klines: {distinct_days} 个交易日（{dmin} ~ {dmax}）')
        print(f'[calendar] PK 状态: {pk_state}')

        # 并集预估：provider 里晚于 K 线末日的那些日子才是"K 线给不出的"
        ahead = {d for d in prov_days if dmax is None or d > dmax}
        if args.dry_run:
            print(f'[calendar] --dry-run：K 线源将为 {exchanges} 各写入 {distinct_days} 行；'
                  f'官方日历将补写最多 {len(ahead)} 个未来交易日 × {len(exchanges)} 个交易所')
            return 0

        written = {}
        for ex in exchanges:
            res = conn.execute(text("""
                INSERT INTO quant.trading_calendar (trade_date, exchange, is_trading_day)
                SELECT DISTINCT trade_date, :ex, TRUE FROM quant.daily_klines
                ON CONFLICT (trade_date, exchange) DO NOTHING
            """), {'ex': ex})
            written[ex] = res.rowcount

        # 官方日历：补齐 K 线没有的日子（含未来交易日）
        prov_written = 0
        if prov_days:
            rows = [{'d': d.isoformat(), 'ex': ex} for ex in exchanges for d in sorted(prov_days)]
            res = conn.execute(
                text("""
                    INSERT INTO quant.trading_calendar (trade_date, exchange, is_trading_day)
                    VALUES (:d, :ex, TRUE)
                    ON CONFLICT DO NOTHING
                """), rows)
            prov_written = res.rowcount

        total = conn.execute(text('SELECT count(*) FROM quant.trading_calendar')).scalar()
        for ex, n in written.items():
            print(f'[calendar] {ex}: K 线源新增 {n} 行')
        if prov_days:
            print(f'[calendar] 官方日历并集补写 {prov_written} 行（含未来交易日 {len(ahead)} 天）')
        print(f'[calendar] 表内总行数: {total}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""一次性历史回填：ma60 / adx / volatility_20 三个因子（2026-11-03，w-0b085607）

背景：FactorStage.DEFAULT_TECHNICAL_FACTORS 长期缺这三个因子，每日 factor_compute
从未落库 → ML 32 特征中对应 3 列全 NaN、LightGBM 特征重要性恒 0。
2026-11-03 已把三者补进默认清单（domain/backtest/stages/factor_stage.py），
本脚本回填历史使 11-05 重训时 350 天窗口内有真实值。

一致性保证：直接复用与日线管线完全相同的计算器实现
（MovingAverageFactors.ma60 / TrendFactors.adx / VolatilityFactors.volatility_20），
逐日截断窗口计算，与每日增量落库的值同源同口径。

用法：cd quantsys-v2 && source activate-py313.sh && python tools/backfill_trend_vol_factors.py [--days 500] [--limit N]
"""
import argparse
import sys
import time

import psycopg2
import psycopg2.extras

from domain.factors.library.moving_average import MovingAverageFactors
from domain.factors.library.trend import TrendFactors
from domain.factors.library.volatility import VolatilityFactors

DB = dict(host='127.0.0.1', user='yunpeng', dbname='quant_investment')
FACTORS = ('ma60', 'adx', 'volatility_20')
MIN_BARS = 60  # ma60 需要 60 根预热；adx/volatility_20 要求更低，统一按最严


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=500, help='回填回溯自然日（默认500，覆盖训练350天窗口+预热）')
    ap.add_argument('--limit', type=int, default=0, help='只跑前 N 只（调试用）')
    args = ap.parse_args()

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT symbol FROM quant.factor_values WHERE factor_name='ma5' ORDER BY symbol")
    symbols = [r[0] for r in cur.fetchall()]
    if args.limit:
        symbols = symbols[:args.limit]
    print(f'universe: {len(symbols)} symbols, lookback {args.days}d', flush=True)

    ma, tr, vo = MovingAverageFactors(), TrendFactors(), VolatilityFactors()
    total_rows, t0 = 0, time.time()

    for si, sym in enumerate(symbols):
        cur.execute(
            """SELECT trade_date, open, high, low, close, volume FROM quant.daily_klines
               WHERE symbol=%s AND trade_date >= CURRENT_DATE - %s * INTERVAL '1 day'
               ORDER BY trade_date""", (sym, args.days))
        rows = cur.fetchall()
        if len(rows) < MIN_BARS:
            continue
        klines = [dict(zip(['trade_date', 'open', 'high', 'low', 'close', 'volume'], r)) for r in rows]
        for k in klines:
            for f in ('open', 'high', 'low', 'close', 'volume'):
                k[f] = float(k[f])

        batch = []
        for i in range(MIN_BARS - 1, len(klines)):
            window = klines[:i + 1]
            d = klines[i]['trade_date']
            try:
                v_ma = ma.ma60(window).get('value')
                v_adx = tr.adx(window).get('value')
                v_vo = vo.volatility_20(window).get('value')
            except Exception:
                continue
            for name, val in (('ma60', v_ma), ('adx', v_adx), ('volatility_20', v_vo)):
                if val is not None:
                    batch.append((sym, d, name, float(val)))

        if batch:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO quant.factor_values (symbol, factor_date, factor_name, factor_value)
                   VALUES %s ON CONFLICT (symbol, factor_date, factor_name)
                   DO UPDATE SET factor_value = EXCLUDED.factor_value""",
                batch, page_size=5000)
            conn.commit()
            total_rows += len(batch)

        if (si + 1) % 50 == 0:
            print(f'progress {si + 1}/{len(symbols)} rows={total_rows} elapsed={time.time() - t0:.0f}s', flush=True)

    print(f'DONE: symbols={len(symbols)} rows_inserted={total_rows} elapsed={time.time() - t0:.0f}s', flush=True)
    cur.close()
    conn.close()


if __name__ == '__main__':
    sys.exit(main())

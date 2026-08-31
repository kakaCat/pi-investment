"""M6-4 candidate 参数扩大验证：macd 635 默认 vs 最优参数 fast5/slow13/sig3
范围：16 股 × 2024H1/H2（强势区间）· 真实回测
"""
import sys, time, json, traceback
sys.path.insert(0, '.')
from adapters.shared.services import strategy_service

SYMS = ['600519','000858','600036','600000','601318','600030','000333','601166','601288','600900',
        '300750','002594','300308','300274','688981','300059']
PERIODS = [('2024-01-01','2024-06-30'),('2024-07-01','2024-12-31')]

VARIANTS = {
    'default': None,
    'candidate_fast5_slow13_sig3': {'fast_period':5,'slow_period':13,'signal_period':3},
}

def run_one(name, ov, sid=635):
    sh, ret, mdd, n = 0.0, 0.0, 0.0, 0
    for s in SYMS:
        for sd, ed in PERIODS:
            for attempt in range(3):
                try:
                    r = strategy_service.backtest_strategy(strategy_id=sid, symbol=s, start_date=sd, end_date=ed, initial_cash=1000000, params_override=ov)
                    sh += r.get('sharpe_ratio') or 0
                    ret += r.get('total_return') or 0
                    mdd += r.get('max_drawdown') or 0
                    n += 1
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f'  [FAIL] {s} {sd}~{ed}: {e}', flush=True)
                    else:
                        time.sleep(2)
    return {'n': n, 'avg_sharpe': round(sh/n,3) if n else None,
            'avg_return': round(ret/n,4) if n else None,
            'avg_mdd': round(mdd/n,3) if n else None}

results = {}
for name, ov in VARIANTS.items():
    print(f'=== {name} ===', flush=True)
    results[name] = run_one(name, ov)
    print(json.dumps(results[name], ensure_ascii=False), flush=True)

json.dump(results, open('/tmp/m64_macd_candidate.json','w'), ensure_ascii=False, indent=1)
print('DONE')

"""M6-4 市场状态过滤验证：macd 635(默认) vs 640(个股200MA熊市过滤)
范围：16 股 × 3 时段 · 真实回测
"""
import sys, time, json
sys.path.insert(0, '.')
from adapters.shared.services import strategy_service

SYMS = ['600519','000858','600036','600000','601318','600030','000333','601166','601288','600900',
        '300750','002594','300308','300274','688981','300059']
PERIODS = [('2023-01-01','2023-12-31'),('2024-01-01','2024-06-30'),('2024-07-01','2024-12-31')]
STRATS = {"macd_default": 635, "macd_market_filter": 640, "macd_index_filter": 641, "macd_trailing_stop": 642}

def run_one(sid):
    sh, ret, mdd, wr, n = 0.0, 0.0, 0.0, 0.0, 0
    by_period = {p[0]: {'sharpe': [], 'ret': []} for p in PERIODS}
    for s in SYMS:
        for sd, ed in PERIODS:
            for attempt in range(3):
                try:
                    r = strategy_service.backtest_strategy(strategy_id=sid, symbol=s, start_date=sd, end_date=ed, initial_cash=1000000)
                    sh += r.get('sharpe_ratio') or 0
                    ret += r.get('total_return') or 0
                    mdd += r.get('max_drawdown') or 0
                    wr += r.get('win_rate') or 0
                    n += 1
                    by_period[sd]['sharpe'].append(r.get('sharpe_ratio') or 0)
                    by_period[sd]['ret'].append(r.get('total_return') or 0)
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f'  [FAIL] {s} {sd}: {e}', flush=True)
                    else:
                        time.sleep(2)
    out = {'n': n, 'avg_sharpe': round(sh/n,3) if n else None,
           'avg_return': round(ret/n,4) if n else None,
           'avg_mdd': round(mdd/n,3) if n else None,
           'avg_winrate': round(wr/n,3) if n else None,
           'by_period': {k: {'avg_sharpe': round(sum(v['sharpe'])/len(v['sharpe']),3) if v['sharpe'] else None,
                             'avg_return': round(sum(v['ret'])/len(v['ret']),4) if v['ret'] else None}
                         for k,v in by_period.items()}}
    return out

results = {}
for name, sid in STRATS.items():
    print(f'=== {name} (id={sid}) ===', flush=True)
    results[name] = run_one(sid)
    print(json.dumps(results[name], ensure_ascii=False, indent=1), flush=True)

json.dump(results, open('/tmp/m64_market_filter.json','w'), ensure_ascii=False, indent=1)
print('DONE')

#!/usr/bin/env python3
"""
完整频率优化测试 — 使用真实的 backtest engine + 聚合
"""
import sys, os, logging
logging.basicConfig(level=logging.INFO)

sys.path.insert(0, '/Users/mac/Documents/ai/pi-investment/quantsys-v2')
sys.path.insert(0, '/Users/mac/Documents/ai/pi-investment/quant')

# Clear module cache
for key in list(sys.modules.keys()):
    if 'strategy_code_service' in key:
        del sys.modules[key]

# ==========================================
# Aggregation function
# ==========================================
def aggregate_5min_to(klines, period):
    bars_per_group = 3 if period == '15min' else 6
    result, group = [], []
    for k in klines:
        should_flush = False
        if group:
            prev_dt = str(group[-1].get('trade_date', ''))
            curr_dt = str(k.get('trade_date', ''))
            prev_time = prev_dt.split(' ')[1][:8] if ' ' in prev_dt else ''
            curr_time = curr_dt.split(' ')[1][:8] if ' ' in curr_dt else ''
            if prev_time < '12:00:00' and curr_time >= '13:00:00':
                should_flush = True
            elif ' ' in curr_dt and ' ' in prev_dt:
                if curr_dt.split(' ')[0] != prev_dt.split(' ')[0]:
                    should_flush = True
        if len(group) >= bars_per_group:
            should_flush = True
        if should_flush and group:
            result.append({'open':float(group[0]['open']),'high':max(float(g['high'])for g in group),
                'low':min(float(g['low'])for g in group),'close':float(group[-1]['close']),
                'volume':sum(float(g['volume'])for g in group),'trade_date':group[0]['trade_date'],
                'trade_datetime':group[0].get('trade_datetime','')})
            group = []
        group.append(k)
    if group:
        result.append({'open':float(group[0]['open']),'high':max(float(g['high'])for g in group),
            'low':min(float(g['low'])for g in group),'close':float(group[-1]['close']),
            'volume':sum(float(g['volume'])for g in group),'trade_date':group[0]['trade_date'],
            'trade_datetime':group[0].get('trade_datetime','')})
    return result

# ==========================================
# Monkey-patch StrategyCodeService._get_klines to add aggregation
# ==========================================
from application.services.strategy_code_service import StrategyCodeService

original_get_klines = StrategyCodeService._get_klines

def patched_get_klines(self, *args, **kwargs):
    result = original_get_klines(self, *args, **kwargs)
    period = kwargs.get('period') or (args[5] if len(args) > 5 else None)
    if period in ('15min', '30min') and result:
        result = aggregate_5min_to(result, period)
    return result

StrategyCodeService._get_klines = patched_get_klines

print("Monkey patch applied. Testing...")

# ==========================================
# Run real backtests
# ==========================================
import time

svc = StrategyCodeService()
strategies = [(72, 'v11'), (87, 'v11-optimized')]
stocks = ['688981', '688256', '002371', '603501']

print("\n" + "="*100)
print("FREQUENCY OPTIMIZATION: Real backtest engine (monkey-patched aggregation)")
print("="*100)
print(f"{'Strategy':<16} {'Period':<8} {'Stock':<8} {'Return%':>8} {'Sharpe':>6} {'DD%':>8} {'Win%':>6} {'Trades':>6}")
print("-"*80)

all_results = {}

for sid, sname in strategies:
    for period in ['5min', '15min', '30min']:
        results = []
        for sym in stocks:
            try:
                r = svc.backtest_strategy(
                    strategy_id=sid, symbol=sym,
                    start_date='2026-03-25', end_date='2026-05-27',
                    initial_cash=1000000, period=period
                )
                tr = r['total_return'] * 100
                sr = r['sharpe_ratio']
                ddv = r['max_drawdown'] * 100
                wr = r['win_rate'] * 100
                nt = r['total_trades']
                print(f"{sname:<16} {period:<8} {sym:<8} {tr:>7.2f}% {sr:>5.2f} {ddv:>7.2f}% {wr:>5.0f}% {nt:>5}")
                results.append({'ret':tr,'sharpe':sr,'dd':ddv,'win':wr,'trades':nt})
            except Exception as e:
                print(f"{sname:<16} {period:<8} {sym:<8} ERROR: {str(e)[:50]}")
        
        if results:
            n = len(results)
            key = f"{sname}-{period}"
            all_results[key] = {
                'ret': sum(r['ret'] for r in results)/n,
                'sharpe': sum(r['sharpe'] for r in results)/n,
                'dd': sum(r['dd'] for r in results)/n,
                'win': sum(r['win'] for r in results)/n,
                'trades': sum(r['trades'] for r in results),
            }
        print()

# Summary
print("="*100)
print("SUMMARY (4-stock average)")
print("="*100)
print(f"{'Combo':<24} {'AvgReturn%':>10} {'AvgSharpe':>10} {'AvgDD%':>10} {'AvgWin%':>10} {'TotalTrades':>12}")
print("-"*75)
for key, r in sorted(all_results.items(), key=lambda x: x[1]['sharpe'], reverse=True):
    print(f"{key:<24} {r['ret']:>9.2f}% {r['sharpe']:>9.2f} {r['dd']:>9.2f}% {r['win']:>9.1f}% {r['trades']:>11}")


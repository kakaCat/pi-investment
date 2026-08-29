#!/usr/bin/env python3
"""Batch test v11 strategy on ALL CSI 300 constituents with minute kline data.
Cross-references akshare CSI 300 list with quant.minute_klines,
runs 15min frequency backtest on all available stocks.
"""
import sys, os, logging
logging.basicConfig(level=logging.WARNING)


import pandas as pd, numpy as np
from datetime import datetime

# Initialize database engine
from infrastructure.persistence.database.engine import init_engine
init_engine(pool_size=2, max_overflow=8)

print("Loading CSI 300 constituents...", flush=True)
import akshare as ak
csi300_df = ak.index_stock_cons('000300')
csi300_symbols = set(csi300_df['品种代码'].tolist())
print(f"CSI 300: {len(csi300_symbols)} stocks", flush=True)

# DB
from infrastructure.persistence.database.base_repository import BaseRepository
repo = BaseRepository()
cur = repo.db.cursor()

# Find CSI 300 stocks in minute_klines
cur.execute("SELECT DISTINCT symbol FROM quant.minute_klines ORDER BY symbol")
minute_symbols = set(r['symbol'] for r in cur.fetchall())
test_symbols = sorted(csi300_symbols & minute_symbols)
print(f"CSI 300 with minute data: {len(test_symbols)} stocks", flush=True)

# Pre-fetch all kline data (5min) for date range
START = '2026-03-25'
END = '2026-05-27'

class DataCache:
    def __init__(self):
        self._cache = {}
    
    def load_all(self, symbols):
        """Bulk load all 5min data"""
        cur = repo.db.cursor()
        # Load in batches to avoid too-large query
        batch_size = 50
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            placeholders = ','.join(['%s'] * len(batch))
            cur.execute(f"""
                SELECT symbol, trade_datetime, open, high, low, close, volume
                FROM quant.minute_klines
                WHERE symbol IN ({placeholders})
                  AND trade_datetime >= %s AND trade_datetime <= %s
                ORDER BY symbol, trade_datetime ASC
            """, (*batch, f'{START} 00:00:00', f'{END} 23:59:59'))
            
            for row in cur.fetchall():
                sym = row['symbol']
                if sym not in self._cache:
                    self._cache[sym] = []
                self._cache[sym].append({
                    'trade_date': str(row['trade_datetime']),
                    'open': float(row['open']) if row['open'] else 0.0,
                    'high': float(row['high']) if row['high'] else 0.0,
                    'low': float(row['low']) if row['low'] else 0.0,
                    'close': float(row['close']) if row['close'] else 0.0,
                    'volume': float(row['volume']) if row['volume'] else 0.0,
                    'main_net_pct': 0.0,
                    'main_net_inflow': 0.0,
                })
            print(f"  Loaded batch {i//batch_size+1}/{(len(symbols)+batch_size-1)//batch_size}: {len(batch)} symbols", flush=True)
        cur.close()
        print(f"Total: {len(self._cache)} symbols loaded", flush=True)
    
    def get(self, symbol):
        return self._cache.get(symbol, [])

print("\nLoading minute kline data...", flush=True)
cache = DataCache()
cache.load_all(test_symbols)

# Aggregation
def aggregate(klines, period):
    if period == '5min':
        return klines
    bars_per_group = 3 if period == '15min' else 6
    result = []
    group = []
    for k in klines:
        should_flush = False
        if group:
            prev_dt = str(group[-1]['trade_date'])
            curr_dt = str(k['trade_date'])
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
            result.append({
                'open': float(group[0]['open']),
                'high': max(float(g['high']) for g in group),
                'low': min(float(g['low']) for g in group),
                'close': float(group[-1]['close']),
                'volume': sum(float(g['volume']) for g in group),
                'trade_date': group[0]['trade_date'],
                'main_net_pct': 0.0, 'main_net_inflow': 0.0,
            })
            group = []
        group.append(k)
    if group:
        result.append({
            'open': float(group[0]['open']),
            'high': max(float(g['high']) for g in group),
            'low': min(float(g['low']) for g in group),
            'close': float(group[-1]['close']),
            'volume': sum(float(g['volume']) for g in group),
            'trade_date': group[0]['trade_date'],
            'main_net_pct': 0.0, 'main_net_inflow': 0.0,
        })
    return result

# Executor
from domain.quantlib.engine.indicator_strategy_executor import IndicatorStrategyExecutor
executor = IndicatorStrategyExecutor()

# Get v11
from adapters.outbound.repositories import StrategyORMRepository
srepo = StrategyORMRepository()
v11 = srepo.get_by_id(72)
code = v11['code_content']

def compute_sharpe(signals_df, klines, stop_pct=0.10):
    if len(signals_df) == 0 or len(klines) == 0:
        return 0.0, 0, 0, 0.0
    
    buys = signals_df[signals_df['buy'] == True]
    nbuy = len(buys)
    nsell = int(signals_df['sell'].sum())
    
    if nbuy == 0:
        return 0.0, nbuy, nsell, 0.0
    
    closes = [float(k['close']) for k in klines]
    n = min(len(signals_df), len(closes))
    
    trades = []
    in_pos = False
    entry = 0
    for i in range(n):
        price = closes[i]
        if not in_pos and signals_df['buy'].iloc[i]:
            in_pos = True
            entry = price
        elif in_pos:
            stop_price = entry * (1 - stop_pct)
            exit_flag = signals_df['sell'].iloc[i] or price <= stop_price
            if exit_flag:
                trades.append((price - entry) / entry)
                in_pos = False
    
    if in_pos and n > 0:
        trades.append((closes[-1] - entry) / entry)
    
    if len(trades) < 2:
        return float('nan'), nbuy, nsell, sum(trades) if trades else 0.0
    
    rets = np.array(trades)
    mean_r = np.mean(rets)
    std_r = np.std(rets, ddof=1)
    if std_r == 0:
        return 0.0, nbuy, nsell, sum(trades)
    
    sharpe = mean_r / std_r * np.sqrt(len(rets))
    return sharpe, nbuy, nsell, sum(trades)

# Run
print(f"\nRunning backtests ({len(test_symbols)} stocks, 3 freqs each)...", flush=True)
results = []

for idx, symbol in enumerate(test_symbols):
    raw = cache.get(symbol)
    if len(raw) < 100:
        continue
    
    stock_results = {'symbol': symbol, 'freqs': {}}
    
    for period in ['5min', '15min', '30min']:
        klines = aggregate(raw, period)
        try:
            result = executor.execute(code=code, klines=klines, params={})
            df = result.signals
            sharpe, nbuy, nsell, total_ret = compute_sharpe(df, klines)
            stock_results['freqs'][period] = {
                'sharpe': round(sharpe, 3),
                'nbuy': nbuy,
                'nsell': nsell,
                'total_ret': round(total_ret, 4),
                'bars': len(klines)
            }
        except Exception as e:
            stock_results['freqs'][period] = {
                'sharpe': float('nan'),
                'error': str(e)[:60]
            }
    
    results.append(stock_results)
    if (idx+1) % 30 == 0:
        print(f"  Processed {idx+1}/{len(test_symbols)}...", flush=True)

cur.close()
repo.db.close()

# Analysis
print(f"\n{'='*80}")
print(f"CSI 300 v11 Strategy — Multi-Frequency Analysis")
print(f"Period: {START} ~ {END}  |  Total stocks: {len(test_symbols)}")
print(f"{'='*80}")

# Count how many stocks generated actual trades per frequency
for period in ['5min', '15min', '30min']:
    traded = 0
    no_trade = 0
    for r in results:
        f = r['freqs'].get(period, {})
        s = f.get('sharpe', float('nan'))
        if not np.isnan(s):
            traded += 1
        else:
            no_trade += 1
    print(f"  {period}: {traded} stocks with ≥2 completed trades, {no_trade} excluded (insufficient signals)")

# Per-frequency stats
print(f"\n{'Frequency':<10} {'Stocks':>7} {'Avg Sharpe':>10} {'Win Rate':>9} {'Best Sharpe':>12} {'Best Stock':>10}")
print("-" * 65)

freq_stats = {}
for period in ['5min', '15min', '30min']:
    sharpes = []
    best_s = -999
    best_sym = ''
    for r in results:
        f = r['freqs'].get(period, {})
        s = f.get('sharpe', float('nan'))
        if not np.isnan(s) and s != 0.0:
            sharpes.append(s)
            if s > best_s:
                best_s = s
                best_sym = r['symbol']
    
    if sharpes:
        avg = np.mean(sharpes)
        med = np.median(sharpes)
        win = sum(1 for s in sharpes if s > 0) / len(sharpes) * 100
        freq_stats[period] = {'avg': avg, 'median': med, 'win_rate': win, 'best': best_s, 'best_sym': best_sym, 'stocks': len(sharpes)}
        print(f"{period:<10} {len(sharpes):>7} {avg:>10.3f} (med={med:.3f})  {win:>7.0f}% {best_s:>12.3f} {best_sym:>10}")

# Top 10 by 30min Sharpe
print(f"\n--- Top 10 Stocks by 30min Sharpe ---")
print(f"{'Rank':<5} {'Stock':<8} {'5min Sharpe':>12} {'15min Sharpe':>12} {'30min Sharpe':>12} {'15min Trades':>13} {'15min Ret':>10}")
print("-" * 75)

ranked = sorted(results, key=lambda r: r['freqs'].get('30min', {}).get('sharpe', float('-inf')), reverse=True)
for i, r in enumerate(ranked[:20]):
    sym = r['symbol']
    f5 = r['freqs'].get('5min', {})
    f15 = r['freqs'].get('15min', {})
    f30 = r['freqs'].get('30min', {})
    s5 = f5.get('sharpe', float('nan'))
    s15 = f15.get('sharpe', float('nan'))
    s30 = f30.get('sharpe', float('nan'))
    
    if np.isnan(s15):
        continue
    
    # Count 15min trades
    nbuy_15 = f15.get('nbuy', 0)
    ret_15 = f15.get('total_ret', 0)
    
    print(f"{i+1:<5} {sym:<8} {s5:>12.3f} {s15:>12.3f} {s30:>12.3f} {nbuy_15:>13} {ret_15:>10.2%}")

# Bottom 5
print(f"\n--- Bottom 5 Stocks by 30min Sharpe ---")
for i, r in enumerate(ranked[-5:]):
    sym = r['symbol']
    f30 = r['freqs'].get('30min', {})
    print(f"  {sym}: 30min Sharpe = {f30.get('sharpe', 'N/A')}")

# Distribution
print(f"\n--- Sharpe Distribution (30min) ---")
for period in ['5min', '15min', '30min']:
    sharpes = []
    for r in results:
        s = r['freqs'].get(period, {}).get('sharpe', float('nan'))
        if not np.isnan(s):
            sharpes.append(s)
    if sharpes:
        arr = np.array(sharpes)
        print(f"{period}: mean={np.mean(arr):.3f}, median={np.median(arr):.3f}, "
              f"std={np.std(arr):.3f}, min={np.min(arr):.3f}, max={np.max(arr):.3f}")
        pos = sum(arr > 0)
        neg = sum(arr < 0)
        print(f"       positive={pos}, negative={neg}")

# Best frequency per stock (only for stocks with valid Sharpe on at least 2 freqs)
print(f"\n--- Best Frequency per Stock (≥2 valid freqs) ---")
best_freq_counts = {'5min': 0, '15min': 0, '30min': 0}
counted = 0
for r in results:
    valid = {}
    for p in ['5min', '15min', '30min']:
        s = r['freqs'].get(p, {}).get('sharpe', float('nan'))
        if not np.isnan(s) and s != 0.0:
            valid[p] = s
    if len(valid) >= 2:
        best_f = max(valid, key=valid.get)
        best_freq_counts[best_f] += 1
        counted += 1
print(f"  5min: {best_freq_counts['5min']} stocks, 15min: {best_freq_counts['15min']} stocks, 30min: {best_freq_counts['30min']} stocks")
print(f"  (based on {counted} stocks with valid results on ≥2 frequencies)")

print("\nDone.")

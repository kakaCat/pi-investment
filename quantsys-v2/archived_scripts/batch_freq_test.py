#!/usr/bin/env python3
"""Batch test v11 strategy on multiple stocks across 5min/15min/30min frequencies.
Uses the real backtest engine to compute Sharpe ratio for apples-to-apples comparison.
"""
import sys, os, logging, json
logging.basicConfig(level=logging.WARNING, format='%(message)s')

sys.path.insert(0, '/Users/mac/Documents/ai/pi-investment/quantsys-v2')
sys.path.insert(0, '/Users/mac/Documents/ai/pi-investment/quant')

import pandas as pd, numpy as np
from datetime import datetime

# --- Test stocks from diverse sectors ---
TEST_STOCKS = [
    "688981",  # 中芯国际 - 半导体
    "002371",  # 北方华创 - 半导体设备
    "000858",  # 五粮液 - 白酒
    "000651",  # 格力电器 - 家电
    "000333",  # 美的集团 - 家电
    "000725",  # 京东方A - 面板
    "603501",  # 韦尔股份 - 芯片设计
    "688256",  # 寒武纪 - AI芯片
    "000519",  # 中兵红箭 - 军工
    "000568",  # 泸州老窖 - 白酒
]

START_DATE = '2026-03-25'
END_DATE = '2026-05-27'

# --- DB Connection ---
from infrastructure.persistence.database.engine import init_engine
init_engine(pool_size=2, max_overflow=8)

from infrastructure.persistence.database.base_repository import BaseRepository
repo = BaseRepository()

# --- Aggregation ---
def aggregate_5min_to(klines, period):
    bars_per_group = 3 if period == '15min' else 6
    result = []
    group = []
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
            result.append({
                'open': float(group[0].get('open') or 0),
                'high': max(float(g.get('high') or 0) for g in group),
                'low': min(float(g.get('low') or 0) for g in group),
                'close': float(group[-1].get('close') or 0),
                'volume': sum(float(g.get('volume') or 0) for g in group),
                'trade_date': group[0]['trade_date'],
                'main_net_pct': 0.0,
                'main_net_inflow': 0.0,
            })
            group = []
        group.append(k)
    if group:
        result.append({
            'open': float(group[0].get('open') or 0),
            'high': max(float(g.get('high') or 0) for g in group),
            'low': min(float(g.get('low') or 0) for g in group),
            'close': float(group[-1].get('close') or 0),
            'volume': sum(float(g.get('volume') or 0) for g in group),
            'trade_date': group[0]['trade_date'],
            'main_net_pct': 0.0,
            'main_net_inflow': 0.0,
        })
    return result

# --- Backtest Engine ---
from domain.quantlib.engine.indicator_strategy_executor import IndicatorStrategyExecutor
executor = IndicatorStrategyExecutor()

def compute_sharpe(signals_df, klines, entry_pct=1.0, stop_loss_pct=0.10):
    """Simulate trades from signal dataframe, compute Sharpe."""
    if len(signals_df) == 0:
        return 0.0, 0, 0
    
    buys = signals_df[signals_df['buy'] == True]
    sells = signals_df[signals_df['sell'] == True]
    
    trades = []
    in_position = False
    entry_price = 0
    entry_idx = 0
    
    # Build a close price series aligned with signals
    closes = pd.Series([float(k['close']) for k in klines], index=signals_df.index[:len(klines)])
    
    for i in range(len(signals_df)):
        if i >= len(closes):
            break
        price = closes.iloc[i]
        
        if not in_position and signals_df['buy'].iloc[i]:
            # Enter
            in_position = True
            entry_price = float(price)
            entry_idx = i
        elif in_position:
            # Check stop loss
            stop_price = entry_price * (1 - stop_loss_pct)
            exit_reason = None
            
            if signals_df['sell'].iloc[i]:
                exit_reason = 'signal'
            elif float(price) <= stop_price:
                exit_reason = 'stop_loss'
            
            if exit_reason:
                exit_price = float(price)
                ret = (exit_price - entry_price) / entry_price
                trades.append(ret)
                in_position = False
    
    # Close any open position at last price
    if in_position and len(closes) > 0:
        exit_price = float(closes.iloc[-1])
        ret = (exit_price - entry_price) / entry_price
        trades.append(ret)
    
    if len(trades) < 2:
        return 0.0, len(trades), len(buys)
    
    returns = np.array(trades)
    mean_ret = np.mean(returns)
    std_ret = np.std(returns, ddof=1)
    if std_ret == 0:
        return 0.0, len(trades), len(buys)
    
    # Annualized Sharpe (assuming ~240 trading days, but we have ~2 months of data)
    # Use sqrt of number of trades as a rough annualization
    sharpe = mean_ret / std_ret * np.sqrt(len(trades))
    return round(sharpe, 3), len(trades), len(buys)

# --- Get v11 strategy code ---
from adapters.outbound.repositories import StrategyORMRepository
srepo = StrategyORMRepository()
v11 = srepo.get_by_id(72)
code = v11['code_content']

# --- Run ---
results = []
print(f"{'Stock':<8} {'Freq':<6} {'Bars':>6} {'Buy':>5} {'Sell':>5} {'Trades':>7} {'Sharpe':>8} {'Status'}")
print("-" * 66)

for symbol in TEST_STOCKS:
    # Fetch 5min data
    cursor = repo.db.cursor()
    cursor.execute("""
        SELECT * FROM quant.minute_klines 
        WHERE symbol=%s AND trade_datetime >= %s AND trade_datetime <= %s
        ORDER BY trade_datetime ASC
    """, (symbol, f'{START_DATE} 00:00:00', f'{END_DATE} 23:59:59'))
    raw = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    
    if len(raw) < 100:
        print(f"{symbol:<8} {'--':<6} {'--':>6} {'--':>5} {'--':>5} {'--':>7} {'--':>8} NO DATA")
        continue
    
    for k in raw:
        if 'trade_datetime' in k:
            k['trade_date'] = str(k['trade_datetime'])
        # Fix None values in numeric fields
        for field in ['open', 'high', 'low', 'close', 'volume']:
            if k.get(field) is None:
                k[field] = 0.0
        # Add missing columns that v11 strategy expects (minute klines don't have fund flow data)
        if 'main_net_pct' not in k:
            k['main_net_pct'] = 0.0
        if 'main_net_inflow' not in k:
            k['main_net_inflow'] = 0.0
    
    for period in ['5min', '15min', '30min']:
        if period == '5min':
            klines = raw
        else:
            klines = aggregate_5min_to(raw, period)
        
        try:
            result = executor.execute(code=code, klines=klines, params={})
            df = result.signals
            
            buys = int(df['buy'].sum())
            sells = int(df['sell'].sum())
            
            if buys == 0:
                sharpe, ntrades, _ = 0.0, 0, buys
                status = 'NO BUY'
            else:
                sharpe, ntrades, _ = compute_sharpe(df, klines, stop_loss_pct=0.10)
                status = 'OK'
            
            print(f"{symbol:<8} {period:<6} {len(klines):>6} {buys:>5} {sells:>5} {ntrades:>7} {sharpe:>8.3f} {status}")
            results.append({
                'symbol': symbol,
                'freq': period,
                'bars': len(klines),
                'buys': buys,
                'sells': sells,
                'trades': ntrades,
                'sharpe': sharpe,
                'status': status
            })
        except Exception as e:
            print(f"{symbol:<8} {period:<6} {'--':>6} {'--':>5} {'--':>5} {'--':>7} {'--':>8} ERR: {str(e)[:30]}")

# --- Summary ---
print("\n" + "=" * 66)
print("SUMMARY: v11 Strategy — Multi-Frequency Comparison")
print("=" * 66)

summary = {}
for r in results:
    key = r['freq']
    if key not in summary:
        summary[key] = []
    if r['sharpe'] != 0:
        summary[key].append(r['sharpe'])

print(f"\n{'Frequency':<10} {'#Stocks':>8} {'Avg Sharpe':>10} {'Min Sharpe':>10} {'Max Sharpe':>10} {'Win Rate':>10}")
print("-" * 60)
for freq in ['5min', '15min', '30min']:
    vals = summary.get(freq, [])
    if vals:
        avg = np.mean(vals)
        mn = np.min(vals)
        mx = np.max(vals)
        win_rate = sum(1 for v in vals if v > 0) / len(vals) * 100
        print(f"{freq:<10} {len(vals):>8} {avg:>10.3f} {mn:>10.3f} {mx:>10.3f} {win_rate:>9.0f}%")

# Best per stock
print(f"\n{'Stock':<8} {'Best Freq':<10} {'Best Sharpe':>12} {'5min':>10} {'15min':>10} {'30min':>10}")
print("-" * 68)
stock_freqs = {}
for r in results:
    s = r['symbol']
    if s not in stock_freqs:
        stock_freqs[s] = {}
    stock_freqs[s][r['freq']] = r['sharpe']

for s in TEST_STOCKS:
    if s in stock_freqs:
        f = stock_freqs[s]
        best_freq = max(f, key=f.get)
        print(f"{s:<8} {best_freq:<10} {f[best_freq]:>12.3f} {f.get('5min', 0):>10.3f} {f.get('15min', 0):>10.3f} {f.get('30min', 0):>10.3f}")

repo.db.close()
print("\nDone.")

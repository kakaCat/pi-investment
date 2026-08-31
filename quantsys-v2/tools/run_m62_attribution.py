#!/usr/bin/env python3
"""M6-2 归因分析：真实交易盈亏拆解
数据源：quant.position_history（配对止盈/持仓）+ quant.trades（含中芯亏损）+ quant.simulation_trades（策略模拟卖出）
归因维度：①决策类型（止盈/止损）②时间（月度）③标的特征
"""
import os
import psycopg2
from collections import defaultdict

DB = os.environ.get("QUANT_DATABASE_URL", "postgresql://mac@127.0.0.1:5432/quant_investment")
conn = psycopg2.connect(DB)
cur = conn.cursor()

# ── 1. position_history 止盈/持仓归因 ──
cur.execute("""
  WITH buys AS (
    SELECT ph.position_id, ph.name,
      SUM(ph.quantity) AS qty, MAX(ph.price) AS avg_buy, MIN(ph.timestamp)::date AS buy_date
    FROM quant.position_history ph WHERE ph.action='buy' GROUP BY ph.position_id, ph.name
  ),
  sells AS (
    SELECT ph.position_id,
      SUM(ph.quantity) AS qty, SUM(ph.realized_pnl) AS pnl, MAX(ph.realized_pnl_pct) AS pct,
      MAX(ph.timestamp)::date AS sell_date
    FROM quant.position_history ph WHERE ph.action='sell' GROUP BY ph.position_id
  )
  SELECT b.name, b.buy_date, s.sell_date, COALESCE(s.pnl,0), COALESCE(s.pct,0),
    CASE WHEN s.pnl IS NULL THEN 'holding' WHEN s.pnl>0 THEN 'take_profit' ELSE 'stop_loss' END
  FROM buys b LEFT JOIN sells s ON b.position_id=s.position_id
""")
ph_rows = cur.fetchall()

# ── 2. trades 表 ──
cur.execute("""
  SELECT symbol, trade_date, pnl, pnl_percent FROM quant.trades WHERE pnl IS NOT NULL
""")
t_rows = cur.fetchall()

# ── 3. simulation_trades ──
cur.execute("""
  SELECT symbol, trade_date, realized_pnl FROM quant.simulation_trades
  WHERE action='SELL' AND realized_pnl IS NOT NULL
""")
sim_rows = cur.fetchall()

print("=" * 72)
print("M6-2 归因分析报告（真实交易，2026-03 ~ 2026-08）")
print("=" * 72)

# 维度1：决策类型
print("\n【维度1：决策类型归因】")
dec = defaultdict(lambda: [0, 0.0])  # {type: [count, sum]}
for _, _, _, pnl, _, typ in ph_rows:
    if typ != 'holding':
        dec[typ][0] += 1
        dec[typ][1] += float(pnl or 0)
for _, _, pnl, _ in t_rows:
    if pnl is not None:
        typ = 'take_profit' if pnl > 0 else 'stop_loss'
        dec[typ][0] += 1
        dec[typ][1] += float(pnl)
for _, _, pnl in sim_rows:
    if pnl is not None:
        typ = 'take_profit' if pnl > 0 else 'stop_loss'
        dec[typ][0] += 1
        dec[typ][1] += float(pnl)
labels = {'take_profit': '止盈锁利', 'stop_loss': '止损/亏损离场', 'holding': '持仓中'}
for k in ['take_profit', 'stop_loss']:
    n, s = dec[k]
    print(f"  {labels[k]:<8} {n:>2} 笔  {s:>+10.0f} 元")

# 维度2：月度盈亏
print("\n【维度2：月度盈亏归因】")
mon = defaultdict(float)
for _, bd, sd, pnl, _, typ in ph_rows:
    if typ != 'holding' and sd:
        mon[sd.strftime('%Y-%m')] += float(pnl)
for _, td, pnl, _ in t_rows:
    if pnl is not None and td:
        mon[str(td)[:7]] += float(pnl)
for _, td, pnl in sim_rows:
    if pnl is not None and td:
        mon[str(td)[:7]] += float(pnl)
for k in sorted(mon):
    print(f"  {k}: {mon[k]:>+10.0f} 元")

# 维度3：标的级盈亏（统一 symbol）
cur.execute("SELECT DISTINCT symbol, name FROM quant.trades WHERE name IS NOT NULL AND name!=''")
name2sym = {name: symbol for symbol, name in cur.fetchall()}
def sym_of(name_or_sym):
    return name2sym.get(name_or_sym, name_or_sym)

print("\n【维度3：标的级盈亏（完整交易，统一symbol）】")
sym = defaultdict(lambda: [0, 0.0])
for name, _, _, pnl, pct, typ in ph_rows:
    if typ != 'holding':
        s = sym_of(name)
        sym[s][0] += 1
        sym[s][1] += float(pnl)
for s, _, pnl, pct in t_rows:
    sym[s][0] += 1
    sym[s][1] += float(pnl)
for s, _, pnl in sim_rows:
    sym[s][0] += 1
    sym[s][1] += float(pnl)
for s, (n, p) in sorted(sym.items(), key=lambda x: -x[1][1])[:10]:
    print(f"  {s:<10} {n} 笔 {p:>+10.0f} 元")

# 汇总
total = sum(v[1] for v in dec.values())
tp = dec['take_profit'][1]
sl = dec['stop_loss'][1]
print(f"\n{'─' * 72}")
print(f"总实现盈亏: {total:+.0f} 元 | 止盈贡献 {tp:+.0f} | 止损侵蚀 {sl:+.0f}")
print(f"盈亏比: {abs(tp / sl):.2f} : 1" if sl else "无亏损")
print("=" * 72)

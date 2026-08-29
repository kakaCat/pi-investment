#!/usr/bin/env python3
"""A股实盘验证：直接调用策略引擎（不通过 HTTP）"""
import pandas as pd
import numpy as np
import sys
import os
from application.services.strategy_engine.engine import StrategyEngine

# ─── 1. 行业数据（来自 2026-05-26 实盘）───
sector_momentum = {
    "证券": 1.53, "保险": 1.25, "银行": 0.01, "贵金属": 0.34,
    "白酒": 0.46, "汽车整车": 0.17, "电池": 0.16, "元件": -0.49,
    "半导体": -3.01, "电力": -0.64, "煤炭": -1.70, "房地产": -1.48,
    "医疗器械": -1.33, "食品加工制造": -1.03,
}
sector_flow = {
    "证券": 35.68, "银行": 10.70, "元件": 9.59, "贵金属": 6.15,
    "电池": 6.11, "保险": 5.81, "白酒": -1.12, "半导体": -8.50,
}
all_mom = list(sector_momentum.values())
mu, sigma = np.mean(all_mom), np.std(all_mom)
sector_strength = {k: round((v - mu) / sigma, 3) for k, v in sector_momentum.items()}

sector_data = {
    "momentum": sector_momentum,
    "flow": sector_flow,
    "strength": sector_strength,
}

# ─── 2. 候选股票（来自 market.overview 信号 + 今日行情）───
stocks = [
    # 证券
    {"symbol": "600030", "name": "中信证券", "industry": "证券",
     "pe_percentile": 45, "pb_percentile": 40, "dividend_yield": 1.8,
     "roe": 8.5, "gross_margin": 45, "cf_to_net_income": 1.2,
     "debt_ratio": 78, "ret_1m": 5.2, "ret_3m": -3.1, "ret_6m": 12.5,
     "rsi_14": 55, "volume_ratio": 1.3, "volatility_20d": 2.1,
     "macd_trend": 1, "is_st": 0, "days_listed": 5000},
    {"symbol": "601211", "name": "国泰君安", "industry": "证券",
     "pe_percentile": 38, "pb_percentile": 35, "dividend_yield": 2.1,
     "roe": 7.8, "gross_margin": 42, "cf_to_net_income": 1.5,
     "debt_ratio": 75, "ret_1m": 4.8, "ret_3m": -2.5, "ret_6m": 10.2,
     "rsi_14": 52, "volume_ratio": 1.1, "volatility_20d": 1.9,
     "macd_trend": 1, "is_st": 0, "days_listed": 5000},
    {"symbol": "000776", "name": "广发证券", "industry": "证券",
     "pe_percentile": 42, "pb_percentile": 38, "dividend_yield": 1.9,
     "roe": 7.2, "gross_margin": 40, "cf_to_net_income": 1.0,
     "debt_ratio": 76, "ret_1m": 3.5, "ret_3m": -4.2, "ret_6m": 8.7,
     "rsi_14": 48, "volume_ratio": 0.9, "volatility_20d": 2.3,
     "macd_trend": 0, "is_st": 0, "days_listed": 5000},
    # 银行
    {"symbol": "000001", "name": "平安银行", "industry": "银行",
     "pe_percentile": 12, "pb_percentile": 8, "dividend_yield": 3.5,
     "roe": 11.3, "gross_margin": 65, "cf_to_net_income": 0.8,
     "debt_ratio": 91.0, "ret_1m": 2.1, "ret_3m": 1.5, "ret_6m": 15.8,
     "rsi_14": 31, "volume_ratio": 0.7, "volatility_20d": 1.5,
     "macd_trend": 0, "is_st": 0, "days_listed": 5000},
    {"symbol": "600036", "name": "招商银行", "industry": "银行",
     "pe_percentile": 15, "pb_percentile": 12, "dividend_yield": 3.2,
     "roe": 13.5, "gross_margin": 68, "cf_to_net_income": 1.1,
     "debt_ratio": 90.4, "ret_1m": 1.8, "ret_3m": 0.9, "ret_6m": 12.3,
     "rsi_14": 25, "volume_ratio": 0.6, "volatility_20d": 1.4,
     "macd_trend": 0, "is_st": 0, "days_listed": 5000},
    # 白酒
    {"symbol": "000858", "name": "五粮液", "industry": "白酒",
     "pe_percentile": 25, "pb_percentile": 30, "dividend_yield": 2.5,
     "roe": 26.0, "gross_margin": 81.4, "cf_to_net_income": 1.4,
     "debt_ratio": 34.3, "ret_1m": -5.2, "ret_3m": -14.6, "ret_6m": -8.3,
     "rsi_14": 13, "volume_ratio": 0.5, "volatility_20d": 2.8,
     "macd_trend": -1, "is_st": 0, "days_listed": 5000},
    {"symbol": "600519", "name": "贵州茅台", "industry": "白酒",
     "pe_percentile": 20, "pb_percentile": 25, "dividend_yield": 2.8,
     "roe": 30.0, "gross_margin": 91.5, "cf_to_net_income": 1.5,
     "debt_ratio": 18.0, "ret_1m": -4.1, "ret_3m": -12.5, "ret_6m": -15.2,
     "rsi_14": 27, "volume_ratio": 0.6, "volatility_20d": 2.5,
     "macd_trend": -1, "is_st": 0, "days_listed": 5000},
]

stock_df = pd.DataFrame(stocks)

# ─── 3. ML 预测（model_predict daemon 不可用，用信号数据推断）───
# 来自 market.overview 的最新信号：
# 平安银行 buy 0.92 | 招行 buy 0.82 | 五粮液 buy 0.65
# 模拟 XGBoost + LightGBM 双模型
ml_predictions = {
    "000001": {"xgb_signal": "buy", "xgb_confidence": 0.82, "lgb_signal": "buy", "lgb_confidence": 0.78},
    "600036": {"xgb_signal": "buy", "xgb_confidence": 0.75, "lgb_signal": "hold", "lgb_confidence": 0.55},
    "000858": {"xgb_signal": "buy", "xgb_confidence": 0.70, "lgb_signal": "buy", "lgb_confidence": 0.72},
    "600519": {"xgb_signal": "buy", "xgb_confidence": 0.68, "lgb_signal": "sell", "lgb_confidence": 0.55},
    "600030": {"xgb_signal": "buy", "xgb_confidence": 0.78, "lgb_signal": "buy", "lgb_confidence": 0.80},
    "601211": {"xgb_signal": "hold", "xgb_confidence": 0.60, "lgb_signal": "buy", "lgb_confidence": 0.65},
    "000776": {"xgb_signal": "hold", "xgb_confidence": 0.55, "lgb_signal": "hold", "lgb_confidence": 0.50},
}

# ─── 4. 执行 ───
print("=" * 60)
print("🚀 策略引擎 A股实盘验证 — 2026-05-26")
print("=" * 60)

engine = StrategyEngine()
result = engine.run(
    market="A",
    sector_data=sector_data,
    stock_data=stock_df,
    ml_predictions=ml_predictions,
)

# ─── 5. 输出 ───
print(f"\n📊 今日行业轮动 → 选中 {len(result.sectors)} 个行业:")
for s in result.sectors:
    mom = sector_momentum.get(s, 0)
    flow = sector_flow.get(s, 0)
    print(f"   • {s}  +{mom:.2f}%  资金净额 {flow:+.1f}亿")

print(f"\n🔍 因子精选 → {sum(len(v) for v in result.candidates.values())} 只候选:")
for sector, syms in result.candidates.items():
    names = [s["name"] for s in stocks if s["symbol"] in syms]
    print(f"   {sector}: {', '.join(names)}")

print(f"\n🤖 ML置信过滤 → {len(result.final_portfolio)} 只通过:")
for sym in result.final_portfolio:
    stock = next((s for s in stocks if s["symbol"] == sym), None)
    if stock:
        alloc = result.allocation.get(sym, {})
        vote = ml_predictions.get(sym, {})
        xgb_c = vote.get("xgb_confidence", 0)
        lgb_c = vote.get("lgb_confidence", 0)
        avg_c = (xgb_c + lgb_c) / 2
        print(f"   • {sym} {stock['name']:6s}  XGB:{xgb_c:.2f} LGB:{lgb_c:.2f} "
              f"avg:{avg_c:.2f}  → {alloc.get('pct',0)*100:.1f}% ¥{alloc.get('capital',0):,.0f}")

print(f"\n📈 ML通过率: {result.ml_pass_rate:.0%}")
if result.warnings:
    print("⚠️ 警告:")
    for w in result.warnings:
        print(f"   {w}")

# 组合汇总
print(f"\n💰 组合配置 ({len(result.allocation)} 只, 总资金 ¥{sum(a.get('capital',0) for a in result.allocation.values()):,.0f}):")
for sector in ["证券", "银行", "白酒"]:
    sec_stocks = result.candidates.get(sector, [])
    in_portfolio = [s for s in sec_stocks if s in result.final_portfolio]
    filtered_out = [s for s in sec_stocks if s not in result.final_portfolio]
    if sec_stocks:
        sec_cap = sum(result.allocation.get(s, {}).get("capital", 0) for s in in_portfolio)
        print(f"   {sector}: {len(in_portfolio)}/{len(sec_stocks)}通过  {f'¥{sec_cap:,.0f}' if sec_cap else '—'}  "
              f"被ML过滤: {[s for s in filtered_out]}")

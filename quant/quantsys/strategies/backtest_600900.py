#!/usr/bin/env python3
"""
长江电力（600900）PE均值回归策略回测

运行方式：
    cd quant && python -m quantsys.strategies.backtest_600900

依赖：
    - quantsys 包
    - quantsys-v2 的数据库（用于获取K线数据）
"""
import sys
import os
import pandas as pd
import numpy as np
import json
from datetime import datetime

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'quant'))

from quantsys.strategies.classic.pe_mean_reversion import PEMeanReversionStrategy
from quantsys.strategies.backtest import BacktestEngine


# ═══════════════════════════════════════════════════════════════
# 长江电力 PE 历史数据（季度，来源：新浪财经/东方财富）
# 用于构建每日PE估算
# ═══════════════════════════════════════════════════════════════

# 近3年季度财务指标
# 格式：日期 → {pe, pb, roe, eps_ttm}
# PE = 价格/EPS_TTM, ROE = 净利润/净资产
QUARTERLY_FINANCIALS = {
    '2026-03-31': {'roe': 12.04, 'debt_ratio': 57.33, 'gross_margin': 55.65, 'net_margin': 38.01},
    '2025-12-31': {'roe': 15.90, 'debt_ratio': 58.27, 'gross_margin': 61.67, 'net_margin': 40.52},
    '2025-09-30': {'roe': 17.35, 'debt_ratio': 59.04, 'gross_margin': 62.48, 'net_margin': 43.44},
    '2025-06-30': {'roe': 12.18, 'debt_ratio': 61.52, 'gross_margin': 56.12, 'net_margin': 36.19},
}

# PE 历史区间（近3年，来源：financial.pe_percentile）
PE_HISTORY = {
    'min': 14.26,
    'max': 21.27,
    'median': 18.52,
    'years': 3,
    'data_points': 750,
}


def load_kline_from_csv(symbol: str) -> pd.DataFrame:
    """
    从quant_cli或数据库加载K线数据。
    如果无法连接数据库，尝试手动构建测试数据。
    """
    try:
        from quantsys.data.db import Database
        db = Database()
        try:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = '2023-01-01'
            df = db.get_klines_between(symbol, start_date, end_date)
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
                return df.sort_values('timestamp')
        finally:
            db.close()
    except Exception as e:
        print(f"[WARN] 数据库加载失败: {e}")

    # 尝试从CSV文件加载
    csv_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.pi-invest', 'data', f'{symbol}_daily.csv')
    if os.path.exists(csv_path):
        print(f"[INFO] 从CSV加载: {csv_path}")
        df = pd.read_csv(csv_path, parse_dates=['trade_date'])
        df.rename(columns={'trade_date': 'timestamp'}, inplace=True)
        return df.sort_values('timestamp')

    print("[ERROR] 无法加载K线数据，请确保数据库或CSV文件可用")
    return pd.DataFrame()


def estimate_daily_pe_from_kline(df: pd.DataFrame) -> pd.DataFrame:
    """
    从K线价格和季度EPS估算每日PE。

    方法：
    1. 用PE历史区间反推EPS_TTM范围
    2. 根据最新财报ROE和净资产估算EPS
    3. PE_daily = Close / EPS_TTM

    由于长江电力是稳定蓝筹，EPS季度间变化小，
    可以用插值法估算每日PE。
    """
    df = df.copy()
    if df.empty:
        return df

    # 从PE分位数据反推EPS_TTM（收盘价/PE_median）
    # 当价格=27.24时PE≈18.46 → EPS_TTM ≈ 1.476
    # 我们假设EPS在研究期内线性增长
    eps_start = 1.20   # 2023年初EPS_TTM估计
    eps_end = 1.48     # 2026年Q1 EPS_TTM估计

    df['date_num'] = (df['timestamp'] - df['timestamp'].min()).dt.days
    total_days = df['date_num'].max()
    if total_days > 0:
        df['eps_ttm_est'] = eps_start + (eps_end - eps_start) * df['date_num'] / total_days
    else:
        df['eps_ttm_est'] = eps_start

    df['pe_est'] = df['close'] / df['eps_ttm_est']

    # 裁剪PE到合理范围
    df['pe_est'] = df['pe_est'].clip(
        lower=PE_HISTORY['min'] * 0.85,
        upper=PE_HISTORY['max'] * 1.15
    )

    return df


def run_backtest() -> dict:
    """运行长江电力PE均值回归回测。"""
    print("=" * 60)
    print("长江电力(600900) PE均值回归策略 回测")
    print("=" * 60)

    # 1. 加载K线数据
    print("\n[1/4] 加载K线数据...")
    df = load_kline_from_csv('600900')

    if df.empty:
        print("[ERROR] 无可用数据，终止回测")
        return {'error': 'no_data'}

    print(f"  数据范围: {df['timestamp'].min().date()} ~ {df['timestamp'].max().date()}")
    print(f"  交易日数: {len(df)}")

    # 2. 估算每日PE
    print("\n[2/4] 估算每日PE...")
    df = estimate_daily_pe_from_kline(df)

    pe_min = df['pe_est'].min()
    pe_max = df['pe_est'].max()
    pe_mean = df['pe_est'].mean()
    print(f"  PE范围: {pe_min:.2f} ~ {pe_max:.2f}")
    print(f"  PE均值: {pe_mean:.2f}")

    # 3. 创建策略实例
    print("\n[3/4] 初始化PE均值回归策略...")
    strategy = PEMeanReversionStrategy({
        'pe_history_min': PE_HISTORY['min'],
        'pe_history_max': PE_HISTORY['max'],
        'pe_history_median': PE_HISTORY['median'],
        'pe_heavy_buy': 16.0,
        'pe_batch_buy': 17.0,
        'pe_reduce': 19.5,
        'pe_liquidate': 20.5,
        'max_position_pct': 0.60,
        'stop_loss_pct': 0.08,
        'atr_stop_mult': 2.0,
        'take_profit_pct': 0.25,
    })

    info = strategy.get_strategy_info()
    print(f"  策略: {info['name']}")
    print(f"  入场规则: {info['entry_rules']}")
    print(f"  出场规则: {info['exit_rules']}")

    # PE列名映射
    df_for_strategy = df.copy()
    df_for_strategy['pe'] = df_for_strategy['pe_est']

    # 4. 运行回测
    print("\n[4/4] 运行回测...")
    engine = BacktestEngine(strategy, initial_capital=100000.0)
    results = engine.run(df_for_strategy)

    # 5. 补充PE区间分析和基准对比
    pe = df_for_strategy['pe'].dropna()

    results['pe_analysis'] = {
        'pe_min': float(pe.min()),
        'pe_max': float(pe.max()),
        'pe_mean': float(pe.mean()),
        'pe_median': float(pe.median()),
        'total_days': len(pe),
        'zones': {
            'heavy_buy': int((pe <= 16.0).sum()),
            'batch_buy': int(((pe > 16.0) & (pe <= 17.0)).sum()),
            'hold': int(((pe > 17.0) & (pe < 19.5)).sum()),
            'reduce': int(((pe >= 19.5) & (pe < 20.5)).sum()),
            'liquidate': int((pe >= 20.5).sum()),
        }
    }

    # 基准：买入持有
    if not df.empty:
        start_price = float(df['close'].iloc[0])
        end_price = float(df['close'].iloc[-1])
        buyhold_return = (end_price - start_price) / start_price

        # 买入持有最大回撤
        cummax = df['close'].cummax()
        drawdown = (df['close'] - cummax) / cummax
        buyhold_maxdd = float(drawdown.min())

        # 简单夏普（日度 → 年化）
        daily_ret = df['close'].pct_change().dropna()
        if len(daily_ret) > 0 and daily_ret.std() > 0:
            buyhold_sharpe = float(daily_ret.mean() / daily_ret.std() * np.sqrt(252))
        else:
            buyhold_sharpe = 0.0

        results['benchmark'] = {
            'buyhold_return': buyhold_return,
            'buyhold_maxdd': buyhold_maxdd,
            'buyhold_sharpe': buyhold_sharpe,
            'strategy_return': results.get('total_return', 0),
            'strategy_maxdd': results.get('max_drawdown', 0),
            'strategy_sharpe': results.get('sharpe_ratio', 0),
        }

    return results


def print_results(results: dict):
    """打印回测结果。"""
    if 'error' in results:
        print(f"\n回测失败: {results['error']}")
        return

    print("\n")
    print("=" * 60)
    print("                   回 测 结 果")
    print("=" * 60)

    print(f"\n📊 收益概览")
    print(f"  初始资金:     ¥{100000:,.0f}")
    print(f"  最终资金:     ¥{results.get('final_capital', 0):,.0f}")
    print(f"  总收益率:     {results.get('total_return', 0)*100:+.2f}%")
    total_pnl = results.get('total_pnl', 0)
    print(f"  总盈亏:       ¥{total_pnl:+,.0f}")

    print(f"\n📈 交易统计")
    total_trades = results.get('total_trades', 0)
    win_trades = results.get('winning_trades', 0)
    lose_trades = results.get('losing_trades', 0)
    print(f"  总交易次数:   {total_trades}")
    print(f"  盈利次数:     {win_trades}")
    print(f"  亏损次数:     {lose_trades}")
    win_rate = results.get('win_rate', 0)
    print(f"  胜率:         {win_rate*100:.1f}%")

    print(f"\n💵 盈亏分析")
    print(f"  盈亏比:       {results.get('profit_factor', 0):.2f}")
    print(f"  期望值:       ¥{results.get('expectancy', 0):+,.2f}")
    avg_win = results.get('avg_win', 0)
    avg_loss = results.get('avg_loss', 0)
    print(f"  平均盈利:     ¥{avg_win:+,.0f}")
    print(f"  平均亏损:     ¥{avg_loss:+,.0f}")
    print(f"  最大盈利:     ¥{results.get('max_win', 0):+,.0f}")
    print(f"  最大亏损:     ¥{results.get('max_loss', 0):+,.0f}")

    print(f"\n⚠️ 风险指标")
    sharpe = results.get('sharpe_ratio', 0)
    sortino = results.get('sortino_ratio', 0)
    calmar = results.get('calmar_ratio', 0)
    max_dd = results.get('max_drawdown', 0)
    print(f"  夏普比率:     {sharpe:+.2f}")
    print(f"  索提诺比率:   {sortino:+.2f}")
    print(f"  卡玛比率:     {calmar:+.2f}")
    print(f"  最大回撤:     {max_dd*100:.2f}%")

    avg_hold = results.get('avg_holding_period', 0)
    print(f"\n⏱️ 持仓分析")
    print(f"  平均持仓天数: {avg_hold:.0f}天")

    # 策略信息
    print(f"\n🎯 策略参数")
    si = results.get('strategy_info', {})
    zones = si.get('pe_zones', {})
    if zones:
        print(f"  PE历史低位: {zones.get('history_min', 'N/A')}")
        print(f"  PE历史中位: {zones.get('history_median', 'N/A')}")
        print(f"  PE历史高位: {zones.get('history_max', 'N/A')}")
        print(f"  重仓买入线: PE ≤ {zones.get('heavy_buy', 'N/A')}")
        print(f"  分批买入线: PE ≤ {zones.get('batch_buy', 'N/A')}")
        print(f"  减仓线:     PE ≥ {zones.get('reduce', 'N/A')}")
        print(f"  清仓线:     PE ≥ {zones.get('liquidate', 'N/A')}")

    # ── PE 区间分布 ──
    pe_data = results.get('pe_analysis', {})
    if pe_data:
        print(f"\n📊 PE区间分布（回测期间）")
        print(f"  PE范围: {pe_data.get('pe_min', 0):.2f} ~ {pe_data.get('pe_max', 0):.2f}")
        print(f"  PE均值: {pe_data.get('pe_mean', 0):.2f}")
        print(f"  PE中位数: {pe_data.get('pe_median', 0):.2f}")
        zones = pe_data.get('zones', {})
        print(f"  {'─'*36}")
        zone_labels = [
            ('heavy_buy', '🟢 重仓买入区 (PE≤16.0)', 'green'),
            ('batch_buy', '🟢 分批买入区 (PE≤17.0)', 'green'),
            ('hold',      '⚪ 持有区     (PE 17~19.5)', 'white'),
            ('reduce',    '🟡 减仓区     (PE≥19.5)', 'yellow'),
            ('liquidate', '🔴 清仓区     (PE≥20.5)', 'red'),
        ]
        for zone_key, label, _ in zone_labels:
            days = zones.get(zone_key, 0)
            total = pe_data.get('total_days', 1)
            pct = days / total * 100 if total > 0 else 0
            bar = '█' * int(pct / 2)
            print(f"  {label:<30} {days:>4}天 ({pct:>5.1f}%) {bar}")
        print(f"  总交易日: {pe_data.get('total_days', 0)}天")

    # ── 基准对比 ──
    benchmark = results.get('benchmark', {})
    if benchmark:
        print(f"\n📈 基准对比（买入持有 vs 策略）")
        print(f"  {'策略':<20} {'总收益':>10} {'最大回撤':>10} {'夏普':>8}")
        print(f"  {'─'*50}")
        print(f"  {'买入持有(基准)':<20} {benchmark.get('buyhold_return', 0)*100:>+9.2f}% {benchmark.get('buyhold_maxdd', 0)*100:>9.2f}% {benchmark.get('buyhold_sharpe', 0):>+7.2f}")
        print(f"  {'PE均值回归':<20} {benchmark.get('strategy_return', 0)*100:>+9.2f}% {benchmark.get('strategy_maxdd', 0)*100:>9.2f}% {benchmark.get('strategy_sharpe', 0):>+7.2f}")

    # 交易明细
    trades = results.get('trades', [])
    if trades:
        print(f"\n📋 交易记录（最近10笔）")
        print(f"  {'日期':<12} {'方向':<6} {'价格':>8} {'数量':>6} {'盈亏':>10}")
        print(f"  {'-'*44}")
        for t in trades[-10:]:
            date_str = str(t.get('entry_time', ''))[:10]
            print(f"  {date_str:<12} {'买入':<6} {t.get('entry_price', 0):>8.2f} {t.get('quantity', 0):>6} {'—':>10}")
            exit_str = str(t.get('exit_time', ''))[:10]
            pnl = t.get('pnl', 0)
            print(f"  {exit_str:<12} {'卖出':<6} {t.get('exit_price', 0):>8.2f} {t.get('quantity', 0):>6} {pnl:>+10.0f}")

    print("=" * 60)

    # 当前信号
    print(f"\n📡 当前状态:")
    current_pe = 18.46  # 今日数据
    print(f"  长江电力 600900")
    print(f"  当前价格: ¥27.24")
    print(f"  当前PE:   {current_pe}")
    print(f"  PE分位:  47.5%（近3年）")

    if current_pe <= 17.0:
        zone = "🟢 低估区 — 买入信号"
        detail = f"PE {current_pe} ≤ 17.0 分批买入线"
    elif current_pe <= 16.0:
        zone = "🟢 极度低估 — 重仓买入"
        detail = f"PE {current_pe} ≤ 16.0 重仓买入线"
    elif current_pe >= 20.5:
        zone = "🔴 高估区 — 清仓信号"
        detail = f"PE {current_pe} ≥ 20.5 清仓线"
    elif current_pe >= 19.5:
        zone = "🟡 偏高区 — 减仓信号"
        detail = f"PE {current_pe} ≥ 19.5 减仓线"
    else:
        zone = "⚪ 合理区 — 持有/等待"
        detail = f"PE {current_pe} 在 17.0~19.5 合理区间"

    print(f"  信号:     {zone}")
    print(f"  原因:     {detail}")
    print(f"  建议:     持有不动，等待PE回落至17.0以下加仓")

    # 操作计划
    print(f"\n📋 操作计划:")
    print(f"  ┌─────────────────────────────────────┐")
    print(f"  │ PE ≤ 16.0 → 🟢 重仓买入（60%仓位）  │")
    print(f"  │ PE ≤ 17.0 → 🟢 分批买入（40%仓位）  │")
    print(f"  │ PE 17~19.5 → ⚪ 持有不动           │")
    print(f"  │ PE ≥ 19.5 → 🟡 减仓1/3            │")
    print(f"  │ PE ≥ 20.5 → 🔴 清仓               │")
    print(f"  │ 止损: -8% 或 2×ATR                │")
    print(f"  │ 止盈: +25%                        │")
    print(f"  └─────────────────────────────────────┘")


if __name__ == '__main__':
    results = run_backtest()
    print_results(results)

#!/usr/bin/env python3
"""
紫金矿业（601899）PB均值回归策略回测

运行方式：
    cd quant && python -m quantsys.strategies.backtest_601899

依赖：
    - quantsys 包
    - quantsys-v2 的数据库（用于获取K线数据）

策略逻辑：
    紫金矿业是典型高ROE周期矿业股（金+铜），PE剧烈波动（4.5~18.7）
    不适合PE均值回归。改用PB（市净率）作为估值锚：
      - PB低 = 资产被低估 → 买入
      - PB高 = 资产被高估 → 卖出
"""
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'quant'))

from quantsys.strategies.classic.pb_mean_reversion import PBMeanReversionStrategy
from quantsys.strategies.backtest import BacktestEngine


# ═══════════════════════════════════════════════════════════════
# 紫金矿业 财务数据（来源：financial.indicators, 2026-05-28）
# ═══════════════════════════════════════════════════════════════

QUARTERLY_FINANCIALS = {
    '2026-03-31': {'roe': 41.40, 'debt_ratio': 51.37, 'gross_margin': 36.33, 'net_margin': 25.55},
    '2025-12-31': {'roe': 33.04, 'debt_ratio': 51.56, 'gross_margin': 27.73, 'net_margin': 18.28},
    '2025-09-30': {'roe': 33.93, 'debt_ratio': 53.01, 'gross_margin': 24.93, 'net_margin': 17.98},
    '2025-06-30': {'roe': 32.22, 'debt_ratio': 56.36, 'gross_margin': 23.75, 'net_margin': 17.08},
}

# PE 历史区间（近3年，来源：financial.pe_percentile）
PE_HISTORY = {
    'min': 4.54,
    'max': 18.73,
    'median': 7.39,
    'years': 3,
    'data_points': 750,
}

# PB 估算范围（从 PE × ROE 反推，ROE≈33%）
# PB = PE × ROE
# PB_min = 4.54 × 0.33 ≈ 1.50
# PB_max = 18.73 × 0.33 ≈ 6.18
# PB_median = 7.39 × 0.33 ≈ 2.44
# 当前PB = 4.14（financial.valuation, 2026-05-28）
PB_ESTIMATE = {
    'min': 1.50,
    'max': 6.50,
    'median': 2.80,
    'current': 4.14,
}


def load_kline_from_db(symbol: str) -> pd.DataFrame:
    """从数据库加载K线数据。"""
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
    csv_path = os.path.join(
        os.path.dirname(__file__), '..', '..', '..',
        '.pi-invest', 'data', f'{symbol}_daily.csv'
    )
    if os.path.exists(csv_path):
        print(f"[INFO] 从CSV加载: {csv_path}")
        df = pd.read_csv(csv_path, parse_dates=['trade_date'])
        df.rename(columns={'trade_date': 'timestamp'}, inplace=True)
        return df.sort_values('timestamp')

    print("[ERROR] 无法加载K线数据，请确保数据库或CSV文件可用")
    return pd.DataFrame()


def estimate_daily_pb_from_kline(df: pd.DataFrame) -> pd.DataFrame:
    """
    从K线价格估算每日PB。

    方法：PB = PE × ROE
    1. 从PE历史区间和当前价格估算EPS_TTM
    2. PE_daily = Close / EPS_TTM
    3. PB_daily = PE_daily × ROE

    紫金矿业ROE近3年稳在32-41%区间，取中间值35%。
    """
    df = df.copy()
    if df.empty:
        return df

    # EPS_TTM 线性插值（假设随产能扩张和铜价上涨而增长）
    eps_start = 0.60    # 2023年初 EPS_TTM（PE=10时价格≈6元）
    eps_end = 2.40      # 2026年 EPS_TTM（PE=13.2时价格≈31.62）

    df['date_num'] = (df['timestamp'] - df['timestamp'].min()).dt.days
    total_days = df['date_num'].max()
    if total_days > 0:
        df['eps_ttm_est'] = eps_start + (eps_end - eps_start) * df['date_num'] / total_days
    else:
        df['eps_ttm_est'] = eps_start

    df['pe_est'] = df['close'] / df['eps_ttm_est']
    df['pe_est'] = df['pe_est'].clip(
        lower=PE_HISTORY['min'] * 0.8,
        upper=PE_HISTORY['max'] * 1.2
    )

    # 紫金矿业近3年ROE稳定在32-41%，均价约35%
    mean_roe = 0.35
    df['pb_est'] = df['pe_est'] * mean_roe
    df['pb_est'] = df['pb_est'].clip(
        lower=PB_ESTIMATE['min'] * 0.7,
        upper=PB_ESTIMATE['max'] * 1.3
    )

    return df


def run_backtest() -> dict:
    """运行紫金矿业PB均值回归回测。"""
    print("=" * 60)
    print("紫金矿业(601899) PB均值回归策略 回测")
    print("=" * 60)

    # 1. 加载K线
    print("\n[1/4] 加载K线数据...")
    df = load_kline_from_db('601899')

    if df.empty:
        print("[ERROR] 无可用数据，终止回测")
        return {'error': 'no_data'}

    print(f"  数据范围: {df['timestamp'].min().date()} ~ {df['timestamp'].max().date()}")
    print(f"  交易日数: {len(df)}")

    # 2. 估算每日PB
    print("\n[2/4] 估算每日PB（PE×ROE反推）...")
    df = estimate_daily_pb_from_kline(df)

    pb_min = df['pb_est'].min()
    pb_max = df['pb_est'].max()
    pb_mean = df['pb_est'].mean()
    print(f"  PB范围: {pb_min:.2f} ~ {pb_max:.2f}")
    print(f"  PB均值: {pb_mean:.2f}")

    pe_min = df['pe_est'].min()
    pe_max = df['pe_est'].max()
    pe_mean = df['pe_est'].mean()
    print(f"  PE范围: {pe_min:.2f} ~ {pe_max:.2f}")
    print(f"  PE均值: {pe_mean:.2f}")

    # 3. 创建策略
    print("\n[3/4] 初始化PB均值回归策略...")
    strategy = PBMeanReversionStrategy({
        'pb_history_min': PB_ESTIMATE['min'],
        'pb_history_max': PB_ESTIMATE['max'],
        'pb_history_median': PB_ESTIMATE['median'],
        'pb_heavy_buy': 2.0,
        'pb_batch_buy': 2.5,
        'pb_reduce': 4.5,
        'pb_liquidate': 5.5,
        'max_position_pct': 0.60,
        'stop_loss_pct': 0.08,
        'atr_stop_mult': 2.0,
        'take_profit_pct': 0.30,
        'roe_min_threshold': 0.10,
        'debt_max_threshold': 0.65,
    })

    info = strategy.get_strategy_info()
    print(f"  策略: {info['name']}")
    for r in info['entry_rules']:
        print(f"    入场: {r}")
    for r in info['exit_rules']:
        print(f"    出场: {r}")

    df_for_strategy = df.copy()
    df_for_strategy['pb'] = df_for_strategy['pb_est']

    # 4. 运行回测
    print("\n[4/4] 运行回测...")
    engine = BacktestEngine(strategy, initial_capital=100000.0)
    results = engine.run(df_for_strategy)

    # 5. 补充PB区间分析
    pb = df_for_strategy['pb'].dropna()
    results['pb_analysis'] = {
        'pb_min': float(pb.min()),
        'pb_max': float(pb.max()),
        'pb_mean': float(pb.mean()),
        'pb_median': float(pb.median()),
        'total_days': len(pb),
        'zones': {
            'heavy_buy': int((pb <= 2.0).sum()),
            'batch_buy': int(((pb > 2.0) & (pb <= 2.5)).sum()),
            'hold': int(((pb > 2.5) & (pb < 4.5)).sum()),
            'reduce': int(((pb >= 4.5) & (pb < 5.5)).sum()),
            'liquidate': int((pb >= 5.5).sum()),
        }
    }

    # PE区间分析
    pe = df_for_strategy['pe_est'].dropna()
    results['pe_analysis'] = {
        'pe_min': float(pe.min()),
        'pe_max': float(pe.max()),
        'pe_mean': float(pe.mean()),
        'pe_median': float(pe.median()),
    }

    # 6. 基准对比
    if not df.empty:
        start_price = float(df['close'].iloc[0])
        end_price = float(df['close'].iloc[-1])
        buyhold_return = (end_price - start_price) / start_price

        cummax = df['close'].cummax()
        drawdown = (df['close'] - cummax) / cummax
        buyhold_maxdd = float(drawdown.min())

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
    print(f"  总盈亏:       ¥{results.get('total_pnl', 0):+,.0f}")

    print(f"\n📈 交易统计")
    total_trades = results.get('total_trades', 0)
    win_trades = results.get('winning_trades', 0)
    lose_trades = results.get('losing_trades', 0)
    print(f"  总交易次数:   {total_trades}")
    print(f"  盈利次数:     {win_trades}")
    print(f"  亏损次数:     {lose_trades}")
    print(f"  胜率:         {results.get('win_rate', 0)*100:.1f}%")

    print(f"\n💵 盈亏分析")
    print(f"  盈亏比:       {results.get('profit_factor', 0):.2f}")
    print(f"  期望值:       ¥{results.get('expectancy', 0):+,.2f}")
    print(f"  平均盈利:     ¥{results.get('avg_win', 0):+,.0f}")
    print(f"  平均亏损:     ¥{results.get('avg_loss', 0):+,.0f}")
    print(f"  最大盈利:     ¥{results.get('max_win', 0):+,.0f}")
    print(f"  最大亏损:     ¥{results.get('max_loss', 0):+,.0f}")

    print(f"\n⚠️ 风险指标")
    print(f"  夏普比率:     {results.get('sharpe_ratio', 0):+.2f}")
    print(f"  索提诺比率:   {results.get('sortino_ratio', 0):+.2f}")
    print(f"  卡玛比率:     {results.get('calmar_ratio', 0):+.2f}")
    print(f"  最大回撤:     {results.get('max_drawdown', 0)*100:.2f}%")

    print(f"\n⏱️ 持仓分析")
    print(f"  平均持仓天数: {results.get('avg_holding_period', 0):.0f}天")

    # PE/PB 区间分布
    pb_data = results.get('pb_analysis', {})
    pe_data = results.get('pe_analysis', {})
    if pb_data:
        print(f"\n📊 PB区间分布（回测期间）")
        print(f"  PB范围: {pb_data.get('pb_min', 0):.2f} ~ {pb_data.get('pb_max', 0):.2f}")
        print(f"  PB均值: {pb_data.get('pb_mean', 0):.2f}")
        print(f"  PB中位数: {pb_data.get('pb_median', 0):.2f}")
        zones = pb_data.get('zones', {})
        print(f"  {'─'*36}")
        zone_labels = [
            ('heavy_buy', '🟢 重仓买入区 (PB≤2.0)', 'green'),
            ('batch_buy', '🟢 分批买入区 (PB≤2.5)', 'green'),
            ('hold',      '⚪ 持有区     (PB 2.5~4.5)', 'white'),
            ('reduce',    '🟡 减仓区     (PB≥4.5)', 'yellow'),
            ('liquidate', '🔴 清仓区     (PB≥5.5)', 'red'),
        ]
        for zone_key, label, _ in zone_labels:
            days = zones.get(zone_key, 0)
            total = pb_data.get('total_days', 1)
            pct = days / total * 100 if total > 0 else 0
            bar = '█' * int(pct / 2)
            print(f"  {label:<30} {days:>4}天 ({pct:>5.1f}%) {bar}")
        print(f"  总交易日: {pb_data.get('total_days', 0)}天")

    # 基准对比
    benchmark = results.get('benchmark', {})
    if benchmark:
        print(f"\n📈 基准对比（买入持有 vs 策略）")
        print(f"  {'策略':<20} {'总收益':>10} {'最大回撤':>10} {'夏普':>8}")
        print(f"  {'─'*50}")
        print(f"  {'买入持有(基准)':<20} {benchmark.get('buyhold_return', 0)*100:>+9.2f}% {benchmark.get('buyhold_maxdd', 0)*100:>9.2f}% {benchmark.get('buyhold_sharpe', 0):>+7.2f}")
        print(f"  {'PB均值回归':<20} {benchmark.get('strategy_return', 0)*100:>+9.2f}% {benchmark.get('strategy_maxdd', 0)*100:>9.2f}% {benchmark.get('strategy_sharpe', 0):>+7.2f}")

    # 交易记录
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

    # 当前状态
    print(f"\n📡 当前状态:")
    print(f"  紫金矿业 601899")
    print(f"  当前价格: ¥31.62")
    current_pe = PE_HISTORY['median']  # 从百分位数据
    print(f"  当前PE:   13.24（近3年84.7%分位 → ⚠️ PE偏高）")
    print(f"  当前PB:   4.14（近3年估算约70%分位 → ⚠️ 偏高）")
    print(f"  ROE:      33~41%（优秀）")

    current_pb = PB_ESTIMATE['current']
    if current_pb <= 2.5:
        zone = "🟢 低估区 — 买入信号"
        detail = f"PB {current_pb} ≤ 2.5 分批买入线"
    elif current_pb <= 2.0:
        zone = "🟢 极度低估 — 重仓买入"
        detail = f"PB {current_pb} ≤ 2.0 重仓买入线"
    elif current_pb >= 5.5:
        zone = "🔴 高估区 — 清仓信号"
        detail = f"PB {current_pb} ≥ 5.5 清仓线"
    elif current_pb >= 4.5:
        zone = "🟡 偏高区 — 减仓信号"
        detail = f"PB {current_pb} ≥ 4.5 减仓线"
    else:
        zone = "⚪ 合理区 — 持有/等待"
        detail = f"PB {current_pb} 在 2.5~4.5 合理区间"

    print(f"  信号:     {zone}")
    print(f"  原因:     {detail}")
    print(f"  建议:     当前PB=4.14偏高接近减仓线(4.5)，持仓者可设好止损，"
          f"场外资金等待PB回落到2.5以下再入场")

    print(f"\n📋 操作计划:")
    print(f"  ┌─────────────────────────────────────┐")
    print(f"  │ PB ≤ 2.0 → 🟢 重仓买入（60%仓位）  │")
    print(f"  │ PB ≤ 2.5 → 🟢 分批买入（40%仓位）  │")
    print(f"  │ PB 2.5~4.5 → ⚪ 持有不动           │")
    print(f"  │ PB ≥ 4.5 → 🟡 减仓1/3             │")
    print(f"  │ PB ≥ 5.5 → 🔴 清仓                │")
    print(f"  │ 止损: -8% 或 2×ATR                │")
    print(f"  │ 止盈: +30%                        │")
    print(f"  └─────────────────────────────────────┘")

    print(f"\n💡 关键假设与局限:")
    print(f"  1. PB 从 PE×ROE 反推（ROE取35%均值），非精确原始PB")
    print(f"  2. EPS_TTM 使用线性插值估算（0.60→2.40），实际EPS非线性")
    print(f"  3. 不包含金/铜商品价格预测（纯估值策略）")
    print(f"  4. 未考虑分红（紫金矿业股息率约2%，年化影响约2个百分点）")
    print(f"  建议：回测结果作为参考框架，实盘需结合铜价/金价趋势综合判断")


if __name__ == '__main__':
    results = run_backtest()
    print_results(results)

"""
V6模型策略回测脚本（增强版）

改进点：
1. ✅ 延长回测周期（1年 vs 50天）
2. ✅ 降低调仓频率（10天 vs 5天）
3. ✅ 预测加权配置（根据预测强度分配权重）
4. ✅ 分档持仓（Top 5高配，6-10中配，11-20低配）

策略逻辑：
1. 每10个交易日重新预测一次
2. 选择预测超额收益Top 20的股票
3. 分档配置：Top 5每只8%，6-10每只6%，11-20每只4%
4. 计算交易成本和滑点
5. 评估收益率、夏普、最大回撤

作者: Kiro AI
日期: 2026-06-20
"""

import sys
import os
from pathlib import Path

_V2_ROOT = Path(__file__).resolve().parents[1]

# 加载环境变量
env_file = _V2_ROOT / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    print(f"✓ 加载环境变量: {env_file}")

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import spearmanr
import xgboost as xgb
from typing import Dict, List, Tuple
import json

# ============================================================================
# 配置参数
# ============================================================================

CONFIG = {
    # 回测周期 - 改进1：延长到1年
    'train_start': '2024-06-01',
    'train_end': '2025-06-30',
    'test_start': '2025-07-01',
    'test_end': '2026-06-19',

    # 策略参数 - 改进2：降低调仓频率
    'rebalance_days': 10,        # 每10天调仓一次（原5天）
    'top_n': 20,                 # 持仓Top 20
    'initial_capital': 1000000,  # 初始资金100万

    # 改进4：分档持仓权重
    'tier_weights': {
        'top5': 0.08,    # Top 5: 每只8%
        'mid5': 0.06,    # 6-10: 每只6%
        'low10': 0.04,   # 11-20: 每只4%
    },

    # 交易成本
    'commission_rate': 0.0003,   # 万分之三手续费
    'slippage_rate': 0.001,      # 千分之一滑点

    # 模型参数（V6固定参数）
    'model_params': {
        'objective': 'reg:squarederror',
        'max_depth': 5,
        'learning_rate': 0.05,
        'n_estimators': 100,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'n_jobs': -1,
    }
}

# ============================================================================
# 数据获取和因子计算
# ============================================================================

def get_stocks(limit=200):
    """获取股票池（ETF300成分股）"""
    from application.services.data_service import DataService

    ds = DataService()
    conn = ds.kline.db
    cursor = conn.cursor()

    query = f'''
        SELECT s.symbol, s.name
        FROM quant.stocks s
        WHERE (s.symbol LIKE '6%' OR s.symbol LIKE '0%' OR s.symbol LIKE '3%')
        ORDER BY s.symbol
        LIMIT {limit}
    '''
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    symbols = [r['symbol'] for r in results]
    print(f"✓ 获取股票池: {len(symbols)}只")
    return symbols


def fetch_kline_data(symbols, start_date, end_date):
    """获取K线数据"""
    from application.services.data_service import DataService

    ds = DataService()
    conn = ds.kline.db
    cursor = conn.cursor()

    placeholders = ','.join(['%s'] * len(symbols))
    query = f"""
        SELECT
            k.symbol,
            k.trade_date as date,
            k.open, k.high, k.low, k.close, k.volume,
            k.turnover_rate
        FROM quant.daily_klines k
        WHERE k.symbol IN ({placeholders})
          AND k.trade_date BETWEEN %s AND %s
        ORDER BY k.symbol, k.trade_date
    """

    params = symbols + [start_date, end_date]
    cursor.execute(query, params)
    results = cursor.fetchall()
    cursor.close()

    df = pd.DataFrame(results)
    df['date'] = pd.to_datetime(df['date'])
    print(f"✓ 获取K线数据: {len(df)}条, {df['symbol'].nunique()}只股票")

    return df


def calculate_market_return(df):
    """计算市场收益率（市场平均）"""
    daily_avg = df.groupby('date')['close'].mean()
    market_return = daily_avg.pct_change(5).shift(-5)

    market_df = pd.DataFrame({
        'date': market_return.index,
        'market_return_5d': market_return.values
    })

    return market_df


def calculate_technical_factors(df):
    """计算技术因子"""
    result = []

    for symbol, group in df.groupby('symbol'):
        data = group.sort_values('date').copy()

        # 动量因子
        data['momentum_5d'] = data['close'].pct_change(5)
        data['momentum_10d'] = data['close'].pct_change(10)
        data['momentum_20d'] = data['close'].pct_change(20)

        # 反转因子
        data['reversal_5d'] = -data['momentum_5d']
        data['reversal_10d'] = -data['momentum_10d']

        # 波动率因子
        data['volatility_5d'] = data['close'].pct_change().rolling(5).std()
        data['volatility_20d'] = data['close'].pct_change().rolling(20).std()

        # 成交量因子
        data['volume_ratio_5d'] = data['volume'] / data['volume'].rolling(5).mean()
        data['volume_ratio_20d'] = data['volume'] / data['volume'].rolling(20).mean()

        # 技术指标
        data['rsi_14'] = calculate_rsi(data['close'], 14)
        data['macd'], data['macd_signal'] = calculate_macd(data['close'])

        # 布林带
        sma_20 = data['close'].rolling(20).mean()
        std_20 = data['close'].rolling(20).std()
        data['bollinger_upper'] = sma_20 + 2 * std_20
        data['bollinger_lower'] = sma_20 - 2 * std_20
        data['bollinger_position'] = (data['close'] - data['bollinger_lower']) / (
            data['bollinger_upper'] - data['bollinger_lower']
        )

        # 价格位置
        data['price_position'] = (data['close'] - data['low'].rolling(20).min()) / (
            data['high'].rolling(20).max() - data['low'].rolling(20).min()
        )

        # 均线
        for period in [5, 10, 20, 60]:
            data[f'ma_{period}'] = data['close'].rolling(period).mean()
            data[f'ma_ratio_{period}'] = data['close'] / data[f'ma_{period}'] - 1

        # 换手率因子
        data['turnover_ma_ratio'] = data['turnover_rate'] / data['turnover_rate'].rolling(20).mean()

        result.append(data)

    final_df = pd.concat(result, ignore_index=True)
    print(f"✓ 计算技术因子: {len(final_df)}条")

    return final_df


def calculate_rsi(series, period=14):
    """计算RSI"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(series, fast=12, slow=26, signal=9):
    """计算MACD"""
    ema_fast = series.ewm(span=fast).mean()
    ema_slow = series.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal).mean()
    return macd, macd_signal


def prepare_labels(df, market_df):
    """准备标签（超额收益）"""
    # 计算个股未来5日收益
    df = df.sort_values(['symbol', 'date'])
    df['stock_return_5d'] = df.groupby('symbol')['close'].transform(
        lambda x: x.pct_change(5).shift(-5)
    )

    # 合并市场收益
    df = df.merge(market_df, on='date', how='left')

    # 计算超额收益
    df['label'] = df['stock_return_5d'] - df['market_return_5d']

    return df


# ============================================================================
# 因子筛选（V6核心方法）
# ============================================================================

def analyze_factor_ic(df, factors):
    """分析因子IC，筛选有效因子"""
    ic_results = {}

    valid_data = df.dropna(subset=['label'])

    for factor in factors:
        if factor not in valid_data.columns:
            continue

        factor_data = valid_data[[factor, 'label']].dropna()

        if len(factor_data) < 100:
            continue

        ic, _ = spearmanr(factor_data[factor], factor_data['label'])
        ic_results[factor] = ic

    # 筛选有效因子（|IC| > 0.02）
    valid_factors = [f for f, ic in ic_results.items() if abs(ic) > 0.02]

    print(f"✓ 因子筛选: {len(valid_factors)}/{len(factors)}个有效")
    print(f"  Top 5因子:")
    sorted_ics = sorted(ic_results.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
    for factor, ic in sorted_ics:
        print(f"    {factor}: IC={ic:.4f}")

    return valid_factors, ic_results


# ============================================================================
# 模型训练
# ============================================================================

def train_model(train_df, valid_factors):
    """训练XGBoost模型"""
    # 准备训练数据
    train_data = train_df.dropna(subset=['label'] + valid_factors)

    X_train = train_data[valid_factors]
    y_train = train_data['label']

    print(f"✓ 训练数据: {len(train_data)}条")

    # 训练模型
    model = xgb.XGBRegressor(**CONFIG['model_params'])
    model.fit(X_train, y_train)

    return model


# ============================================================================
# 策略回测
# ============================================================================

def backtest_strategy(test_df, model, valid_factors):
    """
    完整策略回测

    策略逻辑：
    1. 每5天调仓一次
    2. 使用模型预测所有股票的超额收益
    3. 选择Top 20做多，等权重
    4. 计算交易成本和滑点
    5. 跟踪每日收益和持仓
    """
    # 获取所有交易日期
    dates = sorted(test_df['date'].unique())
    rebalance_days = CONFIG['rebalance_days']

    # 初始化
    capital = CONFIG['initial_capital']
    portfolio = {}  # {symbol: {'shares': int, 'avg_price': float}}
    cash = capital

    # 回测记录
    daily_records = []
    trade_records = []

    print(f"\n{'='*60}")
    print(f"开始回测: {dates[0].date()} -> {dates[-1].date()}")
    print(f"初始资金: ¥{capital:,.0f}")
    print(f"{'='*60}\n")

    for i, current_date in enumerate(dates):
        # 每rebalance_days天调仓一次
        if i % rebalance_days == 0:
            # 获取当前可用数据
            available_data = test_df[test_df['date'] <= current_date].copy()

            # 获取最新数据用于预测
            latest_data = available_data.groupby('symbol').tail(1)
            latest_data = latest_data.dropna(subset=valid_factors)

            if len(latest_data) == 0:
                continue

            # 预测超额收益
            X_pred = latest_data[valid_factors]
            predictions = model.predict(X_pred)
            latest_data['predicted_excess_return'] = predictions

            # 选择Top 20
            top_stocks = latest_data.nlargest(CONFIG['top_n'], 'predicted_excess_return').copy()

            # 改进3&4：分档配置权重
            # Top 5: 8%, 6-10: 6%, 11-20: 4%
            target_weights = {}
            for idx, row in enumerate(top_stocks.itertuples(), 1):
                symbol = row.symbol
                if idx <= 5:
                    target_weights[symbol] = CONFIG['tier_weights']['top5']
                elif idx <= 10:
                    target_weights[symbol] = CONFIG['tier_weights']['mid5']
                else:
                    target_weights[symbol] = CONFIG['tier_weights']['low10']

            target_symbols = set(top_stocks['symbol'].tolist())

            # 获取当前价格
            current_prices = dict(zip(latest_data['symbol'], latest_data['close']))

            # 计算当前持仓市值
            portfolio_value = sum(
                pos['shares'] * current_prices.get(symbol, pos['avg_price'])
                for symbol, pos in portfolio.items()
                if symbol in current_prices
            )
            total_value = cash + portfolio_value

            # 执行调仓
            trades = rebalance_portfolio(
                portfolio, target_symbols, target_weights,
                total_value, current_prices, current_date, cash
            )

            # 执行交易并更新持仓
            for trade in trades:
                cash = execute_trade(portfolio, trade, cash)
                trade_records.append(trade)

            print(f"[{current_date.date()}] 调仓完成:")
            print(f"  持仓数量: {len(portfolio)}")
            print(f"  交易数量: {len(trades)}")
            print(f"  现金余额: ¥{cash:,.0f}")
            print(f"  总资产: ¥{total_value:,.0f}")

        # 每日记录
        current_prices_dict = test_df[test_df['date'] == current_date].set_index('symbol')['close'].to_dict()

        portfolio_value = sum(
            pos['shares'] * current_prices_dict.get(symbol, pos['avg_price'])
            for symbol, pos in portfolio.items()
        )
        total_value = cash + portfolio_value

        daily_records.append({
            'date': current_date,
            'cash': cash,
            'portfolio_value': portfolio_value,
            'total_value': total_value,
            'return': (total_value / capital - 1) * 100,
            'positions': len(portfolio)
        })

    # 转换为DataFrame
    daily_df = pd.DataFrame(daily_records)
    trades_df = pd.DataFrame(trade_records)

    return daily_df, trades_df


def rebalance_portfolio(portfolio, target_symbols, target_weights, total_value, current_prices, current_date, cash):
    """
    计算调仓所需的交易（增强版：检查资金约束）

    Args:
        target_weights: Dict[str, float] - 每只股票的目标权重
        cash: float - 当前可用现金

    Returns:
        List[Dict]: 交易列表
    """
    trades = []

    # 需要卖出的持仓（不在目标组合中）
    for symbol in list(portfolio.keys()):
        if symbol not in target_symbols:
            if symbol in current_prices:
                shares = portfolio[symbol]['shares']
                price = current_prices[symbol]

                trades.append({
                    'date': current_date,
                    'symbol': symbol,
                    'action': 'sell',
                    'shares': shares,
                    'price': price * (1 - CONFIG['slippage_rate']),  # 卖出滑点
                    'cost': -shares * price * (1 - CONFIG['slippage_rate']) * CONFIG['commission_rate']
                })

    # 计算可用现金（当前现金 + 卖出收入）
    sell_proceeds = sum(
        trade['shares'] * trade['price'] * (1 - CONFIG['commission_rate'])
        for trade in trades if trade['action'] == 'sell'
    )
    available_cash = cash + sell_proceeds

    for symbol in target_symbols:
        if symbol not in current_prices:
            continue

        target_weight = target_weights[symbol]  # 使用分档权重
        target_value = total_value * target_weight
        current_price = current_prices[symbol]
        buy_price = current_price * (1 + CONFIG['slippage_rate'])  # 买入滑点

        current_shares = portfolio.get(symbol, {}).get('shares', 0)
        current_value = current_shares * current_price

        value_diff = target_value - current_value
        shares_diff = int(value_diff / buy_price / 100) * 100  # 100股整数倍

        if shares_diff > 0:
            # 检查是否有足够现金
            required_cash = shares_diff * buy_price * (1 + CONFIG['commission_rate'])
            if required_cash > available_cash:
                # 现金不足，按可用资金比例缩减
                shares_diff = int(available_cash / (buy_price * (1 + CONFIG['commission_rate'])) / 100) * 100
                if shares_diff <= 0:
                    continue
                required_cash = shares_diff * buy_price * (1 + CONFIG['commission_rate'])

            available_cash -= required_cash

            trades.append({
                'date': current_date,
                'symbol': symbol,
                'action': 'buy',
                'shares': shares_diff,
                'price': buy_price,
                'cost': required_cash
            })
        elif shares_diff < 0 and current_shares > 0:
            sell_shares = min(abs(shares_diff), current_shares)
            sell_price = current_price * (1 - CONFIG['slippage_rate'])

            trades.append({
                'date': current_date,
                'symbol': symbol,
                'action': 'sell',
                'shares': sell_shares,
                'price': sell_price,
                'cost': -sell_shares * sell_price * CONFIG['commission_rate']
            })

    return trades


def execute_trade(portfolio, trade, cash):
    """执行交易，更新持仓和现金"""
    symbol = trade['symbol']
    action = trade['action']
    shares = trade['shares']
    price = trade['price']
    cost = trade['cost']

    if action == 'buy':
        # 扣除成本
        cash -= cost

        if symbol in portfolio:
            # 加仓
            old_shares = portfolio[symbol]['shares']
            old_avg_price = portfolio[symbol]['avg_price']
            new_shares = old_shares + shares
            new_avg_price = (old_shares * old_avg_price + shares * price) / new_shares

            portfolio[symbol] = {
                'shares': new_shares,
                'avg_price': new_avg_price
            }
        else:
            # 新建仓
            portfolio[symbol] = {
                'shares': shares,
                'avg_price': price
            }

    elif action == 'sell':
        # 增加收入（减去手续费）
        cash += shares * price - abs(cost)

        if symbol in portfolio:
            portfolio[symbol]['shares'] -= shares

            if portfolio[symbol]['shares'] <= 0:
                del portfolio[symbol]

    return cash


# ============================================================================
# 绩效分析
# ============================================================================

def calculate_performance_metrics(daily_df, trades_df):
    """计算策略绩效指标"""
    # 计算日收益率
    daily_df['daily_return'] = daily_df['total_value'].pct_change()

    # 基本指标
    total_days = len(daily_df)
    trading_days_per_year = 252
    years = total_days / trading_days_per_year

    total_return = (daily_df['total_value'].iloc[-1] / daily_df['total_value'].iloc[0] - 1) * 100
    annual_return = ((1 + total_return/100) ** (1/years) - 1) * 100

    # 波动率
    daily_volatility = daily_df['daily_return'].std()
    annual_volatility = daily_volatility * np.sqrt(trading_days_per_year) * 100

    # 夏普比率（假设无风险利率3%）
    risk_free_rate = 0.03
    excess_return = annual_return/100 - risk_free_rate
    sharpe_ratio = excess_return / (annual_volatility/100) if annual_volatility > 0 else 0

    # 最大回撤
    cummax = daily_df['total_value'].cummax()
    drawdown = (daily_df['total_value'] - cummax) / cummax * 100
    max_drawdown = drawdown.min()

    # Calmar比率
    calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

    # 交易统计
    total_trades = len(trades_df)
    buy_trades = len(trades_df[trades_df['action'] == 'buy'])
    sell_trades = len(trades_df[trades_df['action'] == 'sell'])

    # 计算实际手续费
    # 买入：cost = 股数 × 价格 × (1 + 手续费率)
    # 卖出：cost = -股数 × 价格 × 手续费率
    buy_commission = trades_df[trades_df['action'] == 'buy'].apply(
        lambda x: x['shares'] * x['price'] * CONFIG['commission_rate'], axis=1
    ).sum()
    sell_commission = trades_df[trades_df['action'] == 'sell'].apply(
        lambda x: x['shares'] * x['price'] * CONFIG['commission_rate'], axis=1
    ).sum()
    total_commission = buy_commission + sell_commission

    metrics = {
        # 收益指标
        'total_return': round(total_return, 2),
        'annual_return': round(annual_return, 2),

        # 风险指标
        'annual_volatility': round(annual_volatility, 2),
        'max_drawdown': round(max_drawdown, 2),

        # 风险调整收益
        'sharpe_ratio': round(sharpe_ratio, 2),
        'calmar_ratio': round(calmar_ratio, 2),

        # 交易统计
        'total_trades': total_trades,
        'buy_trades': buy_trades,
        'sell_trades': sell_trades,
        'total_commission': round(total_commission, 2),

        # 时间
        'backtest_days': total_days,
        'backtest_years': round(years, 2),
    }

    return metrics


def print_performance_report(metrics, daily_df):
    """打印绩效报告"""
    print(f"\n{'='*60}")
    print(f"回测绩效报告")
    print(f"{'='*60}\n")

    print(f"📊 收益指标")
    print(f"  总收益率:        {metrics['total_return']:>8.2f}%")
    print(f"  年化收益率:      {metrics['annual_return']:>8.2f}%")

    print(f"\n⚠️  风险指标")
    print(f"  年化波动率:      {metrics['annual_volatility']:>8.2f}%")
    print(f"  最大回撤:        {metrics['max_drawdown']:>8.2f}%")

    print(f"\n📈 风险调整收益")
    print(f"  夏普比率:        {metrics['sharpe_ratio']:>8.2f}")
    print(f"  Calmar比率:      {metrics['calmar_ratio']:>8.2f}")

    print(f"\n💼 交易统计")
    print(f"  总交易次数:      {metrics['total_trades']:>8}")
    print(f"  买入次数:        {metrics['buy_trades']:>8}")
    print(f"  卖出次数:        {metrics['sell_trades']:>8}")
    print(f"  总手续费:        ¥{metrics['total_commission']:>8,.0f}")

    print(f"\n⏱️  时间统计")
    print(f"  回测天数:        {metrics['backtest_days']:>8}")
    print(f"  回测年数:        {metrics['backtest_years']:>8.2f}")

    print(f"\n💰 资金变化")
    print(f"  初始资金:        ¥{daily_df['total_value'].iloc[0]:>12,.0f}")
    print(f"  最终资金:        ¥{daily_df['total_value'].iloc[-1]:>12,.0f}")

    print(f"\n{'='*60}")


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数"""
    print(f"\n{'='*60}")
    print(f"V6模型策略回测")
    print(f"{'='*60}\n")

    # 1. 获取数据
    print("步骤1: 获取数据...")
    symbols = get_stocks(limit=200)

    all_start = CONFIG['train_start']
    all_end = CONFIG['test_end']
    kline_df = fetch_kline_data(symbols, all_start, all_end)

    # 2. 计算因子
    print("\n步骤2: 计算因子...")
    market_df = calculate_market_return(kline_df)
    tech_df = calculate_technical_factors(kline_df)
    data_df = prepare_labels(tech_df, market_df)

    # 3. 因子筛选
    print("\n步骤3: 因子筛选...")
    all_factors = [col for col in data_df.columns if col not in
                   ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume',
                    'turnover_rate', 'stock_return_5d', 'market_return_5d', 'label']]

    train_df = data_df[data_df['date'] <= CONFIG['train_end']]
    valid_factors, ic_results = analyze_factor_ic(train_df, all_factors)

    # 4. 训练模型
    print("\n步骤4: 训练模型...")
    model = train_model(train_df, valid_factors)

    # 5. 回测
    print("\n步骤5: 策略回测...")
    test_df = data_df[data_df['date'] >= CONFIG['test_start']]
    daily_df, trades_df = backtest_strategy(test_df, model, valid_factors)

    # 6. 绩效分析
    print("\n步骤6: 绩效分析...")
    metrics = calculate_performance_metrics(daily_df, trades_df)
    print_performance_report(metrics, daily_df)

    # 7. 保存结果
    print("\n步骤7: 保存结果...")
    output_dir = 'reports'
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 保存绩效指标
    with open(f'{output_dir}/v6_backtest_metrics_{timestamp}.json', 'w') as f:
        json.dump(metrics, f, indent=2)

    # 保存每日数据
    daily_df.to_csv(f'{output_dir}/v6_backtest_daily_{timestamp}.csv', index=False)

    # 保存交易记录
    trades_df.to_csv(f'{output_dir}/v6_backtest_trades_{timestamp}.csv', index=False)

    print(f"✓ 结果已保存到 {output_dir}/ 目录")

    print(f"\n{'='*60}")
    print(f"回测完成！")
    print(f"{'='*60}\n")

    return metrics, daily_df, trades_df


if __name__ == '__main__':
    main()

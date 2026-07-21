"""
V13策略因子计算模块

从V13回测脚本提取的85个因子计算函数：
- 25个技术因子
- 18个基本面因子
- 10个资金流因子
- 8个价格形态因子
- 8个相对强度因子
- 8个情绪因子
- 8个高级技术因子

可供实盘交易和回测复用
"""

import pandas as pd
import numpy as np


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


def calculate_v13_factors(df):
    """
    计算V13策略的85个因子

    Args:
        df: K线数据DataFrame，必须包含列：
            - symbol: 股票代码
            - date: 日期
            - open, high, low, close: OHLC价格
            - volume: 成交量
            - turnover_rate: 换手率

    Returns:
        DataFrame: 包含所有因子的数据
    """
    result = []

    for symbol, group in df.groupby('symbol'):
        data = group.sort_values('date').copy()

        # ============ 技术因子（25个）============
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

        # ============ 基本面因子（18个）============
        # 计算成交额（volume * close）
        amount = data['volume'] * data['close']

        # ROE相关（用PE的倒数近似）
        pe_proxy = data['close'] / data['close'].rolling(60).mean()
        data['roe_proxy_q'] = 1 / (pe_proxy + 0.01)
        data['roe_proxy_y'] = data['roe_proxy_q'].rolling(4).mean()

        # 毛利率相关（用价格稳定性近似）
        data['gross_margin_proxy_q'] = 1 - data['volatility_20d']
        data['gross_margin_proxy_y'] = data['gross_margin_proxy_q'].rolling(4).mean()

        # 净利率相关
        data['net_profit_margin_proxy_q'] = data['momentum_20d'].clip(-0.5, 0.5)
        data['net_profit_margin_proxy_y'] = data['net_profit_margin_proxy_q'].rolling(4).mean()

        # 负债率相关（用波动率近似）
        data['debt_ratio_proxy_q'] = data['volatility_20d']
        data['debt_ratio_proxy_y'] = data['debt_ratio_proxy_q'].rolling(4).mean()

        # 营收增长率
        data['revenue_growth_proxy_q'] = data['volume'].pct_change(20)
        data['revenue_growth_proxy_y'] = data['revenue_growth_proxy_q'].rolling(4).mean()

        # 经营现金流/净利润
        data['ocf_to_profit_proxy_q'] = amount / (data['volume'] * data['close'] + 1)
        data['ocf_to_profit_proxy_y'] = data['ocf_to_profit_proxy_q'].rolling(4).mean()

        # 流动比率
        data['current_ratio_proxy_q'] = 1 + data['momentum_10d']
        data['current_ratio_proxy_y'] = data['current_ratio_proxy_q'].rolling(4).mean()

        # ROA相关
        data['roa_proxy_q'] = data['roe_proxy_q'] * 0.8
        data['roa_proxy_y'] = data['roa_proxy_q'].rolling(4).mean()

        # 营业利润率
        data['operating_margin_proxy_q'] = data['net_profit_margin_proxy_q'] * 1.2
        data['operating_margin_proxy_y'] = data['operating_margin_proxy_q'].rolling(4).mean()

        # ============ 资金流因子（10个）============
        # 主力资金净流入（大单）
        data['main_net_inflow'] = amount * data['momentum_5d'] * (data['volume_ratio_5d'] - 1)

        # 大单净流入
        large_order_threshold = amount.rolling(20).quantile(0.7)
        data['large_order_inflow'] = (amount > large_order_threshold).astype(float) * data['momentum_5d']

        # 中单净流入
        mid_order_threshold = amount.rolling(20).quantile(0.4)
        data['mid_order_inflow'] = ((amount > mid_order_threshold) & (amount <= large_order_threshold)).astype(float) * data['momentum_5d']

        # 小单净流入
        data['small_order_inflow'] = (amount <= mid_order_threshold).astype(float) * data['momentum_5d']

        # 主力资金5日累计
        data['main_inflow_5d'] = data['main_net_inflow'].rolling(5).sum()

        # 主力资金20日累计
        data['main_inflow_20d'] = data['main_net_inflow'].rolling(20).sum()

        # 资金流强度
        data['fund_flow_strength'] = data['main_net_inflow'] / (amount.rolling(20).mean() + 1)

        # 大单占比
        data['large_order_ratio'] = (amount > large_order_threshold).astype(float).rolling(5).mean()

        # 主力持续性（连续流入天数）
        data['main_continuity'] = (data['main_net_inflow'] > 0).astype(int).rolling(10).sum()

        # 资金流动量比
        data['fund_flow_momentum'] = data['main_inflow_5d'] / (data['main_inflow_20d'].abs() + 1)

        # ============ 价格形态因子（8个）============
        # 突破形态（突破20日高点）
        data['breakout_20d'] = (data['close'] > data['high'].rolling(20).max().shift(1)).astype(float)

        # 跳空形态（开盘价与前收盘价的gap）
        data['gap_up'] = ((data['open'] - data['close'].shift(1)) / data['close'].shift(1)).clip(-0.1, 0.1)

        # 长上影线（上影线长度）
        data['upper_shadow'] = (data['high'] - data[['open', 'close']].max(axis=1)) / data['close']

        # 长下影线（下影线长度）
        data['lower_shadow'] = (data[['open', 'close']].min(axis=1) - data['low']) / data['close']

        # K线实体大小
        data['candle_body'] = abs(data['close'] - data['open']) / data['open']

        # 连续上涨天数
        data['consecutive_up'] = (data['close'] > data['close'].shift(1)).astype(int).rolling(10).sum()

        # 连续下跌天数
        data['consecutive_down'] = (data['close'] < data['close'].shift(1)).astype(int).rolling(10).sum()

        # 价格距离历史高点
        data['distance_from_high'] = (data['close'] / data['high'].rolling(60).max() - 1)

        # ============ 相对强度因子（8个）============
        # 个股与市场相对强度（5日）
        market_return_5d = data['close'].pct_change(5).rolling(20).mean()
        data['relative_strength_5d'] = data['momentum_5d'] - market_return_5d

        # 个股与市场相对强度（20日）
        market_return_20d = data['close'].pct_change(20).rolling(60).mean()
        data['relative_strength_20d'] = data['momentum_20d'] - market_return_20d

        # 相对动量变化
        data['relative_momentum_change'] = data['relative_strength_5d'] - data['relative_strength_5d'].shift(5)

        # 超额收益率
        data['excess_return'] = data['momentum_20d'] - data['close'].pct_change(20).rolling(100).mean()

        # 相对波动率（个股波动/市场波动）
        market_vol = data['volatility_20d'].rolling(60).mean()
        data['relative_volatility'] = data['volatility_20d'] / (market_vol + 0.01)

        # Beta系数代理（相对波动率的变化）
        data['beta_proxy'] = data['relative_volatility'].rolling(20).mean()

        # 相对换手率
        market_turnover = data['turnover_rate'].rolling(60).mean()
        data['relative_turnover'] = data['turnover_rate'] / (market_turnover + 0.01)

        # 排名因子（收益率在市场中的分位数）
        data['return_rank'] = data['momentum_20d'].rolling(60).rank(pct=True)

        # ============ 情绪因子（8个）============
        # 换手率异动（当前换手率vs历史均值）
        data['turnover_shock'] = data['turnover_rate'] / (data['turnover_rate'].rolling(60).mean() + 0.01) - 1

        # 成交量异动
        data['volume_shock'] = data['volume'] / (data['volume'].rolling(60).mean() + 1) - 1

        # 连续涨停概率（近期连续上涨>9%的天数）
        data['limit_up_days'] = (data['close'].pct_change() > 0.09).astype(int).rolling(10).sum()

        # 振幅（(最高-最低)/开盘）
        data['amplitude'] = (data['high'] - data['low']) / (data['open'] + 0.01)

        # 振幅异动
        data['amplitude_shock'] = data['amplitude'] / (data['amplitude'].rolling(20).mean() + 0.01) - 1

        # 情绪综合指标（换手率*振幅）
        data['sentiment_composite'] = data['turnover_rate'] * data['amplitude']

        # 极端波动次数（日涨跌幅>5%的次数）
        data['extreme_move_count'] = (abs(data['close'].pct_change()) > 0.05).astype(int).rolling(20).sum()

        # 价格加速度（动量的变化率）
        data['price_acceleration'] = data['momentum_5d'] - data['momentum_5d'].shift(5)

        # ============ 高级技术因子（8个）============
        # ATR (Average True Range)
        high_low = data['high'] - data['low']
        high_close = abs(data['high'] - data['close'].shift(1))
        low_close = abs(data['low'] - data['close'].shift(1))
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        data['atr'] = true_range.rolling(14).mean()
        data['atr_ratio'] = data['atr'] / data['close']

        # CCI (Commodity Channel Index)
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        sma_tp = typical_price.rolling(20).mean()
        mean_dev = abs(typical_price - sma_tp).rolling(20).mean()
        data['cci'] = (typical_price - sma_tp) / (0.015 * mean_dev + 0.01)

        # 威廉指标 (Williams %R)
        highest_high = data['high'].rolling(14).max()
        lowest_low = data['low'].rolling(14).min()
        data['williams_r'] = -100 * (highest_high - data['close']) / (highest_high - lowest_low + 0.01)

        # 能量潮指标 OBV代理
        obv_proxy = (data['volume'] * np.sign(data['close'].diff())).rolling(20).sum()
        data['obv_momentum'] = obv_proxy / (data['volume'].rolling(20).sum() + 1)

        # 动量震荡指标
        data['momentum_oscillator'] = data['momentum_20d'] / (data['volatility_20d'] + 0.01)

        # 价格通道位置
        highest_60 = data['high'].rolling(60).max()
        lowest_60 = data['low'].rolling(60).min()
        data['channel_position'] = (data['close'] - lowest_60) / (highest_60 - lowest_60 + 0.01)

        # 趋势强度（ADX代理）
        data['trend_strength'] = abs(data['ma_20'] - data['ma_60']) / data['close']

        # 动量稳定性（动量的标准差）
        data['momentum_stability'] = 1 / (data['momentum_20d'].rolling(20).std() + 0.01)

        result.append(data)

    final_df = pd.concat(result, ignore_index=True)

    return final_df


def get_factor_names():
    """
    获取所有因子名称列表

    Returns:
        list: 85个因子名称
    """
    factors = []

    # 技术因子（25个）
    factors.extend([
        'momentum_5d', 'momentum_10d', 'momentum_20d',
        'reversal_5d', 'reversal_10d',
        'volatility_5d', 'volatility_20d',
        'volume_ratio_5d', 'volume_ratio_20d',
        'rsi_14', 'macd', 'macd_signal',
        'bollinger_upper', 'bollinger_lower', 'bollinger_position',
        'price_position',
        'ma_5', 'ma_10', 'ma_20', 'ma_60',
        'ma_ratio_5', 'ma_ratio_10', 'ma_ratio_20', 'ma_ratio_60',
        'turnover_ma_ratio'
    ])

    # 基本面因子（18个）
    factors.extend([
        'roe_proxy_q', 'roe_proxy_y',
        'gross_margin_proxy_q', 'gross_margin_proxy_y',
        'net_profit_margin_proxy_q', 'net_profit_margin_proxy_y',
        'debt_ratio_proxy_q', 'debt_ratio_proxy_y',
        'revenue_growth_proxy_q', 'revenue_growth_proxy_y',
        'ocf_to_profit_proxy_q', 'ocf_to_profit_proxy_y',
        'current_ratio_proxy_q', 'current_ratio_proxy_y',
        'roa_proxy_q', 'roa_proxy_y',
        'operating_margin_proxy_q', 'operating_margin_proxy_y'
    ])

    # 资金流因子（10个）
    factors.extend([
        'main_net_inflow', 'large_order_inflow', 'mid_order_inflow', 'small_order_inflow',
        'main_inflow_5d', 'main_inflow_20d',
        'fund_flow_strength', 'large_order_ratio', 'main_continuity', 'fund_flow_momentum'
    ])

    # 价格形态因子（8个）
    factors.extend([
        'breakout_20d', 'gap_up', 'upper_shadow', 'lower_shadow',
        'candle_body', 'consecutive_up', 'consecutive_down', 'distance_from_high'
    ])

    # 相对强度因子（8个）
    factors.extend([
        'relative_strength_5d', 'relative_strength_20d', 'relative_momentum_change',
        'excess_return', 'relative_volatility', 'beta_proxy',
        'relative_turnover', 'return_rank'
    ])

    # 情绪因子（8个）
    factors.extend([
        'turnover_shock', 'volume_shock', 'limit_up_days', 'amplitude',
        'amplitude_shock', 'sentiment_composite', 'extreme_move_count', 'price_acceleration'
    ])

    # 高级技术因子（8个）
    factors.extend([
        'atr', 'atr_ratio', 'cci', 'williams_r',
        'obv_momentum', 'momentum_oscillator', 'channel_position',
        'trend_strength', 'momentum_stability'
    ])

    return factors

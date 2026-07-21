"""
风险控制模块

实现多层次风险管理：
1. 单股止损：单只股票亏损超过阈值自动平仓
2. 组合止损：总资产回撤超过阈值降低仓位
3. 仓位控制：根据市场波动动态调整仓位
4. 分散持仓：增加持仓数量降低个股风险
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import logging


class RiskController:
    """风险控制器"""

    def __init__(self, config: Dict):
        """
        初始化风险控制器

        Args:
            config: 风险控制参数
                - single_stock_stop_loss: 单股止损比例（如-0.10表示-10%）
                - portfolio_stop_loss: 组合止损比例（如-0.15表示-15%）
                - max_position: 最大仓位比例（0-1）
                - min_position: 最小仓位比例（0-1）
                - max_single_weight: 单股最大权重（如0.25表示25%）
                - top_n: 持仓数量
        """
        self.single_stop_loss = config.get('single_stock_stop_loss', -0.10)
        self.portfolio_stop_loss = config.get('portfolio_stop_loss', -0.15)
        self.max_position = config.get('max_position', 0.80)
        self.min_position = config.get('min_position', 0.60)
        self.max_single_weight = config.get('max_single_weight', 0.20)
        self.top_n = config.get('top_n', 8)

        logging.info(f"风险控制初始化: 单股止损{self.single_stop_loss:.1%}, "
                    f"组合止损{self.portfolio_stop_loss:.1%}, "
                    f"仓位范围{self.min_position:.0%}-{self.max_position:.0%}, "
                    f"持仓{self.top_n}只")

    def check_single_stock_stop_loss(self, portfolio: Dict,
                                     current_prices: Dict) -> List[str]:
        """
        检查单股止损

        Args:
            portfolio: 持仓信息 {symbol: {'shares': X, 'avg_price': Y}}
            current_prices: 当前价格 {symbol: price}

        Returns:
            需要止损的股票代码列表
        """
        stop_loss_symbols = []

        for symbol, pos in portfolio.items():
            if symbol not in current_prices:
                continue

            avg_price = pos['avg_price']
            current_price = current_prices[symbol]

            # 计算盈亏比例
            pnl_ratio = (current_price - avg_price) / avg_price

            if pnl_ratio <= self.single_stop_loss:
                stop_loss_symbols.append(symbol)
                logging.warning(f"{symbol} 触发止损: {pnl_ratio:.2%} <= {self.single_stop_loss:.2%}")

        return stop_loss_symbols

    def calculate_position_scale(self, current_value: float,
                                peak_value: float,
                                market_volatility: float = None) -> float:
        """
        根据回撤和市场波动率计算目标仓位

        Args:
            current_value: 当前总资产
            peak_value: 峰值资产
            market_volatility: 市场波动率（可选）

        Returns:
            目标仓位比例 (0-1)
        """
        # 计算当前回撤
        drawdown = (current_value - peak_value) / peak_value

        # 基础仓位
        base_position = self.max_position

        # 根据回撤调整仓位
        if drawdown <= self.portfolio_stop_loss:
            # 触发组合止损，降低到最小仓位
            position = self.min_position
            logging.warning(f"组合回撤{drawdown:.2%}，降低仓位至{position:.0%}")
        elif drawdown < self.portfolio_stop_loss / 2:
            # 回撤较大但未触发止损，线性降低仓位
            # 例如：回撤-10%时，仓位70%
            ratio = 1 - abs(drawdown) / abs(self.portfolio_stop_loss)
            position = self.min_position + (base_position - self.min_position) * ratio
            logging.info(f"组合回撤{drawdown:.2%}，调整仓位至{position:.0%}")
        else:
            # 回撤较小，保持高仓位
            position = base_position

        # 根据市场波动率调整（可选）
        if market_volatility is not None:
            if market_volatility > 0.03:  # 高波动
                position *= 0.8
                logging.info(f"高市场波动率{market_volatility:.2%}，降低仓位至{position:.0%}")

        return max(self.min_position, min(self.max_position, position))

    def select_stocks(self, predictions: pd.DataFrame,
                     current_holdings: List[str] = None) -> Tuple[List[str], Dict[str, float]]:
        """
        根据预测选股并分配权重

        Args:
            predictions: 预测结果 DataFrame，包含 'symbol' 和 'predicted_return'
            current_holdings: 当前持仓股票列表（优先保留）

        Returns:
            (选中的股票列表, 权重字典)
        """
        # 按预测收益排序
        predictions = predictions.sort_values('predicted_return', ascending=False)

        # 选择Top N
        top_stocks = predictions.head(self.top_n)['symbol'].tolist()

        # 等权重分配（简单策略）
        equal_weight = 1.0 / len(top_stocks)
        weights = {symbol: equal_weight for symbol in top_stocks}

        # 确保单股权重不超过上限
        for symbol in weights:
            if weights[symbol] > self.max_single_weight:
                weights[symbol] = self.max_single_weight

        # 归一化权重
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        return top_stocks, weights

    def calculate_target_shares(self, total_cash: float,
                                position_scale: float,
                                weights: Dict[str, float],
                                prices: Dict[str, float],
                                lot_size: int = 100) -> Dict[str, int]:
        """
        计算目标持仓股数

        Args:
            total_cash: 可用资金
            position_scale: 目标仓位比例
            weights: 股票权重字典
            prices: 股票价格字典
            lot_size: 交易单位（A股为100股）

        Returns:
            目标持仓 {symbol: shares}
        """
        target_investment = total_cash * position_scale
        target_shares = {}

        for symbol, weight in weights.items():
            if symbol not in prices or prices[symbol] <= 0:
                continue

            # 计算该股票的目标金额
            symbol_amount = target_investment * weight

            # 计算股数（取整到交易单位）
            shares = int(symbol_amount / prices[symbol] / lot_size) * lot_size

            if shares >= lot_size:
                target_shares[symbol] = shares

        return target_shares


def backtest_with_risk_control(trader, start_date: str, end_date: str,
                               risk_config: Dict = None) -> Dict:
    """
    带风险控制的回测

    Args:
        trader: SimulationTrader实例
        start_date: 开始日期
        end_date: 结束日期
        risk_config: 风险控制配置

    Returns:
        回测结果字典
    """
    if risk_config is None:
        risk_config = {
            'single_stock_stop_loss': -0.10,  # 单股-10%止损
            'portfolio_stop_loss': -0.15,      # 组合-15%止损
            'max_position': 0.80,              # 最大80%仓位
            'min_position': 0.60,              # 最小60%仓位
            'max_single_weight': 0.15,         # 单股最大15%
            'top_n': 8                         # 持仓8只
        }

    risk_controller = RiskController(risk_config)

    # 获取股票池
    stocks = trader._get_stock_pool(limit=50)
    symbols = [s['symbol'] for s in stocks]

    # 获取历史数据
    hist_data = trader._get_historical_data(symbols, start_date, end_date)

    if len(hist_data) == 0:
        logging.error("无历史数据")
        return {}

    # 计算因子
    factors_df = trader.factor_calc.calculate_factors(hist_data)
    factors_df = factors_df.sort_values(['symbol', 'date'])
    factors_df['future_return'] = factors_df.groupby('symbol')['close'].pct_change(5).shift(-5)

    valid_data = factors_df.dropna(subset=['future_return'])

    # 模拟交易
    dates = sorted(valid_data['date'].unique())

    # 初始化
    initial_capital = 100000.0
    cash = initial_capital
    portfolio = {}  # {symbol: {'shares': X, 'avg_price': Y}}
    peak_value = initial_capital

    daily_values = []
    daily_returns = []
    trades = []

    for i in range(len(dates) - 5):
        date = dates[i]
        day_data = valid_data[valid_data['date'] == date].copy()

        if len(day_data) < 5:
            continue

        # 预测
        X = day_data[trader.valid_factors].fillna(0)
        predictions = trader.model.predict(X)
        day_data['prediction'] = predictions

        # 当前价格
        current_prices = dict(zip(day_data['symbol'], day_data['close']))

        # 1. 检查单股止损
        stop_loss_symbols = risk_controller.check_single_stock_stop_loss(
            portfolio, current_prices
        )

        # 卖出止损股票
        for symbol in stop_loss_symbols:
            if symbol in portfolio:
                pos = portfolio[symbol]
                sell_price = current_prices[symbol]
                sell_amount = pos['shares'] * sell_price * 0.9985  # 扣除手续费
                cash += sell_amount

                pnl = (sell_price - pos['avg_price']) / pos['avg_price']
                trades.append({
                    'date': date,
                    'symbol': symbol,
                    'action': 'STOP_LOSS',
                    'shares': pos['shares'],
                    'price': sell_price,
                    'pnl': pnl
                })

                del portfolio[symbol]

        # 计算当前总资产
        portfolio_value = sum(
            pos['shares'] * current_prices.get(symbol, pos['avg_price'])
            for symbol, pos in portfolio.items()
            if symbol in current_prices
        )
        total_value = cash + portfolio_value

        # 更新峰值
        if total_value > peak_value:
            peak_value = total_value

        # 2. 计算目标仓位
        position_scale = risk_controller.calculate_position_scale(
            total_value, peak_value
        )

        # 3. 选股和权重分配
        top_stocks, weights = risk_controller.select_stocks(
            day_data[['symbol', 'prediction']].rename(columns={'prediction': 'predicted_return'}),
            list(portfolio.keys())
        )

        # 4. 计算目标持仓
        target_shares = risk_controller.calculate_target_shares(
            total_value, position_scale, weights, current_prices
        )

        # 5. 执行调仓
        # 卖出不在目标中的股票
        for symbol in list(portfolio.keys()):
            if symbol not in target_shares:
                pos = portfolio[symbol]
                sell_price = current_prices.get(symbol, pos['avg_price'])
                sell_amount = pos['shares'] * sell_price * 0.9985
                cash += sell_amount

                pnl = (sell_price - pos['avg_price']) / pos['avg_price']
                trades.append({
                    'date': date,
                    'symbol': symbol,
                    'action': 'SELL',
                    'shares': pos['shares'],
                    'price': sell_price,
                    'pnl': pnl
                })

                del portfolio[symbol]

        # 买入/调整目标股票
        for symbol, target_shr in target_shares.items():
            current_shr = portfolio.get(symbol, {}).get('shares', 0)
            diff = target_shr - current_shr

            if diff > 0 and symbol in current_prices:
                # 买入
                buy_price = current_prices[symbol]
                buy_cost = diff * buy_price * 1.0015  # 含手续费

                if buy_cost <= cash:
                    cash -= buy_cost

                    if symbol in portfolio:
                        # 加仓：计算新的平均成本
                        old_cost = portfolio[symbol]['shares'] * portfolio[symbol]['avg_price']
                        new_cost = old_cost + buy_cost
                        new_shares = portfolio[symbol]['shares'] + diff
                        portfolio[symbol] = {
                            'shares': new_shares,
                            'avg_price': new_cost / new_shares
                        }
                    else:
                        # 新建仓
                        portfolio[symbol] = {
                            'shares': diff,
                            'avg_price': buy_price * 1.0015
                        }

                    trades.append({
                        'date': date,
                        'symbol': symbol,
                        'action': 'BUY',
                        'shares': diff,
                        'price': buy_price
                    })

        # 记录每日净值
        portfolio_value = sum(
            pos['shares'] * current_prices.get(symbol, pos['avg_price'])
            for symbol, pos in portfolio.items()
            if symbol in current_prices
        )
        total_value = cash + portfolio_value

        daily_values.append({
            'date': date,
            'total_value': total_value,
            'cash': cash,
            'portfolio_value': portfolio_value,
            'position': len(portfolio)
        })

        if len(daily_values) > 1:
            daily_return = (total_value - daily_values[-2]['total_value']) / daily_values[-2]['total_value']
            daily_returns.append(daily_return)

    # 计算回测指标
    if len(daily_values) == 0:
        return {}

    daily_values_df = pd.DataFrame(daily_values)
    daily_returns = pd.Series(daily_returns)

    final_value = daily_values_df.iloc[-1]['total_value']
    cumulative_return = (final_value - initial_capital) / initial_capital

    # 年化收益
    days = len(daily_values) * 5
    annual_return = (1 + cumulative_return) ** (252 / days) - 1

    # 夏普比率
    excess_return = daily_returns.mean() - 0.02/252
    sharpe = excess_return / daily_returns.std() * np.sqrt(252) if daily_returns.std() > 0 else 0

    # 最大回撤
    cumsum = daily_values_df['total_value']
    running_max = cumsum.expanding().max()
    drawdown = (cumsum - running_max) / running_max
    max_drawdown = drawdown.min()

    # 胜率
    win_rate = (daily_returns > 0).mean() if len(daily_returns) > 0 else 0

    return {
        'initial_capital': initial_capital,
        'final_value': final_value,
        'cumulative_return': cumulative_return,
        'annual_return': annual_return,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'total_trades': len(trades),
        'avg_position': daily_values_df['position'].mean(),
        'daily_values': daily_values_df,
        'trades': trades
    }

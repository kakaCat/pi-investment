"""回测引擎"""

from statistics import fmean, pstdev

import pandas as pd

from backtesting.risk_manager import RiskManager


class BacktestEngine:
    def __init__(self, initial_capital: float = 100000, risk_manager: RiskManager | None = None):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0
        self.buy_price = 0
        self.trades = []
        self.risk_manager = risk_manager or RiskManager()

    def _sell(self, date, price: float, action: str):
        shares = self.position
        self.capital += shares * price
        self.trades.append(
            {
                'date': date,
                'action': action,
                'price': price,
                'shares': shares,
            }
        )
        self.position = 0
        self.buy_price = 0

    def _reset(self):
        self.capital = self.initial_capital
        self.position = 0
        self.buy_price = 0
        self.trades = []

    def run(self, df: pd.DataFrame, signals: pd.Series):
        self._reset()
        equity_curve = []

        for i in range(len(df)):
            current_price = df['close'].iloc[i]
            current_date = df['date'].iloc[i]
            exited_position = False

            if self.position > 0:
                if self.risk_manager.should_stop_loss(self.buy_price, current_price):
                    self._sell(current_date, current_price, 'sell_stop_loss')
                    exited_position = True

                elif self.risk_manager.should_take_profit(self.buy_price, current_price):
                    self._sell(current_date, current_price, 'sell_take_profit')
                    exited_position = True

            if not exited_position and signals.iloc[i] == 1 and self.position == 0:
                shares = self.risk_manager.calculate_position_size(self.capital, current_price)
                cost = shares * current_price
                if shares <= 0 or cost > self.capital:
                    equity_curve.append(self.capital + self.position * current_price)
                    continue

                self.position = shares
                self.buy_price = current_price
                self.trades.append(
                    {
                        'date': current_date,
                        'action': 'buy',
                        'price': current_price,
                        'shares': shares,
                    }
                )
                self.capital -= cost
            elif not exited_position and self.position > 0 and i == len(df) - 1:
                self._sell(current_date, current_price, 'sell')

            equity_curve.append(self.capital + self.position * current_price)

        final_value = self.capital + self.position * df['close'].iloc[-1]
        trade_returns = self._calculate_trade_returns()

        return {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'return': (final_value / self.initial_capital - 1) * 100,
            'trades': len(self.trades),
            'win_rate': self._calculate_win_rate(trade_returns),
            'max_drawdown': self._calculate_max_drawdown(equity_curve),
            'sharpe_ratio': self._calculate_sharpe_ratio(trade_returns),
        }

    def _calculate_trade_returns(self):
        returns = []
        buy_price = None

        for trade in self.trades:
            if trade['action'] == 'buy':
                buy_price = trade['price']
            elif trade['action'].startswith('sell') and buy_price:
                returns.append((trade['price'] - buy_price) / buy_price)
                buy_price = None

        return returns

    def _calculate_win_rate(self, trade_returns):
        if not trade_returns:
            return 0.0
        winning_trades = [ret for ret in trade_returns if ret > 0]
        return len(winning_trades) / len(trade_returns) * 100

    def _calculate_max_drawdown(self, equity_curve):
        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0

        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return max_dd * 100

    def _calculate_sharpe_ratio(self, trade_returns):
        if not trade_returns:
            return 0.0

        std = pstdev(trade_returns)
        if std == 0:
            return 0.0

        return fmean(trade_returns) / std

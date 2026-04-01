"""回测引擎"""

from __future__ import annotations

from statistics import fmean, pstdev
from typing import TYPE_CHECKING

import pandas as pd

from backtesting.risk_manager import RiskManager

if TYPE_CHECKING:
    from strategies.base import BaseStrategy


class BacktestEngine:
    REQUIRED_COLUMNS = ('date', 'close', 'volume')

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

    def _prepare_inputs(self, df: pd.DataFrame, signals: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
        missing_columns = [column for column in self.REQUIRED_COLUMNS if column not in df.columns]
        if missing_columns:
            missing = ', '.join(missing_columns)
            raise ValueError(f'Backtest data missing required columns: {missing}')

        market_data = df.loc[:, list(self.REQUIRED_COLUMNS)].copy()
        market_data['date'] = pd.to_datetime(market_data['date'], errors='coerce')
        market_data['close'] = pd.to_numeric(market_data['close'], errors='coerce')
        market_data['volume'] = pd.to_numeric(market_data['volume'], errors='coerce')
        market_data = market_data.replace([float('inf'), float('-inf')], pd.NA)

        if market_data.isna().any().any():
            raise ValueError('Backtest data contains invalid date/close/volume values')

        market_data = market_data.sort_values('date').drop_duplicates(subset=['date'], keep='last')
        signal_series = pd.Series(signals, copy=True)
        signal_values = pd.to_numeric(signal_series, errors='coerce')
        if signal_values.isna().any():
            raise ValueError('Signals contain invalid values')

        if len(signal_values) == len(market_data) and isinstance(signal_values.index, pd.RangeIndex):
            return market_data.reset_index(drop=True), signal_values.reset_index(drop=True)

        signal_dates = pd.to_datetime(signal_series.index, errors='coerce')
        if signal_dates.isna().any():
            raise ValueError('Signals must match market data length or use a valid date index')

        signal_frame = pd.DataFrame({'date': signal_dates, 'signal': signal_values.to_numpy()})
        signal_frame = signal_frame.sort_values('date').drop_duplicates(subset=['date'], keep='last')

        aligned = market_data.merge(signal_frame, on='date', how='inner').reset_index(drop=True)
        if aligned.empty:
            raise ValueError('Signals do not align with market data')

        return aligned[list(self.REQUIRED_COLUMNS)], aligned['signal']

    def run(
        self,
        df: pd.DataFrame,
        signals: pd.Series | None = None,
        strategy: BaseStrategy | None = None,
    ):
        self._reset()
        if strategy is not None:
            if signals is not None:
                raise ValueError('Pass either signals or strategy, not both')
            signals = strategy.generate_signals(df.copy())
        if signals is None:
            raise ValueError('Backtest requires signals or a strategy')

        df, signals = self._prepare_inputs(df, signals)
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

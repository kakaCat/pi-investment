"""
Backtesting engine for strategy validation.

Usage:
    python -m python.strategies.backtest --strategy ma_cross --symbol 000001.SZ --start 2015-01-01 --end 2025-12-31
"""
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, List
import json

from .classic.ma_cross import MACrossStrategy
from .classic.rsi_reversal import RSIReversalStrategy
from .classic.bollinger_breakout import BollingerBreakoutStrategy
from .utils import generate_backtest_report
from quantsys.data.db import Database


class BacktestEngine:
    """Backtesting engine for strategy validation."""

    def __init__(
        self,
        strategy,
        initial_capital: float = 100000.0,
        commission: float = 0.0003,  # 0.03% commission
        slippage: float = 0.0001  # 0.01% slippage
    ):
        """
        Initialize backtest engine.

        Args:
            strategy: Strategy instance
            initial_capital: Initial capital
            commission: Commission rate
            slippage: Slippage rate
        """
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.equity_curve = []
        self.trades = []

    def load_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Load historical data from the configured quant database.

        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV data
        """
        try:
            database = Database()
            try:
                df = database.get_klines_between(symbol, start_date, end_date)
            finally:
                database.close()

            if df.empty:
                print(f"No data found for {symbol} between {start_date} and {end_date}")
                return pd.DataFrame()

            # Handle different date formats (YYYYMMDD or YYYY-MM-DD)
            df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
            return df

        except Exception as e:
            print(f"Error loading data: {e}")
            return pd.DataFrame()

    def run(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Run backtest on historical data.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            Backtest results dictionary
        """
        if data.empty:
            return {'error': 'No data provided'}

        # Reset strategy
        self.strategy.reset()
        self.capital = self.initial_capital
        self.equity_curve = [self.initial_capital]
        self.trades = []

        # Process each bar sequentially
        for idx in range(len(data)):
            # Get current and historical data up to this point
            current_data = data.iloc[:idx+1].copy()
            row = data.iloc[idx]
            bar = row.to_dict()

            # Calculate signals on current data window
            signals = self.strategy.calculate_signals(current_data)

            # Get signals for current bar only
            bar_signals = [s for s in signals if s.timestamp == row['timestamp']]

            for signal in bar_signals:
                if signal.action == 'buy':
                    self._execute_buy(signal, bar)
                elif signal.action == 'sell':
                    self._execute_sell(signal, bar)

            # Update equity curve
            equity = self._calculate_equity(bar['close'])
            self.equity_curve.append(equity)

        # Generate report
        equity_series = pd.Series(self.equity_curve)
        report = generate_backtest_report(
            self.strategy.trades,
            equity_series,
            self.initial_capital
        )

        report['strategy_info'] = self.strategy.get_strategy_info()
        report['final_capital'] = self.capital
        report['equity_curve'] = self.equity_curve

        return report

    def _execute_buy(self, signal, bar):
        """Execute buy order."""
        symbol = signal.symbol
        price = signal.price * (1 + self.slippage)  # Apply slippage

        # Reserve 0.1% for commission to avoid insufficient capital
        # Use 99.9% of capital for buying shares
        available_capital = self.capital * 0.999
        max_shares = int(available_capital / price)

        if max_shares <= 0:
            return

        # Calculate actual cost with commission
        cost = price * max_shares
        commission_cost = cost * self.commission
        total_cost = cost + commission_cost

        if total_cost > self.capital:
            # Reduce shares if still over budget
            max_shares = int((self.capital * 0.99) / price)
            if max_shares <= 0:
                return
            cost = price * max_shares
            commission_cost = cost * self.commission
            total_cost = cost + commission_cost

        # Create order
        from .base import Order
        order = Order(
            order_id=f"order_{len(self.strategy.orders)}",
            symbol=symbol,
            action='buy',
            quantity=max_shares,
            price=price,
            filled_price=price,
            filled_time=signal.timestamp,
            status='filled'
        )

        # Update capital
        self.capital -= total_cost

        # Update strategy
        self.strategy.on_order_filled(order)
        self.strategy.orders.append(order)

    def _execute_sell(self, signal, bar):
        """Execute sell order."""
        symbol = signal.symbol
        position = self.strategy.get_position(symbol)

        if not position:
            return

        price = signal.price * (1 - self.slippage)  # Apply slippage
        quantity = position.quantity

        # Calculate proceeds
        proceeds = price * quantity
        commission_cost = proceeds * self.commission
        net_proceeds = proceeds - commission_cost

        # Create order
        from .base import Order
        order = Order(
            order_id=f"order_{len(self.strategy.orders)}",
            symbol=symbol,
            action='sell',
            quantity=quantity,
            price=price,
            filled_price=price,
            filled_time=signal.timestamp,
            status='filled'
        )

        # Update capital
        self.capital += net_proceeds

        # Update strategy
        self.strategy.on_order_filled(order)
        self.strategy.orders.append(order)

    def _calculate_equity(self, current_price: float) -> float:
        """Calculate current equity (cash + positions)."""
        equity = self.capital

        for position in self.strategy.positions.values():
            equity += position.quantity * current_price

        return equity


def main():
    """Main entry point for backtesting."""
    parser = argparse.ArgumentParser(description='Backtest trading strategies')
    parser.add_argument('--strategy', type=str, required=True,
                        choices=['ma_cross', 'rsi_reversal', 'bollinger_breakout'],
                        help='Strategy to backtest')
    parser.add_argument('--symbol', type=str, required=True,
                        help='Stock symbol (e.g., 000001.SZ)')
    parser.add_argument('--start', type=str, required=True,
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True,
                        help='End date (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=100000.0,
                        help='Initial capital (default: 100000)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file for results (JSON)')

    args = parser.parse_args()

    # Create strategy
    if args.strategy == 'ma_cross':
        strategy = MACrossStrategy()
    elif args.strategy == 'rsi_reversal':
        strategy = RSIReversalStrategy()
    elif args.strategy == 'bollinger_breakout':
        strategy = BollingerBreakoutStrategy()
    else:
        print(f"Unknown strategy: {args.strategy}")
        sys.exit(1)

    # Create backtest engine
    engine = BacktestEngine(strategy, initial_capital=args.capital)

    # Load data
    print(f"Loading data for {args.symbol} from {args.start} to {args.end}...")
    data = engine.load_data(args.symbol, args.start, args.end)

    if data.empty:
        print("No data loaded. Exiting.")
        sys.exit(1)

    print(f"Loaded {len(data)} bars")

    # Run backtest
    print(f"Running backtest with {args.strategy}...")
    results = engine.run(data)

    # Print results
    print("\n" + "="*60)
    print(f"BACKTEST RESULTS: {strategy.get_strategy_info()['name']}")
    print("="*60)
    print(f"Symbol: {args.symbol}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Initial Capital: ${args.capital:,.2f}")
    print(f"Final Capital: ${results.get('final_capital', 0):,.2f}")
    print(f"\nTotal Return: {results.get('total_return', 0)*100:.2f}%")
    print(f"Total PnL: ${results.get('total_pnl', 0):,.2f}")
    print(f"\nTotal Trades: {results.get('total_trades', 0)}")
    print(f"Winning Trades: {results.get('winning_trades', 0)}")
    print(f"Losing Trades: {results.get('losing_trades', 0)}")
    print(f"Win Rate: {results.get('win_rate', 0)*100:.2f}%")
    print(f"\nProfit Factor: {results.get('profit_factor', 0):.2f}")
    print(f"Expectancy: ${results.get('expectancy', 0):.2f}")
    print(f"\nAvg Win: ${results.get('avg_win', 0):.2f}")
    print(f"Avg Loss: ${results.get('avg_loss', 0):.2f}")
    print(f"Max Win: ${results.get('max_win', 0):.2f}")
    print(f"Max Loss: ${results.get('max_loss', 0):.2f}")
    print(f"\nSharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
    print(f"Sortino Ratio: {results.get('sortino_ratio', 0):.2f}")
    print(f"Calmar Ratio: {results.get('calmar_ratio', 0):.2f}")
    print(f"Max Drawdown: {results.get('max_drawdown', 0)*100:.2f}%")
    print(f"\nAvg Holding Period: {results.get('avg_holding_period', 0):.1f} days")
    print("="*60)

    # Save results
    if args.output:
        # Remove equity_curve for JSON serialization (too large)
        results_copy = results.copy()
        results_copy.pop('equity_curve', None)

        with open(args.output, 'w') as f:
            json.dump(results_copy, f, indent=2, default=str)
        print(f"\nResults saved to {args.output}")


if __name__ == '__main__':
    main()

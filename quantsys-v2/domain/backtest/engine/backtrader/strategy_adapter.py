"""
Backtrader Strategy Adapters
=============================

Adapts existing quantsys-v2 strategies to Backtrader framework.

Two adapter types:
1. IndicatorStrategyAdapter - for df['buy']/df['sell'] strategies
2. SignalStrategyAdapter - for StrategyBase.generate_signal() strategies
"""

import backtrader as bt
import pandas as pd
import numpy as np
from typing import Dict, Any, Callable, Optional
import logging


logger = logging.getLogger(__name__)


class IndicatorStrategyAdapter(bt.Strategy):
    """
    Adapter for indicator-based strategies (df['buy'], df['sell']).
    
    Converts existing strategies that generate buy/sell signals via DataFrame columns
    into Backtrader-compatible strategies.
    
    Original strategy format:
        def my_strategy(df, fast=5, slow=20):
            df['ma_fast'] = df['close'].rolling(fast).mean()
            df['ma_slow'] = df['close'].rolling(slow).mean()
            df['buy'] = df['ma_fast'] > df['ma_slow']
            df['sell'] = df['ma_fast'] < df['ma_slow']
            return df
    
    Usage:
        cerebro.addstrategy(
            IndicatorStrategyAdapter,
            strategy_func=my_strategy,
            strategy_params={'fast': 5, 'slow': 20}
        )
    """
    
    params = (
        ('strategy_func', None),    # Strategy function
        ('strategy_params', {}),     # Strategy parameters
        ('printlog', False),         # Print trade logs
    )
    
    def __init__(self):
        """Initialize adapter."""
        self.order = None
        self.buy_price = None
        self.buy_comm = None
        
        # Validate strategy function
        if self.params.strategy_func is None:
            raise ValueError("strategy_func parameter is required")
    
    def log(self, txt, dt=None):
        """Logging function."""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} {txt}')
    
    def notify_order(self, order):
        """Called when order status changes."""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}, '
                        f'Cost: {order.executed.value:.2f}, '
                        f'Comm: {order.executed.comm:.2f}')
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
            else:
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}, '
                        f'Cost: {order.executed.value:.2f}, '
                        f'Comm: {order.executed.comm:.2f}')
            
            self.bar_executed = len(self)
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        
        self.order = None
    
    def notify_trade(self, trade):
        """Called when a trade is closed."""
        if not trade.isclosed:
            return
        
        self.log(f'OPERATION PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')
    
    def next(self):
        """Called on each bar."""
        # Check if order is pending
        if self.order:
            return
        
        # Get historical data up to current bar
        df = self._get_historical_data()
        
        # Call strategy function to generate signals
        try:
            result_df = self.params.strategy_func(df, **self.params.strategy_params)
        except Exception as e:
            logger.error(f"Strategy function failed: {e}")
            return
        
        # Get current signals (last row)
        current_buy = False
        current_sell = False
        
        if 'buy' in result_df.columns:
            current_buy = bool(result_df['buy'].iloc[-1])
        if 'sell' in result_df.columns:
            current_sell = bool(result_df['sell'].iloc[-1])
        
        # Execute trading logic
        if not self.position:  # Not in position
            if current_buy:
                self.log(f'BUY CREATE, {self.datas[0].close[0]:.2f}')
                self.order = self.buy()
        else:  # In position
            if current_sell:
                self.log(f'SELL CREATE, {self.datas[0].close[0]:.2f}')
                self.order = self.sell()
    
    def _get_historical_data(self) -> pd.DataFrame:
        """
        Get all historical data up to current bar.

        Returns:
            DataFrame with OHLCV data
        """
        data = self.datas[0]

        records = []
        # Use negative indexing to access historical bars
        for i in range(len(data)):
            idx = i - len(data)
            records.append({
                'open': data.open[idx],
                'high': data.high[idx],
                'low': data.low[idx],
                'close': data.close[idx],
                'volume': data.volume[idx],
            })

        return pd.DataFrame(records)


class SignalStrategyAdapter(bt.Strategy):
    """
    Adapter for signal-based strategies (StrategyBase.generate_signal()).
    
    Converts existing strategies that use StrategyBase interface into
    Backtrader-compatible strategies.
    
    Original strategy format:
        class MyStrategy(StrategyBase):
            def generate_signal(self, klines, params):
                # ... calculate indicators ...
                return {
                    'action': 'buy' | 'sell' | 'hold',
                    'confidence': 0.0-1.0,
                    'reason': 'explanation'
                }
    
    Usage:
        strategy_obj = MyStrategy()
        cerebro.addstrategy(
            SignalStrategyAdapter,
            strategy_obj=strategy_obj,
            strategy_params={'fast': 5, 'slow': 20}
        )
    """
    
    params = (
        ('strategy_obj', None),      # StrategyBase instance
        ('strategy_params', {}),      # Strategy parameters
        ('printlog', False),          # Print trade logs
    )
    
    def __init__(self):
        """Initialize adapter."""
        self.order = None
        self.buy_price = None
        self.buy_comm = None
        
        # Validate strategy object
        if self.params.strategy_obj is None:
            raise ValueError("strategy_obj parameter is required")
        
        if not hasattr(self.params.strategy_obj, 'generate_signal'):
            raise ValueError("strategy_obj must have generate_signal() method")
    
    def log(self, txt, dt=None):
        """Logging function."""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()} {txt}')
    
    def notify_order(self, order):
        """Called when order status changes."""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY EXECUTED, Price: {order.executed.price:.2f}')
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
            else:
                self.log(f'SELL EXECUTED, Price: {order.executed.price:.2f}')
            
            self.bar_executed = len(self)
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        
        self.order = None
    
    def notify_trade(self, trade):
        """Called when a trade is closed."""
        if not trade.isclosed:
            return
        
        self.log(f'OPERATION PROFIT, GROSS: {trade.pnl:.2f}, NET: {trade.pnlcomm:.2f}')
    
    def next(self):
        """Called on each bar."""
        # Check if order is pending
        if self.order:
            return
        
        # Convert to klines format
        klines = self._get_klines()
        
        # Call strategy to generate signal
        try:
            signal = self.params.strategy_obj.generate_signal(
                klines, 
                self.params.strategy_params
            )
        except Exception as e:
            logger.error(f"Strategy generate_signal() failed: {e}")
            return
        
        # Validate signal format
        if not isinstance(signal, dict) or 'action' not in signal:
            logger.error(f"Invalid signal format: {signal}")
            return
        
        action = signal.get('action', 'hold')
        confidence = signal.get('confidence', 0.0)
        reason = signal.get('reason', '')
        
        # Execute trading logic
        if not self.position:  # Not in position
            if action == 'buy':
                self.log(f'BUY CREATE, {self.datas[0].close[0]:.2f}, '
                        f'Confidence: {confidence:.2f}, Reason: {reason}')
                self.order = self.buy()
        else:  # In position
            if action == 'sell':
                self.log(f'SELL CREATE, {self.datas[0].close[0]:.2f}, '
                        f'Confidence: {confidence:.2f}, Reason: {reason}')
                self.order = self.sell()
    
    def _get_klines(self) -> list:
        """
        Convert Backtrader data to klines format.

        Returns:
            List of kline dicts (quantsys-v2 format)
        """
        data = self.datas[0]
        klines = []

        for i in range(len(data)):
            # Use negative indexing to access historical bars
            idx = i - len(data)
            klines.append({
                'trade_date': data.datetime.date(idx),
                'open': float(data.open[idx]),
                'high': float(data.high[idx]),
                'low': float(data.low[idx]),
                'close': float(data.close[idx]),
                'volume': float(data.volume[idx]),
            })

        return klines

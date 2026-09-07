"""
Backtrader Backtest Engine
===========================

Professional backtest engine using Backtrader framework.

Features:
- Single and multi-stock backtesting
- Parallel execution support
- Flexible commission and slippage models
- Multiple built-in analyzers
- Professional order matching
"""

import backtrader as bt
import pandas as pd
from typing import Dict, List, Any, Callable, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import logging


logger = logging.getLogger(__name__)


class BacktraderEngine:
    """
    Backtrader backtest engine with parallel support.
    
    Provides professional backtesting capabilities:
    - Accurate order matching (market, limit, stop orders)
    - Multiple slippage models
    - Flexible commission structures
    - Built-in performance analyzers
    - Parallel execution for multiple stocks
    
    Example:
        >>> engine = BacktraderEngine(
        ...     initial_cash=100000,
        ...     commission=0.0003,
        ...     slippage_perc=0.0001
        ... )
        >>> result = engine.backtest_single(
        ...     symbol='600000.SH',
        ...     df=df_600000,
        ...     strategy_func=ma_cross_strategy,
        ...     strategy_params={'fast': 5, 'slow': 20}
        ... )
    """
    
    def __init__(
        self,
        initial_cash: float = 100000.0,
        commission: float = 0.0003,          # 0.03% (万三)
        slippage_perc: float = 0.0001,       # 0.01% slippage
        n_workers: int = 8
    ):
        """
        Initialize Backtrader engine.
        
        Args:
            initial_cash: Initial capital
            commission: Commission rate (0.0003 = 0.03% = 万三)
            slippage_perc: Slippage percentage
            n_workers: Number of parallel workers
        """
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage_perc = slippage_perc
        self.n_workers = n_workers
    
    def backtest_single(
        self,
        symbol: str,
        df: pd.DataFrame,
        strategy_func: Callable,
        strategy_params: Dict[str, Any],
        printlog: bool = False
    ) -> Dict[str, Any]:
        """
        Backtest single stock.
        
        Args:
            symbol: Stock symbol
            df: OHLCV DataFrame
            strategy_func: Strategy function (df['buy'], df['sell'] format)
            strategy_params: Strategy parameters
            printlog: Print trade logs
            
        Returns:
            Backtest results dict with metrics
        """
        from domain.backtest.engine.backtrader.data_feed import PandasDataFeed
        from domain.backtest.engine.backtrader.strategy_adapter import IndicatorStrategyAdapter
        
        # Create Cerebro instance
        cerebro = bt.Cerebro()
        
        # Add data
        try:
            data = PandasDataFeed.from_dataframe(df, symbol)
            cerebro.adddata(data)
        except Exception as e:
            logger.error(f"Failed to add data for {symbol}: {e}")
            return {
                'symbol': symbol,
                'error': str(e),
                'success': False
            }
        
        # Add strategy
        cerebro.addstrategy(
            IndicatorStrategyAdapter,
            strategy_func=strategy_func,
            strategy_params=strategy_params,
            printlog=printlog
        )
        
        # Set initial cash
        cerebro.broker.setcash(self.initial_cash)
        
        # Set commission
        cerebro.broker.setcommission(commission=self.commission)
        
        # Set slippage
        cerebro.broker.set_slippage_perc(self.slippage_perc)
        
        # Add analyzers
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        
        # Run backtest
        try:
            initial_value = cerebro.broker.getvalue()
            results = cerebro.run()
            final_value = cerebro.broker.getvalue()
        except Exception as e:
            logger.error(f"Backtest failed for {symbol}: {e}")
            return {
                'symbol': symbol,
                'error': str(e),
                'success': False
            }
        
        # Extract results
        strategy = results[0]
        
        # Get analyzer results
        sharpe_analysis = strategy.analyzers.sharpe.get_analysis()
        returns_analysis = strategy.analyzers.returns.get_analysis()
        drawdown_analysis = strategy.analyzers.drawdown.get_analysis()
        trades_analysis = strategy.analyzers.trades.get_analysis()
        
        return {
            'symbol': symbol,
            'success': True,
            'initial_value': initial_value,
            'final_value': final_value,
            'total_return': (final_value - initial_value) / initial_value,
            'sharpe_ratio': sharpe_analysis.get('sharperatio', None),
            'max_drawdown': drawdown_analysis.get('max', {}).get('drawdown', 0) / 100,  # Convert to decimal
            'max_drawdown_period': drawdown_analysis.get('max', {}).get('len', 0),
            'total_trades': trades_analysis.get('total', {}).get('total', 0),
            'won_trades': trades_analysis.get('won', {}).get('total', 0),
            'lost_trades': trades_analysis.get('lost', {}).get('total', 0),
            'win_rate': self._calculate_win_rate(trades_analysis),
            'average_win': trades_analysis.get('won', {}).get('pnl', {}).get('average', 0),
            'average_loss': trades_analysis.get('lost', {}).get('pnl', {}).get('average', 0),
        }
    
    def backtest_multiple(
        self,
        market_data: Dict[str, pd.DataFrame],
        strategy_func: Callable,
        strategy_params: Dict[str, Any],
        parallel: bool = True,
        printlog: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Backtest multiple stocks (with parallel support).
        
        Args:
            market_data: Dict of {symbol: DataFrame}
            strategy_func: Strategy function
            strategy_params: Strategy parameters
            parallel: Enable parallel execution (default True)
            printlog: Print trade logs
            
        Returns:
            List of backtest results
        """
        symbols = list(market_data.keys())
        
        # Decide execution mode
        if not parallel or len(symbols) < 10:
            # Serial execution for small datasets
            logger.info(f"Running serial backtest for {len(symbols)} stocks")
            results = []
            for symbol, df in market_data.items():
                result = self.backtest_single(
                    symbol, df, strategy_func, strategy_params, printlog
                )
                results.append(result)
            return results
        else:
            # Parallel execution
            logger.info(f"Running parallel backtest for {len(symbols)} stocks "
                       f"with {self.n_workers} workers")
            
            with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
                # Submit all tasks
                future_to_symbol = {}
                for symbol, df in market_data.items():
                    future = executor.submit(
                        self.backtest_single,
                        symbol, df, strategy_func, strategy_params, printlog
                    )
                    future_to_symbol[future] = symbol
                
                # Collect results
                results = []
                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Backtest failed for {symbol}: {e}")
                        results.append({
                            'symbol': symbol,
                            'error': str(e),
                            'success': False
                        })
                
                return results
    
    def backtest_with_strategy_obj(
        self,
        symbol: str,
        klines: list,
        strategy_obj,
        strategy_params: Dict[str, Any],
        printlog: bool = False
    ) -> Dict[str, Any]:
        """
        Backtest with StrategyBase object.
        
        Args:
            symbol: Stock symbol
            klines: List of kline dicts
            strategy_obj: StrategyBase instance
            strategy_params: Strategy parameters
            printlog: Print trade logs
            
        Returns:
            Backtest results
        """
        from domain.backtest.engine.backtrader.data_feed import PandasDataFeed
        from domain.backtest.engine.backtrader.strategy_adapter import SignalStrategyAdapter
        
        # Convert klines to DataFrame
        df = pd.DataFrame(klines)
        
        # Create Cerebro instance
        cerebro = bt.Cerebro()
        
        # Add data
        try:
            data = PandasDataFeed.from_dataframe(df, symbol)
            cerebro.adddata(data)
        except Exception as e:
            logger.error(f"Failed to add data for {symbol}: {e}")
            return {
                'symbol': symbol,
                'error': str(e),
                'success': False
            }
        
        # Add strategy
        cerebro.addstrategy(
            SignalStrategyAdapter,
            strategy_obj=strategy_obj,
            strategy_params=strategy_params,
            printlog=printlog
        )
        
        # Set broker parameters
        cerebro.broker.setcash(self.initial_cash)
        cerebro.broker.setcommission(commission=self.commission)
        cerebro.broker.set_slippage_perc(self.slippage_perc)
        
        # Add analyzers
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        
        # Run backtest
        try:
            initial_value = cerebro.broker.getvalue()
            results = cerebro.run()
            final_value = cerebro.broker.getvalue()
        except Exception as e:
            logger.error(f"Backtest failed for {symbol}: {e}")
            return {
                'symbol': symbol,
                'error': str(e),
                'success': False
            }
        
        # Extract results (same as backtest_single)
        strategy = results[0]
        sharpe_analysis = strategy.analyzers.sharpe.get_analysis()
        drawdown_analysis = strategy.analyzers.drawdown.get_analysis()
        trades_analysis = strategy.analyzers.trades.get_analysis()
        
        return {
            'symbol': symbol,
            'success': True,
            'initial_value': initial_value,
            'final_value': final_value,
            'total_return': (final_value - initial_value) / initial_value,
            'sharpe_ratio': sharpe_analysis.get('sharperatio', None),
            'max_drawdown': drawdown_analysis.get('max', {}).get('drawdown', 0) / 100,
            'total_trades': trades_analysis.get('total', {}).get('total', 0),
            'won_trades': trades_analysis.get('won', {}).get('total', 0),
            'lost_trades': trades_analysis.get('lost', {}).get('total', 0),
            'win_rate': self._calculate_win_rate(trades_analysis),
        }
    
    @staticmethod
    def _calculate_win_rate(trades_analysis: dict) -> float:
        """Calculate win rate from trade analysis."""
        total = trades_analysis.get('total', {}).get('total', 0)
        if total == 0:
            return 0.0
        
        won = trades_analysis.get('won', {}).get('total', 0)
        return won / total

#!/usr/bin/env python3
"""
智能并行回测引擎

根据数据规模自动选择最优回测策略：
- <500股票：串行执行
- 500-2000股票：共享内存并行
- >2000股票：共享内存并行（增加workers）
"""

import sys
import time
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing import shared_memory
import logging


logger = logging.getLogger(__name__)


class SmartBacktestEngine:
    """智能回测引擎 - 自动选择最优并行策略

    支持两种回测引擎：
    1. 原生引擎（快速，简化）
    2. Backtrader 引擎（专业，精确）
    """

    def __init__(
        self,
        n_workers: int = 8,
        auto_tune: bool = True,
        use_backtrader: bool = False,
        initial_cash: float = 100000.0,
        commission: float = 0.0003,
        slippage_perc: float = 0.0001
    ):
        """
        Args:
            n_workers: 并行worker数量
            auto_tune: 是否自动调优（基于小样本测试）
            use_backtrader: 是否使用 Backtrader 引擎（默认 False）
            initial_cash: 初始资金（仅 Backtrader）
            commission: 佣金率（仅 Backtrader）
            slippage_perc: 滑点百分比（仅 Backtrader）
        """
        self.n_workers = n_workers
        self.auto_tune = auto_tune
        self.performance_cache = {}  # 缓存性能数据
        self.use_backtrader = use_backtrader

        # 创建 Backtrader 引擎（如果启用）
        if self.use_backtrader:
            from domain.backtest.engine.backtrader.backtrader_engine import BacktraderEngine
            self.bt_engine = BacktraderEngine(
                initial_cash=initial_cash,
                commission=commission,
                slippage_perc=slippage_perc,
                n_workers=n_workers
            )
            logger.info("Using Backtrader engine for professional backtesting")

    def backtest(
        self,
        market_data: Dict[str, pd.DataFrame],
        strategy_func,
        strategy_params: Dict,
        method: str = 'auto'
    ) -> List[Dict]:
        """
        智能回测

        Args:
            market_data: 市场数据 {symbol: DataFrame}
            strategy_func: 策略函数
            strategy_params: 策略参数
            method: 'auto', 'serial', 'parallel_shared', 'parallel_threaded'

        Returns:
            回测结果列表
        """
        # 如果启用 Backtrader，使用 Backtrader 引擎
        if self.use_backtrader:
            logger.info(f"Running backtest with Backtrader engine for {len(market_data)} stocks")
            return self.bt_engine.backtest_multiple(
                market_data=market_data,
                strategy_func=strategy_func,
                strategy_params=strategy_params,
                parallel=(method != 'serial')
            )

        # 否则使用原生引擎
        n_stocks = len(market_data)

        # 自动选择方法
        if method == 'auto':
            method = self._choose_method(n_stocks)
            logger.info(f"Auto-selected method: {method} for {n_stocks} stocks")

        # 执行回测
        start_time = time.perf_counter()

        if method == 'serial':
            results = self._backtest_serial(market_data, strategy_func, strategy_params)
        elif method == 'parallel_shared':
            results = self._backtest_parallel_shared(market_data, strategy_func, strategy_params)
        elif method == 'parallel_threaded':
            results = self._backtest_parallel_threaded(market_data, strategy_func, strategy_params)
        else:
            raise ValueError(f"Unknown method: {method}")

        elapsed = time.perf_counter() - start_time

        logger.info(f"Backtest completed: {n_stocks} stocks in {elapsed:.3f}s "
                   f"({n_stocks/elapsed:.1f} stocks/sec)")

        return results

    def _choose_method(self, n_stocks: int) -> str:
        """根据股票数量选择最优方法"""
        if n_stocks < 500:
            return 'serial'
        elif n_stocks < 2000:
            return 'parallel_shared'
        else:
            # 大规模场景，可以考虑增加workers
            return 'parallel_shared'

    def _backtest_serial(
        self,
        market_data: Dict[str, pd.DataFrame],
        strategy_func,
        strategy_params: Dict
    ) -> List[Dict]:
        """串行回测"""
        results = []

        for symbol, df in market_data.items():
            result = self._backtest_single_stock(symbol, df, strategy_func, strategy_params)
            results.append(result)

        return results

    def _backtest_parallel_threaded(
        self,
        market_data: Dict[str, pd.DataFrame],
        strategy_func,
        strategy_params: Dict
    ) -> List[Dict]:
        """线程池并行回测"""
        with ThreadPoolExecutor(max_workers=self.n_workers) as executor:
            futures = []

            for symbol, df in market_data.items():
                future = executor.submit(
                    self._backtest_single_stock,
                    symbol, df, strategy_func, strategy_params
                )
                futures.append(future)

            results = [f.result() for f in futures]

        return results

    def _backtest_parallel_shared(
        self,
        market_data: Dict[str, pd.DataFrame],
        strategy_func,
        strategy_params: Dict
    ) -> List[Dict]:
        """共享内存并行回测"""
        # 准备共享内存
        shm, metadata = self._prepare_shared_memory(market_data)

        try:
            # 并行处理
            with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
                futures = []

                for i in range(len(metadata['symbols'])):
                    future = executor.submit(
                        _backtest_single_stock_shared,
                        i, metadata, strategy_func, strategy_params
                    )
                    futures.append(future)

                results = [f.result() for f in futures]

            return results

        finally:
            # 清理共享内存
            shm.close()
            shm.unlink()

    def _prepare_shared_memory(
        self,
        market_data: Dict[str, pd.DataFrame]
    ) -> Tuple[shared_memory.SharedMemory, Dict]:
        """准备共享内存"""
        symbols = list(market_data.keys())
        n_stocks = len(symbols)
        n_days = len(next(iter(market_data.values())))

        # 创建共享数组：[n_stocks, n_days, 5] (open, high, low, close, volume)
        shape = (n_stocks, n_days, 5)
        dtype = np.float64
        nbytes = int(np.prod(shape) * np.dtype(dtype).itemsize)

        shm = shared_memory.SharedMemory(create=True, size=nbytes)
        shared_array = np.ndarray(shape, dtype=dtype, buffer=shm.buf)

        # 填充数据
        for i, symbol in enumerate(symbols):
            df = market_data[symbol]
            shared_array[i, :, 0] = df['open'].values
            shared_array[i, :, 1] = df['high'].values
            shared_array[i, :, 2] = df['low'].values
            shared_array[i, :, 3] = df['close'].values
            shared_array[i, :, 4] = df['volume'].values

        # 返回共享内存和元数据
        metadata = {
            'shm_name': shm.name,
            'shape': shape,
            'dtype': 'float64',
            'symbols': symbols
        }

        return shm, metadata

    def _backtest_single_stock(
        self,
        symbol: str,
        df: pd.DataFrame,
        strategy_func,
        strategy_params: Dict
    ) -> Dict:
        """回测单只股票"""
        result_df = strategy_func(df, **strategy_params)

        # 计算指标
        total_return = (1 + result_df['strategy_returns'].fillna(0)).prod() - 1
        sharpe_ratio = (
            result_df['strategy_returns'].mean() /
            (result_df['strategy_returns'].std() + 1e-10) *
            np.sqrt(252)
        )

        return {
            'symbol': symbol,
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'n_trades': (result_df['signal'].diff() != 0).sum()
        }

    def benchmark(
        self,
        market_data: Dict[str, pd.DataFrame],
        strategy_func,
        strategy_params: Dict,
        methods: Optional[List[str]] = None
    ) -> Dict:
        """
        基准测试不同方法

        Args:
            market_data: 市场数据
            strategy_func: 策略函数
            strategy_params: 策略参数
            methods: 要测试的方法列表，None表示测试所有

        Returns:
            性能对比结果
        """
        if methods is None:
            methods = ['serial', 'parallel_threaded', 'parallel_shared']

        results = {}

        for method in methods:
            logger.info(f"Benchmarking method: {method}")

            try:
                start = time.perf_counter()
                _ = self.backtest(market_data, strategy_func, strategy_params, method=method)
                elapsed = time.perf_counter() - start

                results[method] = {
                    'time': elapsed,
                    'throughput': len(market_data) / elapsed
                }

                logger.info(f"  {method}: {elapsed:.3f}s ({results[method]['throughput']:.1f} stocks/sec)")

            except Exception as e:
                logger.error(f"  {method} failed: {e}")
                results[method] = {'error': str(e)}

        # 计算加速比
        if 'serial' in results and 'time' in results['serial']:
            serial_time = results['serial']['time']

            for method, result in results.items():
                if 'time' in result:
                    result['speedup'] = serial_time / result['time']

        return results


# 全局函数（用于multiprocessing）
def _backtest_single_stock_shared(
    stock_idx: int,
    metadata: Dict,
    strategy_func,
    strategy_params: Dict
) -> Dict:
    """使用共享内存回测单只股票"""
    # 访问共享内存
    shm = shared_memory.SharedMemory(name=metadata['shm_name'])
    shape = metadata['shape']
    dtype = np.dtype(metadata['dtype'])
    shared_array = np.ndarray(shape, dtype=dtype, buffer=shm.buf)

    # 提取该股票的数据
    symbol = metadata['symbols'][stock_idx]
    stock_data = shared_array[stock_idx]

    # 构建DataFrame
    df = pd.DataFrame({
        'date': pd.date_range('2023-01-01', periods=shape[1], freq='D'),
        'open': stock_data[:, 0],
        'high': stock_data[:, 1],
        'low': stock_data[:, 2],
        'close': stock_data[:, 3],
        'volume': stock_data[:, 4]
    })

    # 回测
    result_df = strategy_func(df, **strategy_params)

    # 计算指标
    total_return = (1 + result_df['strategy_returns'].fillna(0)).prod() - 1
    sharpe_ratio = (
        result_df['strategy_returns'].mean() /
        (result_df['strategy_returns'].std() + 1e-10) *
        np.sqrt(252)
    )

    result = {
        'symbol': symbol,
        'total_return': total_return,
        'sharpe_ratio': sharpe_ratio,
        'n_trades': (result_df['signal'].diff() != 0).sum()
    }

    shm.close()
    return result


# ============================================================================
# 示例策略
# ============================================================================

def simple_ma_strategy(df: pd.DataFrame, fast: int = 5, slow: int = 20) -> pd.DataFrame:
    """简单移动平均策略"""
    df = df.copy()

    # 计算移动平均
    df['ma_fast'] = df['close'].rolling(fast).mean()
    df['ma_slow'] = df['close'].rolling(slow).mean()

    # 生成信号
    df['signal'] = 0
    df.loc[df['ma_fast'] > df['ma_slow'], 'signal'] = 1
    df.loc[df['ma_fast'] < df['ma_slow'], 'signal'] = -1

    # 计算收益
    df['returns'] = df['close'].pct_change()
    df['strategy_returns'] = df['signal'].shift(1) * df['returns']

    return df


# ============================================================================
# 使用示例
# ============================================================================

def main():
    """使用示例"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    # 生成测试数据
    print("生成测试数据...")
    np.random.seed(42)
    market_data = {}

    n_stocks = 1000
    n_days = 252

    for i in range(n_stocks):
        symbol = f"00{i:04d}.SZ"

        base_price = 10 + np.random.rand() * 90
        returns = np.random.randn(n_days) * 0.02
        close = base_price * np.exp(np.cumsum(returns))

        df = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=n_days, freq='D'),
            'open': close * 0.99,
            'high': close * 1.01,
            'low': close * 0.99,
            'close': close,
            'volume': np.random.randint(1000000, 10000000, n_days)
        })

        market_data[symbol] = df

    print(f"数据规模: {n_stocks} 股票 × {n_days} 天")

    # 创建智能回测引擎
    engine = SmartBacktestEngine(n_workers=8)

    # 策略参数
    strategy_params = {'fast': 5, 'slow': 20}

    # 自动选择最优方法
    print("\n[自动模式]")
    results = engine.backtest(
        market_data,
        simple_ma_strategy,
        strategy_params,
        method='auto'
    )

    print(f"回测完成: {len(results)} 只股票")
    print(f"平均收益: {np.mean([r['total_return'] for r in results]):.2%}")
    print(f"平均夏普: {np.mean([r['sharpe_ratio'] for r in results]):.2f}")

    # 基准测试
    print("\n[基准测试]")
    benchmark_results = engine.benchmark(
        market_data,
        simple_ma_strategy,
        strategy_params
    )

    print("\n性能对比:")
    print(f"{'方法':<20} {'耗时':>10} {'吞吐量':>15} {'加速比':>10}")
    print("-" * 60)

    for method, result in benchmark_results.items():
        if 'time' in result:
            print(f"{method:<20} {result['time']:>9.3f}s "
                  f"{result['throughput']:>10.1f} stocks/s "
                  f"{result.get('speedup', 1.0):>9.2f}x")
        else:
            print(f"{method:<20} ERROR: {result.get('error', 'Unknown')}")


if __name__ == '__main__':
    main()

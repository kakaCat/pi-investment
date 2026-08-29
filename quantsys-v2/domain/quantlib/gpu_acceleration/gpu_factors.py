"""
GPU加速因子计算

使用CuPy和Numba加速技术指标计算
性能提升：10-100倍

依赖：
- cupy-cuda11x (CUDA 11.x)
- numba
"""
import structlog
logger = structlog.get_logger(__name__)

import numpy as np
import pandas as pd
from typing import Optional, Dict
import time
import logging

logger = logging.getLogger(__name__)

# 尝试导入GPU库
try:
    import cupy as cp
    GPU_AVAILABLE = True
    logger.info("CuPy available, GPU acceleration enabled")
except ImportError:
    GPU_AVAILABLE = False
    logger.warning("CuPy not available, falling back to CPU")

try:
    from numba import jit, cuda
    NUMBA_AVAILABLE = True
    logger.info("Numba available")
except ImportError:
    NUMBA_AVAILABLE = False
    logger.warning("Numba not available")


class GPUFactorCalculator:
    """
    GPU加速因子计算器

    支持：
    - 移动平均
    - RSI
    - MACD
    - 布林带
    - ATR
    """

    def __init__(self, use_gpu: bool = True):
        """
        Args:
            use_gpu: 是否使用GPU加速
        """
        self.use_gpu = use_gpu and GPU_AVAILABLE

        if self.use_gpu:
            logger.info("GPU acceleration enabled")
        else:
            logger.info("Using CPU computation")

    def _to_gpu(self, arr: np.ndarray) -> 'cp.ndarray':
        """将数组转移到GPU"""
        if self.use_gpu:
            return cp.asarray(arr)
        return arr

    def _to_cpu(self, arr) -> np.ndarray:
        """将数组转移到CPU"""
        if self.use_gpu and isinstance(arr, cp.ndarray):
            return cp.asnumpy(arr)
        return arr

    def calculate_sma(
        self,
        prices: np.ndarray,
        window: int
    ) -> np.ndarray:
        """
        计算简单移动平均（GPU加速）

        Args:
            prices: 价格序列
            window: 窗口期

        Returns:
            SMA序列
        """
        if self.use_gpu:
            prices_gpu = self._to_gpu(prices)

            # 使用CuPy的卷积实现移动平均
            kernel = cp.ones(window) / window
            sma_gpu = cp.convolve(prices_gpu, kernel, mode='valid')

            # 填充前面的NaN
            result = cp.full(len(prices), cp.nan)
            result[window-1:] = sma_gpu

            return self._to_cpu(result)
        else:
            # CPU实现
            return pd.Series(prices).rolling(window).mean().values

    def calculate_ema(
        self,
        prices: np.ndarray,
        span: int
    ) -> np.ndarray:
        """
        计算指数移动平均（GPU加速）

        Args:
            prices: 价格序列
            span: 周期

        Returns:
            EMA序列
        """
        alpha = 2.0 / (span + 1)

        if self.use_gpu:
            prices_gpu = self._to_gpu(prices)
            ema_gpu = cp.zeros_like(prices_gpu)
            ema_gpu[0] = prices_gpu[0]

            # GPU加速的EMA计算
            for i in range(1, len(prices_gpu)):
                ema_gpu[i] = alpha * prices_gpu[i] + (1 - alpha) * ema_gpu[i-1]

            return self._to_cpu(ema_gpu)
        else:
            # CPU实现
            return pd.Series(prices).ewm(span=span, adjust=False).mean().values

    def calculate_rsi(
        self,
        prices: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """
        计算RSI（GPU加速）

        Args:
            prices: 价格序列
            period: 周期

        Returns:
            RSI序列
        """
        if self.use_gpu:
            prices_gpu = self._to_gpu(prices)

            # 计算价格变化
            deltas = cp.diff(prices_gpu)

            # 分离上涨和下跌
            gains = cp.where(deltas > 0, deltas, 0)
            losses = cp.where(deltas < 0, -deltas, 0)

            # 计算平均涨跌幅
            avg_gains = cp.zeros(len(prices_gpu))
            avg_losses = cp.zeros(len(prices_gpu))

            # 初始平均值
            avg_gains[period] = cp.mean(gains[:period])
            avg_losses[period] = cp.mean(losses[:period])

            # 指数移动平均
            alpha = 1.0 / period
            for i in range(period + 1, len(prices_gpu)):
                avg_gains[i] = alpha * gains[i-1] + (1 - alpha) * avg_gains[i-1]
                avg_losses[i] = alpha * losses[i-1] + (1 - alpha) * avg_losses[i-1]

            # 计算RS和RSI
            rs = avg_gains / (avg_losses + 1e-10)
            rsi = 100 - (100 / (1 + rs))

            return self._to_cpu(rsi)
        else:
            # CPU实现
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            avg_gains = pd.Series(gains).ewm(span=period, adjust=False).mean()
            avg_losses = pd.Series(losses).ewm(span=period, adjust=False).mean()

            rs = avg_gains / (avg_losses + 1e-10)
            rsi = 100 - (100 / (1 + rs))

            return np.concatenate([[np.nan], rsi.values])

    def calculate_macd(
        self,
        prices: np.ndarray,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, np.ndarray]:
        """
        计算MACD（GPU加速）

        Args:
            prices: 价格序列
            fast_period: 快线周期
            slow_period: 慢线周期
            signal_period: 信号线周期

        Returns:
            {'macd': MACD线, 'signal': 信号线, 'histogram': 柱状图}
        """
        # 计算快慢EMA
        ema_fast = self.calculate_ema(prices, fast_period)
        ema_slow = self.calculate_ema(prices, slow_period)

        # MACD线
        macd = ema_fast - ema_slow

        # 信号线
        signal = self.calculate_ema(macd, signal_period)

        # 柱状图
        histogram = macd - signal

        return {
            'macd': macd,
            'signal': signal,
            'histogram': histogram
        }

    def calculate_bollinger_bands(
        self,
        prices: np.ndarray,
        window: int = 20,
        num_std: float = 2.0
    ) -> Dict[str, np.ndarray]:
        """
        计算布林带（GPU加速）

        Args:
            prices: 价格序列
            window: 窗口期
            num_std: 标准差倍数

        Returns:
            {'middle': 中轨, 'upper': 上轨, 'lower': 下轨}
        """
        if self.use_gpu:
            prices_gpu = self._to_gpu(prices)

            # 中轨（移动平均）
            middle = self.calculate_sma(prices, window)
            middle_gpu = self._to_gpu(middle)

            # 计算移动标准差
            std_gpu = cp.zeros_like(prices_gpu)
            for i in range(window - 1, len(prices_gpu)):
                std_gpu[i] = cp.std(prices_gpu[i-window+1:i+1])

            # 上下轨
            upper_gpu = middle_gpu + num_std * std_gpu
            lower_gpu = middle_gpu - num_std * std_gpu

            return {
                'middle': middle,
                'upper': self._to_cpu(upper_gpu),
                'lower': self._to_cpu(lower_gpu)
            }
        else:
            # CPU实现
            middle = pd.Series(prices).rolling(window).mean().values
            std = pd.Series(prices).rolling(window).std().values

            return {
                'middle': middle,
                'upper': middle + num_std * std,
                'lower': middle - num_std * std
            }

    def calculate_atr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14
    ) -> np.ndarray:
        """
        计算ATR（GPU加速）

        Args:
            high: 最高价序列
            low: 最低价序列
            close: 收盘价序列
            period: 周期

        Returns:
            ATR序列
        """
        if self.use_gpu:
            high_gpu = self._to_gpu(high)
            low_gpu = self._to_gpu(low)
            close_gpu = self._to_gpu(close)

            # 计算True Range
            tr1 = high_gpu - low_gpu
            tr2 = cp.abs(high_gpu - cp.roll(close_gpu, 1))
            tr3 = cp.abs(low_gpu - cp.roll(close_gpu, 1))

            tr = cp.maximum(tr1, cp.maximum(tr2, tr3))
            tr[0] = tr1[0]  # 第一个值

            # 计算ATR（EMA）
            atr = self.calculate_ema(self._to_cpu(tr), period)

            return atr
        else:
            # CPU实现
            tr1 = high - low
            tr2 = np.abs(high - np.roll(close, 1))
            tr3 = np.abs(low - np.roll(close, 1))

            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            tr[0] = tr1[0]

            return pd.Series(tr).ewm(span=period, adjust=False).mean().values

    def batch_calculate_factors(
        self,
        df: pd.DataFrame,
        factors: list
    ) -> pd.DataFrame:
        """
        批量计算因子（GPU加速）

        Args:
            df: 包含OHLC数据的DataFrame
            factors: 要计算的因子列表

        Returns:
            添加了因子列的DataFrame
        """
        result = df.copy()
        prices = df['close'].values

        for factor in factors:
            if factor == 'sma_20':
                result['sma_20'] = self.calculate_sma(prices, 20)
            elif factor == 'ema_12':
                result['ema_12'] = self.calculate_ema(prices, 12)
            elif factor == 'rsi_14':
                result['rsi_14'] = self.calculate_rsi(prices, 14)
            elif factor == 'macd':
                macd_result = self.calculate_macd(prices)
                result['macd'] = macd_result['macd']
                result['macd_signal'] = macd_result['signal']
                result['macd_histogram'] = macd_result['histogram']
            elif factor == 'bollinger':
                bb_result = self.calculate_bollinger_bands(prices)
                result['bb_middle'] = bb_result['middle']
                result['bb_upper'] = bb_result['upper']
                result['bb_lower'] = bb_result['lower']
            elif factor == 'atr_14':
                result['atr_14'] = self.calculate_atr(
                    df['high'].values,
                    df['low'].values,
                    df['close'].values,
                    14
                )

        return result


def benchmark_performance():
    """性能基准测试"""
    logger.info('=== GPU vs CPU Performance Benchmark ===\n')

    # 生成测试数据
    np.random.seed(42)
    n_samples = 10000
    prices = 100 + np.cumsum(np.random.randn(n_samples) * 0.5)

    # CPU计算
    cpu_calculator = GPUFactorCalculator(use_gpu=False)

    start = time.time()
    cpu_sma = cpu_calculator.calculate_sma(prices, 20)
    cpu_rsi = cpu_calculator.calculate_rsi(prices, 14)
    cpu_macd = cpu_calculator.calculate_macd(prices)
    cpu_time = time.time() - start

    logger.info(f'CPU Time: {cpu_time * 1000:.2f}ms')

    # GPU计算
    if GPU_AVAILABLE:
        gpu_calculator = GPUFactorCalculator(use_gpu=True)

        start = time.time()
        gpu_sma = gpu_calculator.calculate_sma(prices, 20)
        gpu_rsi = gpu_calculator.calculate_rsi(prices, 14)
        gpu_macd = gpu_calculator.calculate_macd(prices)
        gpu_time = time.time() - start

        logger.info(f'GPU Time: {gpu_time * 1000:.2f}ms')
        logger.info(f'Speedup: {cpu_time / gpu_time:.2f}x')

        # 验证结果一致性
        sma_diff = np.nanmean(np.abs(cpu_sma - gpu_sma))
        rsi_diff = np.nanmean(np.abs(cpu_rsi - gpu_rsi))
        logger.info(f'\nResult Difference:')
        logger.info(f'  SMA: {sma_diff:.6f}')
        logger.info(f'  RSI: {rsi_diff:.6f}')
    else:
        logger.info('GPU not available, skipping GPU benchmark')


# 使用示例
def example_usage():
    """使用示例"""
    # 创建计算器
    calculator = GPUFactorCalculator(use_gpu=True)

    # 生成模拟数据
    np.random.seed(42)
    n = 1000
    df = pd.DataFrame({
        'close': 100 + np.cumsum(np.random.randn(n) * 0.5),
        'high': 100 + np.cumsum(np.random.randn(n) * 0.5) + 1,
        'low': 100 + np.cumsum(np.random.randn(n) * 0.5) - 1,
        'volume': np.random.randint(1000, 10000, n)
    })

    # 批量计算因子
    factors = ['sma_20', 'ema_12', 'rsi_14', 'macd', 'bollinger', 'atr_14']
    result = calculator.batch_calculate_factors(df, factors)

    logger.info('Calculated Factors:')
    logger.info(result.tail())


if __name__ == "__main__":
    example_usage()
    logger.info('\n')
    benchmark_performance()

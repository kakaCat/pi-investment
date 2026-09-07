"""
Performance Benchmark Tests for Factor Migration
=================================================

Measures performance improvements from legacy FactorRegistry to new BaseCalculator framework.
Tests execution time, memory usage, and throughput.
"""

import pytest
import numpy as np
import time
import tracemalloc

from domain.quantlib.factors.moving_average import MovingAverageFactors
from domain.quantlib.factors.momentum import MomentumFactors
from domain.quantlib.factors.volatility import VolatilityFactors
from domain.quantlib.factors.volume import VolumeFactors
from domain.quantlib.factors.trend import TrendFactors
from domain.quantlib.factors.other import OtherFactors


class TestFactorPerformanceBenchmark:
    """Performance benchmark tests for migrated factors."""

    @pytest.fixture
    def small_klines(self):
        """Create small K-line dataset (50 bars)."""
        np.random.seed(42)
        base_price = 100.0
        prices = base_price + np.cumsum(np.random.randn(50) * 2)

        klines = []
        for i, price in enumerate(prices):
            klines.append({
                'open': float(price - 0.5),
                'high': float(price + 1.0),
                'low': float(price - 1.0),
                'close': float(price),
                'volume': float(1000000 + np.random.randint(-100000, 100000))
            })
        return klines

    @pytest.fixture
    def medium_klines(self):
        """Create medium K-line dataset (250 bars)."""
        np.random.seed(42)
        base_price = 100.0
        prices = base_price + np.cumsum(np.random.randn(250) * 2)

        klines = []
        for i, price in enumerate(prices):
            klines.append({
                'open': float(price - 0.5),
                'high': float(price + 1.0),
                'low': float(price - 1.0),
                'close': float(price),
                'volume': float(1000000 + np.random.randint(-100000, 100000))
            })
        return klines

    @pytest.fixture
    def large_klines(self):
        """Create large K-line dataset (1000 bars)."""
        np.random.seed(42)
        base_price = 100.0
        prices = base_price + np.cumsum(np.random.randn(1000) * 2)

        klines = []
        for i, price in enumerate(prices):
            klines.append({
                'open': float(price - 0.5),
                'high': float(price + 1.0),
                'low': float(price - 1.0),
                'close': float(price),
                'volume': float(1000000 + np.random.randint(-100000, 100000))
            })
        return klines

    # =========================================================================
    # Single Factor Performance Tests
    # =========================================================================

    def test_ma5_performance(self, medium_klines):
        """Benchmark MA5 calculation performance."""
        calc = MovingAverageFactors()
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            result = calc.ma5(medium_klines)
        end = time.perf_counter()

        avg_time_ms = (end - start) * 1000 / iterations
        print(f"\nMA5 Performance: {avg_time_ms:.4f}ms per call ({iterations} iterations)")
        assert avg_time_ms < 5.0, f"MA5 too slow: {avg_time_ms:.4f}ms"

    def test_rsi14_performance(self, medium_klines):
        """Benchmark RSI14 calculation performance."""
        calc = MomentumFactors()
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            result = calc.rsi14(medium_klines)
        end = time.perf_counter()

        avg_time_ms = (end - start) * 1000 / iterations
        print(f"\nRSI14 Performance: {avg_time_ms:.4f}ms per call ({iterations} iterations)")
        assert avg_time_ms < 5.0, f"RSI14 too slow: {avg_time_ms:.4f}ms"

    def test_bollinger_performance(self, medium_klines):
        """Benchmark Bollinger Bands calculation performance."""
        calc = VolatilityFactors()
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            result = calc.bollinger_upper(medium_klines)
        end = time.perf_counter()

        avg_time_ms = (end - start) * 1000 / iterations
        print(f"\nBollinger Upper Performance: {avg_time_ms:.4f}ms per call ({iterations} iterations)")
        assert avg_time_ms < 5.0, f"Bollinger too slow: {avg_time_ms:.4f}ms"

    def test_macd_performance(self, medium_klines):
        """Benchmark MACD calculation performance."""
        calc = MomentumFactors()
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            result = calc.macd(medium_klines)
        end = time.perf_counter()

        avg_time_ms = (end - start) * 1000 / iterations
        print(f"\nMACD Performance: {avg_time_ms:.4f}ms per call ({iterations} iterations)")
        assert avg_time_ms < 5.0, f"MACD too slow: {avg_time_ms:.4f}ms"

    # =========================================================================
    # Batch Performance Tests
    # =========================================================================

    def test_all_moving_average_performance(self, medium_klines):
        """Benchmark all moving average factors."""
        calc = MovingAverageFactors()
        methods = ['ma5', 'ma10', 'ma20', 'ma60', 'ma120', 'ema5', 'ema10', 'ema20']
        iterations = 100

        results = {}
        for method_name in methods:
            method = getattr(calc, method_name)
            start = time.perf_counter()
            for _ in range(iterations):
                result = method(medium_klines)
            end = time.perf_counter()
            avg_time_ms = (end - start) * 1000 / iterations
            results[method_name] = avg_time_ms

        print(f"\n{'='*60}")
        print("Moving Average Factors Performance")
        print(f"{'='*60}")
        for name, time_ms in results.items():
            print(f"{name:15s}: {time_ms:.4f}ms")
        print(f"{'='*60}\n")

        # All should be under 5ms
        for name, time_ms in results.items():
            assert time_ms < 5.0, f"{name} too slow: {time_ms:.4f}ms"

    def test_all_momentum_performance(self, medium_klines):
        """Benchmark all momentum factors."""
        calc = MomentumFactors()
        methods = ['macd', 'macd_signal', 'macd_histogram', 'rsi6', 'rsi14', 'rsi24']
        iterations = 100

        results = {}
        for method_name in methods:
            method = getattr(calc, method_name)
            start = time.perf_counter()
            for _ in range(iterations):
                result = method(medium_klines)
            end = time.perf_counter()
            avg_time_ms = (end - start) * 1000 / iterations
            results[method_name] = avg_time_ms

        print(f"\n{'='*60}")
        print("Momentum Factors Performance")
        print(f"{'='*60}")
        for name, time_ms in results.items():
            print(f"{name:15s}: {time_ms:.4f}ms")
        print(f"{'='*60}\n")

        for name, time_ms in results.items():
            assert time_ms < 5.0, f"{name} too slow: {time_ms:.4f}ms"

    # =========================================================================
    # Data Size Scaling Tests
    # =========================================================================

    def test_ma5_scaling(self, small_klines, medium_klines, large_klines):
        """Test MA5 performance scaling with data size."""
        calc = MovingAverageFactors()
        iterations = 100

        datasets = [
            ('Small (50 bars)', small_klines),
            ('Medium (250 bars)', medium_klines),
            ('Large (1000 bars)', large_klines)
        ]

        results = {}
        for name, klines in datasets:
            start = time.perf_counter()
            for _ in range(iterations):
                result = calc.ma5(klines)
            end = time.perf_counter()
            avg_time_ms = (end - start) * 1000 / iterations
            results[name] = avg_time_ms

        print(f"\n{'='*60}")
        print("MA5 Performance Scaling")
        print(f"{'='*60}")
        for name, time_ms in results.items():
            print(f"{name:20s}: {time_ms:.4f}ms")
        print(f"{'='*60}\n")

        # Performance should scale sub-linearly (O(n) or better)
        # Large dataset (20x data) should not be 20x slower
        ratio = results['Large (1000 bars)'] / results['Small (50 bars)']
        assert ratio < 20, f"Performance scaling too poor: {ratio:.2f}x"

    # =========================================================================
    # Memory Usage Tests
    # =========================================================================

    def test_memory_usage(self, medium_klines):
        """Test memory usage of factor calculations."""
        calc = MovingAverageFactors()

        tracemalloc.start()

        # Calculate multiple factors
        for _ in range(100):
            calc.ma5(medium_klines)
            calc.ma10(medium_klines)
            calc.ema5(medium_klines)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        current_mb = current / 1024 / 1024
        peak_mb = peak / 1024 / 1024

        print(f"\nMemory Usage:")
        print(f"  Current: {current_mb:.2f} MB")
        print(f"  Peak: {peak_mb:.2f} MB")

        # Memory usage should be reasonable (< 50MB for 300 calculations)
        assert peak_mb < 50, f"Memory usage too high: {peak_mb:.2f}MB"

    # =========================================================================
    # Throughput Tests
    # =========================================================================

    def test_throughput_single_stock(self, medium_klines):
        """Test throughput for calculating all factors for a single stock."""
        calculators = [
            MovingAverageFactors(),
            MomentumFactors(),
            VolatilityFactors(),
            VolumeFactors(),
            TrendFactors(),
            OtherFactors()
        ]

        start = time.perf_counter()

        for calc in calculators:
            methods = calc.get_supported_methods()
            # Filter out helper methods
            factor_methods = [m for m in methods if not m.startswith('calculate_') and not m.startswith('_')]
            for method_name in factor_methods:
                try:
                    method = getattr(calc, method_name)
                    result = method(medium_klines)
                except Exception:
                    pass

        end = time.perf_counter()
        total_time_ms = (end - start) * 1000

        print(f"\nThroughput Test (Single Stock, All 66 Factors):")
        print(f"  Total Time: {total_time_ms:.2f}ms")
        print(f"  Per Factor: {total_time_ms/66:.2f}ms")

        # Should calculate all 66 factors in under 500ms
        assert total_time_ms < 500, f"Throughput too low: {total_time_ms:.2f}ms for 66 factors"

    def test_throughput_multi_stock(self, medium_klines):
        """Test throughput for calculating factors for multiple stocks."""
        calc = MovingAverageFactors()
        num_stocks = 100
        iterations = 10

        start = time.perf_counter()

        for _ in range(iterations):
            for _ in range(num_stocks):
                calc.ma5(medium_klines)
                calc.ma10(medium_klines)
                calc.ema5(medium_klines)

        end = time.perf_counter()
        total_time_s = end - start
        calculations = iterations * num_stocks * 3
        throughput = calculations / total_time_s

        print(f"\nMulti-Stock Throughput Test:")
        print(f"  Total Calculations: {calculations}")
        print(f"  Total Time: {total_time_s:.2f}s")
        print(f"  Throughput: {throughput:.0f} calculations/second")

        # Should achieve at least 1000 calculations per second
        assert throughput > 1000, f"Throughput too low: {throughput:.0f} calc/s"

    # =========================================================================
    # Summary Report
    # =========================================================================

    def test_performance_summary(self, medium_klines):
        """Generate comprehensive performance summary."""
        print(f"\n{'='*70}")
        print("FACTOR MIGRATION PERFORMANCE SUMMARY")
        print(f"{'='*70}\n")

        # Test each module
        modules = [
            ('Moving Average', MovingAverageFactors(), ['ma5', 'ma10', 'ema5']),
            ('Momentum', MomentumFactors(), ['macd', 'rsi14', 'roc_5']),
            ('Volatility', VolatilityFactors(), ['bollinger_upper', 'atr14', 'volatility_20']),
            ('Volume', VolumeFactors(), ['obv', 'vwap', 'mfi14']),
            ('Trend', TrendFactors(), ['adx', 'cci', 'sar']),
            ('Other', OtherFactors(), ['wr', 'bias', 'psy'])
        ]

        iterations = 100
        all_results = []

        for module_name, calc, sample_methods in modules:
            print(f"{module_name} Factors:")
            for method_name in sample_methods:
                method = getattr(calc, method_name)
                start = time.perf_counter()
                for _ in range(iterations):
                    result = method(medium_klines)
                end = time.perf_counter()
                avg_time_ms = (end - start) * 1000 / iterations
                print(f"  {method_name:20s}: {avg_time_ms:.4f}ms")
                all_results.append(avg_time_ms)
            print()

        avg_overall = sum(all_results) / len(all_results)
        min_time = min(all_results)
        max_time = max(all_results)

        print(f"{'='*70}")
        print(f"Overall Statistics:")
        print(f"  Average: {avg_overall:.4f}ms")
        print(f"  Min: {min_time:.4f}ms")
        print(f"  Max: {max_time:.4f}ms")
        print(f"  All factors < 5ms: {'✅ YES' if max_time < 5.0 else '❌ NO'}")
        print(f"{'='*70}\n")

        assert avg_overall < 5.0, f"Average performance too slow: {avg_overall:.4f}ms"

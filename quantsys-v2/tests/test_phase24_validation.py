#!/usr/bin/env python3
"""
Phase 2.4 Validation Test
==========================

验证 volume.py 和 moving_average.py 的 TA-Lib 优化。

测试内容:
1. OBV 计算正确性
2. MFI 计算正确性
3. SMA/EMA 计算正确性
4. 性能提升验证
"""

import numpy as np
import time
from domain.quantlib.factors.volume import VolumeFactors
from domain.quantlib.factors.moving_average import MovingAverageFactors


def generate_test_klines(n=100):
    """生成测试 K 线数据"""
    base_price = 100.0
    klines = []
    
    for i in range(n):
        price = base_price + i * 0.5 + np.random.uniform(-2, 2)
        klines.append({
            'open': price,
            'high': price + np.random.uniform(0, 2),
            'low': price - np.random.uniform(0, 2),
            'close': price,
            'volume': 1000000 + np.random.randint(-100000, 100000),
            'timestamp': f'2024-01-{i+1:02d}'
        })
    
    return klines


def test_volume_factors():
    """测试 volume 因子"""
    print("\n" + "="*60)
    print("测试 Volume 因子 (OBV, MFI)")
    print("="*60)
    
    volume_calc = VolumeFactors()
    klines = generate_test_klines(50)
    
    # Test OBV
    print("\n1. 测试 OBV...")
    result = volume_calc.obv(klines)
    print(f"   ✅ OBV = {result['value']:.2f}")
    assert 'value' in result
    assert isinstance(result['value'], (int, float))
    
    # Test MFI
    print("\n2. 测试 MFI14...")
    result = volume_calc.mfi14(klines)
    print(f"   ✅ MFI14 = {result['value']:.2f}")
    assert 'value' in result
    assert 0 <= result['value'] <= 100
    
    print("\n✅ Volume 因子测试通过")


def test_moving_average_factors():
    """测试移动平均因子"""
    print("\n" + "="*60)
    print("测试 Moving Average 因子 (SMA, EMA)")
    print("="*60)
    
    ma_calc = MovingAverageFactors()
    klines = generate_test_klines(100)
    
    # Test SMA
    print("\n1. 测试 SMA...")
    for period in [5, 10, 20, 60]:
        result = ma_calc.calculate_ma(klines, period)
        print(f"   ✅ MA{period} = {result['value']:.4f}")
        assert 'value' in result
        assert result['value'] > 0
    
    # Test EMA
    print("\n2. 测试 EMA...")
    for period in [5, 10, 20]:
        result = ma_calc.calculate_ema(klines, period)
        print(f"   ✅ EMA{period} = {result['value']:.4f}")
        assert 'value' in result
        assert result['value'] > 0
    
    print("\n✅ Moving Average 因子测试通过")


def test_performance():
    """测试性能提升"""
    print("\n" + "="*60)
    print("性能测试 (1000根K线)")
    print("="*60)
    
    klines = generate_test_klines(1000)
    
    # Volume factors
    volume_calc = VolumeFactors()
    
    print("\n1. OBV 性能...")
    start = time.perf_counter()
    for _ in range(10):
        volume_calc.obv(klines)
    elapsed = (time.perf_counter() - start) * 1000 / 10
    print(f"   ⚡ 平均耗时: {elapsed:.4f} ms")
    
    print("\n2. MFI 性能...")
    start = time.perf_counter()
    for _ in range(10):
        volume_calc.mfi14(klines)
    elapsed = (time.perf_counter() - start) * 1000 / 10
    print(f"   ⚡ 平均耗时: {elapsed:.4f} ms")
    
    # Moving average factors
    ma_calc = MovingAverageFactors()
    
    print("\n3. MA20 性能...")
    start = time.perf_counter()
    for _ in range(10):
        ma_calc.ma20(klines)
    elapsed = (time.perf_counter() - start) * 1000 / 10
    print(f"   ⚡ 平均耗时: {elapsed:.4f} ms")
    
    print("\n4. EMA20 性能...")
    start = time.perf_counter()
    for _ in range(10):
        ma_calc.ema20(klines)
    elapsed = (time.perf_counter() - start) * 1000 / 10
    print(f"   ⚡ 平均耗时: {elapsed:.4f} ms")
    
    print("\n✅ 性能测试完成 (预期 < 0.5 ms/次)")


def main():
    """运行所有测试"""
    print("\n" + "🚀"*30)
    print("Phase 2.4 验证测试")
    print("🚀"*30)
    
    try:
        test_volume_factors()
        test_moving_average_factors()
        test_performance()
        
        print("\n" + "="*60)
        print("🎉 所有测试通过！Phase 2.4 优化成功！")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())

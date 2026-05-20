"""
因子库使用示例

演示如何使用因子库计算技术因子和基本面因子
"""
import pandas as pd
import numpy as np
from factors.calculator import FactorCalculator
from factors.cache import FactorCache
from factors.technical import MA, EMA, MACD, RSI, KDJ, ATR, BollingerBands, OBV, VWAP
from factors.fundamental import PE, PB, ROE, ROA, GrossMargin, NetMargin


def generate_sample_data(days=100):
    """生成示例OHLCV数据"""
    dates = pd.date_range('2024-01-01', periods=days, freq='D')
    np.random.seed(42)

    data = pd.DataFrame({
        'date': dates,
        'open': 100 + np.random.randn(days).cumsum(),
        'high': 102 + np.random.randn(days).cumsum(),
        'low': 98 + np.random.randn(days).cumsum(),
        'close': 100 + np.random.randn(days).cumsum(),
        'volume': np.random.randint(1000000, 5000000, days)
    })

    # 确保 high >= close >= low
    data['high'] = data[['high', 'close']].max(axis=1)
    data['low'] = data[['low', 'close']].min(axis=1)

    return data


def example_single_factor():
    """示例1: 计算单个因子"""
    print("=" * 60)
    print("示例1: 计算单个因子")
    print("=" * 60)

    data = generate_sample_data()

    # 计算MA5
    ma5 = MA(period=5)
    result = ma5.calculate(data)

    print(f"\n因子名称: {ma5.name}")
    print(f"因子描述: {ma5.description}")
    print(f"\n最近5天的MA5值:")
    print(result.tail())


def example_multiple_factors():
    """示例2: 批量计算多个因子"""
    print("\n" + "=" * 60)
    print("示例2: 批量计算多个因子")
    print("=" * 60)

    data = generate_sample_data()

    # 创建因子计算器
    calculator = FactorCalculator(max_workers=4)

    # 注册多个因子
    factors = [
        MA(period=5),
        MA(period=20),
        MA(period=60),
        EMA(period=12),
        RSI(period=14),
        ATR(period=14)
    ]
    calculator.register_batch(factors)

    print(f"\n已注册 {len(calculator)} 个因子")

    # 批量计算
    results = calculator.calculate_all(data)

    print(f"\n计算结果 (最近5天):")
    print(results.tail())

    print(f"\n因子统计信息:")
    print(results.describe())


def example_macd_kdj():
    """示例3: 计算返回多列的因子 (MACD, KDJ)"""
    print("\n" + "=" * 60)
    print("示例3: 计算MACD和KDJ")
    print("=" * 60)

    data = generate_sample_data()

    # MACD
    macd = MACD()
    macd_result = macd.calculate(data)

    print("\nMACD结果 (最近5天):")
    print(macd_result.tail())

    # KDJ
    kdj = KDJ()
    kdj_result = kdj.calculate(data)

    print("\nKDJ结果 (最近5天):")
    print(kdj_result.tail())


def example_bollinger_bands():
    """示例4: 计算布林带"""
    print("\n" + "=" * 60)
    print("示例4: 计算布林带")
    print("=" * 60)

    data = generate_sample_data()

    bb = BollingerBands(period=20, std_dev=2.0)
    result = bb.calculate(data)

    print("\n布林带结果 (最近5天):")
    print(result.tail())

    # 分析当前价格在布林带中的位置
    latest = result.iloc[-1]
    print(f"\n最新数据分析:")
    print(f"当前价格: {data['close'].iloc[-1]:.2f}")
    print(f"布林带上轨: {latest['bb_upper']:.2f}")
    print(f"布林带中轨: {latest['bb_middle']:.2f}")
    print(f"布林带下轨: {latest['bb_lower']:.2f}")
    print(f"价格位置百分比: {latest['bb_percent']:.2%}")


def example_with_cache():
    """示例5: 使用缓存加速计算"""
    print("\n" + "=" * 60)
    print("示例5: 使用缓存")
    print("=" * 60)

    data = generate_sample_data()
    cache = FactorCache(cache_dir=".pi-invest/factor-cache", ttl_hours=24)

    symbol = "000001"
    start_date = "2024-01-01"
    end_date = "2024-04-10"

    # 尝试从缓存获取
    cached_ma5 = cache.get("MA5", symbol, start_date, end_date)

    if cached_ma5 is not None:
        print("\n从缓存中获取MA5")
        result = cached_ma5
    else:
        print("\n缓存未命中，重新计算MA5")
        ma5 = MA(period=5)
        result = ma5.calculate(data)

        # 保存到缓存
        cache.set("MA5", symbol, start_date, end_date, result)
        print("已保存到缓存")

    print(f"\nMA5结果 (最近5天):")
    print(result.tail())

    # 查看缓存统计
    stats = cache.get_cache_stats()
    print(f"\n缓存统计:")
    print(f"  缓存文件数: {stats['total_files']}")
    print(f"  缓存大小: {stats['total_size_mb']:.2f} MB")
    print(f"  过期文件数: {stats['expired_files']}")


def example_performance_test():
    """示例6: 性能测试"""
    print("\n" + "=" * 60)
    print("示例6: 性能测试")
    print("=" * 60)

    import time

    data = generate_sample_data(days=252)  # 一年的数据

    calculator = FactorCalculator(max_workers=4)

    # 注册20个技术因子
    factors = [
        MA(5), MA(10), MA(20), MA(60),
        EMA(12), EMA(26),
        RSI(14), RSI(6),
        ATR(14),
        BollingerBands(),
        OBV(),
        VWAP(),
    ]
    calculator.register_batch(factors)

    print(f"\n测试配置:")
    print(f"  数据点数: {len(data)}")
    print(f"  因子数量: {len(calculator)}")

    # 串行计算
    start = time.time()
    factor_names = list(calculator.factors.keys())
    result_serial = calculator.calculate_batch(factor_names, data, parallel=False)
    serial_time = time.time() - start

    # 并行计算
    start = time.time()
    result_parallel = calculator.calculate_batch(factor_names, data, parallel=True)
    parallel_time = time.time() - start

    print(f"\n性能结果:")
    print(f"  串行计算耗时: {serial_time:.3f}秒")
    print(f"  并行计算耗时: {parallel_time:.3f}秒")
    print(f"  加速比: {serial_time/parallel_time:.2f}x")

    # 验证每个因子的计算时间 < 1秒
    print(f"\n单因子平均耗时: {parallel_time/len(calculator):.3f}秒")


def example_fundamental_factors():
    """示例7: 基本面因子计算"""
    print("\n" + "=" * 60)
    print("示例7: 基本面因子计算")
    print("=" * 60)

    # 生成示例财务数据
    data = pd.DataFrame({
        'price': [10.5, 11.2, 10.8, 11.5, 12.0],
        'eps': [0.5, 0.52, 0.55, 0.58, 0.60],
        'bvps': [5.0, 5.2, 5.3, 5.5, 5.6],
        'net_profit': [100, 105, 110, 115, 120],
        'equity': [1000, 1050, 1100, 1150, 1200],
        'total_assets': [2000, 2100, 2200, 2300, 2400],
        'revenue': [500, 520, 540, 560, 580],
        'cost': [300, 310, 320, 330, 340]
    })

    # 计算估值因子
    pe = PE()
    pb = PB()
    pe_result = pe.calculate(data)
    pb_result = pb.calculate(data)

    print("\n估值因子:")
    print(f"PE (市盈率): {pe_result.tolist()}")
    print(f"PB (市净率): {pb_result.tolist()}")

    # 计算盈利能力因子
    roe = ROE()
    roa = ROA()
    gross_margin = GrossMargin()
    net_margin = NetMargin()

    roe_result = roe.calculate(data)
    roa_result = roa.calculate(data)
    gross_margin_result = gross_margin.calculate(data)
    net_margin_result = net_margin.calculate(data)

    print("\n盈利能力因子:")
    print(f"ROE (净资产收益率): {roe_result.tolist()}")
    print(f"ROA (总资产收益率): {roa_result.tolist()}")
    print(f"毛利率: {gross_margin_result.tolist()}")
    print(f"净利率: {net_margin_result.tolist()}")


if __name__ == '__main__':
    print("\n因子库使用示例\n")

    example_single_factor()
    example_multiple_factors()
    example_macd_kdj()
    example_bollinger_bands()
    example_with_cache()
    example_performance_test()
    example_fundamental_factors()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)

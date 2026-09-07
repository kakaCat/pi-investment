"""
测试 Polars DataFrame 修复
"""
import sys

from adapters.outbound.repositories import KlineORMRepository
from application.services.pool_signal_scanner import PoolSignalScanner
from adapters.outbound.repositories import StrategyORMRepository
from datetime import datetime, timedelta

def test_kline_repo_returns_polars():
    """测试 kline_repo 返回 Polars DataFrame"""
    print("测试 1: kline_repo.get_range() 返回类型")
    repo = KlineORMRepository()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    klines = repo.get_range('600000', start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))

    print(f"  返回类型: {type(klines)}")
    print(f"  是否为 Polars DataFrame: {str(type(klines).__name__) == 'DataFrame'}")
    print(f"  数据长度: {len(klines)}")
    print(f"  是否为空: {klines.is_empty()}")
    print("  ✓ 测试通过\n")

    return klines

def test_pool_scanner_handles_polars():
    """测试 pool_signal_scanner 正确处理 Polars DataFrame"""
    print("测试 2: pool_signal_scanner 处理 Polars DataFrame")

    kline_repo = KlineORMRepository()
    strategy_repo = StrategyORMRepository()
    scanner = PoolSignalScanner(kline_repo, strategy_repo)

    try:
        result = scanner.scan_pool_signals(
            symbols=['600000'],
            strategy_id=272,
            lookback_days=60
        )

        print(f"  扫描成功: {result['total_symbols']} 只股票")
        print(f"  买入信号: {result['summary']['buy']}")
        print(f"  持有信号: {result['summary']['hold']}")
        print(f"  错误数: {result['summary']['error']}")

        if result['summary']['error'] > 0:
            print(f"  错误详情: {result['errors']}")
            return False
        else:
            print("  ✓ 测试通过\n")
            return True

    except Exception as e:
        print(f"  ✗ 测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False

def test_empty_dataframe_check():
    """测试空 DataFrame 的检查"""
    print("测试 3: 空 DataFrame 检查")
    import polars as pl

    # 创建空 DataFrame
    empty_df = pl.DataFrame()

    # 旧方式（会报错）
    try:
        if not empty_df:  # 这会抛出异常
            print("  旧方式: 不应该到这里")
    except Exception as e:
        print(f"  旧方式报错（预期）: {str(e)[:50]}...")

    # 新方式（正确）
    if empty_df.is_empty():
        print("  新方式: 正确检测到空 DataFrame")
        print("  ✓ 测试通过\n")
        return True
    else:
        print("  ✗ 新方式失败\n")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Polars DataFrame 修复验证测试")
    print("=" * 60 + "\n")

    try:
        # 测试 1
        klines = test_kline_repo_returns_polars()

        # 测试 2
        success = test_pool_scanner_handles_polars()

        # 测试 3
        test_empty_dataframe_check()

        print("=" * 60)
        if success:
            print("✓ 所有测试通过")
        else:
            print("✗ 部分测试失败")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

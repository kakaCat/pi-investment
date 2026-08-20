#!/usr/bin/env python
"""
验证 batch_get_fundamentals 方法修复

问题：StockORMRepository 缺少 batch_get_fundamentals 方法
修复：添加了该方法，从 Stock 表批量查询基本面数据
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent

from adapters.outbound.repositories import StockORMRepository


def test_method_exists():
    """测试方法是否存在"""
    repo = StockORMRepository()
    assert hasattr(repo, 'batch_get_fundamentals'), "batch_get_fundamentals 方法不存在"
    print("✓ batch_get_fundamentals 方法已存在")
    return True


def test_empty_list():
    """测试空列表"""
    repo = StockORMRepository()
    result = repo.batch_get_fundamentals([])
    assert result == {}, f"空列表应返回空字典，实际返回: {result}"
    print("✓ 空列表测试通过")
    return True


def test_batch_query():
    """测试批量查询"""
    repo = StockORMRepository()
    symbols = ['000001', '600036', '999999']  # 最后一个不存在

    result = repo.batch_get_fundamentals(symbols)

    # 验证返回结构
    assert isinstance(result, dict), "返回值应为字典"
    assert len(result) == 3, f"应返回3个元素，实际: {len(result)}"

    # 验证键存在
    for symbol in symbols:
        assert symbol in result, f"结果中缺少 {symbol}"

    print(f"✓ 批量查询测试通过，返回 {len(result)} 个结果")

    # 显示结果示例
    for symbol in symbols[:2]:
        if result[symbol]:
            print(f"  - {symbol}: PE={result[symbol].get('pe_ratio')}, ROE={result[symbol].get('roe')}")

    return True


if __name__ == '__main__':
    print("=" * 60)
    print("验证 batch_get_fundamentals 修复")
    print("=" * 60)
    print()

    try:
        test_method_exists()
        test_empty_list()
        test_batch_query()

        print()
        print("=" * 60)
        print("✓ 所有测试通过！修复验证成功。")
        print("=" * 60)
        sys.exit(0)

    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        sys.exit(1)

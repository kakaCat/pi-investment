#!/usr/bin/env python
"""
验证 batch_get_fundamentals 方法修复

问题：StockORMRepository 缺少 batch_get_fundamentals 方法
修复：添加了该方法，从 Stock 表批量查询基本面数据

测试：
1. 方法存在性检查
2. 空列表测试
3. 批量查询测试
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from adapters.outbound.repositories import StockORMRepository


def test_method_exists():
    """测试方法是否存在"""
    repo = StockORMRepository()
    assert hasattr(repo, 'batch_get_fundamentals'), "batch_get_fundamentals 方法不存在"
    print("✓ batch_get_fundamentals 方法已存在")


def test_empty_list():
    """测试空列表"""
    repo = StockORMRepository()
    result = repo.batch_get_fundamentals([])
    assert result == {}, f"空列表应返回空字典，实际返回: {result}"
    print("✓ 空列表测试通过")


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

    # 验证不存在的股票返回 None
    assert result['999999'] is None, "不存在的股票应返回 None"

    # 验证存在的股票有数据
    for symbol in ['000001', '600036']:
        if result[symbol] is not None:
            assert 'pe_ratio' in result[symbol], f"{symbol} 缺少 pe_ratio 字段"
            assert 'roe' in result[symbol], f"{symbol} 缺少 roe 字段"
            print(f"✓ {symbol} 数据结构正确: {list(result[symbol].keys())}")
        else:
            print(f"⚠ {symbol} 在数据库中不存在（这可能是正常的）")

    print(f"✓ 批量查询测试通过，返回 {len(result)} 个结果")


def test_method_signature():
    """测试方法签名"""
    import inspect
    repo = StockORMRepository()
    sig = inspect.signature(repo.batch_get_fundamentals)

    # 验证参数
    params = list(sig.parameters.keys())
    assert 'symbols' in params, "方法应该接受 symbols 参数"

    # 验证返回类型注解
    if sig.return_annotation != inspect.Signature.empty:
        print(f"✓ 返回类型注解: {sig.return_annotation}")

    print(f"✓ 方法签名正确: {sig}")


if __name__ == '__main__':
    print("=" * 60)
    print("测试 batch_get_fundamentals 修复")
    print("=" * 60)
    print()

    try:
        test_method_exists()
        test_method_signature()
        test_empty_list()
        test_batch_query()

        print()
        print("=" * 60)
        print("✓ 所有测试通过！修复验证成功。")
        print("=" * 60)
        sys.exit(0)

    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"✗ 测试失败: {e}")
        print("=" * 60)
        sys.exit(1)

    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        sys.exit(1)

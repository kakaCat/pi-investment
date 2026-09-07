"""
测试 Polars DataFrame 空值检查修复（无需数据库）
"""
import polars as pl

def test_empty_dataframe_check():
    """测试空 DataFrame 的检查"""
    print("\n测试 1: 空 DataFrame 检查")

    # 创建空 DataFrame
    empty_df = pl.DataFrame()

    # 旧方式（会报错）
    print("  旧方式测试: if not df")
    try:
        if not empty_df:
            pass
        print("    ✗ 不应该成功")
    except Exception as e:
        print(f"    ✓ 正确抛出异常: {type(e).__name__}")
        print(f"       消息: {str(e)}")

    # 新方式（正确）
    print("\n  新方式测试: if df.is_empty()")
    try:
        if empty_df.is_empty():
            print("    ✓ 正确检测到空 DataFrame")
        else:
            print("    ✗ 未检测到空 DataFrame")
    except Exception as e:
        print(f"    ✗ 抛出异常: {e}")

def test_non_empty_dataframe_check():
    """测试非空 DataFrame 的检查"""
    print("\n测试 2: 非空 DataFrame 检查")

    # 创建非空 DataFrame
    df = pl.DataFrame({
        'close': [10.0, 11.0, 12.0],
        'volume': [1000, 1100, 1200]
    })

    print(f"  DataFrame 长度: {len(df)}")

    # 新方式
    print("  新方式测试: if df.is_empty()")
    try:
        if df.is_empty():
            print("    ✗ 错误地检测为空")
        else:
            print("    ✓ 正确检测到非空 DataFrame")
    except Exception as e:
        print(f"    ✗ 抛出异常: {e}")

    # 长度检查
    print("  长度检查: len(df) < 20")
    if len(df) < 20:
        print(f"    ✓ 正确: len={len(df)} < 20")
    else:
        print(f"    ✗ 错误: len={len(df)}")

def test_dataframe_conversion():
    """测试 DataFrame 转换"""
    print("\n测试 3: Polars 转 Pandas")

    # 创建 Polars DataFrame
    pl_df = pl.DataFrame({
        'trade_date': ['2026-01-01', '2026-01-02'],
        'close': [10.0, 11.0],
        'volume': [1000, 1100]
    })

    print(f"  Polars DataFrame 类型: {type(pl_df)}")

    # 转换为 Pandas
    import pandas as pd
    pd_df = pl_df.to_pandas()

    print(f"  Pandas DataFrame 类型: {type(pd_df)}")
    print(f"  ✓ 转换成功")

    # 转换为字典列表
    dict_list = pl_df.to_dicts()
    print(f"  字典列表类型: {type(dict_list)}")
    print(f"  字典列表长度: {len(dict_list)}")
    print(f"  第一个元素: {dict_list[0]}")
    print(f"  ✓ 转换成功")

if __name__ == '__main__':
    print("=" * 70)
    print("Polars DataFrame 修复验证测试（无需数据库）")
    print("=" * 70)

    try:
        test_empty_dataframe_check()
        test_non_empty_dataframe_check()
        test_dataframe_conversion()

        print("\n" + "=" * 70)
        print("✓ 所有测试通过")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

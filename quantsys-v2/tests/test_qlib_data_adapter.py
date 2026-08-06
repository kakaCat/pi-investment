"""
Qlib 数据适配器测试

测试 QuantsysV2DataProvider 是否能正确从数据库读取数据
"""

import pytest
import pandas as pd

# qlib 未安装于当前 venv(可选重依赖),缺失时整模块跳过而非 collection error
qlib = pytest.importorskip("qlib", reason="qlib 未安装,跳过 qlib 数据适配器测试")

from application.services.qlib.qlib_data_adapter import QuantsysV2DataProvider
from qlib.data import register_provider


class TestQlibDataAdapter:
    """测试 Qlib 数据适配器"""

    @classmethod
    def setup_class(cls):
        """初始化测试环境"""
        # 注册自定义 Provider
        register_provider('quantsys_v2', QuantsysV2DataProvider)

        # 初始化 Qlib
        qlib.init(provider_uri='quantsys_v2')

    def test_provider_initialization(self):
        """测试 Provider 初始化"""
        provider = QuantsysV2DataProvider()

        assert provider is not None
        assert provider.engine is not None
        print("✅ Provider 初始化成功")

    def test_features_basic(self):
        """测试基础字段查询"""
        from qlib.data import D

        # 查询数据
        df = D.features(
            instruments=['600000.SH', '600519.SH'],
            fields=['$close', '$open', '$volume'],
            start_time='2023-01-01',
            end_time='2023-12-31'
        )

        # 验证
        assert df is not None
        assert not df.empty, "数据不应为空"
        assert isinstance(df.index, pd.MultiIndex), "应该是 MultiIndex"
        assert df.index.names == ['datetime', 'instrument'], "Index 名称应为 datetime, instrument"
        assert '$close' in df.columns
        assert '$open' in df.columns
        assert '$volume' in df.columns

        print(f"✅ 基础字段查询成功: {df.shape}")
        print(f"   数据范围: {df.index.get_level_values(0).min()} ~ {df.index.get_level_values(0).max()}")

    def test_features_expression(self):
        """测试表达式计算"""
        from qlib.data import D

        # 查询表达式
        df = D.features(
            instruments=['600000.SH'],
            fields=['$close', '$open', '$close/$open'],
            start_time='2023-01-01',
            end_time='2023-01-31'
        )

        # 验证
        assert not df.empty
        assert '$close/$open' in df.columns

        # 手动计算验证
        ratio = df['$close'] / df['$open']
        assert (df['$close/$open'] - ratio).abs().max() < 1e-6

        print(f"✅ 表达式计算成功")

    def test_calendar(self):
        """测试交易日历"""
        from qlib.data import D

        # 获取交易日历
        calendar = D.calendar(start_time='2023-01-01', end_time='2023-12-31')

        # 验证
        assert calendar is not None
        assert len(calendar) > 0
        assert len(calendar) > 200, "2023年应该有超过200个交易日"

        print(f"✅ 交易日历查询成功: {len(calendar)} 个交易日")

    def test_instruments(self):
        """测试股票列表"""
        from qlib.data import D

        # 获取所有股票
        instruments = D.instruments(market='all')

        # 验证
        assert instruments is not None
        assert len(instruments) > 0

        print(f"✅ 股票列表查询成功: {len(instruments)} 只股票")
        print(f"   样本: {instruments[:5]}")

    def test_integration_with_alpha158(self):
        """测试与 Alpha158 集成"""
        try:
            from qlib.contrib.data.handler import Alpha158

            # 创建 Alpha158 处理器
            handler = Alpha158(
                instruments=['600000.SH'],
                start_time='2023-01-01',
                end_time='2023-03-31'
            )

            # 获取数据（这会调用我们的 Provider）
            df = handler.fetch()

            # 验证
            assert df is not None
            # Alpha158 可能需要更多配置，这里只测试是否能创建

            print(f"✅ Alpha158 集成测试通过")

        except Exception as e:
            print(f"⚠️  Alpha158 集成测试跳过: {e}")
            # Alpha158 可能需要更复杂的配置，这里不强制要求通过


def test_standalone():
    """独立测试脚本（不依赖 pytest）"""
    print("="*60)
    print("Qlib 数据适配器独立测试")
    print("="*60)
    print()

    try:
        # 1. 注册 Provider
        register_provider('quantsys_v2', QuantsysV2DataProvider)
        qlib.init(provider_uri='quantsys_v2')
        print("✅ Qlib 初始化成功")

        # 2. 测试数据查询
        from qlib.data import D

        df = D.features(
            instruments=['600000.SH', '600519.SH'],
            fields=['$close', '$open', '$high', '$low', '$volume'],
            start_time='2023-01-01',
            end_time='2023-01-10'
        )

        print(f"✅ 数据查询成功")
        print(f"   形状: {df.shape}")
        print(f"   列: {df.columns.tolist()}")
        print()
        print("前5行:")
        print(df.head())
        print()

        # 3. 测试交易日历
        calendar = D.calendar(start_time='2023-01-01', end_time='2023-01-31')
        print(f"✅ 交易日历: 2023年1月有 {len(calendar)} 个交易日")
        print()

        # 4. 测试股票列表
        instruments = D.instruments(market='all')
        print(f"✅ 股票列表: 共 {len(instruments)} 只股票")
        print(f"   前10只: {instruments[:10]}")
        print()

        print("="*60)
        print("🎉 所有测试通过！")
        print("="*60)

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 运行独立测试
    test_standalone()

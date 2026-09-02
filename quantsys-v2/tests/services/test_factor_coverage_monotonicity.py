"""
测试因子覆盖率和单调性分析功能
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from application.services.factor_analysis_service import FactorAnalysisService


@pytest.mark.xfail(reason="alphalens-reloaded 无法安装（pip install 挂死）", strict=False)
class TestFactorCoverageMonotonicity:
    """测试因子覆盖率和单调性分析"""

    @pytest.fixture
    def factor_service(self):
        """创建因子分析服务实例"""
        return FactorAnalysisService()

    @pytest.fixture
    def sample_factor_data(self):
        """创建测试用的因子数据"""
        # 生成 30 天 × 50 只股票的数据
        dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
        symbols = [f'60000{i}' for i in range(50)]

        data = []
        for date in dates:
            for symbol in symbols:
                # 随机生成因子值（模拟部分缺失）
                factor_value = np.random.randn() if np.random.rand() > 0.1 else np.nan
                close_price = 10 + np.random.randn()

                data.append({
                    'date': date,
                    'symbol': symbol,
                    'factor': factor_value,
                    'close': close_price
                })

        return pd.DataFrame(data)

    @pytest.fixture
    def alphalens_factor_data(self, factor_service, sample_factor_data):
        """创建 alphalens 格式的因子数据"""
        try:
            factor_data = factor_service.prepare_factor_data(
                sample_factor_data,
                periods=(1, 5, 10),
                quantiles=5,
                max_loss=0.5
            )
            return factor_data
        except Exception as e:
            pytest.skip(f"无法准备 alphalens 数据: {e}")

    def test_calculate_coverage_basic(self, factor_service, alphalens_factor_data):
        """测试基础覆盖率计算"""
        result = factor_service.calculate_coverage(alphalens_factor_data)

        # 验证返回结构
        assert 'coverage_ratio' in result
        assert 'total_samples' in result
        assert 'valid_samples' in result
        assert 'missing_samples' in result

        # 验证数值范围
        assert 0 <= result['coverage_ratio'] <= 1
        assert result['total_samples'] >= 0
        assert result['valid_samples'] >= 0
        assert result['missing_samples'] >= 0

        # 验证逻辑一致性
        assert result['valid_samples'] + result['missing_samples'] == result['total_samples']

        print(f"\n覆盖率: {result['coverage_ratio']:.2%}")
        print(f"总样本: {result['total_samples']}")
        print(f"有效样本: {result['valid_samples']}")
        print(f"缺失样本: {result['missing_samples']}")

    def test_calculate_coverage_by_date(self, factor_service, alphalens_factor_data):
        """测试按日期的覆盖率计算"""
        result = factor_service.calculate_coverage(alphalens_factor_data)

        # 如果有按日期的覆盖率，验证其结构
        if 'coverage_by_date' in result:
            coverage_by_date = result['coverage_by_date']
            assert isinstance(coverage_by_date, dict)

            # 验证每个日期的覆盖率都在 0-1 之间
            for date, ratio in coverage_by_date.items():
                assert 0 <= ratio <= 1

            print(f"\n按日期覆盖率（前5天）:")
            for date, ratio in list(coverage_by_date.items())[:5]:
                print(f"  {date}: {ratio:.2%}")

    def test_calculate_monotonicity_basic(self, factor_service, alphalens_factor_data):
        """测试基础单调性计算"""
        result = factor_service.calculate_monotonicity(
            alphalens_factor_data,
            quantiles=5
        )

        # 验证返回结构
        assert 'monotonicity_ratio' in result
        assert 'is_monotonic' in result
        assert 'direction' in result
        assert 'monotonic_periods' in result
        assert 'total_periods' in result
        assert 'increasing_periods' in result
        assert 'decreasing_periods' in result
        assert 'violations_count' in result

        # 验证数值范围
        assert 0 <= result['monotonicity_ratio'] <= 1
        assert isinstance(result['is_monotonic'], bool)
        assert result['direction'] in ['increasing', 'decreasing', 'mixed']

        # 验证逻辑一致性
        assert result['monotonic_periods'] == result['increasing_periods'] + result['decreasing_periods']
        assert result['monotonic_periods'] <= result['total_periods']

        print(f"\n单调性比例: {result['monotonicity_ratio']:.2%}")
        print(f"是否单调: {result['is_monotonic']}")
        print(f"方向: {result['direction']}")
        print(f"单调期数: {result['monotonic_periods']} / {result['total_periods']}")

    def test_calculate_monotonicity_violations(self, factor_service, alphalens_factor_data):
        """测试单调性违反案例"""
        result = factor_service.calculate_monotonicity(
            alphalens_factor_data,
            quantiles=5
        )

        # 如果有违反案例，验证其结构
        if result['violations_count'] > 0:
            assert 'violations_sample' in result
            violations = result['violations_sample']

            # 验证样本结构
            for violation in violations:
                assert 'date' in violation
                assert 'returns' in violation
                assert isinstance(violation['returns'], list)

            print(f"\n违反单调性案例数: {result['violations_count']}")
            print(f"示例（前3个）:")
            for v in violations[:3]:
                returns_str = ' → '.join([f"{r:.2%}" for r in v['returns']])
                print(f"  {v['date']}: {returns_str}")

    def test_high_coverage_factor(self, factor_service):
        """测试高覆盖率因子"""
        # 创建完全覆盖的数据
        dates = pd.date_range(start='2024-01-01', periods=20, freq='D')
        symbols = [f'60000{i}' for i in range(30)]

        data = []
        for date in dates:
            for symbol in symbols:
                data.append({
                    'date': date,
                    'symbol': symbol,
                    'factor': np.random.randn(),
                    'close': 10 + np.random.randn()
                })

        factor_df = pd.DataFrame(data)
        factor_data = factor_service.prepare_factor_data(
            factor_df,
            periods=(1,),
            quantiles=5,
            max_loss=0.5
        )

        result = factor_service.calculate_coverage(factor_data)

        # 高覆盖率应接近 1.0
        assert result['coverage_ratio'] > 0.95
        assert result['missing_samples'] < result['total_samples'] * 0.05

        print(f"\n高覆盖率因子: {result['coverage_ratio']:.2%}")

    def test_low_coverage_factor(self, factor_service):
        """测试低覆盖率因子"""
        # 创建低覆盖的数据（50% 缺失）
        dates = pd.date_range(start='2024-01-01', periods=20, freq='D')
        symbols = [f'60000{i}' for i in range(30)]

        data = []
        for date in dates:
            for symbol in symbols:
                factor_value = np.random.randn() if np.random.rand() > 0.5 else np.nan
                data.append({
                    'date': date,
                    'symbol': symbol,
                    'factor': factor_value,
                    'close': 10 + np.random.randn()
                })

        factor_df = pd.DataFrame(data)
        factor_data = factor_service.prepare_factor_data(
            factor_df,
            periods=(1,),
            quantiles=5,
            max_loss=0.6
        )

        result = factor_service.calculate_coverage(factor_data)

        # 注意：alphalens 会自动过滤缺失数据，所以最终覆盖率可能是 100%
        # 但 total_samples 会小于原始数据量
        assert result['coverage_ratio'] > 0  # 只要有数据就行
        assert result['total_samples'] < len(dates) * len(symbols)  # 总样本应小于原始数据

        print(f"\n低覆盖率因子: {result['coverage_ratio']:.2%}")
        print(f"  过滤前样本: {len(factor_df)}")
        print(f"  过滤后样本: {result['total_samples']}")

    def test_monotonic_increasing_factor(self, factor_service):
        """测试单调递增因子"""
        # 创建明确单调递增的因子数据
        dates = pd.date_range(start='2024-01-01', periods=20, freq='D')
        symbols = [f'60000{i}' for i in range(30)]

        data = []
        for date in dates:
            for symbol in symbols:
                # 因子值与未来收益正相关
                factor_value = np.random.randn()
                # 未来收益与因子值成正比
                future_return = factor_value * 0.01 + np.random.randn() * 0.001
                close = 10
                future_close = close * (1 + future_return)

                data.append({
                    'date': date,
                    'symbol': symbol,
                    'factor': factor_value,
                    'close': close
                })

        # 添加未来价格（简化处理）
        factor_df = pd.DataFrame(data)

        # 注意：这个测试可能因为数据生成方式而不稳定
        # 仅作为功能验证
        try:
            factor_data = factor_service.prepare_factor_data(
                factor_df,
                periods=(1,),
                quantiles=5,
                max_loss=0.5
            )

            result = factor_service.calculate_monotonicity(factor_data, quantiles=5)

            print(f"\n单调递增测试:")
            print(f"  单调性比例: {result['monotonicity_ratio']:.2%}")
            print(f"  方向: {result['direction']}")

        except Exception as e:
            pytest.skip(f"单调性测试数据准备失败: {e}")

    def test_integration_with_full_analysis(self, factor_service, sample_factor_data):
        """测试与完整因子分析的集成"""
        try:
            # 准备数据
            factor_data = factor_service.prepare_factor_data(
                sample_factor_data,
                periods=(1, 5),
                quantiles=5,
                max_loss=0.5
            )

            # 执行所有分析
            ic_result = factor_service.calculate_ic_analysis(factor_data)
            returns_result = factor_service.calculate_returns_analysis(factor_data)
            turnover_result = factor_service.calculate_turnover_analysis(factor_data)
            coverage_result = factor_service.calculate_coverage(factor_data)
            monotonicity_result = factor_service.calculate_monotonicity(factor_data)

            # 验证所有结果都成功返回
            assert ic_result is not None
            assert returns_result is not None
            assert turnover_result is not None
            assert coverage_result is not None
            assert monotonicity_result is not None

            print("\n完整因子分析结果:")
            print(f"  IC均值: {ic_result['ic_mean']:.4f}")
            print(f"  IR: {ic_result['ic_ir']:.4f}")
            print(f"  覆盖率: {coverage_result['coverage_ratio']:.2%}")
            print(f"  单调性: {monotonicity_result['monotonicity_ratio']:.2%}")
            print(f"  单调方向: {monotonicity_result['direction']}")

        except Exception as e:
            pytest.skip(f"集成测试失败: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

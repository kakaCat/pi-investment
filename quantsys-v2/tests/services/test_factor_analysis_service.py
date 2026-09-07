"""
因子分析服务测试
"""
import pytest
import pandas as pd
import numpy as np
from application.services.factor_analysis_service import FactorAnalysisService, ALPHALENS_AVAILABLE


@pytest.fixture
def factor_service():
    """创建因子分析服务实例"""
    return FactorAnalysisService()


@pytest.fixture
def sample_factor_data():
    """生成样本因子数据"""
    np.random.seed(42)

    symbols = ['600000.SH', '600519.SH', '000001.SZ']
    dates = pd.date_range('2024-01-01', periods=50, freq='D')

    data = []
    for symbol in symbols:
        for date in dates:
            data.append({
                'symbol': symbol,
                'date': date.strftime('%Y-%m-%d'),
                'factor': np.random.randn(),  # 随机因子值
                'close': 10 + np.random.randn() * 2  # 随机价格
            })

    return pd.DataFrame(data)


@pytest.fixture
def sample_prices_data(sample_factor_data):
    """从因子数据中提取价格数据"""
    return sample_factor_data[['symbol', 'date', 'close']].copy()


class TestFactorAnalysisService:
    """因子分析服务测试套件"""

    def test_service_initialization(self, factor_service):
        """测试服务初始化"""
        assert factor_service is not None
        assert isinstance(factor_service, FactorAnalysisService)

    @pytest.mark.skipif(not ALPHALENS_AVAILABLE, reason="alphalens not available")
    def test_prepare_factor_data(self, factor_service, sample_factor_data):
        """测试因子数据准备"""
        factor_data = factor_service.prepare_factor_data(
            sample_factor_data,
            periods=(1, 5)
        )

        assert factor_data is not None
        assert isinstance(factor_data, pd.DataFrame)
        assert len(factor_data) > 0

        # 检查列是否包含期望的前瞻收益列
        assert any('1D' in str(col) for col in factor_data.columns)

    @pytest.mark.skipif(not ALPHALENS_AVAILABLE, reason="alphalens not available")
    def test_prepare_factor_data_with_separate_prices(
        self,
        factor_service,
        sample_factor_data,
        sample_prices_data
    ):
        """测试使用单独价格数据准备因子数据"""
        # 从 factor_data 中移除 close 列
        factor_only = sample_factor_data[['symbol', 'date', 'factor']].copy()

        factor_data = factor_service.prepare_factor_data(
            factor_only,
            prices_df=sample_prices_data,
            periods=(1, 5)
        )

        assert factor_data is not None
        assert len(factor_data) > 0

    def test_validate_factor_data_missing_columns(self, factor_service):
        """测试缺少必需列的验证"""
        invalid_df = pd.DataFrame({
            'symbol': ['600000.SH'],
            'date': ['2024-01-01']
            # 缺少 'factor' 列
        })

        with pytest.raises(ValueError, match="缺少必需列"):
            factor_service._validate_factor_data(invalid_df)

    def test_validate_factor_data_empty(self, factor_service):
        """测试空数据验证"""
        empty_df = pd.DataFrame(columns=['symbol', 'date', 'factor'])

        with pytest.raises(ValueError, match="不能为空"):
            factor_service._validate_factor_data(empty_df)

    def test_validate_factor_data_all_nan(self, factor_service):
        """测试全 NaN 因子值验证"""
        nan_df = pd.DataFrame({
            'symbol': ['600000.SH', '600519.SH'],
            'date': ['2024-01-01', '2024-01-02'],
            'factor': [np.nan, np.nan]
        })

        with pytest.raises(ValueError, match="全部为 NaN"):
            factor_service._validate_factor_data(nan_df)

    @pytest.mark.skipif(not ALPHALENS_AVAILABLE, reason="alphalens not available")
    def test_calculate_ic_analysis(self, factor_service, sample_factor_data):
        """测试 IC 分析"""
        # 准备数据
        factor_data = factor_service.prepare_factor_data(
            sample_factor_data,
            periods=(1, 5)
        )

        # 计算 IC
        ic_result = factor_service.calculate_ic_analysis(factor_data)

        # 验证结果
        assert 'ic_mean' in ic_result
        assert 'ic_std' in ic_result
        assert 'ic_ir' in ic_result
        assert 'ic_series' in ic_result
        assert 't_stat' in ic_result
        assert 'p_value' in ic_result

        # 检查值的合理性
        assert isinstance(ic_result['ic_mean'], float)
        assert isinstance(ic_result['ic_std'], float)
        assert isinstance(ic_result['ic_ir'], float)
        assert isinstance(ic_result['ic_series'], dict)

    @pytest.mark.skipif(not ALPHALENS_AVAILABLE, reason="alphalens not available")
    def test_calculate_returns_analysis(self, factor_service, sample_factor_data):
        """测试分层收益分析"""
        # 准备数据
        factor_data = factor_service.prepare_factor_data(
            sample_factor_data,
            periods=(1, 5)
        )

        # 计算分层收益
        returns_result = factor_service.calculate_returns_analysis(
            factor_data,
            quantiles=5
        )

        # 验证结果
        assert 'mean_return_by_quantile' in returns_result
        assert 'mean_return_spread' in returns_result
        assert 'quantiles' in returns_result

        assert returns_result['quantiles'] == 5
        assert isinstance(returns_result['mean_return_by_quantile'], dict)
        assert isinstance(returns_result['mean_return_spread'], dict)

    @pytest.mark.skipif(not ALPHALENS_AVAILABLE, reason="alphalens not available")
    def test_calculate_turnover_analysis(self, factor_service, sample_factor_data):
        """测试换手率分析"""
        # 准备数据
        factor_data = factor_service.prepare_factor_data(
            sample_factor_data,
            periods=(1, 5)
        )

        # 计算换手率
        turnover_result = factor_service.calculate_turnover_analysis(factor_data)

        # 验证结果
        assert 'mean_turnover' in turnover_result
        assert 'autocorrelation' in turnover_result

        assert isinstance(turnover_result['mean_turnover'], float)
        assert isinstance(turnover_result['autocorrelation'], dict)

        # 换手率可能超过 1（当自相关性为负时）
        # 只验证不是 NaN
        assert not np.isnan(turnover_result['mean_turnover'])

    @pytest.mark.skipif(not ALPHALENS_AVAILABLE, reason="alphalens not available")
    def test_calculate_factor_correlation(self, factor_service, sample_factor_data):
        """测试因子相关性矩阵"""
        # 准备两个不同的因子
        factor_data_1 = factor_service.prepare_factor_data(
            sample_factor_data,
            periods=(1,)
        )

        # 创建第二个因子（稍微修改一下）
        factor_data_2_df = sample_factor_data.copy()
        factor_data_2_df['factor'] = factor_data_2_df['factor'] * 0.5 + np.random.randn(len(factor_data_2_df)) * 0.5

        factor_data_2 = factor_service.prepare_factor_data(
            factor_data_2_df,
            periods=(1,)
        )

        # 计算相关性
        factors = {
            'factor_1': factor_data_1,
            'factor_2': factor_data_2
        }

        corr_matrix = factor_service.calculate_factor_correlation(factors)

        # 验证结果
        assert isinstance(corr_matrix, pd.DataFrame)
        assert corr_matrix.shape == (2, 2)

        # 对角线应该是 1（自相关）
        assert abs(corr_matrix.loc['factor_1', 'factor_1'] - 1.0) < 0.01
        assert abs(corr_matrix.loc['factor_2', 'factor_2'] - 1.0) < 0.01

    def test_create_factor_series(self, factor_service, sample_factor_data):
        """测试因子 Series 创建"""
        factor_series = factor_service._create_factor_series(sample_factor_data)

        assert isinstance(factor_series, pd.Series)
        assert factor_series.index.names == ['date', 'symbol']
        assert len(factor_series) == len(sample_factor_data)

    def test_create_prices_dataframe(self, factor_service, sample_prices_data):
        """测试价格 DataFrame 创建"""
        prices_df = factor_service._create_prices_dataframe(sample_prices_data)

        assert isinstance(prices_df, pd.DataFrame)
        assert prices_df.index.name == 'date'

        # 列应该是股票代码
        symbols = sample_prices_data['symbol'].unique()
        for symbol in symbols:
            assert symbol in prices_df.columns


class TestEdgeCases:
    """边界情况测试"""

    def test_alphalens_not_available(self, factor_service, sample_factor_data):
        """测试 alphalens 不可用时的行为"""
        if ALPHALENS_AVAILABLE:
            pytest.skip("alphalens is available, skipping this test")

        with pytest.raises(ImportError, match="alphalens not available"):
            factor_service.prepare_factor_data(sample_factor_data)

    @pytest.mark.skipif(not ALPHALENS_AVAILABLE, reason="alphalens not available")
    def test_small_dataset(self, factor_service):
        """测试小数据集"""
        # 只有 5 天 × 2 只股票
        small_data = pd.DataFrame({
            'symbol': ['600000.SH'] * 5 + ['600519.SH'] * 5,
            'date': pd.date_range('2024-01-01', periods=5).tolist() * 2,
            'factor': np.random.randn(10),
            'close': 10 + np.random.randn(10)
        })
        small_data['date'] = small_data['date'].dt.strftime('%Y-%m-%d')

        # 应该能处理（尽管结果可能不可靠）
        factor_data = factor_service.prepare_factor_data(small_data, periods=(1,))
        assert len(factor_data) > 0

    @pytest.mark.skipif(not ALPHALENS_AVAILABLE, reason="alphalens not available")
    def test_missing_prices(self, factor_service):
        """测试价格缺失"""
        data = pd.DataFrame({
            'symbol': ['600000.SH'] * 10,
            'date': pd.date_range('2024-01-01', periods=10).astype(str).tolist(),
            'factor': np.random.randn(10),
            'close': [10, 11, np.nan, 13, 14, np.nan, 16, 17, 18, 19]
        })

        # alphalens 应该能处理缺失价格（会跳过）
        # 对边界情况使用更高的 max_loss 容忍度
        factor_data = factor_service.prepare_factor_data(data, periods=(1,), max_loss=1.0)
        # 不应该抛出异常
        assert factor_data is not None

    @pytest.mark.skipif(not ALPHALENS_AVAILABLE, reason="alphalens not available")
    def test_constant_factor(self, factor_service):
        """测试恒定因子值"""
        data = pd.DataFrame({
            'symbol': ['600000.SH'] * 10 + ['600519.SH'] * 10,
            'date': pd.date_range('2024-01-01', periods=10).tolist() * 2,
            'factor': [1.0] * 20,  # 恒定因子值
            'close': 10 + np.random.randn(20)
        })
        data['date'] = data['date'].dt.strftime('%Y-%m-%d')

        # 对恒定因子使用更高的 max_loss 容忍度
        factor_data = factor_service.prepare_factor_data(data, periods=(1,), max_loss=1.0)

        # IC 应该是 NaN 或接近 0（因为没有变化）
        ic_result = factor_service.calculate_ic_analysis(factor_data)
        # 不应该抛出异常
        assert 'ic_mean' in ic_result
